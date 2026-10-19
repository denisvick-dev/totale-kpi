"""
components/aderencia.py
=======================
Aderência à projeção de fechamento, por grupo (monitor, projeto ou
monitor × projeto) — cálculo puro usados pela aba **🎯 Aderência à
Projeção** do painel de Produtividade (``pages/pontos.py``).

A entrada é o ranking **por equipe** já calculado pela página
(colunas de grupo + ``Nome Equipe`` + ``Pontos`` + ``Projeção`` de
fechamento pelo ritmo, em dias úteis Seg–Sáb sem feriados). Para
cada grupo:

- **Meta do grupo** = meta mensal por equipe × nº de equipes do grupo;
- **Aderência projetada** = projeção de fechamento do grupo ÷ meta
  do grupo — acima de 100%, o grupo fecha o mês na meta se mantiver
  o ritmo atual;
- **Equipes aderentes** = equipes cuja projeção individual já atinge
  a meta por equipe (a projeção é somada por equipe dentro do grupo
  antes da comparação, pois o ranking pode ter uma linha por
  equipe × projeto);
- **Gap p/ Meta** = meta do grupo − projeção (negativo = folga);
- **Ritmo atual / necessário** em pontos por equipe por dia útil —
  o necessário é o ritmo médio, nos dias restantes, para fechar
  exatamente na meta.

As faixas de situação seguem a legenda do próprio painel
(300/350/375/400 pts): a partir de 4/3 da meta é "Alta performance"
(400 sobre a meta-base de 300), de 90% é "Próximo da meta"
(≈275 sobre 300).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd

#: Faixas relativas à meta escolhida (razão projeção ÷ meta).
FAIXA_ALTA_PERFORMANCE = 4 / 3
FAIXA_PROXIMO_META = 0.90

COL_EQUIPE = "Nome Equipe"
COL_PONTOS = "Pontos"
COL_PROJECAO = "Projeção"

COLUNAS_SAIDA_EXTRA: tuple[str, ...] = (
    "Equipes",
    "Pontos",
    "Projeção",
    "Meta Grupo",
    "Aderência Projetada",
    "Equipes Aderentes",
    "% Equipes Aderentes",
    "Gap p/ Meta",
    "Ritmo Atual",
    "Ritmo Necessário",
    "Situação",
)


def classificar_aderencia(razao: float) -> str:
    """Situação do grupo a partir da razão projeção ÷ meta."""
    if razao is None or (isinstance(razao, float) and np.isnan(razao)):
        return "Sem dados"
    if razao >= FAIXA_ALTA_PERFORMANCE:
        return "Alta performance"
    if razao >= 1.0:
        return "Na meta"
    if razao >= FAIXA_PROXIMO_META:
        return "Próximo da meta"
    return "Abaixo da meta"


def calcular_aderencia(
    df_equipes: pd.DataFrame,
    colunas_grupo: str | Sequence[str],
    meta_por_equipe: float,
    *,
    dias_passados: int,
    dias_restantes: int,
) -> pd.DataFrame:
    """
    Aderência projetada por grupo a partir do ranking por equipe.

    Retorna um DataFrame ordenado da maior para a menor aderência,
    com as colunas do grupo seguidas de :data:`COLUNAS_SAIDA_EXTRA`.
    Entrada vazia ou sem as colunas necessárias devolve um DataFrame
    vazio já com essas colunas (a página decide a mensagem).
    """
    grupos = [colunas_grupo] if isinstance(colunas_grupo, str) else list(colunas_grupo)
    colunas_saida = grupos + list(COLUNAS_SAIDA_EXTRA)

    necessarias = grupos + [COL_EQUIPE, COL_PONTOS, COL_PROJECAO]
    if (
        df_equipes is None
        or df_equipes.empty
        or meta_por_equipe <= 0
        or not set(necessarias).issubset(df_equipes.columns)
    ):
        return pd.DataFrame(columns=colunas_saida)

    df = df_equipes.copy()
    df[COL_PONTOS] = pd.to_numeric(df[COL_PONTOS], errors="coerce").fillna(0.0)
    df[COL_PROJECAO] = pd.to_numeric(df[COL_PROJECAO], errors="coerce").fillna(0.0)
    for col in grupos + [COL_EQUIPE]:
        df[col] = df[col].fillna("—").astype(str)

    # Totais e n° de equipes (únicas) por grupo.
    resumo = (
        df.groupby(grupos)
        .agg(
            Equipes=(COL_EQUIPE, "nunique"),
            Pontos=(COL_PONTOS, "sum"),
            Projeção=(COL_PROJECAO, "sum"),
        )
        .reset_index()
    )

    # Equipes aderentes: projeção somada por equipe dentro do grupo.
    por_equipe = (
        df.groupby(grupos + [COL_EQUIPE])[COL_PROJECAO].sum().rename("_proj_equipe")
    )
    aderentes = (
        (por_equipe >= meta_por_equipe).groupby(level=grupos).sum().rename("_ader")
    )
    resumo = resumo.merge(aderentes.reset_index(), on=grupos, how="left")
    resumo = resumo.rename(columns={"_ader": "Equipes Aderentes"})
    resumo["Equipes Aderentes"] = resumo["Equipes Aderentes"].fillna(0).astype(int)
    resumo["Equipes"] = resumo["Equipes"].astype(int)

    resumo["Meta Grupo"] = resumo["Equipes"] * float(meta_por_equipe)
    resumo["Aderência Projetada"] = np.where(
        resumo["Meta Grupo"] > 0,
        resumo["Projeção"] / resumo["Meta Grupo"],
        np.nan,
    )
    resumo["% Equipes Aderentes"] = np.where(
        resumo["Equipes"] > 0,
        resumo["Equipes Aderentes"] / resumo["Equipes"],
        np.nan,
    )
    resumo["Gap p/ Meta"] = resumo["Meta Grupo"] - resumo["Projeção"]

    base_passados = max(1, int(dias_passados))
    resumo["Ritmo Atual"] = (
        resumo["Pontos"] / base_passados / resumo["Equipes"].replace(0, np.nan)
    )
    if dias_restantes > 0:
        faltante = (resumo["Meta Grupo"] - resumo["Pontos"]).clip(lower=0)
        resumo["Ritmo Necessário"] = (
            faltante / int(dias_restantes) / resumo["Equipes"].replace(0, np.nan)
        )
    else:
        resumo["Ritmo Necessário"] = 0.0

    resumo["Situação"] = resumo["Aderência Projetada"].map(classificar_aderencia)

    return (
        resumo[colunas_saida]
        .sort_values("Aderência Projetada", ascending=False)
        .reset_index(drop=True)
    )


__all__ = [
    "COLUNAS_SAIDA_EXTRA",
    "FAIXA_ALTA_PERFORMANCE",
    "FAIXA_PROXIMO_META",
    "calcular_aderencia",
    "classificar_aderencia",
]
