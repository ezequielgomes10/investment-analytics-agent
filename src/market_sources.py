"""Fontes complementares: estatísticas, expectativas e calendário, nunca ofertas."""
import json
from time import monotonic
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

import xlrd
from .update_data import number as normalize_number


def decimal(value, low='-100', high='1000000000000'):
    if isinstance(value, bool) or value is None:
        raise ValueError('Número ausente')
    number = Decimal(normalize_number(value))
    if not number.is_finite() or not Decimal(low) <= number <= Decimal(high):
        raise ValueError('Número fora do domínio')
    return format(number, 'f')


def parse_focus(payload, today):
    entries = json.loads(payload)['value']
    rows = []
    for indicator in ('Selic', 'IPCA'):
        selected = [r for r in entries if r['Indicador'] == indicator and r['baseCalculo'] == 0]
        if not selected:
            raise ValueError('Focus incompleto')
        latest = max(r['Data'] for r in selected)
        if date.fromisoformat(latest) > today:
            raise ValueError('Publicação futura')
        for r in selected:
            if r['Data'] != latest:
                continue
            year = int(r['DataReferencia'])
            if not today.year <= year <= today.year + 10:
                continue
            rows.append({'indicador': indicator, 'ano': year, 'data_referencia': latest,
                         'mediana_pct': decimal(r['Mediana'], '-100', '100'),
                         'unidade': '% a.a. no fim do ano' if indicator == 'Selic' else '% de inflação no ano',
                         'natureza': 'expectativa, não taxa contratada nem trajetória mensal'})
    if not rows or len({r['indicador'] for r in rows}) != 2:
        raise ValueError('Focus sem horizonte válido')
    if len({(r['indicador'],r['ano']) for r in rows}) != len(rows):
        raise ValueError('Focus duplicado')
    return {'data_referencia': min(r['data_referencia'] for r in rows), 'registros': rows}


def parse_bank(payload, today):
    records = json.loads(payload)['data']
    if not isinstance(records, list):
        raise ValueError('Lista bancária inválida')
    rows = []
    for r in records:
        if r['targetAudience'] != 'PESSOA_NATURAL' or r['investmentType'] not in ('CDB','RDB','LCI','LCA'):
            continue
        index = r['index']['indexer']
        dist = r['index']['issueRemunerationRate']
        conditions = r['investmentConditions']
        low = Decimal(decimal(dist['minimum'], '0','10'))
        high = Decimal(decimal(dist['maximum'], '0','10'))
        if low > high:
            raise ValueError('Faixa de taxa invertida')
        # O contrato usa representação decimal: 1.025 = 102.5% do CDI.
        unit = '% do indexador' if index in ('CDI','DI','SELIC') else '% a.a. prefixado' if index == 'PRE_FIXADO' else '% a.a. de parcela adicional'
        liquidity = conditions['redemptionTerm']
        if liquidity not in ('DIARIA','DATA_VENCIMENTO','DIARIA_PRAZO_CARENCIA'):
            raise ValueError('Liquidez desconhecida')
        for field in ('expirationPeriod','gracePeriod'):
            if conditions[field] not in ('1_360','361_1080','1081+'):
                raise ValueError('Faixa de prazo desconhecida')
        rows.append({'instituicao': r['participant']['name'], 'emissor': r['issuerInstitutionName'],
                     'cnpj_emissor': r['issuerInstitutionCnpjNumber'], 'produto': r['investmentType'],
                     'indexador': index, 'taxa_min_pct': format(low*100,'f'), 'taxa_max_pct': format(high*100,'f'),
                     'unidade': unit, 'minimo_brl': decimal(conditions['minimumAmount'],'0'),
                     'liquidez': liquidity, 'faixa_vencimento_dias': conditions['expirationPeriod'],
                     'faixa_carencia_dias': conditions['gracePeriod'],
                     'data_referencia': None, 'natureza': 'estatística de produtos; não é oferta contratável',
                     'liberado_para_projecao': False})
    return {'data_referencia': None, 'registros': rows, 'total_recebido': len(records)}


def parse_calendar(payload, today):
    book = xlrd.open_workbook(file_contents=payload)
    dates = set()
    sheet = book.sheet_by_index(0)
    for cell in sheet.col(0):
        if cell.ctype == xlrd.XL_CELL_DATE:
            dates.add(xlrd.xldate_as_datetime(cell.value, book.datemode).date().isoformat())
    if len(dates) < 100 or not any(d.startswith(str(today.year)) for d in dates):
        raise ValueError('Calendário sem cobertura do ano da análise')
    years = sorted({int(d[:4]) for d in dates})
    return {'data_referencia': None, 'registros': [{'data': d} for d in sorted(dates)],
            'ano_inicial': min(years), 'ano_final': max(years),
            'limite': 'Feriados bancários nacionais; não inclui municipais, eleições ou último dia do ano. Não substitui calendário específico de liquidação.'}


def dias_uteis(inicio, fim, calendario):
    """Intervalo [início, fim); não simula liquidação de produtos."""
    start, end = date.fromisoformat(inicio), date.fromisoformat(fim)
    if end < start or start.year < calendario['ano_inicial'] or end.year > calendario['ano_final']:
        raise ValueError('Período fora da cobertura do calendário')
    holidays = {r['data'] for r in calendario['registros']}
    return sum((start+timedelta(days=i)).weekday()<5 and (start+timedelta(days=i)).isoformat() not in holidays for i in range((end-start).days))


def download(source, timeout, fetch):
    if source['tipo'] != 'openfinance':
        return [(source['url'], fetch(source, timeout))]
    url = urlsplit(source['url'])
    pages, seen, expected = [], set(), None
    started = monotonic()
    for page in range(1, 51):
        remaining = timeout - (monotonic() - started)
        if remaining <= 0:
            raise TimeoutError("Tempo total da consulta bancária excedido")
        query = dict(parse_qsl(url.query))
        query.update({'page': page, 'page-size': 1000})
        requested = urlunsplit((url.scheme,url.netloc,url.path,urlencode(query),''))
        payload = fetch({**source,'url':requested}, remaining)
        body = json.loads(payload)
        total = body['meta']['totalPages']
        if type(total) is not int or not 1 <= total <= 50:
            raise ValueError('Paginação fora do limite')
        if expected is not None and total != expected:
            raise ValueError('Paginação mudou durante a consulta')
        expected = total
        fingerprint = json.dumps(body['data'], sort_keys=True)
        if fingerprint in seen and body['data']:
            raise ValueError('Página repetida')
        seen.add(fingerprint)
        pages.append((requested,payload))
        if sum(len(b) for _,b in pages) > 20_000_000:
            raise ValueError('Resposta bancária excede limite')
        if page == total:
            count = sum(len(json.loads(b)['data']) for _,b in pages)
            if count != body['meta']['totalRecords']:
                raise ValueError('Paginação incompleta')
            return pages
    raise ValueError('Paginação incompleta')


def collect(config, previous, *, offline, today, now, timeout, fetch, evidence, data):
    sources = config.get('fontes', [])
    def one(source):
        identifier = source['id']
        last = previous.get(identifier, {}).get('ultimo_dado_valido')
        status = {'nome':source['nome'], 'tipo':source['tipo'], 'url':source['url'],
                  'estado':'apenas_historico' if last else 'sem_dados', 'tentativa_em':None,
                  'erro':None, 'ultimo_dado_valido':last, 'consultado_nesta_analise':False}
        if offline:
            return identifier,status
        status['tentativa_em'] = now
        try:
            pages = download(source,timeout,fetch)
            if source['tipo']=='openfinance':
                body = {'data':[r for _,b in pages for r in json.loads(b)['data']]}
                parsed = parse_bank(json.dumps(body).encode(),today)
            elif source['tipo']=='focus':
                parsed = parse_focus(pages[0][1],today)
            elif source['tipo']=='anbima':
                parsed = parse_calendar(pages[0][1],today)
            else:
                html = pages[0][1].decode('utf-8-sig')
                if '<html' not in html.lower() or 'daycoval' not in html.lower():
                    raise ValueError('Documento inesperado')
                parsed = {'data_referencia':None,'registros':[], 'nota':'Página dinâmica consultada. Taxas não extraídas; condições exigem conferência no site.'}
            if last and parsed.get('data_referencia') and last.get('data_referencia') and parsed['data_referencia'] < last['data_referencia']:
                raise ValueError('Publicação anterior ao último dado válido')
            proofs = [evidence(data,b,identifier=identifier,local=False,now=now,source={**source,'url':u}) for u,b in pages]
            status.update(ultimo_dado_valido={**parsed,'evidencias':proofs},consultado_nesta_analise=True,
                          estado={'focus':'expectativas_consultadas','anbima':'calendario_consultado','openfinance':'estatisticas_consultadas','documental':'pagina_consultada_sem_taxas'}[source['tipo']])
            if source['tipo']=='focus' and (today-date.fromisoformat(parsed['data_referencia'])).days > source['defasagem_maxima_dias']:
                status['estado']='publicacao_defasada'
        except Exception as exc:
            status.update(estado='consulta_falhou',erro=f'{type(exc).__name__}: falha ao obter ou validar a fonte')
        return identifier,status
    with ThreadPoolExecutor(max_workers=4) as pool:
        return dict(pool.map(one,sources))


def contexto(statuses, today, pedido, *, historico=False):
    result = {'fontes':{},'expectativas':[],'referencias_bancarias':[],'calendario':None,'dias_uteis_meta':None}
    for identifier, original in statuses.items():
        status = {k:v for k,v in original.items() if k!='ultimo_dado_valido'}
        if historico:
            status.update(estado='apenas_historico',consultado_nesta_analise=False)
        result['fontes'][identifier] = status
        last = original.get('ultimo_dado_valido')
        if not last:
            continue
        usable = status['consultado_nesta_analise'] and status['estado']!='publicacao_defasada'
        proof = last['evidencias'][0]
        for row in last['registros']:
            record = {**row,'fonte_id':identifier,'fonte_url':proof['url_consultada'],
                      'consultado_em':proof['consultado_em'],'consulta_atual':usable}
            if status['tipo']=='focus': result['expectativas'].append(record)
            if status['tipo']=='openfinance': result['referencias_bancarias'].append(record)
        if status['tipo']=='anbima':
            result['calendario'] = {k:v for k,v in last.items() if k!='registros'}
            if usable and pedido.get('data_meta'):
                try: result['dias_uteis_meta']=dias_uteis(today,pedido['data_meta'],last)
                except ValueError: pass
    return result
