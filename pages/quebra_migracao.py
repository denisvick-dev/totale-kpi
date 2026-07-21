"""
Página dedicada à análise do segmento Migração (Mudança de Pacote + GPON).
Coloque em pages/ para navegação automática.
"""
from __future__ import annotations

import sys
from pathlib import Path

# ⬇️ Adiciona a pasta 'pages' ao sys.path para permitir importar 'quebra'
sys.path.insert(0, str(Path(__file__).resolve().parent))

from datetime import datetime

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Importa tudo do arquivo principal + reaproveita sub-abas do PME
from quebra import (
    Config,
    Motor,
    Utils,
    aplicar_estilo,
    render_alerta_sla,
    render_dataframe,
    render_insight,
    render_kpi,
    render_kpi_sm,
    render_resultado_base,
    render_section,
    render_segmento_header,
)
from quebra_pme import (
    _sub_visao_geral,
    _sub_causa_raiz,
    _sub_tecnicos,
    _sub_plano_acao,
)


st.set_page_config(
    page_title="Migração — Quebra de Agenda", page_icon="🔄", layout="wide"
)

for k in ("df_memoria", "pdf_migracao"):
    st.session_state.setdefault(k, None)


ACOES_MIGRACAO = [
    (
        "🟠 ALTA",
        "Verificar estoque de equipamentos GPON nos almoxarifados das regiões com maior quebra — falta de material é causa frequente.",
        "alerta",
    ),
    (
        "🟡 MÉDIA",
        "Confirmar certificação dos técnicos em instalação GPON. Migrações exigem habilitação técnica específica.",
        "acao",
    ),
    (
        "🟡 MÉDIA",
        "Priorizar agendamentos de migração no início do turno — instalações GPON têm tempo médio maior.",
        "acao",
    ),
    (
        "🟢 BAIXA",
        "Validar se ordens de Migração pendentes possuem pré-vistoria aprovada.",
        "info",
    ),
]

FMT_QUEBRA = {
    "Quebra Atual": "{:.2%}",
    "Fechamento Base": "{:.2%}",
    "Fechamento Otimista": "{:.2%}",
    "Fechamento Pessimista": "{:.2%}",
}


def main():
    aplicar_estilo()

    st.markdown(
        '<div class="hero" style="background: linear-gradient(135deg, #0C4A6E 0%, #0369A1 100%);">'
        "<h1>🔄 Migração — Quebra de Agenda</h1>"
        "<p>Análise estratégica de Mudança de Pacote + GPON</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.get("df_memoria") is None:
        st.warning(
            "⚠️ Nenhuma base carregada. Abra a página principal e faça o upload primeiro."
        )
        st.info("👈 Volte ao **Dashboard Geral** no menu lateral para carregar a base.")
        return

    df_full = st.session_state["df_memoria"].copy()
    if "Status Contrato" not in df_full.columns:
        col_status = Utils.buscar_coluna(df_full, ["STATUS DA O.S 1", "STATUS OS 1"])
        df_full["Status Contrato"] = (
            Utils.classificar_status(df_full[col_status]) if col_status else "Pendente"
        )

    # ── Sidebar ────────────────────────────────────────────────
    with st.sidebar:
        st.header("🎯 Filtros Migração")

        monitores = ["Todos"] + sorted(
            str(x)
            for x in df_full["MONITOR"].dropna().unique()
            if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
        )
        sel_mon = st.selectbox("👔 Monitor", monitores, key="mon_mig")
        df_filt = (
            df_full if sel_mon == "Todos" else df_full[df_full["MONITOR"] == sel_mon]
        )

        tecnicos = ["Todos"] + sorted(
            str(x)
            for x in df_filt["TÉCNICO"].dropna().unique()
            if str(x) not in {"nan", "NÃO MAPEADO"}
        )
        sel_tec = st.selectbox("👤 Técnico", tecnicos, key="tec_mig")
        df = df_filt if sel_tec == "Todos" else df_filt[df_filt["TÉCNICO"] == sel_tec]

        st.divider()
        st.subheader("🔮 Probabilidades")
        p_ot = st.slider("Otimista (%)", 0, 100, 15, 5, key="pot_mig") / 100.0
        p_base = st.slider("Base (%)", 0, 100, 25, 5, key="pbase_mig") / 100.0
        p_pess = st.slider("Pessimista (%)", 0, 100, 50, 5, key="ppess_mig") / 100.0

        st.divider()
        sla_meta = (
            st.number_input(
                "Meta SLA Migração (%)", 0.0, 100.0, 25.0, 1.0, key="sla_mig_v"
            )
            / 100
        )

        # Valores fixos (removidos da interface)
        min_aloc = 1
        top_n = 999999

    # ── Validações e renderização principal ────────────────────
    if df.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    render_resultado_base(sorted(df[Config.COL_REGIAO].unique()), len(df))

    df_seg = df[df["TIPO_SERVICO"] == "Migração"].copy()
    if df_seg.empty:
        st.info("⚠️ Nenhum registro classificado como Migração nos filtros atuais.")
        return

    m_seg = Motor.projetar(df_seg, p_base)
    render_segmento_header("Migração", m_seg["quebra_atual"], sla_meta)
    render_alerta_sla(m_seg["quebra_atual"], sla_meta, "Migração")
    st.markdown("")

    # ── Sub-abas ───────────────────────────────────────────────
    sub1, sub2, sub3, sub4 = st.tabs(
        [
            "📊 Visão Geral",
            "🔍 Causa Raiz",
            "👤 Técnicos",
            "🎯 Plano de Ação",
        ]
    )

    with sub1:
        _sub_visao_geral(df_seg, m_seg, p_ot, p_base, p_pess, sla_meta, "Migração")

    with sub2:
        _sub_causa_raiz(df_seg, "Migração")

    with sub3:
        _sub_tecnicos(df_seg, "Migração", p_base, min_aloc, top_n, sla_meta)

    with sub4:
        _sub_plano_acao(df_seg, "Migração", p_base, sla_meta, ACOES_MIGRACAO)


if __name__ == "__main__":
    main()