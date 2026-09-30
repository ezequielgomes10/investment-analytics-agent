"""Regressões do fluxo da base; rede simulada e arquivos isolados por teste."""

import csv
import io
import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse, parse_qs

from src import data_access as access
from src import update_data as ingest

ROOT = Path(__file__).resolve().parents[1]


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        temp_root = ROOT / "tests/.tmp"
        temp_root.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="iaa_", dir=temp_root)
        self.data = Path(self.temp.name) / "data"
        self.data.mkdir()
        for filename in ("catalogo_produtos.json", "regras_tributarias.json", "fontes.json",
                         "ofertas_renda_fixa.csv", "escopo_comparacao.json"):
            shutil.copyfile(ROOT / "data" / filename, self.data / filename)
        shutil.copytree(ROOT / "data/docs", self.data / "docs")
        (self.data / "raw").mkdir()
        for filename in ("selic_11.csv", "poupanca_195.csv"):
            shutil.copyfile(ROOT / "data/raw" / filename, self.data / "raw" / filename)
        # O recorte real de 58 linhas é suficiente para exercitar o pipeline.
        self.treasury = b"\n".join((ROOT / "data/raw/tesouro_taxas_precos.csv").read_bytes().splitlines()[:59]) + b"\n"
        (self.data / "raw/tesouro_taxas_precos.csv").write_bytes(self.treasury)
        self.day = patch.object(ingest, "reference_day", return_value=date(2026, 9, 28))
        self.day.start()
        self.addCleanup(self.day.stop)
        self.addCleanup(self.cleanup_temp)

    def cleanup_temp(self):
        target = Path(self.temp.name).resolve()
        self.assertTrue(target.is_relative_to((ROOT / "tests/.tmp").resolve()))
        self.temp.cleanup()

    def fetch(self, source, timeout):
        identifier = source["id"]
        if identifier == "tesouro_manha":
            return self.treasury.replace(b"25/09/2026", b"28/09/2026")
        row = {"data": "28/09/2026", "valor": "0.05"}
        if identifier == "poupanca_195":
            row["dataFim"] = "28/10/2026"
        if identifier == "ipca_433":
            row["data"] = "01/08/2026"
        return json.dumps([row]).encode()

    def run_update(self, offline=False, fetch=None):
        with patch.object(ingest, "fetch", side_effect=fetch or self.fetch):
            return ingest.update(offline=offline, data_dir=self.data)

    def context(self, request=None, offline=False, **kwargs):
        with patch.object(ingest, "fetch", side_effect=self.fetch):
            return access.contexto_de_dados(request, offline=offline, data_dir=self.data, **kwargs)

    def test_decimal_preserva_escala_e_rejeita_numeros_invalidos(self):
        self.assertEqual(ingest.number("19.949,88"), "19949.88")
        self.assertEqual(ingest.number("0,050788"), "0.050788")
        self.assertEqual(ingest.number("0.050788"), "0.050788")
        for value in (True, None, [], "NaN", "Infinity", "1,2,3", "1.2,3"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ingest.number(value)

    def test_offline_sem_rede_sem_dados_falsamente_atuais(self):
        with patch.object(ingest, "fetch", side_effect=AssertionError("Não chamar rede")):
            result = ingest.update(offline=True, data_dir=self.data)
        self.assertEqual(len(result["historico_indicadores"]), 20)
        self.assertEqual(len(result["fontes"]["tesouro_manha"]["ultimo_dado_valido"]["registros"]), 58)
        self.assertEqual(result["fontes"]["ipca_433"]["estado"], "sem_dados")
        self.assertTrue(all(not s["utilizavel_como_dado_publicado_recente"] for s in result["fontes"].values()))

    def test_sucesso_seguido_de_falha_preserva_todas_as_fontes(self):
        first = self.run_update()
        second = self.run_update(fetch=OSError("sem rede"))
        for identifier in first["fontes"]:
            with self.subTest(source=identifier):
                before = first["fontes"][identifier]["ultimo_dado_valido"]
                after = second["fontes"][identifier]
                self.assertEqual(after["ultimo_dado_valido"], before)
                self.assertEqual(after["estado"], "consulta_falhou")
                self.assertFalse(after["utilizavel_como_dado_publicado_recente"])

    def test_offline_posterior_nao_regride_ao_original(self):
        first = self.run_update()
        second = self.run_update(offline=True)
        for identifier in first["fontes"]:
            self.assertEqual(second["fontes"][identifier]["ultimo_dado_valido"], first["fontes"][identifier]["ultimo_dado_valido"])
            self.assertFalse(second["fontes"][identifier]["utilizavel_como_dado_publicado_recente"])

    def test_resposta_incompleta_nao_interrompe_outras_fontes(self):
        def incomplete(source, timeout):
            if source["id"] == "poupanca_195":
                return b'[{"data":"28/09/2026","valor":"0.6"}]'
            return self.fetch(source, timeout)
        result = self.run_update(fetch=incomplete)
        self.assertEqual(result["fontes"]["poupanca_195"]["estado"], "consulta_falhou")
        self.assertTrue(result["fontes"]["tesouro_manha"]["utilizavel_como_dado_publicado_recente"])
        self.assertTrue(result["fontes"]["ipca_433"]["utilizavel_como_dado_publicado_recente"])

    def test_null_data_e_formato_errado_falham_por_fonte(self):
        for payload in (b'{"erro":"falha"}', b'[{"data":null,"valor":"0.1"}]', b'[{"data":"28/09/2026","valor":null}]'):
            with self.subTest(payload=payload):
                result = self.run_update(fetch=lambda source, timeout: payload)
                self.assertTrue(all(s["estado"] == "consulta_falhou" for s in result["fontes"].values()))

    def test_falha_de_evidencia_nao_libera_dado_e_preserva_anterior(self):
        before = self.run_update(offline=True)
        original = ingest.atomic_bytes
        def fail_evidence(path, payload):
            if "evidencias" in path.parts:
                raise OSError("disco indisponível")
            original(path, payload)
        with patch.object(ingest, "atomic_bytes", side_effect=fail_evidence):
            after = self.run_update()
        for identifier, status in after["fontes"].items():
            self.assertEqual(status["estado"], "consulta_falhou")
            self.assertFalse(status["utilizavel_como_dado_publicado_recente"])
            self.assertEqual(status["ultimo_dado_valido"], before["fontes"][identifier]["ultimo_dado_valido"])

    def test_falha_de_commit_preserva_snapshot_anterior(self):
        before = self.run_update()
        original = ingest.atomic_bytes
        def fail_pointer(path, payload):
            if path.name == "snapshot_atual.json":
                raise OSError("sem espaço")
            original(path, payload)
        with patch.object(ingest, "atomic_bytes", side_effect=fail_pointer), self.assertRaises(OSError):
            self.run_update()
        self.assertEqual(ingest.read_snapshot(self.data)["execucao_id"], before["execucao_id"])

    def test_publicacao_regressiva_nao_substitui_ultima_valida(self):
        first = self.run_update()
        def older(source, timeout):
            return self.fetch(source, timeout).replace(b"28/09/2026", b"24/09/2026").replace(b"01/08/2026", b"01/07/2026")
        second = self.run_update(fetch=older)
        for identifier in first["fontes"]:
            self.assertEqual(second["fontes"][identifier]["estado"], "consulta_falhou")
            self.assertEqual(second["fontes"][identifier]["ultimo_dado_valido"], first["fontes"][identifier]["ultimo_dado_valido"])

    def test_revisao_mesma_data_e_reproduzivel(self):
        first = self.run_update()
        def revised(source, timeout):
            return self.fetch(source, timeout).replace(b'"0.05"', b'"0.06"')
        second = self.run_update(fetch=revised)
        archived = ingest.read_snapshot(self.data, first["execucao_id"])
        self.assertEqual(archived["fontes"]["selic_11"]["ultimo_dado_valido"]["registros"][-1]["valor_pct"], "0.05")
        self.assertEqual(second["fontes"]["selic_11"]["ultimo_dado_valido"]["registros"][-1]["valor_pct"], "0.06")
        self.assertNotEqual(first["execucao_id"], second["execucao_id"])

    def test_defasagem_e_data_futura(self):
        source = ingest.load_registry(self.data)["fontes"][0]
        with self.assertRaises(ValueError):
            ingest.parse_bcb(b'[{"data":"29/09/2026","valor":"0.05"}]', source, date(2026, 9, 28))
        result = self.run_update(fetch=lambda source, timeout: self.fetch(source, timeout).replace(b"28/09/2026", b"01/09/2026").replace(b"01/08/2026", b"01/01/2026"))
        # A publicação regressiva pode falhar quando o arquivo local já é melhor.
        self.assertTrue(all(not status["utilizavel_como_dado_publicado_recente"] for status in result["fontes"].values()))
        self.assertEqual(result["fontes"]["ipca_433"]["estado"], "publicacao_defasada")

    def test_meta_selic_consulta_termina_na_data_da_analise(self):
        source = next(s for s in ingest.load_registry(self.data)["fontes"] if s["id"] == "selic_meta_432")
        bounded = ingest.source_for_date(source, date(2026, 9, 28))
        query = parse_qs(urlparse(bounded["url"]).query)
        self.assertEqual(query["dataFinal"], ["28/09/2026"])
        self.assertEqual(query["dataInicial"], ["30/08/2026"])
        result = self.run_update()
        proof = result["fontes"]["selic_meta_432"]["ultimo_dado_valido"]["evidencia"]
        self.assertEqual(proof["url_consultada"], bounded["url"])

    def test_duplicatas_e_unidade_errada_sao_rejeitadas(self):
        source = ingest.load_registry(self.data)["fontes"][0]
        row = {"data": "28/09/2026", "valor": "0.05"}
        with self.assertRaises(ValueError):
            ingest.parse_bcb(json.dumps([row, row]).encode(), source, date(2026, 9, 28))
        registry = ingest.load_registry(self.data)
        registry["fontes"][0]["unidade"] = "pct_ao_ano"
        (self.data / "fontes.json").write_bytes(ingest.json_bytes(registry))
        with self.assertRaises(ValueError):
            self.run_update()

    def test_tesouro_independente_da_ordem_e_sem_auditar_precos_antigos(self):
        lines = self.treasury.splitlines()
        old = lines[1].replace(b"25/09/2026", b"24/09/2026").split(b";")
        old[5] = b"0"
        payloads = [b"\n".join([lines[0], b";".join(old)] + lines[1:]),
                    b"\n".join(lines + [b";".join(old)])]
        source = ingest.load_registry(self.data)["fontes"][-1]
        self.assertEqual(ingest.parse_treasury(payloads[0], source, date(2026, 9, 28)),
                         ingest.parse_treasury(payloads[1], source, date(2026, 9, 28)))
        invalid_latest = lines[1].split(b";")
        invalid_latest[5] = b"0"
        with self.assertRaises(ValueError):
            ingest.parse_treasury(b"\n".join([lines[0], b";".join(invalid_latest)]), source, date(2026, 9, 28))

    def test_historico_local_invalido_nao_impede_coleta_online(self):
        (self.data / "raw/selic_11.csv").write_text("invalido", encoding="utf-8")
        result = self.run_update()
        self.assertTrue(result["fontes"]["selic_11"]["utilizavel_como_dado_publicado_recente"])
        self.assertIsNotNone(result["fontes"]["selic_11"]["erro_historico_local"])

    def test_contexto_filtra_modalidades_e_identifica_venda_antecipada(self):
        request = {"meta_brl": 15000, "saldo_inicial_brl": 5000, "aporte_mensal_brl": 2000,
                   "prazo_meses": 4, "necessita_resgate_antecipado": False}
        context = self.context(request)
        self.assertEqual(len(context["titulos_tesouro"]), 15)
        self.assertEqual(sum(context["titulos_excluidos_por_modalidade"].values()), 43)
        self.assertEqual(context["campos_faltantes"], [])
        self.assertTrue(any(t["exige_venda_antes_vencimento_na_meta"] for t in context["titulos_tesouro"]))
        self.assertTrue(any(t["vence_antes_da_meta_exige_premissa_reinvestimento"] for t in context["titulos_tesouro"]))
        for title in context["titulos_tesouro"]:
            self.assertEqual(title["exige_venda_antes_vencimento_na_meta"], title["data_vencimento"] > "2027-01-28")
        self.assertTrue(context["capacidades"]["entradas_para_planejamento_sem_rendimento_completas"])
        self.assertIn("selic_meta_432", context["indicadores_publicados_recentemente"])
        self.assertIn("FGC", context["conhecimento_documental"]["texto"])
        self.assertIn("validacao", context["tributacao"])
        self.assertFalse(context["tributacao"]["validacao"]["permite_calculo_liquido"])
        self.assertTrue(all(not p["comparacao_numerica_disponivel"] for p in context["disponibilidade_por_produto"]))

    def test_contexto_por_produto_nao_inclui_fontes_irrelevantes(self):
        context = self.context({"produtos": ["poupanca"]})
        self.assertEqual(list(context["fontes"]), ["poupanca_195"])
        self.assertEqual(context["titulos_tesouro"], [])
        self.assertEqual(len(context["tributacao"]["regras"]), 1)
        observation = context["indicadores_publicados_recentemente"]["poupanca_195"]
        self.assertFalse(observation["periodo_encerrado_na_data_da_analise"])

    def test_dados_pessoais_nao_sao_persistidos(self):
        context = self.context({"meta_brl": 987654.32}, offline=True)
        self.assertEqual(context["pedido"]["meta_brl"], "987654.32")
        snapshot = ingest.read_snapshot(self.data)
        self.assertNotIn("987654", json.dumps(snapshot))
        self.assertNotIn("pedido", snapshot)

    def test_pedido_invalido_nao_inicia_coleta(self):
        for request in ({"meta_brl": -1}, {"prazo_meses": True}, {"produtos": ["inexistente"]},
                        {"necessita_resgate_antecipado": "sim"}, {"saldo_inicial_brl": "NaN"},
                        {"prazo_meses": 4, "data_meta": "2027-01-01"}):
            with self.subTest(request=request), patch.object(ingest, "update") as update, self.assertRaises(ValueError):
                access.contexto_de_dados(request, data_dir=self.data)
            update.assert_not_called()

    def test_reproducao_preserva_base_e_nao_se_apresenta_como_atual(self):
        first = self.context()
        catalog = json.loads((self.data / "catalogo_produtos.json").read_text(encoding="utf-8"))
        catalog["versao"] = "versao_posterior"
        (self.data / "catalogo_produtos.json").write_bytes(ingest.json_bytes(catalog))
        with patch.object(ingest, "fetch", side_effect=AssertionError("Sem rede na reprodução")):
            replay = access.contexto_de_dados(data_dir=self.data, execucao_id=first["execucao_id"])
        self.assertEqual(replay["catalogo"]["versao"], first["catalogo"]["versao"])
        self.assertEqual(replay["indicadores_publicados_recentemente"], {})
        self.assertEqual(replay["modo"], "reproducao_historica")

    def test_lock_e_hash_impedem_estado_inconsistente(self):
        with ingest.update_lock(self.data), self.assertRaises(RuntimeError):
            self.run_update()
        result = self.run_update()
        path = self.data / "processed/execucoes" / f"{result['execucao_id']}.json"
        path.write_bytes(path.read_bytes() + b" ")
        with self.assertRaises(ValueError):
            ingest.read_snapshot(self.data)

    def test_execucao_arquivada_alterada_e_detectada(self):
        result = self.run_update()
        path = self.data / "processed/execucoes" / f"{result['execucao_id']}.json"
        result["modo"] = "alterado"
        path.write_bytes(ingest.json_bytes(result))
        with self.assertRaises(ValueError):
            ingest.read_snapshot(self.data, result["execucao_id"])

    def test_fim_de_mes_e_valores_excessivos(self):
        request, _ = access.normalize_request({"prazo_meses": 1}, date(2026, 1, 31))
        self.assertEqual(request["data_meta"], "2026-02-28")
        with self.assertRaises(ValueError):
            access.normalize_request({"meta_brl": "1e30"}, date(2026, 9, 28))

    def test_oferta_manual_nao_e_promovida_e_validade_e_verificada(self):
        values = ["oferta1", "cdb", "Emissor de teste", "Grupo de teste", "di", "100", "pct_do_di",
                  "100", "0", "2027-09-28", "diario", "https://example.com/oferta",
                  "2026-09-28T09:00:00-03:00", "2026-09-28T10:00:00-03:00", "2026-09-29", "documentada"]
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(access.OFFER_FIELDS)
        writer.writerow(values)
        result = access.inspect_offers(stream.getvalue(), date(2026, 9, 28))
        self.assertTrue(result["cadastradas"][0]["estrutura_valida"])
        self.assertFalse(result["cadastradas"][0]["liberada_para_comparacao"])
        expired = access.inspect_offers(stream.getvalue(), date(2026, 9, 30))
        self.assertFalse(expired["cadastradas"][0]["estrutura_valida"])

    def test_arquivo_real_completo_preserva_recorte(self):
        payload = (ROOT / "data/raw/tesouro_taxas_precos.csv").read_bytes()
        source = ingest.load_registry(self.data)["fontes"][-1]
        rows = ingest.parse_treasury(payload, source, date(2026, 9, 28))
        self.assertEqual(len(rows), 58)
        self.assertEqual({row["data_referencia"] for row in rows}, {"2026-09-25"})


if __name__ == "__main__":
    unittest.main()
