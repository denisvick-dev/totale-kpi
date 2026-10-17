"""Contrato visual compartilhado por páginas independentes."""

from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from components import componentes


ROOT = Path(__file__).resolve().parents[1]


def test_hero_e_kpi_escapam_conteudo_e_mantem_identidade(monkeypatch):
    blocos = []
    monkeypatch.setattr(componentes.st, "markdown", lambda html, **kwargs: blocos.append(html))
    componentes.render_hero("Painel <teste>", "Resumo & operação", "Indicadores")
    assert 'class="hero-corp"' in blocos[0]
    assert 'class="hero-badge"' in blocos[0]
    assert "Painel &lt;teste&gt;" in blocos[0]
    assert "Resumo &amp; operação" in blocos[0]

    class Coluna:
        def markdown(self, html, **kwargs):
            blocos.append(html)

    componentes.render_kpi(Coluna(), "Total", "<script>", "Hoje", tema="verde")
    componentes.render_kpi_sm(Coluna(), "Parcial", "8", tema="azul")
    assert "&lt;script&gt;" in blocos[1]
    assert "<script>" not in blocos[1]
    assert 'class="kpi-card kpi-card--sm"' in blocos[2]
    assert "--kpi-accent:" in blocos[1]


def test_home_mantem_navegacao_nos_cards():
    app = AppTest.from_file(ROOT / "streamlit_app.py").run()
    assert not app.exception
    assert len(app.get("page_link")) == 7  # seis painéis + atualização
    assert any('class="hero-corp"' in item.value for item in app.markdown)


def test_gestao_de_ativos_carrega_com_hero_compartilhado():
    app = AppTest.from_file(ROOT / "pages/gestao_ativos.py").run()
    assert not app.exception
    assert any('class="hero-corp"' in item.value for item in app.markdown)


def test_atualizacao_usa_hero_e_cards_sem_acessar_planilhas():
    app = AppTest.from_file(ROOT / "pages/envio_excel.py")
    app.session_state["dados_cons"] = {"Consultivo": pd.DataFrame({"a": [1]})}
    app.session_state["dados_prod"] = {"Prod": pd.DataFrame({"a": [1]})}
    app.run()
    assert not app.exception
    assert any('class="hero-corp"' in item.value for item in app.markdown)
    assert sum('class="kpi-card"' in item.value for item in app.markdown) == 6
