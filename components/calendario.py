"""
components/calendario.py
========================
Calendário operacional TOTALE.

Regra oficial de projeção:
    ▸ A semana útil vai de **segunda-feira a sábado** (domingo NÃO conta).
    ▸ **Feriados** também são descontados (nacionais + estaduais de SP).

Todas as páginas que projetam volume fim de mês devem usar este módulo,
para que qtde_os, pontos, consultivo e demais painéis falem a mesma língua.

Exemplos
--------
>>> from datetime import date
>>> from components.calendario import InfoCalendario, dias_uteis_mes
>>> cal = InfoCalendario.calcular(date(2026, 10, 17))
>>> cal.total_dias_uteis == dias_uteis_mes(2026, 10)
True
>>> cal.dias_passados > 0 and cal.dias_faltantes >= 0
True
"""

from __future__ import annotations

import calendar
import json
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Union

TipoData = Union[date, datetime, str]

# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════════
#: Segunda a sábado trabalham, domingo não (formato de weekmask do numpy).
WEEKMASK_SEG_SAB: str = "1111110"

#: weekday() do Python: 0 = segunda ... 6 = domingo.
DIAS_UTEIS_SEMANA: tuple[int, ...] = (0, 1, 2, 3, 4, 5)

#: UF usada para os feriados estaduais.
UF_PADRAO: str = "SP"

#: Arquivo opcional com feriados extras (``{"2026-07-10": "Feriado municipal"}``
#: ou ``["2026-07-10", ...]``).
ARQUIVO_FERIADOS_EXTRA: Path = Path("config/feriados_extra.json")

#: Variável de ambiente com feriados extras separados por vírgula.
ENV_FERIADOS_EXTRA: str = "TOTALE_FERIADOS_EXTRA"

# ═══════════════════════════════════════════════════════════════════════
# FERIADOS FIXOS
# ═══════════════════════════════════════════════════════════════════════
FERIADOS_FIXOS_NACIONAIS: dict[tuple[int, int], str] = {
    (1, 1): "Confraternização Universal",
    (4, 21): "Tiradentes",
    (5, 1): "Dia do Trabalho",
    (9, 7): "Independência do Brasil",
    (10, 12): "Nossa Senhora Aparecida",
    (11, 2): "Finados",
    (11, 15): "Proclamação da República",
    (11, 20): "Dia Nacional de Zumbi e da Consciência Negra",
    (12, 25): "Natal",
}

FERIADOS_FIXOS_ESTADUAIS: dict[str, dict[tuple[int, int], str]] = {
    "SP": {
        (7, 9): "Revolução Constitucionalista de 1932 (SP)",
    },
    "RJ": {
        (4, 23): "Dia de São Jorge (RJ)",
        (11, 20): "Dia da Consciência Negra (RJ)",
    },
    "MG": {
        (4, 21): "Tiradentes (MG)",
    },
}

#: Pontos facultativos NÃO entram na contagem por padrão (são dias trabalhados).
PONTOS_FACULTATIVOS_NACIONAIS: dict[tuple[int, int], str] = {
    (2, 13): "Carnaval (terça-feira)",
    (10, 28): "Dia do Servidor Público",
    (12, 24): "Véspera de Natal",
    (12, 31): "Véspera de Ano Novo",
}


# ═══════════════════════════════════════════════════════════════════════
# CONVERSÃO E FERIADOS MÓVEIS
# ═══════════════════════════════════════════════════════════════════════
def para_data(valor: TipoData) -> date:
    """Converte ``date``, ``datetime`` ou ``YYYY-MM-DD`` em :class:`date`."""
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return datetime.strptime(str(valor).strip()[:10], "%Y-%m-%d").date()


def calcular_pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano)."""
    a = ano % 19
    b, c = divmod(ano, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    ajuste_dia_semana = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * ajuste_dia_semana) // 451
    mes, dia = divmod(h + ajuste_dia_semana - 7 * m + 114, 31)
    return date(ano, mes, dia + 1)


def feriados_moveis(ano: int) -> dict[date, str]:
    """Feriados móveis (Carnaval, Paixão de Cristo e Corpus Christi)."""
    pascoa = calcular_pascoa(ano)
    return {
        pascoa - timedelta(days=48): "Carnaval",
        pascoa - timedelta(days=2): "Paixão de Cristo",
        pascoa + timedelta(days=60): "Corpus Christi",
    }


# ═══════════════════════════════════════════════════════════════════════
# CARGA DOS FERIADOS
# ═══════════════════════════════════════════════════════════════════════
def _ler_arquivo_extras(caminho: Path = ARQUIVO_FERIADOS_EXTRA) -> dict[date, str]:
    try:
        if not caminho.exists():
            return {}
        conteudo = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

    extras: dict[date, str] = {}
    if isinstance(conteudo, Mapping):
        for chave, nome in conteudo.items():
            if str(chave).startswith("_"):  # chaves de documentação
                continue
            try:
                extras[para_data(chave)] = str(nome) or "Feriado extra"
            except ValueError:
                continue
    elif isinstance(conteudo, (list, tuple)):
        for item in conteudo:
            if isinstance(item, Mapping):
                extras[para_data(item.get("data"))] = str(
                    item.get("nome", "Feriado extra")
                )
            else:
                extras[para_data(item)] = "Feriado extra"
    return extras


def _ler_env_extras() -> dict[date, str]:
    bruto = os.getenv(ENV_FERIADOS_EXTRA, "")
    extras: dict[date, str] = {}
    for pedaco in bruto.split(","):
        pedaco = pedaco.strip()
        if not pedaco:
            continue
        try:
            extras[para_data(pedaco.split(":", 1)[0])] = "Feriado extra"
        except ValueError:
            continue
    return extras


def _ler_secrets_extras() -> dict[date, str]:
    """Feriados extras vindos de ``.streamlit/secrets.toml`` (``[calendario]``)."""
    try:
        import streamlit as st  # import local: o módulo também roda sem Streamlit

        secao = st.secrets.get("calendario", {})
    except Exception:
        return {}

    bruto = None
    try:
        bruto = secao.get("feriados_extra", None)
    except AttributeError:
        return {}

    extras: dict[date, str] = {}
    if isinstance(bruto, Mapping):
        for chave, nome in bruto.items():
            try:
                extras[para_data(chave)] = str(nome)
            except ValueError:
                continue
    elif isinstance(bruto, (list, tuple)):
        for item in bruto:
            try:
                extras[para_data(item)] = "Feriado extra"
            except ValueError:
                continue
    return extras


@lru_cache(maxsize=64)
def feriados_do_ano(ano: int, uf: str = UF_PADRAO) -> dict[date, str]:
    """Feriados nacionais + estaduais + móveis de um ano (sem os extras)."""
    feriados: dict[date, str] = {
        date(ano, mes, dia): nome
        for (mes, dia), nome in FERIADOS_FIXOS_NACIONAIS.items()
    }
    for (mes, dia), nome in FERIADOS_FIXOS_ESTADUAIS.get(uf.upper(), {}).items():
        feriados.setdefault(date(ano, mes, dia), nome)
    feriados.update(feriados_moveis(ano))
    return feriados


def feriados_extras() -> dict[date, str]:
    """Feriados extras (arquivo JSON, secrets e variável de ambiente)."""
    extras: dict[date, str] = {}
    extras.update(_ler_arquivo_extras())
    extras.update(_ler_secrets_extras())
    extras.update(_ler_env_extras())
    return extras


def carregar_feriados(ano: int | None = None, uf: str = UF_PADRAO) -> dict[date, str]:
    """Todos os feriados considerados: fixos, móveis, estaduais e extras."""
    feriados = dict(feriados_do_ano(int(ano) if ano else date.today().year, uf))
    for dia, nome in feriados_extras().items():
        if ano is None or dia.year == ano:
            feriados.setdefault(dia, nome)
    return feriados


# ═══════════════════════════════════════════════════════════════════════
# CONTAGEM DE DIAS ÚTEIS (SEG–SÁB, SEM FERIADOS)
# ═══════════════════════════════════════════════════════════════════════
def eh_dia_util(dia: TipoData, feriados: Iterable[date] | None = None) -> bool:
    """Segunda a sábado, desde que não seja feriado."""
    data = para_data(dia)
    if data.weekday() not in DIAS_UTEIS_SEMANA:
        return False
    if feriados is None:
        feriados = carregar_feriados(data.year)
    return data not in set(feriados)


def listar_dias_uteis(
    inicio: TipoData, fim: TipoData, feriados: Iterable[date] | None = None
) -> list[date]:
    """Dias úteis no intervalo **[início, fim]** (fim incluído)."""
    di, df_ = para_data(inicio), para_data(fim)
    if di > df_:
        return []
    if feriados is None:
        feriados = carregar_feriados(di.year) | carregar_feriados(df_.year)
    return [d for d in _intervalo(di, df_) if eh_dia_util(d, feriados)]


def _intervalo(inicio: date, fim: date) -> Iterable[date]:
    for n in range((fim - inicio).days + 1):
        yield inicio + timedelta(days=n)


def contar_dias_uteis(
    inicio: TipoData, fim: TipoData, feriados: Iterable[date] | None = None
) -> int:
    """Quantidade de dias úteis (Seg–Sáb, sem feriados) em **[início, fim]**."""
    return len(listar_dias_uteis(inicio, fim, feriados))


def feriados_entre(
    inicio: TipoData, fim: TipoData, feriados: Mapping[date, str] | None = None
) -> list[date]:
    """Feriados (Seg–Sáb) que caem dentro de **[início, fim]**."""
    di, df_ = para_data(inicio), para_data(fim)
    if di > df_:
        return []
    if feriados is None:
        feriados = carregar_feriados(di.year)
        if df_.year != di.year:
            feriados = {**feriados, **carregar_feriados(df_.year)}
    return sorted(
        d for d in feriados if di <= d <= df_ and d.weekday() in DIAS_UTEIS_SEMANA
    )


def dias_uteis_mes(ano: int, mes: int, feriados: Iterable[date] | None = None) -> int:
    """Dias úteis totais do mês (Seg–Sáb, sem domingos nem feriados)."""
    _, ultimo = calendar.monthrange(ano, mes)
    return contar_dias_uteis(date(ano, mes, 1), date(ano, mes, ultimo), feriados)


# ═══════════════════════════════════════════════════════════════════════
# CALENDÁRIO DO MÊS DE REFERÊNCIA
# ═══════════════════════════════════════════════════════════════════════
@dataclass(frozen=True)
class InfoCalendario:
    """
    Dias úteis do mês de referência (Seg–Sáb, sem feriados).

    ``dias_passados`` conta o dia de referência (hoje já trabalha).
    ``dias_faltantes`` são os dias úteis depois dele.
    """

    ano: int
    mes: int
    data_referencia: date
    total_dias_uteis: int
    dias_passados: int
    dias_faltantes: int
    feriados_no_mes: tuple[tuple[date, str], ...] = field(default_factory=tuple)

    @property
    def feriados_restantes(self) -> tuple[tuple[date, str], ...]:
        return tuple(
            (d, n) for d, n in self.feriados_no_mes if d > self.data_referencia
        )

    @property
    def nome_mes(self) -> str:
        meses = [
            "Janeiro",
            "Fevereiro",
            "Março",
            "Abril",
            "Maio",
            "Junho",
            "Julho",
            "Agosto",
            "Setembro",
            "Outubro",
            "Novembro",
            "Dezembro",
        ]
        return f"{meses[self.mes - 1]}/{self.ano}"

    @classmethod
    def calcular(
        cls,
        data_referencia: TipoData | None = None,
        uf: str = UF_PADRAO,
        feriados: Mapping[date, str] | None = None,
    ) -> InfoCalendario:
        ref = para_data(data_referencia) if data_referencia else date.today()
        ano, mes = ref.year, ref.month
        _, ultimo_dia = calendar.monthrange(ano, mes)
        primeiro, ultimo = date(ano, mes, 1), date(ano, mes, ultimo_dia)

        if feriados is None:
            feriados = carregar_feriados(ano, uf)

        total = contar_dias_uteis(primeiro, ultimo, feriados)
        passados = contar_dias_uteis(primeiro, ref, feriados)
        faltantes = max(0, total - passados)

        feriados_mes = tuple(
            sorted(
                (d, n)
                for d, n in feriados.items()
                if primeiro <= d <= ultimo and d.weekday() in DIAS_UTEIS_SEMANA
            )
        )

        return cls(
            ano=ano,
            mes=mes,
            data_referencia=ref,
            total_dias_uteis=total,
            dias_passados=passados,
            dias_faltantes=faltantes,
            feriados_no_mes=feriados_mes,
        )


# ═══════════════════════════════════════════════════════════════════════
# PROJEÇÕES
# ═══════════════════════════════════════════════════════════════════════
def projetar_por_ritmo(
    realizado: float,
    dias_passados: int,
    dias_faltantes: int,
) -> tuple[float, float]:
    """
    Projeção de fim de mês pelo ritmo diário em dias úteis (Seg–Sáb, sem feriados).

    Retorna ``(media_diaria, projecao)``.
    """
    base = max(0, int(dias_passados))
    media = float(realizado) / base if base > 0 else 0.0
    return media, float(realizado) + media * max(0, int(dias_faltantes))


def fator_projecao(total_dias_uteis: int, dias_decorridos: int) -> float:
    """Fator multiplicativo ``total / decorrido`` (usado em consultivos)."""
    if dias_decorridos <= 0 or total_dias_uteis <= dias_decorridos:
        return 1.0
    return float(total_dias_uteis) / float(dias_decorridos)


__all__ = [
    "ARQUIVO_FERIADOS_EXTRA",
    "DIAS_UTEIS_SEMANA",
    "ENV_FERIADOS_EXTRA",
    "FERIADOS_FIXOS_ESTADUAIS",
    "FERIADOS_FIXOS_NACIONAIS",
    "PONTOS_FACULTATIVOS_NACIONAIS",
    "UF_PADRAO",
    "WEEKMASK_SEG_SAB",
    "InfoCalendario",
    "calcular_pascoa",
    "carregar_feriados",
    "contar_dias_uteis",
    "dias_uteis_mes",
    "eh_dia_util",
    "fator_projecao",
    "feriados_do_ano",
    "feriados_entre",
    "feriados_extras",
    "feriados_moveis",
    "listar_dias_uteis",
    "para_data",
    "projetar_por_ritmo",
]
