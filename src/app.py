"""Interface de conversa: conectar, conversar e visualizar o planejamento."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st
from src import gemini_service as gemini
from src.data_access import contexto_de_dados, normalize_request
from src.update_data import reference_day
from src.recommendations import recomendar_no_chat, panorama
from src.planning import planejar, brl, resumo_calculado
from src.ui import aplicar_estilo, cabecalho


def desconectar():
    gemini.fechar_cliente(st.session_state.pop("cliente_gemini", None))
    for field in ("_chave_ativa", "conexao_gemini", "mensagens", "pedido_conversa",
                  "resultado", "contexto", "erro_chat"):
        st.session_state.pop(field, None)
    st.session_state["chave_gemini"] = ""


def conectar():
    with st.container(key="connection"):
        st.subheader("Conectar ao Gemini")
        st.text_input("Chave da API Gemini", type="password", key="chave_gemini",
                      placeholder="Cole sua chave aqui")
        st.caption("Usamos a chave nesta sessão, sem salvar em arquivo. Suas mensagens são enviadas ao Google.")
        if st.button("Conectar", type="primary", disabled=not st.session_state.get("chave_gemini", "").strip()):
            client = None
            with st.spinner("Testando a conexão…"):
                try:
                    key = st.session_state["chave_gemini"].strip()
                    client = gemini.criar_cliente(key)
                    gemini.testar_conexao(client)
                except gemini.GeminiUnavailable as error:
                    gemini.fechar_cliente(client)
                    st.error(str(error))
                else:
                    st.session_state.update(cliente_gemini=client, _chave_ativa=key,
                                            conexao_gemini=True, mensagens=[])
                    st.rerun()
        st.markdown('[Criar uma chave no Google AI Studio](https://aistudio.google.com/app/apikey)')


def pedir_dados(pedido):
    questions = {"meta_brl": "Quanto você quer juntar?", "prazo_meses": "Em quantos meses?",
                 "saldo_inicial_brl": "Quanto você já tem guardado?",
                 "aporte_mensal_brl": "Quanto consegue aportar por mês?",
                 "necessita_resgate_antecipado": "Você pode precisar resgatar antes da meta?"}
    missing = [q for field, q in questions.items() if pedido.get(field) is None]
    return " ".join(missing[:2])


def responder(question, progresso):
    key = st.session_state["_chave_ativa"]
    client = st.session_state["cliente_gemini"]
    history = st.session_state["mensagens"][-12:]
    question = gemini.limpar_segredos(question, key)
    progresso.caption("Entendendo sua mensagem…")
    interpretation = gemini.interpretar(client, question, history, st.session_state.get("pedido_conversa", {}))
    intent, changes = interpretation["intencao"], interpretation["alteracoes"]
    if intent == "fora_escopo":
        return question, "Meu foco é planejamento de metas e investimentos. Posso ajudar com seu objetivo financeiro; não acesso contas ou dados de outras pessoas."
    if intent == "saudacao":
        return question, "Olá! Posso ajudar com sua meta ou tirar uma dúvida sobre investimentos."
    previous = {} if intent == "nova_meta" else st.session_state.get("pedido_conversa", {})
    pedido = {**previous, **changes}
    try:
        normalize_request(pedido, reference_day())
    except ValueError:
        return question, "Não alterei seu planejamento. Informe valores em reais com até duas casas decimais e prazo entre um e mil e duzentos meses. A meta precisa ser positiva."
    st.session_state["pedido_conversa"] = pedido
    if changes or intent == "nova_meta":
        st.session_state.pop("resultado", None)
    progresso.caption("Consultando o mercado…")
    st.session_state.pop("contexto", None)
    try:
        contexto = contexto_de_dados(pedido, offline=False, timeout=8)
    except Exception:
        contexto = None
    st.session_state["contexto"] = contexto
    if intent == "fontes":
        return question, panorama(contexto)
    if intent == "conceito":
        try:
            texto = gemini.explicar(client, question, history, None, contexto, key=key, intencao=intent)
        except gemini.GeminiUnavailable:
            texto = "Não consegui responder a essa dúvida agora. Tente novamente."
        return question, texto
    required = ("meta_brl", "saldo_inicial_brl", "aporte_mensal_brl", "prazo_meses")
    result = st.session_state.get("resultado")
    if all(field in pedido for field in required):
        try:
            result = planejar(pedido)
        except (ValueError, ArithmeticError):
            st.session_state.pop("resultado", None)
            return question, "Não consegui calcular com esses valores. Informe a meta, o saldo, o aporte mensal e o prazo corrigidos."
        st.session_state["resultado"] = result
    progresso.caption("Preparando sua resposta…")
    if not result:
        texto = pedir_dados(pedido)
    else:
        try:
            texto = gemini.explicar(client, question, history, result, contexto, key=key)
        except gemini.GeminiUnavailable:
            texto = resumo_calculado(result)
    if result and pedir_dados(pedido):
        texto += " " + pedir_dados(pedido)
    answer = recomendar_no_chat(pedido, contexto) + "\n\n" + texto
    return question, answer


def mostrar_dashboard(result):
    st.subheader("Seu planejamento")
    st.caption("Evolução dos aportes · sem rendimento · depósitos ao fim de cada mês")
    cols = st.columns(4)
    cols[0].metric("Meta", brl(result["pedido"]["meta_brl"]))
    cols[1].metric("Saldo sem rendimento", brl(result["total_sem_rendimento_brl"]))
    cols[2].metric("Falta para a meta", brl(result["diferenca_para_meta_brl"]))
    cols[3].metric("Aporte necessário / mês", brl(result["aporte_necessario_sem_rendimento_brl"]))
    rows = result["evolucao"]
    chart = pd.DataFrame({"Mês": [r["mes"] for r in rows],
                          "Seu aporte, sem rendimento": [float(r["saldo_sem_rendimento_brl"]) for r in rows],
                          "Aporte necessário, sem rendimento": [float(r["saldo_aporte_necessario_brl"]) for r in rows],
                          "Meta": [float(r["meta_brl"]) for r in rows]})
    colors = ["#222222", "#777777", "#AAAAAA"]
    if result["hipotese"]:
        chart["Hipótese bruta de rendimento"] = [float(r["saldo_hipotetico_bruto_brl"]) for r in rows]
        colors.append("#555555")
    st.line_chart(chart, x="Mês", y=list(chart.columns[1:]), color=colors,
                  x_label="Meses a partir de hoje", y_label="Saldo (R$)", height=340)
def main():
    st.set_page_config(page_title="IAA · Investment Analytics Agent", page_icon="🏛️", layout="centered")
    aplicar_estilo()
    cabecalho()
    if not st.session_state.get("conexao_gemini"):
        conectar()
        return

    with st.container(key="conversation"):
        left, right = st.columns([6, 1])
        left.caption("SUA CONVERSA COM O IAA")
        right.button("Sair", on_click=desconectar, type="tertiary")
        if not st.session_state["mensagens"]:
            st.markdown('<p class="ia-invitation">Qual é a sua meta?</p>', unsafe_allow_html=True)
            st.caption("Conte quanto quer juntar e em quanto tempo.")
        for mensagem in st.session_state["mensagens"]:
            with st.chat_message(mensagem["papel"], avatar=":material/account_balance:" if mensagem["papel"] == "assistant" else ":material/person:"):
                st.markdown(mensagem["texto"].replace("$", r"\$"))
        if st.session_state.get("erro_chat"):
            st.error(st.session_state.pop("erro_chat"))
        question = st.chat_input("Escreva sua mensagem…", max_chars=4000)
        if question:
            progresso = st.empty()
            try:
                question, answer = responder(question, progresso)
            except gemini.GeminiUnavailable as error:
                st.session_state["erro_chat"] = str(error)
            else:
                st.session_state["mensagens"].extend([{"papel": "user", "texto": question},
                                                       {"papel": "assistant", "texto": answer}])
                st.session_state["mensagens"] = st.session_state["mensagens"][-24:]
            progresso.empty()
            st.rerun()
    if st.session_state.get("resultado") and st.session_state["mensagens"]:
        with st.container(key="dashboard"):
            mostrar_dashboard(st.session_state["resultado"])


if __name__ == "__main__":
    main()
