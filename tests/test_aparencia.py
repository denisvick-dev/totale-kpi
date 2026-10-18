"""Regressões do seletor corporativo sem precisar das planilhas de produção."""

from pathlib import Path

import plotly.io as pio
import pytest
from streamlit.testing.v1 import AppTest

from components.paleta import COR_PRIMARIA
from components.sidebar import TEMAS_SIDEBAR

APP = """
import streamlit as st
from components.componentes import aplicar_estilo
from components.sidebar import render_seletor_tema_sidebar
st.set_page_config(layout="wide")
if st.session_state.get("mostrar_seletor", True):
    render_seletor_tema_sidebar()
aplicar_estilo()
# As páginas também aplicam estilos; não devem duplicar o seletor.
aplicar_estilo()
st.sidebar.button("Limpar filtros")
st.sidebar.multiselect("Bases", ["São Paulo", "Campinas"], default=["São Paulo"])
"""


def css_renderizado(app):
    return "\n".join(item.value for item in app.markdown if "<style>" in item.value)


def test_padrao_e_sem_seletor_duplicado():
    app = AppTest.from_string(APP).run()
    assert not app.exception
    assert len(app.selectbox) == 1
    assert app.selectbox[0].value == "prata"
    assert TEMAS_SIDEBAR["prata"].fundo in css_renderizado(app)


@pytest.mark.parametrize("tema", TEMAS_SIDEBAR)
def test_troca_de_tema_e_persistencia(tema):
    app = AppTest.from_string(APP).run()
    app.selectbox[0].select(tema).run()
    assert not app.exception
    assert app.session_state["totale_tema_sidebar"] == tema
    assert TEMAS_SIDEBAR[tema].fundo in css_renderizado(app)
    app.button[0].click().run()
    assert app.selectbox[0].value == tema
    assert app.multiselect[0].value == ["São Paulo"]
    # Mesmo sem o widget (página independente), a preferência permanece.
    app.session_state["mostrar_seletor"] = False
    app.run().run()
    assert not app.exception
    assert TEMAS_SIDEBAR[tema].fundo in css_renderizado(app)
    app.session_state["mostrar_seletor"] = True
    app.run()
    assert app.selectbox[0].value == tema
    assert pio.templates["corporativo"].layout.colorway[0] == COR_PRIMARIA


def test_sessoes_nao_compartilham_preferencia():
    primeira = AppTest.from_string(APP).run()
    primeira.selectbox[0].select("azul").run()
    segunda = AppTest.from_string(APP).run()
    assert segunda.selectbox[0].value == "prata"
    assert primeira.selectbox[0].value == "azul"


def test_preferencia_invalida_volta_ao_padrao():
    app = AppTest.from_string(APP)
    app.session_state["totale_tema_sidebar"] = "tema_removido"
    app.run()
    assert not app.exception
    assert app.selectbox[0].value == "prata"


def test_entrypoint_exibe_um_seletor_global():
    raiz = Path(__file__).resolve().parents[1]
    app = AppTest.from_file(str(raiz / "streamlit_app.py")).run()
    assert not app.exception
    assert len(app.selectbox) == 1
    app.selectbox[0].select("azul").run()
    assert not app.exception
    assert TEMAS_SIDEBAR["azul"].fundo in css_renderizado(app)
    # AppTest executa o arquivo da página diretamente ao trocar de página.
    # A preferência deve funcionar mesmo sem renderizar o seletor novamente.
    app.switch_page("pages/pontos.py").run()
    assert not app.exception
    assert app.session_state["totale_tema_sidebar"] == "azul"
    assert TEMAS_SIDEBAR["azul"].fundo in css_renderizado(app)


def test_botao_com_help_no_sidebar_nao_encolhe_por_seletor_de_icone():
    """Regressão: st.button(..., help=...) usa data-testid='stTooltipIcon'."""
    app = AppTest.from_string(APP).run()
    css = css_renderizado(app)

    assert '[data-testid*="Icon"]' not in css
    assert '[data-testid*="icon"]' not in css
    assert '[data-testid="stIconMaterial"]' in css
    assert '[data-testid="stTooltipIcon"]' in css
    assert "width: 100% !important;" in css


def test_sidebar_respeita_acessibilidade_de_foco_e_movimento():
    app = AppTest.from_string(APP).run()
    css = css_renderizado(app)

    assert '[data-testid="stExpander"] summary' in css
    assert "background: transparent !important;" in css
    assert "summary:hover" in css
    assert ":is(a, button, summary, input, textarea):focus-visible" in css
    assert '[data-baseweb="select"] > div:focus-within' in css
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "transition: none !important;" in css
