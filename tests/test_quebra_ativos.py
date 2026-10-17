"""Regressões offline do vínculo entre Quebra de Agenda e lista_ativos."""

import pandas as pd

from components.componentes import estilizar_dataframe
from pages import quebra


def test_leitura_autenticada_da_mesma_aba_da_gestao(monkeypatch):
    chamadas = {}
    raw = [{"RE": "10", "Login": " abC.0 ", "Técnico": "Ana", "Monitor": "Lia", "Situação": "ATIVO"}]

    class Worksheet:
        def get_all_records(self, **kwargs):
            return raw

    class Sheet:
        def worksheet(self, name):
            chamadas["aba"] = name
            return Worksheet()

    class Client:
        def open_by_key(self, key):
            chamadas["id"] = key
            return Sheet()

    monkeypatch.setattr(quebra.st, "secrets", {"gcp_service_account": {"type": "service_account"}})
    monkeypatch.setattr(quebra.Credentials, "from_service_account_info", lambda *a, **k: object())
    monkeypatch.setattr(quebra.gspread, "authorize", lambda creds: Client())
    monkeypatch.setattr(quebra.st, "connection", lambda *a, **k: (_ for _ in ()).throw(AssertionError("fallback indevido")))

    ativos = quebra.DataLoader.buscar_gsheets.__wrapped__()
    assert chamadas == {"id": quebra.Config.SHEET_ID_ATIVOS, "aba": "lista_ativos"}
    assert ativos.loc[0, "Login"] == "ABC"
    assert ativos.attrs["fonte_ativos"] == "Google Sheets (autenticado)"


def test_fallback_conexao_sem_conta_de_servico(monkeypatch):
    monkeypatch.setattr(quebra.st, "secrets", {})
    conexao = type("Conexao", (), {"read": lambda self, **kw: pd.DataFrame({
        "Login": ["x"], "Monitor": ["Marta"],
    })})()
    monkeypatch.setattr(quebra.st, "connection", lambda *a, **k: conexao)
    ativos = quebra.DataLoader.buscar_gsheets.__wrapped__()
    assert ativos.loc[0, "Monitor"] == "Marta"
    assert ativos.attrs["fonte_ativos"] == "Google Sheets (conexão)"


def test_falha_na_leitura_nao_fica_silenciosa(monkeypatch):
    monkeypatch.setattr(quebra.st, "secrets", {})
    monkeypatch.setattr(quebra.st, "connection", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("indisponível")))
    monkeypatch.setattr(quebra.pd, "read_csv", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("privada")))
    ativos = quebra.DataLoader.buscar_gsheets.__wrapped__()
    assert ativos.empty
    assert "lista_ativos" in ativos.attrs["erro_ativos"]


def test_login_normalizado_e_monitor_da_lista_prevalece():
    ativos = quebra.DataLoader._normalizar_lista_ativos(pd.DataFrame({
        "Login": ["abc", "def.0", "saiu"],
        "Técnico": ["Ana", "Beto", "Cris"],
        "Monitor": ["Lia", "João", "Outro"],
        "Situação": ["ATIVO", "FÉRIAS", "DESLIGADO"],
    }))
    assert ativos["Login"].tolist() == ["ABC", "DEF"]
    com_alias = quebra.DataLoader._normalizar_lista_ativos(pd.DataFrame({
        "Matrícula": ["errado"], "Login": ["correto"],
        "Gestor": ["outro"], "Monitor": ["Lia"],
    }))
    assert com_alias.loc[0, "Login"] == "CORRETO"
    assert com_alias.loc[0, "Monitor"] == "Lia"
    ativos.attrs["fonte_ativos"] = "Google Sheets (autenticado)"
    base = pd.DataFrame({
        "CONTRATO": ["123", "124", "125"],
        "LOGIN DO TÉCNICO": [" ABC.0 ", "def", "sem cadastro"],
        "MONITOR": ["Antigo", "", "Arquivo"],
        "STATUS DA O.S 1": ["EXECUTADA", "NÃO EXECUTADA", "EXECUTADA"],
    })
    df = quebra.DataLoader.preparar_base.__wrapped__(base, ativos)
    assert df["MONITOR"].tolist() == ["LIA", "JOÃO", "ARQUIVO"]
    assert df["ORIGEM_MAPEAMENTO"].tolist() == ["Merge (Sheets)", "Merge (Sheets)", "Arquivo Origem"]
    assert df.attrs["diag_vinculados"] == 2
    assert df.attrs["fonte_ativos"] == "Google Sheets (autenticado)"


def test_tabela_compartilhada_formata_sem_alterar_valores():
    df = pd.DataFrame({"Monitor": ["LIA", "Total Geral"], "Quebra Geral": [0.12, 0.15]})
    html = estilizar_dataframe(df, {"Quebra Geral": "{:.1%}"}).to_html()
    assert "12.0%" in html
    assert "#EAF2FC" in html
    assert df.loc[1, "Quebra Geral"] == 0.15
