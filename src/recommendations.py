"""Indicação inicial, tabela do chat e orientação detalhada de investimentos."""
from decimal import Decimal
from datetime import date
from .planning import month_date
from .update_data import reference_day


def orientar(pedido, contexto):
    rows = []
    liquidity = pedido.get("necessita_resgate_antecipado")
    months = pedido.get("prazo_meses")
    for product in (contexto or {}).get("catalogo", {}).get("produtos", []):
        pid = product["id"]
        status = "Avaliar condições"
        reason = "Confira contrato, custos e adequação à data da meta."
        if pid == "tesouro_selic":
            status = "Considerar para liquidez"
            reason = "Alternativa para avaliar quando o acesso ao dinheiro importa. Venda antecipada ocorre a preço de mercado; confira liquidação e custos."
        elif pid == "cdb":
            status = "Considerar somente com liquidez compatível"
            reason = "Procure uma oferta com resgate e vencimento compatíveis com a meta. A base não verifica uma oferta ou taxa de CDB."
        elif pid == "poupanca":
            status = "Alternativa simples para comparar"
            reason = "Considere a data de aniversário: retirar antes dela afeta o rendimento do período. Não há evidência aqui de que seja a mais rentável."
        elif pid in ("lci", "lca"):
            status = "Depende da carência e do vencimento"
            reason = "Sem uma oferta verificada, não é possível confirmar acesso ao dinheiro na data da meta. Não contratar antes de conferir essas condições."
        elif pid in ("tesouro_prefixado", "tesouro_ipca"):
            status = "Exige compatibilidade de vencimento"
            reason = "Avalie apenas com vencimento compatível e entendimento das oscilações; saída antecipada pode produzir perda."
            if liquidity is True or (months is not None and months <= 12):
                status = "Não priorizar nesta triagem"
                reason = "Prazo curto ou necessidade de resgate torna relevante o risco de vender com perda antes do vencimento."
        if liquidity is None or months is None:
            status = "Orientação provisória — faltam dados"
        sources = (contexto or {}).get("fontes", {})
        source_ids = {"cdb": ["cdi_12"], "lci": ["cdi_12"], "lca": ["cdi_12"],
                      "poupanca": ["poupanca_195"], "tesouro_selic": ["selic_11", "tesouro_manha"],
                      "tesouro_prefixado": ["tesouro_manha"], "tesouro_ipca": ["ipca_433", "tesouro_manha"]}.get(pid, [])
        missing_sources = [sid for sid in source_ids if not sources.get(sid, {}).get("utilizavel_como_dado_publicado_recente")]
        market = "Referências recentes consultadas" if not missing_sources else "Sem referência recente confirmada: " + ", ".join(missing_sources)
        titles = [t for t in (contexto or {}).get("titulos_tesouro", []) if t.get("produto_id") == pid]
        if titles and pedido.get("data_meta"):
            early = sum(t["data_vencimento"] > pedido["data_meta"] for t in titles)
            market += f". {early} de {len(titles)} títulos da base vencem após a meta; exigiriam venda antecipada."
        rows.append({"produto_id": pid, "Produto": product["nome"], "Orientação": status,
                     "Dados de mercado": market,
                     "Motivo e condição": reason, "Liquidez": product["liquidez"],
                     "Riscos": "; ".join(product["riscos"]), "Garantia": product["garantia"],
                     "Fonte": product["fonte_conceitual"]})
    return rows


def panorama(context):
    if not context:
        return "Não obtive um contexto de mercado válido nesta tentativa. Não há base para indicar o investimento mais vantajoso agora."
    sources = context.get("fontes", {})
    recent = sum(bool(s.get("utilizavel_como_dado_publicado_recente")) for s in sources.values())
    total = len(sources)
    prefix = f"Consulta de mercado: {recent} de {total} fontes com publicação recente validada nesta análise."
    if context.get("modo") in ("offline", "reproducao_historica"):
        prefix = "Base histórica: esta visualização não confirma as condições atuais de investimento."
    rates = []
    labels = {"selic_meta_432": "Meta Selic", "selic_11": "Selic efetiva", "cdi_12": "CDI", "poupanca_195": "Poupança", "ipca_433": "IPCA"}
    units = {"pct_ao_dia": "% ao dia", "pct_ao_ano": "% ao ano", "pct_no_mes": "% no mês", "pct_no_periodo_informado": "% no período"}
    for identifier, observation in context.get("indicadores_publicados_recentemente", {}).items():
        if not sources.get(identifier, {}).get("utilizavel_como_dado_publicado_recente"):
            continue
        end = " a " + observation["data_fim"] if observation.get("data_fim") else ""
        proof = observation.get("evidencia", {})
        rates.append(f"{labels.get(identifier, identifier)}: {observation['valor_pct']} {units.get(observation['unidade'], observation['unidade'])}, referência {observation['data_referencia']}{end}; fonte {proof.get('url_consultada') or proof.get('fonte_documental', '')}; consulta {proof.get('consultado_em') or 'não comprovada'}.")
    treasury = sources.get('tesouro_manha', {})
    if treasury.get('evidencia'):
        proof = treasury['evidencia']
        rates.append(f"Tesouro: {treasury['estado']}; referência {treasury.get('data_referencia')}; fonte {proof.get('url_consultada') or proof.get('fonte_documental', '')}.")
    for source in context.get('mercado_complementar', {}).get('fontes', {}).values():
        rates.append(f"{source['nome']}: {source['estado']}; fonte {source['url']}.")
    return prefix + ("\n\n" + "\n\n".join(rates) if rates else "") + "\n\nSem ofertas bancárias verificadas e projeções líquidas comparáveis, ainda não é possível apontar qual rende mais para sua meta."


def _pct(value):
    return format(Decimal(str(value)).quantize(Decimal('0.01')), 'f').replace('.', ',')


def recomendar_no_chat(pedido, contexto):
    contexto = contexto or {}
    liquidez = pedido.get('necessita_resgate_antecipado')
    meses = pedido.get('prazo_meses')
    hoje = date.fromisoformat(contexto['data_analise']) if contexto.get('data_analise') else reference_day()
    dias_meta = (month_date(hoje, meses) - hoje).days if meses is not None else None
    if liquidez is True:
        recomendacao = ('**Minha indicação inicial é Tesouro Selic**, porque você pode precisar resgatar antes da meta. '
                        'Confira o prazo de crédito do resgate: ele não equivale a dinheiro disponível imediatamente a qualquer hora.')
    elif liquidez is False and meses is not None:
        recomendacao = ('**Minha indicação é procurar um CDB com vencimento compatível com sua meta.** '
                        'Como você pode manter o dinheiro aplicado, vale comparar também LCI e LCA com carência compatível. '
                        'A escolha da oferta depende da taxa líquida, do emissor e das condições de resgate; as referências abaixo ainda não confirmam uma oferta para contratar.')
        if meses <= 12:
            recomendacao += ' Para esse prazo curto, eu não priorizaria Prefixado ou IPCA+ com vencimento posterior à meta.'
    else:
        recomendacao = '**A indicação ainda é provisória:** Tesouro Selic se você precisar de flexibilidade; CDB, LCI ou LCA podem entrar na comparação se puder esperar o vencimento.'

    def taxa_selic():
        titulos = sorted((r for r in contexto.get('titulos_tesouro', [])
                          if r.get('produto_id') == 'tesouro_selic' and r.get('publicacao_recente')
                          and r['data_vencimento'] > hoje.isoformat()),
                         key=lambda r: r['data_vencimento'])
        if titulos:
            r = titulos[0]
            taxa = r.get('taxa_compra_manha_pct_aa')
            if taxa is not None:
                sinal = '+' if Decimal(taxa) >= 0 else '−'
                return f"Selic {sinal} {_pct(abs(Decimal(taxa)))}% a.a. · publicação {r['data_referencia']}"
        return 'Acompanha a Selic; cotação do título não confirmada nesta consulta'

    tabela = [['Tesouro Selic', taxa_selic(), 'Liquidez diária; conferir horário e liquidação']]
    referencias = contexto.get('mercado_complementar', {}).get('referencias_bancarias', [])
    for produto in ('CDB', 'LCI', 'LCA'):
        registros = [r for r in referencias if r.get('produto') == produto and r.get('consulta_atual')
                     and r.get('indexador') in ('CDI', 'DI')]
        if liquidez is True:
            registros = [r for r in registros if r.get('liquidez') == 'DIARIA']
        if pedido.get('saldo_inicial_brl') is not None:
            saldo = Decimal(str(pedido['saldo_inicial_brl']))
            registros = [r for r in registros if Decimal(r.get('minimo_brl', '0')) <= saldo]
        if meses is not None:
            minimo_dias = {'1_360': 1, '361_1080': 361, '1081+': 1081}
            registros = [r for r in registros
                         if minimo_dias.get(r.get('faixa_carencia_dias'), float('inf')) <= dias_meta
                         and (r.get('liquidez') != 'DATA_VENCIMENTO'
                              or minimo_dias.get(r.get('faixa_vencimento_dias'), float('inf')) <= dias_meta)]
        if registros:
            menor = min(Decimal(r['taxa_min_pct']) for r in registros)
            maior = max(Decimal(r['taxa_max_pct']) for r in registros)
            taxa = f'{_pct(menor)}–{_pct(maior)}% do CDI (faixa estatística)'
        else:
            taxa = 'Sem referência confirmada para seu saldo e prazo'
        condicao = ('Resgate e carência dependem da oferta' if produto == 'CDB'
                    else 'Só considerar com carência e vencimento compatíveis')
        if liquidez is True and produto in ('LCI', 'LCA'):
            condicao = 'Não priorizar: você pode precisar sacar antes'
        tabela.append([produto, taxa, condicao])
    linhas = ['| Investimento | Referência consultada | Para sua meta |', '|---|---|---|']
    linhas += ['| ' + ' | '.join(row) + ' |' for row in tabela]
    nota = ('As faixas bancárias não são ofertas nem rendimentos líquidos; não compare seus percentuais diretamente com a taxa do Tesouro. '
            'A data individual dessas taxas não é informada pelos bancos.')
    return recomendacao + '\n\n' + '\n'.join(linhas) + '\n\n' + nota
