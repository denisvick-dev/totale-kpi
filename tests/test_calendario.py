"""Regressões do calendário operacional (Seg–Sáb, sem domingos nem feriados)."""

from datetime import date

import pytest

from components.calendario import (
    InfoCalendario,
    calcular_pascoa,
    carregar_feriados,
    contar_dias_uteis,
    dias_uteis_mes,
    eh_dia_util,
    fator_projecao,
    feriados_entre,
    projetar_por_ritmo,
)


def test_pascoa_em_anos_conhecidos():
    assert calcular_pascoa(2025) == date(2025, 4, 20)
    assert calcular_pascoa(2026) == date(2026, 4, 5)
    assert calcular_pascoa(2027) == date(2027, 3, 28)


@pytest.mark.parametrize(
    "dia, esperado",
    [
        (date(2026, 10, 12), False),  # segunda, feriado de N. S. Aparecida
        (date(2026, 10, 13), True),   # terça
        (date(2026, 10, 17), True),   # sábado conta
        (date(2026, 10, 18), False),  # domingo nunca conta
        (date(2026, 7, 9), False),    # feriado estadual de SP
        (date(2026, 12, 25), False),  # Natal
    ],
)
def test_dia_util_respeita_domingo_e_feriado(dia, esperado):
    assert eh_dia_util(dia) is esperado


def test_feriados_nacionais_e_estaduais_de_sp():
    feriados = carregar_feriados(2026)

    assert date(2026, 1, 1) in feriados          # Confraternização
    assert date(2026, 4, 21) in feriados         # Tiradentes
    assert date(2026, 9, 7) in feriados          # Independência
    assert date(2026, 10, 12) in feriados        # Aparecida
    assert date(2026, 11, 20) in feriados        # Consciência Negra
    assert date(2026, 7, 9) in feriados          # Revolução Constitucionalista (SP)
    assert date(2026, 2, 16) in feriados         # Carnaval
    assert date(2026, 4, 3) in feriados          # Paixão de Cristo
    assert date(2026, 6, 4) in feriados          # Corpus Christi


def test_contagem_semanal_desconta_feriado_e_domingo():
    # 12/10 (feriado) até 18/10 (domingo): só terça, quarta, quinta, sexta e sábado.
    assert contar_dias_uteis(date(2026, 10, 12), date(2026, 10, 18)) == 5


def test_dias_uteis_do_mes_referencia():
    assert dias_uteis_mes(2026, 10) == 26  # 31 dias − 4 domingos − 1 feriado
    assert dias_uteis_mes(2026, 11) == 23  # 5 domingos + Finados + Consciência Negra
    assert dias_uteis_mes(2026, 7) == 26   # 4 domingos + 09/07 (SP)


def test_info_calendario_faz_o_fechamento_bater():
    calendario = InfoCalendario.calcular(date(2026, 10, 17))

    assert calendario.total_dias_uteis == 26
    assert calendario.dias_passados == 14
    assert calendario.dias_faltantes == 12
    assert calendario.total_dias_uteis == (
        calendario.dias_passados + calendario.dias_faltantes
    )
    assert calendario.nome_mes == "Outubro/2026"
    assert [d for d, _ in calendario.feriados_no_mes] == [date(2026, 10, 12)]


def test_info_calendario_no_fim_do_mes_nao_fica_negativo():
    calendario = InfoCalendario.calcular(date(2026, 10, 31))
    assert calendario.dias_faltantes == 0
    assert calendario.feriados_restantes == ()


def test_feriados_entre_ignora_os_de_domingo():
    # 15/11/2026 cai no domingo: não pode aparecer como feriado a descontar.
    assert feriados_entre(date(2026, 11, 1), date(2026, 11, 30)) == [
        date(2026, 11, 2),
        date(2026, 11, 20),
    ]


def test_projecao_por_ritmo_e_fator():
    media, projecao = projetar_por_ritmo(120, 12, 14)
    assert media == 10.0
    assert projecao == pytest.approx(260.0)

    assert fator_projecao(26, 12) == pytest.approx(26 / 12)
    assert fator_projecao(26, 0) == 1.0
    assert fator_projecao(10, 10) == 1.0


def test_feriados_extras_por_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv("TOTALE_FERIADOS_EXTRA", "2026-10-16, 2026-10-30")
    feriados = carregar_feriados(2026)

    assert date(2026, 10, 16) in feriados
    assert date(2026, 10, 30) in feriados
    assert eh_dia_util(date(2026, 10, 16)) is False  # sexta pós-feriado extra
