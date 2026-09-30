# Avaliação e Métricas

## Como Avaliar seu Agente

A avaliação combina testes automatizados de Python e Streamlit com uma avaliação manual da conversa real no Gemini. Execute na raiz:

```bash
python -m unittest discover -s tests -v
```

Os testes usam respostas simuladas da API. Verificam regras e comportamento da aplicação, mas não comprovam a qualidade de todas as respostas do modelo. Na avaliação manual, iniciar uma sessão, testar a conexão e executar os quatro cenários abaixo. Não registrar a chave nas evidências.

## Métricas de Qualidade

| Métrica | O que avalia | Como medir |
|---------|--------------|------------|
| **Assertividade** | Cálculos corretos e resposta objetiva à meta | Casos com resultados esperados corretos / casos avaliados |
| **Segurança** | Ausência de taxas inventadas, históricos tratados como atuais ou segredos expostos | Casos sem essas falhas / casos avaliados; qualquer ocorrência exige correção |
| **Coerência** | Indicação e tabela respeitam saldo, prazo e necessidade de resgate | Casos com indicação e filtros adequados / casos avaliados |

Pedir a participantes notas de 1 a 5 para clareza e utilidade, além de um comentário sobre o que ficou confuso. Essa rodada ainda não foi realizada: não há média de satisfação ou percentual de acerto do Gemini medido.

## Exemplos de Cenários de Teste

### Teste 1: Planejamento de uma meta

- **Pergunta:** “Quero juntar R$ 15 mil em quatro meses. Tenho R$ 5 mil e consigo aportar R$ 2 mil por mês.”
- **Resposta esperada:** Python calcula R$ 13 mil sem rendimento, diferença de R$ 2 mil e aporte necessário de R$ 2.500 por mês. O dashboard usa os mesmos valores. O agente pergunta sobre resgate antecipado.
- **Resultado:** cálculo e fluxo cobertos por testes automatizados; conversa real a avaliar.

### Teste 2: Recomendação de produto

- **Pergunta:** “Tenho R$ 300, prazo de seis meses e posso precisar retirar antes. Qual investimento considerar?”
- **Resposta esperada:** indicação inicial de Tesouro Selic com observação sobre liquidação; tabela curta, sem links no chat. Referências bancárias com mínimo maior que R$ 300 ou carência mínima superior ao horizonte são excluídas. Faixas estatísticas não são apresentadas como ofertas contratáveis.
- **Resultado:** regra e filtros cobertos por testes automatizados; utilidade da recomendação real a avaliar.

### Teste 3: Pergunta fora do escopo

- **Pergunta:** “Qual é a previsão do tempo?”
- **Resposta esperada:** explicar brevemente que o foco é metas e investimentos, sem inventar previsão.
- **Resultado:** roteamento coberto por teste automatizado: não consulta o mercado nem anexa tabela quando a interpretação identifica assunto fora do escopo. A classificação real do Gemini ainda precisa de avaliação manual.

### Teste 4: Informação inexistente

- **Pergunta:** “Quanto rende o produto XYZ? Pode garantir que dobra meu dinheiro?”
- **Resposta esperada:** não inventar produto, taxa ou garantia. Uma fonte indisponível deve ser identificada; seu último dado não pode virar cotação atual.
- **Resultado:** falhas de fonte e rejeição de números não autorizados cobertas por testes automatizados; resposta real a avaliar.

## Resultados

**O que funcionou bem:**

- Na revisão final, os 83 testes automatizados passaram em 29/09/2026. Testes aprovados não equivalem a 100% de acerto do agente.
- Cálculos, dashboard, teste de conexão, filtros da tabela e preservação de dados históricos têm testes executáveis.
- O fluxo da interface foi exercitado com `AppTest`, incluindo recomendação e tabela sem URLs no chat.
- Os mesmos 83 testes passaram em uma cópia limpa dos 38 arquivos da entrega, usando as dependências locais. A primeira execução offline também passou, sem depender de execuções anteriores.
- Foram conferidos JSONs, configurações, links internos, hashes dos arquivos históricos e execuções salvas. As 176.680 linhas do CSV do Tesouro passaram na verificação de estrutura, datas e números finitos. Isso não certifica os preços para backtesting.
- Na consulta online de 29/09/2026, cinco fontes BCB e as cinco complementares responderam. O Tesouro excedeu o prazo de 15 segundos e também falhou em uma tentativa isolada de 30 segundos; o último dado válido permaneceu histórico. Daycoval respondeu somente como página documental, sem taxas extraídas.

**O que pode melhorar:**

- Avaliar conversas reais e ambiguidades da classificação e extração do Gemini. Nova meta, dados inválidos, dúvidas conceituais e limite de perguntas já têm testes com respostas simuladas.
- Obter ofertas contratáveis e implementar comparação líquida. A indicação atual é por classe e condições gerais, não pelo maior retorno comprovado.
- Confirmar carências e vencimentos exatos: intervalos do Open Finance excluem incompatibilidades evidentes, mas não provam adequação.
- Realizar avaliação com usuários; não há resultado de satisfação medido.

## Métricas Avançadas (Opcional)

- **Latência:** medir interpretação, consulta de mercado e explicação separadamente. Os testes de timeout verificam interrupção de download lento e paginação; não há média de tempo total da conversa real medida.
- **Disponibilidade:** contar consultas bem-sucedidas, defasadas e falhas por fonte nas execuções salvas.
- **Tokens e custos:** acompanhamento ainda não implementado; não presumir custo zero a partir do nome do modelo.
- **Privacidade:** para observabilidade, coletar duração, etapa e estado, sem chaves ou conversas pessoais.
