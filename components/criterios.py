"""
components/criterios.py
=======================
Módulo centralizado de critérios de classificação para o portal TOTALE.

CRITÉRIOS PRINCIPAIS:
    🔄 MIGRAÇÃO (AND — os 2 critérios juntos):
        1️⃣  TIPO O.S 1  contém  "MUDANCA DE PACOTE"
        2️⃣  FLAG_GPON   =       "Sim"

    🔦 FLAG_GPON (auto-gerado):
        HABILIDADE DE TRABALHO contém "PON(1/100)" → "Sim"

    🏠 NOVOS DOMICÍLIOS: TIPO O.S contém "ADESAO"
    🏢 PME: é Novos Domicílios E Capacidade contém "PME"

ARQUITETURA:
    ✅ Regras de classificação
    ✅ Detecção de colunas
    ✅ Métricas consolidadas
    ✅ Painéis internos de UI
"""

from __future__ import annotations

import unicodedata
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════
VAZIOS_GERAIS: set[str] = {
    "",
    "NAN",
    "NONE",
    "NULL",
    "N/A",
    "NA",
    "NAO INFORMADO",
    "NÃO INFORMADO",
    "-",
    "SEM INFORMACAO",
    "SEM INFORMAÇÃO",
    ".",
    "..",
    "...",
}
VAZIOS_CONTRATO: set[str] = VAZIOS_GERAIS | {
    "0",
    "S/N",
    "SEM CONTRATO",
    "?",
    "??",
}


def _norm_str(texto: str) -> str:
    return (
        unicodedata.normalize("NFKD", texto)
        .encode("ascii", errors="ignore")
        .decode("ascii")
        .upper()
        .strip()
    )


TERMO_MIGRACAO_OS: str = _norm_str("MUDANCA DE PACOTE")
VALOR_FLAG_GPON_SIM: str = "SIM"
TERMO_GPON_HABILIDADE: str = "PON(1/100)"

TERMOS_ND: Tuple[str, ...] = ("ADESAO",)
TERMOS_PME: Tuple[str, ...] = ("PME",)

CANDS_TIPO_OS_1: List[str] = [
    "TIPO O.S 1",
    "TIPO OS 1",
    "TIPO O.S. 1",
    "TIPO_OS_1",
    "TIPO_O_S_1",
]
CANDS_FLAG_GPON: List[str] = [
    "FLAG_GPON",
    "FLAG GPON",
    "FLAGGPON",
    "IS_GPON",
]
CANDS_CAPACIDADE: List[str] = [
    "CATEGORIAS DA CAPACIDADE",
    "CATEGORIA DA CAPACIDADE",
    "CATEGORIAS CAPACIDADE",
    "CATEGORIA CAPACIDADE",
    "CAPACIDADE",
]
CANDS_HABILIDADE: List[str] = [
    "HABILIDADE DE TRABALHO",
    "HABILIDADES DE TRABALHO",
    "HABILIDADE",
    "HABILIDADES",
    "SKILL",
    "SKILLS",
]


# ═══════════════════════════════════════════════════════════════════════
# NORMALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════
def normalizar_str(texto: str) -> str:
    return _norm_str(texto)


def norm_col_nome(nome: str) -> str:
    return (
        unicodedata.normalize("NFKD", nome)
        .encode("ascii", errors="ignore")
        .decode("ascii")
        .upper()
        .strip()
        .replace(".", "")
        .replace("_", " ")
    )


# ═══════════════════════════════════════════════════════════════════════
# DETECÇÃO DE COLUNAS
# ═══════════════════════════════════════════════════════════════════════
def detectar_cols_tipo(df: pd.DataFrame) -> List[str]:
    return [
        c
        for c in df.columns
        if "TIPO" in norm_col_nome(str(c))
        and ("OS" in norm_col_nome(str(c)) or "O S" in norm_col_nome(str(c)))
    ]


def detectar_col_tipo_os_1(df: pd.DataFrame) -> Optional[str]:
    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}
    for cand in CANDS_TIPO_OS_1:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for col_norm, col_real in cols_norm.items():
        if "TIPO" in col_norm and ("OS" in col_norm or "O S" in col_norm):
            if col_norm.endswith("1") or col_norm.endswith(" 1"):
                return col_real
    return None


def detectar_col_flag_gpon(df: pd.DataFrame) -> Optional[str]:
    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}
    for cand in CANDS_FLAG_GPON:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for col_norm, col_real in cols_norm.items():
        if "GPON" in col_norm and "FLAG" in col_norm:
            return col_real
    return None


def detectar_col_capacidade(df: pd.DataFrame) -> Optional[str]:
    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}
    for cand in CANDS_CAPACIDADE:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for col_norm, col_real in cols_norm.items():
        if "CAPACIDADE" in col_norm:
            return col_real
    return None


def detectar_col_habilidade(df: pd.DataFrame) -> Optional[str]:
    for nome in [
        "HABILIDADE DE TRABALHO",
        "Habilidade de Trabalho",
        "habilidade de trabalho",
        "HABILIDADES DE TRABALHO",
        "HABILIDADE_DE_TRABALHO",
        "HABILIDADE",
    ]:
        if nome in df.columns:
            return nome
    for c in df.columns:
        if str(c).strip().upper() == "HABILIDADE DE TRABALHO":
            return c
    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}
    for cand in CANDS_HABILIDADE:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for c in df.columns:
        if "HABIL" in str(c).upper():
            return c
    for c in df.columns:
        try:
            amostra = df[c].dropna().astype(str).head(100)
            if amostra.str.contains(r"PON\(1/100\)", na=False, regex=True).any():
                return c
        except Exception:
            continue
    return None


def detectar_col_status_atividade(df: pd.DataFrame) -> Optional[str]:
    for nome in [
        "STATUS DA ATIVIDADE",
        "Status da Atividade",
        "status da atividade",
        "STATUS_DA_ATIVIDADE",
    ]:
        if nome in df.columns:
            return nome
    for c in df.columns:
        if str(c).strip().upper() == "STATUS DA ATIVIDADE":
            return c
    alvo_norm = norm_col_nome("STATUS DA ATIVIDADE")
    for c in df.columns:
        if norm_col_nome(str(c)) == alvo_norm:
            return c
    for c in df.columns:
        cu = str(c).upper()
        if "STATUS" in cu and "ATIVIDADE" in cu:
            return c
    return None


def detectar_col_contrato(df: pd.DataFrame) -> Optional[str]:
    for nome in ["CONTRATO", "Contrato", "contrato"]:
        if nome in df.columns:
            return nome
    for c in df.columns:
        if str(c).strip().upper() == "CONTRATO":
            return c
    alvo_norm = norm_col_nome("CONTRATO")
    for c in df.columns:
        if norm_col_nome(str(c)) == alvo_norm:
            return c
    _EVITAR = {"STATUS", "DATA", "TIPO", "VALOR", "PLANO", "SITUACAO"}
    candidatas = [
        c
        for c in df.columns
        if "CONTRATO" in str(c).upper()
        and not any(e in str(c).upper() for e in _EVITAR)
    ]
    if candidatas:
        return min(candidatas, key=lambda x: len(str(x)))
    return None


# ═══════════════════════════════════════════════════════════════════════
# COLUNAS AUXILIARES
# ═══════════════════════════════════════════════════════════════════════
def criar_coluna_tipos_agrupados(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols_tipo = detectar_cols_tipo(df)

    if not cols_tipo:
        df["_TIPOS_OS_AGRUPADOS"] = ""
        df["_TIPOS_OS_SET"] = pd.Series(
            [frozenset() for _ in range(len(df))],
            index=df.index,
            dtype=object,
        )
        return df

    def _agrupar(row: pd.Series) -> Tuple[str, FrozenSet[str]]:
        raw, norm = set(), set()
        for col in cols_tipo:
            val = str(row.get(col, "")).strip()
            if not val or val.upper() in VAZIOS_GERAIS:
                continue
            vn = normalizar_str(val)
            if vn and vn not in VAZIOS_GERAIS:
                raw.add(val)
                norm.add(vn)
        return (" + ".join(sorted(raw)) if raw else ""), frozenset(norm)

    res = df[cols_tipo].apply(_agrupar, axis=1, result_type="expand")
    df["_TIPOS_OS_AGRUPADOS"] = res[0]
    df["_TIPOS_OS_SET"] = res[1]
    return df


def criar_flag_gpon(df: pd.DataFrame) -> Tuple[pd.DataFrame, Optional[str], int]:
    df = df.copy()

    col_ex = detectar_col_flag_gpon(df)
    if col_ex and col_ex != "FLAG_GPON":
        df = df.rename(columns={col_ex: "FLAG_GPON"})

    if "FLAG_GPON" in df.columns:
        n_sim = int(
            df["FLAG_GPON"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .eq(VALOR_FLAG_GPON_SIM)
            .sum()
        )
        return df, None, n_sim

    col_hab = detectar_col_habilidade(df)
    if not col_hab:
        df["FLAG_GPON"] = "Não"
        return df, None, 0

    serie = df[col_hab].fillna("").astype(str).str.strip()
    serie_v = serie.where(~serie.str.upper().isin(VAZIOS_GERAIS), other="")
    mask = serie_v.str.contains(TERMO_GPON_HABILIDADE, na=False, regex=False)
    df["FLAG_GPON"] = np.where(mask, "Sim", "Não")
    return df, col_hab, int(mask.sum())


# ═══════════════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════
def classificar_tipo_servico(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
    df = criar_coluna_tipos_agrupados(df)
    df, _, _ = criar_flag_gpon(df)

    col_tipo = detectar_col_tipo_os_1(df)
    col_gpon = detectar_col_flag_gpon(df)
    col_cap = detectar_col_capacidade(df)

    serie_tipo = (
        df[col_tipo].fillna("").astype(str).map(normalizar_str)
        if col_tipo
        else pd.Series("", index=df.index)
    )
    serie_gpon = (
        df[col_gpon].fillna("").astype(str).map(normalizar_str)
        if col_gpon
        else pd.Series("", index=df.index)
    )
    serie_cap = (
        df[col_cap].fillna("").astype(str).map(normalizar_str)
        if col_cap
        else pd.Series("", index=df.index)
    )

    flag_pac = serie_tipo.str.contains(TERMO_MIGRACAO_OS, na=False, regex=False)
    flag_gpn = serie_gpon == VALOR_FLAG_GPON_SIM
    flag_mig = flag_pac & flag_gpn

    def _tem_nd(t: FrozenSet[str]) -> bool:
        return any(termo in val for val in t for termo in TERMOS_ND)

    flag_nd = df["_TIPOS_OS_SET"].map(_tem_nd)
    flag_pme = flag_nd & serie_cap.str.contains("PME", na=False)

    resultado = pd.Series("Outros", index=df.index)
    resultado[flag_nd] = "Novos Domicílios"
    resultado[flag_pme] = "PME"
    resultado[flag_mig] = "Migração"

    return df, resultado


# ═══════════════════════════════════════════════════════════════════════
# MÉTRICAS OFICIAIS (BASEADAS EM TOTAL DE TAREFAS)
# ═══════════════════════════════════════════════════════════════════════
def extrair_metricas_criterios(df: pd.DataFrame) -> dict:
    """
    Extrai métricas usando TOTAL DE TAREFAS do DF já classificado.
    NÃO recalcula classificação.
    """
    if df.empty or "TIPO_SERVICO" not in df.columns:
        return {}

    # Garantir coluna numérica
    if "TOTAL DE TAREFAS" in df.columns:
        tarefas = pd.to_numeric(df["TOTAL DE TAREFAS"], errors="coerce").fillna(1)
    else:
        tarefas = pd.Series(1, index=df.index)

    total = int(tarefas.sum())

    metricas = {
        "total": total,
        "total_linhas": len(df),
        "migracao": int(tarefas[df["TIPO_SERVICO"] == "Migração"].sum()),
        "novos_domicilios": int(
            tarefas[df["TIPO_SERVICO"] == "Novos Domicílios"].sum()
        ),
        "pme": int(tarefas[df["TIPO_SERVICO"] == "PME"].sum()),
        "outros": int(tarefas[df["TIPO_SERVICO"] == "Outros"].sum()),
    }

    # Critérios individuais
    col_tipo = detectar_col_tipo_os_1(df)
    col_gpon = detectar_col_flag_gpon(df)
    col_hab = detectar_col_habilidade(df)

    if col_tipo:
        s = df[col_tipo].fillna("").astype(str).map(normalizar_str)
        mask = s.str.contains(TERMO_MIGRACAO_OS, na=False, regex=False)
        metricas["criterio_pacote"] = int(tarefas[mask].sum())
    else:
        metricas["criterio_pacote"] = 0

    if col_gpon:
        s = df[col_gpon].fillna("").astype(str).map(normalizar_str)
        mask = s == VALOR_FLAG_GPON_SIM
        metricas["criterio_gpon_sim"] = int(tarefas[mask].sum())
    else:
        metricas["criterio_gpon_sim"] = 0

    metricas["criterio_and_migracao"] = metricas["migracao"]

    if col_hab:
        s = df[col_hab].fillna("").astype(str).str.strip()
        sv = s.where(~s.str.upper().isin(VAZIOS_GERAIS), other="")
        mask = sv.str.contains(TERMO_GPON_HABILIDADE, na=False, regex=False)
        metricas["habilidade_pon"] = int(tarefas[mask].sum())
    else:
        metricas["habilidade_pon"] = 0

    return metricas


# ═══════════════════════════════════════════════════════════════════════
# PAINEL OFICIAL DE CRITÉRIOS (EM ABA — BASEADO EM TOTAL DE TAREFAS)
# ═══════════════════════════════════════════════════════════════════════
def render_painel_criterios(df: pd.DataFrame) -> None:
    """
    Painel oficial de critérios dentro de uma aba.
    Números = soma de TOTAL DE TAREFAS.
    """
    metricas = extrair_metricas_criterios(df)

    if not metricas:
        st.warning("⚠️ Base ainda não classificada.")
        return

    total = metricas["total"]
    total_linhas = metricas["total_linhas"]

    def pct(n: int) -> str:
        return f"{(n / total * 100):.1f}%" if total else "0%"

    def fmt(n: int) -> str:
        return f"{n:,}".replace(",", ".")

    # ── ABA ─────────────────────────────────────────────────────────
    tab_criterios, tab_detalhes = st.tabs(
        [
            "📊 Critérios de Classificação",
            "🔎 Detalhes dos Critérios",
        ]
    )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ABA 1 — PAINEL PRINCIPAL
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab_criterios:

        st.markdown(
            f'<div style="font-size:14px;color:#475569;margin-bottom:16px;">'
            f"📦 <b>{fmt(total)}</b> tarefas consolidadas "
            f"(<b>{fmt(total_linhas)}</b> registros)"
            f"</div>",
            unsafe_allow_html=True,
        )

        # ── Segmentos ────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)

        def _card(col, emoji, label, valor, cor_bg, cor_brd, cor_txt, cor_num):
            col.markdown(
                f'<div style="background:{cor_bg};border-left:4px solid {cor_brd};'
                f'padding:14px 16px;border-radius:8px;height:110px;">'
                f'<div style="font-size:11px;font-weight:700;color:{cor_txt};'
                f'text-transform:uppercase;letter-spacing:0.5px;">'
                f"{emoji} {label}</div>"
                f'<div style="font-size:28px;font-weight:800;color:{cor_num};'
                f'line-height:1.1;margin-top:4px;">{fmt(valor)}</div>'
                f'<div style="font-size:11px;color:#475569;margin-top:2px;">'
                f"{pct(valor)}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )

        _card(
            c1,
            "🔄",
            "MIGRAÇÃO (AND)",
            metricas["migracao"],
            "#EFF6FF",
            "#0369A1",
            "#0369A1",
            "#0C4A6E",
        )
        _card(
            c2,
            "🏠",
            "NOVOS DOMICÍLIOS",
            metricas["novos_domicilios"],
            "#F0FDF4",
            "#16A34A",
            "#15803D",
            "#14532D",
        )
        _card(
            c3, "🏢", "PME", metricas["pme"], "#FAF5FF", "#7C3AED", "#6D28D9", "#4C1D95"
        )
        _card(
            c4,
            "⚪",
            "OUTROS",
            metricas["outros"],
            "#F8FAFC",
            "#64748B",
            "#475569",
            "#334155",
        )

        # ── Critérios Individuais ──────────────────────────────────
        st.markdown(
            '<hr style="margin:20px 0;border:none;border-top:1px solid #E2E8F0;">'
            '<div style="font-size:13px;font-weight:700;color:#0F172A;margin-bottom:12px;">'
            "🔍 Critérios Individuais (Total de Tarefas)</div>",
            unsafe_allow_html=True,
        )

        d1, d2, d3, d4 = st.columns(4)

        def _card_sm(col, emoji, label, valor, cor_bg, cor_brd, cor_txt, cor_num):
            col.markdown(
                f'<div style="background:{cor_bg};padding:12px 14px;border-radius:8px;'
                f'border-left:3px solid {cor_brd};height:80px;">'
                f'<div style="font-size:11px;font-weight:700;color:{cor_txt};">'
                f"{emoji} {label}</div>"
                f'<div style="font-size:22px;font-weight:800;color:{cor_num};'
                f'line-height:1.1;margin-top:4px;">{fmt(valor)}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

        _card_sm(
            d1,
            "1️⃣",
            "MUDANCA DE PACOTE",
            metricas["criterio_pacote"],
            "#FEF3C7",
            "#F59E0B",
            "#92400E",
            "#78350F",
        )
        _card_sm(
            d2,
            "2️⃣",
            "FLAG_GPON = Sim",
            metricas["criterio_gpon_sim"],
            "#E0F2FE",
            "#0284C7",
            "#0369A1",
            "#0C4A6E",
        )
        _card_sm(
            d3,
            "✅",
            "AND (Migração)",
            metricas["criterio_and_migracao"],
            "#DBEAFE",
            "#1D4ED8",
            "#1E40AF",
            "#1E3A8A",
        )
        _card_sm(
            d4,
            "🔦",
            "HABILIDADE PON(1/100)",
            metricas["habilidade_pon"],
            "#FCE7F3",
            "#DB2777",
            "#9D174D",
            "#831843",
        )

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # ABA 2 — DETALHES
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    with tab_detalhes:

        st.markdown("#### 📋 Regras de Classificação")
        st.markdown(
            "| Segmento | Regra |\n"
            "|----------|-------|\n"
            "| 🔄 **Migração** | `TIPO O.S 1` contém `MUDANCA DE PACOTE` **E** `FLAG_GPON` = `Sim` |\n"
            "| 🏠 **Novos Domicílios** | `TIPO O.S` contém `ADESAO` |\n"
            "| 🏢 **PME** | É Novos Domicílios **E** `Capacidade` contém `PME` |\n"
            "| 🔦 **FLAG_GPON** | `HABILIDADE DE TRABALHO` contém `PON(1/100)` → `Sim` |\n"
            "| ⚪ **Outros** | Não atende nenhum critério acima |"
        )

        st.markdown("---")
        st.markdown("#### 🔗 Colunas Detectadas")

        col_tipo = detectar_col_tipo_os_1(df)
        col_gpon = detectar_col_flag_gpon(df)
        col_cap = detectar_col_capacidade(df)
        col_hab = detectar_col_habilidade(df)

        det = pd.DataFrame(
            [
                {
                    "Critério": "TIPO O.S 1",
                    "Coluna": col_tipo or "❌ Não encontrada",
                    "Status": "✅" if col_tipo else "❌",
                },
                {
                    "Critério": "FLAG_GPON",
                    "Coluna": col_gpon or "❌ Não encontrada",
                    "Status": "✅" if col_gpon else "❌",
                },
                {
                    "Critério": "Capacidade",
                    "Coluna": col_cap or "❌ Não encontrada",
                    "Status": "✅" if col_cap else "❌",
                },
                {
                    "Critério": "Habilidade",
                    "Coluna": col_hab or "❌ Não encontrada",
                    "Status": "✅" if col_hab else "❌",
                },
            ]
        )
        st.dataframe(det, hide_index=True, use_container_width=True)

        st.markdown("---")
        st.markdown("#### 📊 Distribuição por TIPO_SERVICO")

        if "TIPO_SERVICO" in df.columns and "TOTAL DE TAREFAS" in df.columns:
            tarefas = pd.to_numeric(df["TOTAL DE TAREFAS"], errors="coerce").fillna(1)
            dist = (
                df.assign(_TAR=tarefas)
                .groupby("TIPO_SERVICO")
                .agg(Registros=("TIPO_SERVICO", "size"), Tarefas=("_TAR", "sum"))
                .reset_index()
                .rename(columns={"TIPO_SERVICO": "Segmento"})
                .sort_values("Tarefas", ascending=False)
            )
            dist["Tarefas"] = dist["Tarefas"].astype(int)
            dist["% Tarefas"] = dist["Tarefas"] / dist["Tarefas"].sum()
            st.dataframe(
                dist.style.format({"% Tarefas": "{:.1%}", "Tarefas": "{:,.0f}"}),
                hide_index=True,
                use_container_width=True,
            )

        st.markdown("---")
        st.markdown("#### 🔬 Diagnóstico Migração")

        m1, m2, m3 = st.columns(3)
        m1.metric(
            "1️⃣ MUDANCA DE PACOTE",
            fmt(metricas["criterio_pacote"]),
            help="Tarefas com TIPO O.S 1 = MUDANCA DE PACOTE",
        )
        m2.metric(
            "2️⃣ FLAG_GPON = Sim",
            fmt(metricas["criterio_gpon_sim"]),
            help="Tarefas com FLAG_GPON = Sim",
        )
        m3.metric(
            "✅ AND (Migração)",
            fmt(metricas["criterio_and_migracao"]),
            help="Tarefas que atendem os 2 critérios",
        )

        if metricas["criterio_and_migracao"] == 0:
            if metricas["criterio_pacote"] == 0:
                st.error("❌ Nenhuma tarefa com MUDANCA DE PACOTE.")
            elif metricas["criterio_gpon_sim"] == 0:
                st.error("❌ Nenhuma tarefa com FLAG_GPON = Sim.")
            else:
                st.warning(
                    f"⚠️ {fmt(metricas['criterio_pacote'])} tarefas com PACOTE e "
                    f"{fmt(metricas['criterio_gpon_sim'])} com GPON, "
                    "mas nenhuma com os dois juntos."
                )
        else:
            st.success(
                f"✅ **{fmt(metricas['criterio_and_migracao'])}** tarefas "
                f"classificadas como Migração."
            )


def render_debug_criterios(df_full: pd.DataFrame, expanded: bool = False) -> None:
    """Expander de diagnóstico técnico dos critérios."""
    with st.expander("🔎 Diagnóstico Técnico de Critérios", expanded=expanded):
        col_tipo = detectar_col_tipo_os_1(df_full)
        col_gpon = detectar_col_flag_gpon(df_full)
        col_cap = detectar_col_capacidade(df_full)
        col_hab = detectar_col_habilidade(df_full)

        st.markdown("**🔗 Colunas detectadas:**")
        cc1, cc2 = st.columns(2)
        cc1.markdown(
            f"**TIPO O.S 1:** "
            + (f"✅ `{col_tipo}`" if col_tipo else "❌")
            + f"\n\n**FLAG_GPON:** "
            + (f"✅ `{col_gpon}`" if col_gpon else "❌")
        )
        cc2.markdown(
            f"**HABILIDADE:** "
            + (f"✅ `{col_hab}`" if col_hab else "❌")
            + f"\n\n**Capacidade:** "
            + (f"✅ `{col_cap}`" if col_cap else "❌")
        )

        if "TIPO_SERVICO" in df_full.columns:
            st.markdown("---")
            st.markdown("**📊 Distribuição:**")
            dist = df_full["TIPO_SERVICO"].value_counts().reset_index()
            dist.columns = ["Segmento", "Registros"]
            st.dataframe(dist, hide_index=True, use_container_width=True)


def render_card_destaque_migracao() -> None:
    st.markdown(
        """
<div style="background:linear-gradient(135deg,#0C4A6E 0%,#0369A1 50%,#0284C7 100%);
            padding:20px 26px;border-radius:12px;color:white;
            box-shadow:0 6px 24px rgba(12,74,110,0.30);margin-bottom:20px;
            border-left:5px solid #FBBF24;">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
        <span style="font-size:26px;">🔄</span>
        <span style="font-size:18px;font-weight:800;">
            CRITÉRIO DE MIGRAÇÃO
        </span>
        <span style="background:rgba(255,255,255,0.20);padding:3px 10px;
                     border-radius:12px;font-size:10px;font-weight:700;">
            AND — 2 critérios juntos
        </span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
        <div style="background:rgba(255,255,255,0.10);padding:12px 16px;border-radius:8px;">
            1️⃣ <code>TIPO O.S 1</code> contém <b>"MUDANCA DE PACOTE"</b>
        </div>
        <div style="background:rgba(255,255,255,0.10);padding:12px 16px;border-radius:8px;">
            2️⃣ <code>FLAG_GPON</code> = <b>"Sim"</b>
        </div>
    </div>
    <div style="margin-top:12px;padding:10px;background:rgba(251,191,36,0.15);
                border-radius:6px;font-size:12px;color:#FEF3C7;">
        🔦 <b>FLAG_GPON</b> auto: HABILIDADE contém <b>PON(1/100)</b>
    </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_lista_colunas(df: pd.DataFrame, expanded: bool = False) -> None:
    if df.empty:
        return
    with st.expander("📋 Colunas da Base", expanded=expanded):
        df_cols = pd.DataFrame(
            {
                "#": range(1, len(df.columns) + 1),
                "Coluna": df.columns.tolist(),
                "Tipo": [str(df[c].dtype) for c in df.columns],
            }
        )
        st.dataframe(
            df_cols,
            hide_index=True,
            use_container_width=True,
            height=min(600, 40 + len(df_cols) * 35),
        )
        st.caption(
            f"Total: **{len(df.columns)} colunas** · "
            f"**{len(df):,} registros**".replace(",", ".")
        )


__all__ = [
    "VAZIOS_GERAIS",
    "VAZIOS_CONTRATO",
    "TERMO_MIGRACAO_OS",
    "VALOR_FLAG_GPON_SIM",
    "TERMO_GPON_HABILIDADE",
    "TERMOS_ND",
    "TERMOS_PME",
    "normalizar_str",
    "norm_col_nome",
    "detectar_cols_tipo",
    "detectar_col_tipo_os_1",
    "detectar_col_flag_gpon",
    "detectar_col_capacidade",
    "detectar_col_habilidade",
    "detectar_col_status_atividade",
    "detectar_col_contrato",
    "criar_coluna_tipos_agrupados",
    "criar_flag_gpon",
    "classificar_tipo_servico",
    "extrair_metricas_criterios",
    "render_painel_criterios",
    "render_debug_criterios",
    "render_card_destaque_migracao",
    "render_lista_colunas",
]
