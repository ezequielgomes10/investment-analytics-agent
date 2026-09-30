"""Coleta auditável: python -m src.update_data [--offline]. HTTPS validado pelo sistema."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from time import monotonic

import argparse
import csv
import hashlib
import io
import json
import os
import ssl
import re
import tempfile
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

import truststore

DATA = Path(__file__).resolve().parents[1] / "data"
# Fuso civil utilizado pelo projeto; não depende de tzdata no Windows.
BRASILIA = timezone(timedelta(hours=-3))
UNITS = {"cdi_12": "pct_ao_dia", "selic_11": "pct_ao_dia", "selic_meta_432": "pct_ao_ano",
         "poupanca_195": "pct_no_periodo_informado", "ipca_433": "pct_no_mes",
         "tesouro_manha": "taxa_titulo_pct_ao_ano_e_preco_brl"}
RAW_FILES = {"selic_11": "selic_11.csv", "poupanca_195": "poupanca_195.csv",
             "tesouro_manha": "tesouro_taxas_precos.csv"}
TREASURY_COLUMNS = ["Tipo Titulo", "Data Vencimento", "Data Base", "Taxa Compra Manha",
                    "Taxa Venda Manha", "PU Compra Manha", "PU Venda Manha", "PU Base Manha"]
TREASURY_VALUES = ["taxa_compra_manha_pct_aa", "taxa_venda_manha_pct_aa",
                   "pu_compra_manha_brl", "pu_venda_manha_brl", "pu_base_manha_brl"]


def reference_day():
    return datetime.now(BRASILIA).date()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def atomic_bytes(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".iaa_", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def update_lock(data):
    data.mkdir(parents=True, exist_ok=True)
    lock = data / ".update.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as error:
        raise RuntimeError("Atualização em andamento. Se o processo caiu, confira antes de remover data/.update.lock.") from error
    try:
        os.close(descriptor)
        yield
    finally:
        lock.unlink()


def number(raw, *, positive=False):
    if isinstance(raw, bool) or not isinstance(raw, (str, int, float, Decimal)):
        raise ValueError("Valor numérico ausente ou de tipo inválido")
    representation = str(raw).strip()
    if len(representation) > 100:
        raise ValueError("Número excede a precisão suportada")
    if "," in representation:
        if not re.fullmatch(r"[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+),\d+", representation):
            raise ValueError("Decimal brasileiro inválido")
        representation = representation.replace(".", "").replace(",", ".")
    try:
        value = Decimal(representation)
    except InvalidOperation as error:
        raise ValueError("Número inválido") from error
    if not value.is_finite() or (positive and value <= 0):
        raise ValueError("Número fora do domínio")
    if abs(value.as_tuple().exponent) > 100 or abs(value.adjusted()) > 100:
        raise ValueError("Número excede a precisão suportada")
    return format(value, "f")


def parsed_date(raw, today, *, future=False):
    if not isinstance(raw, str):
        raise ValueError("Data ausente ou de tipo inválido")
    value = datetime.strptime(raw.strip(), "%d/%m/%Y").date()
    if not future and value > today:
        raise ValueError("Data de referência futura")
    return value.isoformat()


def csv_rows(payload, expected):
    reader = csv.DictReader(io.StringIO(payload.decode("utf-8-sig")), delimiter=";")
    if reader.fieldnames != expected:
        raise ValueError("Cabeçalho CSV inesperado")
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("Linha CSV incompleta ou com colunas extras")
        yield row


def parse_bcb(payload, source, today, *, local=False):
    identifier = source["id"]
    required = ["data", "dataFim", "valor"] if identifier == "poupanca_195" else ["data", "valor"]
    raw_rows = list(csv_rows(payload, required)) if local else json.loads(payload)
    if not isinstance(raw_rows, list) or not raw_rows:
        raise ValueError("BCB deve retornar uma lista não vazia")
    rows, seen = [], set()
    for raw in raw_rows:
        if not isinstance(raw, dict) or any(key not in raw for key in required):
            raise ValueError("Registro BCB incompleto: " + ", ".join(required))
        start = parsed_date(raw["data"], today)
        end = parsed_date(raw["dataFim"], today, future=True) if identifier == "poupanca_195" else None
        if end and end <= start:
            raise ValueError("Período da poupança inconsistente")
        amount = number(raw["valor"])
        value = Decimal(amount)
        lower, upper = ((0, 1) if identifier in ("selic_11", "cdi_12") else
                        (-100, 100) if identifier == "ipca_433" else (0, 100))
        if not lower <= value < upper:
            raise ValueError("Valor fora do intervalo técnico configurado")
        key = (start, end)
        if key in seen:
            raise ValueError("Observação duplicada")
        seen.add(key)
        rows.append({"indicador": identifier, "data_referencia": start, "data_fim": end,
                     "valor_pct": amount, "unidade": source["unidade"]})
    return sorted(rows, key=lambda row: row["data_referencia"])


def parse_treasury(payload, source, today):
    # Primeiro identifica a data máxima. A validação numérica é do recorte,
    # independente da ordem do CSV; preços antigos zerados ficam no bruto.
    newest = None
    selected = []
    for raw in csv_rows(payload, TREASURY_COLUMNS):
        reference = parsed_date(raw["Data Base"], today)
        if newest is None or reference > newest:
            newest, selected = reference, [raw]
        elif reference == newest:
            selected.append(raw)
    if not selected:
        raise ValueError("Tesouro sem registros")
    rows, seen = [], set()
    for raw in selected:
        expiry = parsed_date(raw["Data Vencimento"], today, future=True)
        name = raw["Tipo Titulo"].strip()
        if not name or expiry <= newest:
            raise ValueError("Título ou vencimento inválido")
        key = (name, expiry)
        if key in seen:
            raise ValueError("Título duplicado na última data")
        seen.add(key)
        row = {"produto": name, "data_referencia": newest, "data_vencimento": expiry}
        for original, normalized in zip(TREASURY_COLUMNS[3:], TREASURY_VALUES):
            row[normalized] = number(raw[original], positive=original.startswith("PU"))
        rows.append(row)
    return sorted(rows, key=lambda row: (row["produto"], row["data_vencimento"]))


def fetch(source, timeout):
    limit = source.get("limite_download_bytes", 2_000_000)
    request = Request(source["url"], headers={"User-Agent": "IAA-data-lab/2.0"})
    # Usa as autoridades confiáveis do sistema, mantendo verificação de cadeia e hostname.
    started = monotonic()
    with urlopen(request, timeout=timeout, context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)) as response:
        chunks, size = [], 0
        while size <= limit:
            if monotonic() - started >= timeout:
                raise TimeoutError("Tempo de download excedido")
            chunk = response.read1(min(65536, limit + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        payload = b"".join(chunks)
    if len(payload) > limit:
        raise ValueError("Resposta excedeu o limite de tamanho")
    return payload


def source_for_date(source, today):
    """Limita séries com janela configurada à data real da análise."""
    if "janela_dias" not in source:
        return source
    days = source["janela_dias"]
    if type(days) is not int or not 1 <= days <= 3650:
        raise ValueError("Janela de consulta inválida")
    parameters = urlencode({"dataInicial": (today - timedelta(days=days - 1)).strftime("%d/%m/%Y"),
                            "dataFinal": today.strftime("%d/%m/%Y")})
    return {**source, "url": source["url"] + ("&" if "?" in source["url"] else "?") + parameters}


def load_registry(data):
    registry = json.loads((data / "fontes.json").read_text(encoding="utf-8"))
    seen = set()
    for source in registry["fontes"]:
        identifier = source["id"]
        if identifier in seen or identifier not in UNITS:
            raise ValueError("Fonte duplicada ou sem parser implementado")
        seen.add(identifier)
        if source["unidade"] != UNITS[identifier]:
            raise ValueError("Unidade incompatível com o parser da fonte")
        if not source["url"].startswith("https://") or not 0 <= source["defasagem_maxima_dias"] <= 90:
            raise ValueError("URL ou defasagem inválida")
    if not seen:
        raise ValueError("Cadastro de fontes vazio")
    return registry


def read_snapshot(data_dir=DATA, execution_id=None):
    """Lê uma execução íntegra. Falha explícita evita usar estado adulterado."""
    data = Path(data_dir)
    if execution_id is None:
        pointer = data / "processed/snapshot_atual.json"
        if not pointer.exists():
            return None
        entry = json.loads(pointer.read_text(encoding="utf-8"))
        execution_id = entry["execucao_id"]
    else:
        entry = None
    if not re.fullmatch(r"[a-f0-9]{32}", execution_id):
        raise ValueError("Identificador de execução inválido")
    payload = (data / "processed/execucoes" / f"{execution_id}.json").read_bytes()
    if entry and digest(payload) != entry["sha256"]:
        raise ValueError("Hash da execução não confere; atualização interrompida")
    snapshot = json.loads(payload)
    if snapshot["execucao_id"] != execution_id or snapshot["versao_schema"] != 1:
        raise ValueError("Snapshot incompatível")
    content = {key: value for key, value in snapshot.items() if key != "sha256_conteudo"}
    if digest(json_bytes(content)) != snapshot.get("sha256_conteudo"):
        raise ValueError("Conteúdo da execução arquivada não confere")
    return snapshot


def static_knowledge(data, registry):
    files = {"catalogo": "catalogo_produtos.json", "tributacao": "regras_tributarias.json",
             "escopo": "escopo_comparacao.json", "documentos": "docs/risco_liquidez_garantias.md",
             "ofertas_csv": "ofertas_renda_fixa.csv"}
    result = {"fontes": registry, "hashes": {"fontes.json": digest((data / "fontes.json").read_bytes())}}
    for key, filename in files.items():
        payload = (data / filename).read_bytes()
        result["hashes"][filename] = digest(payload)
        text = payload.decode("utf-8-sig")
        result[key] = json.loads(text) if filename.endswith(".json") else text
    additional = data / "fontes_complementares.json"
    if additional.exists():
        payload = additional.read_bytes()
        result["fontes_complementares"] = json.loads(payload)
        result["hashes"]["fontes_complementares.json"] = digest(payload)
    products = result["catalogo"]["produtos"]
    rules = result["tributacao"]["regras"]
    product_ids = [product["id"] for product in products]
    rule_ids = [rule["id"] for rule in rules]
    if len(set(product_ids)) != len(product_ids) or len(set(rule_ids)) != len(rule_ids):
        raise ValueError("IDs duplicados na base conceitual")
    for product in products:
        if product["tributacao_id"] not in rule_ids or product["taxa_atual"] is not None:
            raise ValueError("Vínculo tributário inválido ou taxa corrente no catálogo")
    if set(result["escopo"]["produtos"]) != set(product_ids):
        raise ValueError("Escopo e catálogo incompatíveis")
    return result


def evidence(data, payload, *, identifier, local, now, source):
    sha = digest(payload)
    # Também arquiva o original por hash: a evidência independe de alterações
    # posteriores no arquivo de entrada ou no manifesto.
    extension = "csv" if local or identifier == "tesouro_manha" else "json"
    extension = {"anbima":"xls", "documental":"html"}.get(source.get("tipo"), extension)
    relative = f"raw/evidencias/{sha}.{extension}"
    path = data / relative
    if path.exists():
        if digest(path.read_bytes()) != sha:
            raise ValueError("Evidência existente com hash inválido")
    else:
        atomic_bytes(path, payload)
    return {"arquivo": relative, "sha256": sha,
            "origem": "historico_local" if local else "consulta_url",
            "url_consultada": None if local else source["url"],
            "fonte_documental": source["documentacao"],
            "consultado_em": None if local else now,
            "importado_em": now if local else None}


def make_dataset(data, payload, source, today, now, *, local):
    identifier = source["id"]
    rows = (parse_treasury(payload, source, today) if identifier == "tesouro_manha"
            else parse_bcb(payload, source, today, local=local))
    proof = evidence(data, payload, identifier=identifier, local=local, now=now, source=source)
    return {"data_referencia": max(row["data_referencia"] for row in rows),
            "registros": rows, "evidencia": proof}


def update(*, offline=False, timeout=20, data_dir=DATA):
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 60:
        raise ValueError("Timeout deve ser inteiro entre 1 e 60 segundos")
    data = Path(data_dir)
    with update_lock(data):
        return _update(data, offline=offline, timeout=timeout)


def _update(data, *, offline, timeout):
    registry = load_registry(data)
    knowledge = static_knowledge(data, registry)
    previous = read_snapshot(data) or {"fontes": {}, "historico_indicadores": []}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    today = reference_day()
    history = {(r["indicador"], r["data_referencia"], r["data_fim"]): r
               for r in previous["historico_indicadores"]}
    downloads = {}
    if not offline:
        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {source["id"]: pool.submit(fetch, source_for_date(source, today), timeout)
                       for source in registry["fontes"]}
            for identifier, future in futures.items():
                try:
                    downloads[identifier] = future.result()
                except Exception as error:
                    downloads[identifier] = error
    statuses = {}
    for source in registry["fontes"]:
        identifier = source["id"]
        last = previous["fontes"].get(identifier, {}).get("ultimo_dado_valido")
        status = {"estado": "sem_dados", "tentativa_em": None,
                  "unidade": source["unidade"], "url_configurada": source["url"],
                  "utilizavel_como_dado_publicado_recente": False,
                  "erro": None, "erro_historico_local": None}
        if last is None and identifier in RAW_FILES:
            local = data / "raw" / RAW_FILES[identifier]
            if local.exists():
                try:
                    last = make_dataset(data, local.read_bytes(), source, today, now, local=True)
                except (OSError, ValueError, UnicodeError, csv.Error) as error:
                    status["erro_historico_local"] = f"{type(error).__name__}: {error}"
        if offline:
            status["estado"] = "apenas_historico" if last else "sem_dados"
        else:
            status["tentativa_em"] = now
            try:
                requested_source = source_for_date(source, today)
                payload = downloads[identifier]
                if isinstance(payload, Exception):
                    raise payload
                current = make_dataset(data, payload, requested_source, today,
                                       status["tentativa_em"], local=False)
                if last and current["data_referencia"] < last["data_referencia"]:
                    raise ValueError("Fonte retornou publicação anterior ao último dado válido")
                last = current
                age = (today - date.fromisoformat(last["data_referencia"])).days
                recent = 0 <= age <= source["defasagem_maxima_dias"]
                status.update(estado="publicacao_recente" if recent else "publicacao_defasada",
                              utilizavel_como_dado_publicado_recente=recent)
            except (OSError, ValueError, UnicodeError, csv.Error) as error:
                status.update(estado="consulta_falhou", erro=f"{type(error).__name__}: {str(error)[:240]}",
                              utilizavel_como_dado_publicado_recente=False)
        status["ultimo_dado_valido"] = last
        if last and identifier != "tesouro_manha":
            for row in last["registros"]:
                key = (identifier, row["data_referencia"], row["data_fim"])
                history[key] = {**row, "evidencia": last["evidencia"]}
        statuses[identifier] = status
    from .market_sources import collect
    additional = collect(knowledge.get("fontes_complementares", {}), previous.get("fontes_complementares", {}),
                         offline=offline, today=today, now=now, timeout=timeout, fetch=fetch,
                         evidence=evidence, data=data)
    execution_id = uuid.uuid4().hex
    snapshot = {"versao_schema": 1, "execucao_id": execution_id, "iniciado_em": now,
                "concluido_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "modo": "offline" if offline else "online", "fontes": statuses,
                "base_conceitual": knowledge, "fontes_complementares": additional,
                "historico_indicadores": sorted(history.values(), key=lambda row: (row["indicador"], row["data_referencia"], row["data_fim"] or "")),
                "nota": "Publicação recente é uma checagem de defasagem; não é oferta, disponibilidade de compra ou previsão."}
    snapshot["sha256_conteudo"] = digest(json_bytes(snapshot))
    payload = json_bytes(snapshot)
    # Um único commit: arquivos e contexto pertencem à mesma execução. Falha
    # de persistência propaga e deixa o ponteiro anterior intacto.
    atomic_bytes(data / "processed/execucoes" / f"{execution_id}.json", payload)
    atomic_bytes(data / "processed/snapshot_atual.json", json_bytes({"execucao_id": execution_id, "sha256": digest(payload)}))
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        snapshot = update(offline=args.offline, timeout=args.timeout)
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        parser.exit(2, f"Atualização não concluída: {error}\n")
    print("Execução:", snapshot["execucao_id"])
    for identifier, status in snapshot["fontes"].items():
        last = status["ultimo_dado_valido"]
        print(identifier, status["estado"], last["data_referencia"] if last else "sem dados", status["erro"] or status["erro_historico_local"] or "")
    for identifier, status in snapshot.get("fontes_complementares", {}).items():
        last = status.get("ultimo_dado_valido") or {}
        print(identifier, status["estado"], len(last.get("registros", [])), status.get("erro") or "")
    if any(s["erro"] or s["erro_historico_local"] for s in snapshot["fontes"].values()) or any(s.get("erro") for s in snapshot.get("fontes_complementares", {}).values()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
