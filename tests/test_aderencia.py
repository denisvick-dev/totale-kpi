"""Testes da aderência à projeção (``components/aderencia``)."""

from __future__ import annotations

import pandas as pd
import pytest

from components.aderencia import calcular_aderencia, classificar_aderencia

RANKING = pd.DataFrame(
    {
        "Supervisor": ["Mon A", "Mon A", "Mon B", "Mon B", "Mon B"],
        "Projeto": ["P1", "P2", "P1", "P1", "P2"],
        # Eq1 aparece em dois projetos do mesmo monitor.
        "Nome Equipe": ["Eq1", "Eq1", "Eq2", "Eq3", "Eq3"],
        "Pontos": [200.0, 100.0, 150.0, 100.0, 50.0],
        "Projeção": [250.0, 100.0, 290.0, 200.0, 80.0],
    }
)


def test_aderencia_por_monitor():
    saida = calcular_aderencia(
        RANKING, "Supervisor", 300, dias_passados=10, dias_restantes=10
    )

    # Ordenado da maior para a menor aderência.
    mon_a, mon_b = saida.iloc[0], saida.iloc[1]
    assert mon_a["Supervisor"] == "Mon A"
    # Eq1 em dois projetos conta uma vez; projeção 250+100=350 ≥ 300.
    assert mon_a["Equipes"] == 1
    assert mon_a["Equipes Aderentes"] == 1
    assert mon_a["Meta Grupo"] == 300
    assert mon_a["Aderência Projetada"] == pytest.approx(350 / 300)
    assert mon_a["Situação"] == "Na meta"

    # Mon B: 2 equipes, projeção 290+200+80=570 sobre meta 600 (95%).
    assert mon_b["Equipes"] == 2
    assert mon_b["Equipes Aderentes"] == 0  # Eq2 projeta 290; Eq3, 280
    assert mon_b["% Equipes Aderentes"] == 0
    assert mon_b["Aderência Projetada"] == pytest.approx(570 / 600)
    assert mon_b["Gap p/ Meta"] == 30
    assert mon_b["Situação"] == "Próximo da meta"
    # Faltam (600-300) pts em 10 dias para 2 equipes = 15 pts/equipe/dia.
    assert mon_b["Ritmo Necessário"] == pytest.approx(15.0)
    assert mon_b["Ritmo Atual"] == pytest.approx(300 / 10 / 2)


def test_aderencia_por_projeto_e_combinada():
    por_projeto = calcular_aderencia(
        RANKING, "Projeto", 300, dias_passados=10, dias_restantes=5
    )
    p1 = por_projeto.set_index("Projeto").loc["P1"]
    assert p1["Equipes"] == 3  # Eq1, Eq2, Eq3 atuam em P1
    assert p1["Pontos"] == 450

    combinada = calcular_aderencia(
        RANKING,
        ["Supervisor", "Projeto"],
        400,
        dias_passados=10,
        dias_restantes=0,
    )
    assert list(combinada.columns[:2]) == ["Supervisor", "Projeto"]
    assert len(combinada) == 4
    # Sem dias restantes, o ritmo necessário é zero (não há mais tempo).
    assert (combinada["Ritmo Necessário"] == 0).all()


def test_entrada_vazia_ou_invalida():
    assert calcular_aderencia(
        pd.DataFrame(), "Supervisor", 300, dias_passados=1, dias_restantes=1
    ).empty
    sem_projecao = RANKING.drop(columns=["Projeção"])
    assert calcular_aderencia(
        sem_projecao, "Supervisor", 300, dias_passados=1, dias_restantes=1
    ).empty
    assert calcular_aderencia(
        RANKING, "Supervisor", 0, dias_passados=1, dias_restantes=1
    ).empty


@pytest.mark.parametrize(
    ("razao", "esperado"),
    [
        (1.40, "Alta performance"),
        (1.00, "Na meta"),
        (0.95, "Próximo da meta"),
        (0.50, "Abaixo da meta"),
        (float("nan"), "Sem dados"),
    ],
)
def test_classificar_aderencia(razao, esperado):
    assert classificar_aderencia(razao) == esperado
