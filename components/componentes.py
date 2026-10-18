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

import base64
import logging
import os
import re
from collections.abc import Callable
from html import escape
from pathlib import Path
from typing import Any, Literal, Union

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

from components.paleta import (
    COR_ALERTA,
    COR_BORDA,
    COR_DIVIDER,
    COR_FUNDO,
    COR_NEUTRO,
    COR_PRIMARIA,
    COR_SECUNDARIA,
    COR_SUCESSO,
    COR_TEXTO,
    COR_TEXTO_2,
    COR_TEXTO_3,
)

# Compatibilidade com os imports usados antes da extração para sidebar.py.
from components.sidebar import (
    TEMAS_SIDEBAR as TEMAS_SIDEBAR,
)
from components.sidebar import (
    TemaSidebar as TemaSidebar,
)
from components.sidebar import gerar_css_sidebar
from components.sidebar import (
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

#: Fonte exclusiva dos títulos dos heros.
#: Se a Oscine não estiver disponível — ativa no computador (Adobe Fonts /
#: Creative Cloud), kit web configurado ou arquivo em ``assets/fonts`` —,
#: a cadeia anterior (Manrope → Segoe UI) assume automaticamente.
FONTE_HERO = "'Oscine', 'Oscine Trial', " + FONTE_TITULO

#: Pesos procurados em ``assets/fonts`` para auto-hospedar a Oscine.
_PESOS_FONTE_HERO: tuple = (
    (
        400,
        ("oscine-regular", "oscine_regular", "oscine", "oscine-book", "oscine-roman"),
    ),
    (500, ("oscine-medium", "oscine_medium")),
    (700, ("oscine-bold", "oscine_bold", "oscine-semibold", "oscine-demi")),
    (800, ("oscine-extrabold", "oscine_extrabold", "oscine-heavy", "oscine-black")),
)
_FORMATOS_FONTE = {
    ".woff2": "woff2",
    ".woff": "woff",
    ".otf": "opentype",
    ".ttf": "truetype",
}
_PASTA_FONTES = Path(__file__).resolve().parents[1] / "assets" / "fonts"
# A pasta ``fonts`` na raiz também é aceita: alguns checkouts baixam o kit da
# Oscine fora de ``assets`` (a licença não permite versionar os binários).
_PASTA_FONTES_ALT = Path(__file__).resolve().parents[1] / "fonts"

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


def _url_kit_fonte_hero() -> str:
    """
    URL do kit da Oscine (Adobe Fonts/Typekit ou CDN própria).

    Configure em ``.streamlit/secrets.toml``::

        [tipografia]
        fonte_hero_url = "https://use.typekit.net/XXXXXXX.css"

    ou na variável de ambiente ``TOTALE_FONTE_HERO_URL``.
    """
    url = ""
    try:
        secao = st.secrets.get("tipografia", {})
        url = str(secao.get("fonte_hero_url", "") or "")
    except Exception:
        url = ""
    return (url or os.getenv("TOTALE_FONTE_HERO_URL", "")).strip()


def _pastas_de_fontes() -> tuple[Path, ...]:
    """Pastas procuradas para auto-hospedar a Oscine, em ordem de prioridade."""
    return (_PASTA_FONTES, _PASTA_FONTES_ALT)


def _normalizar_nome_fonte(nome: str) -> str:
    """Compara nomes de fonte sem depender de caixa, espaços ou separadores.

    Aceita tanto os nomes canônicos do instalador (``oscine-bold.woff2``)
    quanto os arquivos originais do kit (``Oscine Bold.otf``).
    """
    return re.sub(r"[^a-z0-9]+", "-", str(nome).lower()).strip("-")


def _localizar_arquivo_fonte(pastas_nomes: tuple) -> Path | None:
    desejados = {_normalizar_nome_fonte(nome) for nome in pastas_nomes}
    for pasta in _pastas_de_fontes():
        if not pasta.is_dir():
            continue
        for extensao in _FORMATOS_FONTE:
            for arquivo in sorted(pasta.iterdir()):
                if (
                    arquivo.is_file()
                    and arquivo.suffix.lower() == extensao
                    and _normalizar_nome_fonte(arquivo.stem) in desejados
                ):
                    return arquivo
    return None


@st.cache_data(show_spinner=False)
def _css_fonte_hero_selfhosted(assinatura: str) -> str:
    """
    Gera os ``@font-face`` da Oscine a partir de ``assets/fonts``.

    Os arquivos são embutidos em base64 (o Streamlit Cloud não serve arquivos
    estáticos por padrão). Se a pasta estiver vazia, nada é gerado e a fonte
    continua dependendo da instalação local/kit web.
    """
    del assinatura  # usado apenas como chave de cache
    pastas = [pasta for pasta in _pastas_de_fontes() if pasta.is_dir()]
    if not pastas:
        return ""

    regras = []
    for peso, nomes in _PESOS_FONTE_HERO:
        arquivo = _localizar_arquivo_fonte(nomes)
        if arquivo is None:
            continue
        formato = _FORMATOS_FONTE.get(arquivo.suffix.lower(), "woff2")
        try:
            dados = base64.b64encode(arquivo.read_bytes()).decode("ascii")
        except OSError as exc:
            logger.warning("Não foi possível ler a fonte %s: %s", arquivo, exc)
            continue
        regras.append(
            "@font-face { font-family: 'Oscine'; font-style: normal; "
            f"font-weight: {peso}; font-display: swap; "
            f"src: url(data:font/{formato};base64,{dados}) "
            f"format('{formato}'); }}"
        )
    return "\n".join(regras)


def _css_fonte_hero() -> str:
    """CSS que disponibiliza a Oscine para os títulos dos heros."""
    kit = _url_kit_fonte_hero()
    if kit:
        return f"@import url('{kit}');"

    try:
        assinatura = "|".join(
            sorted(
                f"{pasta}:{p.name}:{p.stat().st_mtime_ns}"
                for pasta in _pastas_de_fontes()
                if pasta.is_dir()
                for p in pasta.glob("*")
                if p.is_file()
            )
        )
        return _css_fonte_hero_selfhosted(assinatura)
    except Exception as exc:  # nunca derrubar a página por causa de fonte
        logger.warning("Falha ao preparar a fonte dos heros: %s", exc)
        return ""


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
    "ok": ("#ECFDF5", "#065F46", "#6EE7B7", "✓"),
    "info": ("#EFF6FF", "#1E40AF", "#93C5FD", "i"),
    "alerta": ("#FFFBEB", "#92400E", "#FCD34D", "!"),
    "critico": ("#FEF2F2", "#991B1B", "#FCA5A5", "✕"),
    "acao": ("#F5F3FF", "#5B21B6", "#C4B5FD", "→"),
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
    st.html(
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
        unsafe_allow_javascript=True,
    )


def _build_links_html() -> str:
    tags = "\n".join(
        f'<link rel="stylesheet" href="{url}">' for url in _GOOGLE_FONTS_URLS
    )
    return (
        '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
        '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>\n' + tags
    )


# ====================================================
# CSS GLOBAL
# ====================================================
def _injetar_css_global() -> None:
    links_html = _build_links_html()
    css_fonte_hero = _css_fonte_hero()

    css = f"""{links_html}
    <style>
    /* ── Fonte dos títulos dos heros (Oscine) ── */
    {css_fonte_hero}

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
        --font-hero:      {FONTE_HERO};
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
    span:not([class*="material"]):not([data-testid="stIconMaterial"]) {{
        font-family: var(--font-texto) !important;
    }}

    /* ── Títulos (Oscine) ── */
    h1, h2, h3, h4, h5, h6,
    .hero-title, .section-title {{
        font-family: var(--font-hero) !important;
        font-weight: 700;
        letter-spacing: -0.2px;
    }}
    h1, .hero-title {{ font-weight: 800; }}
    /* Valores de KPI/métrica seguem com a fonte institucional (numérica). */
    .kpi-value, [data-testid="stMetricValue"] {{
        font-family: var(--font-titulo) !important;
        font-weight: 700;
    }}

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
    :is(.stButton, .stDownloadButton, .stFormSubmitButton) [data-testid="stTooltipIcon"],
    :is(.stButton, .stDownloadButton, .stFormSubmitButton) [data-testid="stTooltipHoverTarget"] {{
        width: 100%;
    }}

    /* ── Tabelas Corporativas: moldura, cabeçalho e tipografia ── */
    [data-testid="stDataFrame"], [data-testid="stTable"] {{
        border: 1px solid #DCE5F0;
        border-top: 3px solid var(--cor-primaria);
        border-radius: 12px;
        overflow: hidden;
        background: var(--cor-fundo-card, #FFFFFF);
        box-shadow: 0 8px 24px rgba(10, 47, 107, 0.065), 0 2px 6px rgba(15, 23, 42, 0.03);
        transition: border-color 0.18s ease, box-shadow 0.18s ease;
    }}
    [data-testid="stDataFrame"]:hover, [data-testid="stTable"]:hover {{
        border-color: #B4C8E1;
        border-top-color: var(--cor-secundaria);
        box-shadow: 0 12px 28px rgba(10, 47, 107, 0.11), 0 4px 10px rgba(15, 23, 42, 0.05);
    }}
    [data-testid="stDataFrame"] [data-testid="stElementToolbar"] {{
        background: rgba(255, 255, 255, 0.95);
        border: 1px solid #DCE5F0;
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(10, 47, 107, 0.08);
    }}
    .stDataFrame, .stTable,
    table, thead, tbody, tr, th, td {{
        font-family: var(--font-titulo) !important;
    }}
    thead th, [data-testid="stTable"] th {{
        background: linear-gradient(180deg, #0D387D 0%, var(--cor-primaria) 100%);
        color: #FFFFFF !important;
        font-weight: 700;
        font-size: 11.5px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 10px 14px;
        border-bottom: 2px solid var(--cor-secundaria);
    }}
    th {{ font-weight: 600; color: var(--cor-texto-2); }}
    td {{ font-variant-numeric: tabular-nums; color: var(--cor-texto); }}

    /* Barra superior corporativa para DataFrames */
    .corp-table-bar {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
        padding: 10px 14px;
        margin: 8px 0 8px 0;
        background: linear-gradient(90deg, #F8FAFC 0%, #FFFFFF 100%);
        border: 1px solid #DCE5F0;
        border-left: 4px solid var(--cor-primaria);
        border-radius: 10px;
        box-shadow: 0 2px 8px rgba(10, 47, 107, 0.04);
    }}
    .corp-table-bar-main {{
        display: flex;
        align-items: center;
        gap: 10px;
        min-width: 0;
    }}
    .corp-table-icon {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 30px;
        height: 30px;
        flex: none;
        border-radius: 8px;
        background: #EAF2FC;
        color: var(--cor-primaria);
        font-size: 17px !important;
    }}
    .corp-table-title {{
        font-family: var(--font-hero) !important;
        font-size: 14.5px;
        font-weight: 700;
        color: var(--cor-texto);
        letter-spacing: -0.01em;
        line-height: 1.25;
        margin: 0;
    }}
    .corp-table-sub {{
        font-size: 11.5px;
        color: var(--cor-texto-2);
        margin-top: 1px;
    }}
    .corp-table-meta {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        flex-wrap: wrap;
    }}
    .corp-table-badge {{
        display: inline-flex;
        align-items: center;
        padding: 3px 10px;
        border-radius: 999px;
        background: #EAF2FC;
        border: 1px solid #C8DCF5;
        color: var(--cor-primaria);
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.03em;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
    }}
    .corp-table-badge--muted {{
        background: #F1F5F9;
        border-color: #E2E8F0;
        color: #475569;
    }}

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
        font-family: var(--font-hero) !important;
        font-size: clamp(25px, 2.7vw, 38px);
        font-weight: 400; letter-spacing: -.035em;
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
        font-family: var(--font-hero) !important;
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
    "azul": "#EAF2FC",
    "verde": "#E5F7EF",
    "vermelho": "#FDEBED",
    "laranja": "#FFF0E1",
    "cinza": "#EFF2F6",
}
_TEMA_ICONES = {
    "azul": "analytics",
    "verde": "trending_up",
    "vermelho": "warning",
    "laranja": "bolt",
    "cinza": "bar_chart",
}


def render_hero(titulo: str, subtitulo: str = "", badge: str = "") -> None:
    if not titulo:
        raise ValueError("render_hero: 'titulo' não pode ser vazio.")

    sub_html = (
        f'<p class="hero-subtitle">{escape(str(subtitulo))}</p>' if subtitulo else ""
    )
    badge_html = (
        f'<span class="hero-badge">{escape(str(badge))}</span>' if badge else ""
    )

    st.markdown(
        f'<div class="hero-corp">'
        f'<div class="hero-content">'
        f"{badge_html}"
        f'<h1 class="hero-title">{escape(str(titulo))}</h1>'
        f"{sub_html}"
        f"</div></div>",
        unsafe_allow_html=True,
    )


def render_section(titulo: str, divider: str = "gray") -> None:
    st.subheader(titulo, divider=divider)  # type: ignore[arg-type]


def render_section_header(icon: str, title: str, badge: str = "") -> None:
    """Cabeçalho de seção com Material Symbol ou emoji, conforme o ícone recebido."""
    if not title:
        raise ValueError("render_section_header: 'title' vazio.")

    badge_html = (
        f'<span class="section-badge">{escape(str(badge))}</span>' if badge else ""
    )
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
    col.markdown(
        _html_kpi(label, valor, sub, tema, pequeno=False), unsafe_allow_html=True
    )


def render_kpi_sm(
    container: Any,
    label: str,
    valor: str,
    sub: str = "",
    tema: TemaKPI = "azul",
) -> None:
    container.markdown(
        _html_kpi(label, valor, sub, tema, pequeno=True), unsafe_allow_html=True
    )


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


_COLUNAS_ID_EXATAS: frozenset[str] = frozenset(
    {
        "id",
        "re",
        "cod",
        "cód",
        "cód. equipe",
        "códauxequipe",
        "contrato",
        "cep",
        "login",
        "login netsales",
        "login_tecnico",
        "posicao",
        "posição",
        "rank",
        "#",
        "ano",
        "os",
    }
)
_TERMOS_COLUNA_ID: tuple[str, ...] = (
    "cód",
    "cod",
    "contrato",
    "cep",
    "login",
)
_TERMOS_COLUNA_PERCENTUAL: tuple[str, ...] = (
    "%",
    "taxa",
    "quebra",
    "eficiencia",
    "eficiência",
    "conversao",
    "conversão",
    "acumulado",
    "pct",
)

_STATUS_ESTILOS_CORP: dict[str, str] = {
    "executada": "background-color: #ECFDF5; color: #065F46; font-weight: 700; text-align: center;",
    "executado": "background-color: #ECFDF5; color: #065F46; font-weight: 700; text-align: center;",
    "ativo": "background-color: #ECFDF5; color: #065F46; font-weight: 700; text-align: center;",
    "ativa": "background-color: #ECFDF5; color: #065F46; font-weight: 700; text-align: center;",
    "concluída": "background-color: #ECFDF5; color: #065F46; font-weight: 700; text-align: center;",
    "concluido": "background-color: #ECFDF5; color: #065F46; font-weight: 700; text-align: center;",
    "sim": "background-color: #ECFDF5; color: #065F46; font-weight: 700; text-align: center;",
    "✅": "background-color: #ECFDF5; color: #065F46; font-weight: 700; text-align: center;",
    "merge (sheets)": "background-color: #ECFDF5; color: #065F46; font-weight: 600; text-align: center;",
    "não executada": "background-color: #FEF2F2; color: #991B1B; font-weight: 700; text-align: center;",
    "nao executada": "background-color: #FEF2F2; color: #991B1B; font-weight: 700; text-align: center;",
    "inoperante": "background-color: #FEF2F2; color: #991B1B; font-weight: 700; text-align: center;",
    "desligado": "background-color: #FEF2F2; color: #991B1B; font-weight: 700; text-align: center;",
    "inativo": "background-color: #FEF2F2; color: #991B1B; font-weight: 700; text-align: center;",
    "cancelada": "background-color: #FEF2F2; color: #991B1B; font-weight: 700; text-align: center;",
    "❌": "background-color: #FEF2F2; color: #991B1B; font-weight: 700; text-align: center;",
    "não mapeado": "background-color: #FEF2F2; color: #991B1B; font-weight: 600; text-align: center;",
    "nao mapeado": "background-color: #FEF2F2; color: #991B1B; font-weight: 600; text-align: center;",
    "pendente": "background-color: #FFFBEB; color: #92400E; font-weight: 700; text-align: center;",
    "férias": "background-color: #FFFBEB; color: #92400E; font-weight: 700; text-align: center;",
    "ferias": "background-color: #FFFBEB; color: #92400E; font-weight: 700; text-align: center;",
    "em aberto": "background-color: #FFFBEB; color: #92400E; font-weight: 700; text-align: center;",
    "aberto": "background-color: #FFFBEB; color: #92400E; font-weight: 700; text-align: center;",
    "⚠️": "background-color: #FFFBEB; color: #92400E; font-weight: 700; text-align: center;",
    "arquivo origem": "background-color: #FFFBEB; color: #92400E; font-weight: 600; text-align: center;",
    "etn": "background-color: #F5F3FF; color: #5B21B6; font-weight: 700; text-align: center;",
    "afastado": "background-color: #F1F5F9; color: #475569; font-weight: 600; text-align: center;",
    "não": "color: #6B7280; text-align: center;",
    "nao": "color: #6B7280; text-align: center;",
}

_REGIAO_ESTILOS_CORP: dict[str, str] = {
    "leste": "background-color: #EFF6FF; color: #1E40AF; font-weight: 700; text-align: center;",
    "net-leste": "background-color: #EFF6FF; color: #1E40AF; font-weight: 700; text-align: center;",
    "gru": "background-color: #ECFDF5; color: #065F46; font-weight: 700; text-align: center;",
    "guarulhos": "background-color: #ECFDF5; color: #065F46; font-weight: 700; text-align: center;",
    "net-guarulhos": "background-color: #ECFDF5; color: #065F46; font-weight: 700; text-align: center;",
    "abcdm": "background-color: #F5F3FF; color: #5B21B6; font-weight: 700; text-align: center;",
    "net-abcdm": "background-color: #F5F3FF; color: #5B21B6; font-weight: 700; text-align: center;",
    "outras": "background-color: #F1F5F9; color: #475569; font-weight: 600; text-align: center;",
}

_SEGMENTO_ESTILOS_CORP: dict[str, str] = {
    "novos domicílios": "background-color: #ECFDF5; color: #065F46; font-weight: 700;",
    "novos domicilios": "background-color: #ECFDF5; color: #065F46; font-weight: 700;",
    "🏠 novos domicílios": "background-color: #ECFDF5; color: #065F46; font-weight: 700;",
    "migração": "background-color: #EFF6FF; color: #1E40AF; font-weight: 700;",
    "migracao": "background-color: #EFF6FF; color: #1E40AF; font-weight: 700;",
    "🔄 migração": "background-color: #EFF6FF; color: #1E40AF; font-weight: 700;",
    "pme": "background-color: #F5F3FF; color: #5B21B6; font-weight: 700;",
    "🏢 pme": "background-color: #F5F3FF; color: #5B21B6; font-weight: 700;",
    "🔦 flag_gpon": "background-color: #FFFBEB; color: #92400E; font-weight: 700;",
    "outros": "color: #475569; font-weight: 600;",
    "⚪ outros": "color: #475569; font-weight: 600;",
}


def _inferir_formatos_corporativos(
    df: pd.DataFrame, fmt: FmtDict | None = None
) -> dict[str, BaseFormatter]:
    """Combina formatos explícitos com inferência corporativa para colunas numéricas."""
    formatos: dict[str, BaseFormatter] = {
        c: f for c, f in (fmt or {}).items() if c in df.columns and f is not None
    }
    for col in df.columns:
        if col in formatos:
            continue
        col_norm = str(col).strip().casefold()
        if col_norm in _COLUNAS_ID_EXATAS or any(
            termo in col_norm for termo in _TERMOS_COLUNA_ID
        ):
            continue
        serie = df[col]
        if pd.api.types.is_bool_dtype(serie):
            continue
        if pd.api.types.is_integer_dtype(serie):
            formatos[col] = "{:,}"
        elif pd.api.types.is_float_dtype(serie):
            if any(termo in col_norm for termo in _TERMOS_COLUNA_PERCENTUAL):
                formatos[col] = "{:.1%}"
            else:
                formatos[col] = "{:,.1f}"
    return formatos


def _estilo_status_corporativo(valor: object) -> str:
    chave = str(valor or "").strip().casefold()
    return _STATUS_ESTILOS_CORP.get(chave, "")


def _estilo_regiao_corporativo(valor: object) -> str:
    chave = str(valor or "").strip().casefold()
    return _REGIAO_ESTILOS_CORP.get(chave, "")


def _estilo_segmento_corporativo(valor: object) -> str:
    chave = str(valor or "").strip().casefold()
    return _SEGMENTO_ESTILOS_CORP.get(chave, "")


def _estilo_posicao_corporativo(valor: object) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    if "🥇" in texto or texto in {"1", "1º"}:
        return "background-color: #FEF9C3; color: #854D0E; font-weight: 800; text-align: center;"
    if "🥈" in texto or texto in {"2", "2º"}:
        return "background-color: #F1F5F9; color: #334155; font-weight: 800; text-align: center;"
    if "🥉" in texto or texto in {"3", "3º"}:
        return "background-color: #FFEDD5; color: #9A3412; font-weight: 800; text-align: center;"
    return f"color: {COR_PRIMARIA}; font-weight: 700; text-align: center;"


def estilizar_dataframe(
    df: pd.DataFrame, fmt: FmtDict | None = None
) -> pd.io.formats.style.Styler:
    """Faixas corporativas, destaques semânticos e totais preservando os dados brutos."""
    df_clean = df.reset_index(drop=True)
    styler = df_clean.style

    formatos = _inferir_formatos_corporativos(df_clean, fmt)
    if formatos:
        styler = styler.format(formatos)  # type: ignore[arg-type]

    styler = styler.set_table_styles(
        [
            {
                "selector": "thead th",
                "props": [
                    ("background-color", COR_PRIMARIA),
                    ("color", "#FFFFFF"),
                    ("font-family", FONTE_TITULO),
                    ("font-weight", "700"),
                    ("font-size", "11.5px"),
                    ("text-transform", "uppercase"),
                    ("letter-spacing", "0.05em"),
                    ("padding", "10px 14px"),
                    ("border-bottom", f"2px solid {COR_SECUNDARIA}"),
                ],
            },
            {
                "selector": "tbody td",
                "props": [
                    ("font-family", FONTE_TITULO),
                    ("padding", "9px 14px"),
                    ("border-bottom", f"1px solid {COR_BORDA}"),
                    ("font-variant-numeric", "tabular-nums"),
                ],
            },
        ]
    )

    # A aplicação célula a célula em bases grandes tornaria a navegação lenta.
    if len(df_clean) <= 1000 and len(df_clean.columns) > 0:

        def faixa(linha: pd.Series) -> list[str]:
            primeiro = str(linha.iloc[0]).strip().casefold() if len(linha) else ""
            total = (
                primeiro.startswith(
                    ("total geral", "total ", "consolidado", "média geral")
                )
                or primeiro == "total"
            )
            fundo = (
                "#EAF2FC"
                if total
                else ("#F5F8FC" if int(linha.name) % 2 else "#FFFFFF")
            )
            cor_txt = COR_PRIMARIA if total else COR_TEXTO
            estilo = f"background-color: {fundo}; color: {cor_txt};"
            if total:
                estilo += f"font-weight: 700; border-top: 2px solid {COR_PRIMARIA};"
            return [estilo] * len(linha)

        styler = styler.apply(faixa, axis=1)

        cols_pos = [
            c
            for c in df_clean.columns
            if str(c).strip().casefold() in {"posição", "posicao", "rank", "#"}
        ]
        if cols_pos:
            styler = styler.map(_estilo_posicao_corporativo, subset=cols_pos)  # type: ignore[arg-type]

        cols_status = [
            c
            for c in df_clean.columns
            if str(c).strip().casefold()
            in {
                "status",
                "status contrato",
                "situação",
                "situacao",
                "status_atividade",
                "status da atividade",
                "flag_gpon",
                "origem_mapeamento",
            }
        ]
        if cols_status:
            styler = styler.map(_estilo_status_corporativo, subset=cols_status)  # type: ignore[arg-type]

        cols_regiao = [
            c
            for c in df_clean.columns
            if str(c).strip().casefold() in {"região", "regiao", "base"}
        ]
        if cols_regiao:
            styler = styler.map(_estilo_regiao_corporativo, subset=cols_regiao)  # type: ignore[arg-type]

        cols_seg = [
            c
            for c in df_clean.columns
            if str(c).strip().casefold()
            in {"tipo_servico", "tipo de serviço", "segmento", "classificação"}
        ]
        if cols_seg:
            styler = styler.map(_estilo_segmento_corporativo, subset=cols_seg)  # type: ignore[arg-type]

    return styler


def render_dataframe(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "bar_chart",
    height: int = 400,
    fmt: FmtDict | None = None,
    badge: str = "",
    subtitulo: str = "",
    **kwargs: Any,
) -> None:
    if not isinstance(df, pd.DataFrame):
        raise TypeError(f"Esperado pd.DataFrame, recebido {type(df).__name__}.")

    if df.empty:
        st.info("Nenhum dado disponível para exibição.")
        return

    if titulo:
        icone_limpo = str(icone or "").strip()
        if icone_limpo:
            eh_material = bool(re.fullmatch(r"[a-z0-9_]+", icone_limpo))
            cls_icone = (
                "material-symbols-rounded corp-table-icon"
                if eh_material
                else "corp-table-icon"
            )
            icone_html = (
                f'<span class="{cls_icone}" aria-hidden="true">'
                f"{escape(icone_limpo)}</span>"
            )
        else:
            icone_html = ""

        sub_html = (
            f'<div class="corp-table-sub">{escape(str(subtitulo))}</div>'
            if subtitulo
            else ""
        )
        n_linhas = f"{len(df):,}".replace(",", ".")
        rotulo_linhas = "registro" if len(df) == 1 else "registros"
        badge_principal = badge or f"{n_linhas} {rotulo_linhas}"
        badge_cols = f"{len(df.columns)} col." if len(df.columns) > 1 else "1 col."

        st.markdown(
            f'<div class="corp-table-bar">'
            f'<div class="corp-table-bar-main">'
            f"{icone_html}"
            f'<div><div class="corp-table-title">{escape(str(titulo))}</div>{sub_html}</div>'
            f"</div>"
            f'<div class="corp-table-meta">'
            f'<span class="corp-table-badge">{escape(str(badge_principal))}</span>'
            f'<span class="corp-table-badge corp-table-badge--muted">{escape(badge_cols)}</span>'
            f"</div></div>",
            unsafe_allow_html=True,
        )

    altura = min(height, 46 + 36 * len(df)) if isinstance(height, int) else height
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
        st.dataframe(
            df, height=altura, use_container_width=True, hide_index=True, **kwargs
        )
