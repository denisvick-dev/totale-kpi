import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from dataclasses import dataclass, field
from typing import Dict, Tuple, Optional
from io import BytesIO

# ====================================================
# CONFIG
# ====================================================
@dataclass(frozen=True)
class Config:
    URL_ATIVOS: str = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    SLA_QUEBRA_MAXIMA: float = 0.20  # 20%

    TEMAS_CARD: Dict[str, Dict[str, str]] = field(default_factory=dict)

    def __post_init__(self):
        if not self.TEMAS_CARD:
            object.__setattr__(self, "TEMAS_CARD", {
                "azul": {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
                "verde": {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
                "laranja": {"fundo": "#FFF7ED", "texto": "#C2410C", "borda": "#F97316", "titulo": "#9A3412"},
                "roxo": {"fundo": "#FAF5FF", "texto": "#7E22CE", "borda": "#A855F7", "titulo": "#581C87"},
                "vermelho": {"fundo": "#FEF2F2", "texto": "#B91C1C", "borda": "#EF4444", "titulo": "#991B1B"},
                "cinza": {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
            })


CFG = Config()


# ====================================================
# UTIL
# ====================================================
def normalizar_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    return df


def buscar_coluna(df: pd.DataFrame, palavras_chave: list[str]) -> Optional[str]:
    if df is None or df.empty:
        return None
    cols_upper = {c.upper(): c for c in df.columns}
    for p in palavras_chave:
        key = p.upper()
        if key in cols_upper:
            return cols_upper[key]
    return None


def normalizar_login(s: pd.Series) -> pd.Series:
    return (
        s.astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
        .str.upper()
    )


def classificar_os_series(status_series: pd.Series) -> pd.Series:
    # Conceito novo: somente EXECUTADA / NÃO EXECUTADA; resto é pendente
    s = status_series.fillna("").astype(str).str.strip().str.upper()

    executada = (s == "EXECUTADA")
    nao_exec = s.isin(["NÃO EXECUTADA", "NAO EXECUTADA"])

    return pd.Series(
        np.select([executada, nao_exec], ["Executada", "Não Executada"], default="Pendente"),
        index=status_series.index
    )


# ====================================================
# VISUAL
# ====================================================
def criar_card(titulo: str, valor: str, tema: str = "azul", subtitulo: str = "") -> str:
    cores = CFG.TEMAS_CARD.get(tema, CFG.TEMAS_CARD["azul"])
    return f"""
    <div style="background-color: {cores['fundo']}; padding: 15px; border-radius: 8px; border-left: 5px solid {cores['borda']}; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <p style="margin: 0; font-size: 13px; color: {cores['titulo']}; font-weight: bold; text-transform: uppercase;">{titulo}</p>
        <h2 style="margin: 5px 0 0 0; color: {cores['texto']}; font-weight: 900; font-size: 28px;">{valor}</h2>
        <p style="margin: 5px 0 0 0; font-size: 12px; color: #64748B; font-weight: 500;">{subtitulo}</p>
    </div>
    """


def grafico_velocimetro(valor: float, meta: float) -> go.Figure:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=valor * 100,
        number={'suffix': "%", 'valueformat': '.1f', 'font': {'size': 36}},
        title={'text': "Termômetro de Quebra", 'font': {'size': 16}},
        gauge={
            'axis': {'range': [0, max(30, valor * 100 + 10)], 'tickwidth': 1},
            'bar': {'color': "#1E293B"},
            'bgcolor': "white",
            'borderwidth': 1,
            'steps': [
                {'range': [0, meta * 100], 'color': "#bbf7d0"},
                {'range': [meta * 100, (meta + 0.05) * 100], 'color': "#fef08a"},
                {'range': [(meta + 0.05) * 100, 100], 'color': "#fecaca"}
            ],
            'threshold': {'line': {'color': "red", 'width': 3}, 'thickness': 0.75, 'value': meta * 100}
        }
    ))
    fig.update_layout(margin=dict(t=30, b=10, l=10, r=10), height=200)
    return fig


# ====================================================
# DADOS (I/O + PREP)
# ====================================================
@st.cache_data(show_spinner=False)
def ler_arquivo_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
    try:
        name = filename.lower()
        bio = BytesIO(file_bytes)

        if name.endswith(".csv"):
            return pd.read_csv(bio, sep=None, engine="python", encoding="utf-8")
        if name.endswith((".xlsx", ".xls")):
            return pd.read_excel(bio, engine="openpyxl")

        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=600, show_spinner=False)
def buscar_gsheets() -> pd.DataFrame:
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_gs = conn.read(spreadsheet=CFG.URL_ATIVOS)  # não usar ttl=0 aqui
        if df_gs is None or df_gs.empty:
            return pd.DataFrame()

        df_gs = normalizar_cols(df_gs)

        col_log = buscar_coluna(df_gs, ['LOGIN', 'ID', 'MATRÍCULA', 'MATRICULA'])
        col_tec = buscar_coluna(df_gs, ['TÉCNICO', 'NOME'])
        col_mon = buscar_coluna(df_gs, ['MONITOR', 'GESTOR'])

        df_gs = df_gs.rename(columns={
            col_log: "LOGIN",
            col_tec: "TÉCNICO",
            col_mon: "MONITOR"
        })

        # Mantém apenas o que for útil e existir
        keep = [c for c in ["LOGIN", "TÉCNICO", "MONITOR"] if c in df_gs.columns]
        df_gs = df_gs[keep].copy()

        if "LOGIN" in df_gs.columns:
            df_gs["LOGIN"] = normalizar_login(df_gs["LOGIN"])

        return df_gs.drop_duplicates(subset=["LOGIN"], keep="last") if "LOGIN" in df_gs.columns else df_gs
    except Exception:
        return pd.DataFrame()


def preparar_base(df: pd.DataFrame, df_gsheets: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = normalizar_cols(df)

    # TOTAL DE TAREFAS
    if "TOTAL DE TAREFAS" not in df.columns:
        df["TOTAL DE TAREFAS"] = 1
    df["TOTAL DE TAREFAS"] = pd.to_numeric(df["TOTAL DE TAREFAS"], errors="coerce").fillna(0)

    # Limpeza mínima
    if "CONTRATO" in df.columns:
        df = df.dropna(subset=["CONTRATO"])

    # Flags serviço
    tipo_os = df.get("TIPO DE O.S 1", df.get("TIPO O.S 1", pd.Series("", index=df.index))).astype(str).str.upper()
    hab_trab = df.get("HABILIDADE DE TRABALHO", pd.Series("", index=df.index)).astype(str).str.upper()

    df["CHECK_GPON"] = hab_trab.str.contains(r"PON\(1/100\)", regex=True, na=False)
    df["CHECK_ND"] = tipo_os.str.contains("ADESAO", na=False)
    df["CHECK_MIGRACAO"] = tipo_os.str.contains("MUDANCA DE PACOTE", na=False) & df["CHECK_GPON"]
    df["CHECK_PME"] = hab_trab.str.contains("PME", na=False)

    # Cruzamento (login)
    col_login = buscar_coluna(df, ["LOGIN", "LOGIN DO TÉCNICO", "USUÁRIO", "MATRÍCULA", "MATRICULA"])
    if col_login and (df_gsheets is not None) and (not df_gsheets.empty) and ("LOGIN" in df_gsheets.columns):
        df[col_login] = normalizar_login(df[col_login])

        # remove colunas antigas se existirem, pra evitar conflito
        for c in ["TÉCNICO", "MONITOR"]:
            if c in df.columns:
                df = df.drop(columns=[c])

        df = df.merge(df_gsheets, left_on=col_login, right_on="LOGIN", how="left")

    # Defaults
    if "TÉCNICO" not in df.columns:
        df["TÉCNICO"] = "NÃO MAPEADO"
    df["TÉCNICO"] = df["TÉCNICO"].fillna("NÃO MAPEADO")

    if "MONITOR" not in df.columns:
        df["MONITOR"] = "SEM MONITOR"
    df["MONITOR"] = df["MONITOR"].fillna("SEM MONITOR")

    return df


# ====================================================
# MÉTRICAS
# ====================================================
def calcular_quebra(df_alvo: pd.DataFrame) -> Tuple[float, float, float, float, float]:
    """
    Retorna:
      vol_alocado, vol_considerado(exec+naoexec), exec, naoexec, taxa_quebra
    """
    if df_alvo is None or df_alvo.empty or "Status Contrato" not in df_alvo.columns:
        return 0.0, 0.0, 0.0, 0.0, 0.0

    vol_alocado = float(df_alvo["TOTAL DE TAREFAS"].sum())

    exec_ = float(df_alvo.loc[df_alvo["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum())
    naoexec = float(df_alvo.loc[df_alvo["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum())

    vol_considerado = exec_ + naoexec
    taxa = (naoexec / vol_considerado) if vol_considerado > 0 else 0.0

    return vol_alocado, vol_considerado, exec_, naoexec, taxa


# ====================================================
# APP
# ====================================================
st.set_page_config(page_title="Gestão de Quebra", page_icon="📊", layout="wide")
st.title("🗣️ Painel Executivo: Quebra de Agenda")

if "df_memoria" not in st.session_state:
    st.session_state["df_memoria"] = None

# Upload
if st.session_state["df_memoria"] is None:
    arquivo = st.file_uploader("📥 Envie a base de dados (Excel ou CSV)", type=["xlsx", "xls", "csv"])
    if arquivo:
        with st.spinner("Analisando dados e cruzando hierarquia..."):
            df_base = ler_arquivo_bytes(arquivo.getvalue(), arquivo.name)
            df_gs = buscar_gsheets()
            st.session_state["df_memoria"] = preparar_base(df_base, df_gs)
        st.rerun()

# Dashboard
else:
    df_full = st.session_state["df_memoria"]

    col_aviso, col_btn = st.columns([4, 1])
    with col_aviso:
        st.success("✅ Base processada com sucesso!")
    with col_btn:
        if st.button("🔄 Enviar outra base", use_container_width=True):
            st.session_state["df_memoria"] = None
            st.rerun()

    col_status = buscar_coluna(df_full, ["STATUS DA O.S 1", "STATUS OS", "STATUS"])
    col_motivo = buscar_coluna(df_full, ["MOTIVO", "SUBSTATUS", "MOTIVO BAIXA", "OBSERVAÇÃO", "OBSERVACAO"])

    if not col_status:
        st.error("⚠️ Coluna de 'Status' não encontrada na planilha.")
        st.stop()

    # Status (vetorizado)
    df_full = df_full.copy()
    df_full["Status Contrato"] = classificar_os_series(df_full[col_status])

    # Sidebar filtros
    with st.sidebar:
        st.header("🎯 Filtros")
        df_filtrado = df_full

        qtd_orfaos = int((df_filtrado["TÉCNICO"] == "NÃO MAPEADO").sum()) if "TÉCNICO" in df_filtrado.columns else 0
        if qtd_orfaos > 0:
            st.error(f"⚠️ {qtd_orfaos} logins não existem no Google Sheets.")

        for col, titulo, bloqueados in [
            ("MONITOR", "👔 Monitor", {"nan", "SEM MONITOR"}),
            ("TÉCNICO", "👤 Técnico", {"nan", "NÃO MAPEADO"}),
        ]:
            if col in df_filtrado.columns:
                valores = [str(x) for x in df_filtrado[col].unique()]
                valores = [v for v in valores if v not in bloqueados]
                opcoes = ["Todos"] + sorted(valores)
                selecao = st.selectbox(titulo, opcoes)
                if selecao != "Todos":
                    df_filtrado = df_filtrado[df_filtrado[col] == selecao]

    df = df_filtrado.copy()

    # KPIs gerais
    vol_alocado, vol_considerado, t_exec, t_nao_exec, tx_geral = calcular_quebra(df)

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(criar_card("Total Tarefas", f"{vol_alocado:,.0f}", "azul", "Volume Alocado"), unsafe_allow_html=True)
    with c2:
        st.markdown(criar_card("Executadas", f"{t_exec:,.0f}", "verde", "Sucesso"), unsafe_allow_html=True)
    with c3:
        st.markdown(criar_card("Não Executadas", f"{t_nao_exec:,.0f}", "laranja", "Quebras"), unsafe_allow_html=True)
    with c4:
        cor = "vermelho" if tx_geral > CFG.SLA_QUEBRA_MAXIMA else "roxo"
        st.markdown(criar_card("Taxa Geral", f"{tx_geral:,.2%}", cor, "Referência SLA"), unsafe_allow_html=True)

    # Quebra por serviço
    st.write("---")
    st.markdown("### 📊 Quebra por Tipo de Serviço")

    servicos = {
        "ND (Adesão)": df[df.get("CHECK_ND", False) == True],
        "Migração": df[df.get("CHECK_MIGRACAO", False) == True],
        "Tecnologia GPON": df[df.get("CHECK_GPON", False) == True],
        "Cliente PME": df[df.get("CHECK_PME", False) == True],
    }

    s1, s2, s3, s4, sgraf = st.columns([1, 1, 1, 1, 3])
    cols_cards = [s1, s2, s3, s4]

    svc_rows = []
    for i, (nome_svc, df_svc) in enumerate(servicos.items()):
        v_aloc, v_cons, ex, ne, taxa = calcular_quebra(df_svc)
        svc_rows.append({"Serviço": nome_svc, "Taxa": taxa, "Vol": v_cons})

        cor = "vermelho" if taxa > CFG.SLA_QUEBRA_MAXIMA else "cinza"
        with cols_cards[i]:
            st.markdown(
                criar_card(nome_svc, f"{taxa:,.2%}", cor, f"Vol: {v_cons:,.0f} OS"),
                unsafe_allow_html=True
            )

    with sgraf:
        df_svc = pd.DataFrame(svc_rows)
        df_svc = df_svc[df_svc["Vol"] > 0].sort_values("Taxa", ascending=True)
        if not df_svc.empty:
            fig_svc = px.bar(
                df_svc, x="Taxa", y="Serviço",
                orientation="h", color="Taxa",
                color_continuous_scale="Reds"
            )
            fig_svc.update_traces(texttemplate="%{x:.2%}", textposition="outside", cliponaxis=False)
            fig_svc.update_layout(
                xaxis_tickformat=".0%",
                showlegend=False,
                margin=dict(t=0, b=0, l=0, r=0),
                xaxis_title="",
                yaxis_title=""
            )
            st.plotly_chart(fig_svc, use_container_width=True, config={"displayModeBar": False})

    st.write("---")

    # Distribuição / Top motivos / Top monitores
    g1, g2, g3 = st.columns([1, 1.2, 1.2])

    with g1:
        st.markdown("#### 📉 Distribuição")
        df_pie = df.groupby("Status Contrato", as_index=False)["TOTAL DE TAREFAS"].sum()
        if not df_pie.empty:
            fig = px.pie(
                df_pie,
                names="Status Contrato",
                values="TOTAL DE TAREFAS",
                hole=0.5,
                color="Status Contrato",
                color_discrete_map={"Executada": "#16A34A", "Não Executada": "#DC2626", "Pendente": "#94A3B8"},
            )
            fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.2), margin=dict(t=10, b=10, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with g2:
        st.markdown("#### 🔎 Top Motivos")
        if col_motivo and col_motivo in df.columns:
            df_motivos = (
                df[df["Status Contrato"] == "Não Executada"]
                .groupby(col_motivo, as_index=False)["TOTAL DE TAREFAS"].sum()
                .sort_values("TOTAL DE TAREFAS", ascending=False)
                .head(5)
            )
            if not df_motivos.empty:
                fig_m = px.bar(
                    df_motivos, x="TOTAL DE TAREFAS", y=col_motivo,
                    orientation="h", color_discrete_sequence=["#DC2626"],
                    text="TOTAL DE TAREFAS"
                )
                fig_m.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=0, r=0, t=10, b=0), xaxis_title="", yaxis_title="")
                st.plotly_chart(fig_m, use_container_width=True, config={"displayModeBar": False})

    with g3:
        st.markdown("#### 👔 Top Monitores")
        if "MONITOR" in df.columns:
            p_mon = pd.crosstab(df["MONITOR"], df["Status Contrato"], values=df["TOTAL DE TAREFAS"], aggfunc="sum").fillna(0)
            if "Não Executada" in p_mon.columns:
                p_mon["Total"] = p_mon.sum(axis=1)
                p_mon["% Quebra"] = np.where(p_mon["Total"] > 0, p_mon["Não Executada"] / p_mon["Total"], 0.0)
                rank_mon = (
                    p_mon[p_mon["Total"] >= 5]
                    .sort_values("% Quebra", ascending=False)
                    .head(5)
                    .reset_index()
                )
                st.dataframe(
                    rank_mon[["MONITOR", "Não Executada", "% Quebra"]],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "% Quebra": st.column_config.ProgressColumn("Taxa", min_value=0, max_value=1, format="%.2f")
                    },
                )

    st.write("---")

    # Tabelas
    tab_acao, tab_base = st.tabs(["🚨 Fila de Tratamento (Backoffice)", "🧾 Base de Dados Completa"])

    with tab_acao:
        df_acao = df[df["Status Contrato"] == "Não Executada"].copy()
        if not df_acao.empty:
            cols_chaves = [c for c in ["CONTRATO", "TÉCNICO", "MONITOR", col_motivo, "TOTAL DE TAREFAS"] if c and c in df_acao.columns]
            st.dataframe(df_acao[cols_chaves] if cols_chaves else df_acao, use_container_width=True, hide_index=True)
            st.download_button(
                "📥 Baixar Fila (.CSV)",
                data=df_acao.to_csv(index=False, sep=";", encoding="utf-8-sig"),
                file_name="fila.csv",
                mime="text/csv",
            )
        else:
            st.success("Nenhuma quebra registrada!")

    with tab_base:
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "📥 Baixar Base (.CSV)",
            data=df.to_csv(index=False, sep=";", encoding="utf-8-sig"),
            file_name="base.csv",
            mime="text/csv",
        )