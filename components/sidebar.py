"""Temas, preferência de sessão e estilos da barra lateral TOTALE.

No entrypoint, após st.set_page_config():
    from components.sidebar import render_seletor_tema_sidebar
    from components.componentes import aplicar_estilo

    render_seletor_tema_sidebar()
    aplicar_estilo()

As páginas podem continuar chamando apenas aplicar_estilo().
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from components.paleta import COR_PRIMARIA, COR_SECUNDARIA


# Apenas tokens do sidebar variam: cores semânticas de KPIs e gráficos são
# preservadas. Nunca altere constantes globais a partir de uma sessão de usuário.
@dataclass(frozen=True)
class TemaSidebar:
    rotulo: str
    fundo: str
    texto: str
    texto_suave: str
    borda: str
    destaque: str
    hover: str
    ativo: str
    controle: str
    texto_controle: str
    borda_controle: str


TEMAS_SIDEBAR: dict[str, TemaSidebar] = {
    "prata": TemaSidebar(
        "Prata TOTALE", "linear-gradient(180deg, #E8EAED, #CDD2D7)",
        "#0F172A", "#334155", "#A0A7B0", COR_PRIMARIA,
        "#F1F5F9", "#FFFFFF", "#FFFFFF", "#0F172A", "#94A3B8",
    ),
    "azul": TemaSidebar(
        "Azul institucional", f"linear-gradient(180deg, {COR_PRIMARIA}, #061D43)",
        "#FFFFFF", "#CBD5E1", "#49648D", "#FDBA74",
        "#183E76", "#234C85", "#FFFFFF", "#0F172A", "#94A3B8",
    ),
    "laranja": TemaSidebar(
        "Laranja TOTALE", "linear-gradient(180deg, #FFF7ED, #FED7AA)",
        "#431407", "#7C2D12", "#D5945C", "#9A3412",
        "#FFEDD5", "#FFFFFF", "#FFFFFF", "#431407", "#B77948",
    ),
    "claro": TemaSidebar(
        "Claro corporativo", "#F8FAFC",
        "#0F172A", "#475569", "#CBD5E1", COR_PRIMARIA,
        "#E2E8F0", "#DBEAFE", "#FFFFFF", "#0F172A", "#94A3B8",
    ),
}

_CHAVE_TEMA_SIDEBAR = "totale_tema_sidebar"
_CHAVE_SELETOR_SIDEBAR = "_totale_seletor_sidebar"
_TEMA_SIDEBAR_PADRAO = "prata"


def _obter_tema_sidebar() -> TemaSidebar:
    chave = st.session_state.get(_CHAVE_TEMA_SIDEBAR, _TEMA_SIDEBAR_PADRAO)
    return TEMAS_SIDEBAR.get(chave, TEMAS_SIDEBAR[_TEMA_SIDEBAR_PADRAO])


def _salvar_tema_sidebar() -> None:
    # Chave permanente separada da chave do widget: sobrevive à limpeza de
    # widgets quando o seletor não está presente em uma página.
    st.session_state[_CHAVE_TEMA_SIDEBAR] = st.session_state[_CHAVE_SELETOR_SIDEBAR]


def render_seletor_tema_sidebar() -> None:
    """Exibe uma vez no entrypoint, antes de aplicar_estilo().

    A preferência é isolada por sessão e compartilhada por todas as páginas.
    Em scripts independentes, chame esta função após st.set_page_config().
    """
    chave = st.session_state.get(_CHAVE_TEMA_SIDEBAR, _TEMA_SIDEBAR_PADRAO)
    if chave not in TEMAS_SIDEBAR:
        chave = _TEMA_SIDEBAR_PADRAO
    st.session_state[_CHAVE_TEMA_SIDEBAR] = chave
    st.session_state[_CHAVE_SELETOR_SIDEBAR] = chave
    with st.sidebar.expander("🎨 Aparência TOTALE", expanded=False):
        st.selectbox(
            "Cor da barra lateral",
            options=list(TEMAS_SIDEBAR),
            format_func=lambda valor: TEMAS_SIDEBAR[valor].rotulo,
            key=_CHAVE_SELETOR_SIDEBAR,
            on_change=_salvar_tema_sidebar,
            help="Escolha uma combinação da paleta TOTALE. Vale para todas as páginas nesta sessão.",
        )
        st.markdown(
            f'<div class="totale-paleta" aria-label="Paleta TOTALE: azul, laranja e prata">'
            f'<span style="background:{COR_PRIMARIA}"></span>'
            f'<span style="background:{COR_SECUNDARIA}"></span>'
            '<span style="background:#CDD2D7"></span></div>',
            unsafe_allow_html=True,
        )
        st.caption("Azul institucional • Laranja TOTALE • Prata")


def gerar_css_sidebar() -> str:
    """Retorna CSS sem tags <style>, usando o tema da sessão atual.

    Chamado por aplicar_estilo() para reaplicar o tema sem duplicar widgets.
    """
    sidebar = _obter_tema_sidebar()
    return f"""
    /* ── Sidebar: tokens isolados por sessão ── */
    section[data-testid="stSidebar"] {{
        --sidebar-texto: {sidebar.texto};
        --sidebar-suave: {sidebar.texto_suave};
        --sidebar-borda: {sidebar.borda};
        --sidebar-destaque: {sidebar.destaque};
        --sidebar-hover: {sidebar.hover};
        --sidebar-ativo: {sidebar.ativo};
        --sidebar-controle: {sidebar.controle};
        --sidebar-texto-controle: {sidebar.texto_controle};
        --sidebar-borda-controle: {sidebar.borda_controle};
        background: {sidebar.fundo} !important;
        color: var(--sidebar-texto) !important;
        border-right: 1px solid var(--sidebar-borda);
    }}
    section[data-testid="stSidebar"] :is(p, label, h1, h2, h3, h4),
    section[data-testid="stSidebar"] summary,
    section[data-testid="stSidebar"] [data-testid="stIconMaterial"],
    section[data-testid="stSidebar"] [data-testid="stSidebarNavLink"] {{
        color: var(--sidebar-texto) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
        color: var(--sidebar-suave) !important;
    }}
    section[data-testid="stSidebar"] :is(h1, h2, h3, h4) {{
        font-weight: 700;
        letter-spacing: -0.3px;
    }}
    section[data-testid="stSidebar"] hr {{
        border-color: var(--sidebar-borda);
        margin: 12px 0;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] details {{
        border-color: var(--sidebar-borda);
        border-radius: var(--radius);
    }}

    /* Navegação: o item ativo não depende apenas da cor. */
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a {{
        border-radius: 6px;
        padding: 8px 12px;
        border-left: 3px solid transparent;
        color: var(--sidebar-texto) !important;
        transition: background-color 0.15s ease;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a span {{
        color: inherit !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a:hover {{
        background: var(--sidebar-hover) !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stSidebarNav"] a[aria-current="page"] {{
        background: var(--sidebar-ativo) !important;
        border-left-color: var(--sidebar-destaque);
        font-weight: 700;
    }}
    section[data-testid="stSidebar"] :is(a, button, summary):focus-visible {{
        outline: 2px solid var(--sidebar-destaque) !important;
        outline-offset: 2px;
    }}

    /* Controles com superfície clara, inclusive no tema azul. Não usar um
       seletor universal de cor: ele sobrescreve tags, botões e ícones. */
    section[data-testid="stSidebar"] [data-baseweb="select"] > div,
    section[data-testid="stSidebar"] [data-baseweb="input"],
    section[data-testid="stSidebar"] :is(input, textarea) {{
        background: var(--sidebar-controle) !important;
        color: var(--sidebar-texto-controle) !important;
        border-color: var(--sidebar-borda-controle) !important;
        border-radius: 6px;
    }}
    section[data-testid="stSidebar"] [data-baseweb="select"] :is(span, input),
    section[data-testid="stSidebar"] [data-baseweb="tag"] :is(span, svg) {{
        color: var(--sidebar-texto-controle) !important;
    }}
    section[data-testid="stSidebar"] [data-baseweb="select"] svg {{
        fill: var(--sidebar-texto-controle);
    }}
    section[data-testid="stSidebar"] [data-baseweb="tag"] {{
        background: #E2E8F0 !important;
    }}
    section[data-testid="stSidebar"] [data-baseweb="select"] > div:focus-within,
    section[data-testid="stSidebar"] [data-baseweb="input"]:focus-within,
    section[data-testid="stSidebar"] textarea:focus {{
        outline: 2px solid var(--sidebar-destaque);
        outline-offset: 1px;
    }}
    section[data-testid="stSidebar"] .stButton button,
    section[data-testid="stSidebar"] .stDownloadButton button,
    section[data-testid="stSidebar"] .stFormSubmitButton button {{
        background: var(--sidebar-controle) !important;
        color: var(--sidebar-texto-controle) !important;
        border: 1px solid var(--sidebar-borda-controle) !important;
    }}
    section[data-testid="stSidebar"] :is(.stButton, .stDownloadButton, .stFormSubmitButton) button:hover,
    section[data-testid="stSidebar"] button[kind="primary"] {{
        background: {COR_PRIMARIA} !important;
        color: #FFFFFF !important;
        border-color: var(--sidebar-destaque) !important;
    }}
    section[data-testid="stSidebar"] :is(.stButton, .stDownloadButton, .stFormSubmitButton) button p {{
        color: inherit !important;
    }}
    section[data-testid="stSidebar"] .totale-paleta {{
        display: flex;
        gap: 6px;
        margin: 8px 0;
    }}
    section[data-testid="stSidebar"] .totale-paleta span {{
        display: block;
        width: 36px;
        height: 8px;
        border-radius: 4px;
        border: 1px solid var(--sidebar-borda);
    }}

    section[data-testid="stSidebar"] [data-testid*="Icon"],
    section[data-testid="stSidebar"] [class*="material"] {{
        color: var(--sidebar-destaque) !important;
        font-size: 16px !important;
        width: 16px !important;
        height: 16px !important;
    }}
    """
