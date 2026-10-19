"""
quebra.py
=========
Super Relatório Corporativo de Desempenho | Quebra Operacional Unificada
Integrado ao novo Design System (componentes.py) e às Regras Oficiais (criterios.py).
"""

from __future__ import annotations

import logging
from datetime import datetime
from io import BytesIO
from typing import Any

import gspread
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from google.oauth2.service_account import Credentials
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

from components import base_operacional as bo
from components.componentes import (
    aplicar_estilo,
    estilizar_dataframe,
    render_dataframe,
    render_hero,
    render_insight,
    render_kpi,
    render_section_header,
)
from components.upload_base import (
    limpar_bases_operacionais,
    limpar_cache_lista_ativos,
    render_status_upload,
    render_upload_base_operacional,
)
from components.criterios import (
    classificar_tipo_servico,
    extrair_metricas_criterios,
    render_card_destaque_migracao,
    render_debug_criterios,
    render_lista_colunas,
    render_painel_criterios,
)

# ═══════════════════════════════════════════════════════
# CONFIGURAÇÕES E CONSTANTES
# ═══════════════════════════════════════════════════════
logger = logging.getLogger(__name__)


class Config:
    SLA_GERAL = 0.20
    SLA_MIGRACAO = 0.25
    SLA_PME = 0.20

    URL_LISTA_ATIVOS = (
        "https://docs.google.com/spreadsheets/d/"
        f"{bo.resolver_sheet_id(default='1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg')}/edit"
    )
    SHEET_ID_ATIVOS = bo.resolver_sheet_id(
        default="1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
    )
    WORKSHEET_ATIVOS = "lista_ativos"

    COL_REGIAO = "REGIÃO"
    ORDEM_TIPOS = ["Novos Domicílios", "Migração", "PME"]

    COLS_BASE_PRIORITARIAS = [
        "CONTRATO",
        "LOGIN",
        "TÉCNICO",
        "MONITOR",
        "FLAG_GPON",
        "ORIGEM_MAPEAMENTO",
        "REGIÃO",
        "TIPO_SERVICO",
        "Status Contrato",
        "TOTAL DE TAREFAS",
        "_TIPOS_OS_AGRUPADOS",
        "_COL_BAIXA",
    ]


def _fmt_int(v: int) -> str:
    return f"{int(v):,}".replace(",", ".")


# ═══════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════
class Utils:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras: list) -> str | None:
        if df is None or df.empty:
            return None
        cols = {
            str(c)
            .strip()
            .upper()
            .replace(".", "")
            .replace("_", "")
            .replace("  ", " "): c
            for c in df.columns
        }
        for p in palavras:
            pn = (
                str(p)
                .strip()
                .upper()
                .replace(".", "")
                .replace("_", "")
                .replace("  ", " ")
            )
            for cn, co in cols.items():
                if pn in cn:
                    return co
        return None

    @staticmethod
    def gerar_excel(df: pd.DataFrame, aba: str = "Dados") -> bytes:
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name=aba[:31])
            ws = w.sheets[aba[:31]]
            hf = PatternFill("solid", fgColor="0A2F6B")
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for row in ws.iter_rows(min_row=1, max_row=1):
                for cell in row:
                    cell.fill = hf
                    cell.font = Font(color="FFFFFF", bold=True)
            for i, col in enumerate(df.columns, 1):
                try:
                    max_len = max(
                        df[col].fillna("").astype(str).str.len().max(), len(str(col))
                    )
                    ws.column_dimensions[get_column_letter(i)].width = min(
                        max(max_len + 2, 12), 40
                    )
                except Exception:
                    ws.column_dimensions[get_column_letter(i)].width = 20
        return out.getvalue()


# ═══════════════════════════════════════════════════════
# CARREGAMENTO E TRATAMENTO DE DADOS
# ═══════════════════════════════════════════════════════
class DataLoader:
    """Leitura e tratamento — pipeline compartilhado de ``base_operacional``."""

    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
        """Leitura compartilhada (tudo como texto, como na página)."""
        try:
            return bo.ler_arquivo_bytes(file_bytes, filename, dtype=str)
        except Exception as e:
            st.error(f"❌ Erro ao ler arquivo: {e}")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(ttl=300, show_spinner="🔗 Vinculando Lista de Ativos...")
    def buscar_gsheets() -> pd.DataFrame:
        """
        Lê a aba ``lista_ativos`` da planilha de ativos; só recorre ao CSV
        público se necessário. A implementação vive em
        ``components/base_operacional``; as dependências são injetadas aqui
        para manter o cache do Streamlit funcionando.
        """
        return bo.carregar_lista_ativos(
            sheet_id=Config.SHEET_ID_ATIVOS,
            worksheet=Config.WORKSHEET_ATIVOS,
            url=Config.URL_LISTA_ATIVOS,
            credenciais=Credentials.from_service_account_info,
            autorizar=gspread.authorize,
            read_csv=pd.read_csv,
        )

    @staticmethod
    def _normalizar_lista_ativos(raw: pd.DataFrame) -> pd.DataFrame:
        """Padroniza a aba ``lista_ativos`` (implementação em base_operacional)."""
        return bo.normalizar_lista_ativos(raw)

    @staticmethod
    def _normalizar_login(serie: pd.Series) -> pd.Series:
        return (
            serie.fillna("")
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
            .str.upper()
        )

    @staticmethod
    def compatibilizar_base(df: pd.DataFrame) -> pd.DataFrame:
        """Adapta sessões/caches antigos ao esquema esperado pelo relatório."""
        if df is None:
            return pd.DataFrame()

        base = df.copy()
        base.columns = base.columns.astype(str).str.strip()

        # Sessões do Streamlit sobrevivem a mudanças de código e podem conter
        # versões antigas da base (por exemplo, ``Monitor`` em vez de ``MONITOR``).
        if "MONITOR" not in base.columns:
            col_monitor = Utils.buscar_coluna(
                base, ["MONITOR", "SUPERVISOR", "GESTOR", "COORDENADOR", "NOME MONITOR"]
            )
            if col_monitor:
                base["MONITOR"] = base[col_monitor]
            else:
                base["MONITOR"] = "SEM MONITOR"
                base.attrs["coluna_monitor_ausente"] = True
        base["MONITOR"] = base["MONITOR"].fillna("").astype(str).str.strip().str.upper()
        base.loc[
            base["MONITOR"].isin(["", "NAN", "NONE", "NULL", "0", "N/A", "<NA>"]),
            "MONITOR",
        ] = "SEM MONITOR"

        if "TÉCNICO" not in base.columns:
            col_tecnico = Utils.buscar_coluna(
                base,
                [
                    "TÉCNICO",
                    "TECNICO",
                    "NOME TÉCNICO",
                    "NOME TECNICO",
                    "NOME DO TÉCNICO",
                    "NOME DO TECNICO",
                ],
            )
            base["TÉCNICO"] = base[col_tecnico] if col_tecnico else "NÃO MAPEADO"
        base["TÉCNICO"] = base["TÉCNICO"].fillna("").astype(str).str.strip().str.upper()
        base.loc[
            base["TÉCNICO"].isin(["", "NAN", "NONE", "NULL", "0", "N/A", "<NA>"]),
            "TÉCNICO",
        ] = "NÃO MAPEADO"

        col_status = Utils.buscar_coluna(base, ["STATUS CONTRATO"])
        if col_status is None:
            col_status = Utils.buscar_coluna(
                base, ["STATUS DA O.S 1", "STATUS OS 1", "STATUS DA OS 1"]
            )
        base["Status Contrato"] = (
            bo.Utils.classificar_status(base[col_status]) if col_status else "Pendente"
        )

        col_total = Utils.buscar_coluna(
            base, ["TOTAL DE TAREFAS", "TOTAL TAREFAS", "QTD TAREFAS"]
        )
        base["TOTAL DE TAREFAS"] = (
            pd.to_numeric(base[col_total], errors="coerce").fillna(1).clip(lower=0)
            if col_total
            else 1
        )
        return base

    @staticmethod
    @st.cache_data(show_spinner=False)
    def preparar_base(
        df: pd.DataFrame,
        df_gs: pd.DataFrame,
        fonte_ativos: str = "",
        erro_ativos: str = "",
    ) -> pd.DataFrame:
        """
        Tratamento compartilhado (``components/base_operacional``).

        Mantém os ``attrs`` de diagnóstico usados pelas abas da página.
        """
        return bo.preparar_base_quebra(df, df_gs, fonte_ativos, erro_ativos)


# ═══════════════════════════════════════════════════════
# MOTORES ANALÍTICOS
# ═══════════════════════════════════════════════════════
class Analise:
    @staticmethod
    def matriz_resumo(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or "TIPO_SERVICO" not in df.columns:
            return pd.DataFrame()

        df_valid = df[df["TIPO_SERVICO"] != "Outros"].copy()
        if df_valid.empty:
            return pd.DataFrame()

        grp = (
            df_valid.groupby(["MONITOR", "TIPO_SERVICO", "Status Contrato"])[
                "TOTAL DE TAREFAS"
            ]
            .sum()
            .unstack("Status Contrato", fill_value=0)
            .reindex(columns=["Executada", "Não Executada"], fill_value=0)
            .rename(
                columns={
                    "Executada": "executados",
                    "Não Executada": "nao_executados",
                }
            )
            .reset_index()
        )

        grp["pct"] = np.where(
            (grp["executados"] + grp["nao_executados"]) > 0,
            grp["nao_executados"] / (grp["executados"] + grp["nao_executados"]),
            0.0,
        )

        pivot = grp.pivot_table(
            index="MONITOR", columns="TIPO_SERVICO", values="pct", fill_value=0.0
        )
        for t in Config.ORDEM_TIPOS:
            if t not in pivot.columns:
                pivot[t] = 0.0
        pivot = pivot[Config.ORDEM_TIPOS]

        tot_status = (
            df_valid.groupby(["MONITOR", "Status Contrato"])["TOTAL DE TAREFAS"]
            .sum()
            .unstack(fill_value=0)
            .reindex(pivot.index)
            .fillna(0)
        )
        exec_col = (
            tot_status["Executada"]
            if "Executada" in tot_status.columns
            else pd.Series(0, index=pivot.index)
        )
        ne_col = (
            tot_status["Não Executada"]
            if "Não Executada" in tot_status.columns
            else pd.Series(0, index=pivot.index)
        )
        den = exec_col + ne_col

        pivot["Quebra Geral"] = np.where(den > 0, ne_col / den, 0.0)
        pivot["Total Tarefas"] = (
            df_valid.groupby("MONITOR")["TOTAL DE TAREFAS"]
            .sum()
            .reindex(pivot.index)
            .fillna(0)
            .astype(int)
        )
        pivot = pivot.reset_index().rename(columns={"MONITOR": "Monitor"})

        total_row: dict[str, Any] = {"Monitor": "Total Geral"}
        for tipo in Config.ORDEM_TIPOS:
            sub = df_valid[df_valid["TIPO_SERVICO"] == tipo]
            ex = sub.loc[
                sub["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"
            ].sum()
            ne = sub.loc[
                sub["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"
            ].sum()
            total_row[tipo] = ne / (ex + ne) if (ex + ne) > 0 else 0.0

        ex_g = df_valid.loc[
            df_valid["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"
        ].sum()
        ne_g = df_valid.loc[
            df_valid["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"
        ].sum()
        total_row["Quebra Geral"] = ne_g / (ex_g + ne_g) if (ex_g + ne_g) > 0 else 0.0
        total_row["Total Tarefas"] = int(df_valid["TOTAL DE TAREFAS"].sum())

        return pd.concat([pivot, pd.DataFrame([total_row])], ignore_index=True)

    @staticmethod
    def metricas_segmento(df_seg: pd.DataFrame) -> dict[str, Any]:
        aloc = float(df_seg["TOTAL DE TAREFAS"].sum())
        exe = float(
            df_seg.loc[
                df_seg["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"
            ].sum()
        )
        nex = float(
            df_seg.loc[
                df_seg["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"
            ].sum()
        )
        pen = max(0.0, aloc - exe - nex)
        quebra = (nex / (exe + nex)) if (exe + nex) > 0 else 0.0
        return {
            "alocado": aloc,
            "exec": exe,
            "naoexec": nex,
            "pend": pen,
            "quebra": quebra,
        }

    @staticmethod
    def ranking_tecnicos(df_seg: pd.DataFrame) -> pd.DataFrame:
        if df_seg.empty:
            return pd.DataFrame()
        df_w = df_seg.copy()
        df_w["_exec"] = np.where(
            df_w["Status Contrato"] == "Executada", df_w["TOTAL DE TAREFAS"], 0
        )
        df_w["_ne"] = np.where(
            df_w["Status Contrato"] == "Não Executada", df_w["TOTAL DE TAREFAS"], 0
        )

        df_t = (
            df_w.groupby(["TÉCNICO", "MONITOR"])
            .agg(
                Alocado=("TOTAL DE TAREFAS", "sum"),
                Executadas=("_exec", "sum"),
                Nao_Executadas=("_ne", "sum"),
            )
            .reset_index()
        )

        df_t["Considerado"] = df_t["Executadas"] + df_t["Nao_Executadas"]
        df_t["Quebra Atual"] = np.where(
            df_t["Considerado"] > 0, df_t["Nao_Executadas"] / df_t["Considerado"], 0.0
        )
        return df_t.sort_values("Nao_Executadas", ascending=False).reset_index(
            drop=True
        )


# ═══════════════════════════════════════════════════════
# VISÕES DO APLICATIVO
# ═══════════════════════════════════════════════════════
def view_executiva(df: pd.DataFrame, meta_pct: float):
    if df.empty:
        st.info("Sem dados para a Visão Executiva.")
        return

    df_matriz = Analise.matriz_resumo(df)
    if df_matriz.empty:
        render_insight("Não foi possível gerar a matriz de resumo.", tipo="alerta")
        return

    total_row = df_matriz[df_matriz["Monitor"] == "Total Geral"].iloc[0]

    render_section_header("bar_chart", "Panorama Corporativo", "Consolidado")
    k1, k2, k3, k4 = st.columns(4)
    render_kpi(
        k1, "Total O.S. (Base)", _fmt_int(total_row["Total Tarefas"]), tema="azul"
    )
    render_kpi(
        k2,
        "Quebra Consolidada",
        f"{float(total_row['Quebra Geral']):.2%}",
        sub=f"Meta: {meta_pct:.0%}",
        tema="vermelho" if float(total_row["Quebra Geral"]) > meta_pct else "verde",
    )
    render_kpi(k3, "Meta Global", f"{meta_pct:.0%}", tema="cinza")
    pior = max(Config.ORDEM_TIPOS, key=lambda t: float(total_row.get(t, 0)))
    render_kpi(
        k4,
        "Segmento Crítico",
        pior,
        f"Quebra: {float(total_row[pior]):.2%}",
        tema="laranja",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    render_section_header("grid_view", "Matriz de Desempenho (Monitor × Segmento)")

    # Mesmo visual das outras tabelas, com sinalização das quebras acima da meta.
    def _cor_celula(val):
        if pd.notna(val):
            if val > meta_pct:
                return (
                    "background-color: #FEF2F2; color: #B4232E; "
                    "font-weight: 700; text-align: center;"
                )
            return (
                "background-color: #ECFDF5; color: #087A55; "
                "font-weight: 700; text-align: center;"
            )
        return ""

    formatos: dict[str, Any] = {
        **{c: "{:.1%}" for c in Config.ORDEM_TIPOS},
        "Quebra Geral": "{:.1%}",
        "Total Tarefas": "{:,.0f}",
    }
    sty = estilizar_dataframe(df_matriz, formatos)
    cols_pct = Config.ORDEM_TIPOS + ["Quebra Geral"]
    if hasattr(sty, "map"):
        sty = sty.map(_cor_celula, subset=pd.Index(cols_pct))
    else:
        sty = sty.applymap(_cor_celula, subset=cols_pct)  # type: ignore[attr-defined]
    st.dataframe(
        sty,
        use_container_width=True,
        hide_index=True,
        height=min(520, 40 + 36 * len(df_matriz)),
    )

    st.markdown("<br>", unsafe_allow_html=True)
    render_section_header("show_chart", "Distribuição Visual por Segmento")
    df_plot = df_matriz[df_matriz["Monitor"] != "Total Geral"]

    fig = go.Figure()
    cores = {"Novos Domicílios": "#0A2F6B", "Migração": "#E8700A", "PME": "#7C3AED"}
    for tipo in Config.ORDEM_TIPOS:
        fig.add_trace(
            go.Bar(
                name=tipo,
                x=df_plot["Monitor"],
                y=df_plot[tipo],
                marker_color=cores.get(tipo, "#6B7280"),
                text=[f"{v:.1%}" for v in df_plot[tipo]],
                textposition="outside",
            )
        )
    fig.add_hline(
        y=meta_pct,
        line_dash="dash",
        line_color="#D13438",
        annotation_text=f"META: {meta_pct:.0%}",
    )
    fig.update_layout(
        barmode="group",
        height=420,
        yaxis_tickformat=".0%",
        margin=dict(t=30, b=20, l=10, r=10),
    )
    st.plotly_chart(fig, use_container_width=True)


def view_segmento(df: pd.DataFrame, segmento: str, meta: float):
    if segmento == "Migração":
        render_hero(
            "Migração — Quebra de Agenda",
            "Análise estratégica dedicada às mudanças de pacotes",
            "MIGRAÇÃO",
        )
        render_card_destaque_migracao()
    elif segmento == "PME":
        render_hero(
            "PME — Quebra de Agenda",
            "Análise estratégica dedicada às Pequenas e Médias Empresas",
            "PME",
        )
        render_insight(
            "🏢 **Critério PME**: é **Novos Domicílios** (TIPO O.S contém `ADESAO`) "
            "**E** HABILIDADE DE TRABALHO contém `PME(1/100)`.",
            tipo="info",
        )
    else:
        render_hero(f"🏠 {segmento}", "Painel Operacional de Desempenho", "SEGMENTO")

    df_seg = df[df["TIPO_SERVICO"] == segmento]
    if df_seg.empty:
        st.info(f"Nenhum registro classificado como {segmento}")
        return

    m = Analise.metricas_segmento(df_seg)

    if m["quebra"] <= meta:
        render_insight(
            f"**{segmento}** está **DENTRO DA META** de {meta:.0%} (Atual: **{m['quebra']:.2%}**).",
            tipo="ok",
        )
    else:
        render_insight(
            f"**{segmento}** está **FORA DA META** de {meta:.0%} (Atual: **{m['quebra']:.2%}**). Ação requerida!",
            tipo="critico",
        )

    t1, t2, t3, t4 = st.tabs(
        [
            "📊 Visão Geral",
            "🔍 Pareto de Baixa",
            "👤 Ranking Técnicos",
            "📋 Fila de Pendentes",
        ]
    )

    with t1:
        c1, c2, c3, c4 = st.columns(4)
        render_kpi(c1, "Total Alocado", _fmt_int(m["alocado"]), tema="azul")
        render_kpi(c2, "Executadas", _fmt_int(m["exec"]), tema="verde")
        render_kpi(c3, "Não Executadas", _fmt_int(m["naoexec"]), tema="vermelho")
        render_kpi(c4, "Pendentes", _fmt_int(m["pend"]), tema="laranja")

    with t2:
        col_baixa = (
            "_COL_BAIXA"
            if "_COL_BAIXA" in df_seg.columns
            else Utils.buscar_coluna(df_seg, ["MOTIVO DE BAIXA", "CÓD DE BAIXA 1"])
        )
        df_ne = df_seg[df_seg["Status Contrato"] == "Não Executada"]

        if not df_ne.empty and col_baixa:
            df_c = df_ne.groupby(col_baixa)["TOTAL DE TAREFAS"].sum().reset_index()
            df_c.columns = ["Motivo de Baixa", "Volume"]
            df_c = df_c.sort_values("Volume", ascending=False).head(15)
            df_c["% do Total"] = df_c["Volume"] / df_c["Volume"].sum()
            df_c["Acumulado"] = df_c["% do Total"].cumsum()
            render_dataframe(
                df_c,
                titulo="Pareto de Motivos de Baixa",
                icone="search",
                fmt={"% do Total": "{:.1%}", "Acumulado": "{:.1%}", "Volume": "{:,}"},
            )
        else:
            render_insight(
                "Nenhum motivo de baixa registrado para as não executadas.", tipo="info"
            )

    with t3:
        df_tec = Analise.ranking_tecnicos(df_seg)
        render_dataframe(
            df_tec,
            titulo="Ranking de Quebra por Técnico",
            icone="person",
            badge=f"{len(df_tec)} técnicos",
            height=450,
            fmt={
                "Quebra Atual": "{:.1%}",
                "Alocado": "{:,}",
                "Executadas": "{:,}",
                "Nao_Executadas": "{:,}",
                "Considerado": "{:,}",
            },
        )

    with t4:
        df_pend = df_seg[
            df_seg["Status Contrato"]
            .str.upper()
            .isin(["PENDENTE", "PENDING", "ABERTO", "EM ABERTO"])
        ]
        cols = [
            c
            for c in ["CONTRATO", "TÉCNICO", "MONITOR", "REGIÃO", "FLAG_GPON"]
            if c in df_pend.columns
        ]
        render_dataframe(
            df_pend[cols],
            titulo="Fila de Ordens Pendentes",
            icone="list_alt",
            badge=f"{len(df_pend)} pendentes",
            height=450,
        )


def view_criterios(df: pd.DataFrame):
    render_section_header("target", "Critérios de Classificação", "Regras Oficiais")
    render_painel_criterios(df)


def _filtrar_base_analitica(
    df: pd.DataFrame, colunas: list[str], busca: str = ""
) -> pd.DataFrame:
    """Seleciona colunas e aplica uma busca literal, sem alterar a base original."""
    resultado = df.loc[:, colunas].copy()
    termo = busca.strip().upper()
    if not termo:
        return resultado

    corresponde = pd.Series(False, index=resultado.index)
    for coluna in resultado.columns:
        corresponde |= (
            resultado[coluna]
            .astype(str)
            .str.upper()
            .str.contains(termo, na=False, regex=False)
        )
    return resultado.loc[corresponde]


def view_base_completa(df: pd.DataFrame, df_full: pd.DataFrame):
    if df.empty:
        st.info("Nenhum registro disponível na base.")
        return

    render_section_header("link", "Qualidade do Mapeamento", "Google Sheets")

    total_reg = len(df)
    via_merge = (
        int((df["ORIGEM_MAPEAMENTO"] == "Merge (Sheets)").sum())
        if "ORIGEM_MAPEAMENTO" in df.columns
        else 0
    )
    via_arquivo = (
        int((df["ORIGEM_MAPEAMENTO"] == "Arquivo Origem").sum())
        if "ORIGEM_MAPEAMENTO" in df.columns
        else 0
    )
    sem_map = int((df["MONITOR"] == "SEM MONITOR").sum())
    pct_map = (total_reg - sem_map) / total_reg if total_reg else 0.0

    c1, c2, c3, c4 = st.columns(4)
    render_kpi(c1, "Total Registros", _fmt_int(total_reg), tema="azul")
    render_kpi(
        c2,
        "Via Merge Sheets",
        _fmt_int(via_merge),
        f"{(via_merge / total_reg if total_reg else 0):.1%}",
        tema="verde",
    )
    render_kpi(
        c3, "Arquivo Origem", _fmt_int(via_arquivo), "Fallback aplicado", tema="laranja"
    )
    render_kpi(
        c4,
        "Taxa Mapeamento",
        f"{pct_map:.1%}",
        f"{_fmt_int(sem_map)} sem monitor",
        tema="verde" if pct_map >= 0.9 else "vermelho",
    )

    st.markdown("<br>", unsafe_allow_html=True)
    render_section_header("table_view", "Base Analítica Filtrada")

    with st.expander("⚙️ Configurar Colunas e Filtros da Tabela", expanded=False):
        cfg1, cfg2 = st.columns([1, 2])
        with cfg1:
            modo = st.radio(
                "Visualização",
                ["Essenciais", "Todas as colunas", "Personalizado"],
                key="base_modo_cols",
            )
            n_linhas = st.number_input(
                "Máx. Linhas", 100, 50000, 1000, 100, key="base_n_linhas"
            )
        with cfg2:
            cols_disp = list(df.columns)
            if modo == "Essenciais":
                cols_sel = [c for c in Config.COLS_BASE_PRIORITARIAS if c in df.columns]
            elif modo == "Todas as colunas":
                cols_sel = cols_disp
            else:
                default_cols = [
                    c for c in Config.COLS_BASE_PRIORITARIAS if c in df.columns
                ]
                cols_sel = st.multiselect(
                    "Colunas", cols_disp, default=default_cols, key="base_cols_custom"
                )
            busca = st.text_input(
                "🔎 Buscar texto em qualquer coluna...", "", key="base_busca"
            )

    if not cols_sel:
        st.info("Selecione ao menos uma coluna para visualizar.")
        return

    df_view = _filtrar_base_analitica(df, cols_sel, busca)
    limite_linhas = int(n_linhas)
    if len(df_view) > limite_linhas:
        st.caption(
            f"Exibindo {limite_linhas:,} de {len(df_view):,} registros filtrados. "
            "A exportação inclui todos os resultados da busca."
        )
    render_dataframe(
        df_view.head(limite_linhas),
        titulo="Registros da Base Analítica",
        icone="table_view",
        badge=f"{len(df_view):,} filtrados".replace(",", "."),
        height=420,
    )

    # ── Exportações ──
    st.markdown("<br>", unsafe_allow_html=True)
    render_section_header("download", "Exportação de Bases")

    e1, e2, e3 = st.columns(3)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    with e1:
        st.download_button(
            "📥 Base Filtrada (Excel)",
            Utils.gerar_excel(df_view, "Filtrada"),
            f"base_filtrada_{stamp}.xlsx",
            use_container_width=True,
        )
    with e2:
        st.download_button(
            "📦 Base Completa (Excel)",
            Utils.gerar_excel(df_full, "Completa"),
            f"base_completa_{stamp}.xlsx",
            use_container_width=True,
        )
    with e3:
        sem_mon = df[df["MONITOR"] == "SEM MONITOR"]
        st.download_button(
            "⚠️ Sem Monitor (Excel)",
            Utils.gerar_excel(
                sem_mon if not sem_mon.empty else pd.DataFrame({"Info": ["Nenhum"]}),
                "Sem_Monitor",
            ),
            f"sem_monitor_{stamp}.xlsx",
            use_container_width=True,
            disabled=sem_mon.empty,
        )

    st.markdown("<br>", unsafe_allow_html=True)
    render_debug_criterios(df_full, expanded=False)
    render_lista_colunas(df_full, expanded=False)


# ═══════════════════════════════════════════════════════
# EXECUÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════
def main():
    st.set_page_config(
        page_title="Quebra Operacional | TOTALE",
        page_icon="📉",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    aplicar_estilo()

    if "df_memoria" not in st.session_state or st.session_state["df_memoria"] is None:
        render_hero(
            titulo="Gestão de Quebra de Agenda",
            subtitulo="Importe a base operacional para gerar o Super Relatório Consolidado",
            badge="SISTEMA TOTALE",
        )
        render_upload_base_operacional(
            "quebra",
            titulo="Carregar Base de Dados",
            recarregar_apos_envio=True,
        )
        return

    df_full = st.session_state["df_memoria"]
    if not isinstance(df_full, pd.DataFrame):
        st.error("A base carregada não é válida. Troque ou envie a base novamente.")
        return

    df_full = DataLoader.compatibilizar_base(df_full)
    monitor_disponivel = not bool(df_full.attrs.get("coluna_monitor_ausente", False))
    # 🛡️ Garante que TIPO_SERVICO exista mesmo com cache antigo em sessão
    if "TIPO_SERVICO" not in df_full.columns:
        df_full, _ = classificar_tipo_servico(df_full)
    st.session_state["df_memoria"] = df_full

    # ── SIDEBAR ──
    with st.sidebar:
        st.header("🎯 Filtros Globais")

        mons = ["Todos"] + sorted(
            str(x) for x in df_full["MONITOR"].dropna().unique() if str(x).strip() != ""
        )
        sel_mon = st.selectbox("👔 Monitor", mons)
        df_filt = (
            df_full if sel_mon == "Todos" else df_full[df_full["MONITOR"] == sel_mon]
        )

        tecs = ["Todos"] + sorted(
            str(x) for x in df_filt["TÉCNICO"].dropna().unique() if str(x).strip() != ""
        )
        sel_tec = st.selectbox("👤 Técnico", tecs)
        df = df_filt if sel_tec == "Todos" else df_filt[df_filt["TÉCNICO"] == sel_tec]

        if Config.COL_REGIAO in df_full.columns:
            regs = ["Todas"] + sorted(
                str(x) for x in df_full[Config.COL_REGIAO].dropna().unique()
            )
            sel_reg = st.selectbox("📍 Região", regs)
            if sel_reg != "Todas":
                df = df[df[Config.COL_REGIAO] == sel_reg]

        st.header("⚙️ Base de dados")
        render_status_upload()
        if st.button(
            "📁 Trocar base",
            use_container_width=True,
            help=(
                "Limpa as bases operacionais da sessão e volta ao envio "
                "manual. Vale para Quebra, Volumetria e Rota Inicial, "
                "que compartilham o mesmo arquivo."
            ),
        ):
            limpar_bases_operacionais()
            st.rerun()

        with st.expander("Opções avançadas", expanded=False):
            if st.button("🔗 Atualizar Lista de Ativos", use_container_width=True):
                arquivo = st.session_state.get("quebra_arquivo")
                if arquivo:
                    DataLoader.buscar_gsheets.clear()
                    limpar_cache_lista_ativos()
                    gs = DataLoader.buscar_gsheets()
                    raw = DataLoader.ler_arquivo(*arquivo)
                    st.session_state["df_memoria"] = DataLoader.preparar_base(
                        raw,
                        gs,
                        gs.attrs.get("fonte_ativos", ""),
                        gs.attrs.get("erro_ativos", ""),
                    )
                    st.rerun()
                else:
                    st.warning(
                        "O arquivo original não está mais nesta sessão. Use "
                        "**📁 Trocar base** e envie o arquivo novamente."
                    )

    # ── HERO TOPO ──
    render_hero(
        "Super Relatório de Quebra de Agenda",
        "Análise Executiva Consolidada por Segmento e Monitor",
        "TOTALE",
    )

    d_imp = df_full.attrs.get("diag_importado", len(df_full))
    d_susp = df_full.attrs.get("diag_susp", 0)
    d_inv = df_full.attrs.get("diag_inv", 0)
    d_fin = df_full.attrs.get("diag_final", len(df_full))
    n_mon = df_full[df_full["MONITOR"] != "SEM MONITOR"]["MONITOR"].nunique()

    met = extrair_metricas_criterios(df_full)

    render_insight(
        f"Base: **{_fmt_int(d_imp)}** importados · **{_fmt_int(d_susp)}** suspensos e "
        f"**{_fmt_int(d_inv)}** inválidos removidos · **{_fmt_int(d_fin)}** ativas · "
        f"**{n_mon}** monitores · "
        f"🔄 AND Migração: **{_fmt_int(met.get('criterio_and_migracao', 0))}** tarefas · "
        f"🏢 AND PME: **{_fmt_int(met.get('criterio_and_pme', 0))}** tarefas",
        tipo="info" if n_mon > 0 else "alerta",
    )

    # Nunca apresentar "SEM MONITOR" como se fosse um resultado válido do Sheets.
    erro_ativos = df_full.attrs.get("erro_ativos", "")
    vinculados = df_full.attrs.get("diag_vinculados", 0)
    if not monitor_disponivel:
        st.warning(
            "⚠️ A base carregada não contém uma coluna de monitor. "
            "Os registros foram mantidos como SEM MONITOR; atualize ou reenvie "
            "uma base com essa informação."
        )
    elif erro_ativos:
        st.warning(
            f"⚠️ {erro_ativos} Os dados da matriz podem usar apenas o arquivo enviado."
        )
    elif not vinculados:
        st.warning(
            "⚠️ Nenhum login da base corresponde à lista_ativos. "
            "Confira a coluna de login no arquivo e na planilha "
            f"(coluna detectada: {df_full.attrs.get('diag_login') or 'nenhuma'}). "
            "Se a planilha foi ajustada há pouco, use **🔗 Atualizar Lista de "
            "Ativos** na barra lateral para refazer o vínculo."
        )
    elif n_mon == 0:
        st.warning(
            "⚠️ Logins vinculados, mas nenhum monitor preenchido. "
            "Confira a coluna Monitor na lista_ativos."
        )
    else:
        st.caption(
            f"🔗 Lista de Ativos: {df_full.attrs.get('fonte_ativos', 'Google Sheets')} · "
            f"{_fmt_int(vinculados)} de {_fmt_int(len(df_full))} registros vinculados "
            f"({_fmt_int(df_full.attrs.get('diag_ativos', 0))} logins na lista)."
        )

    # ── ABAS PRINCIPAIS ──
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "🏢 Visão Executiva",
            "🏠 Novos Domicílios",
            "🔄 Migração",
            "🏢 PME",
            "🎯 Critérios",
            "📋 Base Completa",
        ]
    )

    with tab1:
        view_executiva(df, Config.SLA_GERAL)
    with tab2:
        view_segmento(df, "Novos Domicílios", Config.SLA_GERAL)
    with tab3:
        view_segmento(df, "Migração", Config.SLA_MIGRACAO)
    with tab4:
        view_segmento(df, "PME", Config.SLA_PME)
    with tab5:
        view_criterios(df)
    with tab6:
        view_base_completa(df, df_full)


if __name__ == "__main__":
    main()
