import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import Optional, List

# ====================================================
# BLOCO 1: CONFIGURAÇÕES GLOBAIS
# ====================================================
class Configuracoes:
    TEMAS_CARD = {
        "azul": {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
        "verde": {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
        "laranja": {"fundo": "#FFF7ED", "texto": "#C2410C", "borda": "#F97316", "titulo": "#9A3412"},
        "amarelo": {"fundo": "#FEF9C3", "texto": "#A16207", "borda": "#EAB308", "titulo": "#854D0E"},
        "roxo": {"fundo": "#FAF5FF", "texto": "#7E22CE", "borda": "#A855F7", "titulo": "#581C87"}, 
    }

# ====================================================
# BLOCO 2: COMPONENTES VISUAIS
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
    def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return df
        df.columns = df.columns.str.upper().str.strip()
        
        mapa = {
            "QTDE_CONSULTIVO": "CONSULTIVOS", "QTDE. CONS.": "CONSULTIVOS", "QTDE_CONS": "CONSULTIVOS",
            "QTDE_PRODUTOS": "VENDAS", "QTDE. PROD.": "VENDAS", "PRODUTOS": "VENDAS",
            "QTDE_MESH": "MESH", "QTDE. MESH": "MESH",
            "QTDE_TV": "TV", "QTDE. TV": "TV",
            "QTDE_VIRTUA": "VIRTUA", "QTDE. VIRTUA": "VIRTUA"
        }
        for col_origem, col_destino in mapa.items():
            if col_origem in df.columns:
                df[col_destino] = pd.to_numeric(df[col_origem], errors="coerce").fillna(0).astype(int)
        return df

    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras_chave: List[str]) -> Optional[str]:
        """Busca genérica de colunas baseada em palavras-chave."""
        cols_upper = {c.upper(): c for c in df.columns}
        for palavra in palavras_chave:
            if palavra in cols_upper: 
                return cols_upper[palavra]
        return None

# ====================================================
# BLOCO 4: GRÁFICOS
# ====================================================
class Graficos:
    @staticmethod
    def grafico_linhas_vendas(df: pd.DataFrame, x_col: str, y_cons: str, y_prod: str) -> go.Figure:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df[x_col], y=df[y_cons], name='Oportunidades', mode='lines+markers', line=dict(color='#94A3B8', width=2)))
        fig.add_trace(go.Scatter(x=df[x_col], y=df[y_prod], name='Vendas', mode='lines+markers', line=dict(color='#22C55E', width=3), marker=dict(size=8)))
        
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), hovermode="x unified",
            yaxis=dict(title="Quantidade", showgrid=True, gridcolor="rgba(0,0,0,0.05)")
        )
        return fig

    @staticmethod
    def grafico_rosca_mix(df_mix: pd.DataFrame) -> go.Figure:
        fig = px.pie(df_mix, names="Produto", values="Quantidade", hole=0.6, color_discrete_sequence=['#A855F7', '#F97316', '#3B82F6'])
        fig.update_traces(textposition='inside', textinfo='percent+label')
        fig.update_layout(margin=dict(t=10, b=10, l=0, r=0), showlegend=False, paper_bgcolor="rgba(0,0,0,0)")
        return fig

# ====================================================
# BLOCO 5: MOCK DE DADOS (TESTE)
# ====================================================
@st.cache_data(show_spinner=False)
def gerar_dados_teste():
    import numpy as np
    datas = pd.date_range(start="2023-10-01", periods=15, freq="D").tolist() * 3
    tecnicos = ["JOAO SILVA", "MARIA SOUZA", "CARLOS ALBERTO"] * 15
    return pd.DataFrame({
        "DATA": datas, "VENDEDOR": tecnicos, "MONITOR": ["SUP A", "SUP B", "SUP A"] * 15,
        "BASE": ["SP", "SP", "CAMPINAS"] * 15,
        "QTDE_CONSULTIVO": np.random.randint(3, 12, size=45), 
        "QTDE_PRODUTOS": np.random.randint(0, 5, size=45),
        "QTDE_MESH": np.random.randint(0, 3, size=45), 
        "QTDE_TV": np.random.randint(0, 2, size=45), 
        "QTDE_VIRTUA": np.random.randint(0, 2, size=45)
    })

# ====================================================
# BLOCO 6: INICIALIZAÇÃO DA PÁGINA E BASE
# ====================================================
st.set_page_config(page_title="Visão Consultivo", page_icon="🗣️", layout="wide")
st.title("🗣️ Raio-X: Módulo Consultivo (Vendas)")
st.markdown("Auditoria de performance comercial, taxa de conversão e mix de produtos ofertados.")

# Busca dados da Sessão
df_cons = None
if "df_consultivo" in st.session_state:
    df_cons = st.session_state["df_consultivo"]
elif "dados_cons" in st.session_state:
    df_cons = st.session_state["dados_cons"].get("Consultivo", pd.DataFrame())

if df_cons is None or df_cons.empty:
    st.warning("⚠️ Base não encontrada na sessão. Carregando dados de demonstração.")
    df_cons = gerar_dados_teste()

df_cons = Utilitarios.padronizar_colunas(df_cons)

# Identificação de colunas usando a nova função genérica
col_tec = Utilitarios.buscar_coluna(df_cons, ["VENDEDOR", "TÉCNICO", "TECNICO", "NOME EQUIPE", "LOGIN"])
col_sup = Utilitarios.buscar_coluna(df_cons, ["SUPERVISOR", "MONITOR", "GESTOR", "COORDENADOR", "LÍDER"])
col_base = Utilitarios.buscar_coluna(df_cons, ["BASE", "PROJETO", "CIDADE", "FILIAL", "LOCALIDADE"])
col_data = Utilitarios.buscar_coluna(df_cons, ["DATA", "DATA AGENDAMENTO", "DATE"])

if not col_tec:
    st.error("❌ Coluna de Vendedor/Técnico não encontrada.")
    st.stop()

# Limpeza da coluna técnico
df_cons[col_tec] = df_cons[col_tec].astype(str).str.strip().str.upper()

# ====================================================
# BLOCO 7: MOTOR DE BUSCA EM CASCATA
# ====================================================
with st.container(border=True):
    st.markdown("#### 🎯 Localizar Técnico")
    
    f_base, f_sup = st.columns(2)
    
    # Máscaras de filtro (Mais rápido que copiar o DataFrame inteiro)
    mask = pd.Series(True, index=df_cons.index)

    with f_base:
        if col_base:
            bases = ["Todas"] + sorted([str(b) for b in df_cons[col_base].dropna().unique() if str(b).strip() != ""])
            base_sel = st.selectbox("📍 Filtrar por Base:", bases)
            if base_sel != "Todas":
                mask &= (df_cons[col_base] == base_sel)

    with f_sup:
        if col_sup:
            monitores = ["Todos"] + sorted([str(m) for m in df_cons.loc[mask, col_sup].dropna().unique() if str(m).strip() != ""])
            sup_sel = st.selectbox("👤 Filtrar por Gestor:", monitores)
            if sup_sel != "Todos":
                mask &= (df_cons[col_sup] == sup_sel)

    st.divider()

    col_busca, col_info = st.columns([1, 2], gap="large")
    tecnicos_filtrados = sorted([t for t in df_cons.loc[mask, col_tec].unique() if t and t != "NAN"])
    
    with col_busca:
        tec_selecionado = st.selectbox("🔎 Selecione o Técnico:", options=[""] + tecnicos_filtrados)

    df_tec = pd.DataFrame()
    if tec_selecionado:
        df_tec = df_cons[df_cons[col_tec] == tec_selecionado].copy()
        
        # Coleta de forma segura (pegando o valor mais frequente em caso de troca de supervisor)
        sup_tec = df_tec[col_sup].mode()[0] if col_sup and not df_tec[col_sup].empty else "Não Atribuído"
        base_tec = df_tec[col_base].mode()[0] if col_base and not df_tec[col_base].empty else "Não Atribuída"
        
        with col_info:
            st.markdown("<br>", unsafe_allow_html=True)
            st.info(f"**👤 Gestor Comercial:** {sup_tec} ㅤ|ㅤ **📍 Base:** {base_tec}")

# ====================================================
# BLOCO 8: RENDERIZAÇÃO DO DASHBOARD
# ====================================================
if tec_selecionado and not df_tec.empty:
    st.divider()
    
    if "CONSULTIVOS" not in df_tec.columns or "VENDAS" not in df_tec.columns:
        st.error("Colunas métricas (CONSULTIVOS/VENDAS) ausentes.")
        st.stop()

    t_cons = int(df_tec["CONSULTIVOS"].sum())
    t_prod = int(df_tec["VENDAS"].sum())
    taxa_conversao = (t_prod / t_cons) if t_cons > 0 else 0

    # 1. CARDS
    st.markdown(f"### 🎯 Funil de Abordagem de **{tec_selecionado}**")
    vc1, vc2, vc3 = st.columns(3)
    with vc1: st.markdown(ComponenteVisual.criar_card("Oportunidades", str(t_cons), "azul", "Tentativas", "🗣️"), unsafe_allow_html=True)
    with vc2: st.markdown(ComponenteVisual.criar_card("Vendas Fechadas", str(t_prod), "amarelo", "Produtos", "🚀"), unsafe_allow_html=True)
    
    cor_win = "verde" if taxa_conversao >= 0.1 else "laranja"
    with vc3: st.markdown(ComponenteVisual.criar_card("Win Rate", f"{taxa_conversao:.1%}", cor_win, "Conversão", "📈"), unsafe_allow_html=True)
    
    st.write("---")

    # 2. GRÁFICOS
    g_linha, g_pizza = st.columns([2, 1])
    
    with g_linha:
        st.markdown("#### 📉 Ritmo de Ofertas Diárias")
        if col_data:
            # Tratamento de erro seguro para datas
            df_tec[col_data] = pd.to_datetime(df_tec[col_data], errors="coerce").dt.date
            df_tec_grafico = df_tec.dropna(subset=[col_data])
            
            if not df_tec_grafico.empty:
                df_tempo = df_tec_grafico.groupby(col_data)[["CONSULTIVOS", "VENDAS"]].sum().reset_index()
                st.plotly_chart(Graficos.grafico_linhas_vendas(df_tempo, col_data, "CONSULTIVOS", "VENDAS"), use_container_width=True)
            else:
                st.info("Nenhuma data válida encontrada para este técnico.")
        else:
            st.info("Coluna de data não encontrada na base.")

    with g_pizza:
        st.markdown("#### 📦 Mix de Produtos")
        mix_data = {
            "Mesh": int(df_tec["MESH"].sum()) if "MESH" in df_tec.columns else 0,
            "TV": int(df_tec["TV"].sum()) if "TV" in df_tec.columns else 0,
            "Virtua": int(df_tec["VIRTUA"].sum()) if "VIRTUA" in df_tec.columns else 0
        }
        
        df_mix = pd.DataFrame(list(mix_data.items()), columns=["Produto", "Quantidade"])
        df_mix = df_mix[df_mix["Quantidade"] > 0]
        
        if not df_mix.empty:
            st.plotly_chart(Graficos.grafico_rosca_mix(df_mix), use_container_width=True)
        else:
            st.warning("Nenhum produto (Mesh/TV/Virtua) vendido.")

    st.write("---")

    # 3. TABELA DETALHADA
    st.markdown("#### 🧾 Extrato Comercial Detalhado")
    
    colunas_exibir = [c for c in [col_data, col_tec, "CONSULTIVOS", "VENDAS", "MESH", "TV", "VIRTUA"] if c is not None and c in df_tec.columns]
    df_exibir = df_tec[colunas_exibir].copy()
    
    if col_data:
        df_exibir = df_exibir.sort_values(by=col_data, ascending=False)

    max_vendas = int(df_exibir["VENDAS"].max()) if not df_exibir.empty else 10

    # 1. Criamos um dicionário base apenas com strings fixas (isso resolve o erro da IDE)
    configs_tabela = {
        "CONSULTIVOS": st.column_config.NumberColumn("🗣️ Oportunidades", help="Total de abordagens"),
        "VENDAS": st.column_config.ProgressColumn("💰 Vendas", format="%d", min_value=0, max_value=max_vendas),
        "MESH": st.column_config.NumberColumn("📶 Mesh"),
        "TV": st.column_config.NumberColumn("📺 TV"),
        "VIRTUA": st.column_config.NumberColumn("🌐 Virtua")
    }

    # 2. Adicionamos as colunas dinâmicas apenas se elas existirem (garantindo que são strings)
    if col_data is not None:
        configs_tabela[col_data] = st.column_config.DateColumn("Data", format="DD/MM/YYYY")
        
    if col_tec is not None:
        configs_tabela[col_tec] = st.column_config.TextColumn("Técnico")

    # 3. Renderizamos o dataframe passando o dicionário limpo
    st.dataframe(
        df_exibir, 
        use_container_width=True, 
        hide_index=True,
        column_config=configs_tabela
    )