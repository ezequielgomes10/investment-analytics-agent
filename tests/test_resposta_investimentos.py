import unittest
from src.recommendations import recomendar_no_chat


class RecomendacaoChatTests(unittest.TestCase):
    def test_exclui_taxas_com_minimo_ou_carencia_incompativeis(self):
        rows = [{'produto': 'CDB', 'consulta_atual': True, 'indexador': 'CDI',
                 'taxa_min_pct': '120', 'taxa_max_pct': '130', 'minimo_brl': '500'},
                {'produto': 'LCI', 'consulta_atual': True, 'indexador': 'CDI',
                 'taxa_min_pct': '95', 'taxa_max_pct': '99', 'minimo_brl': '100',
                 'faixa_carencia_dias': '361_1080'}]
        texto = recomendar_no_chat({'saldo_inicial_brl': '300', 'prazo_meses': 6},
                                  {'mercado_complementar': {'referencias_bancarias': rows}})
        self.assertNotIn('130,00', texto)
        self.assertNotIn('99,00', texto)

    def test_liquidez_prioriza_selic_sem_prometer_resgate_imediato(self):
        texto = recomendar_no_chat({'necessita_resgate_antecipado': True, 'prazo_meses': 4}, {})
        self.assertIn('indicação inicial é Tesouro Selic', texto)
        self.assertIn('não equivale a dinheiro disponível imediatamente', texto)
        self.assertEqual(len([l for l in texto.splitlines() if l.startswith('|')]), 6)
        self.assertNotIn('http', texto)

    def test_sem_resgate_recomenda_classe_com_condicoes(self):
        texto = recomendar_no_chat({'necessita_resgate_antecipado': False, 'prazo_meses': 4}, {})
        self.assertIn('procurar um CDB', texto)
        self.assertIn('carência compatível', texto)
        self.assertIn('não priorizaria Prefixado', texto)

    def test_taxa_historica_nao_aparece_como_atual(self):
        row = {'produto': 'CDB', 'consulta_atual': False, 'indexador': 'CDI', 'taxa_min_pct': '110', 'taxa_max_pct': '120'}
        contexto = {'mercado_complementar': {'referencias_bancarias': [row]}}
        texto = recomendar_no_chat({}, contexto)
        self.assertNotIn('120,00', texto)
        row['consulta_atual'] = True
        texto = recomendar_no_chat({}, contexto)
        self.assertIn('110,00–120,00% do CDI (faixa estatística)', texto)
        self.assertIn('não são ofertas', texto)

    def test_tesouro_mostra_taxa_adicional_sem_trocar_por_meta_selic(self):
        contexto = {'titulos_tesouro': [{'produto_id': 'tesouro_selic', 'publicacao_recente': True,
            'data_vencimento': '2029-03-01', 'data_referencia': '2026-09-29', 'taxa_compra_manha_pct_aa': '0.05'}]}
        self.assertIn('Selic + 0,05% a.a.', recomendar_no_chat({}, contexto))

    def test_resgate_exclui_taxas_de_produtos_bloqueados(self):
        row = {'produto':'CDB','consulta_atual':True,'indexador':'CDI',
               'taxa_min_pct':'130','taxa_max_pct':'150','liquidez':'DATA_VENCIMENTO'}
        texto = recomendar_no_chat({'necessita_resgate_antecipado':True},
                                  {'mercado_complementar':{'referencias_bancarias':[row]}})
        self.assertNotIn('150,00', texto)

    def test_prazo_usa_calendario_e_nao_trinta_e_um_dias_por_mes(self):
        row = {'produto':'CDB','consulta_atual':True,'indexador':'CDI',
               'taxa_min_pct':'130','taxa_max_pct':'150','liquidez':'DATA_VENCIMENTO',
               'faixa_carencia_dias':'1_360','faixa_vencimento_dias':'1081+'}
        texto = recomendar_no_chat({'prazo_meses':35}, {'data_analise':'2026-01-01',
                                  'mercado_complementar':{'referencias_bancarias':[row]}})
        self.assertNotIn('150,00', texto)

    def test_titulo_vencido_e_excluido_e_adicional_negativo_formatado(self):
        title = {'produto_id':'tesouro_selic','publicacao_recente':True,'data_vencimento':'2026-09-28',
                 'data_referencia':'2026-09-25','taxa_compra_manha_pct_aa':'0.05'}
        context = {'data_analise':'2026-09-29','titulos_tesouro':[title]}
        self.assertNotIn('0,05%', recomendar_no_chat({}, context))
        title.update(data_vencimento='2029-03-01', taxa_compra_manha_pct_aa='-0.05')
        self.assertIn('Selic − 0,05%', recomendar_no_chat({}, context))
