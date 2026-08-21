"""
Central de Performance | Painel de Consultivos e Produtos
Arquivo: pages/consultivo.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st
from io import BytesIO
from typing import Any, Optional, cast
from streamlit_gsheets import GSheetsConnection

# ====================================================
# IMPORTAÇÃO DOS COMPONENTES CORPORATIVOS
# ====================================================
from components.componentes import (
    aplicar_estilo,
    render_hero,
    render_insight,
    render_kpi,
    render_section_header,
)

# ====================================================
# 1. CONFIGURAÇÕES E UTILITÁRIOS
# ====================================================
st.set_page_config(page_title="Total de Consultivos", page_icon="📋", layout="wide")

URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"


class Calculos:
    """Lógica de negócio e cálculos de projeção/share."""

    @staticmethod
    def share(valor: float, geral: float) -> str:
        if geral == 0 or pd.isna(geral) or abs(valor - geral) < 0.0001:
            return "Visão Geral"
        return f"{(valor / geral) * 100:.1f}% do Total"

    @staticmethod
    def fator_projecao(df: pd.DataFrame) -> tuple[float, int]:
        if df.empty or "DATA" not in df.columns or df["DATA"].isna().all():
            return 1.0, 0
            
        hoje = pd.Timestamp.today().normalize()
        if df["DATA"].max().month != hoje.month or df["DATA"].max().year != hoje.year:
            return 1.0, 0

        inicio_mes = hoje.replace(day=1)
        prox_mes = inicio_mes.replace(day=28) + pd.Timedelta(days=4)
        fim_mes = prox_mes - pd.Timedelta(days=prox_mes.day)

        dias_uteis_total = len([d for d in pd.date_range(inicio_mes, fim_mes) if d.dayofweek < 6])
        dias_decorridos = len([d for d in pd.date_range(inicio_mes, hoje) if d.dayofweek < 6])
        faltantes = dias_uteis_total - dias_decorridos

        fator = dias_uteis_total / dias_decorridos if dias_decorridos > 0 and faltantes > 0 else 1.0
        return fator, faltantes


class EstiloTabela:
    """Regras de coloração condicional para o DataFrame."""

    @staticmethod
    def colorir_metas(valor: Any) -> str:
        """Destaca valores numéricos maiores que 350 com verde de sucesso."""
        try:
            numero = pd.to_numeric(valor, errors="coerce")
            if pd.notna(numero) and numero > 350:
                return "background-color: #ECFDF5; color: #065F46; font-weight: bold;"
        except (TypeError, ValueError):
            pass
        return ""


# ====================================================
# 2. PREPARAÇÃO DE DADOS
# ====================================================
@st.cache_data(ttl=300)
def carregar_hierarquia() -> pd.DataFrame:
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=URL_ATIVOS, ttl=0)
    df.columns = df.columns.str.strip()
    return df[["Login", "Técnico", "Monitor", "Base"]].drop_duplicates(subset=["Login"])


def preparar_ranking(df: pd.DataFrame, colunas_grupo: list, fator_proj: float = 1.0) -> pd.DataFrame:
    colunas_soma = ["Qtde. Cons.", "Qtde. Prod.", "Qtde. Mesh", "Qtde. TV", "Qtde. Virtua"]
    colunas_soma = [c for c in colunas_soma if c in df.columns]

    res = df.groupby(colunas_grupo, dropna=False)[colunas_soma].sum().reset_index()
    renomeios = {
        "Qtde. Cons.": "Total Consultivos",
        "Qtde. Prod.": "Total Produtos",
        "Qtde. Mesh": "Mesh",
        "Qtde. TV": "TV Box",
        "Qtde. Virtua": "Virtua",
    }
    res = res.rename(columns=renomeios).fillna(0)

    col_sort = "Total Consultivos" if "Total Consultivos" in res.columns else "Total Produtos"
    res = res.sort_values(col_sort, ascending=False)
    res.insert(0, "Posição", range(1, len(res) + 1))

    nova_ordem = ["Posição"] + colunas_grupo

    if "Total Consultivos" in res.columns:
        nova_ordem.append("Total Consultivos")
    if "Total Produtos" in res.columns:
        nova_ordem.append("Total Produtos")

    if "Total Consultivos" in res.columns and fator_proj > 1.0:
        res["Proj. Consultivos"] = (res["Total Consultivos"] * fator_proj).astype(int)
        nova_ordem.append("Proj. Consultivos")

    if "Total Produtos" in res.columns and fator_proj > 1.0:
        res["Proj. Produtos"] = (res["Total Produtos"] * fator_proj).astype(int)
        nova_ordem.append("Proj. Produtos")

    for col in ["Mesh", "TV Box", "Virtua"]:
        if col in res.columns:
            nova_ordem.append(col)

    metricas = [c for c in nova_ordem if c not in ["Posição"] + colunas_grupo]
    res[metricas] = res[metricas].astype(int)
    return res[nova_ordem]


# ====================================================
# 3. APLICAÇÃO PRINCIPAL
# ====================================================
def main():
    # ── Estilo Global e Hero ─────────────────────────────────────────
    aplicar_estilo()
    render_hero(
        titulo="Painel de Consultivos e Produtos",
        subtitulo="Análise de mix de produtos, consultivos realizados e oportunidades comerciais.",
        badge="Performance"
    )

    # ── Validação Inicial ────────────────────────────────────────────
    if "dados_cons" not in st.session_state or "Consultivo" not in st.session_state["dados_cons"]:
        st.warning("⚠️ Carregue os dados na aba principal primeiro.")
        st.stop()

    df = st.session_state["dados_cons"]["Consultivo"].copy()

    # ── Tratamento de Dados ──────────────────────────────────────────
    mapa = {
        "QTDE_CONSULTIVO": "Qtde. Cons.",
        "QTDE_PRODUTOS": "Qtde. Prod.",
        "QTDE_MESH": "Qtde. Mesh",
        "QTDE_TV": "Qtde. TV",
        "QTDE_VIRTUA": "Qtde. Virtua",
    }
    for k, v in mapa.items():
        df[v] = pd.to_numeric(df.get(k, 0), errors="coerce").fillna(0).astype(int)

    if "DATA" in df.columns:
        df["DATA"] = pd.to_datetime(df["DATA"], errors="coerce", dayfirst=True)

    try:
        df_ativos = carregar_hierarquia()
        df["LOGIN NETSALES"] = df.get("LOGIN NETSALES", "").astype(str).str.strip()
        df = df.drop(columns=["Monitor", "Base"], errors="ignore")
        df = pd.merge(df, df_ativos, left_on="LOGIN NETSALES", right_on="Login", how="outer")
    except Exception as e:
        st.error(f"Erro ao carregar hierarquia: {e}")

    df["LOGIN NETSALES"] = df["LOGIN NETSALES"].fillna(df["Login"]).fillna("SEM LOGIN")

    if "VENDEDOR" not in df.columns:
        df["VENDEDOR"] = np.nan

    df["VENDEDOR"] = (
        df["VENDEDOR"]
        .fillna(df["Técnico"])
        .fillna(df["LOGIN NETSALES"])
        .fillna("Nome Não Cadastrado")
    )
    df["Monitor"] = df["Monitor"].fillna("Não Identificado")
    df["Base"] = df["Base"].fillna("Não Identificada")

    for col in ["Qtde. Cons.", "Qtde. Prod.", "Qtde. Mesh", "Qtde. TV", "Qtde. Virtua"]:
        if col in df.columns:
            df[col] = df[col].fillna(0).astype(int)

    # ── Variáveis Globais ────────────────────────────────────────────
    t_cons = df["Qtde. Cons."].sum()
    t_prod = df["Qtde. Prod."].sum()

    # ── Filtros (Sidebar) ────────────────────────────────────────────
    st.sidebar.markdown("### 🎯 Filtros Avançados")
    base_sel = st.sidebar.selectbox("Base:", ["Todas"] + sorted(df["Base"].dropna().unique().tolist()))
    
    monitor_opts = ["Todos"] + sorted(
        df[df["Base"] == base_sel]["Monitor"].dropna().unique().tolist()
        if base_sel != "Todas" else df["Monitor"].dropna().unique().tolist()
    )
    monitor_sel = st.sidebar.selectbox("Monitor:", monitor_opts)

    if base_sel != "Todas":
        df = df[df["Base"] == base_sel]
    if monitor_sel != "Todos":
        df = df[df["Monitor"] == monitor_sel]

    # ── Cálculos Filtrados ───────────────────────────────────────────
    f_cons, f_prod = df["Qtde. Cons."].sum(), df["Qtde. Prod."].sum()
    f_mesh, f_tv, f_vir = df["Qtde. Mesh"].sum(), df["Qtde. TV"].sum(), df["Qtde. Virtua"].sum()
    
    eq_ativas = df.groupby("LOGIN NETSALES")["Qtde. Cons."].sum()
    eq_total, eq_produtivas = len(eq_ativas), len(eq_ativas[eq_ativas > 0])
    eficiencia = (eq_produtivas / eq_total) if eq_total > 0 else 0

    fator_proj, falt_dias = Calculos.fator_projecao(df)

    # ── UI: KPIs Equipes ─────────────────────────────────────────────
    render_section_header("groups", "Indicadores de Equipe")
    c1, c2, c3, c4 = st.columns(4)
    render_kpi(c1, "Total Equipes", f"{eq_total:,.0f}", tema="azul")
    render_kpi(c2, "Equipes Produtivas", f"{eq_produtivas:,.0f}", tema="verde")
    render_kpi(c3, "Técnicos Zerados", f"{eq_total - eq_produtivas:,.0f}", tema="vermelho")
    render_kpi(c4, "Eficiência (Conversão)", f"{eficiencia:.2%}", tema="cinza")

    # ── UI: Resultados Realizados ────────────────────────────────────
    render_section_header("bar_chart", "Resultado Realizado (Até o momento)")
    c5, c6, c7, c8, c9 = st.columns(5)
    render_kpi(c5, "Tot. Consultivos", f"{f_cons:,.0f}", sub=Calculos.share(f_cons, t_cons), tema="laranja")
    render_kpi(c6, "Tot. Produtos", f"{f_prod:,.0f}", sub=Calculos.share(f_prod, t_prod), tema="azul")
    render_kpi(c7, "Total Mesh", f"{f_mesh:,.0f}", tema="cinza")
    render_kpi(c8, "Total TV Box", f"{f_tv:,.0f}", tema="cinza")
    render_kpi(c9, "Total Virtua", f"{f_vir:,.0f}", tema="cinza")

    # ── UI: Projeções ────────────────────────────────────────────────
    if falt_dias > 0:
        st.markdown("<br>", unsafe_allow_html=True)
        render_insight(f"Faltam **{falt_dias} dias úteis** para o fechamento do mês.", tipo="info")
        
        render_section_header("trending_up", "Projeção Fim do Mês")
        p1, p2, _ = st.columns([1, 1, 3])
        
        proj_cons = int(f_cons * fator_proj)
        proj_prod = int(f_prod * fator_proj)
        
        render_kpi(p1, "Proj. Consultivos", f"{proj_cons:,}", sub=f"+ {proj_cons - f_cons} est.", tema="laranja")
        render_kpi(p2, "Proj. Produtos", f"{proj_prod:,}", sub=f"+ {proj_prod - f_prod} est.", tema="laranja")

    st.divider()

    # ── UI: Tabela Consolidada ───────────────────────────────────────
    col_tit, col_tog, _ = st.columns([3, 1, 1])
    with col_tit:
        render_section_header("table_view", "Visão Consolidada")
    with col_tog:
        st.markdown("<br>", unsafe_allow_html=True) # Espaçamento para alinhar
        detalhar_tec = st.toggle("Detalhar por Técnico")

    grupo = ["LOGIN NETSALES", "VENDEDOR", "Monitor", "Base"] if detalhar_tec else ["Monitor"]
    df_exibir = preparar_ranking(df, grupo, fator_proj)

    colunas_proj = [c for c in df_exibir.columns if "Proj." in str(c)]
    colunas_reais = [c for c in ["Total Consultivos", "Total Produtos"] if c in df_exibir.columns]
    todas_num = [c for c in df_exibir.columns if c not in ["Posição"] + grupo]

    # Formatação Styler do Pandas
    style_df = df_exibir.style.format(formatter=cast(Any, {c: "{:,}" for c in todas_num}))

    if colunas_reais:
        style_df = style_df.set_properties(
            **{"background-color": "#F8FAFC", "font-weight": "bold"},
            subset=cast(Any, colunas_reais),
        )
    if colunas_proj:
        style_df = style_df.set_properties(
            **{"background-color": "#FFF7ED", "color": "#C2410C", "font-weight": "bold"},
            subset=cast(Any, colunas_proj),
        )

    if colunas_reais:
        style_df = style_df.map(EstiloTabela.colorir_metas, subset=cast(Any, colunas_reais))

    st.dataframe(style_df, use_container_width=True, height=450, hide_index=True)

    # ── UI: Alerta de Equipes Zeradas ────────────────────────────────
    st.divider()
    render_section_header("warning", "Equipes Zeradas (Sem Consultivos)")
    
    df_zerados = df_exibir[df_exibir["Total Consultivos"] == 0]

    if not df_zerados.empty:
        st.dataframe(df_zerados, use_container_width=True, hide_index=True)
    else:
        render_insight("✅ Excelente! 100% da operação possui pelo menos um consultivo registrado.", tipo="ok")

    # ── Exportação ───────────────────────────────────────────────────
    st.divider()
    render_section_header("download", "Exportar Relatório")

    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df_exibir.to_excel(w, index=False, sheet_name="Performance")

    st.download_button(
        label="📥 Baixar Dados em Excel (.xlsx)",
        data=out.getvalue(),
        file_name="relatorio_performance_consultivos.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )


if __name__ == "__main__":
    main()