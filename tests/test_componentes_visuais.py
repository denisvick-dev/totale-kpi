"""Contrato visual compartilhado por páginas independentes."""

import re
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from components import componentes

ROOT = Path(__file__).resolve().parents[1]


def test_hero_e_kpi_escapam_conteudo_e_mantem_identidade(monkeypatch):
    blocos = []
    monkeypatch.setattr(
        componentes.st, "markdown", lambda html, **kwargs: blocos.append(html)
    )
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
    monkeypatch.setattr(
        componentes.st, "markdown", lambda html, **kw: blocos.append(html)
    )
    componentes._injetar_css_global()
    return blocos[0]


def test_injecao_de_fontes_usa_api_html_atual(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        componentes.st,
        "html",
        lambda body, **kwargs: chamadas.append((body, kwargs)),
    )

    componentes._injetar_fontes_no_head_pai()

    assert len(chamadas) == 1
    body, kwargs = chamadas[0]
    assert kwargs == {"unsafe_allow_javascript": True}
    assert "<script>" in body
    assert all(url in body for url in componentes._GOOGLE_FONTS_URLS)


def test_titulos_dos_heros_usam_a_oscine_com_fallback(monkeypatch):
    css = _css_global(monkeypatch)

    assert componentes.FONTE_HERO.startswith("'Oscine'")
    assert "Manrope" in componentes.FONTE_HERO  # cadeia de fallback preservada
    assert f"--font-hero:      {componentes.FONTE_HERO};" in css

    bloco_hero = next(
        bloco
        for bloco in re.findall(r"\.hero-title\s*\{[^}]*\}", css)
        if "clamp(25px" in bloco
    )
    assert "font-family: var(--font-hero) !important;" in bloco_hero
    assert "font-weight: 400;" in bloco_hero
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


def test_fontes_versionadas_do_kit_alimentam_a_oscine_dos_heros(monkeypatch):
    """Os TTFs versionados em ``fonts/`` são a fonte real dos heros.

    Regressão: ``Oscine-Regular.ttf`` e ``Oscine-Bold.ttf`` precisam casar com
    o leitor de ``assets/fonts``/``fonts``; sem isso os títulos dos heros caem
    silenciosamente no Manrope mesmo com os arquivos presentes no repositório.
    """
    monkeypatch.delenv("TOTALE_FONTE_HERO_URL", raising=False)
    componentes._css_fonte_hero_selfhosted.clear()

    pesos = {peso: nomes for peso, nomes in componentes._PESOS_FONTE_HERO}
    regular = componentes._localizar_arquivo_fonte(pesos[400])
    bold = componentes._localizar_arquivo_fonte(pesos[700])
    assert regular is not None and regular.name.lower().startswith("oscine")
    assert bold is not None and bold.name.lower().startswith("oscine")

    css = componentes._css_fonte_hero()
    assert "font-family: 'Oscine'" in css
    assert ";base64," in css
    assert "font-weight: 400" in css
    assert "font-weight: 700" in css


def test_estilizar_dataframe_aplica_destaques_corporativos_e_preserva_ids():
    df = pd.DataFrame(
        {
            "Posição": ["🥇 1º", "🥈 2º", "Total Geral"],
            "CONTRATO": [123456, 654321, 999999],
            "Status Contrato": ["Executada", "Não Executada", "Pendente"],
            "REGIÃO": ["LESTE", "GRU", "ABCDM"],
            "TIPO_SERVICO": ["Migração", "Novos Domicílios", "PME"],
            "Volume": [1200, 850, 2050],
            "Taxa Execução": [0.85, 0.72, 0.80],
        }
    )

    html = componentes.estilizar_dataframe(df).to_html()

    # Cabeçalho institucional e linha de total
    assert componentes.COR_PRIMARIA in html
    assert "#EAF2FC" in html
    # Formatação automática de métricas sem alterar IDs de contrato
    assert "1,200" in html
    assert "85.0%" in html
    assert "123,456" not in html
    # Destaques semânticos de status, região, segmento e pódio
    assert "#ECFDF5" in html  # Executada / GRU / Novos Domicílios
    assert "#FEF2F2" in html  # Não Executada
    assert "#EFF6FF" in html  # LESTE / Migração
    assert "#F5F3FF" in html  # ABCDM / PME
    assert "#FEF9C3" in html  # 1º lugar
    assert f"font-family: {componentes.FONTE_TABELA};" in html


def test_fonte_das_tabelas_e_a_oscine_com_fallback():
    assert componentes.FONTE_TABELA.startswith("'Oscine'")
    assert "Manrope" in componentes.FONTE_TABELA  # cadeia de fallback preservada


def test_dataframes_usam_a_fonte_corporativa_no_css_global(monkeypatch):
    css = _css_global(monkeypatch)

    assert f"--font-tabela:    {componentes.FONTE_TABELA};" in css

    bloco_tabela = re.search(
        r"\.stDataFrame, \.stTable,\s*table, thead, tbody, tr, th, td \{[^}]*\}",
        css,
    )
    assert bloco_tabela is not None
    assert "font-family: var(--font-tabela) !important;" in bloco_tabela.group(0)


def test_config_do_tema_aponta_o_canvas_dos_dataframes_para_a_oscine():
    """O canvas dos ``st.dataframe`` herda a bodyFont de ``[theme] font``.

    Regressão: o glide-data-grid ignora o ``font-family`` do Styler; sem a
    Oscine no ``config.toml`` o grid seguiria na fonte padrão do Streamlit.
    """
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'font = "Oscine, sans-serif"' in config


def test_oscine_e_pre_carregada_para_a_primeira_pintura_do_grid(monkeypatch):
    chamadas = []
    monkeypatch.setattr(
        componentes.st,
        "html",
        lambda body, **kwargs: chamadas.append((body, kwargs)),
    )

    componentes._injetar_fontes_no_head_pai()

    body, _ = chamadas[0]
    assert 'fonts.load("13px Oscine")' in body
    assert 'fonts.load("700 13px Oscine")' in body


def test_render_dataframe_exibe_barra_corporativa_e_escapa_html(monkeypatch):
    blocos = []
    tabelas = []
    monkeypatch.setattr(
        componentes.st, "markdown", lambda html, **kw: blocos.append(html)
    )
    monkeypatch.setattr(
        componentes.st, "dataframe", lambda data, **kw: tabelas.append((data, kw))
    )

    df = pd.DataFrame({"Monitor": ["ANA", "BIA"], "Volume": [10, 20]})
    componentes.render_dataframe(
        df,
        titulo="Relatório <Executivo>",
        icone="groups",
        subtitulo="Consolidado & filtrado",
        badge="2 monitores",
    )

    assert len(blocos) == 1
    assert 'class="corp-table-bar"' in blocos[0]
    assert "Relatório &lt;Executivo&gt;" in blocos[0]
    assert "Consolidado &amp; filtrado" in blocos[0]
    assert "2 monitores" in blocos[0]
    assert "2 col." in blocos[0]
    assert len(tabelas) == 1


def test_qtde_os_estilizar_resumo_formata_metas_com_sinal():
    from pages.qtde_os import EstiloTabela

    df = pd.DataFrame(
        {
            "Supervisor": ["SUP A", "SUP B"],
            "Qtde. de O.S.": [2600, 2100],
            "Meta | 2500": [100, -400],
            "Projeção": [3100, 2450],
        }
    )

    html = EstiloTabela.estilizar_resumo(df).to_html()

    assert "+100" in html
    assert "-400" in html
    assert "2,600" in html
    assert "3,100" in html
    assert "#ECFDF5" in html
    assert "#B4232E" in html
