"""
Gestão de Volumetria
Arquivo: pages/volumetria.py
"""

from __future__ import annotations

from io import BytesIO
from typing import Any, cast

import numpy as np
import pandas as pd
import streamlit as st
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

# ====================================================
# IMPORTAÇÃO DOS COMPONENTES CORPORATIVOS
# ====================================================
from components.calendario import InfoCalendario
from components.componentes import (
    aplicar_estilo,
    render_dataframe,
    render_hero,
    render_insight,
    render_kpi,
    render_section_header,
)

from components.upload_base import (
    limpar_bases_operacionais,
    render_status_upload,
    render_upload_base_operacional,
)

# ==========================================================
# CONFIGURAÇÃO E CONSTANTES
# ==========================================================
st.set_page_config(
    page_title="Volumetria",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


class Config:
    COL_STATUS = "STATUS CONTRATO"
    COL_TOTAL = "TOTAL DE TAREFAS"
    COL_TECNICO = "TÉCNICO"
    COL_MONITOR = "MONITOR"
    COL_REGIAO = "REGIÃO"

    STATUS_ORDEM = ["Executada", "Não Executada", "Pendente"]


# ==========================================================
# CÁLCULOS
# ==========================================================
def calcular_kpis(df: pd.DataFrame) -> dict[str, Any]:
    if df.empty:
        return {
            "total": 0,
            "executadas": 0,
            "nao_executadas": 0,
            "pendentes": 0,
            "baixadas": 0,
            "taxa": 0.0,
            "quebra": 0.0,
            "projecao": 0,
        }
    k_tot = int(round(df[Config.COL_TOTAL].sum()))
    k_exe = int(df[df[Config.COL_STATUS] == "Executada"][Config.COL_TOTAL].sum())
    k_nex = int(df[df[Config.COL_STATUS] == "Não Executada"][Config.COL_TOTAL].sum())
    k_pen = int(df[df[Config.COL_STATUS] == "Pendente"][Config.COL_TOTAL].sum())
    k_bai = k_exe + k_nex
    k_tx = k_exe / k_bai if k_bai > 0 else 0.0
    k_proj = int(k_exe + k_tx * k_pen)

    return {
        "total": k_tot,
        "executadas": k_exe,
        "nao_executadas": k_nex,
        "pendentes": k_pen,
        "baixadas": k_bai,
        "taxa": k_tx,
        "quebra": 1.0 - k_tx,
        "projecao": k_proj,
    }


def calcular_volumetria(df: pd.DataFrame, grupos: list[str]) -> pd.DataFrame:
    tabela = (
        df.groupby(grupos + [Config.COL_STATUS], observed=True)[Config.COL_TOTAL]
        .sum()
        .unstack(Config.COL_STATUS, fill_value=0)
        .reset_index()
    )
    for s in Config.STATUS_ORDEM:
        if s not in tabela.columns:
            tabela[s] = 0
        tabela[s] = tabela[s].astype(int)

    tabela["Baixadas"] = tabela["Executada"] + tabela["Não Executada"]
    tabela["Total Alocado"] = tabela["Baixadas"] + tabela["Pendente"]
    tabela["Taxa Execução"] = np.where(
        tabela["Baixadas"] > 0, tabela["Executada"] / tabela["Baixadas"], 0.0
    )
    tabela["Taxa Quebra"] = 1.0 - tabela["Taxa Execução"]
    tabela["Projeção"] = (
        tabela["Executada"] + tabela["Taxa Execução"] * tabela["Pendente"]
    ).astype(int)

    if Config.COL_TECNICO in df.columns:
        n_tec = (
            df.groupby(grupos, observed=True)[Config.COL_TECNICO]
            .nunique()
            .reset_index(name="Técnicos")
        )
        tabela = tabela.merge(n_tec, on=grupos, how="left")
        tabela["Técnicos"] = tabela["Técnicos"].fillna(0).astype(int)
        tabela["OS/Técnico"] = np.where(
            tabela["Técnicos"] > 0, tabela["Total Alocado"] / tabela["Técnicos"], 0.0
        )
        tabela["Exec/Técnico"] = np.where(
            tabela["Técnicos"] > 0, tabela["Executada"] / tabela["Técnicos"], 0.0
        )

    return tabela.sort_values("Total Alocado", ascending=False)


def gerar_excel(df: pd.DataFrame, nome_aba: str) -> bytes:
    output = BytesIO()
    export = df.copy()

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name=nome_aba[:31])
        ws = writer.sheets[nome_aba[:31]]
        hf = PatternFill("solid", fgColor="0F172A")

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        for cell in ws[1]:
            cell.fill = hf
            cell.font = Font(color="FFFFFF", bold=True)

        for i, col in enumerate(export.columns, 1):
            valores = export[col].head(500).astype(str)
            maior = max([len(str(col))] + [len(v) for v in valores], default=10)
            ws.column_dimensions[get_column_letter(i)].width = min(
                max(maior + 2, 12), 40
            )

    output.seek(0)
    return output.getvalue()


# ==========================================================
# MAIN
# ==========================================================
def main():
    # ── APLICA ESTILO CORPORATIVO ─────────────────────────
    aplicar_estilo()

    # ── HERO ──────────────────────────────────────────────
    render_hero(
        titulo="Gestão de Volumetria",
        subtitulo="Análise executiva de performance e projeções operacionais",
        badge="Operações",
    )

    if "base_data" not in st.session_state:
        st.session_state.base_data = None

    # ── SIDEBAR: BASE DE DADOS ────────────────────────────
    with st.sidebar:
        st.header("⚙️ Base de dados")
        render_status_upload()

        if st.session_state.base_data is not None:
            diag = st.session_state.base_data.attrs.get("diagnostico", {})
            st.write(f"📥 **Entrada:** {diag.get('Inicial', 0)}")
            st.write(f"🗑️ **Vazios:** {diag.get('Removidos por contrato vazio', 0)}")
            st.write(f"📈 **Processadas:** {diag.get('Final', 0)}")
            st.divider()
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

    # ── UPLOAD MANUAL ─────────────────────────────────────
    if st.session_state.base_data is None:
        render_upload_base_operacional(
            "volumetria",
            titulo="Importação Manual",
            recarregar_apos_envio=True,
        )
        return

    df_full = st.session_state.base_data

    # ── FILTROS (SIDEBAR) ──────────────────────────────────
    with st.sidebar:
        st.header("🎯 Filtros")
        mons = sorted(df_full[Config.COL_MONITOR].dropna().astype(str).unique())
        sel_m = st.multiselect("Monitor", mons, default=mons)

        regs = sorted(df_full[Config.COL_REGIAO].dropna().astype(str).unique())
        sel_r = st.multiselect("Região", regs, default=regs)

        tecnicos = sorted(df_full[Config.COL_TECNICO].dropna().astype(str).unique())
        sel_t = st.multiselect("Técnico", tecnicos, default=tecnicos)

        statuses = Config.STATUS_ORDEM
        sel_s = st.multiselect("Status", statuses, default=statuses)

        if st.button("↩️ Limpar filtros", use_container_width=True):
            st.rerun()

    # Aplicação dos filtros
    df = df_full[
        df_full[Config.COL_MONITOR].isin(sel_m)
        & df_full[Config.COL_REGIAO].isin(sel_r)
        & df_full[Config.COL_TECNICO].isin(sel_t)
        & df_full[Config.COL_STATUS].isin(sel_s)
    ]

    if df.empty:
        st.warning("Nenhum dado selecionado.")
        return

    # ── RESULTADO DA BASE (INSIGHT) ────────────────────────
    regioes_ativas = ", ".join(sorted(df[Config.COL_REGIAO].unique()))
    render_insight(
        f"**Resultado da Base:** Foram encontrados **{len(df):,}** registros. <br>Regiões ativas: **{regioes_ativas}**",
        tipo="info",
    )

    # ── KPIs DE VOLUME ─────────────────────────────────────
    kpis = calcular_kpis(df)

    render_section_header("query_stats", "Resumo de Volume")
    c1, c2, c3, c4 = st.columns(4)
    render_kpi(
        c1,
        "Total Alocado",
        f"{kpis['total']:,}",
        f"{kpis['pendentes']:,} pendentes",
        tema="azul",
    )
    render_kpi(
        c2,
        "Executadas",
        f"{kpis['executadas']:,}",
        f"Taxa: {kpis['taxa']:.1%}",
        tema="verde",
    )
    render_kpi(
        c3,
        "Não Executadas",
        f"{kpis['nao_executadas']:,}",
        f"Quebra: {kpis['quebra']:.1%}",
        tema="vermelho",
    )
    render_kpi(
        c4,
        "Projeção Final",
        f"{kpis['projecao']:,}",
        "Baseado na taxa atual",
        tema="laranja",
    )

    # ── CALENDÁRIO (SEG–SÁB, SEM DOMINGOS NEM FERIADOS) ────
    cal = InfoCalendario.calcular()
    feriados_restantes = ", ".join(
        f"{d.strftime('%d/%m')} ({nome})" for d, nome in cal.feriados_restantes[:4]
    )
    render_insight(
        f"🗓️ **{cal.nome_mes}:** {cal.dias_passados} dias úteis já passados e "
        f"**{cal.dias_faltantes}** restantes (segunda a sábado, sem domingos "
        f"nem feriados)."
        + (f" Feriados restantes: {feriados_restantes}." if feriados_restantes else ""),
        tipo="info",
    )

    # ── ABAS PRINCIPAIS ────────────────────────────────────
    t1, t2 = st.tabs(["👥 Equipes", "📋 Base de Dados"])

    with t1:
        te = calcular_volumetria(df, [Config.COL_REGIAO, Config.COL_MONITOR])

        # Formatação das colunas para inteiros, % e decimais via dicionário formatador
        formato = {
            "Executada": "{:,}",
            "Não Executada": "{:,}",
            "Pendente": "{:,}",
            "Baixadas": "{:,}",
            "Total Alocado": "{:,}",
            "Projeção": "{:,}",
            "Técnicos": "{:,}",
            "Taxa Execução": "{:.1%}",
            "Taxa Quebra": "{:.1%}",
            "OS/Técnico": "{:.1f}",
            "Exec/Técnico": "{:.1f}",
        }

        render_dataframe(
            te,
            titulo="Volumetria por Equipe",
            icone="groups",
            fmt=cast(Any, formato),
            badge=f"{len(te)} equipes",
            subtitulo="Consolidado por região e monitor",
            height=500,
        )

        st.download_button(
            "📥 Baixar Relatório (Excel)",
            gerar_excel(te, "Equipes"),
            "volumetria_equipes.xlsx",
            use_container_width=True,
        )

    with t2:
        render_dataframe(
            df.head(500),
            titulo="Visualização da Base (limite 500 linhas)",
            icone="table_rows",
            fmt={"TOTAL DE TAREFAS": "{:,.0f}"},
            badge=f"{len(df):,} na base".replace(",", "."),
            height=500,
        )


if __name__ == "__main__":
    main()
