import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from streamlit.testing.v1 import AppTest
from src import gemini_service

ROOT = Path(__file__).resolve().parents[1]


class AppTests(unittest.TestCase):
    def setUp(self):
        self.context_patch = patch('src.data_access.contexto_de_dados', return_value=None)
        self.context = self.context_patch.start()
        self.addCleanup(self.context_patch.stop)
        self.app = AppTest.from_file(str(ROOT / 'src/app.py'), default_timeout=20).run()

    def connect(self):
        self.app.text_input(key='chave_gemini').set_value('chave_ficticia').run()
        with patch.object(gemini_service, 'criar_cliente', return_value=Mock()), patch.object(gemini_service, 'testar_conexao', return_value=True):
            next(b for b in self.app.button if b.label == 'Conectar').click().run()

    def send(self, changes, text='Minha meta', intent='planejamento'):
        with patch.object(gemini_service, 'interpretar', return_value={'intencao': intent, 'alteracoes': changes}), patch.object(gemini_service, 'explicar', return_value='Confira o planejamento abaixo.'):
            self.app.chat_input[0].set_value(text).run()
        self.assertFalse(self.app.exception)

    def complete(self):
        self.send({'meta_brl':'15000', 'saldo_inicial_brl':'5000', 'aporte_mensal_brl':'2000', 'prazo_meses':4, 'necessita_resgate_antecipado':True})

    def test_entrada_so_mostra_conexao_sem_chat_dashboard_ou_fontes(self):
        self.assertEqual(len(self.app.text_input), 1)
        self.assertEqual(self.app.text_input[0].proto.type, 1)
        self.assertFalse(self.app.chat_input)
        self.assertFalse(self.app.metric)
        self.assertFalse(self.app.expander)
        self.assertFalse(self.app.dataframe)
        self.context.assert_not_called()

    def test_conexao_libera_chat_e_oculta_campo_da_chave(self):
        self.connect()
        self.assertFalse(self.app.text_input)
        self.assertEqual(len(self.app.chat_input), 1)
        self.assertFalse(self.app.metric)
        self.app.run()  # A remoção do widget não pode apagar a chave ativa da sessão.
        self.assertEqual(self.app.session_state['_chave_ativa'], 'chave_ficticia')

    def test_conexao_falha_fecha_cliente_e_nao_libera_chat(self):
        self.app.text_input[0].set_value('ficticia').run()
        client = Mock()
        with patch.object(gemini_service, 'criar_cliente', return_value=client), patch.object(gemini_service, 'testar_conexao', side_effect=gemini_service.GeminiUnavailable('Falha de conexão.')):
            next(b for b in self.app.button if b.label == 'Conectar').click().run()
        self.assertFalse(self.app.chat_input)
        self.assertTrue(self.app.error)
        client.close.assert_called_once()

    def test_dados_incompletos_pergunta_sem_formulario_nem_dashboard(self):
        self.connect()
        self.send({'meta_brl':'15000','prazo_meses':4})
        self.assertFalse(self.app.metric)
        texto = self.app.session_state['mensagens'][-1]['texto']
        self.assertIn('Quanto você já tem guardado?', texto)
        self.assertNotIn('formulário', texto)
        self.assertNotIn('http', texto)
        self.context.assert_called_once()

    def test_dashboard_automatico_usa_conversa_e_atualiza(self):
        self.connect()
        self.complete()
        self.assertEqual(self.app.metric[1].value, 'R$ 13.000,00')
        self.assertIn('| Investimento |', self.app.session_state['mensagens'][-1]['texto'])
        self.assertFalse(self.app.dataframe)
        self.assertEqual(len(self.app.get('arrow_vega_lite_chart')) + len(self.app.get('vega_lite_chart')), 1)
        self.send({'aporte_mensal_brl':'2500'}, 'Posso aportar 2500')
        self.assertEqual(self.app.metric[1].value, 'R$ 15.000,00')

    def test_erro_de_api_preserva_conversa_e_dashboard(self):
        self.connect()
        self.complete()
        with patch.object(gemini_service, 'interpretar', side_effect=gemini_service.GeminiUnavailable('Tente novamente.')):
            self.app.chat_input[0].set_value('Pode explicar?').run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.app.metric[1].value, 'R$ 13.000,00')
        self.assertEqual(len(self.app.session_state['mensagens']), 2)
        self.assertTrue(self.app.error)

    def test_sair_apaga_chave_conversa_e_dashboard(self):
        self.connect()
        self.complete()
        client = self.app.session_state['cliente_gemini']
        next(b for b in self.app.button if b.label == 'Sair').click().run()
        client.close.assert_called_once()
        self.assertEqual(self.app.text_input[0].value, '')
        self.assertFalse(self.app.chat_input)
        self.assertFalse(self.app.metric)
        self.assertNotIn('_chave_ativa', self.app.session_state)

    def test_falha_de_fonte_nao_impede_calculo(self):
        self.connect()
        self.context.side_effect = OSError('sem rede')
        self.complete()
        self.assertEqual(self.app.metric[1].value, 'R$ 13.000,00')

    def test_fontes_aparecem_apenas_quando_solicitadas(self):
        self.connect()
        with patch('src.recommendations.panorama', return_value='Fonte: https://example.com'):
            self.send({}, 'Mostre as fontes', intent='fontes')
        self.assertIn('https://example.com', self.app.session_state['mensagens'][-1]['texto'])

    def test_entrada_invalida_preserva_plano_valido(self):
        self.connect()
        self.complete()
        self.send({'meta_brl':'0'})
        self.assertEqual(self.app.metric[1].value, 'R$ 13.000,00')
        self.assertEqual(self.app.session_state['pedido_conversa']['meta_brl'], '15000')
        self.assertIn('Não alterei', self.app.session_state['mensagens'][-1]['texto'])

    def test_erro_na_explicacao_mantem_resumo_calculado(self):
        self.connect()
        with patch.object(gemini_service, 'interpretar', return_value={'intencao':'planejamento','alteracoes':{'meta_brl':'15000','saldo_inicial_brl':'5000','aporte_mensal_brl':'2000','prazo_meses':4}}), patch.object(gemini_service, 'explicar', side_effect=gemini_service.GeminiUnavailable('Falha.')):
            self.app.chat_input[0].set_value('Minha meta').run()
        self.assertFalse(self.app.exception)
        self.assertIn('R$ 13.000,00', self.app.session_state['mensagens'][-1]['texto'])

    def test_fora_do_escopo_nao_consulta_mercado_nem_mostra_tabela(self):
        self.connect()
        self.send({}, 'Qual a previsão do tempo?', intent='fora_escopo')
        self.context.assert_not_called()
        answer = self.app.session_state['mensagens'][-1]['texto']
        self.assertIn('Meu foco', answer)
        self.assertNotIn('| Investimento |', answer)

    def test_nova_meta_nao_reaproveita_saldo_e_aporte_anteriores(self):
        self.connect()
        self.complete()
        self.send({'meta_brl':'20000'}, 'Quero começar outra meta', intent='nova_meta')
        self.assertFalse(self.app.metric)
        self.assertEqual(self.app.session_state['pedido_conversa'], {'meta_brl':'20000'})

    def test_duvida_conceitual_nao_recebe_tabela_ou_dashboard(self):
        self.connect()
        self.send({}, 'O que é liquidez?', intent='conceito')
        self.assertFalse(self.app.metric)
        self.context.assert_called_once()
        self.assertNotIn('| Investimento |', self.app.session_state['mensagens'][-1]['texto'])

    def test_poucas_perguntas_sem_duplicar_resgate(self):
        self.connect()
        self.send({'meta_brl':'15000','prazo_meses':4})
        self.assertLessEqual(self.app.session_state['mensagens'][-1]['texto'].count('?'), 2)

    def test_mencionar_fontes_sem_pedir_nao_mostra_links(self):
        self.connect()
        with patch('src.recommendations.panorama') as sources:
            self.send({}, 'Não mostre fontes')
        sources.assert_not_called()
