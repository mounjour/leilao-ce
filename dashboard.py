import streamlit as st
import streamlit.components.v1 as components
import json
import os
from html import escape
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from auth import (
    create_billing_portal_url,
    ensure_valid_session,
    get_display_name,
    get_profile,
    get_user,
    is_subscribed,
    logout,
    refresh_profile,
    render_auth_page,
    render_paywall,
)
from favorites import load_favorites, get_favorites, is_favorite, toggle_favorite

st.set_page_config(page_title="Achadinhos & Leilões", page_icon="🚗", layout="wide", initial_sidebar_state="expanded")

BASE_DIR = Path(__file__).resolve().parent

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, button, input, textarea, select {
    font-family: 'Inter', sans-serif !important;
}
.stApp { background: #f5f7fb; }

/* O estilo da sidebar foi consolidado num bloco unico mais abaixo neste
   <style> (procure por "SIDEBAR (bloco unico)"). Antes ficava dividido
   entre aqui e la, com regras conflitantes. */
.pill {
  display:inline-flex; align-items:center; justify-content:center;
  padding:7px 15px; border-radius:999px;
  font-size:12.5px; font-weight:600; line-height:1.1;
  margin-right:6px; margin-bottom:4px; white-space:nowrap;
  border:1px solid color-mix(in srgb, currentColor 24%, transparent);
}
/* Linha dos dois selos (classificacao + estado) no topo do card. */
.pill-row { display:flex; flex-wrap:wrap; gap:8px; margin:2px 0 10px; }
.pill-row .pill { margin:0; }
.p-otimo   { background:#dcfce7; color:#15803d; }
.p-mediano { background:#fef9c3; color:#a16207; }
.p-ruim    { background:#fee2e2; color:#b91c1c; }
.p-inspec  { background:#ffedd5; color:#c2410c; }
.p-semref  { background:#f1f5f9; color:#64748b; }
.p-ebom    { background:#dbeafe; color:#1d4ed8; }
.p-rec     { background:#e0f2fe; color:#0284c7; }
.p-bat     { background:#ffedd5; color:#ea580c; }
.p-sin     { background:#fee2e2; color:#dc2626; }
.p-ni      { background:#f8fafc; color:#334155; }

/* ── BOTÃO FAVORITAR ── estrela grande + texto, última coluna de cada card ── */
div[class*="st-key-fav_"] button {
    background: transparent !important;
    background-color: transparent !important;
    border: 2px solid var(--lce-amber, #f59e0b) !important;
    box-shadow: none !important;
    width: 100% !important;
    height: auto !important;
    min-height: 44px !important;
    padding: 6px 12px !important;
    border-radius: 8px !important;
    color: var(--lce-amber, #f59e0b) !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    line-height: 1.2 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    gap: 6px !important;
    white-space: nowrap !important;
}
div[class*="st-key-fav_"] button strong {
    font-size: 26px !important;
    line-height: 1 !important;
    vertical-align: middle !important;
}
div[class*="st-key-fav_"] button:hover {
    background: color-mix(in srgb, var(--lce-amber, #f59e0b) 12%, transparent) !important;
    opacity: 1 !important;
}
@media (max-width: 430px) {
    div[class*="st-key-fav_"] button { font-size: 12px !important; gap: 4px !important; padding: 6px 8px !important; }
    div[class*="st-key-fav_"] button strong { font-size: 22px !important; }
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
/* stExpandSidebarButton e stBaseButton-headerNoPadding JÁ SÃO o <button>
   (não um wrapper); só stSidebarCollapseButton é um <div> com o botão
   dentro. Por isso os seletores não são todos "... button". */
[data-testid="stSidebarCollapseButton"],
[data-testid="stExpandSidebarButton"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    z-index: 999999 !important;
}

[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"],
button[data-testid="stBaseButton-headerNoPadding"] {
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

/* O ícone é uma fonte de ícones (span), não um <svg>, nesta versão do
   Streamlit — força a cor nele e em qualquer descendente. */
[data-testid="stSidebarCollapseButton"] button *,
[data-testid="stExpandSidebarButton"] *,
button[data-testid="stBaseButton-headerNoPadding"] * {
    visibility: visible !important;
    opacity: 1 !important;
    color: #fff !important;
    fill: #fff !important;
}


/* Layout de cards/métricas em telas pequenas e médias é tratado pelo
   bloco "TEMA ADAPTATIVO E RESPONSIVIDADE V3" abaixo (grid + :has()).
   Esta regra fica isolada porque cobre uma faixa (701-1024px) que o V3
   não toca — o V3 só ajusta stHorizontalBlock, não .banner-info-grid,
   nesse intervalo de tablet. */
@media (min-width: 641px) and (max-width: 1024px) {
    .banner-info-grid { grid-template-columns: repeat(2, 1fr) !important; }
}

/* ── TEMA ADAPTATIVO E RESPONSIVIDADE V3 ────────────────────────── */
/* O Streamlit não expõe --background-color/--text-color/etc. como CSS
   custom properties nesta versão (confirmado: não existem em nenhum
   elemento da página) — var(--background-color, #f5f7fb) sempre caía
   no fallback claro, então o tema nunca mudava de verdade. Detectamos
   o modo escuro nós mesmos via prefers-color-scheme. */
:root {
    --lce-bg: #f5f7fb;
    --lce-surface: #ffffff;
    --lce-text: #0f172a;
    --lce-primary: #2563eb;
    --lce-muted: color-mix(in srgb, var(--lce-text) 66%, transparent);
    --lce-border: color-mix(in srgb, var(--lce-text) 18%, transparent);
    --lce-hover: color-mix(in srgb, var(--lce-primary) 14%, var(--lce-surface));
    --lce-shadow: 0 8px 24px color-mix(in srgb, #000 14%, transparent);
    --lce-radius: 12px;
    /* Fundo/borda dos cards de lote. Separado de --lce-surface pra permitir
       um card mais "fundo" (proximo do fundo da pagina) no tema escuro,
       como na referencia de estilizacao. */
    --lce-card: #ffffff;
    --lce-card-border: var(--lce-border);
    /* f59e0b (o amber "vivo" usado no escuro) so tem 2:1 de contraste
       contra fundo claro — b45309 mantem a mesma familia de cor e passa
       WCAG AA (4.68:1+) no claro. */
    --lce-amber: #b45309;
}

@media (prefers-color-scheme: dark) {
    :root {
        --lce-bg: #0f1729;
        --lce-surface: #1a2540;
        --lce-text: #e2e8f0;
        --lce-primary: #3b82f6;
        --lce-hover: color-mix(in srgb, var(--lce-primary) 20%, var(--lce-surface));
        --lce-shadow: 0 8px 24px rgba(0,0,0,.5);
        --lce-card: #0d1526;
        --lce-card-border: color-mix(in srgb, var(--lce-text) 14%, transparent);
        --lce-amber: #f59e0b;
    }
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

/* Cards e contêineres.
   O Streamlit 1.57 parou de gerar um elemento dedicado
   [data-testid="stVerticalBlockBorderWrapper"] pra st.container(border=True)
   — agora é só mais um stVerticalBlock (com border/radius nativos do
   próprio Streamlit), dentro de um stLayoutWrapper. Como
   st.container(border=True) só é usado pros cards de lote neste arquivo,
   a cadeia completa stColumn > stVerticalBlock > stLayoutWrapper >
   stVerticalBlock identifica o card com segurança — confirmado ao vivo
   que bate 1:1 com o número de cards renderizados, sem pegar nenhum
   outro bloco vertical da página (sidebar, outras colunas etc.). */
div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"] {
    background: var(--lce-card) !important;
    border: 1px solid var(--lce-card-border) !important;
    border-radius: var(--lce-radius) !important;
    box-shadow: 0 2px 10px color-mix(in srgb, #000 7%, transparent);
    height: 100% !important;
}

/* Cards da mesma linha com a mesma altura, mesmo quando um deles tem bem
   menos conteúdo que os outros. Um "esticamento" via flexbox (altura em %
   encadeada por vários divs do Streamlit) não é confiável para cards bem
   menores — troca para CSS Grid, que estica cada célula da linha para a
   altura da maior por padrão (mesmo padrão já usado nas media queries de
   tablet/mobile abaixo, que sobrescrevem isto nessas larguras). */
div[data-testid="stHorizontalBlock"]:has(
  > div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"]
) {
    display: grid !important;
    grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
    gap: 1rem !important;
    align-items: stretch !important;
}
div[data-testid="stHorizontalBlock"]:has(
  > div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"]
) > div[data-testid="stColumn"] {
    width: 100% !important;
    min-width: 0 !important;
}
div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"]:has(> div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"]) {
    height: 100% !important;
}
div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"]:has(> div[data-testid="stVerticalBlock"]) {
    height: 100% !important;
}
div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"] > div {
    height: 100% !important;
    display: flex !important;
    flex-direction: column !important;
}

/* Cards da mesma linha ficam com altura igual (regra acima), mas o
   conteúdo interno varia (nem todo lote tem análise de IA, calendário
   etc.) — sem isto, a linha "Ver lote / Favoritar" ficava na altura
   onde o conteúdo daquele card específico terminava, em vez de sempre
   no rodapé, desalinhando os botões entre os cards de uma mesma linha. */
div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"] > div > div[data-testid="stHorizontalBlock"]:last-child {
    margin-top: auto !important;
}

/* Links dentro do card (Google Calendar / Ver lote) sem sublinhado. */
div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"] a,
div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"] a:hover {
    text-decoration: none !important;
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

/* Botões gerais: contraste estável nos dois temas.
   --lce-primary puro so da 3.68:1 de texto branco no escuro (abaixo dos
   4.5:1 do WCAG AA) - a mesma mistura de 82% que ja era usada so no hover
   passa em 5.15:1 (escuro) / 6.99:1 (claro), entao virou o estado padrao;
   o hover ficou um pouco mais escuro ainda (70%) pra continuar dando
   feedback visivel de interacao. */
div[data-testid="stButton"] button,
[data-testid="stFormSubmitButton"] button,
[data-testid="stLinkButton"] a,
[data-testid="stDownloadButton"] button {
    min-height: 2.5rem !important;
    background: color-mix(in srgb, var(--lce-primary) 82%, #000) !important;
    color: #ffffff !important;
    border: 1px solid var(--lce-primary) !important;
    border-radius: 8px !important;
    box-shadow: none !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    width: 100% !important;
}

div[data-testid="stButton"] button:hover,
[data-testid="stFormSubmitButton"] button:hover,
[data-testid="stLinkButton"] a:hover,
[data-testid="stDownloadButton"] button:hover {
    background: color-mix(in srgb, var(--lce-primary) 70%, #000) !important;
    color: #ffffff !important;
    border-color: var(--lce-primary) !important;
}

div[data-testid="stButton"] button:focus-visible,
[data-testid="stLinkButton"] a:focus-visible {
    outline: 3px solid color-mix(in srgb, var(--lce-primary) 38%, transparent) !important;
    outline-offset: 2px !important;
}

/* Abas legíveis e roláveis em telas estreitas.
   O Streamlit não usa mais data-baseweb="tab"/"tab-list" nas versões atuais
   (confirmado no site publicado: os elementos só têm role="tab"/"tablist" e
   data-testid="stTab") — por isso os seletores cobrem os dois casos, e sem
   eles a aba selecionada ficava com a cor padrão quase-preta do Streamlit
   sobre o fundo escuro, praticamente invisível. */
.stTabs [data-baseweb="tab-list"],
.stTabs [role="tablist"] {
    gap: .25rem !important;
    overflow-x: auto !important;
    scrollbar-width: thin;
}

.stTabs [data-baseweb="tab"],
.stTabs [data-testid="stTab"],
.stTabs [role="tab"] {
    color: var(--lce-muted) !important;
    flex: 0 0 auto !important;
}

.stTabs [data-baseweb="tab"][aria-selected="true"],
.stTabs [data-testid="stTab"][aria-selected="true"],
.stTabs [role="tab"][aria-selected="true"] {
    color: var(--lce-primary) !important;
}

/* ── SIDEBAR (bloco unico) ───────────────────────────────────────────
   Consolidado: antes o estilo da sidebar vivia em DOIS lugares deste
   <style> — um bloco "legado" no topo e este. Para selectors iguais,
   quem vinha depois (este) vencia, entao o render era uma mistura dos
   dois. Aqui ficam so os valores que de fato venciam + as regras que so
   existiam no bloco legado (h2, hr, label uppercase, menu/option,
   slider, primary:hover, tertiary). Verificado via getComputedStyle
   (light + dark): identico ao render anterior.
   Sidebar e azul-escura e independente do tema principal. */
section[data-testid="stSidebar"] {
    background: #172554 !important;
    color: #e2e8f0 !important;
    border-right: 1px solid rgba(255,255,255,.12) !important;
}
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] hr { border-color: rgba(255,255,255,.15) !important; }

section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] span,
section[data-testid="stSidebar"] div,
section[data-testid="stSidebar"] label {
    color: #e2e8f0;
}

/* logo */
section[data-testid="stSidebar"] h2 {
    color: #fff !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
}

/* labels de secao (FILTROS, INFORMACOES) */
section[data-testid="stSidebar"] label {
    color: #93c5fd !important;
    font-size: .78rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: .05em !important;
}

section[data-testid="stSidebar"] input,
section[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: transparent !important;
    border-color: rgba(255,255,255,.35) !important;
    border-radius: 8px !important;
    color: #ffffff !important;
}

/* opcoes do selectbox */
section[data-testid="stSidebar"] [data-baseweb="menu"] { background: #1e3a8a !important; }
section[data-testid="stSidebar"] [role="option"] { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] [role="option"]:hover { background: rgba(255,255,255,.1) !important; }

/* slider */
section[data-testid="stSidebar"] [data-testid="stSlider"] * { color: #e2e8f0 !important; }

/* Navegação da sidebar sobrescreve o estilo geral de botões. */
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="secondary"],
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-secondary"] {
    background: transparent !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(255,255,255,.22) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: .9rem !important;
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
    border-radius: 8px !important;
    font-weight: 700 !important;
    font-size: .9rem !important;
}

section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="primary"]:hover,
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-primary"]:hover {
    background: #dbeafe !important;
}

/* Sair e Atualizar dados */
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="tertiary"],
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-tertiary"] {
    background: transparent !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(255,255,255,.35) !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    font-size: .88rem !important;
}
section[data-testid="stSidebar"] div[data-testid="stButton"] button[kind="tertiary"]:hover,
section[data-testid="stSidebar"] div[data-testid="stButton"] button[data-testid="baseButton-tertiary"]:hover {
    background: rgba(255,255,255,.12) !important;
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
[data-testid="stExpandSidebarButton"] {
    display: flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
    z-index: 999999 !important;
}

[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"],
button[data-testid="stBaseButton-headerNoPadding"] {
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

[data-testid="stSidebarCollapseButton"] button *,
[data-testid="stExpandSidebarButton"] *,
button[data-testid="stBaseButton-headerNoPadding"] * {
    color: #ffffff !important;
    fill: #ffffff !important;
}

/* Tablet: dois cards por linha. */
@media (min-width: 701px) and (max-width: 1100px) {
    div[data-testid="stHorizontalBlock"]:has(
      > div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"]
    ) {
        display: grid !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 1rem !important;
    }

    div[data-testid="stHorizontalBlock"]:has(
      > div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"]
    ) > div[data-testid="stColumn"] {
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

    /* O Streamlit desloca a sidebar recolhida com base na largura padrão
       dele (300px); como forçamos uma largura maior acima, sobrava uma
       tira visível no canto. translateX(-100%) sempre soma a largura
       real, então some por completo independente do valor forçado. */
    section[data-testid="stSidebar"][aria-expanded="false"] {
        transform: translateX(-100%) !important;
    }

    div[data-testid="stHorizontalBlock"]:has(
      > div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"]
    ) {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) !important;
        gap: .875rem !important;
    }

    div[data-testid="stHorizontalBlock"]:has(
      > div[data-testid="stColumn"] > div[data-testid="stVerticalBlock"] > div[data-testid="stLayoutWrapper"] > div[data-testid="stVerticalBlock"]
    ) > div[data-testid="stColumn"] {
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
    .banner-tile .pct { font-size: 13px !important; }
    .banner-tile .lbl { font-size: 10px !important; }
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

# Trechos de URL que indicam uma logo/placeholder genérico da plataforma em
# vez de foto real do lote — a imagem carrega normalmente (não é "quebrada",
# o navegador não detecta erro nenhum), então trata-se como se não houvesse
# foto, para cair no mesmo ícone de categoria. Rede de segurança do lado do
# dashboard: o scraper já filtra esses casos na origem (ver _extrair_foto e
# _raspar_pacto em scraper.py), isso aqui só cobre dado antigo/já salvo.
_FOTOS_PLACEHOLDER_PATTERNS = ("leilomaster.cdndp.com.br", "/fotos-modelo/")


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

    for i, lote in enumerate(lotes_pagina):
        if i % 3 == 0:
            cols = st.columns(3)
        lance   = lote["lance_atual"]
        fipe    = lote["fipe_valor"]
        foto    = lote.get("foto","")
        if any(pat in foto for pat in _FOTOS_PLACEHOLDER_PATTERNS):
            foto = ""
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
                # Foto — se a URL falhar (link caído, hotlink bloqueado etc.),
                # troca pro mesmo ícone de categoria usado quando não há foto
                # nenhuma, em vez de deixar o ícone de imagem quebrada do
                # navegador. O fallback é preenchido por JS (script perto do
                # fim do arquivo) e não por onerror inline: o
                # unsafe_allow_html=True do Streamlit remove atributos
                # on* do HTML por segurança, então onerror="..." aqui
                # nunca chegava a existir de verdade no DOM renderizado.
                if foto:
                    _icone_fb = icones_cat.get(cat, "📦")
                    st.markdown(
                        f"<div class='card-img-box'>"
                        f"<img src='{foto}'>"
                        f"<span class='card-img-fallback' style='display:none;font-size:48px;width:100%;height:100%;align-items:center;justify-content:center'>{_icone_fb}</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(f'<div class="card-img-box" style="font-size:48px">{icones_cat.get(cat,"📦")}</div>', unsafe_allow_html=True)

                # Qtd
                if qtd > 1:
                    st.markdown(f'<span class="qtd-tag">📦 {qtd} unidades neste lote</span>', unsafe_allow_html=True)

                # Badges
                st.markdown(
                    f"<div class='pill-row'>{pill_classif(classif)}{pill_estado(selo)}</div>",
                    unsafe_allow_html=True,
                )

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
                        _det   = quote(f"Lance: R$ {lance:,.0f} | {lote.get('cidade','')} | Achadinhos & Leilões")
                        _loc   = quote(lote.get('cidade',''))
                        _cal   = (f"https://calendar.google.com/calendar/render?action=TEMPLATE"
                                  f"&text={_title}&dates={_ds}/{_de}&details={_det}&location={_loc}")
                        st.markdown(f"[📅 Salvar no Google Calendar]({_cal})")
                    except:
                        pass

                col_link, col_fav = st.columns([3, 2])
                _fonte_label = {"mega": "Mega Leilões", "pacto": "Pacto", "leilo": "Leilo", "mgl": "MGL Leilões", "montenegro": "Montenegro Leilões", "construbem": "Construbem", "danielgarcia": "Daniel Garcia", "mj": "MJ Leilões", "celsocunha": "Celso Cunha"}.get(lote.get("fonte",""), "Leilão")
                col_link.markdown(f"[🔗 Ver lote na {_fonte_label} →]({lote['url']})")
                lote_url = lote.get("url", "")
                heart = "★" if is_favorite(lote_url) else "☆"
                fav_label = f"**{heart}** Favoritar"
                if col_fav.button(fav_label, key=f"fav_{key}_{i}", help="Favoritar"):
                    _usr = get_user()
                    _ses = st.session_state.get("session")
                    if _usr and _ses:
                        _profile = get_profile() or {}
                        _metadata = getattr(_usr, "user_metadata", None) or {}
                        _phone = _profile.get("phone") or _metadata.get("phone", "")
                        _ok, _favoritado, _erro = toggle_favorite(
                            _usr.id,
                            _ses.access_token,
                            lote,
                            phone=_phone,
                        )
                        if _ok:
                            st.toast(
                                "Adicionado aos favoritos ⭐"
                                if _favoritado
                                else "Removido dos favoritos"
                            )
                            st.rerun()
                        else:
                            st.error(_erro)
                    else:
                        st.toast("Faça login para favoritar ⭐")

    if total_pages > 1:
        st.markdown("---")
        c1, c2, c3 = st.columns([1, 2, 1])
        with c1:
            if page > 1 and st.button("← Anterior", key=f"prev_{key}"):
                st.session_state[page_key] = page - 1
                st.session_state["_scroll_to_top"] = True
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
                st.session_state["_scroll_to_top"] = True
                st.rerun()

def pagina_sobre():
    st.markdown("## 📌 Sobre o Achadinhos & Leilões")
    st.markdown("""
O **Achadinhos & Leilões** é uma plataforma de **análise e direcionamento** de oportunidades em leilões de veículos, imóveis e equipamentos no Ceará.

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
1. **Encontre o lote no Achadinhos & Leilões** — use os filtros e análises
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
        st.info("Você ainda não favoritou nenhum lote. Clique em ⭐ em qualquer card para favoritar.") # não alterar ⭐
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
O Achadinhos & Leilões não se responsabiliza por decisões de compra. As análises são orientativas.
""")


def render_user_menu():
    """Conta no topo direito com avatar genérico e ação de logout."""
    user = get_user()
    if not user:
        return

    nome = get_display_name()
    primeiro_nome = nome.split()[0] if nome.split() else "Usuário"
    email = str(getattr(user, "email", "") or "")
    profile = get_profile() or {}

    _, menu_col = st.columns([8, 2])
    with menu_col:
        with st.popover(
            f"👤  {primeiro_nome}",
            use_container_width=True,
        ):
            st.markdown(
                f"""
                <div style="display:flex;align-items:center;gap:12px;padding:4px 2px 12px;">
                  <div style="width:48px;height:48px;min-width:48px;border-radius:50%;
                              background:linear-gradient(135deg,#2563eb,#1e3a8a);
                              display:flex;align-items:center;justify-content:center;
                              box-shadow:0 3px 10px rgba(37,99,235,.3);">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
                         xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                      <circle cx="12" cy="8" r="4" fill="white"/>
                      <path d="M4.5 20c.7-4.1 3.2-6 7.5-6s6.8 1.9 7.5 6"
                            fill="white"/>
                    </svg>
                  </div>
                  <div style="min-width:0;">
                    <div style="font-size:14px;font-weight:700;line-height:1.3;">
                      {escape(nome)}
                    </div>
                    <div style="font-size:11px;opacity:.7;white-space:nowrap;
                                overflow:hidden;text-overflow:ellipsis;max-width:210px;">
                      {escape(email)}
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if bool(profile.get("billing_exempt")):
                st.caption("Conta especial · cobrança isenta")
            elif is_subscribed() and profile.get("stripe_customer_id"):
                try:
                    st.link_button(
                        "Gerenciar assinatura",
                        create_billing_portal_url(),
                        use_container_width=True,
                    )
                except Exception:
                    st.caption("Portal de cobrança temporariamente indisponível.")
            st.divider()
            if st.button(
                "↪ Sair da conta",
                key="top_user_logout",
                use_container_width=True,
            ):
                logout()
                st.rerun()

# ─── APP ──────────────────────────────────────────────────────────────────────

# Renova o token, valida a conta e aplica os limites locais de sessão.
ensure_valid_session()

# Exige uma conta válida antes de mostrar o painel.
if not get_user():
    render_auth_page()
    if get_user():
        st.rerun()
    st.stop()

# Usuários comuns precisam de assinatura ativa. Contas com billing_exempt=true
# passam por esta verificação sem cobrança.
if st.query_params.get("payment") == "success":
    refresh_profile()

if not is_subscribed():
    render_paywall()
    st.stop()

_session = st.session_state.get("session")
_user = get_user()
if _session and st.session_state.get("_favorites_owner") != _user.id:
    _favoritos_ok, _favoritos_erro = load_favorites(
        _user.id,
        _session.access_token,
    )
    if not _favoritos_ok:
        st.toast(_favoritos_erro, icon="⚠️")

render_user_menu()

lotes = carregar()

# Paginação troca de conteúdo mas o navegador mantém a posição de rolagem
# (st.rerun() não reseta scroll) — sem isso, "Próxima"/"Anterior" trocavam
# os cards mas deixavam o usuário olhando pro meio da página anterior.
_rolar_ao_topo = st.session_state.pop("_scroll_to_top", False)
_scroll_snippet = "window.parent.scrollTo({top: 0, behavior: 'instant'});" if _rolar_ao_topo else ""

components.html("""
<script>
(function() {
  """ + _scroll_snippet + """
  function applyFixes(doc) {
    // ── Cor da estrela (☆ cinza / ★ amarelo) ─────────────────────────
    doc.querySelectorAll('button').forEach(function(btn) {
      var t = btn.textContent.trim();
      if (t.includes('★') || t.includes('☆')) {
        // Referencia a variavel em vez de um hex fixo, senao o inline
        // !important daqui vence o !important do CSS e ignora o tema
        // (foi assim que o amber ficou ilegivel no modo claro antes).
        var cor = t.includes('★') ? 'var(--lce-amber)' : 'var(--lce-muted)';
        btn.style.setProperty('color', cor, 'important');
        btn.querySelectorAll('*').forEach(function(el) {
          el.style.setProperty('color', cor, 'important');
        });
      }
    });

    // ── Foto quebrada → ícone de categoria ────────────────────────────
    // Precisa ser feito por JS de verdade: o unsafe_allow_html=True do
    // Streamlit remove atributos onerror="..." do HTML por seguranca,
    // entao um onerror inline no <img> nunca chega a existir no DOM.
    doc.querySelectorAll('.card-img-box img').forEach(function(img) {
      if (img.dataset.fallbackBound) return;
      img.dataset.fallbackBound = '1';
      var mostrarFallback = function() {
        img.style.display = 'none';
        var fallback = img.parentElement.querySelector('.card-img-fallback');
        if (fallback) fallback.style.display = 'flex';
      };
      img.addEventListener('error', mostrarFallback);
      // A imagem pode ja ter falhado antes do listener ser anexado
      // (a MutationObserver so roda depois que o <img> entra no DOM).
      if (img.complete && img.naturalWidth === 0) mostrarFallback();
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
      <div style="font-size:1.15rem;font-weight:800;color:#e2e8f0;">🚗 Achadinhos & Leilões</div>
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

    valores_lance = sorted(l["lance_atual"] for l in lotes if l["lance_atual"] > 0)
    lance_teto = int(valores_lance[-1]) if valores_lance else 500000
    if valores_lance:
        # a régua do slider usa o p90 pra não esticar 35x por causa de 1 ou 2
        # imóveis fora da curva — quem precisa de um valor maior digita no campo
        idx_p90 = min(int(len(valores_lance) * 0.9), len(valores_lance) - 1)
        lance_slider_max = max(int(valores_lance[idx_p90]), 100000)
        lance_slider_max = -(-lance_slider_max // 1000) * 1000  # arredonda pra cima (múltiplo de 1000)
    else:
        lance_slider_max = 500000
    lance_step = 500 if lance_slider_max <= 50000 else 1000

    if "f_lance_num" not in st.session_state:
        st.session_state["f_lance_num"] = lance_teto
    if "f_lance_slider" not in st.session_state:
        st.session_state["f_lance_slider"] = min(lance_teto, lance_slider_max)

    def _sync_lance_do_campo():
        st.session_state["f_lance_slider"] = min(st.session_state["f_lance_num"], lance_slider_max)

    def _sync_lance_do_slider():
        st.session_state["f_lance_num"] = st.session_state["f_lance_slider"]

    st.number_input(
        "Lance máximo (R$)", min_value=0, max_value=lance_teto, step=lance_step,
        key="f_lance_num", on_change=_sync_lance_do_campo,
    )
    st.slider(
        "Ajuste rápido", 0, lance_slider_max, step=lance_step,
        key="f_lance_slider", on_change=_sync_lance_do_slider,
        label_visibility="collapsed",
    )
    f_lance = st.session_state["f_lance_num"]

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
