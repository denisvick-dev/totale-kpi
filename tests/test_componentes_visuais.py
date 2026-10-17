"""Contrato visual compartilhado por páginas independentes."""

import re
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


def _css_global(monkeypatch) -> str:
    """Captura o CSS injetado por aplicar_estilo()."""
    blocos = []
    monkeypatch.setattr(componentes.st, "markdown", lambda html, **kw: blocos.append(html))
    componentes._injetar_css_global()
    return blocos[0]


def test_titulos_dos_heros_usam_a_oscine_com_fallback(monkeypatch):
    css = _css_global(monkeypatch)

    assert componentes.FONTE_HERO.startswith("'Oscine'")
    assert "Manrope" in componentes.FONTE_HERO  # cadeia de fallback preservada
    assert f"--font-hero:      {componentes.FONTE_HERO};" in css

    bloco_hero = next(
        bloco for bloco in re.findall(r"\.hero-title\s*\{[^}]*\}", css)
        if "clamp(25px" in bloco
    )
    assert "font-family: var(--font-hero) !important;" in bloco_hero
    # os demais títulos (h1 soltos, KPIs...) seguem com a fonte institucional
    assert "font-family: var(--font-titulo) !important;" in css


def test_kit_web_da_oscine_e_configuravel(monkeypatch):
    monkeypatch.setenv("TOTALE_FONTE_HERO_URL", "https://use.typekit.net/abc123.css")
    css = _css_global(monkeypatch)

    assert "@import url('https://use.typekit.net/abc123.css');" in css


def test_fonte_auto_hospedada_em_assets_fonts(monkeypatch, tmp_path):
    (tmp_path / "oscine-bold.woff2").write_bytes(b"wOF2conteudo-falso")
    monkeypatch.setattr(componentes, "_PASTA_FONTES", tmp_path)
    monkeypatch.delenv("TOTALE_FONTE_HERO_URL", raising=False)
    componentes._css_fonte_hero_selfhosted.clear()

    css = _css_global(monkeypatch)

    assert "@font-face" in css
    assert "font-family: 'Oscine'" in css
    assert "data:font/woff2;base64" in css


def test_oscine_vale_para_heros_h1_e_titulos_de_secao(monkeypatch):
    css = _css_global(monkeypatch)

    bloco_titulos = re.search(
        r"h1, h2, h3, h4, h5, h6,\s*\.hero-title, \.section-title \{[^}]*\}", css
    )
    assert bloco_titulos is not None
    assert "font-family: var(--font-hero) !important;" in bloco_titulos.group(0)

    bloco_secao = re.search(r"\.section-title \{[^}]*\}", css)
    assert "font-family: var(--font-hero) !important;" in bloco_secao.group(0)


def test_valores_de_kpi_mantem_a_fonte_institucional(monkeypatch):
    css = _css_global(monkeypatch)

    blocos_kpi = re.findall(r"\.kpi-value(?:,|\s*\{)[^}]*\}", css)
    assert blocos_kpi
    assert any(
        "font-family: var(--font-titulo) !important;" in bloco for bloco in blocos_kpi
    )


def test_fonte_auto_hospedada_tambem_e_lida_de_fonts_na_raiz(monkeypatch, tmp_path):
    (tmp_path / "oscine-bold.woff2").write_bytes(b"wOF2conteudo-falso")
    monkeypatch.setattr(componentes, "_PASTA_FONTES", tmp_path / "sem-fontes")
    monkeypatch.setattr(componentes, "_PASTA_FONTES_ALT", tmp_path)
    monkeypatch.delenv("TOTALE_FONTE_HERO_URL", raising=False)
    componentes._css_fonte_hero_selfhosted.clear()

    css = _css_global(monkeypatch)

    assert "font-family: 'Oscine'" in css
    assert "data:font/woff2;base64" in css


def test_fonte_original_do_kit_e_normalizada_pelo_nome(monkeypatch, tmp_path):
    (tmp_path / "Oscine ExtraBold.otf").write_bytes(b"OTTOconteudo-falso")
    monkeypatch.setattr(componentes, "_PASTA_FONTES", tmp_path)
    monkeypatch.setattr(componentes, "_PASTA_FONTES_ALT", tmp_path / "sem-fontes")
    monkeypatch.delenv("TOTALE_FONTE_HERO_URL", raising=False)
    componentes._css_fonte_hero_selfhosted.clear()

    css = _css_global(monkeypatch)

    assert "font-weight: 800" in css
    assert "data:font/opentype;base64" in css
