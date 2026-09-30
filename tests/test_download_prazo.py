import unittest
from unittest.mock import Mock, patch
from src import update_data as ingest, market_sources as market


class DownloadPrazoTests(unittest.TestCase):
    def test_download_lento_interrompe_mesmo_recebendo_bytes(self):
        response = Mock()
        response.read1.return_value = b'x'
        manager = Mock()
        manager.__enter__ = Mock(return_value=response)
        manager.__exit__ = Mock(return_value=False)
        with patch.object(ingest, 'urlopen', return_value=manager), patch.object(
            ingest, 'monotonic', side_effect=[0, 0, 9]
        ), self.assertRaises(TimeoutError):
            ingest.fetch({'url': 'https://example.com'}, 8)
        self.assertEqual(response.read1.call_count, 1)

    def test_paginacao_nao_renova_prazo_a_cada_pagina(self):
        fetch = Mock(return_value=b'{"data":[{}],"meta":{"totalPages":2,"totalRecords":2}}')
        with patch.object(market, 'monotonic', side_effect=[0, 0, 9]), self.assertRaises(TimeoutError):
            market.download({'url': 'https://example.com', 'tipo': 'openfinance'}, 8, fetch)
        self.assertEqual(fetch.call_count, 1)
