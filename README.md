# Investment Analytics Agent

Projeto desenvolvido para o desafio de agente financeiro da DIO. O IAA combina chat Gemini, indicação inicial de investimentos e dashboard Streamlit com cálculos em Python.

O usuário informa meta, saldo inicial, aporte mensal, prazo e necessidade de resgate. O chat entrega uma indicação e uma tabela curta; o dashboard aparece abaixo das respostas. Fontes só aparecem no chat quando solicitadas.

## Executar

Requer Python 3.10 ou superior. Na raiz do projeto, no Windows:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run src/app.py
```

Se a `.venv` já existe, execute somente os dois últimos comandos. Em outros sistemas, use o Python do ambiente virtual correspondente.

## Usar

1. Informe sua chave Gemini e clique em **Conectar**. A aplicação testa a API antes de liberar o chat. O modelo configurado é [`gemini-3.5-flash-lite`](https://ai.google.dev/gemini-api/docs/models); o acesso e a cota dependem do seu projeto Google.
2. Informe sua meta pelo chat. O agente pede dados faltantes, consulta as fontes e calcula o planejamento quando houver entradas suficientes.
3. Confira a indicação, a tabela e, abaixo da conversa, o dashboard. Corrija valores ou prazo enviando outra mensagem. Para começar outro planejamento sem reutilizar saldo e aportes, peça “Quero começar uma nova meta”.
4. Para consultar fontes, peça isso no chat. Para encerrar e apagar a chave da sessão, clique em **Sair**.

A chave fica em memória na sessão, sem arquivo de configuração. Mensagens e o contexto necessário são enviados ao Google para processar o chat. Não publique a chave nem grave o campo revelado em vídeos.

## O que está implementado

- Planejamento sem rendimento pelo chat. O motor mantém suporte a cenários hipotéticos em Python, sem campo adicional na interface.
- Gráficos com os mesmos resultados calculados em Python.
- Indicação inicial por prazo e necessidade de resgate, com tabela de Tesouro Selic, CDB, LCI e LCA.
- Filtros de aplicação mínima e incompatibilidades evidentes de carência/prazo nas referências bancárias.
- Consulta de Selic, CDI, poupança, IPCA, Tesouro, Open Finance BTG/BB, Focus e calendário ANBIMA. Daycoval é referência documental, sem extração automática de taxas.
- Validação, preservação do último dado válido e histórico das consultas.
- Perguntas conceituais recebem explicações; saudações e assuntos fora do escopo não disparam coleta nem tabela de investimentos.

**Limite atual:** as estatísticas bancárias não são ofertas para contratação. Não há comparação líquida por produto, tributação e custos executáveis nem ranking do investimento mais rentável. O calendário não certifica a liquidação de uma aplicação. A indicação é inicial e não substitui as condições do contrato.

## Estrutura

```text
.streamlit/config.toml       Tema da interface
data/                       Catálogo, regras, fontes e dados
  docs/                     Conhecimento sobre risco e liquidez
  raw/                      Três CSVs históricos e manifesto de integridade
docs/                       Os cinco documentos da entrega DIO
examples/meta_4_meses.json   Entrada de exemplo para a base
src/                        Aplicação e módulos
tests/                      Testes automatizados
requirements.txt            Dependências
```

| Módulo | Responsabilidade |
|---|---|
| `src/app.py` | Conexão, conversa e dashboard ao final |
| `src/ui.py` | Estilo visual |
| `src/gemini_service.py` | Conexão, extração da meta e explicação dos resultados |
| `src/planning.py` | Cálculos financeiros do planejamento |
| `src/recommendations.py` | Indicação, tabela do chat e orientação detalhada |
| `src/data_access.py` | Contexto dos dados por meta |
| `src/update_data.py` | Coleta principal, validação e persistência |
| `src/market_sources.py` | Conectores complementares |

A `.venv` é o ambiente local de dependências. `data/processed/` e `data/raw/evidencias/` são gerados pela aplicação para histórico e rastreabilidade. Essas pastas, caches e chaves estão excluídos do Git. Os CSVs históricos em `data/raw/` são mantidos para uso offline.

## Verificar

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m src.update_data --offline
.\.venv\Scripts\python.exe -m src.update_data --timeout 15
.\.venv\Scripts\python.exe -m src.data_access --offline --pedido examples/meta_4_meses.json
```

Os testes de Gemini usam respostas simuladas. A avaliação real da conversa e as limitações estão em [Métricas](docs/04-metricas.md).

## Documentação

1. [Documentação do agente](docs/01-documentacao-agente.md)
2. [Base de conhecimento](docs/02-base-conhecimento.md)
3. [Prompts](docs/03-prompts.md)
4. [Avaliação e métricas](docs/04-metricas.md)
5. [Pitch](docs/05-pitch.md)
