import streamlit as st
import pandas as pd
import numpy as np
import datetime
import calendar
import plotly.express as px

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
    page_title="Dashboard O.S.",
    page_icon="📊", 
    layout="wide"
)

st.title("📊 Painel Executivo - Ordens de Serviço")

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

# 2. Filtro Supervisor
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
# CÁLCULOS DE DATAS E DIAS FALTANTES (INTELIGENTE)
# =========================================
if "Data Agendamento" in df.columns and not df.empty:
    ultima_atualizacao = df["Data Agendamento"].max()
    data_ref = pd.to_datetime(ultima_atualizacao).date()
else:
    ultima_atualizacao = None
    data_ref = datetime.date.today()

# 1. Descobre o ano e mês baseados no RELATÓRIO
ano_ref, mes_ref = data_ref.year, data_ref.month
_, ultimo_dia_num = calendar.monthrange(ano_ref, mes_ref)

primeiro_dia = datetime.date(ano_ref, mes_ref, 1)
ultimo_dia = datetime.date(ano_ref, mes_ref, ultimo_dia_num)

# 2. Converte para Numpy
primeiro_dia_np = np.datetime64(primeiro_dia)
data_ref_np = np.datetime64(data_ref)
ultimo_dia_np = np.datetime64(ultimo_dia)

# 3. Matemática dos Dias Úteis (Seg a Sáb)
total_dias_mes = np.busday_count(primeiro_dia_np, ultimo_dia_np + np.timedelta64(1, "D"), weekmask="1111110")
dias_passados = np.busday_count(primeiro_dia_np, data_ref_np + np.timedelta64(1, "D"), weekmask="1111110")

# Trava de segurança: Quantos dias restam para o mês DO RELATÓRIO acabar
dias_faltantes = max(0, total_dias_mes - dias_passados)

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
    return "background-color: #F8FAFC; color: #334155; font-weight: bold"

def colorir_projecao(valor):
    return "background-color: #334155; color: white; font-weight: bold"

# NOVO: Lógica de Classificação de Performance
def definir_faixa_supervisor(qtd):
    """
    Classifica a quantidade de OS em faixas predefinidas:
    >= 3500 : F3 (Alta Performance)
    3000-3499: F2 (Meta Alcançada)
    2500-2999: F1 (Parcial)
    < 2500   : Abaixo do Mínimo
    """
    try:
        qtd_float = float(qtd)
        if qtd_float >= 3500: 
            return "F3 🌟" # Pode usar emoji para ficar visual
        elif qtd_float >= 3000: 
            return "F2 ✅"
        elif qtd_float >= 2500: 
            return "F1 ⚠️"
        else: 
            return "< 2500 ❌"
    except:
        return "-"
    
# NOVO: Função EXCLUSIVA para Projetos (9000 - 11000)
def definir_faixa_projeto(qtd):
    try:
        qtd_float = float(qtd)
        if qtd_float >= 11000: return "F3 🌟"
        elif qtd_float >= 10000: return "F2 ✅"
        elif qtd_float >= 9000: return "F1 ⚠️"
        else: return "< 9000 ❌"
    except:
        return "-"

# Estilo condicional específico para a coluna Faixa
def colorir_faixa(valor):
    if "F3" in str(valor): # Fundo Dourado/Verde
        return "background-color: #DCFCE7; color: #166534; font-weight: bold; border-radius: 8px;"
    elif "F2" in str(valor): # Fundo Azul Claro
        return "background-color: #DBEAFE; color: #1E40AF; font-weight: bold; border-radius: 8px;"
    elif "F1" in str(valor): # Fundo Amarelo/Ambar
        return "background-color: #FEF3C7; color: #B45309; font-weight: bold; border-radius: 8px;"
    else: # Vermelho/Cinza
        return "background-color: #FEE2E2; color: #991B1B; font-weight: bold; border-radius: 8px;"


# =========================================
# 1. GRÁFICO DE TENDÊNCIA (EVOLUÇÃO DIÁRIA)
# =========================================
st.subheader("📈 Evolução Diária de O.S.")
if not df.empty and "Data Agendamento" in df.columns:
    df_tendencia = df.groupby(df["Data Agendamento"].dt.date)["OS"].count().reset_index()
    df_tendencia.columns = ["Data", "Quantidade"]
    
    fig_linha = px.area(
        df_tendencia, x="Data", y="Quantidade", 
        markers=True, color_discrete_sequence=["#F97316"] # Laranja: "#F97316", Verde: "#22C55E", Azul: "#0EA5E9"
    )
    fig_linha.update_layout(
        xaxis_title="", yaxis_title="", 
        plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=0), height=300
    )
    st.plotly_chart(fig_linha, use_container_width=True)
else:
    st.info("Planilha sem coluna 'Data Agendamento'.")

st.divider()

# =========================================
# 2. VISÃO SUPERVISORES E PROJETOS
# =========================================
col_esq, col_dir = st.columns(2)

# --- VISÃO POR SUPERVISOR ---
with col_esq:
    st.subheader("👨‍💼 Visão por Supervisor")
    if not df.empty and "Supervisor" in df.columns:
        qtde_os_sup = df.groupby("Supervisor")["OS"].count().reset_index(name="Qtde. de O.S.")
        media_ind = qtde_os_sup["Supervisor"].map(media_por_supervisor).fillna(0)

        # Cálculos das Metas e Projeção
        qtde_os_sup["Meta | 2500"] = qtde_os_sup["Qtde. de O.S."] - 2500
        qtde_os_sup["Meta | 3000"] = qtde_os_sup["Qtde. de O.S."] - 3000
        qtde_os_sup["Meta | 3500"] = qtde_os_sup["Qtde. de O.S."] - 3500
        qtde_os_sup["Projeção"] = (qtde_os_sup["Qtde. de O.S."] + (media_ind * dias_faltantes)).astype(int)
        
        # APLICANDO A NOVA COLUNA DE FAIXA
        qtde_os_sup["Faixa"] = qtde_os_sup["Qtde. de O.S."].apply(definir_faixa_supervisor)

        st.dataframe(
            qtde_os_sup.sort_values(by="Qtde. de O.S.", ascending=False)
            .style.map(colorir_os, subset=["Qtde. de O.S."])
            .map(colorir_projecao, subset=["Projeção"])
            .map(colorir_faixa, subset=["Faixa"]) # Adicionando cor à faixa
            , use_container_width=True, hide_index=True, height=400
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

        # Abas para Tabela e Gráfico
        tab_tabela, tab_grafico = st.tabs(["📋 Tabela", "🍩 Gráfico de Share"])
        
        with tab_tabela:
            qtde_os_proj["Faixa"] = qtde_os_proj["Qtde. de O.S."].apply(definir_faixa_projeto)  # Aplicando a função específica para projetos

            st.dataframe(
                qtde_os_proj.sort_values(by="Qtde. de O.S.", ascending=False)
                .style.map(colorir_os, subset=["Qtde. de O.S."])
                .map(colorir_projecao, subset=["Projeção"])
                .map(colorir_faixa, subset=["Faixa"])
                , use_container_width=True, hide_index=True, height=350
            )
            
        with tab_grafico:
            fig_rosca = px.pie(
                qtde_os_proj, values='Qtde. de O.S.', names='Projeto', hole=0.6,
                color_discrete_sequence=px.colors.sequential.Tealgrn_r
            )
            fig_rosca.update_traces(textposition='inside', textinfo='percent+label')
            fig_rosca.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=350, paper_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_rosca, use_container_width=True)
    else:
        st.info("Sem dados de Projeto.")

st.divider()

# =========================================
# 3. VISÃO POR TÉCNICO (TABELA + TOP 10)
# =========================================
st.subheader("👷 Performance de Técnicos")
if not df.empty and "Nome Equipe" in df.columns:
    df_tecnico = df.groupby(["CódAuxEquipe", "Nome Equipe", "Supervisor", "Projeto"])["OS"].count().reset_index(name="Qtde. de O.S.")
    df_tecnico = df_tecnico.sort_values("Qtde. de O.S.", ascending=False)
    
    col_tec1, col_tec2 = st.columns([1.5, 1])
    
    with col_tec1:
        st.markdown("**📋 Tabela Geral de Técnicos**")
        st.dataframe(
            df_tecnico.style.map(colorir_os, subset=["Qtde. de O.S."]),
            use_container_width=True, hide_index=True, height=450
        )
        
    with col_tec2:
        st.markdown("**🏆 Top 10 Técnicos**")
        # Pega os 10 melhores, mas inverte a ordem para o maior ficar no topo do gráfico
        top10 = df_tecnico.head(10).sort_values("Qtde. de O.S.", ascending=True) 
        
        fig_top10 = px.bar(
            top10, x="Qtde. de O.S.", y="Nome Equipe", orientation='h', 
            text="Qtde. de O.S.", color="Qtde. de O.S.", color_continuous_scale="Oranges", range_color=[top10["Qtde. de O.S."].min(), top10["Qtde. de O.S."].max()]
        )
        fig_top10.update_layout(
            xaxis_title="", yaxis_title="", coloraxis_showscale=False,
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", 
            margin=dict(l=0, r=0, t=0, b=0), height=450
        )
        st.plotly_chart(fig_top10, use_container_width=True)
else:
    st.info("Sem dados de Técnicos para exibir.")

# --- RODAPÉ ---
st.divider()
if pd.notna(ultima_atualizacao):
    st.sidebar.divider()
    st.sidebar.caption(f"🕒 ***Última Atualização:*** {pd.to_datetime(ultima_atualizacao).strftime('%d/%m/%Y')}")