"""
componentes.py
==============
Módulo central de estilos, fontes e componentes reutilizáveis
para todo o projeto Streamlit.

Uso em qualquer página:
    from componentes import aplicar_estilo, render_kpi, render_insight
    aplicar_estilo()
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Literal, Union

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

logger = logging.getLogger(__name__)

# ====================================================
# TIPOS
# ====================================================
TemaKPI = Literal["azul", "verde", "vermelho", "laranja", "cinza"]
TipoInsight = Literal["ok", "info", "alerta", "critico", "acao"]

BaseFormatter = Union[str, Callable[[object], str]]
FmtDict = dict[str, BaseFormatter | None]


# ====================================================
# TIPOGRAFIA
# ====================================================
FONTE_TITULO = "'Manrope', 'Segoe UI', Arial, sans-serif"
FONTE_TEXTO = "'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONTE_CODIGO = "'JetBrains Mono', Consolas, 'Courier New', monospace"

_GOOGLE_FONTS_URLS = (
    "https://fonts.googleapis.com/icon?family=Material+Icons",
    "https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded"
    ":opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block",
    "https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined"
    ":opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block",
    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700"
    "&family=Manrope:wght@400;500;600;700;800"
    "&family=JetBrains+Mono:wght@400;500&display=swap",
)


# ====================================================
# PALETA CORPORATIVA
# ====================================================
COR_PRIMARIA = "#0A2F6B"       # Azul institucional
COR_SECUNDARIA = "#E8700A"     # Laranja Totale
COR_SUCESSO = "#0D9668"
COR_ALERTA = "#D13438"
COR_NEUTRO = "#6B7280"
COR_TEXTO = "#111827"
COR_TEXTO_2 = "#4B5563"
COR_TEXTO_3 = "#9CA3AF"
COR_BORDA = "#E5E7EB"
COR_FUNDO = "#F9FAFB"
COR_FUNDO_CARD = "#FFFFFF"
COR_DIVIDER = "#F3F4F6"

_TEMA_CORES: dict[str, str] = {
    "azul": COR_PRIMARIA,
    "verde": COR_SUCESSO,
    "vermelho": COR_ALERTA,
    "laranja": COR_SECUNDARIA,
    "cinza": COR_NEUTRO,
}

_INSIGHT_CONFIG: dict[str, tuple[str, str, str, str]] = {
    "ok":      ("#ECFDF5", "#065F46", "#6EE7B7", "✓"),
    "info":    ("#EFF6FF", "#1E40AF", "#93C5FD", "i"),
    "alerta":  ("#FFFBEB", "#92400E", "#FCD34D", "!"),
    "critico": ("#FEF2F2", "#991B1B", "#FCA5A5", "✕"),
    "acao":    ("#F5F3FF", "#5B21B6", "#C4B5FD", "→"),
}

_PLOTLY_COLORWAY = [
    COR_PRIMARIA,
    COR_SECUNDARIA,
    COR_SUCESSO,
    COR_ALERTA,
    "#7C3AED",
    "#DB2777",
    "#0D9488",
    "#D97706",
    "#4F46E5",
    COR_NEUTRO,
]


# ====================================================
# PLOTLY GLOBAL
# ====================================================
def _configurar_plotly_global() -> None:
    template = go.layout.Template(
        layout=go.Layout(
            font=dict(family=FONTE_TEXTO, size=13, color=COR_TEXTO),
            title=dict(
                font=dict(family=FONTE_TITULO, size=18, color=COR_TEXTO),
                x=0.01,
                xanchor="left",
            ),
            legend=dict(
                font=dict(family=FONTE_TEXTO, size=12, color=COR_TEXTO_2),
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
            ),
            xaxis=dict(
                tickfont=dict(family=FONTE_TEXTO, size=11, color=COR_TEXTO_3),
                title_font=dict(family=FONTE_TEXTO, size=12, color=COR_TEXTO_2),
                gridcolor=COR_DIVIDER,
                zerolinecolor=COR_BORDA,
                showgrid=True,
                gridwidth=1,
            ),
            yaxis=dict(
                tickfont=dict(family=FONTE_TEXTO, size=11, color=COR_TEXTO_3),
                title_font=dict(family=FONTE_TEXTO, size=12, color=COR_TEXTO_2),
                gridcolor=COR_DIVIDER,
                zerolinecolor=COR_BORDA,
                showgrid=True,
                gridwidth=1,
            ),
            hoverlabel=dict(
                font=dict(family=FONTE_TEXTO, size=12),
                bgcolor="#FFFFFF",
                bordercolor=COR_BORDA,
            ),
            margin=dict(l=16, r=16, t=48, b=16),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            colorway=_PLOTLY_COLORWAY,
            hovermode="closest",
        )
    )
    pio.templates["corporativo"] = template
    pio.templates.default = "plotly_white+corporativo"


# ====================================================
# FONTES
# ====================================================
def _injetar_fontes_no_head_pai() -> None:
    urls_js = ", ".join(f'"{u}"' for u in _GOOGLE_FONTS_URLS)
    components.html(
        f"""
        <script>
        (function () {{
            const urls = [{urls_js}];
            const preconnects = [
                'https://fonts.googleapis.com',
                'https://fonts.gstatic.com'
            ];
            let parentDoc;
            try {{ parentDoc = window.parent.document; }}
            catch (e) {{ return; }}
            const head = parentDoc.head;
            preconnects.forEach(function (href) {{
                if (head.querySelector('link[href="' + href + '"]')) return;
                const link = parentDoc.createElement('link');
                link.rel = 'preconnect';
                link.href = href;
                if (href.includes('gstatic')) link.crossOrigin = 'anonymous';
                head.appendChild(link);
            }});
            const existentes = Array.from(
                head.querySelectorAll('link[rel="stylesheet"]')
            ).map(function (l) {{ return l.href; }});
            urls.forEach(function (href) {{
                if (existentes.includes(href)) return;
                const link = parentDoc.createElement('link');
                link.rel  = 'stylesheet';
                link.href = href;
                head.appendChild(link);
            }});
        }})();
        </script>
        """,
        height=0,
    )


def _build_links_html() -> str:
    tags = "\n".join(
        f'<link rel="stylesheet" href="{url}">' for url in _GOOGLE_FONTS_URLS
    )
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n'
        + tags
    )


# ====================================================
# CSS GLOBAL
# ====================================================
def _injetar_css_global() -> None:
    links_html = _build_links_html()

    css = f"""{links_html}
    <style>
    /* ── Font-face fallback ── */
    @font-face {{
        font-family: 'Material Icons';
        font-style: normal; font-weight: 400; font-display: block;
        src: url(https://fonts.gstatic.com/s/materialicons/v143/flUhRq6tzZclQEJ-Vdg-IuiaDsNc.woff2) format('woff2');
    }}
    @font-face {{
        font-family: 'Material Symbols Rounded';
        font-style: normal; font-weight: 400; font-display: block;
        src: url(https://fonts.gstatic.com/s/materialsymbolsrounded/v206/syl0-zNym6YjUruM-QrEh7-nyTnjDwKNJ_190Fjzag.woff2) format('woff2');
    }}
    @font-face {{
        font-family: 'Material Symbols Outlined';
        font-style: normal; font-weight: 400; font-display: block;
        src: url(https://fonts.gstatic.com/s/materialsymbolsoutlined/v206/kJEhBvYX7BgnkSrUwT8OhrdQw4oELdPIeeII9v6oDMzByHX9rA6RzaxHMPdY43zj-jCxv3fzvRNU22ZXGJpEpjC_1v-p_4MrImHCIJIZrDCvHOej.woff2) format('woff2');
    }}

    /* ── Variáveis ── */
    :root {{
        --font-titulo:    {FONTE_TITULO};
        --font-texto:     {FONTE_TEXTO};
        --font-codigo:    {FONTE_CODIGO};
        --cor-primaria:   {COR_PRIMARIA};
        --cor-secundaria: {COR_SECUNDARIA};
        --cor-sucesso:    {COR_SUCESSO};
        --cor-alerta:     {COR_ALERTA};
        --cor-neutro:     {COR_NEUTRO};
        --cor-texto:      {COR_TEXTO};
        --cor-texto-2:    {COR_TEXTO_2};
        --cor-texto-3:    {COR_TEXTO_3};
        --cor-borda:      {COR_BORDA};
        --cor-fundo:      {COR_FUNDO};
        --radius:         8px;
    }}

    /* ── Base Tipográfica ── */
    html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"],
    [data-testid="stHeader"],
    [data-testid="stSidebar"],
    [data-testid="stToolbar"],
    section[data-testid="stSidebar"] {{
        font-family: var(--font-texto) !important;
    }}
    p, label, div, li, a, button, input, select, textarea {{
        font-family: var(--font-texto) !important;
    }}
    span:not([class*="material"]):not([class*="Icon"]):not([class*="icon"])
        :not([data-testid*="Icon"]):not([data-testid*="icon"]) {{
        font-family: var(--font-texto) !important;
    }}

    /* ── Títulos ── */
    h1, h2, h3, h4, h5, h6,
    .hero-title, .section-title, .kpi-value {{
        font-family: var(--font-titulo) !important;
        font-weight: 700;
        letter-spacing: -0.2px;
    }}
    h1, .hero-title {{ font-weight: 800; }}

    /* ── Widgets ── */
    [data-testid="stWidgetLabel"],
    [data-testid="stMarkdownContainer"],
    [data-testid="stMetric"],
    [data-testid="stMetricLabel"],
    [data-baseweb="select"],
    [data-baseweb="input"],
    [data-baseweb="tab"] {{
        font-family: var(--font-texto) !important;
    }}
    [data-testid="stMetricValue"] {{
        font-family: var(--font-titulo) !important;
        font-weight: 700;
        font-variant-numeric: tabular-nums;
    }}

    /* ── Botões Globais ── */
    .stButton button, .stDownloadButton button,
    .stFormSubmitButton button, button[kind] {{
        font-family: var(--font-texto) !important;
        font-weight: 600;
        border-radius: 6px !important;
    }}

    /* ── Tabelas ── */
    .stDataFrame, .stTable,
    table, thead, tbody, tr, th, td {{
        font-family: var(--font-texto) !important;
    }}
    th {{ font-weight: 600; color: var(--cor-texto-2); }}
    td {{ font-variant-numeric: tabular-nums; }}

    /* ── Código ── */
    code, pre, kbd, samp {{
        font-family: var(--font-codigo) !important;
    }}

    /* ── Layout Container ── */
    .main .block-container {{
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1320px;
    }}

    /* ── Scrollbar Sutil ── */
    ::-webkit-scrollbar       {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: #D1D5DB; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #9CA3AF; }}

    /* ═══════════════════════════════════════════════════
       HERO CORPORATIVO — Clean
       ═══════════════════════════════════════════════════ */
    .hero-corp {{
        background: {COR_PRIMARIA};
        padding: 32px 36px;
        border-radius: var(--radius);
        color: #FFFFFF;
        margin-bottom: 28px;
        position: relative;
        overflow: hidden;
    }}
    .hero-corp::after {{
        content: '';
        position: absolute;
        bottom: 0; left: 0;
        width: 100%; height: 3px;
        background: linear-gradient(90deg, {COR_SECUNDARIA} 0%, transparent 60%);
    }}
    .hero-content {{ position: relative; z-index: 1; }}
    .hero-title {{
        font-size: 28px;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.4px;
        font-family: var(--font-titulo) !important;
        color: #FFFFFF;
        line-height: 1.2;
    }}
    .hero-subtitle {{
        font-size: 14px;
        color: rgba(255,255,255,0.72);
        margin: 6px 0 0 0;
        font-weight: 400;
        line-height: 1.5;
    }}
    .hero-badge {{
        display: inline-block;
        background: rgba(255,255,255,0.12);
        padding: 4px 12px;
        border-radius: 4px;
        font-size: 11px;
        font-weight: 600;
        margin-top: 12px;
        letter-spacing: 0.4px;
        text-transform: uppercase;
        color: rgba(255,255,255,0.85);
        border: 1px solid rgba(255,255,255,0.15);
    }}

    /* ═══════════════════════════════════════════════════
       KPI CARDS — Minimalistas
       ═══════════════════════════════════════════════════ */
    .kpi-card {{
        background: {COR_FUNDO_CARD};
        border-radius: var(--radius);
        padding: 18px 20px;
        border: 1px solid var(--cor-borda);
        border-left: 3px solid var(--cor-primaria);
        transition: border-color 0.15s ease;
    }}
    .kpi-card:hover {{
        border-color: #D1D5DB;
    }}
    .kpi-label {{
        font-family: var(--font-texto) !important;
        font-size: 11px;
        font-weight: 600;
        color: var(--cor-texto-3);
        text-transform: uppercase;
        letter-spacing: 0.6px;
        margin-bottom: 4px;
    }}
    .kpi-value {{
        font-family: var(--font-titulo) !important;
        font-size: 26px;
        font-weight: 800;
        color: var(--cor-texto);
        line-height: 1.15;
        font-variant-numeric: tabular-nums;
    }}
    .kpi-sub {{
        font-family: var(--font-texto) !important;
        font-size: 12px;
        color: var(--cor-texto-3);
        margin-top: 4px;
        font-weight: 400;
    }}

    /* ═══════════════════════════════════════════════════
       SEÇÕES
       ═══════════════════════════════════════════════════ */
    .section-header {{
        display: flex;
        align-items: center;
        gap: 10px;
        margin: 28px 0 14px 0;
        padding-bottom: 8px;
        border-bottom: 1px solid var(--cor-borda);
    }}
    .section-title {{
        font-family: var(--font-titulo) !important;
        font-size: 17px;
        font-weight: 700;
        color: var(--cor-texto);
        margin: 0;
    }}
    .section-badge {{
        background: var(--cor-fundo);
        color: var(--cor-texto-3);
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 10px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.4px;
        border: 1px solid var(--cor-borda);
    }}

    /* ═══════════════════════════════════════════════════
       SIDEBAR — PRATA METÁLICO + FONTE ESCURA / LARANJA
       ═══════════════════════════════════════════════════ */
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #E8EAED 0%, #D8DCE0 40%, #CDD2D7 100%) !important;
        border-right: 1px solid #A0A7B0 !important;
        box-shadow: inset -1px 0 0 rgba(255,255,255,0.6);
    }}

    section[data-testid="stSidebar"] *,
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] span,
    section[data-testid="stSidebar"] div,
    section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {{
        color: #0F172A !important;
        font-weight: 500;
    }}

    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4 {{
        color: #000000 !important;
        font-weight: 800 !important;
        letter-spacing: -0.3px;
        border-bottom: 2px solid #E8700A !important;
        padding-bottom: 8px;
        margin-bottom: 12px;
    }}

    section[data-testid="stSidebar"] hr {{
        border-color: rgba(160,167,176,0.6) !important;
        margin: 12px 0 !important;
    }}

    /* Navegação de Páginas */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a,
    section[data-testid="stSidebar"] li a {{
        border-radius: 6px !important;
        padding: 8px 12px !important;
        transition: all 0.15s ease;
        border-left: 3px solid transparent;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span,
    section[data-testid="stSidebar"] li a span {{
        color: #0F172A !important;
        font-weight: 600 !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover,
    section[data-testid="stSidebar"] li a:hover {{
        background: rgba(255,255,255,0.65) !important;
        border-left-color: #E8700A !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover span,
    section[data-testid="stSidebar"] li a:hover span {{
        color: #000000 !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"],
    section[data-testid="stSidebar"] li a[aria-current="page"] {{
        background: linear-gradient(90deg, rgba(232,112,10,0.20) 0%, rgba(232,112,10,0.05) 100%) !important;
        border-left-color: #E8700A !important;
    }}

    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] span,
    section[data-testid="stSidebar"] li a[aria-current="page"] span {{
        color: #000000 !important;
        font-weight: 800 !important;
    }}

    /* Botões dentro do Sidebar */
    section[data-testid="stSidebar"] .stButton button,
    section[data-testid="stSidebar"] .stDownloadButton button {{
        background: linear-gradient(180deg, #FFFFFF 0%, #E8EAED 100%) !important;
        color: #0F172A !important;
        border: 1px solid #A0A7B0 !important;
        box-shadow: 0 1px 2px rgba(0,0,0,0.1) !important;
        font-weight: 700 !important;
    }}

    section[data-testid="stSidebar"] .stButton button:hover,
    section[data-testid="stSidebar"] .stDownloadButton button:hover {{
        background: linear-gradient(180deg, #E8700A 0%, #C85D08 100%) !important;
        color: #FFFFFF !important;
        border-color: #A64D06 !important;
    }}

    /* Inputs e Controles */
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [data-baseweb="input"] > div,
    section[data-testid="stSidebar"] input,
    section[data-testid="stSidebar"] textarea {{
        background: #FFFFFF !important;
        border: 1px solid #A0A7B0 !important;
        color: #000000 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
    }}

    section[data-testid="stSidebar"] [data-baseweb="select"] span {{
        color: #000000 !important;
        font-weight: 600 !important;
    }}

    section[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within,
    section[data-testid="stSidebar"] [data-baseweb="input"] > div:focus-within,
    section[data-testid="stSidebar"] input:focus {{
        border-color: #E8700A !important;
        box-shadow: 0 0 0 2px rgba(232,112,10,0.25) !important;
    }}

    /* ═══════════════════════════════════════════════════
       MATERIAL ICONS OVERRIDE (Força a fonte do ícone)
       ═══════════════════════════════════════════════════ */
    .material-icons, .material-icons-outlined, .material-icons-round,
    .material-symbols-outlined, .material-symbols-rounded,
    [data-testid="stIconMaterial"],
    [data-testid*="Icon"], [data-testid*="icon"],
    span[class*="material"], i[class*="material"] {{
        font-family:
            "Material Symbols Rounded",
            "Material Symbols Outlined",
            "Material Icons" !important;
        font-weight: normal !important;
        font-style: normal !important;
        line-height: 1 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        white-space: nowrap !important;
        direction: ltr !important;
        font-feature-settings: "liga" !important;
        -webkit-font-smoothing: antialiased !important;
        font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24 !important;
    }}
    svg, svg * {{ font-family: inherit !important; }}

    section[data-testid="stSidebar"] [data-testid*="Icon"],
    section[data-testid="stSidebar"] [class*="material"] {{
        color: #E8700A !important;
        font-size: 16px !important;
        width: 16px !important;
        height: 16px !important;
    }}
    </style>
    """

    st.markdown(css, unsafe_allow_html=True)


# ====================================================
# API PÚBLICA & HELPERS
# ====================================================
def aplicar_estilo() -> None:
    """Aplica fonte corporativa, tema Plotly e CSS global."""
    _configurar_plotly_global()
    _injetar_fontes_no_head_pai()
    _injetar_css_global()


def _resolver_cor_tema(tema: str) -> str:
    cor = _TEMA_CORES.get(tema)
    if cor is None:
        logger.warning("Tema desconhecido: '%s'. Usando 'azul'.", tema)
        return COR_PRIMARIA
    return cor


def _markdown_inline_para_html(texto: str) -> str:
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", texto)
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    return texto


# ====================================================
# COMPONENTES REUTILIZÁVEIS
# ====================================================
def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    if not titulo:
        raise ValueError("render_hero: 'titulo' não pode ser vazio.")

    sub_html = f'<p class="hero-subtitle">{subtitulo}</p>' if subtitulo else ""
    badge_html = f'<span class="hero-badge">{badge}</span>' if badge else ""

    st.markdown(
        f'<div class="hero-corp">'
        f'<div class="hero-content">'
        f'<h1 class="hero-title">{titulo}</h1>'
        f'{sub_html}'
        f'{badge_html}'
        f'</div>'
        f'</div>',
        unsafe_allow_html=True,
    )


def render_section(titulo: str, divider: str = "gray") -> None:
    st.subheader(titulo, divider=divider)  # type: ignore[arg-type]


def render_section_header(icon: str, title: str, badge: str = "") -> None:
    """
    Renderiza um cabeçalho de seção com ícone do Material Symbols.
    """
    if not title:
        raise ValueError("render_section_header: 'title' vazio.")
    
    badge_html = f'<span class="section-badge">{badge}</span>' if badge else ""
    
    # Adicionada a classe material-symbols-rounded para desenhar os ícones corretamente
    st.markdown(
        f"""
        <div class="section-header">
            <span class="material-symbols-rounded" style="font-size:22px;line-height:1;color:{COR_SECUNDARIA};">{icon}</span>
            <h2 class="section-title">{title}</h2>
            {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi(
    col: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPI = "azul",
) -> None:
    cor = _resolver_cor_tema(tema)
    col.markdown(
        f"""
        <div class="kpi-card" style="border-left-color:{cor};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="color:{cor};">{valor}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_sm(
    container: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPI = "azul",
) -> None:
    cor = _resolver_cor_tema(tema)
    container.markdown(
        f"""
        <div style="background:{COR_FUNDO_CARD};border-radius:6px;
             padding:10px 14px;border-left:2px solid {cor};
             margin-bottom:6px;border:1px solid {COR_BORDA};
             border-left:2px solid {cor};">
            <div style="font-family:{FONTE_TEXTO};font-size:10px;
                 color:{COR_TEXTO_3};text-transform:uppercase;
                 letter-spacing:0.5px;font-weight:600;">{label}</div>
            <div style="font-family:{FONTE_TITULO};font-size:18px;
                 color:{cor};font-weight:800;line-height:1.2;
                 margin-top:2px;font-variant-numeric:tabular-nums;">{valor}</div>
            <div style="font-family:{FONTE_TEXTO};font-size:11px;
                 color:{COR_TEXTO_3};margin-top:2px;">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_insight(msg: str, tipo: TipoInsight = "info") -> None:
    if not msg:
        return

    config = _INSIGHT_CONFIG.get(tipo)
    if config is None:
        logger.warning("Tipo desconhecido: '%s'. Usando 'info'.", tipo)
        config = _INSIGHT_CONFIG["info"]

    bg, texto, borda, icone = config
    msg_html = _markdown_inline_para_html(msg)

    st.markdown(
        f"""
        <div style="background:{bg};color:{texto};
             border-left:3px solid {borda};
             padding:10px 14px;border-radius:6px;margin:8px 0;
             font-family:{FONTE_TEXTO};font-size:13px;line-height:1.6;">
            <span style="font-weight:700;margin-right:6px;">{icone}</span>{msg_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dataframe(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "bar_chart",
    height: int = 400,
    fmt: FmtDict | None = None,
    **kwargs: Any,
) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Esperado pd.DataFrame, recebido {type(df).__name__}.")

    if df.empty:
        st.info("Nenhum dado disponível para exibição.")
        return

    if titulo:
        st.markdown(
            f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;">'
            f'<span class="material-symbols-rounded" style="font-size:18px;color:{COR_SECUNDARIA};">{icone}</span>'
            f'<span style="font-size:14px;font-weight:700;color:{COR_TEXTO};">{titulo}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    if fmt:
        fmt_valido: FmtDict = {c: f for c, f in fmt.items() if c in df.columns}
        if fmt_valido:
            try:
                st.dataframe(
                    df.style.format(fmt_valido),  # type: ignore[arg-type]
                    height=height,
                    use_container_width=True,
                    hide_index=True,
                    **kwargs,
                )
                return
            except Exception:
                logger.exception("Falha ao formatar. Exibindo sem formatação.")

    st.dataframe(df, height=height, use_container_width=True, hide_index=True, **kwargs)