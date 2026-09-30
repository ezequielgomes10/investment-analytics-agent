<p align="center">
  <img src="assets/logo.svg" width="132" height="156" alt="IAA — símbolo de um banco clássico">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&amp;logo=python&amp;logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-414141?style=for-the-badge&amp;logo=streamlit&amp;logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/Pandas-555555?style=for-the-badge&amp;logo=pandas&amp;logoColor=white" alt="Pandas">
  <img src="https://img.shields.io/badge/Gemini_API-606B78?style=for-the-badge" alt="Gemini API">
</p>

<h1 align="center">Investment Analytics Agent</h1>

<p align="center"><strong>Metas, aportes e escolhas de investimento.</strong></p>
<p align="center">Conte quanto quer juntar e em quanto tempo. O IAA consulta dados públicos,<br>orienta quais investimentos considerar e mostra seu planejamento em um dashboard.</p>

<p align="center">
  <a href="https://aistudio.google.com/app/apikey"><img src="https://img.shields.io/badge/CRIAR_CHAVE_GEMINI-303030?style=for-the-badge" alt="Criar chave da API Gemini"></a>
  <a href="https://github.com/ezequielgomes10/investment-analytics-agent/archive/refs/heads/main.zip"><img src="https://img.shields.io/badge/BAIXAR_PROJETO_COMPLETO-3776AB?style=for-the-badge" alt="Baixar projeto completo em ZIP"></a>
</p>
<p align="center"><a href="https://www.python.org/downloads/windows/">Baixar Python para Windows</a> · <a href="#instalar-e-abrir-no-windows">Como instalar</a> · <a href="#conectar-sua-chave-gemini">Como conectar a API</a></p>

---

Projeto desenvolvido para o desafio de agente financeiro da **DIO**. A conversa usa Gemini; as contas e os gráficos são feitos em Python. Você não precisa saber programar para seguir os passos abaixo.

## Antes de começar

Você precisa de um computador com Windows 10 ou 11, internet, Python 3.10 ou superior e uma conta Google com acesso ao AI Studio. Não precisa instalar Git nem VS Code.

O botão **Baixar projeto completo** inclui código, dados, documentação e testes. O Python é instalado separadamente; as bibliotecas serão baixadas juntas pelo comando do passo 4.

## Instalar e abrir no Windows

### 1. Instale o Python

1. Abra a [página oficial do Python para Windows](https://www.python.org/downloads/windows/).
2. Escolha uma versão estável do Python 3 e o **Windows installer (64-bit)** para um PC comum com Intel ou AMD. Se seu computador usa ARM, escolha o instalador ARM64. Não escolha uma versão de teste nem o pacote “embeddable”.
3. Abra o instalador. Se aparecer **Add python.exe to PATH**, marque essa opção antes de clicar em **Install Now**.
4. Aguarde terminar e feche o instalador.

Se você já usa Python 3.10 ou superior, pode seguir para o próximo passo.

### 2. Baixe e extraia o projeto

1. Clique em **Baixar projeto completo**, no início desta página.
2. Abra a pasta **Downloads** do computador e encontre `investment-analytics-agent-main.zip`.
3. Clique com o botão direito no ZIP e escolha **Extrair Tudo… → Extrair**.
4. Abra a pasta extraída até encontrar `README.md`, `requirements.txt` e as pastas `src`, `data` e `docs`.

É nessa pasta que você vai trabalhar. Não execute os comandos dentro do ZIP nem dentro da pasta `src`.

### 3. Abra o terminal nessa pasta

Na janela da pasta, clique na **barra de endereço**, onde aparece o caminho. Digite `powershell` e pressione **Enter**. Isso abre uma janela para receber os comandos.

Copie a linha abaixo, cole nessa janela e pressione **Enter**:

```powershell
python --version
```

Deve aparecer algo como `Python 3.14.0`. Se não funcionar, tente `py --version`. Se `py` funcionar, use `py` no lugar de `python` no primeiro comando do próximo passo.

### 4. Prepare o aplicativo

Execute **um comando por vez**. Espere a linha de comando voltar antes de colar o seguinte.

Primeiro, crie uma pasta reservada às bibliotecas do projeto. Esse comando pode terminar sem mostrar mensagem:

```powershell
python -m venv .venv
```

Depois, instale todas as bibliotecas necessárias:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

O segundo comando baixa Streamlit, o cliente Gemini e as demais dependências. Pode levar alguns minutos na primeira vez. Você só precisa fazer esta preparação uma vez por instalação.

### 5. Abra o agente

Na mesma janela, execute:

```powershell
.\.venv\Scripts\python.exe -m streamlit run src/app.py
```

Se aparecer um pedido opcional de e-mail do Streamlit, deixe em branco e pressione **Enter**.

O aplicativo deve abrir no navegador. Se isso não acontecer, acesse **[http://localhost:8501](http://localhost:8501)**. Se o terminal mostrar outra porta, use o endereço indicado em **Local URL**.

Mantenha o terminal aberto enquanto usa o agente: ele é o que mantém o aplicativo funcionando.

## Conectar sua chave Gemini

A chave é o código que permite ao agente conversar com o Gemini usando seu projeto Google.

1. Abra o [Google AI Studio — criar chave da API](https://aistudio.google.com/app/apikey) e entre com sua conta Google.
2. Se for seu primeiro acesso, conclua a configuração e aceite os termos para continuar, se concordar com eles.
3. Copie uma chave existente ou clique em **Create API key / Criar chave de API**. Se solicitado, selecione ou crie um projeto. Se seu projeto não aparecer, consulte o [guia do Google para importar projetos](https://ai.google.dev/gemini-api/docs/api-key#importing-projects).
4. Volte ao IAA, cole a chave no campo **Chave da API Gemini** e clique em **Conectar**.
5. Aguarde o teste. **Se o campo da chave desaparecer e o chat aparecer, a conexão funcionou.** Se houver erro, a mensagem explica o motivo.

O modelo usado é `gemini-3.5-flash-lite`. O acesso e a cota disponível dependem do seu projeto Google; uma chave não garante uso gratuito ilimitado. A chave é usada apenas na sessão, sem ser salva em arquivos pelo aplicativo. Suas mensagens são enviadas ao Google para gerar as respostas. Não coloque sua chave no GitHub nem em capturas de tela.

## Sua primeira conversa

Copie este exemplo no chat ou troque os valores pelos seus:

> Quero juntar R$ 15 mil em quatro meses. Tenho R$ 5 mil guardados, posso aportar R$ 2 mil por mês e talvez precise sacar antes.

O agente consulta as fontes e mostra uma indicação inicial, uma pequena tabela de investimentos e, abaixo da conversa, o dashboard. Se faltar alguma informação, ele pergunta.

Nesse exemplo, o planejamento sem rendimento chega a **R$ 13.000**. Faltam **R$ 2.000** para a meta; o aporte necessário seria de **R$ 2.500 por mês**. Esses valores vêm do cálculo em Python.

Você pode continuar a conversa assim:

| O que você quer fazer | O que pode escrever |
|---|---|
| Alterar o aporte e atualizar o gráfico | “Agora consigo guardar R$ 2.500 por mês.” |
| Mudar o prazo | “Mude meu prazo para seis meses.” |
| Entender um conceito | “O que é liquidez?” |
| Consultar a origem dos dados | “Mostre as fontes.” |
| Começar outro planejamento | “Quero começar uma nova meta.” |

As fontes não aparecem automaticamente no chat. Uma nova meta começa sem reutilizar o saldo e os aportes anteriores.

## Fechar e abrir novamente

Para apagar a chave e a conversa da sessão, clique em **Sair**. Para desligar o aplicativo, volte ao terminal e pressione **Ctrl + C**.

Na próxima vez, abra o PowerShell na pasta do projeto, como no passo 3, e execute apenas:

```powershell
.\.venv\Scripts\python.exe -m streamlit run src/app.py
```

Depois, conecte sua chave novamente. Não precisa reinstalar as bibliotecas a cada uso.

## Se algo não funcionar

| O que apareceu | Como resolver |
|---|---|
| `python` não foi encontrado ou abriu a Microsoft Store | Tente `py --version`. Se também falhar, reinstale o Python pelo site oficial e reabra o terminal. |
| `requirements.txt` ou `src/app.py` não encontrado | Você abriu o terminal na pasta errada. Volte à pasta que contém os dois arquivos e repita o passo 3. |
| `.venv\Scripts\python.exe` não encontrado | Execute novamente o primeiro comando do passo 4, na pasta do projeto. |
| Falta uma biblioteca, como `streamlit` | Repita o comando de instalação das dependências, no passo 4, e espere terminar. |
| Chave recusada, acesso negado ou modelo indisponível | Confira a chave e o projeto no AI Studio. Gere outra chave se necessário e confirme o acesso ao modelo. |
| Cota ou limite atingido | Confira os limites no AI Studio e tente novamente quando houver cota disponível. |
| Uma taxa não foi confirmada | A fonte pode estar indisponível ou desatualizada. O planejamento dos aportes continua funcionando; o agente não substitui o dado ausente por uma taxa inventada. |

## O que o projeto faz hoje

O IAA calcula metas e aportes sem rendimento, indica classes de renda fixa conforme prazo e necessidade de resgate e apresenta referências públicas de Tesouro Selic, CDB, LCI e LCA. A consulta inclui indicadores do BCB, Tesouro e fontes complementares descritas na [base de conhecimento](docs/02-base-conhecimento.md).

**A tabela não é um ranking de rentabilidade líquida.** As faixas bancárias são estatísticas, não ofertas para contratar. O projeto ainda não calcula impostos, custos e retorno líquido por produto. Dados indisponíveis ou históricos não são apresentados como cotações atuais confirmadas.

<details>
<summary><strong>Arquivos, testes e documentação técnica</strong></summary>

| Pasta ou arquivo | Conteúdo |
|---|---|
| `src/` | Interface, integração Gemini, consultas e cálculos |
| `data/` | Catálogo, regras, fontes e CSVs históricos |
| `docs/` | Os cinco documentos da entrega DIO |
| `examples/` | Exemplo de entrada para o planejamento |
| `tests/` | Testes automatizados |
| `assets/logo.svg` | Símbolo do projeto usado neste README |
| `.streamlit/config.toml` | Tema visual do aplicativo |
| `requirements.txt` | Bibliotecas instaladas no passo 4 |

Para executar os testes, abra o terminal na pasta do projeto:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes do Gemini usam respostas simuladas. O teste real de conexão acontece ao clicar em **Conectar** no aplicativo.

Para consultar a base pela linha de comando:

```powershell
.\.venv\Scripts\python.exe -m src.update_data --offline
.\.venv\Scripts\python.exe -m src.update_data --timeout 15
.\.venv\Scripts\python.exe -m src.data_access --offline --pedido examples/meta_4_meses.json
```

A `.venv` é criada na instalação. `data/processed/` e `data/raw/evidencias/` são gerados pelas consultas e preservam o histórico local. Essas pastas, caches e chaves ficam fora do Git. Os CSVs históricos necessários acompanham o projeto.

1. [Documentação do agente](docs/01-documentacao-agente.md)
2. [Base de conhecimento](docs/02-base-conhecimento.md)
3. [Prompts](docs/03-prompts.md)
4. [Avaliação e métricas](docs/04-metricas.md)
5. [Pitch](docs/05-pitch.md)

</details>
