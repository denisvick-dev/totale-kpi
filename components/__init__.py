"""
components/__init__.py
======================
Pacote de componentes reutilizáveis do portal TOTALE.
"""

from components.aderencia import (
    calcular_aderencia,
    classificar_aderencia,
)
from components.calendario import (
    InfoCalendario,
    carregar_feriados,
    contar_dias_uteis,
    dias_uteis_mes,
    eh_dia_util,
    fator_projecao,
    projetar_por_ritmo,
)

__all__ = [
    # Aderência à projeção (Produtividade)
    "calcular_aderencia",
    "classificar_aderencia",
    # Calendário
    "InfoCalendario",
    "carregar_feriados",
    "contar_dias_uteis",
    "dias_uteis_mes",
    "eh_dia_util",
    "fator_projecao",
    "projetar_por_ritmo",
]
