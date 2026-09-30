import json
from datetime import date
from unittest import TestCase
from unittest.mock import Mock
from src import market_sources as m


def bank():
    return {'participant':{'name':'Banco teste'},'issuerInstitutionName':'Emissor teste','issuerInstitutionCnpjNumber':'00000000000000',
            'targetAudience':'PESSOA_NATURAL','investmentType':'CDB',
            'index':{'indexer':'CDI','issueRemunerationRate':{'minimum':'1.025','maximum':'1.05'}},
            'investmentConditions':{'minimumAmount':'100','redemptionTerm':'DIARIA','expirationPeriod':'361_1080','gracePeriod':'1_360'}}


class ComplementTests(TestCase):
    def test_bank_preserva_escala_e_faixas_sem_inventar_oferta(self):
        r=m.parse_bank(json.dumps({'data':[bank()]}).encode(),date(2026,9,29))['registros'][0]
        self.assertEqual(r['taxa_min_pct'],'102.500')
        self.assertEqual(r['faixa_carencia_dias'],'1_360')
        self.assertIsNone(r['data_referencia'])
        self.assertFalse(r['liberado_para_projecao'])

    def test_pj_nao_entra_na_comparacao_pf(self):
        r=bank();r['targetAudience']='PESSOA_JURIDICA'
        self.assertEqual(m.parse_bank(json.dumps({'data':[r]}).encode(),date.today())['registros'],[])

    def test_taxas_invalidas_e_faixas_desconhecidas_falham(self):
        for value in ('NaN','Infinity','-1'):
            r=bank();r['index']['issueRemunerationRate']['minimum']=value
            with self.assertRaises(ValueError):m.parse_bank(json.dumps({'data':[r]}).encode(),date.today())
        r=bank();r['investmentConditions']['gracePeriod']='0'
        with self.assertRaises(ValueError):m.parse_bank(json.dumps({'data':[r]}).encode(),date.today())

    def test_focus_separa_expectativa_de_taxa_atual(self):
        rows=[{'Indicador':i,'Data':'2026-09-25','DataReferencia':'2027','baseCalculo':0,'Mediana':v} for i,v in [('Selic',12),('IPCA',4.3)]]
        result=m.parse_focus(json.dumps({'value':rows}),date(2026,9,29))
        self.assertEqual(len(result['registros']),2)
        self.assertIn('fim do ano',result['registros'][0]['unidade'])
        with self.assertRaises(ValueError):m.parse_focus(json.dumps({'value':rows[:1]}),date(2026,9,29))

    def test_paginacao_completa_e_repetida(self):
        source={'url':'https://bank.example/api','tipo':'openfinance'}
        def page(n):return json.dumps({'data':[{'page':n}], 'meta':{'totalPages':2,'totalRecords':2}}).encode()
        fetch=Mock(side_effect=[page(1),page(2)])
        self.assertEqual(len(m.download(source,8,fetch)),2)
        self.assertIn('page=2',fetch.call_args.args[0]['url'])
        with self.assertRaises(ValueError):m.download(source,8,Mock(return_value=page(1)))

    def test_calendario_conta_feriado_e_rejeita_fora_cobertura(self):
        cal={'ano_inicial':2026,'ano_final':2026,'registros':[{'data':'2026-09-07'}]}
        self.assertEqual(m.dias_uteis('2026-09-04','2026-09-08',cal),1)
        with self.assertRaises(ValueError):m.dias_uteis('2026-09-04','2027-09-08',cal)

    def test_offline_e_falha_preservam_ultimo_dado_sem_atualidade(self):
        source={'id':'b','nome':'Banco','tipo':'openfinance','url':'https://bank.example/api'}
        last={'registros':[bank()]}
        previous={'b':{'ultimo_dado_valido':last}}
        fetch=Mock(side_effect=OSError('sem rede'))
        args=dict(today=date(2026,9,29),now='2026-09-29T12:00:00Z',timeout=8,fetch=fetch,evidence=Mock(),data=None)
        offline=m.collect({'fontes':[source]},previous,offline=True,**args)
        fetch.assert_not_called()
        self.assertFalse(offline['b']['consultado_nesta_analise'])
        failure=m.collect({'fontes':[source]},previous,offline=False,**args)
        self.assertEqual(failure['b']['ultimo_dado_valido'],last)
        self.assertEqual(failure['b']['estado'],'consulta_falhou')

    def test_contexto_replay_nao_finge_nova_consulta(self):
        parsed=m.parse_bank(json.dumps({'data':[bank()]}),date(2026,9,29))
        parsed['evidencias']=[{'url_consultada':'https://bank.example/api','consultado_em':'2026-09-29'}]
        sources={'b':{'nome':'Banco','tipo':'openfinance','estado':'estatisticas_consultadas','consultado_nesta_analise':True,'ultimo_dado_valido':parsed}}
        replay=m.contexto(sources,'2026-09-29',{},historico=True)
        self.assertFalse(replay['referencias_bancarias'][0]['consulta_atual'])
        self.assertTrue(sources['b']['consultado_nesta_analise'])
