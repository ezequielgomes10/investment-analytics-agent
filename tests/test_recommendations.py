import json
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from src.recommendations import orientar
from src import gemini_service as gemini


class RecommendationsTests(TestCase):
    def test_resgate_e_prazo_mudam_triagem_sem_inventar_oferta(self):
        catalog = json.loads((Path(__file__).resolve().parents[1] / "data/catalogo_produtos.json").read_text(encoding="utf-8"))
        context = {"catalogo": catalog}
        short = orientar({"prazo_meses": 4, "necessita_resgate_antecipado": True}, context)
        long = orientar({"prazo_meses": 120, "necessita_resgate_antecipado": False}, context)
        self.assertEqual(len(short), 7)
        self.assertEqual(next(r for r in short if r["produto_id"] == "tesouro_ipca")["Orientação"], "Não priorizar nesta triagem")
        self.assertEqual(next(r for r in long if r["produto_id"] == "tesouro_ipca")["Orientação"], "Exige compatibilidade de vencimento")
        self.assertTrue(all("faltam dados" in r["Orientação"] for r in orientar({}, context)))
        self.assertEqual(orientar({}, None), [])

    def test_conexao_exige_resposta_do_modelo_correto(self):
        client = Mock()
        client.models.generate_content.return_value = SimpleNamespace(text='{"texto":"OK"}')
        self.assertTrue(gemini.testar_conexao(client))
        args = client.models.generate_content.call_args.kwargs
        self.assertEqual(args["model"], gemini.MODELO)
        self.assertNotIn("meta_brl", args["contents"])
        client.models.generate_content.return_value = SimpleNamespace(text='{"texto":"errado"}')
        with self.assertRaises(gemini.GeminiUnavailable):
            gemini.testar_conexao(client)

    def test_diagnosticos_sem_expor_excecao(self):
        for code, word in [(400, "rejeitada"), (401, "Autenticação"), (403, "Acesso"), (404, "Modelo"), (429, "Cota"), (503, "indisponível")]:
            error = RuntimeError("SEGREDO api_key=privado")
            error.code = code
            client = Mock()
            client.models.generate_content.side_effect = error
            with self.subTest(code=code), self.assertRaises(gemini.GeminiUnavailable) as caught:
                gemini.testar_conexao(client)
            self.assertIn(word, str(caught.exception))
            self.assertNotIn("SEGREDO", str(caught.exception))
