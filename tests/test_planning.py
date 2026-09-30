import unittest
from datetime import date
from decimal import Decimal

from src.planning import planejar, resumo_calculado


class PlanningTests(unittest.TestCase):
    def plan(self, **changes):
        request = {"meta_brl": "15000", "saldo_inicial_brl": "5000", "aporte_mensal_brl": "2000", "prazo_meses": 4}
        request.update(changes)
        return planejar(request, hoje=date(2026, 9, 28))

    def test_meta_do_projeto_e_alternativas(self):
        result = self.plan()
        self.assertEqual(result["total_sem_rendimento_brl"], "13000.00")
        self.assertEqual(result["diferenca_para_meta_brl"], "2000.00")
        self.assertEqual(result["aporte_necessario_sem_rendimento_brl"], "2500.00")
        self.assertEqual(result["aumento_aporte_sem_rendimento_brl"], "500.00")
        self.assertEqual(result["prazo_necessario_sem_rendimento_meses"], 5)
        self.assertEqual(result["evolucao"][-1]["data"], "2027-01-28")
        self.assertEqual(result["evolucao"][-1]["saldo_aporte_necessario_brl"], "15000.00")
        self.assertIsNone(result["hipotese"])

    def test_centavos_arredondados_para_cima_cumprem_meta(self):
        result = self.plan(meta_brl="100", saldo_inicial_brl="0", aporte_mensal_brl="0", prazo_meses=3)
        self.assertEqual(result["aporte_necessario_sem_rendimento_brl"], "33.34")
        self.assertEqual(result["evolucao"][-1]["saldo_aporte_necessario_brl"], "100.02")

    def test_zero_aporte_sem_promessa_de_prazo(self):
        result = self.plan(aporte_mensal_brl=0)
        self.assertIsNone(result["prazo_necessario_sem_rendimento_meses"])
        self.assertNotIn("necessários None", resumo_calculado(result))

    def test_meta_ja_atingida_nao_pede_novos_aportes(self):
        result = self.plan(saldo_inicial_brl=20000, aporte_mensal_brl=0)
        self.assertTrue(result["meta_atingida_sem_rendimento"])
        self.assertEqual(result["aporte_necessario_sem_rendimento_brl"], "0.00")
        self.assertEqual(result["prazo_necessario_sem_rendimento_meses"], 0)

    def test_taxa_efetiva_anual_preserva_valor_em_doze_meses(self):
        request = {"meta_brl": 15000, "saldo_inicial_brl": 1000, "aporte_mensal_brl": 0, "prazo_meses": 12}
        result = planejar(request, "12", hoje=date(2026, 1, 31))
        self.assertEqual(result["hipotese"]["saldo_final_bruto_brl"], "1120.00")
        self.assertEqual(result["evolucao"][1]["data"], "2026-02-28")
        self.assertEqual(result["evolucao"][2]["data"], "2026-03-31")
        self.assertFalse(result["resultado_liquido_disponivel"])

    def test_aporte_no_fim_nao_rende_no_mes_da_entrada(self):
        request = {"meta_brl": 2000, "saldo_inicial_brl": 0, "aporte_mensal_brl": 1000, "prazo_meses": 1}
        result = planejar(request, "12", hoje=date(2026, 9, 28))
        self.assertEqual(result["hipotese"]["saldo_final_bruto_brl"], "1000.00")
        self.assertEqual(result["hipotese"]["rendimento_bruto_brl"], "0.00")

    def test_hipotese_negativa_e_zero(self):
        request = {"meta_brl": 1000, "saldo_inicial_brl": 1000, "aporte_mensal_brl": 0, "prazo_meses": 12}
        negative = planejar(request, "-10")
        self.assertEqual(negative["hipotese"]["saldo_final_bruto_brl"], "900.00")
        zero = planejar(request, "0")
        self.assertEqual(zero["hipotese"]["saldo_final_bruto_brl"], zero["total_sem_rendimento_brl"])

    def test_entradas_invalidas(self):
        for change in ({"meta_brl": -1}, {"prazo_meses": 0}, {"prazo_meses": True},
                       {"saldo_inicial_brl": "NaN"}, {"aporte_mensal_brl": "1.001"}, {"meta_brl": "1000000000001"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.plan(**change)

    def test_limites_simultaneos_da_hipotese_nao_estouram_precisao(self):
        request = {'meta_brl':'1000000000000','saldo_inicial_brl':'1000000000000',
                   'aporte_mensal_brl':'1000000000000','prazo_meses':1200}
        result = planejar(request, '100')
        self.assertEqual(len(result['evolucao']), 1201)
        self.assertGreater(Decimal(result['hipotese']['saldo_final_bruto_brl']), Decimal('1e42'))


if __name__ == "__main__":
    unittest.main()
