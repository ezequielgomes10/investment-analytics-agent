from datetime import date
from pathlib import Path
from unittest import TestCase
from src import update_data as ingest
from src.recommendations import panorama


class MarketFlowTests(TestCase):
    def test_cdi_tem_fonte_e_unidade_proprias(self):
        root = Path(__file__).resolve().parents[1]
        registry = ingest.load_registry(root / 'data')
        source = next(s for s in registry['fontes'] if s['id'] == 'cdi_12')
        self.assertIn('sgs.12/', source['url'])
        self.assertEqual(source['unidade'], 'pct_ao_dia')
        rows = ingest.parse_bcb(b'[{"data":"25/09/2026","valor":"0.050788"}]', source, date(2026,9,29))
        self.assertEqual(rows[0]['indicador'], 'cdi_12')
        self.assertEqual(rows[0]['valor_pct'], '0.050788')
        with self.assertRaises(ValueError):
            ingest.parse_bcb(b'[{"data":"25/09/2026","valor":"14"}]', source, date(2026,9,29))

    def test_falha_ou_historico_nao_vira_taxa_atual(self):
        observation = {'valor_pct': '0.050788', 'unidade': 'pct_ao_dia', 'data_referencia': '2026-09-25', 'evidencia': {'url_consultada': 'https://api.bcb.gov.br', 'consultado_em': '2026-09-29'}}
        context = {'fontes': {'cdi_12': {'utilizavel_como_dado_publicado_recente': False}}, 'indicadores_historicos': {'cdi_12': observation}}
        self.assertNotIn('0.050788', panorama(context))
        context['indicadores_publicados_recentemente'] = {'cdi_12': observation}
        self.assertNotIn('0.050788', panorama(context))
        context['fontes']['cdi_12']['utilizavel_como_dado_publicado_recente'] = True
        self.assertIn('CDI: 0.050788 % ao dia', panorama(context))
        self.assertIn('2026-09-25', panorama(context))
        self.assertIn('https://api.bcb.gov.br', panorama(context))
