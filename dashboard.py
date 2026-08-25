import streamlit as st
import streamlit.components.v1 as components
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from auth import get_user, is_subscribed, logout, render_auth_page, render_paywall
from favorites import load_favorites, get_favorites, is_favorite, toggle_favorite

st.set_page_config(page_title="LeilãoCE", page_icon="🚗", layout="wide", initial_sidebar_state="expanded")

BASE_DIR = Path(__file__).resolve().parent

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, button, input, textarea, select {
    font-family: 'Inter', sans-serif !important;
}
.stApp { background: #f5f7fb; }

/* ── SIDEBAR — fundo azul escuro ─────────────────────────────────── */
section[data-testid="stSidebar"] {
    background: #1e3a8a !important;
    border-right: none !important; }
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.15) !important; }

/* logo */
section[data-testid="stSidebar"] h2 { color: #fff !important;
    font-size: 1.1rem !important; font-weight: 700 !important; }

/* labels de seção (FILTROS, INFORMAÇÕES) */
section[data-testid="stSidebar"] label { color: #93c5fd !important;
    font-size: .78rem !important; font-weight: 600 !important;
    text-transform: uppercase !important; letter-spacing: .05em !important; }

/* inputs e selects no fundo azul */
section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: rgba(255,255,255,.12) !important;
    border-color: rgba(255,255,255,.25) !important;
    border-radius: 8px !important; color: #fff !important; }

/* opções do selectbox */
section[data-testid="stSidebar"] [data-baseweb="menu"] {
    background: transparent !important;
    border: 1px solid rgba(255,255,255,.35) !important; border-radius: 8px !important; }
section[data-testid="stSidebar"] [role="option"] { background: transparent !important; color: #e2e8f0 !important; }
section[data-testid="stSidebar"] [role="option"]:hover { background: rgba(255,255,255,.12) !important; }

/* slider */
section[data-testid="stSidebar"] [data-testid="stSlider"] * { color: #e2e8f0 !important; }

/* ── BOTÕES DE NAVEGAÇÃO ─────────────────────────────────────────── */

/* inativo — texto claro, fundo transparente */
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"],
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-secondary"] {
    background: transparent !important; color: #e2e8f0 !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 500 !important; font-size: .9rem !important; }
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"]:hover,
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-secondary"]:hover {
    background: rgba(255,255,255,.12) !important; }

/* ativo — fundo branco, texto azul escuro */
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"],
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-primary"] {
    background: #fff !important; color: #1e3a8a !important;
    border: none !important; border-radius: 8px !important;
    font-weight: 700 !important; font-size: .9rem !important; }
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"]:hover,
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-primary"]:hover {
    background: rgba(255,255,255,.12) !important; }

/* Sair e Atualizar dados */
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="tertiary"],
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-tertiary"] {
    background: transparent !important; color: #e2e8f0 !important;
    border: 1px solid rgba(255,255,255,.35) !important; border-radius: 8px !important;
    font-weight: 500 !important; font-size: .88rem !important; }
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="tertiary"]:hover,
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-tertiary"]:hover {
    background: rgba(255,255,255,.12) !important; }
.pill {
  display:inline-block; padding:4px 10px; border-radius:20px;
  font-size:11px; font-weight:600; margin-right:4px; margin-bottom:4px;
}
.p-otimo   { background:#dcfce7; color:#15803d; }
.p-mediano { background:#fef9c3; color:#a16207; }
.p-ruim    { background:#fee2e2; color:#b91c1c; }
.p-inspec  { background:#ffedd5; color:#c2410c; }
.p-semref  { background:#f1f5f9; color:#64748b; }
.p-ebom    { background:#dbeafe; color:#1d4ed8; }
.p-rec     { background:#e0f2fe; color:#0284c7; }
.p-bat     { background:#ffedd5; color:#ea580c; }
.p-sin     { background:#fee2e2; color:#dc2626; }
.p-ni      { background:#f8fafc; color:#94a3b8; }

div[data-testid="stButton"] button { background:#0f172a; color:#fff; border:none; border-radius:8px; font-size:13px; font-weight:500; width:100%; }
div[data-testid="stButton"] button:hover { background:#1e293b; }

/* ── ESTRELA FAVORITAR ── última coluna de cada card ──────────────── */
div[class*="st-key-fav_"] button {
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
    box-shadow: none !important;
    width: auto !important;
    height: auto !important;
    min-height: 0 !important;
    padding: 2px 6px !important;
    font-size: 48px !important;
    color: #f59e0b !important;
    line-height: 1 !important;
}
div[class*="st-key-fav_"] button:hover {
    background: transparent !important;
    opacity: .75;
}

.card-img-box {
  width:100%; height:170px; border-radius:8px; overflow:hidden;
  background:#f1f5f9; display:flex; align-items:center; justify-content:center;
  margin-bottom:10px;
}
.card-img-box img { max-width:100%; max-height:170px; object-fit:contain; }

.banner-info {
  background: linear-gradient(135deg, #1e3a8a, #1e40af);
  color: #fff; padding: 14px 20px; border-radius: 12px; margin-bottom: 16px;
}
.banner-info h4 { margin: 0 0 8px 0; font-size: 14px; color: #fff !important; }
.banner-info-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.banner-tile { background: rgba(255,255,255,0.1); padding: 8px 12px; border-radius: 8px; }
.banner-tile .pct { font-size: 15px; font-weight: 700; color: #fff; }
.banner-tile .lbl { font-size: 11px; color: #bfdbfe; margin-top: 2px; }

.qtd-tag {
  display:inline-block; background:#fef3c7; color:#92400e;
  padding:3px 8px; border-radius:12px; font-size:11px; font-weight:600;
  margin-bottom:4px;
}

.ia-box {
  background:#f8fafc; border:1px solid #e2e8f0;
  border-radius:8px; padding:10px 12px; margin:8px 0;
  font-size:12px;
}
.ia-box .label { color:#64748b; font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:0.5px; margin-bottom:4px; }
.ia-box .rec { color:#334155; font-style:italic; margin-bottom:6px; line-height:1.5; }
.ia-box .ponto-pos { color:#16a34a; font-size:11px; line-height:1.6; }
.ia-box .ponto-neg { color:#dc2626; font-size:11px; line-height:1.6; }

/* ── MÉTRICAS ────────────────────────────────────────────────────── */
.metrics-grid {
  display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:0 0 16px 0;
}
.metric-card {
  background:#fff; border-radius:12px; padding:16px 20px;
  border:1px solid #e2e8f0; text-align:center;
}
.metric-label {
  font-size:11px; color:#64748b; font-weight:600;
  text-transform:uppercase; letter-spacing:0.5px; margin-bottom:6px;
}
.metric-value { font-size:28px; font-weight:700; line-height:1; }
.metric-green  { background:#f0fdf4; border-color:#bbf7d0; }
.metric-yellow { background:#fefce8; border-color:#fde68a; }
.metric-red    { background:#fef2f2; border-color:#fecaca; }

/* ── CABEÇALHO E ELEMENTOS DO STREAMLIT CLOUD ───────────────────── */
/* O controle para reabrir a sidebar é renderizado dentro do header.
   Por isso, o header não pode usar display:none. */
[data-testid="stHeader"] {
    background: transparent !important;
    pointer-events: none !important;
}

.viewerBadge_container__1QSob,
footer[data-testid="stFooter"],
#stDecoration { display: none !important; }

/* O botão de reabrir a sidebar fica dentro da toolbar. */
[data-testid="stToolbar"] {
    display: flex !important;
    visibility: visible !important;
    background: transparent !important;
    pointer-events: none !important;
}

/* Oculta somente os controles desnecessários da toolbar. */
[data-testid="stAppDeployButton"],
[data-testid="stMainMenu"],
[data-testid="stStatusWidget"] {
    display: none !important;
}

/* ── BOTÃO COLAPSO DA SIDEBAR ────────────────────────────────────── */
[data-testid="stSidebarCollapseButton"],
[data-testid="stExpandSidebarButton"],
[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    z-index: 999999 !important;
}

[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"] button,
[data-testid="collapsedControl"] button,
button[data-testid="baseButton-headerNoPadding"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    align-items: center !important;
    justify-content: center !important;
    background: #2563eb !important;
    border-radius: 50% !important;
    width: 2rem !important; height: 2rem !important;
    min-width: 2rem !important; border: none !important;
    padding: 0 !important;
    pointer-events: auto !important;
    box-shadow: 0 2px 8px rgba(37,99,235,.5) !important;
}

[data-testid="stSidebarCollapseButton"] button *,
[data-testid="stExpandSidebarButton"] button *,
[data-testid="collapsedControl"] button *,
button[data-testid="baseButton-headerNoPadding"] * {
    visibility: visible !important;
    opacity: 1 !important;
}

[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stExpandSidebarButton"] svg,
[data-testid="collapsedControl"] svg,
button[data-testid="baseButton-headerNoPadding"] svg {
    display: block !important;
    visibility: visible !important;
    color: #fff !important;
    fill: #fff !important;
}


/* ── RESPONSIVIDADE ─────────────────────────────────────────────── */
@media (max-width: 640px) {
    /* Métricas: 2×2 no mobile */
    .metrics-grid { grid-template-columns: repeat(2, 1fr) !important; }
    .metric-value { font-size: 22px !important; }

    /* Cards: 1 por linha */
    div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"]:has(div[data-testid="stVerticalBlockBorderWrapper"]) {
        min-width: 100% !important;
        flex: 1 1 100% !important;
    }
    .banner-info-grid { grid-template-columns: repeat(2, 1fr) !important; }
    .banner-tile .pct { font-size: 13px !important; }
    .banner-tile .lbl { font-size: 10px !important; }
    .card-img-box    { height: 140px !important; }
}

@media (min-width: 641px) and (max-width: 1024px) {
    div[data-testid="stHorizontalBlock"] { flex-wrap: wrap !important; }
    div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
        min-width: calc(50% - 8px) !important;
        flex: 1 1 calc(50% - 8px) !important;
    }
    .banner-info-grid { grid-template-columns: repeat(2, 1fr) !important; }
}

/* ── TEMA ADAPTATIVO E RESPONSIVIDADE V3 ────────────────────────── */
:root {
    --lce-bg: var(--background-color, #f5f7fb);
    --lce-surface: var(--secondary-background-color, #ffffff);
    --lce-text: var(--text-color, #0f172a);
    --lce-primary: var(--primary-color, #2563eb);
    --lce-muted: color-mix(in srgb, var(--lce-text) 66%, transparent);
    --lce-border: color-mix(in srgb, var(--lce-text) 18%, transparent);
    --lce-hover: color-mix(in srgb, var(--lce-primary) 14%, var(--lce-surface));
    --lce-shadow: 0 8px 24px color-mix(in srgb, #000 14%, transparent);
    --lce-radius: 12px;
}

/* Base: usa as variáveis de tema fornecidas pelo Streamlit. */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"] {
    background: var(--lce-bg) !important;
    color: var(--lce-text) !important;
    color-scheme: light dark;
}

[data-testid="stMainBlockContainer"] {
    max-width: 1440px !important;
    padding-top: 2.5rem !important;
    padding-right: clamp(1rem, 3vw, 3rem) !important;
    padding-left: clamp(1rem, 3vw, 3rem) !important;
}

.stMarkdown,
.stMarkdown p,
.stMarkdown li,
[data-testid="stCaptionContainer"],
[data-testid="stWidgetLabel"] {
    color: var(--lce-text);
}

[data-testid="stCaptionContainer"] {
    color: var(--lce-muted) !important;
}

/* Preserva as fontes de ícones; sem isso aparece o nome da seta. */
.material-symbols-rounded {
    font-family: "Material Symbols Rounded" !important;
    font-weight: normal !important;
    font-style: normal !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    font-feature-settings: "liga" !important;
    -webkit-font-feature-settings: "liga" !important;
    -webkit-font-smoothing: antialiased !important;
}

.material-symbols-outlined {
    font-family: "Material Symbols Outlined" !important;
    font-weight: normal !important;
    font-style: normal !important;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    font-feature-settings: "liga" !important;
    -webkit-font-feature-settings: "liga" !important;
    -webkit-font-smoothing: antialiased !important;
}

/* Cards e contêineres. */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: color-mix(in srgb, var(--lce-surface) 92%, var(--lce-bg)) !important;
    border-color: var(--lce-border) !important;
    border-radius: var(--lce-radius) !important;
    box-shadow: 0 2px 10px color-mix(in srgb, #000 7%, transparent);
}

.card-img-box,
.ia-box {
    background: color-mix(in srgb, var(--lce-surface) 82%, var(--lce-bg)) !important;
    border-color: var(--lce-border) !important;
    color: var(--lce-text) !important;
}

.ia-box .label { color: var(--lce-muted) !important; }
.ia-box .rec { color: var(--lce-text) !important; }

.orientation-box {
    margin: 8px 0;
    padding: 8px 12px;
    background: color-mix(in srgb, var(--orientation-color) 12%, var(--lce-surface));
    border-left: 3px solid var(--orientation-color);
    border-radius: 6px;
}

.orientation-box span {
    color: color-mix(in srgb, var(--orientation-color) 78%, var(--lce-text));
    font-size: 13px;
    font-weight: 700;
}

.metric-card {
    background: var(--lce-surface) !important;
    border-color: var(--lce-border) !important;
    box-shadow: 0 2px 10px color-mix(in srgb, #000 6%, transparent);
}
.metric-label { color: var(--lce-muted) !important; }
.metric-card .metric-value { color: var(--lce-text) !important; }
.metric-green {
    background: color-mix(in srgb, #16a34a 13%, var(--lce-surface)) !important;
    border-color: color-mix(in srgb, #16a34a 45%, var(--lce-border)) !important;
}
.metric-yellow {
    background: color-mix(in srgb, #eab308 13%, var(--lce-surface)) !important;
    border-color: color-mix(in srgb, #eab308 45%, var(--lce-border)) !important;
}
.metric-red {
    background: color-mix(in srgb, #ef4444 13%, var(--lce-surface)) !important;
    border-color: color-mix(in srgb, #ef4444 45%, var(--lce-border)) !important;
}
.metric-green .metric-value {
    color: color-mix(in srgb, #22c55e 72%, var(--lce-text)) !important;
}
.metric-yellow .metric-value {
    color: color-mix(in srgb, #eab308 72%, var(--lce-text)) !important;
}
.metric-red .metric-value {
    color: color-mix(in srgb, #ef4444 72%, var(--lce-text)) !important;
}

.ia-box .ponto-pos {
    color: color-mix(in srgb, #22c55e 72%, var(--lce-text)) !important;
}
.ia-box .ponto-neg {
    color: color-mix(in srgb, #ef4444 72%, var(--lce-text)) !important;
}

.stMarkdown a {
    color: var(--lce-primary);
}

hr, [data-testid="stDivider"] {
    border-color: var(--lce-border) !important;
}

/* Entradas e listas abertas fora da sidebar. */
input,
textarea,
[data-baseweb="select"] > div,
[data-baseweb="input"] > div {
    background: var(--lce-surface) !important;
    color: var(--lce-text) !important;
    border-color: var(--lce-border) !important;
}

input::placeholder,
textarea::placeholder {
    color: var(--lce-muted) !important;
    opacity: 1 !important;
}

[data-baseweb="popover"],
[data-baseweb="menu"],
[role="listbox"] {
    background: var(--lce-surface) !important;
    color: var(--lce-text) !important;
}

[role="option"] {
    background: transparent !important;
    color: var(--lce-text) !important;
}

[role="option"]:hover,
[role="option"][aria-selected="true"] {
    background: var(--lce-hover) !important;
    color: var(--lce-text) !important;
}

/* Botões gerais: contraste estável nos dois temas. */
div[data-testid="stButton"] button,
[data-testid="stFormSubmitButton"] button,
[data-testid="stLinkButton"] a,
[data-testid="stDownloadButton"] button {
    min-height: 2.5rem !important;
    background: var(--lce-primary) !important;
    color: #ffffff !important;
    border: 1px solid color-mix(in srgb, var(--lce-primary) 82%, #000) !important;
    border-radius: 8px !important;
    box-shadow: none !important;
}

div[data-testid="stButton"] button:hover,
[data-testid="stFormSubmitButton"] button:hover,
[data-testid="stLinkButton"] a:hover,
[data-testid="stDownloadButton"] button:hover {
    background: color-mix(in srgb, var(--lce-primary) 82%, #000) !important;
    color: #ffffff !important;
    border-color: var(--lce-primary) !important;
}

div[data-testid="stButton"] button:focus-visible,
[data-testid="stLinkButton"] a:focus-visible {
    outline: 3px solid color-mix(in srgb, var(--lce-primary) 38%, transparent) !important;
    outline-offset: 2px !important;
}

/* Favoritar: não afeta paginação nem outros últimos botões de colunas. */
div[class*="st-key-fav_"] button,
div[class*="st-key-fav_"] button:hover {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    min-height: 0 !important;
    color: #f59e0b !important;
}

/* Abas legíveis e roláveis em telas estreitas. */
.stTabs [data-baseweb="tab-list"] {
    gap: .25rem !important;
    overflow-x: auto !important;
    scrollbar-width: thin;
}

.stTabs [data-baseweb="tab"] {
    color: var(--lce-muted) !important;
    flex: 0 0 auto !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"] {
    color: var(--lce-primary) !important;
}

/* Sidebar permanece azul-escura e independente do tema principal. */
section[data-testid="stSidebar"] {
    background: #172554 !important;
    color: #e2e8f0 !important;
    border-right: 1px solid rgba(255,255,255,.12) !important;
}

section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] label {
    color: #e2e8f0;
}

section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: transparent !important;
    border-color: rgba(255,255,255,.35) !important;
    color: #ffffff !important;
}

/* Placeholder do multiselect "Marca" — mesma cor do texto padrão dos demais selects. */
section[data-testid="stSidebar"] input::placeholder {
    color: #ffffff !important;
    opacity: 1 !important;
}

/* Navegação da sidebar sobrescreve o estilo geral de botões. */
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"],
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-secondary"] {
    background: transparent !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(255,255,255,.22) !important;
}

section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"]:hover,
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-secondary"]:hover {
    background: transparent !important;
    border-color: rgba(255,255,255,.7) !important;
    color: #ffffff !important;
}

section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"],
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-primary"] {
    background: transparent !important;
    color: #ffffff !important;
    border: 2px solid #ffffff !important;
}

/* Header/toolbar e controle da sidebar. */
[data-testid="stHeader"] {
    display: block !important;
    visibility: visible !important;
    background: transparent !important;
    pointer-events: none !important;
}

[data-testid="stToolbar"] {
    display: flex !important;
    visibility: visible !important;
    background: transparent !important;
    pointer-events: none !important;
}

[data-testid="stSidebarCollapseButton"],
[data-testid="stExpandSidebarButton"],
[data-testid="collapsedControl"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    z-index: 999999 !important;
}

[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"] button,
[data-testid="collapsedControl"] button,
button[data-testid="baseButton-headerNoPadding"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    align-items: center !important;
    justify-content: center !important;
    width: 2rem !important;
    min-width: 2rem !important;
    height: 2rem !important;
    min-height: 2rem !important;
    padding: 0 !important;
    background: #2563eb !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 50% !important;
    pointer-events: auto !important;
    box-shadow: 0 2px 8px rgba(37,99,235,.45) !important;
}

[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stExpandSidebarButton"] svg,
[data-testid="collapsedControl"] svg,
button[data-testid="baseButton-headerNoPadding"] svg {
    display: block !important;
    visibility: visible !important;
    color: #ffffff !important;
    fill: #ffffff !important;
}

/* Tablet: dois cards por linha. */
@media (min-width: 701px) and (max-width: 1100px) {
    div[data-testid="stHorizontalBlock"]:has(
      > div[data-testid="column"] > div > div[data-testid="stVerticalBlockBorderWrapper"]
    ) {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 1rem !important;
    }

    div[data-testid="stHorizontalBlock"]:has(
      > div[data-testid="column"] > div > div[data-testid="stVerticalBlockBorderWrapper"]
    ) > div[data-testid="column"] {
        width: 100% !important;
        min-width: 0 !important;
    }
}

/* Mobile: uma coluna, áreas de toque maiores e menos espaçamento. */
@media (max-width: 700px) {
    [data-testid="stMainBlockContainer"] {
        padding-top: 3.25rem !important;
        padding-right: .75rem !important;
        padding-left: .75rem !important;
    }

    section[data-testid="stSidebar"] {
        width: min(88vw, 22rem) !important;
        min-width: min(88vw, 22rem) !important;
    }

    div[data-testid="stHorizontalBlock"]:has(
      > div[data-testid="column"] > div > div[data-testid="stVerticalBlockBorderWrapper"]
    ) {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) !important;
        gap: .875rem !important;
    }

    div[data-testid="stHorizontalBlock"]:has(
      > div[data-testid="column"] > div > div[data-testid="stVerticalBlockBorderWrapper"]
    ) > div[data-testid="column"] {
        width: 100% !important;
        min-width: 0 !important;
    }

    .metrics-grid,
    .banner-info-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
    }

    .metric-card { padding: 14px 10px !important; }
    .metric-value { font-size: 22px !important; }
    .banner-info { padding: 14px !important; }
    .banner-tile { padding: 9px !important; }
    .card-img-box { height: 150px !important; }
    .card-img-box img { max-height: 150px !important; }

    div[data-testid="stButton"] button,
    [data-testid="stLinkButton"] a,
    [data-testid="stDownloadButton"] button {
        min-height: 44px !important;
    }
}

@media (max-width: 430px) {
    .metrics-grid,
    .banner-info-grid {
        grid-template-columns: minmax(0, 1fr) !important;
    }

    .metric-card { text-align: left !important; }
    .metric-value { font-size: 20px !important; }
    .pill { margin-bottom: 6px !important; }
}

/* Fallback para navegadores sem color-mix. */
@supports not (color: color-mix(in srgb, white 50%, black)) {
    :root {
        --lce-muted: #64748b;
        --lce-border: #cbd5e1;
        --lce-hover: #dbeafe;
    }
}
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=1800)
def carregar():
    arquivo = BASE_DIR / "leiloes.json"
    if arquivo.exists():
        with arquivo.open("r", encoding="utf-8") as f:
            return json.load(f)
    return []


@st.cache_data(ttl=60)
def carregar_historico_tokens(limite=30):
    """Lê as últimas execuções registradas pelo scraper."""
    arquivo = BASE_DIR / "historico_tokens_ia.jsonl"
    if not arquivo.exists():
        return []

    registros = []
    try:
        with arquivo.open("r", encoding="utf-8") as f:
            linhas = f.readlines()[-limite:]

        for linha in linhas:
            linha = linha.strip()
            if not linha:
                continue
            try:
                registro = json.loads(linha)
                if isinstance(registro, dict):
                    registros.append(registro)
            except json.JSONDecodeError:
                continue
    except Exception:
        return []

    return registros


def _numero(valor):
    try:
        return int(valor or 0)
    except (TypeError, ValueError):
        return 0


def _horario_execucao(valor):
    if not valor:
        return "Horário não informado"
    try:
        dt = datetime.fromisoformat(str(valor))
        return dt.strftime("%d/%m/%Y às %H:%M")
    except (TypeError, ValueError):
        return str(valor)


def render_painel_tokens():
    historico = carregar_historico_tokens()

    with st.expander("📊 Economia de tokens da IA", expanded=False):
        if not historico:
            st.info(
                "Ainda não há histórico. Ele aparecerá depois que o scraper "
                "das 03:00 ou das 15:00 terminar e enviar "
                "historico_tokens_ia.jsonl para o repositório."
            )
            return

        atual = historico[-1]
        anterior = historico[-2] if len(historico) > 1 else None

        tokens_atual = _numero(atual.get("total_tokens"))
        chamadas_atual = _numero(atual.get("api_tentativas"))
        cache_atual = _numero(atual.get("cache_hits"))
        lotes_atual = _numero(atual.get("total_lotes"))
        taxa_atual = float(atual.get("taxa_cache_pct", 0) or 0)

        delta_tokens = None
        delta_chamadas = None
        reducao = None
        if anterior:
            tokens_anterior = _numero(anterior.get("total_tokens"))
            chamadas_anterior = _numero(anterior.get("api_tentativas"))
            delta_tokens = tokens_atual - tokens_anterior
            delta_chamadas = chamadas_atual - chamadas_anterior
            if tokens_anterior > 0:
                reducao = ((tokens_anterior - tokens_atual) / tokens_anterior) * 100

        st.caption(
            f"Último scraper: {_horario_execucao(atual.get('executado_em'))} "
            "• Execuções programadas: 03:00 e 15:00"
        )

        c1, c2, c3, c4 = st.columns(4)
        c1.metric(
            "Tokens usados",
            f"{tokens_atual:,}".replace(",", "."),
            delta=(f"{delta_tokens:+,}".replace(",", ".") + " vs. anterior")
            if delta_tokens is not None else None,
            delta_color="inverse",
        )
        c2.metric(
            "Chamadas à IA",
            chamadas_atual,
            delta=f"{delta_chamadas:+d} vs. anterior"
            if delta_chamadas is not None else None,
            delta_color="inverse",
        )
        c3.metric("Reutilizados do cache", cache_atual)
        c4.metric("Taxa de cache", f"{taxa_atual:.1f}%")

        if chamadas_atual == 0 and cache_atual > 0:
            st.success(
                "Esta execução não gastou tokens com os veículos já analisados: "
                "as análises foram recuperadas do cache."
            )
        elif reducao is not None and reducao > 0:
            st.success(
                f"O consumo caiu {reducao:.1f}% em relação à execução anterior."
            )
        elif reducao is not None and reducao < 0:
            st.warning(
                f"O consumo aumentou {abs(reducao):.1f}%. Verifique se entraram "
                "lotes novos ou se descrições/quilometragens foram alteradas."
            )
        else:
            st.info(
                "Esta é a primeira execução registrada; a comparação ficará "
                "disponível após o próximo scraper."
            )

        st.caption(
            f"{lotes_atual} lotes processados • "
            f"{_numero(atual.get('sem_dados'))} sem dados suficientes • "
            f"{_numero(atual.get('api_erros'))} erros de IA/JSON"
        )

        if len(historico) > 1:
            tabela = []
            for item in reversed(historico[-8:]):
                tabela.append({
                    "Execução": _horario_execucao(item.get("executado_em")),
                    "Lotes": _numero(item.get("total_lotes")),
                    "Chamadas": _numero(item.get("api_tentativas")),
                    "Cache": _numero(item.get("cache_hits")),
                    "Taxa cache": f"{float(item.get('taxa_cache_pct', 0) or 0):.1f}%",
                    "Tokens": _numero(item.get("total_tokens")),
                })
            st.markdown("##### Últimas execuções")
            st.dataframe(tabela, use_container_width=True, hide_index=True)

def pill_classif(c):
    if "ÓTIMO"       in c: return '<span class="pill p-otimo">✅ ÓTIMO</span>'
    if "MEDIANO"     in c: return '<span class="pill p-mediano">⚠️ MEDIANO</span>'
    if "INSPECIONAR" in c: return '<span class="pill p-inspec">⚠️ INSPECIONAR</span>'
    if "RUIM"        in c: return '<span class="pill p-ruim">❌ RUIM</span>'
    return '<span class="pill p-semref">Sem referência</span>'

def pill_estado(s):
    if "Bom estado"         in s: return '<span class="pill p-ebom">🟢 Bom estado</span>'
    if "Rec. Financiamento" in s: return '<span class="pill p-rec">🔵 Rec. Financiamento</span>'
    if "Batido"             in s: return '<span class="pill p-bat">🟡 Batido</span>'
    if "Sinistrado"         in s: return '<span class="pill p-sin">🔴 Sinistrado</span>'
    return '<span class="pill p-ni">⚪ Não informado</span>'

def orientacao_uso(lance, fipe, estado, qtd=1):
    if estado in ["SINISTRADO","BATIDO","SUCATA"]:
        economia = fipe - lance if fipe > lance > 0 else 0
        economia_str = f" (economia ~R$ {economia:,.0f})" if economia > 0 else ""
        return "🔧", f"Verifique custo de reparo antes de arrematar{economia_str}", "#c2410c"
    if estado == "RECUPERADO_FINANCIAMENTO":
        return "🔵", "Consulte restrições no cartório antes de arrematar", "#1d4ed8"
    if fipe == 0 or lance == 0:
        return "❓", "Sem referência de preço — avalie com cuidado", "#64748b"
    valor_unitario = lance / qtd if qtd > 1 else lance
    pct = (valor_unitario / fipe) * 100
    if pct <= 35: return "🌟", f"EXCELENTE — {pct:.0f}% da FIPE (ótimo para revenda)", "#15803d"
    if pct <= 50: return "💼", f"Ótimo negócio — {pct:.0f}% da FIPE", "#16a34a"
    if pct <= 75: return "🏠", f"Bom para uso próprio — {pct:.0f}% da FIPE", "#ca8a04"
    return "⚠️", f"Avalie com cuidado — {pct:.0f}% da FIPE", "#dc2626"

def desconto_str(lance, fipe, qtd=1):
    valor_unitario = lance / qtd if qtd > 1 else lance
    if fipe > 0 and valor_unitario > 0:
        pct = (1 - valor_unitario/fipe) * 100
        if pct > 0:  return f"▼ {pct:.0f}% abaixo da referência", "#16a34a"
        else:        return f"▲ {abs(pct):.0f}% acima da referência", "#dc2626"
    return None, None

ITEMS_PER_PAGE = 50

def render_lotes(lotes_lista, key="main"):
    icones_cat = {"carros":"🚗","motos":"🏍️","caminhoes":"🚛","imoveis":"🏠",
                  "casas":"🏡","terrenos":"🌍","equipamentos":"⚙️","eletronicos":"📱","outros":"📦"}

    total        = len(lotes_lista)
    total_pages  = max(1, (total + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page_key     = f"page_{key}"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    page = max(1, min(st.session_state[page_key], total_pages))
    st.session_state[page_key] = page

    start         = (page - 1) * ITEMS_PER_PAGE
    lotes_pagina  = lotes_lista[start : start + ITEMS_PER_PAGE]

    cols = st.columns(3)
    for i, lote in enumerate(lotes_pagina):
        lance   = lote["lance_atual"]
        fipe    = lote["fipe_valor"]
        foto    = lote.get("foto","")
        km      = lote.get("km","")
        qtd     = lote.get("quantidade", 1)
        selo    = lote.get("estado_selo","⚪ Não informado")
        estado  = lote.get("estado","NAO_INFORMADO")
        uso     = lote.get("uso_sugerido","")
        rec     = lote.get("avaliacao_plataforma","")
        pos     = lote.get("positivos",[])
        neg     = lote.get("negativos",[])
        classif = lote.get("classificacao","Sem referência")
        cat     = lote.get("categoria","outros")
        icone_o, txt_o, cor_o = orientacao_uso(lance, fipe, estado, qtd)
        desc_txt, desc_cor    = desconto_str(lance, fipe, qtd)

        with cols[i % 3]:
            with st.container(border=True):
                # Foto
                if foto:
                    st.markdown(f'<div class="card-img-box"><img src="{foto}"></div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="card-img-box" style="font-size:48px">{icones_cat.get(cat,"📦")}</div>', unsafe_allow_html=True)

                # Qtd
                if qtd > 1:
                    st.markdown(f'<span class="qtd-tag">📦 {qtd} unidades neste lote</span>', unsafe_allow_html=True)

                # Badges
                st.markdown(f"{pill_classif(classif)} {pill_estado(selo)}", unsafe_allow_html=True)

                # Título
                st.markdown(f"**{lote['marca']} {lote['modelo']}**")
                meta = f"📅 {lote['ano']} • 📍 {lote.get('cidade','')}"
                if km: meta += f" • 🛣️ {km}"
                _data = lote.get("data_leilao", "")
                if _data:
                    try:
                        _dt = datetime.fromisoformat(_data)
                        meta += f" • 🔔 {_dt.strftime('%d/%m às %Hh%M')}"
                    except:
                        pass
                st.caption(meta)

                # Preços
                col_l, col_f = st.columns(2)
                if qtd > 1:
                    col_l.markdown(f"**Lance total**\n\n### R$ {lance:,.0f}")
                    col_f.markdown(f"**Por unidade**\n\n### R$ {lance/qtd:,.0f}")
                    if fipe > 0:
                        st.caption(f"FIPE/Ref por unidade: R$ {fipe:,.0f}")
                else:
                    col_l.markdown(f"**Lance atual**\n\n### R$ {lance:,.0f}")
                    if fipe > 0:
                        col_f.markdown(f"**FIPE / Referência**\n\n~~R$ {fipe:,.0f}~~")
                    else:
                        col_f.markdown("**FIPE / Referência**\n\n*Indisponível*")

                if desc_txt:
                    st.markdown(f"<p style='color:{desc_cor};font-weight:600;font-size:12px;margin:4px 0 8px'>{desc_txt}</p>", unsafe_allow_html=True)

                # Orientação (destaque)
                st.markdown(
                    f"<div class='orientation-box' style='--orientation-color:{cor_o}'>"
                    f"<span>{icone_o} {txt_o}</span>"
                    f"</div>",
                    unsafe_allow_html=True
                )

                # Análise IA — direto no card, sem expander
                if rec or pos or neg or uso:
                    ia_html = '<div class="ia-box"><div class="label">🤖 Análise da IA</div>'
                    if rec:
                        ia_html += f'<div class="rec">{rec}</div>'
                    if uso:
                        ia_html += f'<div style="font-size:11px;color:#1d4ed8;font-weight:600;margin-bottom:6px">🎯 Uso sugerido: {uso}</div>'
                    for pt in pos[:2]:
                        ia_html += f'<div class="ponto-pos">✅ {pt}</div>'
                    for nt in neg[:2]:
                        ia_html += f'<div class="ponto-neg">❌ {nt}</div>'
                    ia_html += '</div>'
                    st.markdown(ia_html, unsafe_allow_html=True)

                # Botão Google Calendar (quando há data disponível)
                if _data:
                    try:
                        _dt    = datetime.fromisoformat(_data)
                        _dt_e  = _dt + timedelta(hours=1)
                        _ds    = _dt.strftime("%Y%m%dT%H%M00")
                        _de    = _dt_e.strftime("%Y%m%dT%H%M00")
                        _title = quote(f"{lote.get('marca','')} {lote.get('modelo','')} {lote.get('ano','')}")
                        _det   = quote(f"Lance: R$ {lance:,.0f} | {lote.get('cidade','')} | LeilãoCE")
                        _loc   = quote(lote.get('cidade',''))
                        _cal   = (f"https://calendar.google.com/calendar/render?action=TEMPLATE"
                                  f"&text={_title}&dates={_ds}/{_de}&details={_det}&location={_loc}")
                        st.markdown(f"[📅 Salvar no Google Calendar]({_cal})")
                    except:
                        pass

                col_link, col_fav = st.columns([4, 1])
                _fonte_label = {"mega": "Mega Leilões", "pacto": "Pacto", "leilo": "Leilo", "construbem": "Construbem", "danielgarcia": "Daniel Garcia", "mj": "MJ Leilões", "celsocunha": "Celso Cunha"}.get(lote.get("fonte",""), "Leilão")
                col_link.markdown(f"[🔗 Ver lote na {_fonte_label} →]({lote['url']})")
                lote_url = lote.get("url", "")
                heart = "★" if is_favorite(lote_url) else "☆"
                if col_fav.button(heart, key=f"fav_{key}_{i}", help="Favoritar"):
                    _usr = get_user()
                    _ses = st.session_state.get("session")
                    if _usr and _ses:
                        from auth import get_profile
                        _profile = get_profile() or {}
                        toggle_favorite(_usr.id, _ses.access_token, lote, phone=_profile.get("phone", ""))
                        st.rerun()
                    else:
                        st.toast("Faça login para favoritar ⭐")

    if total_pages > 1:
        st.markdown("---")
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if page > 1 and st.button("← Anterior", key=f"prev_{key}"):
                st.session_state[page_key] = page - 1
                st.rerun()
        with c2:
            st.markdown(
                f"<p style='text-align:center;color:#64748b;font-size:13px'>"
                f"Página <b>{page}</b> de {total_pages} &nbsp;•&nbsp; {total} lotes</p>",
                unsafe_allow_html=True
            )
        with c3:
            if page < total_pages and st.button("Próxima →", key=f"next_{key}"):
                st.session_state[page_key] = page + 1
                st.rerun()

def pagina_sobre():
    st.markdown("## 📌 Sobre o LeilãoCE")
    st.markdown("""
O **LeilãoCE** é uma plataforma de **análise e direcionamento** de oportunidades em leilões de veículos, imóveis e equipamentos no Ceará.

### Como funcionamos
- **Não vendemos nada.** Somos um sistema independente de análise.
- Monitoramos leilões públicos em sites parceiros como a **Leilo**.
- Comparamos com a **Tabela FIPE** e referências de mercado.
- Usamos **inteligência artificial** para analisar o estado e a viabilidade de cada lote.

### Nosso objetivo
Democratizar o acesso a leilões e ajudar você a tomar decisões informadas, evitando armadilhas comuns e identificando boas oportunidades reais.

### Importante
Não somos leiloeiros, nem afiliados a sites de leilão. Sempre confirme as informações diretamente na plataforma do leilão antes de dar lances.
""")

def pagina_como_comprar():
    st.markdown("## 🛒 Como Comprar em Leilões")
    st.markdown("""
### Passo a passo
1. **Encontre o lote no LeilãoCE** — use os filtros e análises
2. **Clique em "Ver lote na Leilo"** — você será direcionado ao site oficial
3. **Cadastre-se na plataforma do leilão**
4. **Verifique a documentação completa do lote:**
   - Edital do leilão
   - Laudo de vistoria
   - Pendências do bem
   - Custos extras
5. **Faça uma visita presencial** sempre que possível
6. **Dê seu lance** dentro do prazo
7. **Após arrematar:** pague o sinal, taxa do leiloeiro e retire o bem

### Custos típicos
- Lance arrematado
- Taxa do leiloeiro (geralmente 5%)
- Comissão de pagamento (1-3%)
- Transferência e regularização
- Transporte e reparos
""")

def pagina_favoritos():
    favs = list(get_favorites().values())
    st.markdown("## ⭐ Meus Favoritos")
    if not favs:
        st.info("Você ainda não favoritou nenhum lote. Clique em 🤍 em qualquer card para favoritar.")
        return
    st.caption(f"{len(favs)} lote(s) favoritado(s)")
    render_lotes(favs, key="favs")


def pagina_informacoes():
    st.markdown("## ⚠️ Informações Importantes")
    st.markdown("""
### Riscos comuns em leilões
🔴 **Veículos sinistrados** — podem ter danos estruturais não visíveis. Sempre faça inspeção técnica.

🔴 **Pendências jurídicas** — débitos podem ser de responsabilidade do arrematante.

🔴 **Restrições de transferência** — alguns lotes podem ter restrições.

### Documentos a verificar
- CRLV
- Comprovante de quitação de débitos
- Laudo de vistoria oficial
- Edital completo do leilão

### Dicas práticas
✅ Estabeleça orçamento máximo e respeite

✅ Considere todos os custos, não só o lance

✅ Para uso comercial: até 50% da FIPE

✅ Para uso próprio: até 70% da FIPE com bom estado

✅ Sinistrados só valem se você tiver oficina ou contato com mecânico

### Aviso legal
O LeilãoCE não se responsabiliza por decisões de compra. As análises são orientativas.
""")

# ─── APP ──────────────────────────────────────────────────────────────────────

# Auth gate: temporarily disabled for public beta
# if not get_user():
#     render_auth_page()
#     st.stop()

_session = st.session_state.get("session")
if "favorites" not in st.session_state and _session:
    load_favorites(get_user().id, _session.access_token)

lotes = carregar()

components.html("""
<script>
(function() {
  function applyFixes(doc) {
    // ── Cor da estrela (☆ cinza / ★ amarelo) ─────────────────────────
    doc.querySelectorAll('button').forEach(function(btn) {
      var t = btn.textContent.trim();
      if (t.includes('★') || t.includes('☆')) {
        var cor = t.includes('★') ? '#f59e0b' : '#9ca3af';
        btn.style.setProperty('color', cor, 'important');
        btn.querySelectorAll('*').forEach(function(el) {
          el.style.setProperty('color', cor, 'important');
        });
      }
    });
  }

  try {
    var doc = window.parent.document;
    applyFixes(doc);
    new MutationObserver(function() { applyFixes(doc); })
      .observe(doc.body, {childList:true, subtree:true});
  } catch(e) {}
})();
</script>
""", height=0)

if "pagina" not in st.session_state:
    st.session_state["pagina"] = "leiloes"

with st.sidebar:
    user = get_user()
    n_favs = len(get_favorites())

    st.markdown("""
    <div style="padding:1rem 0 .5rem;">
      <div style="font-size:1.15rem;font-weight:800;color:#111827;">🚗 LeilãoCE</div>
      <div style="font-size:.75rem;color:#9ca3af;margin-top:2px;">Monitor de Leilões do Ceará</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    # ── NAVEGAÇÃO PRINCIPAL ──────────────────────────────────────────────
    p = st.session_state["pagina"]

    if st.button("🏠  Leilões", key="nav_leiloes", use_container_width=True,
                 type="primary" if p == "leiloes" else "secondary"):
        st.session_state["pagina"] = "leiloes"
        st.rerun()

    fav_label = f"⭐  Favoritos  ({n_favs})" if n_favs else "⭐  Favoritos"
    if st.button(fav_label, key="nav_favs", use_container_width=True,
                 type="primary" if p == "favoritos" else "secondary"):
        st.session_state["pagina"] = "favoritos"
        st.rerun()

    st.markdown("---")

    # ── FILTROS ──────────────────────────────────────────────────────────
    st.markdown("""<div style="font-size:.72rem;font-weight:700;color:#9ca3af;
                text-transform:uppercase;letter-spacing:.07em;
                margin-bottom:.5rem;">Filtros</div>""", unsafe_allow_html=True)

    cats_existentes = sorted(set(l.get("categoria","") for l in lotes))
    cats_completas  = ["carros","motos","caminhoes","imoveis","casas","terrenos","equipamentos","eletronicos"]
    cats    = ["Todas"] + sorted(set(cats_existentes + cats_completas))
    marcas  = sorted(set(l["marca"] for l in lotes))
    cidades = ["Todas"] + sorted(set(l.get("cidade","") for l in lotes))
    classes = ["Todas","✅ ÓTIMO","⚠️ MEDIANO","❌ RUIM","⚠️ INSPECIONAR","Sem referência"]
    estados = ["Todos","Bom estado","Rec. Financiamento","Batido","Sinistrado","Não informado"]

    f_cat    = st.selectbox("Categoria", cats)
    f_class  = st.selectbox("Classificação", classes)
    f_estado = st.selectbox("Estado", estados)
    f_cidade = st.selectbox("Cidade", cidades)
    f_marca  = st.multiselect("Marca", marcas, placeholder="Todas")
    lance_max = max((l["lance_atual"] for l in lotes if l["lance_atual"] > 0), default=500000)
    f_lance  = st.slider("Lance máximo (R$)", 0, int(lance_max), int(lance_max), step=1000)

    fil_hash = (f_cat, f_class, f_estado, f_cidade, tuple(f_marca), f_lance)
    if st.session_state.get("_fil_hash") != fil_hash:
        for k in list(st.session_state.keys()):
            if k.startswith("page_"):
                st.session_state[k] = 1
        st.session_state["_fil_hash"] = fil_hash

    st.markdown("---")

    # ── INFORMAÇÕES ──────────────────────────────────────────────────────
    st.markdown("""<div style="font-size:.72rem;font-weight:700;color:#9ca3af;
                text-transform:uppercase;letter-spacing:.07em;
                margin-bottom:.5rem;">Informações</div>""", unsafe_allow_html=True)

    if st.button("📌  Sobre", key="nav_sobre", use_container_width=True,
                 type="primary" if p == "sobre" else "secondary"):
        st.session_state["pagina"] = "sobre"
        st.rerun()

    if st.button("🛒  Como comprar", key="nav_comprar", use_container_width=True,
                 type="primary" if p == "comprar" else "secondary"):
        st.session_state["pagina"] = "comprar"
        st.rerun()

    if st.button("⚠️  Informações", key="nav_info", use_container_width=True,
                 type="primary" if p == "informacoes" else "secondary"):
        st.session_state["pagina"] = "informacoes"
        st.rerun()

    st.markdown("---")

    # ── USUÁRIO ──────────────────────────────────────────────────────────
    if user:
        st.markdown(f"""<div style="padding:.4rem 0;">
          <div style="font-size:.72rem;color:#9ca3af;margin-bottom:.2rem;">Conta</div>
          <div style="font-size:.82rem;color:#374151;font-weight:500;
                      white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
            {user.email}</div>
        </div>""", unsafe_allow_html=True)
    if st.button("Sair", key="btn_sair", use_container_width=True):
        logout()
        st.rerun()

pagina = st.session_state.get("pagina", "leiloes")
if pagina == "favoritos":   pagina_favoritos(); st.stop()
if pagina == "sobre":       pagina_sobre(); st.stop()
if pagina == "comprar":     pagina_como_comprar(); st.stop()
if pagina == "informacoes": pagina_informacoes(); st.stop()

if not lotes:
    st.warning("Nenhum lote encontrado. Os dados são atualizados automaticamente 2x ao dia.")
    st.stop()

fil = lotes.copy()
if f_cat != "Todas":    fil = [l for l in fil if l.get("categoria") == f_cat]
if f_marca:             fil = [l for l in fil if l["marca"] in f_marca]
if f_class != "Todas":  fil = [l for l in fil if f_class in l.get("classificacao","")]
if f_estado != "Todos": fil = [l for l in fil if f_estado in l.get("estado_selo","")]
if f_cidade != "Todas": fil = [l for l in fil if l.get("cidade") == f_cidade]
fil = [l for l in fil if l["lance_atual"] <= f_lance]

st.markdown("### 🚗 Monitor de Leilões — Ceará")
st.caption(f"Análise com IA • Comparação com FIPE/mercado • {len(fil)} lotes exibidos")

st.markdown("""
<div class="banner-info">
  <h4>💡 Como decidir se vale a pena</h4>
  <div class="banner-info-grid">
    <div class="banner-tile"><div class="pct">🌟 Até 30%</div><div class="lbl">Excelente oportunidade</div></div>
    <div class="banner-tile"><div class="pct">💼 31-50%</div><div class="lbl">Ótimo para revenda/locação</div></div>
    <div class="banner-tile"><div class="pct">🏠 51-70%</div><div class="lbl">Bom para uso próprio</div></div>
    <div class="banner-tile"><div class="pct">⚠️ +70%</div><div class="lbl">Pouco vantajoso — avalie</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

total  = len(lotes)
otimos = sum(1 for l in lotes if "ÓTIMO"   in l.get("classificacao",""))
medios = sum(1 for l in lotes if "MEDIANO" in l.get("classificacao",""))
ruins  = sum(1 for l in lotes if "RUIM"    in l.get("classificacao","") or "INSPECIONAR" in l.get("classificacao",""))

st.markdown(f"""
<div class="metrics-grid">
  <div class="metric-card">
    <div class="metric-label">Total de lotes</div>
    <div class="metric-value" style="color:#0f172a">{total}</div>
  </div>
  <div class="metric-card metric-green">
    <div class="metric-label">✅ Ótimas</div>
    <div class="metric-value" style="color:#15803d">{otimos}</div>
  </div>
  <div class="metric-card metric-yellow">
    <div class="metric-label">⚠️ Medianas</div>
    <div class="metric-value" style="color:#a16207">{medios}</div>
  </div>
  <div class="metric-card metric-red">
    <div class="metric-label">❌ Ruins/Inspecionar</div>
    <div class="metric-value" style="color:#b91c1c">{ruins}</div>
  </div>
</div>
""", unsafe_allow_html=True)

render_painel_tokens()

st.divider()

if not fil:
    st.info("Nenhum lote encontrado com os filtros aplicados.")
    st.stop()

icones_cat = {"carros":"🚗","motos":"🏍️","caminhoes":"🚛","imoveis":"🏠",
              "casas":"🏡","terrenos":"🌍","equipamentos":"⚙️","eletronicos":"📱","outros":"📦"}
cats_presentes = sorted(set(l.get("categoria","outros") for l in fil))

abas_labels = ["🏠 Todos"] + [f"{icones_cat.get(c,'📦')} {c.title()}" for c in cats_presentes]
abas = st.tabs(abas_labels)

with abas[0]:
    st.caption(f"{len(fil)} lotes")
    render_lotes(fil, key="todos")

for aba, categoria in zip(abas[1:], cats_presentes):
    lotes_cat = [l for l in fil if l.get("categoria") == categoria]
    with aba:
        st.caption(f"{len(lotes_cat)} lotes")
        render_lotes(lotes_cat, key=categoria)
