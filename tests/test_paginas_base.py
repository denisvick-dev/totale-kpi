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
    assert len(app.get("file_uploader")) == 0          # base automática carregada
    assert len(app.get("multiselect")) == 4            # Monitor, Região, Técnico, Status
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
