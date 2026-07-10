import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection

# ====================================================
# BLOCO 1: CONFIGURAÇÕES GLOBAIS E SLA
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
    
    url_ativos = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    SLA_QUEBRA_MAXIMA = 0.20 # 20% de meta máxima de quebra aceitável

# ====================================================
# BLOCO 2: UTILITÁRIOS E COMPONENTES VISUAIS
# ====================================================
class Utilitarios:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras_chave: list) -> str:
        """Busca genérica de colunas ignorando acentos e maiúsculas/minúsculas."""
        cols_upper = {c.upper(): c for c in df.columns}
        for palavra in palavras_chave:
            if palavra.upper() in cols_upper:
                return cols_upper[palavra.upper()]
        return None

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
        
    @staticmethod
    def grafico_velocimetro(valor: float, meta: float) -> go.Figure:
        fig = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = valor * 100,
            number = {'suffix': "%", 'valueformat': '.1f', 'font': {'size': 40}},
            title = {'text': "Termômetro de Quebra", 'font': {'size': 18}},
            gauge = {
                'axis': {'range': [0, max(30, valor * 100 + 10)], 'tickwidth': 1, 'tickcolor': "darkblue"},
                'bar': {'color': "#1E293B"},
                'bgcolor': "white",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, meta * 100], 'color': "#bbf7d0"}, # Verde
                    {'range': [meta * 100, (meta+0.05) * 100], 'color': "#fef08a"}, # Amarelo
                    {'range': [(meta+0.05) * 100, 100], 'color': "#fecaca"}], # Vermelho
                'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': meta * 100}
            }
        ))
        fig.update_layout(margin=dict(t=50, b=20, l=20, r=20), height=250)
        return fig

# ====================================================
# BLOCO 3: MOTOR DE DADOS (CARREGAMENTO E PREPARAÇÃO)
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
        
    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def carregar_ativos(url: str) -> pd.DataFrame:
        conexao = st.connection("gsheets", type=GSheetsConnection)
        return conexao.read(spreadsheet=url, ttl=0)

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_dados_gsheets() -> pd.DataFrame:
        try:
            df_gs = CarregadorDados.carregar_ativos(Configuracoes.url_ativos)
            df_gs.columns = df_gs.columns.str.strip().str.upper()
            
            # Busca dinâmica e renomeação blindada
            col_login = Utilitarios.buscar_coluna(df_gs, ['LOGIN', 'ID', 'MATRÍCULA', 'MATRICULA'])
            col_tec = Utilitarios.buscar_coluna(df_gs, ['TÉCNICO', 'TECNICO', 'NOME', 'VENDEDOR'])
            col_mon = Utilitarios.buscar_coluna(df_gs, ['MONITOR', 'GESTOR', 'SUPERVISOR'])
            
            renomear = {}
            if col_login: renomear[col_login] = 'LOGIN'
            if col_tec: renomear[col_tec] = 'TÉCNICO'
            if col_mon: renomear[col_mon] = 'MONITOR'
            df_gs = df_gs.rename(columns=renomear)
            
            if 'LOGIN' in df_gs.columns:
                df_gs['LOGIN'] = df_gs['LOGIN'].astype(str).str.replace('.0', '', regex=False).str.strip().str.upper()
            if 'TÉCNICO' in df_gs.columns: 
                df_gs['TÉCNICO'] = df_gs['TÉCNICO'].astype(str).str.strip().str.upper()
            if 'MONITOR' in df_gs.columns: 
                df_gs['MONITOR'] = df_gs['MONITOR'].astype(str).str.strip().str.upper()
            
            return df_gs
        except Exception:
            st.warning("⚠️ Não foi possível carregar a hierarquia do Google Sheets. Verifique o link ou a conexão.")
            return pd.DataFrame()

@st.cache_data(show_spinner=False)
def preparar_base_cache(df: pd.DataFrame, df_hierarquia: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip().str.upper()
    
    # Previne erro de falta de acento vindo da planilha do usuário
    col_tec_usuario = Utilitarios.buscar_coluna(df, ['TÉCNICO', 'TECNICO'])
    if col_tec_usuario and col_tec_usuario != 'TÉCNICO':
        df = df.rename(columns={col_tec_usuario: 'TÉCNICO'})
        
    col_mon_usuario = Utilitarios.buscar_coluna(df, ['MONITOR', 'SUPERVISOR', 'GESTOR'])
    if col_mon_usuario and col_mon_usuario != 'MONITOR':
        df = df.rename(columns={col_mon_usuario: 'MONITOR'})
    
    if 'TOTAL DE TAREFAS' not in df.columns: df['TOTAL DE TAREFAS'] = 1 
    else: df['TOTAL DE TAREFAS'] = pd.to_numeric(df['TOTAL DE TAREFAS'], errors='coerce').fillna(0)
    
    if 'CONTRATO' in df.columns: df = df.dropna(subset=['CONTRATO'])
    
    if 'STATUS DA ATIVIDADE' in df.columns:
        df['STATUS DA ATIVIDADE'] = df['STATUS DA ATIVIDADE'].astype(str).str.strip().str.upper()
        df = df[df['STATUS DA ATIVIDADE'] != 'SUSPENSO']

    if 'HABILIDADE DE TRABALHO' in df.columns:
        df['É MESH?'] = df['HABILIDADE DE TRABALHO'].astype(str).str.contains('MESH', case=False, na=False).map({True: 'Sim', False: 'Não'})
        df['É PME?'] = df['HABILIDADE DE TRABALHO'].astype(str).str.contains('PME', case=False, na=False).map({True: 'Sim', False: 'Não'})
        
    # 🔥 MUDANÇA AQUI: Adicionado 'LOGIN DO TÉCNICO' na lista de busca
    col_login_upload = Utilitarios.buscar_coluna(df, ['LOGIN DO TÉCNICO', 'LOGIN TÉCNICO', 'LOGIN TECNICO', 'LOGIN', 'USUÁRIO', 'USUARIO', 'MATRÍCULA', 'MATRICULA', 'ID'])
            
    if col_login_upload and not df_hierarquia.empty and 'LOGIN' in df_hierarquia.columns:
        # Limpa o login do excel (tira espaços, .0, e poe em maiusculo)
        df[col_login_upload] = df[col_login_upload].astype(str).str.replace('.0', '', regex=False).str.strip().str.upper()
        
        # Pega a base do Google Sheets
        df_hierarquia = df_hierarquia[['LOGIN', 'TÉCNICO', 'MONITOR']].drop_duplicates(subset=['LOGIN'], keep='last')
        
        # Remove as colunas originais de Técnico e Monitor da base subida (se tiverem vazias ou erradas)
        colunas_remover = [c for c in ['TÉCNICO', 'MONITOR'] if c in df.columns]
        if colunas_remover: df = df.drop(columns=colunas_remover)
            
        # 🔥 FAZ O MERGE USANDO O "LOGIN DO TÉCNICO" DA SUA PLANILHA
        df = df.merge(df_hierarquia, left_on=col_login_upload, right_on='LOGIN', how='left')
        
        # Preenche com aviso caso o técnico não esteja cadastrado no seu Google Sheets
        df['TÉCNICO'] = df['TÉCNICO'].fillna('NÃO MAPEADO NO SHEETS')
        df['MONITOR'] = df['MONITOR'].fillna('SEM MONITOR')
        
        # Limpa a coluna 'LOGIN' que veio do Google Sheets para não duplicar com 'LOGIN DO TÉCNICO'
        if col_login_upload != 'LOGIN': df = df.drop(columns=['LOGIN'], errors='ignore')

    # Garante que as colunas sempre sejam criadas (Proteção de Falha)
    if 'TÉCNICO' not in df.columns:
        df['TÉCNICO'] = 'NÃO INFORMADO'
        
    if 'MONITOR' not in df.columns:
        df['MONITOR'] = 'SEM MONITOR'
            
    return df

def classificar_os(status):
    status = str(status).strip().upper()
    if status == 'EXECUTADA': return 'Executada'
    elif status in ['NÃO EXECUTADA', 'NAO EXECUTADA']: return 'Não Executada'
    else: return 'Pendente'

def encontrar_coluna_motivo(df: pd.DataFrame):
    possiveis_nomes = ['MOTIVO', 'MOTIVO BAIXA', 'SUBSTATUS', 'SUB STATUS', 'DESCRIÇÃO', 'OBSERVAÇÃO']
    for nome in possiveis_nomes:
        if nome in df.columns: return nome
    return None

# ====================================================
# BLOCO 4: APP (FRONT-END E DASHBOARD)
# ====================================================
st.set_page_config(page_title="Quebra de Agenda", page_icon="📊", layout="wide")
st.title("🗣️ Indicador: Quebra de Agenda")
st.markdown("Auditoria de ordens não executadas, absenteísmo e fila de tratamento de clientes.")

# 1. Cria a variável na memória do Streamlit (se não existir)
if 'df_memoria' not in st.session_state:
    st.session_state['df_memoria'] = None

# 2. SE NÃO TIVER ARQUIVO NA MEMÓRIA: Mostra o Uploader
if st.session_state['df_memoria'] is None:
    arquivo = st.file_uploader("📥 Envie sua base de dados (Excel ou CSV)", type=["xlsx", "xls", "csv"])
    
    if arquivo is not None:
        with st.spinner("Processando dados e cruzando com Google Sheets..."):
            # Lê o arquivo e o GSheets
            df_bruto = CarregadorDados.ler_arquivo(arquivo)
            df_gsheets = CarregadorDados.buscar_dados_gsheets()
            
            # Prepara a base e cruza os dados
            df_full = preparar_base_cache(df_bruto, df_gsheets)
            
            # SALVA NA MEMÓRIA
            st.session_state['df_memoria'] = df_full
            
        # Recarrega a página automaticamente (Isso faz o Uploader sumir!)
        st.rerun()

# 3. SE JÁ TIVER ARQUIVO NA MEMÓRIA: Esconde Uploader e Mostra Dashboard
else:
    # Puxa os dados salvos da memória
    df_full = st.session_state['df_memoria']
    
    # Cabeçalho com botão de reset
    col_aviso, col_btn = st.columns([4, 1])
    with col_aviso:
        st.success("✅ Base processada com sucesso!")
    with col_btn:
        if st.button("🔄 Enviar outra base", use_container_width=True):
            st.session_state['df_memoria'] = None
            st.rerun() # Limpa a memória e volta o Uploader
            
    # --- DAQUI PARA BAIXO É O SEU DASHBOARD NORMAL ---
    if not df_full.empty:
        col_status = Utilitarios.buscar_coluna(df_full, ['STATUS DA O.S 1', 'STATUS OS', 'STATUS'])
        col_motivo = encontrar_coluna_motivo(df_full)
        
        if col_status:
            df_full['Status Contrato'] = df_full[col_status].apply(classificar_os)
            
            # --- SIDEBAR DE FILTROS ---
            with st.sidebar:
                st.header("🎯 Filtros Analíticos")
                df_filtrado = df_full.copy()
                
                # Alerta de Logins não mapeados
                if 'TÉCNICO' in df_filtrado.columns:
                    qtd_nao_mapeados = len(df_filtrado[df_filtrado['TÉCNICO'] == 'NÃO MAPEADO NO SHEETS'])
                    if qtd_nao_mapeados > 0:
                        st.error(f"⚠️ **Auditoria:** {qtd_nao_mapeados} tarefas estão vinculadas a logins que NÃO existem no Google Sheets.")
                    st.divider()
                
                # Filtros Dinâmicos
                if 'MONITOR' in df_filtrado.columns:
                    monitores = sorted([str(m) for m in df_filtrado['MONITOR'].unique() if str(m) != "nan" and m != 'SEM MONITOR'])
                    filtro_mon = st.selectbox(f"👔 Monitor ({len(monitores)}):", ["Todos"] + monitores)
                    if filtro_mon != "Todos": df_filtrado = df_filtrado[df_filtrado['MONITOR'] == filtro_mon]
                
                if 'É MESH?' in df_filtrado.columns:
                    filtro_mesh = st.selectbox("📶 É MESH?", ["Todos", "Sim", "Não"])
                    if filtro_mesh != "Todos": df_filtrado = df_filtrado[df_filtrado['É MESH?'] == filtro_mesh]
                        
                if 'TÉCNICO' in df_filtrado.columns:
                    tecnicos = sorted([str(t) for t in df_filtrado['TÉCNICO'].unique() if str(t) != "nan" and t != 'NÃO MAPEADO NO SHEETS'])
                    filtro_tec = st.selectbox(f"👤 Técnico ({len(tecnicos)}):", ["Todos"] + tecnicos)
                    if filtro_tec != "Todos": df_filtrado = df_filtrado[df_filtrado['TÉCNICO'] == filtro_tec]

            df = df_filtrado.copy()

            # --- CÁLCULO DE KPIs ---
            total_os     = int(df['TOTAL DE TAREFAS'].sum())
            qtd_exec     = int(df.loc[df['Status Contrato'] == 'Executada', 'TOTAL DE TAREFAS'].sum())
            qtd_nao_exec = int(df.loc[df['Status Contrato'] == 'Não Executada', 'TOTAL DE TAREFAS'].sum())
            qtd_pendente = int(df.loc[df['Status Contrato'] == 'Pendente', 'TOTAL DE TAREFAS'].sum())
            
            tx_quebra = (qtd_nao_exec / total_os) if total_os > 0 else 0
            
            # --- CARDS DE VISÃO GERAL ---
            st.divider()
            st.markdown("### 🎯 Visão Geral do Período")
            c1, c2, c3, c4 = st.columns(4)
            with c1: st.markdown(ComponenteVisual.criar_card("Total Tarefas", f"{total_os:,}".replace(',', '.'), "azul", "Volume Alocado", "📋"), unsafe_allow_html=True)
            with c2: st.markdown(ComponenteVisual.criar_card("Executadas", f"{qtd_exec:,}".replace(',', '.'), "verde", "Sucesso", "✅"), unsafe_allow_html=True)
            with c3: st.markdown(ComponenteVisual.criar_card("Não Executadas", f"{qtd_nao_exec:,}".replace(',', '.'), "laranja", "Quebras", "⚠️"), unsafe_allow_html=True)
            
            cor_quebra = "vermelho" if tx_quebra > Configuracoes.SLA_QUEBRA_MAXIMA else "roxo"
            with c4: st.markdown(ComponenteVisual.criar_card("Taxa de Quebra", f"{tx_quebra:.1%}", cor_quebra, "Não Exec. / Total Tarefas", "📉"), unsafe_allow_html=True)
            
            st.write("---")
            
            # --- LINHA 1 DE GRÁFICOS: PROPORÇÃO, GAUGE E TÉCNICOS ---
            g1, g2, g3 = st.columns([1, 1, 1.2])
            
            with g1:
                st.markdown("#### 📊 Proporção")
                df_grafico = df.groupby('Status Contrato')['TOTAL DE TAREFAS'].sum().reset_index()
                if df_grafico['TOTAL DE TAREFAS'].sum() > 0:
                    fig = px.pie(df_grafico, names='Status Contrato', values='TOTAL DE TAREFAS', hole=0.6,
                                 color='Status Contrato', color_discrete_map={'Executada': '#16A34A', 'Não Executada': '#DC2626', 'Pendente': '#94A3B8'})
                    fig.update_traces(textposition='inside', textinfo='percent')
                    fig.update_layout(showlegend=True, legend=dict(orientation="h", y=-0.1), margin=dict(t=10, b=10, l=0, r=0))
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.info("Sem dados o suficiente.")
                    
            with g2:
                st.markdown("#### 🌡️ Saúde da Operação")
                if total_os > 0:
                    fig_gauge = ComponenteVisual.grafico_velocimetro(tx_quebra, Configuracoes.SLA_QUEBRA_MAXIMA)
                    st.plotly_chart(fig_gauge, use_container_width=True, config={'displayModeBar': False})
                else:
                    st.info("Sem dados para o SLA.")
                
            with g3:
                st.markdown("#### 👤 Top 5 Ofensores (Técnicos)")
                if 'TÉCNICO' in df.columns:
                    pivot_tec = pd.pivot_table(df, values='TOTAL DE TAREFAS', index='TÉCNICO', columns='Status Contrato', aggfunc='sum', fill_value=0)
                    for col in ['Executada', 'Não Executada', 'Pendente']:
                        if col not in pivot_tec.columns: pivot_tec[col] = 0
                    
                    pivot_tec['Total'] = pivot_tec['Executada'] + pivot_tec['Não Executada'] + pivot_tec['Pendente']
                    pivot_tec['% Quebra'] = (pivot_tec['Não Executada'] / pivot_tec['Total'])
                    
                    rank_tec = pivot_tec[pivot_tec['Total'] >= 3].sort_values('% Quebra', ascending=False).head(5).reset_index()
                    
                    if not rank_tec.empty:
                        st.dataframe(
                            rank_tec[['TÉCNICO', 'Total', 'Não Executada', '% Quebra']], 
                            use_container_width=True, hide_index=True,
                            column_config={
                                "TÉCNICO": "Técnico", "Total": "Total", "Não Executada": "Quebras",
                                "% Quebra": st.column_config.ProgressColumn("Taxa", format="%.1f%%", min_value=0, max_value=1)
                            }
                        )
                    else:
                        st.success("🎉 Nenhuma quebra crítica encontrada!")
            
            st.write("---")
            
            # --- LINHA 2 DE GRÁFICOS: MOTIVOS E MONITORES ---
            g4, g5 = st.columns([1.2, 1])
            with g4:
                st.markdown("#### 🔎 Principais Motivos de Quebra")
                if col_motivo:
                    df_motivos = df[df['Status Contrato'] == 'Não Executada']
                    if not df_motivos.empty:
                        contagem_motivos = df_motivos.groupby(col_motivo)['TOTAL DE TAREFAS'].sum().reset_index()
                        contagem_motivos = contagem_motivos.sort_values('TOTAL DE TAREFAS', ascending=False).head(8)
                        
                        fig_motivos = px.bar(
                            contagem_motivos, x='TOTAL DE TAREFAS', y=col_motivo, orientation='h', 
                            color_discrete_sequence=['#DC2626'], text='TOTAL DE TAREFAS'
                        )
                        fig_motivos.update_traces(textposition='auto')
                        fig_motivos.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_title="", yaxis_title="", margin=dict(l=0, r=0, t=10, b=0))
                        st.plotly_chart(fig_motivos, use_container_width=True, config={'displayModeBar': False})
                    else:
                        st.success("Nenhuma quebra registrada para exibir motivos.")
                else:
                    st.info("💡 Coluna de 'Motivo' ou 'Substatus' não identificada na base enviada.")

            with g5:
                st.markdown("#### 👔 Performance por Monitor")
                if 'MONITOR' in df.columns:
                    pivot_mon = pd.pivot_table(df, values='TOTAL DE TAREFAS', index='MONITOR', columns='Status Contrato', aggfunc='sum', fill_value=0)
                    for col in ['Executada', 'Não Executada', 'Pendente']:
                        if col not in pivot_mon.columns: pivot_mon[col] = 0
                        
                    pivot_mon['Total'] = pivot_mon['Executada'] + pivot_mon['Não Executada'] + pivot_mon['Pendente']
                    pivot_mon['% Quebra'] = (pivot_mon['Não Executada'] / pivot_mon['Total'])
                    
                    rank_mon = pivot_mon[pivot_mon['Total'] >= 5].sort_values('% Quebra', ascending=False).reset_index()
                    
                    if not rank_mon.empty:
                        st.dataframe(
                            rank_mon[['MONITOR', 'Total', 'Não Executada', '% Quebra']], 
                            use_container_width=True, hide_index=True,
                            column_config={
                                "MONITOR": "Gestor da Equipe", "Total": "Tarefas", "Não Executada": "⚠️ Quebras",
                                "% Quebra": st.column_config.ProgressColumn("Taxa", format="%.1f%%", min_value=0, max_value=1)
                            }
                        )
                    else:
                        st.info("Volume insuficiente para gerar ranking de monitores.")

            st.write("---")
            
            # --- TABELAS DE DADOS: FILA DE TRATAMENTO E BASE COMPLETA ---
            st.markdown("### 🗃️ Exploração e Tratamento de Dados")
            tab_acao, tab_base = st.tabs(["🚨 Fila de Tratamento (Backoffice)", "🧾 Base de Dados Completa"])
            
            with tab_acao:
                st.info("🎯 **Instrução Operacional:** Utilize esta lista para ligar para os clientes, fazer retenção ou tentar o reagendamento imediato.")
                df_acao = df[df['Status Contrato'] == 'Não Executada'].copy()
                
                if not df_acao.empty:
                    colunas_chave = [c for c in ['CONTRATO', 'TÉCNICO', 'MONITOR', col_motivo, 'TOTAL DE TAREFAS'] if c is not None and c in df_acao.columns]
                    if not colunas_chave: colunas_chave = df_acao.columns
                        
                    st.dataframe(df_acao[colunas_chave], use_container_width=True, hide_index=True)
                    csv_acao = df_acao.to_csv(index=False, sep=';', encoding='utf-8-sig')
                    st.download_button("📥 Baixar Fila de Tratamento (.CSV)", data=csv_acao, file_name="fila_tratamento.csv", mime="text/csv", key="btn_acao")
                else:
                    st.success("🎉 Nenhuma O.S. na fila de tratamento no momento!")

            with tab_base:
                st.write("Visão integral de todos os dados analisados (aplicando os filtros da barra lateral).")
                st.dataframe(df, use_container_width=True, hide_index=True)
                csv_completo = df.to_csv(index=False, sep=';', encoding='utf-8-sig')
                st.download_button("📥 Baixar Base Filtrada (.CSV)", data=csv_completo, file_name="base_completa.csv", mime="text/csv", key="btn_base")
                
        else:
            st.error("⚠️ A coluna de 'Status' não foi encontrada na base de dados. Verifique o arquivo enviado.")