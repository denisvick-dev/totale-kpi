import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Optional

# ====================================================
# BLOCO 1: CONFIGURAÇÕES GLOBAIS
# ====================================================
class Configuracoes:
    TEMAS_CARD = {
        "azul": {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
        "verde": {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
        "laranja": {"fundo": "#FFF7ED", "texto": "#C2410C", "borda": "#F97316", "titulo": "#9A3412"},
        "cinza": {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
        "roxo": {"fundo": "#FAF5FF", "texto": "#7E22CE", "borda": "#A855F7", "titulo": "#581C87"}, 
    }

# ====================================================
# BLOCO 2: COMPONENTES VISUAIS (FRONT-END)
# ====================================================
class ComponenteVisual:
    @staticmethod
    def criar_card(titulo: str, valor: str, tema: str = "azul", subtitulo: str = "", icone: str = "") -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        titulo_formatado = f"{icone} {titulo}" if icone else titulo
        
        return f"""
        <div style="background-color: {cores['fundo']}; padding: 20px; border-radius: 10px; border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.05); height: 100%; display: flex; flex-direction: column; justify-content: center; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
            <p style="margin: 0; font-size: 14px; color: {cores['titulo']}; font-weight: bold;">{titulo_formatado}</p>
            <h2 style="margin: 5px 0 0 0; color: {cores['texto']}; font-weight: 900; font-size: 32px;">{valor}</h2>
            <p style="margin: 5px 0 0 0; font-size: 13px; color: #64748B; font-weight: 500;">{subtitulo}</p>
        </div>
        """

# ====================================================
# BLOCO 3: FUNÇÕES UTILITÁRIAS
# ====================================================
class Utilitarios:
    @staticmethod
    def encontrar_coluna_data(df: pd.DataFrame) -> Optional[str]:
        possiveis = ["DATA AGENDAMENTO", "DATA CONCLUSÃO", "DATA", "DATE", "DATA_EXECUCAO"]
        cols_upper = {c.upper(): c for c in df.columns}
        for pos in possiveis:
            if pos in cols_upper: return cols_upper[pos]
        return None
        
    @staticmethod
    def encontrar_coluna_tecnico(df: pd.DataFrame) -> Optional[str]:
        possiveis = ["TÉCNICO", "TECNICO", "VENDEDOR", "NOME EQUIPE", "NOME", "LOGIN"]
        cols_upper = {c.upper(): c for c in df.columns}
        for pos in possiveis:
            if pos in cols_upper: return cols_upper[pos]
        return None

    @staticmethod
    def encontrar_coluna_supervisor(df: pd.DataFrame) -> Optional[str]:
        possiveis = ["SUPERVISOR", "MONITOR", "GESTOR", "COORDENADOR", "LÍDER", "LIDER"]
        cols_upper = {c.upper(): c for c in df.columns}
        for pos in possiveis:
            if pos in cols_upper: return cols_upper[pos]
        return None

    @staticmethod
    def encontrar_coluna_base(df: pd.DataFrame) -> Optional[str]:
        possiveis = ["BASE", "PROJETO", "CIDADE", "FILIAL", "LOCALIDADE"]
        cols_upper = {c.upper(): c for c in df.columns}
        for pos in possiveis:
            if pos in cols_upper: return cols_upper[pos]
        return None

    @staticmethod
    def formatar_numero(valor: float) -> str:
        # Formata com 2 casas decimais no padrão brasileiro (1.234,56)
        if pd.isna(valor): return "0,00"
        formatado = f"{valor:,.2f}"
        return formatado.replace(",", "X").replace(".", ",").replace("X", ".")

# ====================================================
# BLOCO 4: GRÁFICOS E VISUAIS
# ====================================================
class Graficos:
    @staticmethod
    def grafico_combo_raiox(df: pd.DataFrame, x_col: str, y_bar: str, y_line: str) -> go.Figure:
        """Gráfico Misto: Barras de OS e Linha de Pontos"""
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df[x_col], y=df[y_bar], name='Volume O.S.', marker_color='#CBD5E1', opacity=0.8))
        
        # Ajuste no hover para exibir as duas casas decimais no gráfico
        fig.add_trace(go.Scatter(x=df[x_col], y=df[y_line], name='Pontos', mode='lines+markers', 
                                 line=dict(color='#0EA5E9', width=3), marker=dict(size=8, color='#0284C7'), 
                                 yaxis="y2", hovertemplate='%{y:.2f} pts'))
        
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), hovermode="x unified",
            yaxis=dict(title="Quantidade O.S.", showgrid=True, gridcolor="rgba(0,0,0,0.05)"),
            yaxis2=dict(title="Pontos", overlaying="y", side="right", showgrid=False)
        )
        return fig

# ====================================================
# BLOCO 5: MOCK DE DADOS (APENAS PARA PREVENIR ERROS)
# ====================================================
def gerar_dados_teste():
    """Gera dados falsos para Produção caso a sessão esteja vazia"""
    import numpy as np
    datas = pd.date_range(start="2023-10-01", periods=15, freq="D").tolist() * 3
    tecnicos = ["JOAO SILVA", "MARIA SOUZA", "CARLOS ALBERTO"] * 15
    
    return pd.DataFrame({
        "Data": datas, "Nome Equipe": tecnicos, "Supervisor": ["SUP A", "SUP B", "SUP A"] * 15,
        "Base": ["SÃO PAULO", "SÃO PAULO", "CAMPINAS"] * 15, 
        "Pontos": np.random.uniform(10.5, 50.8, size=45), # Agora gera números quebrados
        "OS_Status": ["CONCLUÍDO"] * 45
    })

# ====================================================
# BLOCO 6: INICIALIZAÇÃO E TRATAMENTO DE BASES
# ====================================================
st.set_page_config(page_title="Raio-X do Técnico", page_icon="🔍", layout="wide")

st.title("🔍 Raio-X: Desempenho Operacional")
st.markdown("Auditoria detalhada de **Execução Física** (O.S. e Pontuação) por técnico/equipe.")

# Carregamento Seguro da Base de Produção
df_prod = pd.DataFrame()

if "dados_prod" in st.session_state:
    try:
        p1 = st.session_state["dados_prod"]["Prod"].copy()
        p2 = st.session_state["dados_prod"]["Gpon"].copy()
        df_prod = pd.concat([p1, p2], ignore_index=True)
    except Exception: pass

if df_prod.empty:
    st.warning("⚠️ Base de Produção não encontrada. Carregando dados de demonstração.")
    df_prod = gerar_dados_teste()

# Garante Formatação e tipagem
if "Pontos" in df_prod.columns: 
    df_prod["Pontos"] = pd.to_numeric(df_prod["Pontos"], errors="coerce").fillna(0.0)

# ====================================================
# BLOCO 7: MOTOR DE BUSCA EM CASCATA
# ====================================================
col_tec = Utilitarios.encontrar_coluna_tecnico(df_prod)
col_sup = Utilitarios.encontrar_coluna_supervisor(df_prod)
col_base = Utilitarios.encontrar_coluna_base(df_prod)

if not col_tec:
    st.error("❌ Não foi possível encontrar a coluna de Vendedor/Técnico na base de dados.")
    st.stop()

# Limpeza do nome do Técnico antes dos filtros
df_prod[col_tec] = df_prod[col_tec].astype(str).str.strip().str.upper()

with st.container(border=True):
    st.markdown("#### 🎯 Localizar Técnico/Equipe")
    
    f_base, f_sup = st.columns(2)
    df_filtrado = df_prod.copy()

    # 1. Filtro de Base
    with f_base:
        if col_base:
            lista_bases = ["Todas"] + sorted([str(b) for b in df_filtrado[col_base].dropna().unique() if str(b).strip() != ""])
            base_sel = st.selectbox("📍 Filtrar por Base:", lista_bases)
            if base_sel != "Todas":
                df_filtrado = df_filtrado[df_filtrado[col_base] == base_sel]
        else:
            base_sel = "Todas"

    # 2. Filtro de Gestor
    with f_sup:
        if col_sup:
            lista_monitores = ["Todos"] + sorted([str(m) for m in df_filtrado[col_sup].dropna().unique() if str(m).strip() != ""])
            sup_sel = st.selectbox("👤 Filtrar por Supervisor:", lista_monitores)
            if sup_sel != "Todos":
                df_filtrado = df_filtrado[df_filtrado[col_sup] == sup_sel]
        else:
            sup_sel = "Todos"

    st.divider()

    # 3. Seleção Final
    col_busca, col_info = st.columns([1, 2], gap="large")
    lista_tecnicos = sorted([t for t in df_filtrado[col_tec].unique() if t and t != "NAN"])
    
    with col_busca:
        tec_selecionado = st.selectbox("🔎 Selecione a Equipe/Técnico:", options=[""] + lista_tecnicos)

    if tec_selecionado:
        # Isola a base do técnico selecionado
        df_tec_prod = df_prod[df_prod[col_tec] == tec_selecionado].copy()
        
        sup_tec = df_tec_prod[col_sup].iloc[0] if col_sup and not df_tec_prod.empty else "Não Atribuído"
        base_tec = df_tec_prod[col_base].iloc[0] if col_base and not df_tec_prod.empty else "Não Atribuída"
        
        with col_info:
            st.markdown("<br>", unsafe_allow_html=True)
            st.info(f"**👤 Supervisor:** {sup_tec} ㅤ|ㅤ **📍 Projeto/Base:** {base_tec}")

# ====================================================
# BLOCO 8: RENDERIZAÇÃO DO RELATÓRIO OPERACIONAL
# ====================================================
if tec_selecionado:
    st.divider()
    
    if df_tec_prod.empty:
        st.warning("⚠️ Nenhum dado de Execução Física (O.S./Pontos) encontrado para esta equipe.")
        st.stop()
        
    t_pontos = df_tec_prod["Pontos"].sum() if "Pontos" in df_tec_prod.columns else 0.0
    t_os = len(df_tec_prod)
    pontos_por_os = (t_pontos / t_os) if t_os > 0 else 0.0
    
    # 1. CARDS DE KPI (Agora com as 2 casas decimais cravadas)
    st.markdown(f"### ⚙️ Execução Física de **{tec_selecionado}**")
    kr1, kr2, kr3 = st.columns(3)
    with kr1: st.markdown(ComponenteVisual.criar_card("O.S. Realizadas", str(t_os), "cinza", "Total de Visitas Executadas", "📋"), unsafe_allow_html=True)
    with kr2: st.markdown(ComponenteVisual.criar_card("Pontuação Total", Utilitarios.formatar_numero(t_pontos), "azul", "Soma de Pontos Acumulados", "🎯"), unsafe_allow_html=True)
    with kr3: st.markdown(ComponenteVisual.criar_card("Ticket Médio", Utilitarios.formatar_numero(pontos_por_os), "roxo", "Pts médio por O.S.", "🔌"), unsafe_allow_html=True)
    
    st.write("---")
    
    # 2. GRÁFICO DE PRODUÇÃO
    col_data_prod = Utilitarios.encontrar_coluna_data(df_tec_prod)
    
    if col_data_prod:
        st.markdown("#### 📊 Evolução Diária (Volume vs Qualidade)")
        
        # Tratamento seguro de datas para o gráfico
        df_grafico = df_tec_prod.dropna(subset=[col_data_prod]).copy()
        df_grafico[col_data_prod] = pd.to_datetime(df_grafico[col_data_prod]).dt.date
        df_tempo_prod = df_grafico.groupby(col_data_prod).agg(Pontos=('Pontos', 'sum'), Qtd_OS=('Pontos', 'count')).reset_index()
        
        st.plotly_chart(Graficos.grafico_combo_raiox(df_tempo_prod, col_data_prod, "Qtd_OS", "Pontos"), use_container_width=True)
    else:
        st.info("⚠️ Coluna de data não encontrada para plotar o gráfico de evolução.")
    
    st.write("---")
    
    # 3. TABELA DE EXTRATO OPERACIONAL
    st.markdown("#### 🧾 Extrato Operacional Detalhado")
    
    # Remove colunas desnecessárias para limpeza visual
    col_ignorar = ['lat', 'lon', 'Posição', 'Cidade']
    colunas_exibir = [c for c in df_tec_prod.columns if c not in col_ignorar]
    
    # Configuração de colunas padrão
    config_colunas = {
        "Pontos": st.column_config.NumberColumn("Pontos", format="%.2f") # Força visualização 2 casas decimais na tabela
    }

    # Ordena da data mais recente para a mais antiga (se a coluna existir)
    if col_data_prod:
        df_exibir = df_tec_prod[colunas_exibir].sort_values(by=col_data_prod, ascending=False)
        config_colunas[col_data_prod] = st.column_config.DateColumn("Data", format="DD/MM/YYYY")
    else:
        df_exibir = df_tec_prod[colunas_exibir]

    st.dataframe(
        df_exibir, 
        use_container_width=True, 
        hide_index=True,
        column_config=config_colunas
    )