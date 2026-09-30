"""Planejamento determinístico. Uma hipótese de taxa nunca representa oferta."""

import calendar
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP, localcontext

from .data_access import normalize_request
from .update_data import number, reference_day

CENT = Decimal("0.01")


def money(value):
    return format(Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP), ".2f")


def brl(value):
    formatted = f"{Decimal(value):,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
    return "R$ " + formatted


def month_date(start, months):
    year, month = divmod(start.year * 12 + start.month - 1 + months, 12)
    return date(year, month + 1, min(start.day, calendar.monthrange(year, month + 1)[1]))


def planejar(pedido, taxa_anual=None, *, hoje=None):
    """Aportes ao fim de cada período mensal. Juros compostos de taxa efetiva."""
    today = hoje or reference_day()
    request, _ = normalize_request(pedido, today)
    required = ("meta_brl", "saldo_inicial_brl", "aporte_mensal_brl", "prazo_meses")
    if any(key not in request for key in required):
        raise ValueError("Informe meta, saldo inicial, aporte mensal e prazo em meses.")
    target, initial, payment = (Decimal(request[key]) for key in required[:3])
    months = request["prazo_meses"]
    annual = None
    if taxa_anual is not None and str(taxa_anual).strip():
        annual = Decimal(number(taxa_anual))
        if not Decimal("-99") <= annual <= Decimal("100"):
            raise ValueError("A hipótese de taxa anual deve estar entre -99% e 100%.")
    with localcontext() as ctx:
        ctx.prec = 80
        monthly = (1 + annual / 100) ** (Decimal(1) / 12) - 1 if annual is not None else Decimal(0)
        required_payment = (max(target - initial, Decimal(0)) / months).quantize(CENT, rounding=ROUND_CEILING)
        future_factor = (1 + monthly) ** months
        annuity = (future_factor - 1) / monthly if monthly else Decimal(months)
        required_hypothesis = (max(target - initial * future_factor, Decimal(0)) / annuity).quantize(CENT, rounding=ROUND_CEILING)
        balance = initial
        rows = []
        for month in range(months + 1):
            if month:
                balance = balance * (1 + monthly) + payment
            contributed = initial + payment * month
            row = {"mes": month, "data": month_date(today, month).isoformat(),
                   "saldo_sem_rendimento_brl": money(contributed), "meta_brl": money(target),
                   "saldo_aporte_necessario_brl": money(initial + required_payment * month),
                   "aportes_acumulados_brl": money(contributed)}
            if annual is not None:
                row.update(saldo_hipotetico_bruto_brl=money(balance),
                           rendimento_hipotetico_bruto_brl=money(balance - contributed))
            rows.append(row)
        total = initial + payment * months
        needed_months = (int((max(target - initial, Decimal(0)) / payment).to_integral_value(rounding=ROUND_CEILING))
                         if payment else (0 if initial >= target else None))
        result = {
            "versao_motor": "1.0", "data_calculo": today.isoformat(), "pedido": request,
            "total_sem_rendimento_brl": money(total), "diferenca_para_meta_brl": money(max(target - total, Decimal(0))),
            "excedente_sem_rendimento_brl": money(max(total - target, Decimal(0))),
            "meta_atingida_sem_rendimento": total >= target,
            "aporte_necessario_sem_rendimento_brl": money(required_payment),
            "aumento_aporte_sem_rendimento_brl": money(max(required_payment - payment, Decimal(0))),
            "prazo_necessario_sem_rendimento_meses": needed_months, "evolucao": rows,
            "hipotese": None,
            "origem_entradas": "Valores e prazo informados pelo usuário nesta sessão.",
            "premissas": ["Saldo inicial na data do cálculo; um aporte no fim de cada período mensal.",
                          "Datas mensais preservam o dia inicial ou usam o último dia de um mês mais curto.",
                          "O cenário sem rendimento é uma conta de aportes; não representa retorno zero de um produto.",
                          "Não considera inflação, tributos, custos, regras de um produto ou dias úteis.",
                          "Valores exibidos arredondados a centavos; aporte necessário arredondado para cima."],
            "comparacao_produtos_disponivel": False, "resultado_liquido_disponivel": False,
        }
        if annual is not None:
            result["hipotese"] = {"taxa_anual_efetiva_pct": str(annual),
                                  "taxa_mensal_equivalente_pct": str(monthly * 100),
                                  "saldo_final_bruto_brl": money(balance), "rendimento_bruto_brl": money(balance - total),
                                  "aporte_necessario_bruto_brl": money(required_hypothesis),
                                  "meta_atingida_no_cenario": balance >= target,
                                  "origem": "Taxa hipotética informada pelo usuário; não é cotação nem oferta.",
                                  "premissa": "Taxa anual efetiva constante, convertida por (1 + taxa/100)^(1/12) - 1; aportes no fim do mês."}
        return result


def resumo_calculado(result):
    if result is None:
        return "Informe sua meta, saldo inicial, aporte mensal e prazo para gerar o planejamento."
    request = result["pedido"]
    status = "alcança" if result["meta_atingida_sem_rendimento"] else "não alcança"
    text = (f"Com {brl(request['saldo_inicial_brl'])} iniciais e {request['prazo_meses']} aportes de "
            f"{brl(request['aporte_mensal_brl'])}, você acumula {brl(result['total_sem_rendimento_brl'])} "
            f"sem considerar rendimentos. Esse cenário {status} a meta de {brl(request['meta_brl'])}.")
    if not result["meta_atingida_sem_rendimento"]:
        text += (f" Faltam {brl(result['diferenca_para_meta_brl'])}. Para cumprir o prazo sem depender de rendimento, "
                 f"o aporte seria {brl(result['aporte_necessario_sem_rendimento_brl'])} por mês.")
        needed = result["prazo_necessario_sem_rendimento_meses"]
        if needed is not None:
            text += f" Mantendo o aporte informado, seriam necessários {needed} meses sem rendimento."
    if result["hipotese"]:
        text += (f" Na hipótese de taxa que você informou, o saldo bruto seria "
                 f"{brl(result['hipotese']['saldo_final_bruto_brl'])}. Essa hipótese não é uma taxa atual de investimento; "
                 "impostos e custos não foram calculados.")
    return text
