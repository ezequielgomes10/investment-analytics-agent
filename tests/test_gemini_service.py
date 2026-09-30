import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from src import gemini_service as service
from src.planning import planejar


class GeminiTests(unittest.TestCase):
    def client(self, response):
        if 'alteracoes' in response:
            response.setdefault('intencao', 'planejamento')
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(text=json.dumps(response))
        return client

    def test_modelo_e_schema_sao_enviados(self):
        client = self.client({"alteracoes": [{"campo": "meta_brl", "valor": "15000", "trecho": "15 mil"}]})
        data = service.interpretar(client, "Quero 15 mil", [], {})
        self.assertEqual(data, {"intencao": "planejamento", "alteracoes": {"meta_brl": "15000"}})
        args = client.models.generate_content.call_args.kwargs
        self.assertEqual(args["model"], "gemini-3.5-flash-lite")
        self.assertEqual(args["config"].response_mime_type, "application/json")

    def test_extracao_sem_evidencia_e_rejeitada(self):
        client = self.client({"alteracoes": [{"campo": "saldo_inicial_brl", "valor": "5000", "trecho": "tenho cinco mil"}]})
        with self.assertRaises(service.GeminiUnavailable):
            service.interpretar(client, "Quero planejar uma meta", [], {})

    def test_excecao_do_sdk_nao_expoe_chave(self):
        client = Mock()
        client.models.generate_content.side_effect = RuntimeError("SEGREDO_NAO_EXIBIR api_key=teste")
        with self.assertRaises(service.GeminiUnavailable) as caught:
            service.interpretar(client, "oi", [], {})
        self.assertNotIn("SEGREDO", str(caught.exception))
        self.assertNotIn("api_key", str(caught.exception))

    def test_numeros_so_podem_vir_de_marcadores_conhecidos(self):
        facts = {"saldo_final": "R$ 13.000,00"}
        self.assertEqual(service.validar_explicacao("O total é {{saldo_final}}.", facts), "O total é R$ 13.000,00.")
        for text in ("Vai render 20%", "A taxa é dez por cento", "{{taxa_inventada}}", "Veja https://site.exemplo"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                service.validar_explicacao(text, facts)

    def test_explicacao_inventada_vira_resumo_deterministico(self):
        client = self.client({"texto": "Invista em um CDB que rende 20% garantidos."})
        result = planejar({"meta_brl": 15000, "saldo_inicial_brl": 5000, "aporte_mensal_brl": 2000, "prazo_meses": 4})
        answer = service.explicar(client, "Explica", [], result, None)
        self.assertNotIn("20%", answer)
        self.assertIn("R$ 13.000,00", answer)

    def test_chave_nao_e_incluida_nas_mensagens(self):
        key = "chave_ficticia_de_teste"
        text = service.limpar_segredos(f"minha chave é {key}", key)
        self.assertNotIn(key, text)
        client = self.client({"texto": "Informe sua meta."})
        service.explicar(client, text, [], None, None, key=key)
        self.assertNotIn(key, client.models.generate_content.call_args.kwargs["contents"])

    def test_resposta_vazia_e_json_invalido_sao_erros_controlados(self):
        for text in (None, "", "não é JSON", "[]"):
            client = Mock()
            client.models.generate_content.return_value = SimpleNamespace(text=text)
            with self.subTest(text=text), self.assertRaises(service.GeminiUnavailable):
                service.interpretar(client, "oi", [], {})

    def test_valores_parciais_invalidos_nao_entram_na_meta(self):
        for value in ('-1', '0', '1.001', '1e99999999', '1000000000001'):
            client = self.client({'alteracoes':[{'campo':'meta_brl','valor':value,'trecho':'meta'}]})
            with self.subTest(value=value), self.assertRaises(service.GeminiUnavailable):
                service.interpretar(client, 'Minha meta', [], {})

    def test_intencao_invalida_ou_alteracao_conceitual_e_rejeitada(self):
        for intent in ('invalida', 'conceito'):
            client = self.client({'intencao':intent,'alteracoes':[{'campo':'meta_brl','valor':'10','trecho':'10'}]})
            with self.subTest(intent=intent), self.assertRaises(service.GeminiUnavailable):
                service.interpretar(client, '10', [], {})

    def test_explicacao_nao_envia_serie_inteira_do_dashboard(self):
        client = self.client({'texto':'O saldo é {{saldo_final}}.'})
        result = planejar({'meta_brl':15000,'saldo_inicial_brl':5000,'aporte_mensal_brl':2000,'prazo_meses':1200})
        service.explicar(client, 'Explique', [], result, None)
        payload = json.loads(client.models.generate_content.call_args.kwargs['contents'])
        self.assertNotIn('evolucao', payload['resultado_atual'])
        self.assertEqual(payload['resultado_atual']['total_sem_rendimento_brl'], result['total_sem_rendimento_brl'])


if __name__ == "__main__":
    unittest.main()
