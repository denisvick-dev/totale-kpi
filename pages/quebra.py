import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

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
        "vermelho": {"fundo": "#FEF2F2", "texto": "#B91C1C", "borda": "#EF4444", "titulo": "#991B1B"}, 
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
# BLOCO 3: CARREGAMENTO E PREPARAÇÃO
# ====================================================
class CarregadorDados:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(arquivo_enviado) -> pd.DataFrame:
        try:
            nome_arquivo = arquivo_enviado.name.lower()
            if nome_arquivo.endswith('.csv'):
                return pd.read_csv(arquivo_enviado, sep=None, engine='python', encoding='utf-8')
            elif nome_arquivo.endswith(('.xlsx', '.xls')):
                return pd.read_excel(arquivo_enviado, engine="openpyxl")
            else:
                st.error("⚠️ Formato não suportado.")
                return pd.DataFrame()
        except Exception as e:
            st.error(f"⚠️ Erro ao ler o arquivo: {e}")
            return pd.DataFrame()

@st.cache_data(show_spinner=False)
def preparar_base_cache(df: pd.DataFrame) -> pd.DataFrame:
    """Limpa a base blindando contra letras maiúsculas/minúsculas e espaços."""
    df = df.copy()
    
    # 1. Padroniza os nomes das colunas (tudo maiúsculo e sem espaços em branco nas pontas)
    df.columns = df.columns.str.strip().str.upper()
    
    # 2. Remove nulos da coluna Contrato (se ela existir)
    if 'CONTRATO' in df.columns:
        df = df.dropna(subset=['CONTRATO'])
    
    # 3. Trata a coluna Status da Atividade
    if 'STATUS DA ATIVIDADE' in df.columns:
        # Transforma os dados da coluna em maiúsculo para não haver erro de case sensitive
        df['STATUS DA ATIVIDADE'] = df['STATUS DA ATIVIDADE'].astype(str).str.strip().str.upper()
        df = df[df['STATUS DA ATIVIDADE'] != 'SUSPENSO']
        
    return df
 
def localizar_tipos(df: pd.DataFrame, coluna: str, valor: str) -> pd.DataFrame:
    """Localiza linhas em que a coluna especificada contém o valor desejado (case insensitive) e coloca em uma nova coluna."""
    if 'HABILIDADE DE TRABALHO' in df.columns:
       df['Check_MESH'] = df['HABILIDADE DE TRABALHO'].astype(str).str.contains('MESH', case=False, na=False)
       df['Check_PME'] = df['HABILIDADE DE TRABALHO'].astype(str).str.contains('PME', case=False, na=False)
       return df
    else:
        st.warning(f"⚠️ Coluna '{coluna}' não encontrada na base de dados.")
        return pd.DataFrame() 

# ====================================================
# BLOCO 4: INICIALIZAÇÃO DA PÁGINA E FRONT-END
# ====================================================
st.set_page_config(page_title="Quebra de Agenda", page_icon="📊", layout="wide")
st.title("🗣️ Indicador: Quebra de Agenda")
st.markdown("Auditoria de ordens não executadas e absenteísmo técnico.")

arquivo = st.file_uploader("📥 Envie sua base de dados (Excel ou CSV)", type=["xlsx", "xls", "csv"])

if arquivo is not None:
    # 1. Lê e limpa os dados
    df_bruto = CarregadorDados.ler_arquivo(arquivo)
    df = preparar_base_cache(df_bruto)
    
    if not df.empty:
        # 2. Lógica de Classificação de Status
        col_status = 'STATUS DA O.S 1'
        
        if col_status in df.columns:
            # Padroniza a coluna alvo antes do IF
            df[col_status] = df[col_status].astype(str).str.strip().str.upper()
            
            def classificar_os(status):
                if status == 'EXECUTADA': return 'Executada'
                elif status in ['NÃO EXECUTADA', 'NAO EXECUTADA']: return 'Não Executada'
                else: return 'Pendente'
                
            df['Status Contrato'] = df[col_status].apply(classificar_os)
            
            df['TOTAL DE TAREFAS'] = pd.to_numeric(df['TOTAL DE TAREFAS'], errors='coerce').fillna(0)
                
            # Soma a coluna "Total de Tarefas" de acordo com o status da linha
            total_os     = int(df['TOTAL DE TAREFAS'].sum())
            qtd_exec     = int(df.loc[df['Status Contrato'] == 'Executada', 'TOTAL DE TAREFAS'].sum())
            qtd_nao_exec = int(df.loc[df['Status Contrato'] == 'Não Executada', 'TOTAL DE TAREFAS'].sum())
            qtd_pendente = int(df.loc[df['Status Contrato'] == 'Pendente', 'TOTAL DE TAREFAS'].sum())
            
            # 🔥 Nova Fórmula da Quebra: Não Executadas / Total de Tarefas
            tx_quebra = (qtd_nao_exec / total_os) if total_os > 0 else 0
            
            # Cria as colunas de verificação de tipo (MESH e PME) e as renomeia
            df = localizar_tipos(df, 'HABILIDADE DE TRABALHO', 'MESH')
            df = localizar_tipos(df, 'HABILIDADE DE TRABALHO', 'PME')
            df = df.rename(columns={'Check_MESH': 'É MESH?', 'Check_PME': 'É PME?'})
            
            # 4. RENDERIZAÇÃO DOS CARDS
            st.divider()
            st.markdown("### 🎯 Visão Geral")
            c1, c2, c3, c4 = st.columns(4)
            
            with c1: st.markdown(ComponenteVisual.criar_card("Total Tarefas", str(total_os), "azul", "Volume da Planilha", "📋"), unsafe_allow_html=True)
            with c2: st.markdown(ComponenteVisual.criar_card("Executadas", str(qtd_exec), "verde", "Sucesso", "✅"), unsafe_allow_html=True)
            with c3: st.markdown(ComponenteVisual.criar_card("Não Executadas", str(qtd_nao_exec), "laranja", "Quebras", "⚠️"), unsafe_allow_html=True)
            
            # Define a cor baseada no % de quebra (Ex: Acima de 15% fica vermelho)
            cor_quebra = "vermelho" if tx_quebra > 0.15 else "roxo"
            
            # 🔥 Subtítulo do card atualizado para refletir o cálculo pelo Total
            with c4: st.markdown(ComponenteVisual.criar_card("Taxa de Quebra", f"{tx_quebra:.1%}", cor_quebra, "Não Exec. / Total Tarefas", "📉"), unsafe_allow_html=True)
            
            st.write("---")
            
            # 5. GRÁFICO E TABELA
            g1, g2 = st.columns([1, 2])
            
            with g1:
                st.markdown("#### 📊 Distribuição")
                df_grafico = df.groupby('Status Contrato')['TOTAL DE TAREFAS'].sum().reset_index()
                df_grafico = df_grafico.rename(columns={'Status Contrato': 'Status', 'TOTAL DE TAREFAS': 'Quantidade'})
                
                fig = px.pie(df_grafico, names='Status', values='Quantidade', hole=0.5,
                             color='Status', color_discrete_map={'Executada': '#196B24', 'Não Executada': '#A30000', 'Pendente': '#C2C2C2'})
                fig.update_traces(textposition='inside', textinfo='percent+label')
                fig.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0))
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                
            with g2:
                st.markdown("#### 🧾 Base de Dados Processada")
                st.dataframe(df, use_container_width=True, hide_index=True)
                
        else:
            st.error(f"⚠️ A coluna '{col_status}' não foi encontrada na base de dados.")
            st.info(f"Colunas encontradas: {', '.join(df.columns)}")