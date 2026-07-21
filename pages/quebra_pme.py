"""
Página dedicada à análise do segmento PME.
Coloque em pages/ para navegação automática.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Adiciona a pasta 'pages' ao sys.path para permitir importar 'quebra'
sys.path.insert(0, str(Path(__file__).resolve().parent))

from datetime import datetime
from typing import Any, Dict

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# Importa tudo do arquivo principal
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

st.set_page_config(page_title="PME — Quebra de Agenda", page_icon="🏢", layout="wide")

for k in ("df_memoria", "pdf_pme"):
    st.session_state.setdefault(k, None)


ACOES_PME = [
    (
        "🟡 MÉDIA",
        "Verificar disponibilidade de técnicos habilitados em PME para redistribuição de carteira nas regiões críticas.",
        "acao",
    ),
    (
        "🟡 MÉDIA",
        "Acionar equipe comercial PME para comunicação proativa com clientes com agenda em risco de quebra.",
        "acao",
    ),
    (
        "🟢 BAIXA",
        "Revisar janelas de atendimento PME — clientes empresariais têm menor flexibilidade de horário.",
        "info",
    ),
]

FMT_QUEBRA = {
    "Quebra Atual": "{:.2%}",
    "Fechamento Otimista": "{:.2%}",
    "Fechamento Base": "{:.2%}",
    "Fechamento Pessimista": "{:.2%}",
}


def main():
    aplicar_estilo()

    st.markdown(
        '<div class="hero" style="background: linear-gradient(135deg, #4C1D95 0%, #7C3AED 100%);">'
        "<h1>🏢 PME — Quebra de Agenda</h1>"
        "<p>Análise estratégica dedicada às Pequenas e Médias Empresas</p>"
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
        st.header("🎯 Filtros PME")

        monitores = ["Todos"] + sorted(
            str(x)
            for x in df_full["MONITOR"].dropna().unique()
            if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
        )
        sel_mon = st.selectbox("👔 Monitor", monitores, key="mon_pme")
        df_filt = (
            df_full if sel_mon == "Todos" else df_full[df_full["MONITOR"] == sel_mon]
        )

        tecnicos = ["Todos"] + sorted(
            str(x)
            for x in df_filt["TÉCNICO"].dropna().unique()
            if str(x) not in {"nan", "NÃO MAPEADO"}
        )
        sel_tec = st.selectbox("👤 Técnico", tecnicos, key="tec_pme")
        df = df_filt if sel_tec == "Todos" else df_filt[df_filt["TÉCNICO"] == sel_tec]

        st.divider()
        st.subheader("🔮 Probabilidades")
        p_ot = st.slider("Otimista (%)", 0, 100, 15, 5, key="pot_pme") / 100.0
        p_base = st.slider("Base (%)", 0, 100, 20, 5, key="pbase_pme") / 100.0
        p_pess = st.slider("Pessimista (%)", 0, 100, 50, 5, key="ppess_pme") / 100.0

        st.divider()
        sla_meta = (
            st.number_input(
                "Meta SLA PME (%)", 0.0, 100.0, 20.0, 1.0, key="sla_pme_v"
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

    df_seg = df[df["TIPO_SERVICO"] == "PME"].copy()
    if df_seg.empty:
        st.info("⚠️ Nenhum registro classificado como PME nos filtros atuais.")
        return

    m_seg = Motor.projetar(df_seg, p_base)
    render_segmento_header("PME", m_seg["quebra_atual"], sla_meta)
    render_alerta_sla(m_seg["quebra_atual"], sla_meta, "PME")
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
        _sub_visao_geral(df_seg, m_seg, p_ot, p_base, p_pess, sla_meta, "PME")

    with sub2:
        _sub_causa_raiz(df_seg, "PME")

    with sub3:
        _sub_tecnicos(df_seg, "PME", p_base, min_aloc, top_n, sla_meta)

    with sub4:
        _sub_plano_acao(df_seg, "PME", p_base, sla_meta, ACOES_PME)


# ============================================================
# SUB-ABAS
# ============================================================
def _sub_visao_geral(df_seg, m_seg, p_ot, p_base, p_pess, sla_meta, tipo):
    render_section(f"📊 Resumo Operacional — {tipo}")
    cols = st.columns(5)
    kpis = [
        ("Alocado", f"{int(m_seg['alocado']):,}", "azul", ""),
        ("Executadas", f"{int(m_seg['exec']):,}", "verde", ""),
        ("Não Exec.", f"{int(m_seg['naoexec']):,}", "laranja", ""),
        ("Pendentes", f"{int(m_seg['pend']):,}", "cinza", ""),
        (
            "Quebra Atual",
            f"{m_seg['quebra_atual']:.2%}",
            "vermelho" if m_seg["quebra_atual"] > sla_meta else "verde",
            f"Meta: {sla_meta:.0%}",
        ),
    ]
    for c, (lab, val, tema, sub) in zip(cols, kpis):
        render_kpi(c, lab, val, sub=sub, tema=tema)

    st.markdown("")
    render_section("🔮 Projeções de Fechamento")
    cen = {
        n: Motor.projetar(df_seg, p)
        for n, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]
    }
    c_cen, c_gauge = st.columns([2, 3])
    with c_cen:
        for nome, cd in cen.items():
            cor = "vermelho" if cd["fechamento_proj"] > sla_meta else "verde"
            render_kpi_sm(
                st,
                nome,
                f"{cd['fechamento_proj']:.2%}",
                sub=f"Não Exec. proj.: {int(cd['naoexec_proj']):,}",
                tema=cor,
            )
    with c_gauge:
        cor_bar = "#EF4444" if m_seg["quebra_atual"] > sla_meta else "#10B981"
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number+delta",
                value=m_seg["quebra_atual"] * 100,
                delta={
                    "reference": sla_meta * 100,
                    "increasing": {"color": "#EF4444"},
                    "decreasing": {"color": "#10B981"},
                    "suffix": "%",
                },
                number={"suffix": "%", "font": {"size": 40}},
                gauge={
                    "axis": {"range": [0, 50], "ticksuffix": "%"},
                    "bar": {"color": cor_bar},
                    "steps": [
                        {"range": [0, sla_meta * 100], "color": "#DCFCE7"},
                        {"range": [sla_meta * 100, sla_meta * 120], "color": "#FEF9C3"},
                        {"range": [sla_meta * 120, 50], "color": "#FEE2E2"},
                    ],
                    "threshold": {
                        "line": {"color": "#DC2626", "width": 3},
                        "thickness": 0.85,
                        "value": sla_meta * 100,
                    },
                },
                title={"text": f"Quebra vs. Meta {sla_meta:.0%}", "font": {"size": 14}},
            )
        )
        fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("")
    render_section("🛡️ Folga de SLA")
    folga = Motor.folga_sla(df_seg, sla_meta)
    f1, f2, f3 = st.columns(3)
    cor_f = (
        "vermelho"
        if folga["estourado"]
        else ("verde" if folga["folga_ne_pendente"] > 0 else "laranja")
    )
    render_kpi(
        f1,
        "Folga (OS)",
        f"{int(np.floor(folga['folga_ne_pendente'])):,}",
        sub="Não Exec. ainda permitidas",
        tema=cor_f,
    )
    render_kpi(
        f2,
        "Execução Mínima",
        f"{int(np.ceil(folga['precisa_executar_pendente'])):,}",
        sub="Pendentes que devem ser executadas",
        tema="azul",
    )
    render_kpi(
        f3,
        "Limite NE Total",
        f"{int(folga['limite_ne_total']):,}",
        sub=f"= {sla_meta:.0%} × {int(folga['alocado']):,}",
        tema="cinza",
    )
    st.progress(min(1.0, max(0.0, float(m_seg["quebra_atual"] / (sla_meta * 2)))))


def _sub_causa_raiz(df_seg, tipo):
    render_section(f"🔍 Causa Raiz — {tipo}")
    df_c = Motor.causa_raiz_segmento(df_seg, tipo, "_COL_BAIXA", top_n=8)
    if df_c.empty:
        render_insight(
            "Coluna de código/motivo de baixa não identificada.", tipo="alerta"
        )
        return

    c_tab, c_chart = st.columns([1.2, 2])
    with c_tab:
        render_dataframe(
            df_c,
            titulo=f"Top Motivos — {tipo}",
            icone="🔍",
            fmt={"% do Total": "{:.2%}", "Acumulado": "{:.2%}"},
            height=350,
        )
    with c_chart:
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=df_c["Motivo de Baixa"],
                y=df_c["Volume"],
                name="Volume",
                marker_color="#EF4444",
                text=df_c["Volume"],
                textposition="outside",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_c["Motivo de Baixa"],
                y=df_c["Acumulado"],
                name="Acumulado %",
                yaxis="y2",
                mode="lines+markers",
                line=dict(color="#0EA5E9", width=2),
                marker=dict(size=7),
            )
        )
        fig.update_layout(
            title=f"Pareto de Motivos — {tipo}",
            yaxis=dict(title="Volume"),
            yaxis2=dict(
                title="Acumulado %",
                overlaying="y",
                side="right",
                tickformat=".0%",
                range=[0, 1.1],
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=380,
            xaxis=dict(tickangle=-30),
        )
        fig.add_hline(
            y=0.8,
            line_dash="dot",
            line_color="#F59E0B",
            yref="y2",
            annotation_text="80%",
            annotation_position="top right",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if len(df_c) >= 2:
        t1, t2 = df_c.iloc[0], df_c.iloc[1]
        render_insight(
            f"Os 2 principais motivos (<strong>{t1['Motivo de Baixa']}</strong> e "
            f"<strong>{t2['Motivo de Baixa']}</strong>) respondem por "
            f"<strong>{t2['Acumulado']:.1%}</strong> das quebras em {tipo}.",
            tipo="acao",
        )


def _sub_tecnicos(df_seg, tipo, p_base, min_aloc, top_n, sla_meta):
    render_section(f"👤 Técnicos com Maior Quebra — {tipo}")
    df_tec = Motor.tecnicos_criticos(df_seg, tipo, p_base, float(min_aloc), int(top_n))
    if df_tec.empty:
        render_insight(
            f"Não há técnicos com volume mínimo de {int(min_aloc)} OS.", tipo="info"
        )
        return

    render_dataframe(
        df_tec,
        titulo=f"Técnicos Críticos — {tipo}",
        icone="🚨",
        fmt=FMT_QUEBRA,
        color_col="Fechamento Base",
        color_meta=sla_meta,
        color_invertido=True,
        height=450,
    )
    st.download_button(
        f"📥 Exportar Técnicos {tipo}",
        Utils.gerar_excel(df_tec, f"Tec_{tipo[:25]}"),
        f"tecnicos_{tipo.lower()}.xlsx",
        key=f"dl_tec_{tipo}",
    )

    df_plot = df_tec.head(10).sort_values("Fechamento Base")
    cores = [
        "#EF4444" if v > sla_meta else "#10B981" for v in df_plot["Fechamento Base"]
    ]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df_plot["TÉCNICO"],
            x=df_plot["Fechamento Base"],
            orientation="h",
            marker_color=cores,
            text=[f"{v:.1%}" for v in df_plot["Fechamento Base"]],
            textposition="outside",
        )
    )
    fig.add_vline(
        x=sla_meta,
        line_dash="dash",
        line_color="#DC2626",
        annotation_text=f"Meta {sla_meta:.0%}",
    )
    fig.update_layout(
        title=f"Quebra Projetada por Técnico — {tipo}",
        xaxis_tickformat=".1%",
        height=max(300, len(df_plot) * 36),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    acima = (df_tec["Fechamento Base"] > sla_meta).sum()
    pct = acima / len(df_tec)
    if pct > 0.5:
        render_insight(
            f"<strong>{acima} de {len(df_tec)}</strong> técnicos ({pct:.0%}) "
            f"estão acima da meta. Avalie redistribuição de carteira.",
            tipo="critico",
        )
    elif acima > 0:
        render_insight(
            f"<strong>{acima} técnico(s)</strong> com quebra acima da meta.",
            tipo="alerta",
        )
    else:
        render_insight(f"Todos os técnicos dentro da meta em {tipo}.", tipo="ok")

def _sub_plano_acao(df_seg, tipo, p_base, sla_meta, acoes_especificas):
    render_section(f"🎯 Plano de Ação — {tipo}")
    folga = Motor.folga_sla(df_seg, sla_meta)
    cen = Motor.projetar(df_seg, p_base)
    excesso = max(0.0, folga["naoexec"] - folga["limite_ne_total"])
    pend_exec = folga["precisa_executar_pendente"]

    col_d, col_a = st.columns([1, 1.5])
    with col_d:
        render_section("📋 Diagnóstico")
        render_kpi_sm(
            st,
            "Excesso de NE",
            f"{int(excesso):,}",
            sub="OS além do permitido",
            tema="vermelho" if excesso > 0 else "verde",
        )
        render_kpi_sm(
            st,
            "Pendentes a Executar",
            f"{int(np.ceil(pend_exec)):,}",
            sub=f"Mínimo para atingir meta {sla_meta:.0%}",
            tema="azul",
        )
        render_kpi_sm(
            st,
            "Proj. Base",
            f"{cen['fechamento_proj']:.2%}",
            sub=f"c/ {p_base:.0%} de quebra",
            tema="vermelho" if cen["fechamento_proj"] > sla_meta else "verde",
        )
        st.markdown("")
        if folga["pend"] > 0:
            tx = 1 - (folga["folga_ne_pendente"] / folga["pend"])
            st.markdown(f"**Taxa mínima de execução:** `{max(0, tx):.1%}`")
            st.progress(min(1.0, max(0.0, float(tx))))

    with col_a:
        render_section("✅ Ações Recomendadas")
        acoes = []
        if folga["estourado"]:
            acoes.append(
                (
                    "🔴 IMEDIATA",
                    f"Acionar plantão para recuperar {int(excesso):,} OS não executadas acima do limite.",
                    "critico",
                )
            )
        if pend_exec > 0:
            acoes.append(
                (
                    "🟠 ALTA",
                    f"Garantir execução de pelo menos {int(np.ceil(pend_exec)):,} OS pendentes de {tipo}.",
                    "alerta",
                )
            )
        acoes.extend(acoes_especificas)
        for pri, ac, tp in acoes:
            render_insight(f"<strong>{pri}</strong> — {ac}", tipo=tp)

    st.markdown("")
    df_plano = pd.DataFrame(
        [{"Segmento": tipo, "Prioridade": p, "Ação": a} for p, a, _ in acoes]
    )
    if not df_plano.empty:
        st.download_button(
            f"📥 Exportar Plano — {tipo}",
            Utils.gerar_excel(df_plano, f"Plano_{tipo[:25]}"),
            f"plano_{tipo.lower()}.xlsx",
            key=f"dl_plano_{tipo}",
        )


if __name__ == "__main__":
    main()