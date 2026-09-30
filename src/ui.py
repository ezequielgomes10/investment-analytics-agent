"""Identidade editorial: papel, tinta e tipografia de jornal, sem recursos externos."""
import streamlit as st


def aplicar_estilo():
    st.markdown('''<style>
    :root { color-scheme: light; }
    .stApp { color: #232323; background: #eeeeee; }
    [data-testid="stHeader"] { background: transparent; }
    [data-testid="stToolbar"], #MainMenu, footer { display: none; }
    .stMainBlockContainer { max-width: 960px; padding: 2.8rem 2.5rem 5rem; }
    h1, h2, h3, .ia-masthead, [data-testid="stMetricValue"] { font-family: Georgia, 'Times New Roman', serif !important; }
    .ia-masthead { text-align: center; margin-bottom: 38px; }
    .ia-edition { display: flex; justify-content: space-between; border-top: 1px solid #494949;
      border-bottom: 1px solid #acacac; padding: 9px 0; font: 10px/1.3 Arial, sans-serif;
      letter-spacing: 2px; text-transform: uppercase; color: #646464; }
    .ia-emblem { margin: 22px auto 12px; width: 43px; height: 43px; color: #323232; }
    .ia-masthead h1 { font-size: clamp(29px,4.3vw,48px); font-weight: 700; letter-spacing: -1.8px;
      color: #202020; margin: 0; padding: 0; line-height: 1.12; }
    .ia-masthead p { font: italic 17px/1.5 Georgia, serif; margin: 13px 0 24px; color: #646464; }
    .ia-rule { border-top: 3px solid #303030; border-bottom: 1px solid #303030; height: 6px; }
    .st-key-connection { max-width: 510px; margin: 14px auto 0; padding: 30px 32px 24px;
      border: 1px solid #b9b9b9; background: #f6f6f6; border-radius: 0; }
    .st-key-connection h2 { font-size: 27px; padding: 0 0 12px; font-weight: 400; }
    .st-key-connection a { font-size: 12px; }
    [data-testid="stTextInput"] [data-baseweb="input"], [data-testid="stTextInputRootElement"] {
      background: #fafafa; border: 1px solid #808080; border-radius: 2px; min-height: 46px; }
    .st-key-connection [data-testid="stWidgetLabel"] p { font-size: 14px; color: #333; }
    .st-key-connection [data-testid="stCaptionContainer"] p,
    .st-key-connection [data-testid="stCaption"] p,
    .st-key-connection .stCaption { color: #555 !important; font-size: 13px; opacity: 1; line-height: 1.55; }
    .stTextInput input { color: #242424; font-size: 15px; }
    .stTextInput input::placeholder, textarea::placeholder { color: #777777; opacity: 1; }
    [data-testid="stButton"] button { border-radius: 3px; border-color: #a2a2a2; font-family: Georgia, serif;
      color: #282828; min-height: 40px; background: transparent; }
    [data-testid="stButton"] button[kind="primary"] { background: #262626; color: #f4f4f4; border-color: #262626; padding: 0 25px; }
    [data-testid="stButton"] button:hover { border-color: #5e5e5e; background: #dbdbdb; color: #202020; }
    [data-testid="stButton"] button[kind="tertiary"] { font: 12px Arial, sans-serif; color: #696969; }
    a { color: #515151 !important; text-underline-offset: 3px; }
    [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: #636363 !important; font-size: 12px; }
    .st-key-conversation { padding-top: 0; }
    .ia-invitation { font: 25px/1.4 Georgia, serif; color: #333; padding-top: 22px; margin-bottom: 3px; }
    [data-testid="stChatMessage"] { background: transparent; border-radius: 0; border-bottom: 1px solid #c2c2c2;
      padding: 22px 0; gap: 14px; }
    [data-testid="stChatMessage"] p { line-height: 1.75; }
    [data-testid="stChatMessageAvatarAssistant"], [data-testid="stChatMessageAvatarUser"] {
      background: #dadada; color: #454545; border-radius: 2px; }
    [data-testid="stChatInput"] { background: #fafafa; border: 1px solid #808080; border-radius: 2px; padding: 8px 10px; }
    [data-testid="stChatInput"] > div { background: transparent; border-radius: 0; }
    [data-testid="stChatInput"] textarea { color: #282828; font-size: 16px; }
    [data-testid="stChatInputSubmitButton"] { color: #282828; }
    .st-key-dashboard { border-top: 3px double #787878; margin-top: 34px; padding-top: 24px; }
    .st-key-dashboard h2 { font-size: 29px; font-weight: 400; }
    [data-testid="stMetric"] { border-top: 1px solid #a2a2a2; border-bottom: 1px solid #c3c3c3;
      padding: 15px 0; background: transparent; }
    [data-testid="stMetricLabel"] { color: #686868; font-size: 12px; }
    [data-testid="stMetricValue"] { color: #222222; font-size: clamp(20px,2.6vw,29px); }
    [data-testid="stMarkdownContainer"] table { font-size: 13px; border-collapse: collapse; }
    [data-testid="stMarkdownContainer"] th { background: #dddddd; color: #2d2d2d; }
    [data-testid="stMarkdownContainer"] td, [data-testid="stMarkdownContainer"] th { border-color: #b7b7b7; }
    button:focus-visible, input:focus-visible, textarea:focus-visible { outline: 2px solid #656565 !important; outline-offset: 3px; }
    @media(max-width: 640px) {
      .stMainBlockContainer { padding: 1.2rem 1rem 3rem; }
      .ia-masthead { margin-bottom: 25px; }
      .ia-masthead h1 { letter-spacing: -1px; }
      .ia-edition { font-size: 8px; letter-spacing: 1px; }
      .ia-masthead p { font-size: 14px; }
      .st-key-connection { padding: 23px 18px; }
      [data-testid="stChatMessage"] { gap: 8px; }
      [data-testid="stChatMessage"] table { font-size: 11px; }
    }
    </style>''', unsafe_allow_html=True)


def cabecalho():
    st.markdown('''<header class="ia-masthead">
      <div class="ia-edition"><span>Finanças pessoais</span><span>Planejamento &amp; investimentos</span></div>
      <svg class="ia-emblem" viewBox="0 0 48 48" fill="none" stroke="currentColor" stroke-width="1.3" aria-hidden="true">
      <path d="M4 17 24 5l20 12H4Zm4 4h32M5 40h38M3 44h42M11 22v15m4-15v15m7-15v15m4-15v15m7-15v15m4-15v15"/>
      <circle cx="24" cy="13" r="2"/></svg>
      <h1>Investment Analytics Agent</h1>
      <p>Metas, aportes e escolhas de investimento.</p>
      <div class="ia-rule"></div>
      </header>''', unsafe_allow_html=True)
