"""Testes do upload manual compartilhado (``components/base_operacional``).

Um único arquivo enviado deve gerar as bases de Quebra de Agenda,
Volumetria e Rota Inicial, com vínculo à lista de ativos — e a falha
de um painel não pode bloquear os demais.
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
    # Suspensa: sai de Quebra/Volumetria, mas a Rota Inicial a mantém.
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


def test_upload_gera_as_tres_bases_com_vinculo():
    resultado = bo.gerar_bases_upload(_csv(), "Atividades-teste.csv", ATIVOS)

    assert resultado["linhas_brutas"] == 3
    assert resultado["erros"] == {}

    quebra = resultado["quebra"]
    assert len(quebra) == 2  # suspensa removida
    assert list(quebra["MONITOR"]) == ["MONITOR A", "MONITOR B"]
    assert list(quebra["Status Contrato"]) == ["Executada", "Não Executada"]
    assert quebra.attrs["diag_vinculados"] == 2

    volumetria = resultado["volumetria"]
    assert len(volumetria) == 2
    assert list(volumetria["MONITOR"]) == ["Monitor A", "Monitor B"]
    assert list(volumetria["REGIÃO"]) == ["LESTE", "GRU"]
    assert volumetria.attrs["diagnostico"]["Fonte"] == "Upload manual"

    rota = resultado["rota_inicial"]
    assert len(rota) == 3
    assert list(rota["Monitor"]) == ["Monitor A", "Monitor B", "Monitor A"]
    assert list(rota["PERIODO_TRATADO"]) == ["Manhã", "Tarde I", "Imediata"]
    assert list(rota["REGIÃO"]) == ["LESTE", "GRU", "ABCDM"]


def test_sem_lista_de_ativos_degrada_sem_falhar():
    resultado = bo.gerar_bases_upload(_csv(), "base.csv", pd.DataFrame())

    assert resultado["erros"] == {}
    assert set(resultado["quebra"]["MONITOR"]) == {"SEM MONITOR"}
    # Sem o Sheets, a Volumetria usa o login do arquivo como técnico.
    assert set(resultado["volumetria"]["TÉCNICO"]) == {"TEC1", "TEC2"}
    assert set(resultado["volumetria"]["MONITOR"]) == {"SEM MONITOR"}
    assert len(resultado["rota_inicial"]) == 3


def test_falha_de_um_painel_nao_bloqueia_os_demais():
    # Sem a coluna de status da O.S., só a Volumetria é inviável.
    colunas = [c for c in COLUNAS if c != "STATUS DA O.S 1"]
    linhas = [
        "123;TEC1;ATIVA;2;01 - ADESAO;PON(1/100);CLARO TV+ 4K;08:00 - 10:00;SAO PAULO"
    ]
    resultado = bo.gerar_bases_upload(
        _csv(linhas, colunas), "base.csv", ATIVOS
    )

    assert resultado["volumetria"] is None
    assert "Status da O.S 1" in resultado["erros"]["volumetria"]
    assert resultado["quebra"] is not None
    assert resultado["rota_inicial"] is not None


def test_extensao_invalida_vira_erro_de_leitura():
    resultado = bo.gerar_bases_upload(b"conteudo", "base.txt", ATIVOS)

    assert resultado["linhas_brutas"] == 0
    assert "leitura" in resultado["erros"]
    assert resultado["quebra"] is None


def test_upload_xlsx():
    bruto = pd.DataFrame(
        [linha.split(";") for linha in LINHAS], columns=COLUNAS
    )
    buffer = BytesIO()
    bruto.to_excel(buffer, index=False, engine="openpyxl")

    resultado = bo.gerar_bases_upload(
        buffer.getvalue(), "Atividades.xlsx", ATIVOS
    )

    assert resultado["erros"] == {}
    assert len(resultado["volumetria"]) == 2
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
