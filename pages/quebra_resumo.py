"""
quebra_resumo.py
================
Dashboard Corporativo de Desempenho | Quebra Operacional

Fórmula da Quebra:
    Quebra = Não Executados / (Executados + Não Executados)
    → Pendentes NÃO entram no denominador

Segmentos analisados:
    - Novos Domicílios
    - Migração
    - GPON
    - PME
"""

from __future__ import annotations

import sys
import os
from datetime import datetime
from io import BytesIO
from typing import Any

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# ── PATH RESOLUTION ─────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in [_HERE, _ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from utils import Utils  # type: ignore
    from componentes import aplicar_estilo, render_section  # type: ignore
except ImportError:
    Utils = None
    aplicar_estilo = lambda: None
    render_section = st.subheader


# ====================================================
# CONFIGURAÇÃO CORPORATIVA
# ====================================================
META_QUEBRA = 0.20

COR_PRIMARIA = "#012869"
COR_SECUNDARIA = "#F37C04"
COR_SUCESSO = "#059669"
COR_ALERTA = "#DC2626"
COR_NEUTRO = "#64748B"

CORES_TIPO = {
    "Novos Domicílios": "#1E40AF",
    "Migração": "#0284C7",
    "GPON": "#A21CAF",
    "PME": "#1E3A8A",
    "Quebra Geral": "#78350F",
}

ORDEM_TIPOS = [
    "Novos Domicílios",
    "Migração",
    "GPON",
    "PME",
]

MAPA_TIPO_SERVICO = {
    "Novos Domicílios": ["NOVO", "DOMICILIO", "DOMICÍLIO", "ND"],
    "Migração": ["MIGRA"],
    "GPON": ["GPON", "FIBRA"],
    "PME": ["PME", "EMPRESAR"],
}

COL_CAND_MONITOR = ["MONITOR", "SUPERVISOR", "GESTOR"]
COL_CAND_TECNICO = ["TÉCNICO", "TECNICO", "NOME TÉCNICO", "NOME_TECNICO"]
COL_CAND_LOGIN = ["LOGIN", "LOGIN TÉCNICO", "USUÁRIO", "USER"]
COL_CAND_CONTRATO = [
    "CONTRATO",
    "Nº CONTRATO",
    "NUMERO CONTRATO",
    "CONTRATO_ID",
    "COD_CONTRATO",
]
COL_CAND_TIPO = [
    "TIPO_SERVICO",
    "TIPO SERVIÇO",
    "TIPO SERVICO",
    "SEGMENTO",
    "SERVICO",
    "SERVIÇO",
]
COL_CAND_STATUS = [
    "Status Contrato",
    "STATUS CONTRATO",
    "STATUS DA O.S 1",
    "STATUS OS 1",
    "STATUS",
]
COL_CAND_MOTIVO = [
    "CODIGO DE BAIXA 1",
    "MOTIVO DE BAIXA 1",
    "COD BAIXA 1",
    "CÓDIGO BAIXA 1",
    "CÓD DE BAIXA 1",
]
COL_CAND_REGIAO = ["REGIÃO", "REGIAO", "UF", "ESTADO", "CIDADE", "PRACA"]
COL_CAND_DATA = [
    "PERÍODO",
    "PERIODO",
    "DATA AGENDAMENTO",
    "DATA_AGENDAMENTO",
    "DATA VISITA",
    "DATA",
]
COL_CAND_STATUS_ATIV = [
    "STATUS ATIVIDADE",
    "STATUS ATIVIDADE",
    "STATUS_ATIVIDADE",
    "STATUS DA ATIVIDADE",
    "STATUS_DA_ATIVIDADE",
    "SITUAÇÃO ATIVIDADE",
    "SITUACAO ATIVIDADE",
    "SITUAÇÃO",
    "SITUACAO",
    "STATUS CADASTRO",
    "STATUS_CADASTRO",
    "STATUS CLIENTE",
    "STATUS_CLIENTE",
    "STATUS ASSINATURA",
    "STATUS_ASSINATURA",
    "STATUS CONTRATO ATIVIDADE",
]


# ====================================================
# CSS CORPORATIVO
# ====================================================
def _injetar_css_corporativo() -> None:
    st.markdown(
        """
    <style>
        .main .block-container {
            padding-top: 1rem;
            max-width: 1400px;
        }
        .hero-corp {
            background: linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);
            padding: 32px 40px;
            border-radius: 16px;
            color: white;
            box-shadow: 0 10px 40px rgba(1, 40, 105, 0.25);
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
        }
        .hero-corp::before {
            content: '';
            position: absolute;
            top: -50%; right: -10%;
            width: 400px; height: 400px;
            background: rgba(255,255,255,0.05);
            border-radius: 50%;
        }
        .hero-title {
            font-size: 34px;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.5px;
            font-family: 'Segoe UI', -apple-system, sans-serif;
        }
        .hero-subtitle {
            font-size: 15px;
            opacity: 0.92;
            margin: 6px 0 0 0;
            font-weight: 400;
        }
        .hero-badge {
            display: inline-block;
            background: rgba(255,255,255,0.18);
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 12px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        .kpi-card {
            background: white;
            border-radius: 12px;
            padding: 20px 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.06);
            border-left: 4px solid #012869;
            transition: transform 0.2s;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.10);
        }
        .kpi-label {
            font-size: 11px;
            font-weight: 700;
            color: #64748B;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin-bottom: 6px;
        }
        .kpi-value {
            font-size: 28px;
            font-weight: 800;
            color: #0F172A;
            line-height: 1;
            font-variant-numeric: tabular-nums;
        }
        .kpi-sub {
            font-size: 12px;
            color: #64748B;
            margin-top: 6px;
            font-weight: 500;
        }
        .section-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin: 32px 0 16px 0;
            padding-bottom: 12px;
            border-bottom: 2px solid #E2E8F0;
        }
        .section-title {
            font-size: 20px;
            font-weight: 700;
            color: #012869;
            margin: 0;
        }
        .section-badge {
            background: #F1F5F9;
            color: #475569;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .table-wrapper {
            background: white;
            border-radius: 12px;
            padding: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            overflow-x: auto;
        }
        .info-caption {
            background: #EFF6FF;
            border-left: 3px solid #2563EB;
            padding: 12px 16px;
            border-radius: 4px;
            font-size: 13px;
            color: #1E3A8A;
            margin: 12px 0;
            line-height: 1.6;
        }
        .formula-box {
            background: linear-gradient(135deg, #F0F9FF 0%, #EFF6FF 100%);
            border: 1px solid #BFDBFE;
            border-radius: 8px;
            padding: 14px 20px;
            margin: 12px 0;
            font-size: 14px;
            color: #1E3A8A;
        }
        .formula-box b {
            color: #012869;
        }
    </style>
    """,
        unsafe_allow_html=True,
    )


# ====================================================
# UTILITÁRIOS
# ====================================================
def _is_suspenso(valor: Any) -> bool:
    """
    Retorna True se o status de atividade indica SUSPENSÃO.
    Aceita variações: SUSPENSO, SUSPENSA, SUSP, SUSPENSÃO, BLOQUEADO, INATIVO.
    """
    if pd.isna(valor):
        return False
    s = str(valor).upper().strip()
    if not s or s in {"NAN", "NONE", "—", "-", ""}:
        return False

    termos_susp = [
        "SUSPEN",  # cobre SUSPENSO, SUSPENSA, SUSPENSÃO, SUSP
        "BLOQUEAD",  # BLOQUEADO, BLOQUEADA
        "INATIV",  # INATIVO, INATIVA
    ]
    return any(t in s for t in termos_susp)


def _encontrar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
    cols_upper = {c.upper().strip(): c for c in df.columns}
    for cand in candidatos:
        if cand.upper().strip() in cols_upper:
            return cols_upper[cand.upper().strip()]
    return None


def _classificar_status_os(status: Any) -> str:
    """
    Classifica o status em 3 categorias:
    - 'EXECUTADO'      → OS concluída com sucesso
    - 'NAO_EXECUTADO'  → OS com desfecho negativo (quebra)
    - 'PENDENTE'       → OS ainda em aberto (fora do cálculo)
    """
    if pd.isna(status):
        return "PENDENTE"

    s = str(status).upper().strip()

    # ── NÃO EXECUTADO (Quebra) — checa primeiro por causa de "NÃO EXECUTADO" ──
    termos_nao_exec = [
        "NÃO EXECUTAD",
        "NAO EXECUTAD",
        "QUEBRA",
        "CANCELAD",
        "IMPRODUTIV",
        "SEM ACESSO",
        "REAGENDAD",
        "NÃO REALIZ",
        "NAO REALIZ",
        "INSUCESSO",
    ]
    if any(t in s for t in termos_nao_exec):
        return "NAO_EXECUTADO"

    # ── EXECUTADO ──────────────────────────────────────────────
    termos_exec = [
        "EXECUTAD",
        "CONCLUID",
        "REALIZAD",
        "FINALIZAD",
        "ATENDID",
        "SUCESSO",
    ]
    if any(t in s for t in termos_exec):
        return "EXECUTADO"

    # ── PENDENTE ───────────────────────────────────────────────
    termos_pend = ["PENDENTE", "ABERTO", "EM ABERTO", "AGENDAD", "AGUARD"]
    if any(t in s for t in termos_pend):
        return "PENDENTE"

    return "PENDENTE"


def _is_quebra(status: Any) -> bool:
    return _classificar_status_os(status) == "NAO_EXECUTADO"


def _is_executado(status: Any) -> bool:
    return _classificar_status_os(status) == "EXECUTADO"


def _is_pendente(status: Any) -> bool:
    return _classificar_status_os(status) == "PENDENTE"


def _classificar_tipo(valor: Any) -> str | None:
    if pd.isna(valor):
        return None
    s = str(valor).upper().strip()
    for tipo, termos in MAPA_TIPO_SERVICO.items():
        if any(t in s for t in termos):
            return tipo
    return None


def _fmt_pct_br(v: Any) -> str:
    """Formata percentual no padrão brasileiro: 20,50%"""
    try:
        val = float(v)
        return (
            f"{val * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
        )
    except (ValueError, TypeError):
        return "0,00%"


def _fmt_int_br(v: Any) -> str:
    """Formata inteiro com separador de milhar brasileiro: 1.234"""
    try:
        return f"{int(float(v)):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def _cor_gerencial(valor: float, meta: float) -> str:
    if pd.isna(valor):
        return "background-color: #F1F5F9; color: #64748B;"

    if valor > meta:
        return (
            "background-color: #FEE2E2; "
            "color: #991B1B; "
            "font-weight: 700; "
            "border-left: 3px solid #DC2626;"
        )
    else:
        return (
            "background-color: #D1FAE5; "
            "color: #065F46; "
            "font-weight: 700; "
            "border-left: 3px solid #059669;"
        )


def _gerar_excel(df: pd.DataFrame, sheet: str = "Dados") -> bytes:
    if Utils is not None:
        try:
            return Utils.gerar_excel(df, sheet)
        except Exception:
            pass
    buf = BytesIO()
    df.to_excel(buf, index=False, sheet_name=sheet[:31])
    return buf.getvalue()


def _gerar_excel_multi(dfs: dict[str, pd.DataFrame]) -> bytes:
    """Gera Excel com múltiplas abas."""
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    return buf.getvalue()


# ====================================================
# MATRIZ DE DESEMPENHO (Monitor × Segmento)
# ====================================================
def build_matriz_desempenho(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fórmula: Quebra = Não Executados / (Executados + Não Executados)
    Remove contratos com Status de Atividade = SUSPENSO antes de calcular.
    """

    col_mon = _encontrar_coluna(df, COL_CAND_MONITOR)
    col_tipo = _encontrar_coluna(df, COL_CAND_TIPO)
    col_status = _encontrar_coluna(df, COL_CAND_STATUS)
    col_status_ativ = _encontrar_coluna(df, COL_CAND_STATUS_ATIV)

    if not col_mon or not col_status:
        return pd.DataFrame()

    df_work = df.copy()

    # ✅ REMOVER SUSPENSOS ANTES DE QUALQUER CÁLCULO
    if col_status_ativ:
        mask_nao_suspenso = ~df_work[col_status_ativ].apply(_is_suspenso)
        df_work = df_work[mask_nao_suspenso].copy()

    if df_work.empty:
        return pd.DataFrame()

    df_work["_MON"] = (
        df_work[col_mon].fillna("SEM MONITOR").astype(str).str.strip().str.upper()
    )
    df_work["_TIPO"] = (
        df_work[col_tipo].apply(_classificar_tipo)
        if col_tipo and col_tipo in df_work.columns
        else None
    )

    df_work["_STATUS_CLASS"] = df_work[col_status].apply(_classificar_status_os)
    df_work["_EXEC"] = df_work["_STATUS_CLASS"] == "EXECUTADO"
    df_work["_NAO_EXEC"] = df_work["_STATUS_CLASS"] == "NAO_EXECUTADO"
    df_work["_PEND"] = df_work["_STATUS_CLASS"] == "PENDENTE"

    df_valid = df_work.dropna(subset=["_TIPO"]).copy()
    if df_valid.empty:
        return pd.DataFrame()

    grp = (
        df_valid.groupby(["_MON", "_TIPO"])
        .agg(
            executados=("_EXEC", "sum"),
            nao_executados=("_NAO_EXEC", "sum"),
            pendentes=("_PEND", "sum"),
        )
        .reset_index()
    )

    grp["denominador"] = grp["executados"] + grp["nao_executados"]
    grp["pct"] = np.where(
        grp["denominador"] > 0,
        grp["nao_executados"] / grp["denominador"],
        0.0,
    )

    pivot = grp.pivot_table(
        index="_MON",
        columns="_TIPO",
        values="pct",
        fill_value=0.0,
    )

    for tipo in ORDEM_TIPOS:
        if tipo not in pivot.columns:
            pivot[tipo] = 0.0
    pivot = pivot[ORDEM_TIPOS]

    exec_por_mon = df_work.groupby("_MON")["_EXEC"].sum().rename("exec")
    ne_por_mon = df_work.groupby("_MON")["_NAO_EXEC"].sum().rename("nao_exec")

    pivot = pivot.join(exec_por_mon).join(ne_por_mon)
    denom_mon = pivot["exec"] + pivot["nao_exec"]
    pivot["Quebra Geral"] = np.where(
        denom_mon > 0,
        pivot["nao_exec"] / denom_mon,
        0.0,
    )
    pivot = pivot.drop(columns=["exec", "nao_exec"])

    pivot = pivot.reset_index().rename(columns={"_MON": "Monitor"})

    # Linha Total Geral
    total_row: dict[str, Any] = {"Monitor": "Total Geral"}
    for tipo in ORDEM_TIPOS:
        sub = df_valid[df_valid["_TIPO"] == tipo]
        exec_s = int(sub["_EXEC"].sum())
        ne_s = int(sub["_NAO_EXEC"].sum())
        denom = exec_s + ne_s
        total_row[tipo] = ne_s / denom if denom > 0 else 0.0

    exec_tot = int(df_work["_EXEC"].sum())
    ne_tot = int(df_work["_NAO_EXEC"].sum())
    denom_tot = exec_tot + ne_tot
    total_row["Quebra Geral"] = ne_tot / denom_tot if denom_tot > 0 else 0.0

    pivot = pd.concat([pivot, pd.DataFrame([total_row])], ignore_index=True)

    return pivot


# ====================================================
# EXTRAÇÃO COMPLETA
# ====================================================
def build_extracao_completa(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Retorna (df_extracao, qtd_suspensos_removidos).
    Remove:
      1) Contratos com Status de Atividade = SUSPENSO
      2) Contratos com número vazio/inválido
    """

    col_mon = _encontrar_coluna(df, COL_CAND_MONITOR)
    col_tec = _encontrar_coluna(df, COL_CAND_TECNICO)
    col_login = _encontrar_coluna(df, COL_CAND_LOGIN)
    col_contrato = _encontrar_coluna(df, COL_CAND_CONTRATO)
    col_tipo = _encontrar_coluna(df, COL_CAND_TIPO)
    col_status = _encontrar_coluna(df, COL_CAND_STATUS)
    col_status_ativ = _encontrar_coluna(df, COL_CAND_STATUS_ATIV)
    col_motivo = _encontrar_coluna(df, COL_CAND_MOTIVO)
    col_regiao = _encontrar_coluna(df, COL_CAND_REGIAO)
    col_data = _encontrar_coluna(df, COL_CAND_DATA)

    df_ext = pd.DataFrame(index=df.index)

    df_ext["Contrato"] = df[col_contrato] if col_contrato else "—"
    df_ext["Login"] = df[col_login] if col_login else "—"
    df_ext["Técnico"] = df[col_tec] if col_tec else "—"
    df_ext["Monitor"] = df[col_mon] if col_mon else "—"
    df_ext["Região"] = df[col_regiao] if col_regiao else "—"
    df_ext["Tipo Original"] = df[col_tipo] if col_tipo else "—"
    df_ext["Segmento"] = df[col_tipo].apply(_classificar_tipo) if col_tipo else None
    df_ext["Status"] = df[col_status] if col_status else "—"
    df_ext["Status Atividade"] = (
        df[col_status_ativ].fillna("—").astype(str).str.strip().str.upper()
        if col_status_ativ
        else "—"
    )
    df_ext["Motivo Baixa"] = df[col_motivo] if col_motivo else "—"
    df_ext["Período"] = df[col_data] if col_data else "—"

    # Classificação em 3 estados
    if col_status:
        df_ext["Classificação"] = df[col_status].apply(_classificar_status_os)
    else:
        df_ext["Classificação"] = "PENDENTE"

    df_ext["É Executado"] = df_ext["Classificação"] == "EXECUTADO"
    df_ext["É Não Executado"] = df_ext["Classificação"] == "NAO_EXECUTADO"
    df_ext["É Pendente"] = df_ext["Classificação"] == "PENDENTE"

    # ── ✅ 1) REMOVER SUSPENSOS ─────────────────────────────────
    if col_status_ativ:
        mask_suspenso = df[col_status_ativ].apply(_is_suspenso)
        qtd_suspensos = int(mask_suspenso.sum())
        df_ext = df_ext[~mask_suspenso].copy()
    else:
        qtd_suspensos = 0

    # ── ✅ 2) REMOVER CONTRATOS VAZIOS ──────────────────────────
    df_ext["Contrato"] = df_ext["Contrato"].astype(str).str.strip()

    valores_invalidos = {
        "",
        "—",
        "NAN",
        "NULL",
        "NONE",
        "0",
        "0.0",
        "N/D",
        "N/A",
        "NA",
        "-",
    }

    mask_contrato_valido = (
        df_ext["Contrato"].notna()
        & (~df_ext["Contrato"].str.upper().isin(valores_invalidos))
        & (df_ext["Contrato"].str.len() > 0)
    )

    df_ext = df_ext[mask_contrato_valido].copy()

    # Formatação de Período
    try:
        df_ext["Período"] = (
            pd.to_datetime(df_ext["Período"], dayfirst=True, errors="coerce")
            .dt.strftime("%d/%m/%Y")
            .fillna(df_ext["Período"].astype(str))
        )
    except Exception:
        df_ext["Período"] = df_ext["Período"].astype(str)

    # Padronização
    for col in ["Monitor", "Técnico", "Login", "Região"]:
        df_ext[col] = df_ext[col].fillna("—").astype(str).str.strip().str.upper()

    df_ext = df_ext.reset_index(drop=True)
    df_ext.index = df_ext.index + 1

    return df_ext, qtd_suspensos


# ====================================================
# ESTILO DA TABELA RESUMO
# ====================================================
def _estilizar_tabela(df: pd.DataFrame, meta: float):
    """
    Aplica cores gerenciais + formatação percentual pt-BR robusta.
    """
    cols_pct = [c for c in df.columns if c != "Monitor"]

    def _aplicar_cores(row: pd.Series) -> list[str]:
        estilos: list[str] = []
        is_total = str(row.get("Monitor", "")).upper() == "TOTAL GERAL"

        for col in df.columns:
            if col == "Monitor":
                if is_total:
                    estilos.append(
                        "background: linear-gradient(90deg,#012869 0%,#1E40AF 100%); "
                        "color: white; font-size: 15px; font-weight: 800; "
                        "text-align: left; padding-left: 16px; "
                        "letter-spacing: 0.5px; text-transform: uppercase;"
                    )
                else:
                    estilos.append(
                        "background-color: #F8FAFC; color: #0F172A; "
                        "font-size: 14px; font-weight: 700; "
                        "text-align: left; padding-left: 16px; "
                        "border-right: 2px solid #E2E8F0;"
                    )
            else:
                val = row[col]
                cor_base = _cor_gerencial(val, meta)
                extra = "text-align: center; padding: 12px 8px;"

                if is_total:
                    if val > meta:
                        estilos.append(
                            f"background: #7F1D1D; color: white; "
                            f"font-size: 16px; font-weight: 800; "
                            f"border-top: 3px solid #DC2626; {extra}"
                        )
                    else:
                        estilos.append(
                            f"background: #064E3B; color: white; "
                            f"font-size: 16px; font-weight: 800; "
                            f"border-top: 3px solid #059669; {extra}"
                        )
                else:
                    estilos.append(f"{cor_base} font-size: 14px; {extra}")

        return estilos

    # ── Aplica cores ────────────────────────────────────────────
    styler = df.style.apply(_aplicar_cores, axis=1)

    # ── ✅ FORMATAÇÃO PERCENTUAL — MÉTODO ROBUSTO ──────────────
    # Aplica formatter por coluna individualmente (mais confiável)
    format_dict = {col: _fmt_pct_br for col in cols_pct}
    styler = styler.format(format_dict)  # type: ignore[arg-type]

    # ── Estilos de tabela ───────────────────────────────────────
    styler = styler.set_table_styles(
        [
            {
                "selector": "th",
                "props": [
                    ("background", "linear-gradient(180deg,#012869 0%,#1E3A8A 100%)"),
                    ("color", "white"),
                    ("font-weight", "700"),
                    ("font-size", "13px"),
                    ("text-align", "center"),
                    ("padding", "14px 10px"),
                    ("letter-spacing", "0.5px"),
                    ("text-transform", "uppercase"),
                    ("border", "none"),
                    ("border-right", "1px solid rgba(255,255,255,0.15)"),
                ],
            },
            {
                "selector": "td",
                "props": [
                    ("border-bottom", "1px solid #E2E8F0"),
                    ("font-variant-numeric", "tabular-nums"),
                ],
            },
            {
                "selector": "table",
                "props": [
                    ("border-collapse", "separate"),
                    ("border-spacing", "0"),
                    ("width", "100%"),
                    ("font-family", "'Segoe UI', -apple-system, sans-serif"),
                    ("border-radius", "8px"),
                    ("overflow", "hidden"),
                    ("box-shadow", "0 4px 12px rgba(0,0,0,0.08)"),
                ],
            },
        ]
    )

    return styler


# ====================================================
# GRÁFICO CORPORATIVO
# ====================================================
def plot_desempenho(df_matriz: pd.DataFrame, meta: float) -> go.Figure:
    if df_matriz.empty:
        return go.Figure()

    df_plot = df_matriz.copy()
    cols_tipo = [c for c in df_plot.columns if c != "Monitor"]

    fig = go.Figure()

    for tipo in cols_tipo:
        cor = CORES_TIPO.get(tipo, "#6B7280")

        fig.add_trace(
            go.Bar(
                name=tipo,
                x=df_plot["Monitor"],
                y=df_plot[tipo],
                marker=dict(
                    color=cor,
                    line=dict(color="white", width=1.5),
                ),
                text=[_fmt_pct_br(v) for v in df_plot[tipo]],
                textposition="outside",
                textfont=dict(
                    size=14,
                    color="#1F2937",
                    family="'Segoe UI', sans-serif",
                ),
                cliponaxis=False,
                hovertemplate=(
                    f"<b>{tipo}</b><br>"
                    "Monitor: %{x}<br>"
                    "Quebra: %{y:.2%}<extra></extra>"
                ),
            )
        )

    fig.add_hline(
        y=meta,
        line_dash="dash",
        line_color=COR_ALERTA,
        line_width=3,
        annotation_text=f"<b>META: {meta:.0%}</b>",
        annotation_position="top right",
        annotation_font=dict(color="white", size=14),
        annotation_bgcolor=COR_ALERTA,
        annotation_borderpad=6,
    )

    fig.update_layout(
        title=dict(
            text=(
                "<b style='color:#012869;font-size:22px;'>"
                "Distribuição de Quebras por Monitor e Segmento</b>"
                "<br><span style='color:#64748B;font-size:13px;font-weight:400;'>"
                "Fórmula: Não Executadas ÷ (Executadas + Não Executadas)"
                "</span>"
            ),
            x=0.02,
            xanchor="left",
            y=0.97,
        ),
        barmode="group",
        bargap=0.30,
        bargroupgap=0.08,
        xaxis=dict(
            title="",
            tickangle=-25,
            tickfont=dict(size=15, color="#1F2937"),
            showline=True,
            linewidth=2,
            linecolor="#CBD5E1",
        ),
        yaxis=dict(
            title=dict(text="<b>% de Quebra</b>", font=dict(size=14, color="#475569")),
            tickformat=".0%",
            tickfont=dict(size=13, color="#64748B"),
            gridcolor="#F1F5F9",
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.28,
            xanchor="center",
            x=0.5,
            font=dict(size=13, color="#334155"),
            bgcolor="rgba(248,250,252,0.9)",
            bordercolor="#E2E8F0",
            borderwidth=1,
        ),
        height=620,
        margin=dict(l=50, r=40, t=110, b=160),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="'Segoe UI', -apple-system, sans-serif"),
    )

    return fig


# ====================================================
# COMPONENTES DE UI
# ====================================================
def _render_kpi(
    col, label: str, valor: str, sub: str = "", cor: str = COR_PRIMARIA
) -> None:
    col.markdown(
        f"""
        <div class="kpi-card" style="border-left-color:{cor};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="color:{cor};">{valor}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_section_header(icon: str, title: str, badge: str = "") -> None:
    badge_html = f'<span class="section-badge">{badge}</span>' if badge else ""
    st.markdown(
        f"""
        <div class="section-header">
            <span style="font-size:24px;">{icon}</span>
            <h2 class="section-title">{title}</h2>
            {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ====================================================
# PÁGINA PRINCIPAL
# ====================================================
def main() -> None:
    try:
        aplicar_estilo()
    except Exception:
        pass

    _injetar_css_corporativo()

    # ── HERO ────────────────────────────────────────────────────
    data_ref = datetime.now().strftime("%d/%m/%Y")
    hora_ref = datetime.now().strftime("%H:%M")

    st.markdown(
        f"""
        <div class="hero-corp">
            <div style="position:relative;z-index:2;">
                <h1 class="hero-title">📊 Desempenho | Quebra Operacional</h1>
                <p class="hero-subtitle">
                    Análise consolidada · Novos Domicílios · Migração · GPON · PME
                </p>
                <span class="hero-badge">
                    Atualizado em {data_ref} · {hora_ref}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("df_memoria") is None:
        st.warning("⚠️ **Nenhuma base carregada.**")
        st.info("👈 Volte ao **Dashboard Geral** no menu lateral e realize o upload.")
        return

    df_full: pd.DataFrame = st.session_state["df_memoria"].copy()

    # ── SIDEBAR ─────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            """
            <div style="padding:12px 8px;border-bottom:2px solid #E2E8F0;margin-bottom:16px;">
                <div style="font-size:11px;font-weight:700;color:#64748B;
                     letter-spacing:1px;text-transform:uppercase;">
                    Painel de Controle
                </div>
                <div style="font-size:18px;font-weight:700;color:#012869;margin-top:4px;">
                    ⚙️ Configurações
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_mon = _encontrar_coluna(df_full, COL_CAND_MONITOR)
        if col_mon:
            monitores = ["Todos os Monitores"] + sorted(
                str(x)
                for x in df_full[col_mon].dropna().unique()
                if str(x).upper() not in {"NAN", "SEM MONITOR", "NÃO MAPEADO"}
            )
            sel_mon = st.selectbox("👔 **Monitor**", monitores, key="qr_mon_corp")
            df_filt = (
                df_full
                if sel_mon == "Todos os Monitores"
                else df_full[df_full[col_mon] == sel_mon]
            )
        else:
            df_filt = df_full.copy()

        st.markdown("---")

        meta_slider_pct = (
            st.slider(
                "🎯 **Meta de Quebra (%)**",
                min_value=5,
                max_value=50,
                value=int(META_QUEBRA * 100),
                step=1,
            )
            / 100
        )

        st.markdown("---")
        st.markdown("**🚦 Critério de Cores**")
        st.markdown(
            f"""
            <div style="background:#D1FAE5;color:#065F46;padding:8px 12px;
                 border-radius:6px;font-size:13px;font-weight:600;margin-bottom:6px;">
                ✓ ≤ {meta_slider_pct:.0%} — Dentro da meta
            </div>
            <div style="background:#FEE2E2;color:#991B1B;padding:8px 12px;
                 border-radius:6px;font-size:13px;font-weight:600;">
                ✗ &gt; {meta_slider_pct:.0%} — Acima da meta
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("**🧮 Fórmula da Quebra**")
        st.markdown(
            """
            <div style="background:#F1F5F9;padding:10px;border-radius:6px;
                 font-size:12px;color:#334155;font-family:monospace;">
                Quebra = NE ÷ (E + NE)<br>
                <span style="color:#64748B;">Pendentes não contam</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    if df_filt.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    # ── PROCESSAMENTO ───────────────────────────────────────────
    with st.spinner("⏳ Processando dados gerenciais..."):
        df_matriz = build_matriz_desempenho(df_filt)
        df_extracao, qtd_suspensos = build_extracao_completa(df_filt)

    if df_matriz.empty:
        st.error("⚠️ Dados insuficientes para gerar a matriz de desempenho.")
        return

    # ── KPIs EXECUTIVOS ─────────────────────────────────────────
    _render_section_header("📌", "Indicadores Executivos", "KPIs")

    df_sem_total = df_matriz[df_matriz["Monitor"] != "Total Geral"]
    total_row = df_matriz[df_matriz["Monitor"] == "Total Geral"].iloc[0]

    # Cálculo consolidado
    col_status_full = _encontrar_coluna(df_filt, COL_CAND_STATUS)
    if col_status_full:
        status_class = df_filt[col_status_full].apply(_classificar_status_os)
        total_exec = int((status_class == "EXECUTADO").sum())
        total_nao_exec = int((status_class == "NAO_EXECUTADO").sum())
        total_pendente = int((status_class == "PENDENTE").sum())
        denom_geral = total_exec + total_nao_exec
        quebra_geral = total_nao_exec / denom_geral if denom_geral > 0 else 0.0
    else:
        total_exec = total_nao_exec = total_pendente = 0
        denom_geral = 0
        quebra_geral = 0.0

    total_monitores = len(df_sem_total)
    acima_meta = int((df_sem_total["Quebra Geral"] > meta_slider_pct).sum())
    pior_tipo = max(ORDEM_TIPOS, key=lambda t: float(total_row.get(t, 0)))

    k1, k2, k3, k4 = st.columns(4)

    _render_kpi(
        k1,
        "Quebra Consolidada",
        _fmt_pct_br(quebra_geral),
        f"NE: {_fmt_int_br(total_nao_exec)} / Base: {_fmt_int_br(denom_geral)}",
        COR_ALERTA if quebra_geral > meta_slider_pct else COR_SUCESSO,
    )
    _render_kpi(
        k2,
        "Monitores Ativos",
        _fmt_int_br(total_monitores),
        f"{acima_meta} acima da meta",
        COR_PRIMARIA,
    )
    _render_kpi(
        k3,
        "Pendentes",
        _fmt_int_br(total_pendente),
        "Fora do cálculo de quebra",
        COR_NEUTRO,
    )
    _render_kpi(
        k4,
        "Segmento Crítico",
        pior_tipo,
        f"Quebra: {_fmt_pct_br(total_row[pior_tipo])}",
        COR_SECUNDARIA,
    )

    # ── ABAS ────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)

    tab_resumo, tab_extracao = st.tabs(
        [
            "📊  Matriz Resumo (Monitor × Segmento)",
            "📋  Extração Completa (Drill-down)",
        ]
    )

    # ═══════════════════════════════════════════════════════════
    # TAB 1: RESUMO
    # ═══════════════════════════════════════════════════════════
    with tab_resumo:
        _render_section_header("📋", "Matriz de Desempenho", "Monitor × Segmento")

        st.markdown(
            f"""
            <div class="formula-box">
                🧮 <b>Fórmula aplicada:</b>
                Quebra = Não Executadas ÷ (Executadas + Não Executadas)
                = <b>{_fmt_int_br(total_nao_exec)} ÷ {_fmt_int_br(denom_geral)}
                = {_fmt_pct_br(quebra_geral)}</b>
                <br>
                ℹ️ <b>{_fmt_int_br(total_pendente)}</b> registros pendentes
                não entraram no cálculo. Meta de referência:
                <b>{meta_slider_pct:.0%}</b>.
            </div>
            """,
            unsafe_allow_html=True,
        )

        styler = _estilizar_tabela(df_matriz, meta=meta_slider_pct)
        st.markdown(
            f'<div class="table-wrapper">{styler.hide(axis="index").to_html()}</div>',  # type: ignore
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        exp1, exp2, exp3 = st.columns([1, 1, 4])

        with exp1:
            st.download_button(
                "📊 **Exportar Excel**",
                data=_gerar_excel(df_matriz, "Resumo_Quebra"),
                file_name=f"resumo_quebra_{datetime.now():%Y%m%d_%H%M}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with exp2:
            st.download_button(
                "📄 **Exportar CSV**",
                data=df_matriz.to_csv(index=False, decimal=",").encode("utf-8-sig"),
                file_name=f"resumo_quebra_{datetime.now():%Y%m%d_%H%M}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        # GRÁFICO
        _render_section_header("📊", "Análise Comparativa Visual", "Gráfico")
        fig = plot_desempenho(df_matriz, meta=meta_slider_pct)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    # ═══════════════════════════════════════════════════════════
    # TAB 2: EXTRAÇÃO COMPLETA
    # ═══════════════════════════════════════════════════════════
    with tab_extracao:
        _render_section_header("📋", "Extração Completa da Base", "Drill-down")

        total_os = len(df_extracao)
        total_os_original = len(df_filt)
        removidos_total = total_os_original - total_os
        # removidos por contrato vazio = total removidos - suspensos
        removidos_vazio = max(0, removidos_total - qtd_suspensos)

        ext_exec = int(df_extracao["É Executado"].sum())
        ext_nao_exec = int(df_extracao["É Não Executado"].sum())
        ext_pend = int(df_extracao["É Pendente"].sum())
        ext_denom = ext_exec + ext_nao_exec
        ext_pct = ext_nao_exec / ext_denom if ext_denom > 0 else 0.0

        ek1, ek2, ek3, ek4 = st.columns(4)

        _render_kpi(
            ek1,
            "OS Válidas",
            _fmt_int_br(total_os),
            f"de {_fmt_int_br(total_os_original)} originais",
            COR_PRIMARIA,
        )
        _render_kpi(
            ek2,
            "Executadas",
            _fmt_int_br(ext_exec),
            f"{_fmt_pct_br(ext_exec / total_os if total_os else 0)} do total",
            COR_SUCESSO,
        )
        _render_kpi(
            ek3,
            "Não Executadas",
            _fmt_int_br(ext_nao_exec),
            f"Quebra: {_fmt_pct_br(ext_pct)}",
            COR_ALERTA,
        )
        _render_kpi(
            ek4,
            "Pendentes",
            _fmt_int_br(ext_pend),
            "Fora do cálculo",
            COR_NEUTRO,
        )

        # ── AVISOS DE EXCLUSÃO ────────────────────────────────────
        if qtd_suspensos > 0 or removidos_vazio > 0:
            linhas_aviso = []
            if qtd_suspensos > 0:
                linhas_aviso.append(
                    f"🚫 <b>{_fmt_int_br(qtd_suspensos)}</b> contratos com "
                    f"<b>Status de Atividade = SUSPENSO</b> foram excluídos."
                )
            if removidos_vazio > 0:
                linhas_aviso.append(
                    f"⚠️ <b>{_fmt_int_br(removidos_vazio)}</b> registros com "
                    f"<b>número de contrato vazio/inválido</b> foram excluídos."
                )

            st.markdown(
                f"""
                <div class="info-caption" style="background:#FEF3C7;
                    border-left-color:#D97706;color:#92400E;">
                    <b>Registros excluídos da análise:</b><br>
                    {"<br>".join(linhas_aviso)}
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown(
            f"""
            <div class="formula-box">
                🧮 <b>Cálculo da Quebra desta extração:</b>
                {_fmt_int_br(ext_nao_exec)} ÷ ({_fmt_int_br(ext_exec)} + {_fmt_int_br(ext_nao_exec)})
                = <b>{_fmt_pct_br(ext_pct)}</b>
                <br>
                <span style="color:#64748B;">
                    Suspensos e contratos vazios não entram em nenhum cálculo.
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # ── FILTROS ─────────────────────────────────────────────
        st.markdown(
            """
            <div class="info-caption">
                🔎 Use os filtros abaixo para refinar a extração.
                A tabela é interativa e permite ordenação por qualquer coluna.
            </div>
            """,
            unsafe_allow_html=True,
        )

        fc1, fc2, fc3, fc4 = st.columns(4)

        with fc1:
            opts_seg = ["Todos"] + sorted(
                str(x)
                for x in df_extracao["Segmento"].dropna().unique()
                if str(x) not in {"None", "nan"}
            )
            f_seg = st.selectbox("Segmento", opts_seg, key="ext_f_seg")

        with fc2:
            opts_mon_ext = ["Todos"] + sorted(
                str(x)
                for x in df_extracao["Monitor"].dropna().unique()
                if str(x) not in {"—", "nan"}
            )
            f_mon = st.selectbox("Monitor", opts_mon_ext, key="ext_f_mon")

        with fc3:
            opts_tec = ["Todos"] + sorted(
                str(x)
                for x in df_extracao["Técnico"].dropna().unique()
                if str(x) not in {"—", "nan"}
            )
            f_tec = st.selectbox("Técnico", opts_tec, key="ext_f_tec")

        with fc4:
            f_status = st.selectbox(
                "Status",
                [
                    "Todos",
                    "Somente Executadas",
                    "Somente Não Executadas (Quebra)",
                    "Somente Pendentes",
                ],
                key="ext_f_status",
            )

        # Aplicar filtros
        df_view = df_extracao.copy()
        if f_seg != "Todos":
            df_view = df_view[df_view["Segmento"] == f_seg]
        if f_mon != "Todos":
            df_view = df_view[df_view["Monitor"] == f_mon]
        if f_tec != "Todos":
            df_view = df_view[df_view["Técnico"] == f_tec]
        if f_status == "Somente Executadas":
            df_view = df_view[df_view["É Executado"] == True]
        elif f_status == "Somente Não Executadas (Quebra)":
            df_view = df_view[df_view["É Não Executado"] == True]
        elif f_status == "Somente Pendentes":
            df_view = df_view[df_view["É Pendente"] == True]

        st.markdown(
            f"**Exibindo `{len(df_view):,}` de `{total_os:,}` registros**".replace(
                ",", "."
            ),
        )

        # ── TABELA ──────────────────────────────────────────────
        st.dataframe(
            df_view,
            use_container_width=True,
            height=500,
            hide_index=True,
            column_config={
                "Contrato": st.column_config.TextColumn(
                    "📄 Contrato",
                    width="small",
                    help="Número do contrato",
                ),
                "Status Atividade": st.column_config.TextColumn(
                    "🔒 Status Atividade",
                    width="small",
                    help="Status cadastral do contrato (ATIVO, SUSPENSO, etc.)",
                ),
                "Login": st.column_config.TextColumn("🔑 Login", width="small"),
                "Técnico": st.column_config.TextColumn("👤 Técnico", width="medium"),
                "Monitor": st.column_config.TextColumn("👔 Monitor", width="medium"),
                "Região": st.column_config.TextColumn("🌎 Região", width="small"),
                "Tipo Original": st.column_config.TextColumn(
                    "Tipo (Original)",
                    width="medium",
                ),
                "Segmento": st.column_config.TextColumn("🏷️ Segmento", width="small"),
                "Status": st.column_config.TextColumn("📊 Status", width="medium"),
                "Classificação": st.column_config.TextColumn(
                    "🏁 Classificação",
                    width="small",
                    help="EXECUTADO · NAO_EXECUTADO · PENDENTE",
                ),
                "Motivo Baixa": st.column_config.TextColumn(
                    "💬 Motivo Baixa",
                    width="large",
                ),
                "Período": st.column_config.TextColumn("📅 Período", width="small"),
                "É Executado": st.column_config.CheckboxColumn(
                    "✅",
                    help="OS executada",
                    width="small",
                ),
                "É Não Executado": st.column_config.CheckboxColumn(
                    "❌",
                    help="OS em quebra",
                    width="small",
                ),
                "É Pendente": st.column_config.CheckboxColumn(
                    "⏳",
                    help="OS pendente (fora do cálculo)",
                    width="small",
                ),
            },
            column_order=[
                "Contrato",
                "Login",
                "Técnico",
                "Monitor",
                "Região",
                "Segmento",
                "Tipo Original",
                "Status",
                "Status Atividade",  # ← juntos
                "Classificação",
                "É Executado",
                "É Não Executado",
                "É Pendente",
                "Motivo Baixa",
                "Período",
            ],
        )

        # ── EXPORTAÇÃO ──────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        _render_section_header("📥", "Exportação", "Excel · CSV")

        ex1, ex2, ex3, ex4 = st.columns([1.2, 1.2, 1.5, 3])

        with ex1:
            st.download_button(
                "📊 **Filtrado (Excel)**",
                data=_gerar_excel(df_view, "Extracao_Filtrada"),
                file_name=f"extracao_filtrada_{datetime.now():%Y%m%d_%H%M}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with ex2:
            st.download_button(
                "📊 **Completo (Excel)**",
                data=_gerar_excel(df_extracao, "Extracao_Completa"),
                file_name=f"extracao_completa_{datetime.now():%Y%m%d_%H%M}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with ex3:
            excel_multi = _gerar_excel_multi(
                {
                    "Resumo": df_matriz,
                    "Extracao_Completa": df_extracao,
                }
            )
            st.download_button(
                "📦 **Relatório Consolidado**",
                data=excel_multi,
                file_name=f"relatorio_consolidado_{datetime.now():%Y%m%d_%H%M}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary",
            )

    # ── RODAPÉ ──────────────────────────────────────────────────
    st.markdown(
        f"""
        <div style="text-align:center;padding:20px;margin-top:32px;
             border-top:1px solid #E2E8F0;color:#94A3B8;font-size:12px;">
            <b style="color:#012869;">Dashboard Corporativo · Quebra Operacional</b><br>
            Gerado em {data_ref} às {hora_ref} · Dados sujeitos a atualização
            <br>
            <span style="font-family:monospace;font-size:11px;">
                Fórmula: Quebra = Não Executadas ÷ (Executadas + Não Executadas)
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
