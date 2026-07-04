import streamlit as st
import pandas as pd
import numpy as np
import datetime
import calendar

# ====================================================
# TEMAS E FUNÇÕES VISUAIS (CARDS)
# ====================================================
TEMAS_CARD = {
    "azul":    {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
    "verde":   {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
    "laranja": {"fundo": "#FFF7ED", "texto": "#C2410C", "borda": "#F97316", "titulo": "#9A3412"},
    "cinza":   {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
}

def criar_card_metrica(titulo, valor, tema="azul"):
    cores = TEMAS_CARD.get(tema, TEMAS_CARD["azul"])
    html = f"""
    <div style="
        background-color: {cores['fundo']}; padding: 20px; border-radius: 10px;
        border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 15px;
    ">
        <p style="margin: 0; font-size: 14px; color: {cores['titulo']};"><b>{titulo}</b></p>
        <h2 style="margin: 0; padding-top: 5px; color: {cores['texto']}; font-weight: 900;">{valor}</h2>
    </div>
    """
    return html

# =========================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================
st.set_page_config(
    page_title="Quantidade de O.S.",
    page_icon="📊", 
    layout="wide"
)

st.title("📊 Quantidade de O.S.")

# =========================================
# LEITURA E TRATAMENTO DE DADOS
# =========================================
if "dados_prod" not in st.session_state:
    st.warning("⚠️ Carregue os dados na página principal primeiro.")
    st.stop()

try:
    df = st.session_state["dados_prod"]["Prod"].copy()
except KeyError as erro:
    st.error(f"❌ Aba não encontrada na base de dados: {erro}")
    st.stop()

# Garantir formato de data
if "Data Agendamento" in df.columns:
    df["Data Agendamento"] = pd.to_datetime(df["Data Agendamento"], errors="coerce")

total_geral_os = len(df) # Guarda o valor bruto antes dos filtros

# =========================================
# FILTROS EM CASCATA (SIDEBAR)
# =========================================
st.sidebar.header("🎯 Filtros Avançados")

# 1. Filtro Projeto
if "Projeto" in df.columns:
    opcoes_projeto = ["Todos"] + sorted(df["Projeto"].dropna().astype(str).unique())
    proj_sel = st.sidebar.selectbox("Filtrar por Projeto:", opcoes_projeto)
    if proj_sel != "Todos":
        df = df[df["Projeto"] == proj_sel]

# 2. Filtro Supervisor (Cascata: Responde ao Projeto)
if "Supervisor" in df.columns:
    opcoes_sup = ["Todos"] + sorted(df["Supervisor"].dropna().astype(str).unique())
    sup_sel = st.sidebar.selectbox("Filtrar por Supervisor:", opcoes_sup)
    if sup_sel != "Todos":
        df = df[df["Supervisor"] == sup_sel]

# =========================================
# KPIs SUPERIORES
# =========================================
total_os_filtrado = len(df)
qtd_projetos = df["Projeto"].nunique() if "Projeto" in df.columns else 0
qtd_supervisores = df["Supervisor"].nunique() if "Supervisor" in df.columns else 0

c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(criar_card_metrica("Total O.S. (Geral)", f"{total_geral_os:,}".replace(",", "."), "cinza"), unsafe_allow_html=True)
with c2: st.markdown(criar_card_metrica("Total O.S. (Filtrado)", f"{total_os_filtrado:,}".replace(",", "."), "azul"), unsafe_allow_html=True)
with c3: st.markdown(criar_card_metrica("Projetos Ativos", f"{qtd_projetos}", "laranja"), unsafe_allow_html=True)
with c4: st.markdown(criar_card_metrica("Supervisores Ativos", f"{qtd_supervisores}", "verde"), unsafe_allow_html=True)

st.divider()

# =========================================
# CÁLCULOS DE DATAS E DIAS FALTANTES
# =========================================
ultima_atualizacao = df["Data Agendamento"].max() if ("Data Agendamento" in df.columns and not df.empty) else None

hoje = datetime.date.today()
ano_atual, mes_atual = hoje.year, hoje.month
_, ultimo_dia_num = calendar.monthrange(ano_atual, mes_atual)
ult_dia = datetime.date(ano_atual, mes_atual, ultimo_dia_num)

data_inicio_np = np.datetime64(ultima_atualizacao.date() if pd.notna(ultima_atualizacao) else hoje)
data_fim_np = np.datetime64(ult_dia) + np.timedelta64(1, "D")

# Trava de segurança para não ter dias negativos
dias_faltantes = max(0, np.busday_count(data_inicio_np, data_fim_np, weekmask="1111110"))

# Médias de OS diárias
media_por_supervisor = pd.Series(dtype=float)
media_projeto = pd.Series(dtype=float)

if "Data Agendamento" in df.columns and not df.empty:
    if "Supervisor" in df.columns:
        media_por_supervisor = df.groupby(["Supervisor", "Data Agendamento"])["OS"].count().groupby("Supervisor").mean()
    if "Projeto" in df.columns:
        media_projeto = df.groupby(["Projeto", "Data Agendamento"])["OS"].count().groupby("Projeto").mean()

# =========================================
# FUNÇÕES DE ESTILIZAÇÃO DE TABELAS
# =========================================
def colorir_os(valor):
    return "background-color: #F8FAFC; color: #334155; font-weight: bold" # Fundo Cinza SaaS

def colorir_projecao(valor):
    return "background-color: #334155; color: white; font-weight: bold" # Fundo Escuro

# =========================================
# EXIBIÇÃO DOS DADOS
# =========================================

col_esq, col_dir = st.columns(2)

# --- VISÃO POR SUPERVISOR ---
with col_esq:
    st.subheader("👨‍💼 Visão por Supervisor")
    if not df.empty and "Supervisor" in df.columns:
        qtde_os_sup = df.groupby("Supervisor")["OS"].count().reset_index(name="Qtde. de O.S.")
        media_ind = qtde_os_sup["Supervisor"].map(media_por_supervisor).fillna(0)

        qtde_os_sup["Meta | 2500"] = qtde_os_sup["Qtde. de O.S."] - 2500
        qtde_os_sup["Meta | 3000"] = qtde_os_sup["Qtde. de O.S."] - 3000
        qtde_os_sup["Meta | 3500"] = qtde_os_sup["Qtde. de O.S."] - 3500
        qtde_os_sup["Projeção"] = (qtde_os_sup["Qtde. de O.S."] + (media_ind * dias_faltantes)).astype(int)

        st.dataframe(
            qtde_os_sup.sort_values(by="Qtde. de O.S.", ascending=False)
            .style.map(colorir_os, subset=["Qtde. de O.S."]).map(colorir_projecao, subset=["Projeção"]),
            use_container_width=True, hide_index=True, height=400
        )
    else:
        st.info("Sem dados de Supervisor.")

# --- VISÃO POR PROJETO ---
with col_dir:
    st.subheader("💼 Visão por Projeto")
    if not df.empty and "Projeto" in df.columns:
        qtde_os_proj = df.groupby("Projeto")["OS"].count().reset_index(name="Qtde. de O.S.")
        media_ind = qtde_os_proj["Projeto"].map(media_projeto).fillna(0)

        qtde_os_proj["Meta | 9000"]  = qtde_os_proj["Qtde. de O.S."] - 9000
        qtde_os_proj["Meta | 10000"] = qtde_os_proj["Qtde. de O.S."] - 10000
        qtde_os_proj["Meta | 11000"] = qtde_os_proj["Qtde. de O.S."] - 11000
        qtde_os_proj["Projeção"] = (qtde_os_proj["Qtde. de O.S."] + (media_ind * dias_faltantes)).astype(int)

        st.dataframe(
            qtde_os_proj.sort_values(by="Qtde. de O.S.", ascending=False)
            .style.map(colorir_os, subset=["Qtde. de O.S."]).map(colorir_projecao, subset=["Projeção"]),
            use_container_width=True, hide_index=True, height=400
        )
    else:
        st.info("Sem dados de Projeto.")

st.divider()

# --- VISÃO POR TÉCNICO ---
st.subheader("👷 Visão por Técnico")
if not df.empty and "Nome Equipe" in df.columns:
    df_tecnico = df.groupby(["CódAuxEquipe", "Nome Equipe", "Supervisor", "Projeto"])["OS"].count().reset_index(name="Qtde. de O.S.")
    
    st.dataframe(
        df_tecnico.sort_values("Qtde. de O.S.", ascending=False).style.map(colorir_os, subset=["Qtde. de O.S."]),
        use_container_width=True, hide_index=True, height=500
    )
else:
    st.info("Sem dados de Técnicos para exibir.")

# --- RODAPÉ ---
if pd.notna(ultima_atualizacao):
    st.caption(f"🕒 ***Última Atualização dos Dados:*** {pd.to_datetime(ultima_atualizacao).strftime('%d/%m/%Y')}")