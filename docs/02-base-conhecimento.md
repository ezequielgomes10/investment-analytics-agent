# Base de Conhecimento

O IAA usa dados públicos para contextualizar uma meta e orientar a escolha de classes de investimento. A base coleta, valida e preserva as evidências. Ter uma taxa disponível não significa ter uma oferta contratável ou um cálculo líquido implementado.

## Dados Utilizados

| Arquivo ou pasta | Função |
|---|---|
| `data/catalogo_produtos.json` | Conceitos de sete classes de investimento; sem taxas correntes fixadas no catálogo |
| `data/fontes.json` | Seis fontes principais, unidades e tolerâncias de defasagem |
| `data/fontes_complementares.json` | Focus, ANBIMA, Open Finance BTG/BB e página Daycoval |
| `data/escopo_comparacao.json` | Produtos, títulos mapeados e impedimentos da comparação numérica |
| `data/regras_tributarias.json` | Regras documentais; cálculo líquido desabilitado até validação do motor |
| `data/docs/risco_liquidez_garantias.md` | Conceitos de risco, liquidez e garantias |
| `data/ofertas_renda_fixa.csv` | Estrutura de cadastro de ofertas; atualmente sem registros |
| `data/raw/` | CSVs históricos de Selic, poupança e Tesouro, com manifesto e hashes |
| `data/raw/evidencias/` | Conteúdo bruto das consultas, gerado localmente e fora do Git |
| `data/processed/` | Execuções completas e ponteiro para a última, gerados localmente e fora do Git |

### Fontes e significado das unidades

| Fonte | Conteúdo e limite de uso |
|---|---|
| BCB SGS 11 | Selic efetiva em percentual ao dia; não é CDI |
| BCB SGS 432 | Meta Selic em percentual ao ano; não é retorno contratado |
| BCB SGS 12 | CDI em percentual ao dia, com evidência própria |
| BCB SGS 195 | Poupança em percentual no período informado por `data` e `dataFim` |
| BCB SGS 433 | IPCA mensal histórico; não é projeção |
| Tesouro Transparente | Taxas e preços da manhã por título e vencimento; não confirma compra disponível |
| Open Finance BTG/BB | Estatísticas de CDB, RDB, LCI e LCA para pessoa física; não são ofertas individuais |
| Focus/BCB | Expectativas de Selic de fim de ano e inflação; não são juros médios nem promessa de retorno |
| ANBIMA | Feriados nacionais para contagem de dias úteis; não certifica liquidação de produtos |
| Daycoval | Referência documental; a tabela dinâmica de taxas ainda não tem extração validada |

Os endpoints e links oficiais ficam nos arquivos de fontes. A interface só apresenta fontes na conversa quando o usuário solicita; não há painel de dados visível por padrão.

## Adaptações nos Dados

Os dados fictícios de transações, atendimento e perfil do template foram substituídos por dados de investimentos. A meta e a conversa pertencem à sessão do usuário e não são gravadas na base pública.

Os três CSVs fornecidos foram preservados em `data/raw/`. As cópias idênticas da raiz de `data/` foram removidas; `manifesto.json` mantém os nomes originais e hashes. São arquivos históricos, não downloads atuais.

### O que é validado

- Campos obrigatórios, estrutura, números finitos, unidades e datas coerentes.
- Datas não futuras e rejeição de publicações anteriores ao último dado válido quando há referência temporal.
- No Tesouro, estrutura do histórico e consistência dos títulos da última data; isso não certifica todo o histórico para backtesting.
- Paginação e contagem de registros no Open Finance; percentuais convertidos da representação decimal da API.
- Campos da meta, prazo, valores monetários e relações entre catálogo e regras.
- Persistência das evidências antes de liberar os dados da consulta.

Uma falha preserva o último dado válido, identificado como histórico. A falta de dados nunca vira taxa zero.

### Modalidades do Tesouro

O contexto seleciona Tesouro Selic, Prefixado sem cupons e IPCA+ sem cupons. As demais modalidades permanecem na execução para auditoria, fora da seleção do agente.

Cada título identifica taxa, vencimento e eventual necessidade de venda antecipada ou reinvestimento antes da meta. A taxa do Selic é adicional ao indexador; a do IPCA+ é a parcela real. Esses campos não liberam uma projeção de retorno.

## Estratégia de Integração

### Como os dados são carregados?

Instalação e comandos estão no [README](../README.md). A análise no chat chama `contexto_de_dados(..., offline=False)` e tenta atualizar as fontes. Os seis downloads principais são paralelos; os complementares também usam concorrência limitada. Downloads têm limite de tamanho e tempo, e a paginação bancária compartilha um prazo total por fonte.

As execuções e seus hashes são gravados em `data/processed/execucoes/`. O ponteiro `snapshot_atual.json` só muda após uma gravação completa. Um lock impede atualizações simultâneas. Encerramento abrupto pode deixar um lock residual, que exige conferência antes da remoção.

O modo offline usa arquivos históricos sem rede. As consultas offline pela linha de comando mostram histórico; não confirmam taxas atuais.

### Estados de uma fonte

| Estado | Significado |
|---|---|
| `sem_dados` | Nenhuma observação válida disponível |
| `apenas_historico` | Sem consulta online nesta análise |
| `consulta_falhou` | Falha de transporte, validação ou persistência |
| `publicacao_defasada` | Referência além da tolerância configurada |
| `publicacao_recente` | Publicação validada dentro da tolerância; não é oferta nem previsão |
| `estatisticas_consultadas` | Estatísticas bancárias obtidas, sem data individual de taxa |
| `expectativas_consultadas` | Projeções Focus obtidas |
| `calendario_consultado` | Calendário ANBIMA obtido |
| `pagina_consultada_sem_taxas` | Página documental obtida, sem extração de taxas |

Horário da tentativa, erro e evidência do último dado válido são campos separados. Um arquivo recebido manualmente não recebe um horário de consulta online fictício.

O atualizador retorna código 0 sem erros de fonte, 1 para execução com falhas parciais e 2 se não concluir. Defasagem é um estado de dado e precisa ser conferida mesmo com saída 0.

### Como os dados são usados no prompt?

Python monta a indicação e a tabela de até quatro classes. A tabela usa apenas referências marcadas como consultadas nesta análise; aplica filtros de saldo, liquidez e incompatibilidades evidentes de carência/prazo, contando o horizonte pelo calendário. Títulos vencidos não entram na cotação exibida. Não compara diretamente percentuais de CDI com taxa adicional do Tesouro e não classifica ofertas pelo retorno líquido.

Gemini interpreta entradas explícitas e explica os resultados do planejamento. Números da explicação usam marcadores autorizados. Fontes e taxas não são inseridas livremente pela LLM; a tabela é anexada pelo código. O comportamento é definido em [03-prompts.md](03-prompts.md).

### Reproduzir uma base anterior

```python
from src.data_access import contexto_de_dados

contexto = contexto_de_dados(pedido, execucao_id=id_da_execucao)
```

Essa chamada usa o catálogo, regras e observações arquivados, sem rede e sem apresentá-los como atuais. O pedido não é salvo na base: deve ser fornecido novamente.

## Exemplo de Contexto Montado

```python
contexto = contexto_de_dados({
    "meta_brl": 15000,
    "saldo_inicial_brl": 5000,
    "aporte_mensal_brl": 2000,
    "prazo_meses": 4,
    "necessita_resgate_antecipado": False,
}, offline=True)
```

O retorno inclui `pedido`, `campos_faltantes`, `catalogo`, indicadores recentes e históricos, `titulos_tesouro`, `ofertas`, `tributacao`, `mercado_complementar`, capacidades e impedimentos por produto. Dinheiro é representado por strings decimais. O exemplo completo de entrada está em `examples/meta_4_meses.json`.

## Limites desta etapa e critérios de aceite

- Coleta, validação, histórico, contexto e indicação inicial têm testes executáveis.
- O CSV de ofertas está vazio; as estatísticas bancárias não o substituem.
- Retorno líquido, tributação, custos e liquidação por produto permanecem pendentes.
- Intervalos de carência e vencimento não provam que uma aplicação serve para a data exata da meta.
- As janelas de coleta não garantem séries históricas contínuas. Não há backtesting implementado.
- Evidências e execuções acumulam em disco; não existe exclusão automática, para preservar a reprodução das análises.
