"""Regressões do robô de sincronismo local (motor, fachada e painel)."""

from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from components import robo_local as robo


def _csv(caminho: Path, texto: str, encoding: str = "utf-8") -> Path:
    caminho.write_text(texto, encoding=encoding)
    return caminho


def _xlsx(caminho: Path, df: pd.DataFrame) -> Path:
    df.to_excel(caminho, index=False)
    assert caminho.stat().st_size >= robo._TAMANHO_MINIMO_XLSX
    return caminho


# ── Detecção e nomes ────────────────────────────────────────────────
def test_deteccao_de_base_aceita_minusculas_e_marcador_mais_longo():
    assert robo.detectar_marcador_arquivo("atividades-spo-2026.csv") == "SPO"
    assert (
        robo.detectar_base_arquivo(Path("/tmp/Atividades-GRS.xlsx")) == "NET-GUARULHOS"
    )
    assert robo.detectar_base_arquivo("ABCDM.csv") == "NET-ABCDM"
    assert robo.detectar_base_arquivo("Atividades-sem-base.csv") is None
    assert robo.detectar_marcador_arquivo(None) is None


def test_nomes_de_colunas_unicos_reservam_grafias_existentes():
    nomes = robo._nomes_colunas_unicos(
        ["A", "A", "A.1", "", "Unnamed: 2", "\ufeffBASE"]
    )
    assert nomes == ["A", "A.2", "A.1", "col_3", "col_4", "BASE"]


def test_padronizacao_numerica_equivale_a_celula_a_celula():
    valores = [1.0, 2.5, -0.0, 1e-7, None, 10**20]
    serie = pd.Series(valores, dtype=float)
    vetorial = robo._padronizar_coluna_texto(serie)
    esperado = [
        robo._celula_para_texto(valor) if not pd.isna(valor) else None
        for valor in valores
    ]
    obtido = [None if pd.isna(valor) else str(valor) for valor in vetorial]
    assert obtido == esperado


def test_padronizacao_de_texto_remove_sufixo_e_mantem_zeros():
    valores = ["001", "1.0", "-2.0", "nan", "N/A", ""]
    vetorial = robo._padronizar_coluna_texto(pd.Series(valores, dtype="string"))
    assert vetorial.tolist() == ["001", "1", "-2", "nan", "N/A", ""]

    df = robo._padronizar_dataframe(
        pd.DataFrame({"A": valores, "B": ["x", "y", "z", "w", "v", "u"]})
    )
    assert [None if pd.isna(v) else v for v in df["A"]] == [
        "001",
        "1",
        "-2",
        None,
        None,
        None,
    ]


def test_padronizacao_de_booleanos_mantem_o_texto_anterior():
    serie = pd.Series([True, False, None], dtype="boolean")
    assert robo._padronizar_coluna_texto(serie).tolist()[:2] == ["True", "False"]


def test_padronizacao_do_dataframe_limpa_colunas_e_linhas_vazias():
    df = pd.DataFrame(
        {
            "Nome": [" Ana ", "nan", None],
            "Nome.1": ["1.0", "x", None],
            "Unnamed: 2": [None, None, None],
        }
    )
    saida = robo._padronizar_dataframe(df)
    assert list(saida.columns) == ["Nome", "Nome.1", "col_2"]
    assert saida["Nome"].tolist()[:2] == ["Ana", pd.NA]
    assert saida["Nome.1"].tolist()[:2] == ["1", "x"]


# ── Leitura CSV / Excel ─────────────────────────────────────────────
def test_csv_cp1252_com_ponto_e_virgula_e_acentos(tmp_path):
    caminho = tmp_path / "Atividades-SPO-2026.csv"
    caminho.write_bytes(
        "NOME;OBSERVAÇÃO\nAna;São Paulo\nBia;Guarulhos\n".encode("cp1252")
    )

    leitura = robo.ler_arquivo_detalhado(str(caminho))

    assert leitura.erro is None
    assert leitura.motor == "csv cp1252 sep=';'"
    assert leitura.df is not None
    assert leitura.df["OBSERVAÇÃO"].tolist() == ["São Paulo", "Guarulhos"]


def test_csv_com_virgula_dentro_de_aspas_nao_quebra_o_cabecalho(tmp_path):
    caminho = _csv(
        tmp_path / "Atividades-GRS.csv",
        '"Nome, completo","ID"\n"Ana, Silva",1\n"Bia",2\n',
    )

    leitura = robo.ler_arquivo_detalhado(str(caminho))

    assert leitura.erro is None
    assert leitura.df is not None
    assert list(leitura.df.columns) == ["Nome, completo", "ID"]
    assert leitura.df["Nome, completo"].tolist() == ["Ana, Silva", "Bia"]


def test_colunas_esperadas_sao_alinhadas_sem_diferenciar_caixa(tmp_path):
    caminho = _csv(tmp_path / "Atividades-ABCDM.csv", "nome;valor\nAna;10\n")

    leitura = robo.ler_arquivo_detalhado(
        str(caminho), colunas_esperadas=["Nome", "VALOR"]
    )

    assert leitura.erro is None
    assert leitura.df is not None
    assert list(leitura.df.columns) == ["Nome", "VALOR"]


def test_colunas_esperadas_ausentes_viram_erro_de_negocio(tmp_path):
    caminho = _csv(tmp_path / "Atividades-SPO.csv", "nome\nAna\n")

    leitura = robo.ler_arquivo_detalhado(
        str(caminho), colunas_esperadas=["nome", "contrato"]
    )

    assert leitura.df is None
    assert leitura.erro is not None
    assert "colunas ausentes" in leitura.erro
    assert "contrato" in leitura.erro


def test_xlsx_usa_openpyxl_e_aplica_marcador_da_base(tmp_path):
    caminho = _xlsx(
        tmp_path / "Atividades-GRS-2026.xlsx",
        pd.DataFrame({"NOME": ["Ana", "Bia"], "VALOR": [1.0, 2.0]}),
    )

    leitura = robo.ler_arquivo_detalhado(str(caminho))

    assert leitura.erro is None
    assert leitura.motor is not None
    assert leitura.df is not None
    com_base = robo._aplicar_base_no_dataframe(leitura.df, "NET-GUARULHOS")
    assert com_base["BASE"].tolist() == ["NET-GUARULHOS", "NET-GUARULHOS"]
    assert com_base["VALOR"].tolist() == ["1", "2"]


def test_xlsx_com_titulo_na_primeira_linha_cai_no_header_1(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Relatório TOTALE"])
    ws.append(["NOME", "VALOR"])
    ws.append(["Ana", 1])
    caminho = tmp_path / "Atividades-ABCDM.xlsx"
    wb.save(caminho)

    leitura = robo.ler_arquivo_detalhado(str(caminho))

    assert leitura.erro is None
    assert leitura.df is not None
    assert list(leitura.df.columns) == ["NOME", "VALOR"]
    assert leitura.motor is not None and "header=1" in leitura.motor


def test_xlsx_truncado_e_rejeitado_com_mensagem_clara(tmp_path):
    caminho = tmp_path / "Atividades-SPO.xlsx"
    caminho.write_bytes(b"PK\x03\x04download-incompleto")

    leitura = robo.ler_arquivo_detalhado(str(caminho))

    assert leitura.df is None
    assert leitura.erro is not None
    assert "download incompleto" in leitura.erro


# ── Descoberta e ciclo ──────────────────────────────────────────────
def test_listagem_ignora_temporarios_atalhos_e_arquivos_vazios(tmp_path):
    bom = _csv(tmp_path / "Atividades-SPO-2026.csv", "nome\nAna\n")
    _csv(tmp_path / "Atividades-GRS-2026.csv.tmp", "nome\nBia\n")
    _csv(tmp_path / "~$Atividades-ABCDM.csv", "nome\nBia\n")
    (tmp_path / "Atividades-SPO-vazio.csv").write_text("", encoding="utf-8")
    _csv(tmp_path / "outro-arquivo.csv", "nome\nIgnorado\n")
    os.utime(bom, ns=(1_700_000_000_000_000_000, 1_700_000_000_000_000_000))

    candidatos = robo._listar_candidatos_com_stat(str(tmp_path))

    assert [Path(item[0]).name for item in candidatos] == [bom.name]


def test_selecao_usa_somente_o_arquivo_mais_recente():
    candidatos = [
        ("/tmp/a.csv", 10, 100),
        ("/tmp/b.csv", 30, 100),
        ("/tmp/c.csv", 20, 100),
    ]

    assert robo.selecionar_arquivos(candidatos)[0][0] == "/tmp/b.csv"
    assert robo.selecionar_arquivos([]) == []


def test_processar_candidatos_aplica_base_e_registra_motor(tmp_path):
    caminho = _csv(tmp_path / "Atividades-SPO-2026.csv", "nome;valor\nAna;1\n")

    resultado = robo.processar_candidatos(
        robo._listar_candidatos_com_stat(str(tmp_path))
    )

    assert resultado.df is not None
    assert resultado.bases == ("NET-LESTE",)
    assert resultado.arquivos == (str(caminho),)
    assert resultado.df["BASE"].tolist() == ["NET-LESTE"]
    assert resultado.motores and "csv" in resultado.motores[0]
    assert resultado.duplicatas_removidas == 0


def test_fachada_lista_bases_e_le_mais_recente(tmp_path):
    _csv(tmp_path / "Atividades-SPO.csv", "nome\nSPO\n")
    _csv(tmp_path / "Atividades-GRS.csv", "nome\nGRS\n")
    _csv(tmp_path / "Atividades-ABCDM.csv", "nome\nABCDM\n")

    assert len(robo.TotaleRoboEngine.listar_validos(tmp_path)) == 3
    por_base = robo.TotaleRoboEngine.arquivos_por_base(tmp_path)
    assert set(por_base) == {"NET-ABCDM", "NET-GUARULHOS", "NET-LESTE"}
    assert robo.TotaleRoboEngine.buscar_mais_recente(tmp_path) is not None
    df = robo.TotaleRoboEngine.ler_mais_recente(tmp_path, aplicar_base=True)
    assert df is not None and "BASE" in df.columns


def test_ciclo_headless_grava_csv_e_nao_sobrescreve_a_origem(tmp_path):
    origem = _csv(tmp_path / "Atividades-SPO.csv", "nome;valor\nAna;1\n")
    destino = tmp_path / "saida.csv"

    ciclo = robo.executar_ciclo_headless(str(tmp_path), destino_csv=str(destino))

    assert ciclo.df is not None
    assert destino.exists()
    lido = pd.read_csv(destino, sep=";", encoding="utf-8-sig")
    assert lido["BASE"].tolist() == ["NET-LESTE"]

    with pytest.raises(ValueError, match="sobrescrever"):
        robo.executar_ciclo_headless(str(tmp_path), destino_csv=str(origem))


# ── Painel Streamlit ────────────────────────────────────────────────
def _app_robo(pasta: Path, extra: str = "", ciclos: int = 2) -> AppTest:
    script = f"""
import streamlit as st
from components.robo_local import renderizar_robo_local

st.set_page_config(layout="wide")
renderizar_robo_local(
    pasta_padrao={str(pasta)!r},
    ciclos_estabilidade={ciclos},
    mostrar_config=False,
)
{extra}
"""
    return AppTest.from_string(script).run()


def _markdown(app: AppTest) -> str:
    return "\n".join(str(item.value) for item in app.markdown)


def test_painel_renderiza_bases_e_nao_quebra_sem_arquivos(tmp_path):
    app = _app_robo(tmp_path)

    assert not app.exception
    painel = _markdown(app)
    assert "Bases locais prontas para os painéis" in painel
    assert "NET-ABCDM" in painel
    assert "NET-LESTE" in painel
    assert "NET-GUARULHOS" in painel
    assert "Monitorando novas exportações" in painel
    assert app.toggle[0].label == "Auto-sincronizar"


def test_painel_lista_o_arquivo_da_pasta(tmp_path):
    arquivo = _csv(tmp_path / "Atividades-SPO-2026.csv", "nome\nAna\n")

    app = _app_robo(tmp_path)

    assert not app.exception
    painel = _markdown(app)
    assert arquivo.name in painel
    assert "Fila de arquivos" in painel
    assert "NET-LESTE" in painel


def test_botao_sincronizar_processa_e_publica_df_memoria(tmp_path):
    _csv(tmp_path / "Atividades-SPO-2026.csv", "nome;valor\nAna;1\nBia;2\n")
    app = _app_robo(tmp_path, extra="", ciclos=1)

    assert not app.exception
    assert not app.button(key="robo_sincronizar_agora").disabled
    app.button(key="robo_sincronizar_agora").click().run()

    assert not app.exception
    df = app.session_state["df_memoria"]
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 2
    assert df["BASE"].tolist() == ["NET-LESTE", "NET-LESTE"]
    assert app.session_state["robo_processado_sig"] is not None
    assert "df_memoria_raw" in app.session_state


def test_etl_personalizado_enriquece_a_base_publicada(tmp_path):
    _csv(tmp_path / "Atividades-GRS-2026.csv", "nome\nAna\n")
    script = f"""
import streamlit as st
from components.robo_local import renderizar_robo_local

st.set_page_config(layout="wide")

def etl(df, ativos):
    return df.assign(ETL="ok")

renderizar_robo_local(
    etl_fn=etl,
    pasta_padrao={str(tmp_path)!r},
    ciclos_estabilidade=1,
    mostrar_config=False,
)
"""
    app = AppTest.from_string(script).run()
    app.button(key="robo_sincronizar_agora").click().run()

    assert not app.exception
    df = app.session_state["df_memoria"]
    assert df["ETL"].tolist() == ["ok"]
    assert app.session_state["df_memoria_raw"].shape[1] < df.shape[1]


def test_css_do_painel_usa_oscine_nos_titulos():
    css = robo._CSS_ROBO

    assert "font-family: var(--font-hero) !important;" in css
    assert ".robo-title" in css
    assert ".robo-base-name" in css
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_central_de_atualizacao_hospeda_o_painel_e_publica_a_base(tmp_path):
    from components.robo_local import _listar_candidatos_com_stat, selecionar_arquivos

    pasta = tmp_path / "downloads"
    pasta.mkdir()
    pd.DataFrame(
        {
            "CONTRATO": ["1", "2"],
            "LOGIN DO TÉCNICO": ["login0", "login1"],
            "TÉCNICO": ["ANA", "BIA"],
            "MONITOR": ["MON", "MON"],
            "STATUS DA ATIVIDADE": ["ATIVA", "ATIVA"],
            "STATUS DA O.S 1": ["EXECUTADA", "PENDENTE"],
            "TIPO O.S 1": ["ADESAO", "ADESAO"],
            "HABILIDADE DE TRABALHO": ["HFC(1/100)", "PON(1/100)"],
            "CIDADE": ["SAO PAULO", "GUARULHOS"],
            "TOTAL DE TAREFAS": [1, 1],
        }
    ).to_csv(pasta / "Atividades-SPO-2026.csv", index=False, sep=";")

    assinatura = tuple(selecionar_arquivos(_listar_candidatos_com_stat(str(pasta))))
    app = AppTest.from_file(
        str(Path(__file__).resolve().parents[1] / "pages" / "envio_excel.py")
    )
    app.session_state["dados_cons"] = {"Consultivo": pd.DataFrame({"a": [1]})}
    app.session_state["dados_prod"] = {"Prod": pd.DataFrame({"a": [1]})}
    app.session_state["robo_pasta_alvo"] = str(pasta)
    app.session_state["robo_candidato_sig"] = assinatura
    app.session_state["robo_candidato_stable"] = 2
    app.session_state["robo_processado_sig"] = None
    app.run()

    assert not app.exception
    texto = _markdown(app)
    assert "Robô de sincronismo" in texto
    assert "NET-LESTE" in texto
    df = app.session_state["df_memoria"]
    assert isinstance(df, pd.DataFrame)
    assert "TIPO_SERVICO" in df.columns  # ETL da Quebra aplicado
    assert "df_memoria_raw" in app.session_state


def test_pasta_vazia_nao_varre_o_diretorio_atual(tmp_path, monkeypatch):
    _csv(tmp_path / "Atividades-SPO.csv", "nome\nAna\n")
    monkeypatch.chdir(tmp_path)

    assert robo._listar_candidatos_com_stat("") == []
    assert robo.mapear_arquivos_por_base("") == {}


def test_falha_no_etl_nao_publica_a_base(tmp_path):
    _csv(tmp_path / "Atividades-SPO-2026.csv", "nome\nAna\n")
    script = f"""
import streamlit as st
from components.robo_local import renderizar_robo_local

st.set_page_config(layout="wide")

def etl(df, ativos):
    raise RuntimeError("ETL quebrado")

renderizar_robo_local(
    etl_fn=etl,
    pasta_padrao={str(tmp_path)!r},
    ciclos_estabilidade=1,
    mostrar_config=False,
)
"""
    app = AppTest.from_string(script).run()
    app.button(key="robo_sincronizar_agora").click().run()

    assert not app.exception
    assert "ETL quebrado" in app.session_state["robo_erro"]
    assert "df_memoria" not in app.session_state
    assert not app.session_state["robo_processando"]
    assert app.session_state["robo_falha_sig"] is not None
