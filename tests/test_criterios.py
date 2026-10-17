"""Regressões dos critérios oficiais de classificação (criterios.py)."""

import pandas as pd
import pytest

from components.criterios import (
    TERMO_GPON_HABILIDADE,
    TERMO_MIGRACAO_OS,
    TERMO_PME_HABILIDADE,
    VAZIOS_CONTRATO,
    classificar_tipo_servico,
    detectar_col_habilidade,
    detectar_col_tipo_os_1,
    extrair_metricas_criterios,
)


def base_exemplo() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "CONTRATO": ["1", "2", "3", "4", "5", "6", "7", "8"],
            "TIPO O.S 1": [
                "ADESAO",                       # ND
                "INSTALACAO",                   # ND (termo novo)
                "ADESÃO",                       # ND com acento
                "MUDANCA DE PACOTE",            # Migração (habilidade PON)
                "MUDANCA DE PACOTE",            # sem PON → Outros
                "ADESAO",                       # PME (habilidade PME)
                "REPARO",                       # Outros
                None,                           # vazio → Outros
            ],
            "HABILIDADE DE TRABALHO": [
                "HFC(1/100)",
                "HFC(1/100)",
                "HFC(1/100)",
                "GPON(1/100)",
                "HFC(1/100)",
                "PME(1/100)",
                "HFC(1/100)",
                "HFC(1/100)",
            ],
            "TOTAL DE TAREFAS": [1, 2, 3, 4, 5, 6, 7, 8],
        }
    )


def test_criterios_migracao_usam_habilidade_com_pon():
    # A regra oficial deixou de usar FLAG_GPON e passou a olhar a habilidade.
    assert TERMO_MIGRACAO_OS.upper() == "MUDANCA DE PACOTE"
    assert TERMO_GPON_HABILIDADE == "PON"
    assert TERMO_PME_HABILIDADE == "PME"


def test_vazios_de_contrato_seguem_a_regra_oficial():
    assert VAZIOS_CONTRATO == {"", "NULL", "NAN", "NONE"}


def test_classificacao_por_segmento():
    df, tipo = classificar_tipo_servico(base_exemplo())

    assert tipo.tolist() == [
        "Novos Domicílios",
        "Novos Domicílios",
        "Novos Domicílios",
        "Migração",
        "Outros",
        "PME",
        "Outros",
        "Outros",
    ]
    assert df["TIPO_SERVICO"].tolist() == tipo.tolist()


def test_migracao_exige_mudanca_de_pacote_e_habilidade_pon():
    df = pd.DataFrame(
        {
            "TIPO O.S 1": ["MUDANCA DE PACOTE", "MUDANCA DE PACOTE", "MUDANCA DE PACOTE"],
            "HABILIDADE DE TRABALHO": ["PON(1/100)", "GPON(1/100)", "HFC(1/100)"],
        }
    )
    _, tipo = classificar_tipo_servico(df)
    assert tipo.tolist() == ["Migração", "Migração", "Outros"]


def test_pme_sobrepoe_novos_domicilios():
    df = pd.DataFrame(
        {
            "TIPO O.S 1": ["ADESAO", "ADESAO"],
            "HABILIDADE DE TRABALHO": ["PME(1/100)", "HFC(1/100)"],
        }
    )
    _, tipo = classificar_tipo_servico(df)
    assert tipo.tolist() == ["PME", "Novos Domicílios"]


def test_flag_gpon_e_derivada_da_habilidade():
    df, tipo = classificar_tipo_servico(base_exemplo())
    # "GPON(1/100)" e "PON(1/100)" contêm PON; "HFC"/"PME" não.
    assert df["FLAG_GPON"].tolist() == [
        "Não", "Não", "Não", "Sim", "Não", "Não", "Não", "Não",
    ]


def test_metricas_trazem_os_criterios_oficiais_e_os_alias():
    df, _ = classificar_tipo_servico(base_exemplo())
    metricas = extrair_metricas_criterios(df)

    # Critérios oficiais
    assert metricas["criterio_adesao"] == 1 + 2 + 3 + 6          # ND (inclui PME)
    assert metricas["criterio_mudanca_pacote"] == 4 + 5
    assert metricas["criterio_habilidade_pon"] == 4
    assert metricas["criterio_and_migracao"] == 4
    assert metricas["criterio_habilidade_pme"] == 6
    assert metricas["criterio_and_pme"] == 6

    # Classificação final (soma de TOTAL DE TAREFAS)
    assert metricas["migracao"] == 4
    assert metricas["novos_domicilios"] == 1 + 2 + 3
    assert metricas["pme"] == 6
    assert metricas["outros"] == 5 + 7 + 8

    # Alias de compatibilidade com painéis antigos
    assert metricas["criterio_pacote"] == metricas["criterio_mudanca_pacote"]
    assert metricas["criterio_nd_adesao"] == metricas["criterio_adesao"]
    assert metricas["total"] == sum(range(1, 9))
    assert metricas["total_registros"] == 8


@pytest.mark.parametrize(
    "coluna", ["TIPO O.S 1", "TIPO OS 1", "tipo_os_1", "TIPO O.S. 1"]
)
def test_deteccao_da_coluna_tipo_os_1(coluna):
    df = pd.DataFrame({coluna: ["ADESAO"], "HABILIDADE DE TRABALHO": ["HFC"]})
    assert detectar_col_tipo_os_1(df) == coluna


def test_deteccao_da_coluna_de_habilidade():
    df = pd.DataFrame({"TIPO O.S 1": ["ADESAO"], "HABILIDADES": ["HFC(1/100)"]})
    assert detectar_col_habilidade(df) == "HABILIDADES"


def test_base_sem_colunas_de_criterio_nao_quebra():
    df = pd.DataFrame({"CONTRATO": ["1", "2"]})
    classificado, tipo = classificar_tipo_servico(df)
    assert tipo.tolist() == ["Outros", "Outros"]
    assert classificado["FLAG_GPON"].tolist() == ["Não", "Não"]
    assert extrair_metricas_criterios(classificado)["total_registros"] == 2
