"""Testes da tipografia corporativa (``components/componentes``).

O app usa só fontes SIL OFL, auto-hospedadas em ``assets/fonts``. Estes
testes garantem que os arquivos existem, que o tema do Streamlit aponta
para a mesma família das tabelas e que nenhuma fonte licenciada voltou.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from components import componentes as comp

RAIZ = Path(__file__).resolve().parents[1]
PASTA_FONTES = RAIZ / "assets" / "fonts"


def test_todas_as_familias_declaradas_tem_arquivos():
    disponiveis = comp.fontes_disponiveis()

    assert set(disponiveis) == {"Manrope", "Inter", "JetBrains Mono"}
    for familia, pesos in disponiveis.items():
        assert pesos, f"nenhum arquivo encontrado para {familia}"


def test_pesos_esperados_estao_presentes():
    disponiveis = comp.fontes_disponiveis()

    # Manrope cobre títulos (700/800) e massa de texto (400–600).
    assert disponiveis["Manrope"] == [400, 500, 600, 700, 800]
    assert disponiveis["Inter"] == [400, 500, 600, 700]
    assert disponiveis["JetBrains Mono"] == [400, 500]


def test_cada_familia_tem_a_licenca_ao_lado():
    """A OFL exige distribuir a licença junto com os binários."""
    for config in comp._FAMILIAS_CORPORATIVAS.values():
        licenca = PASTA_FONTES / config["licenca"]
        assert licenca.is_file(), f"licença ausente: {licenca.name}"
        texto = licenca.read_text(encoding="utf-8", errors="ignore")
        assert "SIL Open Font License" in texto


def test_css_gera_font_face_com_base64_para_cada_peso():
    css = comp.css_fontes_corporativas()

    for familia, config in comp._FAMILIAS_CORPORATIVAS.items():
        for peso in config["pesos"]:
            regra = f"font-family: '{familia}'"
            assert regra in css
            assert f"font-weight: {peso}" in css

    regras = re.findall(r"@font-face \{", css)
    total = sum(len(c["pesos"]) for c in comp._FAMILIAS_CORPORATIVAS.values())
    assert len(regras) == total
    # Os binários vão embutidos: sem isso o app dependeria de CDN.
    assert css.count("src: url(data:font/woff2;base64,") == total


def test_tema_do_streamlit_usa_a_mesma_familia_das_tabelas():
    """O canvas do st.dataframe lê `font` do tema, não o Styler."""
    config = tomllib.loads((RAIZ / ".streamlit" / "config.toml").read_text())

    fonte_tema = config["theme"]["font"]
    familia_tabela = comp.FONTE_TABELA.split(",")[0].strip().strip("'\"")
    assert fonte_tema.split(",")[0].strip() == familia_tabela
    assert familia_tabela in comp.FONTE_TABELA


def test_cadeias_de_fonte_terminam_em_fallback_de_sistema():
    for cadeia in (comp.FONTE_TITULO, comp.FONTE_TEXTO, comp.FONTE_TABELA):
        assert cadeia.rstrip().endswith("sans-serif")
    assert comp.FONTE_CODIGO.rstrip().endswith("monospace")


def test_dataframes_forcam_a_fonte_corporativa():
    import pandas as pd

    styler = comp.estilizar_dataframe(pd.DataFrame({"Contrato": [1]}))
    css = styler.to_html()

    familia = comp.FONTE_TABELA.split(",")[0].strip().strip("'\"")
    assert familia in css


def test_nenhuma_referencia_a_fonte_proprietaria():
    """A Oscine saiu do projeto junto com o instalador e os .ttf."""
    arquivos = [
        *(RAIZ / "components").glob("*.py"),
        *(RAIZ / "pages").glob("*.py"),
        RAIZ / "streamlit_app.py",
        RAIZ / ".streamlit" / "config.toml",
    ]
    for arquivo in arquivos:
        conteudo = arquivo.read_text(encoding="utf-8").lower()
        assert "oscine" not in conteudo, f"resíduo de Oscine em {arquivo.name}"

    assert not (RAIZ / "scripts" / "instalar_fonte_hero.py").exists()
    assert not list(PASTA_FONTES.glob("*.ttf"))


def test_aplicar_estilo_nao_duplica_o_css_na_mesma_execucao(monkeypatch):
    """Entrypoint + página chamam aplicar_estilo(); só a primeira injeta.

    Sem o guard, as fontes em base64 (≈275 KB) iriam duas vezes para o DOM.
    """
    estado: dict[str, object] = {}
    monkeypatch.setattr(comp.st, "session_state", estado, raising=False)

    chamadas: list[str] = []
    monkeypatch.setattr(comp, "_configurar_plotly_global", lambda: chamadas.append("plotly"))
    monkeypatch.setattr(comp, "_injetar_fontes_no_head_pai", lambda: chamadas.append("js"))
    monkeypatch.setattr(comp, "_injetar_css_global", lambda: chamadas.append("css"))

    comp.nova_execucao()
    comp.aplicar_estilo()   # entrypoint
    comp.aplicar_estilo()   # página
    assert chamadas == ["plotly", "js", "css"]

    comp.nova_execucao()    # próximo rerun
    comp.aplicar_estilo()
    assert chamadas == ["plotly", "js", "css"] * 2
