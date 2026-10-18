"""As páginas Volumetria e Quebra precisam abrir com e sem a base do robô."""

from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from components import base_operacional as bo

ROOT = Path(__file__).resolve().parents[1]


def base_sintetica(caminho: Path) -> Path:
    pd.DataFrame(
        {
            "CONTRATO": ["1", "2", "3"],
            "LOGIN DO TÉCNICO": ["login0", "login1", "login2"],
            "TÉCNICO": ["TEC A", "TEC A", "TEC B"],
            "MONITOR": ["MON A", "MON A", "MON A"],
            "STATUS DA ATIVIDADE": ["ATIVA", "ATIVA", "ATIVA"],
            "STATUS DA O.S 1": ["EXECUTADA", "NÃO EXECUTADA", "PENDENTE"],
            "TIPO O.S 1": ["ADESAO", "MUDANCA DE PACOTE", "ADESAO"],
            "HABILIDADE DE TRABALHO": ["HFC(1/100)", "PON(1/100)", "PME(1/100)"],
            "CIDADE": ["SAO PAULO", "GUARULHOS", "DIADEMA"],
            "TOTAL DE TAREFAS": [1, 1, 1],
        }
    ).to_excel(caminho, index=False)
    return caminho


def test_volumetria_mostra_upload_quando_nao_ha_base(monkeypatch, tmp_path):
    monkeypatch.setenv("TOTALE_BASE_ENTRADA", str(tmp_path / "vazio_entrada"))
    monkeypatch.setenv("TOTALE_BASE_CACHE", str(tmp_path / "vazio_cache"))

    app = AppTest.from_file(ROOT / "pages" / "volumetria.py").run()

    assert not app.exception
    assert len(app.get("file_uploader")) == 1


def test_quebra_mostra_upload_quando_nao_ha_base(monkeypatch, tmp_path):
    monkeypatch.setenv("TOTALE_BASE_ENTRADA", str(tmp_path / "vazio_entrada"))
    monkeypatch.setenv("TOTALE_BASE_CACHE", str(tmp_path / "vazio_cache"))

    app = AppTest.from_file(ROOT / "pages" / "quebra.py").run()

    assert not app.exception
    assert len(app.get("file_uploader")) == 1


def test_quebra_aceita_sessao_antiga_sem_coluna_monitor():
    app = AppTest.from_file(ROOT / "pages" / "quebra.py")
    app.session_state["df_memoria"] = pd.DataFrame(
        {
            "CONTRATO": ["1"],
            "TÉCNICO": ["TEC A"],
            "Status Contrato": ["Executada"],
            "TOTAL DE TAREFAS": [1],
            "TIPO_SERVICO": ["Novos Domicílios"],
            "TIPO O.S 1": ["ADESAO"],
            "HABILIDADE DE TRABALHO": ["HFC(1/100)"],
            "ORIGEM_MAPEAMENTO": ["Arquivo Origem"],
        }
    )

    app.run()

    assert not app.exception
    assert app.session_state["df_memoria"]["MONITOR"].tolist() == ["SEM MONITOR"]


def test_volumetria_carrega_a_base_do_robo_sem_upload(monkeypatch, tmp_path):
    entrada, cache = tmp_path / "entrada", tmp_path / "cache"
    entrada.mkdir()
    base_sintetica(entrada / "base.xlsx")
    monkeypatch.setenv("TOTALE_BASE_ENTRADA", str(entrada))
    monkeypatch.setenv("TOTALE_BASE_CACHE", str(cache))

    ativos = pd.DataFrame(
        {"Login": ["LOGIN0"], "Técnico": ["TEC SHEETS"], "Monitor": ["MON SHEETS"]}
    )
    ativos.attrs["fonte_ativos"] = "Google Sheets (autenticado)"
    monkeypatch.setattr(bo, "carregar_lista_ativos", lambda *a, **k: ativos)

    app = AppTest.from_file(ROOT / "pages" / "volumetria.py").run()

    assert not app.exception
    assert len(app.get("file_uploader")) == 0  # base automática carregada
    assert len(app.get("multiselect")) == 4  # Monitor, Região, Técnico, Status
    assert bo.status_base(cache)["status"] == "ok"


def test_quebra_carrega_a_base_do_robo_e_mostra_os_segmentos(monkeypatch, tmp_path):
    entrada, cache = tmp_path / "entrada", tmp_path / "cache"
    entrada.mkdir()
    base_sintetica(entrada / "base.xlsx")
    monkeypatch.setenv("TOTALE_BASE_ENTRADA", str(entrada))
    monkeypatch.setenv("TOTALE_BASE_CACHE", str(cache))

    ativos = pd.DataFrame(
        {"Login": ["LOGIN0"], "Técnico": ["TEC SHEETS"], "Monitor": ["MON SHEETS"]}
    )
    ativos.attrs["fonte_ativos"] = "Google Sheets (autenticado)"
    monkeypatch.setattr(bo, "carregar_lista_ativos", lambda *a, **k: ativos)

    app = AppTest.from_file(ROOT / "pages" / "quebra.py").run()

    assert not app.exception
    assert len(app.get("file_uploader")) == 0
    textos = " ".join(item.value for item in app.markdown)
    assert "Super Relatório de Quebra de Agenda" in textos


def test_volumetria_resolve_tipo_da_conexao_gsheets(monkeypatch):
    from pages import volumetria

    argumentos_conexao = {}

    def conectar(nome, **kwargs):
        argumentos_conexao.update(nome=nome, **kwargs)
        return object()

    def carregar_base(**kwargs):
        kwargs["conexao"]()
        return pd.DataFrame({"CONTRATO": ["1"]})

    monkeypatch.setattr(volumetria.st, "connection", conectar)
    monkeypatch.setattr(bo, "carregar_base_volumetria", carregar_base)

    base = volumetria.DataLoader.carregar_base_automatica.__wrapped__()

    assert argumentos_conexao == {
        "nome": "gsheets",
        "type": volumetria.GSheetsConnection,
    }
    assert base["CONTRATO"].tolist() == ["1"]


def test_volumetria_recarregar_limpa_caches_e_forca_leitura(monkeypatch):
    from pages import volumetria

    chamadas = []

    def buscar_hierarquia():
        return pd.DataFrame()

    buscar_hierarquia.clear = lambda: chamadas.append("limpar_hierarquia")

    def carregar_base(forcar=False):
        chamadas.append(("carregar_base", forcar))
        return pd.DataFrame({"TÉCNICO": ["TEC A"]})

    carregar_base.clear = lambda: chamadas.append("limpar_base")

    monkeypatch.setattr(
        volumetria.DataLoader, "buscar_hierarquia_gsheets", buscar_hierarquia
    )
    monkeypatch.setattr(
        volumetria.DataLoader, "carregar_base_automatica", carregar_base
    )

    base = volumetria.DataLoader.recarregar_base_automatica()

    assert chamadas == [
        "limpar_hierarquia",
        "limpar_base",
        ("carregar_base", True),
    ]
    assert base["TÉCNICO"].tolist() == ["TEC A"]


def test_volumetria_botao_atualizar_robo_nao_repete_tentativa(monkeypatch, tmp_path):
    monkeypatch.setenv("TOTALE_BASE_ENTRADA", str(tmp_path / "entrada"))
    monkeypatch.setenv("TOTALE_BASE_CACHE", str(tmp_path / "cache"))
    from pages import volumetria

    chamadas = []

    def carregar_base(forcar=False, **kwargs):
        chamadas.append(forcar)
        return pd.DataFrame()

    monkeypatch.setattr(bo, "carregar_base_volumetria", carregar_base)
    volumetria.st.cache_data.clear()

    app = AppTest.from_file(ROOT / "pages" / "volumetria.py").run()
    assert not app.exception
    assert app.session_state["base_data"] is None
    chamadas.clear()
    app.button[0].click().run()

    assert not app.exception
    assert chamadas == [True]
    assert app.session_state["base_data"] is None
    assert len(app.get("file_uploader")) == 1


def test_filtro_base_analitica_e_literal_e_preserva_a_base():
    from pages.quebra import _filtrar_base_analitica

    base = pd.DataFrame(
        {
            "CONTRATO": ["A+B", "AB", "C"],
            "MONITOR": ["LIA", "LIA", "NINA"],
        }
    )

    filtrada = _filtrar_base_analitica(base, ["CONTRATO"], " + ")

    assert filtrada["CONTRATO"].tolist() == ["A+B"]
    assert list(filtrada.columns) == ["CONTRATO"]
    assert list(base.columns) == ["CONTRATO", "MONITOR"]
