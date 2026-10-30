"""Testes do upload manual da base operacional (``components/base_operacional``).

Um único arquivo enviado gera a base da Rota Inicial, com vínculo à lista
de ativos, e falhas de leitura/contrato devem virar mensagem em ``erros``
em vez de exceção.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd

from components import base_operacional as bo

COLUNAS = [
    "CONTRATO",
    "LOGIN DO TÉCNICO",
    "STATUS DA O.S 1",
    "STATUS DA ATIVIDADE",
    "TOTAL DE TAREFAS",
    "TIPO O.S 1",
    "HABILIDADE DE TRABALHO",
    "PRODUTO",
    "INTERVALO DE TEMPO",
    "CIDADE",
]

LINHAS = [
    "123;TEC1;EXECUTADA;ATIVA;2;01 - ADESAO;PON(1/100) PME;CLARO TV+ 4K;"
    "08:00 - 10:00;SAO PAULO",
    "456;TEC2;NAO EXECUTADA;ATIVA;1;24 - MUDANCA DE PACOTE;PON(1/100);"
    "SOUNDBOX;12:00 - 14:00;GUARULHOS",
    # Suspensa: a Rota Inicial mantém o registro.
    "789;TEC1;PENDENTE;SUSPENSO;1;01 - ADESAO;TV VAS(1/100);INTERNET 500;"
    "Imediata;SANTO ANDRE",
]

ATIVOS = pd.DataFrame(
    {
        "Login": ["TEC1", "TEC2"],
        "Técnico": ["Tecnico Um", "Tecnico Dois"],
        "Monitor": ["Monitor A", "Monitor B"],
        "Base": ["LESTE", "GRU"],
    }
)


def _csv(linhas=LINHAS, colunas=COLUNAS) -> bytes:
    return (";".join(colunas) + "\n" + "\n".join(linhas) + "\n").encode("utf-8")


def test_upload_gera_base_da_rota_inicial_com_vinculo():
    resultado = bo.gerar_bases_upload(_csv(), "Atividades-teste.csv", ATIVOS)

    assert resultado["linhas_brutas"] == 3
    assert resultado["erros"] == {}

    rota = resultado["rota_inicial"]
    assert len(rota) == 3
    assert list(rota["Monitor"]) == ["Monitor A", "Monitor B", "Monitor A"]
    assert list(rota["PERIODO_TRATADO"]) == ["Manhã", "Tarde I", "Imediata"]
    assert list(rota["REGIÃO"]) == ["LESTE", "GRU", "ABCDM"]
    assert rota.attrs["diag_vinculados"] == 3
    assert rota.attrs["diag_ativos"] == 2


def test_sem_lista_de_ativos_degrada_sem_falhar():
    resultado = bo.gerar_bases_upload(_csv(), "base.csv", pd.DataFrame())

    assert resultado["erros"] == {}
    rota = resultado["rota_inicial"]
    assert len(rota) == 3
    assert set(rota["Monitor"]) == {"SEM MONITOR"}
    # Sem a lista, o login do arquivo vira o nome exibido do técnico.
    assert set(rota["NOME_OFICIAL"]) == {"TEC1", "TEC2"}
    assert rota.attrs["diag_vinculados"] == 0


def test_base_sem_contrato_vira_erro_sem_excecao():
    colunas = [c for c in COLUNAS if c != "CONTRATO"]
    linhas = [
        "TEC1;EXECUTADA;ATIVA;2;01 - ADESAO;PON(1/100);CLARO TV+ 4K;"
        "08:00 - 10:00;SAO PAULO"
    ]
    resultado = bo.gerar_bases_upload(_csv(linhas, colunas), "base.csv", ATIVOS)

    assert resultado["rota_inicial"] is None
    assert "contrato" in resultado["erros"]["rota_inicial"].lower()


def test_extensao_invalida_vira_erro_de_leitura():
    resultado = bo.gerar_bases_upload(b"conteudo", "base.txt", ATIVOS)

    assert resultado["linhas_brutas"] == 0
    assert "leitura" in resultado["erros"]
    assert resultado["rota_inicial"] is None


def test_arquivo_sem_registros_vira_erro_de_leitura():
    resultado = bo.gerar_bases_upload(_csv(linhas=[]), "base.csv", ATIVOS)

    assert resultado["linhas_brutas"] == 0
    assert "leitura" in resultado["erros"]
    assert resultado["rota_inicial"] is None


def test_upload_xlsx():
    bruto = pd.DataFrame([linha.split(";") for linha in LINHAS], columns=COLUNAS)
    buffer = BytesIO()
    bruto.to_excel(buffer, index=False, engine="openpyxl")

    resultado = bo.gerar_bases_upload(
        buffer.getvalue(), "Atividades.xlsx", ATIVOS
    )

    assert resultado["erros"] == {}
    assert len(resultado["rota_inicial"]) == 3


def test_normalizar_lista_ativos_limpa_e_deduplica():
    bruta = pd.DataFrame(
        {
            "login": [" tec1.0 ", "TEC1", "TEC2", ""],
            "tecnico": ["Antigo", "Atual", "Dois", "Sem login"],
            "monitor": ["A", "A", "B", "C"],
            "situacao": ["ATIVO", "ATIVO", "DESLIGADO", "ATIVO"],
        }
    )

    normalizada = bo.normalizar_lista_ativos(bruta)

    # ".0"/espaços normalizados, duplicado fica com o último, desligado sai.
    assert list(normalizada["Login"]) == ["TEC1"]
    assert list(normalizada["Técnico"]) == ["Atual"]


def test_hierarquia_de_aceita_lista_bruta():
    hierarquia = bo.hierarquia_de(ATIVOS)

    assert list(hierarquia["__LOGIN_KEY"]) == ["TEC1", "TEC2"]
    assert list(hierarquia["__MON_GS"]) == ["Monitor A", "Monitor B"]
    assert bo.hierarquia_de(pd.DataFrame()).empty


# Habilidades trazem parênteses ("TV VAS(1/100)", "PON(1/100)"); as buscas
# precisam ser literais, senão o parêntese vira grupo de regex e o termo só
# casaria com a grafia sem parênteses — que não existe na exportação real.
def test_flags_de_habilidade_casam_termos_com_parenteses():
    linhas = [
        "111;TEC1;EXECUTADA;ATIVA;1;01 - ADESAO;TV VAS(1/100);CLARO TV;"
        "08:00 - 10:00;SAO PAULO",
        "222;TEC2;EXECUTADA;ATIVA;1;01 - ADESAO;PON(1/100) NETLAR;INTERNET;"
        "12:00 - 14:00;GUARULHOS",
    ]
    resultado = bo.gerar_bases_upload(_csv(linhas), "base.csv", ATIVOS)

    assert resultado["erros"] == {}
    rota = resultado["rota_inicial"].set_index("CONTRATO")

    # Streaming só na primeira linha.
    assert bool(rota.loc["111", "Check_Streaming"]) is True
    assert bool(rota.loc["222", "Check_Streaming"]) is False
    # GPON e Ponto Ultra apenas na segunda.
    assert bool(rota.loc["111", "Check_GPON"]) is False
    assert bool(rota.loc["222", "Check_GPON"]) is True
    assert bool(rota.loc["222", "Check_Ponto_Ultra"]) is True


def test_reprocessar_vinculo_usa_arquivo_da_sessao(monkeypatch):
    from components import upload_base as ub

    estado = {ub.CHAVE_ARQUIVO: (b"conteudo", "base.csv")}
    monkeypatch.setattr(ub.st, "session_state", estado, raising=False)

    chamadas: dict[str, object] = {}
    monkeypatch.setattr(
        ub, "limpar_cache_lista_ativos", lambda: chamadas.update(cache=True)
    )
    monkeypatch.setattr(
        ub,
        "processar_e_publicar",
        lambda conteudo, nome: (
            chamadas.update(arquivo=(conteudo, nome)) or {"linhas": {}}
        ),
    )

    assert ub.reprocessar_vinculo_ativos() is True
    assert chamadas["cache"] is True
    assert chamadas["arquivo"] == (b"conteudo", "base.csv")


def test_reprocessar_vinculo_sem_arquivo_nao_falha(monkeypatch):
    from components import upload_base as ub

    monkeypatch.setattr(ub.st, "session_state", {}, raising=False)

    assert ub.reprocessar_vinculo_ativos() is False
