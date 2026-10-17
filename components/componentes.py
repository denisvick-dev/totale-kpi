"""
componentes.py
==============
Módulo central de estilos, fontes e componentes reutilizáveis
para todo o projeto Streamlit.

Uso em qualquer página:
    from components.componentes import aplicar_estilo, render_kpi, render_insight
    aplicar_estilo()
"""

from __future__ import annotations

import logging
import re
from html import escape
from typing import Any, Callable, Literal, Union

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components

from components.paleta import (
    COR_PRIMARIA, COR_SECUNDARIA, COR_SUCESSO, COR_ALERTA, COR_NEUTRO,
    COR_TEXTO, COR_TEXTO_2, COR_TEXTO_3, COR_BORDA, COR_FUNDO,
    COR_FUNDO_CARD, COR_DIVIDER,
)
from components.sidebar import gerar_css_sidebar
# Compatibilidade com os imports usados antes da extração para sidebar.py.
from components.sidebar import (
    TEMAS_SIDEBAR as TEMAS_SIDEBAR,
    TemaSidebar as TemaSidebar,
    render_seletor_tema_sidebar as render_seletor_tema_sidebar,
)

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

    /* ── Tabelas: moldura consistente inclusive nos st.dataframe das páginas ── */
    [data-testid="stDataFrame"], [data-testid="stTable"] {{
        border: 1px solid var(--cor-borda);
        border-radius: 10px;
        overflow: hidden;
        background: var(--cor-fundo-card, #FFFFFF);
        box-shadow: 0 4px 16px rgba(10, 47, 107, 0.06);
    }}
    [data-testid="stDataFrame"]:hover {{
        border-color: #C7D7E8;
        box-shadow: 0 6px 20px rgba(10, 47, 107, 0.10);
    }}
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
       HERO CORPORATIVO — uma identidade para todas as páginas
       ═══════════════════════════════════════════════════ */
    .hero-corp {{
        position: relative;
        isolation: isolate;
        overflow: hidden;
        padding: clamp(26px, 3vw, 42px) clamp(24px, 3.5vw, 48px);
        margin-bottom: 26px;
        border-radius: 18px;
        background: linear-gradient(115deg, #092452 0%, {COR_PRIMARIA} 56%, #164583 100%);
        border: 1px solid rgba(255, 255, 255, .14);
        box-shadow: 0 16px 38px rgba(10, 47, 107, .16);
        color: #FFFFFF;
    }}
    .hero-corp::before {{
        content: ''; position: absolute; z-index: -1;
        width: 420px; height: 420px; right: -85px; top: -260px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(255, 181, 95, .27), transparent 68%);
        pointer-events: none;
    }}
    .hero-corp::after {{
        content: ''; position: absolute; bottom: 0; left: 0;
        width: 100%; height: 4px;
        background: linear-gradient(90deg, {COR_SECUNDARIA}, #FFC182 42%, transparent 82%);
    }}
    .hero-content {{ position: relative; z-index: 1; max-width: 840px; }}
    .hero-badge {{
        display: inline-flex; align-items: center;
        background: rgba(255, 255, 255, .12);
        border: 1px solid rgba(255, 255, 255, .23);
        border-radius: 999px; padding: 5px 12px;
        font-size: 11px; font-weight: 700; letter-spacing: .08em;
        text-transform: uppercase; color: #FFFFFF;
        margin-bottom: 14px;
    }}
    .hero-title {{
        font-family: var(--font-titulo) !important;
        font-size: clamp(25px, 2.7vw, 38px);
        font-weight: 800; letter-spacing: -.035em;
        line-height: 1.18; margin: 0; color: #FFFFFF;
    }}
    .hero-subtitle {{
        font-size: clamp(13px, 1.2vw, 15px);
        color: #DCE7FA; line-height: 1.6;
        max-width: 680px; margin: 12px 0 0;
    }}

    /* ═══════════════════════════════════════════════════
       CARDS — altura e tipografia consistentes entre painéis
       ═══════════════════════════════════════════════════ */
    .kpi-card {{
        --kpi-accent: {COR_PRIMARIA}; --kpi-tint: #EAF2FC;
        position: relative; overflow: hidden;
        display: flex; flex-direction: column; justify-content: space-between;
        min-height: 142px; height: 100%; box-sizing: border-box;
        padding: 19px 21px; margin-bottom: 12px;
        background: var(--card-surface, #FFFFFF);
        border: 1px solid var(--card-border, {COR_BORDA});
        border-radius: 14px;
        box-shadow: 0 6px 18px rgba(10, 47, 107, .055);
        transition: transform .18s ease, box-shadow .18s ease, border-color .18s ease;
    }}
    .kpi-card::before {{
        content: ''; position: absolute; inset: 0 auto 0 0;
        width: 4px; background: var(--kpi-accent);
    }}
    .kpi-card:hover {{
        transform: translateY(-2px);
        border-color: var(--kpi-accent);
        box-shadow: 0 12px 26px rgba(10, 47, 107, .11);
    }}
    .kpi-top {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }}
    .kpi-icon {{
        display: inline-flex; align-items: center; justify-content: center;
        width: 32px; height: 32px; flex: none;
        border-radius: 10px; background: var(--kpi-tint);
        color: var(--kpi-accent); font-size: 19px !important;
    }}
    .kpi-label {{
        font-family: var(--font-texto) !important;
        font-size: 11px; font-weight: 700;
        color: var(--card-muted, {COR_TEXTO_2});
        text-transform: uppercase; letter-spacing: .07em;
        line-height: 1.4; padding-top: 3px;
    }}
    .kpi-value {{
        font-family: var(--font-titulo) !important;
        font-size: clamp(24px, 2vw, 31px);
        font-weight: 800; letter-spacing: -.035em;
        color: var(--card-text, {COR_TEXTO});
        line-height: 1.15; overflow-wrap: anywhere;
        font-variant-numeric: tabular-nums;
        margin: 10px 0 0;
    }}
    .kpi-sub {{
        font-family: var(--font-texto) !important;
        font-size: 12px; line-height: 1.4;
        color: var(--card-muted, {COR_TEXTO_2});
        margin-top: 6px;
    }}
    .kpi-card--sm {{ min-height: 96px; padding: 12px 15px; margin-bottom: 6px; }}
    .kpi-card--sm .kpi-value {{ font-size: 20px; margin-top: 5px; }}
    .kpi-card--sm .kpi-icon {{ width: 27px; height: 27px; font-size: 16px !important; }}
    @media (max-width: 640px) {{
        .hero-corp {{ padding: 24px; border-radius: 14px; }}
        .kpi-card {{ min-height: 120px; }}
    }}
    @media (prefers-reduced-motion: reduce) {{
        .kpi-card {{ transition: none; }}
        .kpi-card:hover {{ transform: none; }}
    }}

    /* Links de navegação da home: cards clicáveis com ação nativa do Streamlit. */
    [class*="st-key-totale_painel_"] {{
        min-height: 174px;
        padding: 19px 20px;
        border: 1px solid var(--cor-borda);
        border-radius: 14px;
        background: #FFFFFF;
        box-shadow: 0 6px 18px rgba(10, 47, 107, .055);
        transition: border-color .18s ease, box-shadow .18s ease;
    }}
    [class*="st-key-totale_painel_"]:hover {{
        border-color: #A7C4E5;
        box-shadow: 0 10px 24px rgba(10, 47, 107, .11);
    }}
    [class*="st-key-totale_painel_"] h4 {{
        color: {COR_PRIMARIA}; font-size: 16px; margin-bottom: 3px;
    }}
    [class*="st-key-totale_painel_"] [data-testid="stPageLink"] a {{
        color: {COR_PRIMARIA}; font-weight: 700;
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

    {gerar_css_sidebar()}

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

    </style>
    """

    st.markdown(css, unsafe_allow_html=True)


# ====================================================
# API PÚBLICA & HELPERS
# ====================================================
def aplicar_estilo() -> None:
    """Aplica fontes, Plotly e CSS respeitando a preferência da sessão.

    Pode ser chamada pelas páginas sem duplicar o seletor de aparência.
    """
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
    texto = escape(texto)
    texto = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", texto)
    texto = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", texto)
    texto = re.sub(r"`([^`]+)`", r"<code>\1</code>", texto)
    return texto


# ====================================================
# COMPONENTES REUTILIZÁVEIS
# ====================================================
_TEMA_TINTS = {
    "azul": "#EAF2FC", "verde": "#E5F7EF", "vermelho": "#FDEBED",
    "laranja": "#FFF0E1", "cinza": "#EFF2F6",
}
_TEMA_ICONES = {
    "azul": "analytics", "verde": "trending_up", "vermelho": "warning",
    "laranja": "bolt", "cinza": "bar_chart",
}


def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    if not titulo:
        raise ValueError("render_hero: 'titulo' não pode ser vazio.")

    sub_html = f'<p class="hero-subtitle">{escape(str(subtitulo))}</p>' if subtitulo else ""
    badge_html = f'<span class="hero-badge">{escape(str(badge))}</span>' if badge else ""

    st.markdown(
        f'<div class="hero-corp">'
        f'<div class="hero-content">'
        f'{badge_html}'
        f'<h1 class="hero-title">{escape(str(titulo))}</h1>'
        f'{sub_html}'
        f'</div></div>',
        unsafe_allow_html=True,
    )


def render_section(titulo: str, divider: str = "gray") -> None:
    st.subheader(titulo, divider=divider)  # type: ignore[arg-type]


def render_section_header(icon: str, title: str, badge: str = "") -> None:
    """Cabeçalho de seção com Material Symbol ou emoji, conforme o ícone recebido."""
    if not title:
        raise ValueError("render_section_header: 'title' vazio.")

    badge_html = f'<span class="section-badge">{escape(str(badge))}</span>' if badge else ""
    icon_class = "material-symbols-rounded" if re.fullmatch(r"[a-z_]+", icon) else ""
    st.markdown(
        f'<div class="section-header">'
        f'<span class="{icon_class}" style="font-size:22px;line-height:1;color:{COR_SECUNDARIA};" '
        f'aria-hidden="true">{escape(icon)}</span>'
        f'<h2 class="section-title">{escape(title)}</h2>{badge_html}</div>',
        unsafe_allow_html=True,
    )


def _html_kpi(label: str, valor: object, sub: str, tema: TemaKPI, pequeno: bool) -> str:
    cor = _resolver_cor_tema(tema)
    tint = _TEMA_TINTS.get(tema, _TEMA_TINTS["azul"])
    icone = _TEMA_ICONES.get(tema, _TEMA_ICONES["azul"])
    tamanho = " kpi-card--sm" if pequeno else ""
    sub_html = f'<div class="kpi-sub">{escape(str(sub))}</div>' if sub else ""
    return (
        f'<div class="kpi-card{tamanho}" style="--kpi-accent:{cor};--kpi-tint:{tint};">'
        f'<div class="kpi-top"><div class="kpi-label">{escape(str(label))}</div>'
        f'<span class="material-symbols-rounded kpi-icon" aria-hidden="true">{icone}</span></div>'
        f'<div class="kpi-value">{escape(str(valor))}</div>{sub_html}</div>'
    )


def render_kpi(
    col: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPI = "azul",
) -> None:
    col.markdown(_html_kpi(label, valor, sub, tema, pequeno=False), unsafe_allow_html=True)


def render_kpi_sm(
    container: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPI = "azul",
) -> None:
    container.markdown(_html_kpi(label, valor, sub, tema, pequeno=True), unsafe_allow_html=True)


def render_painel_link(caminho: str, titulo: str, descricao: str) -> None:
    """Card de navegação sem HTML envolvendo widgets interativos."""
    chave = re.sub(r"[^a-z0-9]+", "_", caminho.lower()).strip("_")
    with st.container(key=f"totale_painel_{chave}"):
        st.markdown(f"#### {titulo}")
        st.caption(descricao)
        st.page_link(caminho, label="Abrir painel", icon="➡️")


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


def estilizar_dataframe(
    df: pd.DataFrame, fmt: FmtDict | None = None
) -> pd.io.formats.style.Styler:
    """Faixas leves e totais destacados, sem alterar os valores exportáveis do DataFrame."""
    styler = df.reset_index(drop=True).style
    if fmt:
        formatos = {c: f for c, f in fmt.items() if c in df.columns}
        styler = styler.format(formatos)  # type: ignore[arg-type]
    # A aplicação célula a célula em bases grandes tornaria a navegação lenta.
    if len(df) <= 1000:
        def faixa(linha: pd.Series) -> list[str]:
            total = str(linha.iloc[0]).strip().casefold().startswith("total geral")
            fundo = "#EAF2FC" if total else ("#F5F8FC" if int(linha.name) % 2 else "#FFFFFF")
            estilo = f"background-color: {fundo};"
            if total:
                estilo += "font-weight: 700;"
            return [estilo] * len(linha)

        styler = styler.apply(faixa, axis=1)
    return styler


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
            f'<span class="material-symbols-rounded" style="font-size:18px;color:{COR_SECUNDARIA};">{escape(icone)}</span>'
            f'<span style="font-size:14px;font-weight:700;color:{COR_TEXTO};">{escape(titulo)}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

    altura = min(height, 40 + 36 * len(df))
    try:
        st.dataframe(
            estilizar_dataframe(df, fmt),
            height=altura,
            use_container_width=True,
            hide_index=True,
            **kwargs,
        )
    except Exception:
        logger.exception("Falha ao estilizar tabela. Exibindo dados sem formatação.")
        st.dataframe(df, height=altura, use_container_width=True, hide_index=True, **kwargs)
