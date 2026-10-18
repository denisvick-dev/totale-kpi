"""Regressões offline do vínculo entre Quebra de Agenda e lista_ativos."""

import pandas as pd

from components.componentes import estilizar_dataframe
from pages import quebra


def test_leitura_autenticada_da_mesma_aba_da_gestao(monkeypatch):
    chamadas = {}
    raw = [
        {
            "RE": "10",
            "Login": " abC.0 ",
            "Técnico": "Ana",
            "Monitor": "Lia",
            "Situação": "ATIVO",
        }
    ]

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

    monkeypatch.setattr(
        quebra.st, "secrets", {"gcp_service_account": {"type": "service_account"}}
    )
    monkeypatch.setattr(
        quebra.Credentials, "from_service_account_info", lambda *a, **k: object()
    )
    monkeypatch.setattr(quebra.gspread, "authorize", lambda creds: Client())
    monkeypatch.setattr(
        quebra.st,
        "connection",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("fallback indevido")),
    )

    ativos = quebra.DataLoader.buscar_gsheets.__wrapped__()
    assert chamadas == {"id": quebra.Config.SHEET_ID_ATIVOS, "aba": "lista_ativos"}
    assert ativos.loc[0, "Login"] == "ABC"
    assert ativos.attrs["fonte_ativos"] == "Google Sheets (autenticado)"


def test_fallback_conexao_sem_conta_de_servico(monkeypatch):
    monkeypatch.setattr(
        quebra.st, "secrets", {"connections": {"gsheets": {"type": "service_account"}}}
    )
    conexao = type(
        "Conexao",
        (),
        {
            "read": lambda self, **kw: pd.DataFrame(
                {
                    "Login": ["x"],
                    "Monitor": ["Marta"],
                }
            )
        },
    )()
    monkeypatch.setattr(quebra.st, "connection", lambda *a, **k: conexao)
    ativos = quebra.DataLoader.buscar_gsheets.__wrapped__()
    assert ativos.loc[0, "Monitor"] == "Marta"
    assert ativos.attrs["fonte_ativos"] == "Google Sheets (conexão)"


def test_sem_secrets_usa_csv_sem_tentar_conexao_publica(monkeypatch, caplog):
    monkeypatch.setattr(quebra.st, "secrets", {})
    monkeypatch.setattr(
        quebra.st,
        "connection",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("conexão indevida")),
    )
    monkeypatch.setattr(
        quebra.pd,
        "read_csv",
        lambda *a, **k: pd.DataFrame({"Login": ["abc"], "Monitor": ["Lia"]}),
    )

    ativos = quebra.DataLoader.buscar_gsheets.__wrapped__()

    assert ativos["Login"].tolist() == ["ABC"]
    assert ativos.attrs["fonte_ativos"] == "Google Sheets (CSV público)"
    assert "No secrets found" not in caplog.text
    assert "Falha na conexão da lista_ativos" not in caplog.text


def test_recarregar_base_automatica_invalida_caches_e_forca_leitura(monkeypatch):
    chamadas = []

    def buscar_gsheets():
        return pd.DataFrame()

    buscar_gsheets.clear = lambda: chamadas.append("limpar_lista")

    def carregar_base_automatica(forcar=False):
        chamadas.append(("carregar_base", forcar))
        return pd.DataFrame({"MONITOR": ["LIA"]})

    carregar_base_automatica.clear = lambda: chamadas.append("limpar_base")

    monkeypatch.setattr(quebra.DataLoader, "buscar_gsheets", buscar_gsheets)
    monkeypatch.setattr(
        quebra.DataLoader, "carregar_base_automatica", carregar_base_automatica
    )

    base = quebra.DataLoader.recarregar_base_automatica()

    assert chamadas == [
        "limpar_lista",
        "limpar_base",
        ("carregar_base", True),
    ]
    assert base["MONITOR"].tolist() == ["LIA"]


def test_falha_na_leitura_nao_fica_silenciosa(monkeypatch):
    monkeypatch.setattr(quebra.st, "secrets", {})
    monkeypatch.setattr(
        quebra.st,
        "connection",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("indisponível")),
    )
    monkeypatch.setattr(
        quebra.pd,
        "read_csv",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("privada")),
    )
    ativos = quebra.DataLoader.buscar_gsheets.__wrapped__()
    assert ativos.empty
    assert "lista_ativos" in ativos.attrs["erro_ativos"]


def test_login_normalizado_e_monitor_da_lista_prevalece():
    ativos = quebra.DataLoader._normalizar_lista_ativos(
        pd.DataFrame(
            {
                "Login": ["abc", "def.0", "saiu"],
                "Técnico": ["Ana", "Beto", "Cris"],
                "Monitor": ["Lia", "João", "Outro"],
                "Situação": ["ATIVO", "FÉRIAS", "DESLIGADO"],
            }
        )
    )
    assert ativos["Login"].tolist() == ["ABC", "DEF"]
    com_alias = quebra.DataLoader._normalizar_lista_ativos(
        pd.DataFrame(
            {
                "Matrícula": ["errado"],
                "Login": ["correto"],
                "Gestor": ["outro"],
                "Monitor": ["Lia"],
            }
        )
    )
    assert com_alias.loc[0, "Login"] == "CORRETO"
    assert com_alias.loc[0, "Monitor"] == "Lia"
    ativos.attrs["fonte_ativos"] = "Google Sheets (autenticado)"
    base = pd.DataFrame(
        {
            "CONTRATO": ["123", "124", "125"],
            "LOGIN DO TÉCNICO": [" ABC.0 ", "def", "sem cadastro"],
            "MONITOR": ["Antigo", "", "Arquivo"],
            "STATUS DA O.S 1": ["EXECUTADA", "NÃO EXECUTADA", "EXECUTADA"],
        }
    )
    df = quebra.DataLoader.preparar_base.__wrapped__(base, ativos)
    assert df["MONITOR"].tolist() == ["LIA", "JOÃO", "ARQUIVO"]
    assert df["ORIGEM_MAPEAMENTO"].tolist() == [
        "Merge (Sheets)",
        "Merge (Sheets)",
        "Arquivo Origem",
    ]
    assert df.attrs["diag_vinculados"] == 2
    assert df.attrs["fonte_ativos"] == "Google Sheets (autenticado)"


def test_compatibiliza_base_legada_com_aliases_e_sem_monitor():
    legado = pd.DataFrame(
        {
            "Monitor": [" Lia ", None],
            "Tecnico": ["Ana", ""],
            "STATUS DA O.S 1": ["NÃO EXECUTADA", "EXECUTADA"],
            "TOTAL TAREFAS": ["2", "1"],
        }
    )

    base = quebra.DataLoader.compatibilizar_base(legado)

    assert base["MONITOR"].tolist() == ["LIA", "SEM MONITOR"]
    assert base["TÉCNICO"].tolist() == ["ANA", "NÃO MAPEADO"]
    assert base["Status Contrato"].tolist() == ["Não Executada", "Executada"]
    assert base["TOTAL DE TAREFAS"].tolist() == [2, 1]


def test_compatibiliza_base_legada_sem_colunas_de_monitor_e_tecnico():
    legado = pd.DataFrame({"CONTRATO": ["1"]})

    base = quebra.DataLoader.compatibilizar_base(legado)

    assert base["MONITOR"].tolist() == ["SEM MONITOR"]
    assert base["TÉCNICO"].tolist() == ["NÃO MAPEADO"]
    assert base.attrs["coluna_monitor_ausente"] is True
    assert base["Status Contrato"].tolist() == ["Pendente"]
    assert base["TOTAL DE TAREFAS"].tolist() == [1]


def test_tabela_compartilhada_formata_sem_alterar_valores():
    df = pd.DataFrame({"Monitor": ["LIA", "Total Geral"], "Quebra Geral": [0.12, 0.15]})
    html = estilizar_dataframe(df, {"Quebra Geral": "{:.1%}"}).to_html()
    assert "12.0%" in html
    assert "#EAF2FC" in html
    assert df.loc[1, "Quebra Geral"] == 0.15


def test_login_do_tecnico_na_lista_vincula_quebra_e_volumetria(monkeypatch):
    from components import base_operacional as bo
    from pages import volumetria

    for coluna in ("Login do Técnico", "Login do Tecnico", "LOGIN_DO_TECNICO"):
        ativos = quebra.DataLoader._normalizar_lista_ativos(
            pd.DataFrame(
                {
                    coluna: [" abc.0 "],
                    "Técnico": ["Ana"],
                    "Monitor": ["Lia"],
                }
            )
        )
        assert ativos["Login"].tolist() == ["ABC"]
        monkeypatch.setattr(bo, "carregar_lista_ativos", lambda **kw: ativos)
        hierarquia = bo.carregar_hierarquia()
        raw = pd.DataFrame(
            {
                "CONTRATO": ["123"],
                "LOGIN DO TÉCNICO": ["abc"],
                "STATUS DA O.S 1": ["EXECUTADA"],
            }
        )
        quebra_base = quebra.DataLoader.preparar_base.__wrapped__(raw, ativos)
        volumetria_base = volumetria.DataLoader.preparar_base(raw, hierarquia)
        assert quebra_base["MONITOR"].tolist() == ["LIA"]
        assert quebra_base.attrs["diag_vinculados"] == 1
        assert volumetria_base[bo.COL_MONITOR].str.upper().tolist() == ["LIA"]


def test_login_oficial_prevalece_sobre_alias_do_tecnico():
    ativos = quebra.DataLoader._normalizar_lista_ativos(
        pd.DataFrame(
            {
                "Login do Técnico": ["incorreto"],
                "Login": ["correto"],
            }
        )
    )
    assert ativos["Login"].tolist() == ["CORRETO"]
