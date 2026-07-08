import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. CLASSE DE CONFIGURAÇÃO GLOBAL
# ==========================================
class ConfiguracaoApp:
    """Armazena constantes, URLs, mapeamentos e paletas de cores do sistema."""
    URL_GSHEETS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit?usp=drive_link"
    
    MAPEAMENTO_PERIODOS = {
        "08:00 - 10:00": "Manhã", "08:00 - 11:00": "Manhã", "08:00 - 12:00": "Manhã",
        "10:00 - 12:00": "Manhã", "11:00 - 14:00": "Manhã", "12:00 - 14:00": "Tarde I",
        "12:00 - 15:00": "Tarde I", "12:00 - 18:00": "Tarde II", "14:00 - 16:00": "Tarde II",
        "14:00 - 17:00": "Tarde II", "15:00 - 18:00": "Tarde II", "16:00 - 18:00": "Tarde II",
        "17:00 - 20:00": "Tarde II", "Imediata": "Imediata"
    }

    TEMAS_CARD = {
        "amarelo": {"fundo": "#FEF9C3", "texto": "#854D0E", "borda": "#EAB308", "titulo": "#A16207"},
        "azul":    {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
        "verde":   {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
        "roxo":    {"fundo": "#FAF5FF", "texto": "#7E22CE", "borda": "#A855F7", "titulo": "#6B21A8"},
        "cinza":   {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
        "escuro":  {"fundo": "#1E293B", "texto": "#FFFFFF", "borda": "#475569", "titulo": "#E2E8F0"},
    }

    @staticmethod
    def configurar_pagina():
        st.set_page_config(page_title="Painel Operacional Totale", page_icon="📊", layout="wide", initial_sidebar_state="expanded")


# ==========================================
# 2. CLASSE DE EXTRAÇÃO DE DADOS
# ==========================================
class CarregadorDados:
    """Responsável por conectar com fontes externas e ler dados brutos."""
    
    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_google_sheets() -> pd.DataFrame:
        colunas = ["Login", "Técnico", "Monitor", "Base"]
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(spreadsheet=ConfiguracaoApp.URL_GSHEETS, usecols=colunas)
            df = df.dropna(subset=["Login"])
            df["Login"] = df["Login"].astype(str).str.strip()
            return df
        except Exception:
            st.sidebar.error("⚠️ Falha ao sincronizar com Google Sheets.")
            return pd.DataFrame(columns=colunas)

    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_excel(arquivo_enviado) -> pd.DataFrame:
        return pd.read_excel(arquivo_enviado, engine="openpyxl")


# ==========================================
# 3. CLASSE DE REGRAS DE NEGÓCIO
# ==========================================
class ProcessadorDados:
    """Aplica tipificações, cruzamentos e cálculos matemáticos."""
    
    @staticmethod
    @st.cache_data(show_spinner=False)
    def transformar_base_principal(df_bruto: pd.DataFrame, df_ativos: pd.DataFrame) -> pd.DataFrame:
        df = df_bruto.copy()

        # Limpeza
        if "Contrato" in df.columns:
            df = df[~df["Contrato"].astype(str).str.fullmatch(r'^\s*$|nan', case=False, na=True)]
        if "Login do Técnico" in df.columns:
            df["Login do Técnico"] = df["Login do Técnico"].astype(str).str.strip()
        
        # Numéricos
        if "Total de tarefas" in df.columns:
            df["Total de tarefas"] = pd.to_numeric(df["Total de tarefas"].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
        else:
            df["Total de tarefas"] = 1 

        # Merge (PROCV) com Google Sheets
        if not df_ativos.empty and "Login do Técnico" in df.columns:
            df = df.merge(df_ativos, left_on="Login do Técnico", right_on="Login", how="left")
            df = df.rename(columns={"Técnico_y": "Nome Oficial (Sheets)", "Técnico_x": "Técnico (Excel)"})

        # Tipificação (Criando as flags booleanas)
        str_tipo_os = df.get("Tipo O.S 1", pd.Series(dtype=str)).astype(str)
        str_hab_trab = df.get("Habilidade de Trabalho", pd.Series(dtype=str)).astype(str)
        str_produto = df.get("Produto", pd.Series(dtype=str)).astype(str)

        df["Check_ND"] = str_tipo_os.str.contains("ADESAO", case=False, na=False)
        df["Check_Migracao"] = str_tipo_os.str.strip().str.upper() == "24 - MUDANCA DE PACOTE"
        df["Check_GPON"] = str_hab_trab.str.contains(r"PON\(1/100\)", regex=True, case=False, na=False)
        df["Check_Streaming"] = str_hab_trab.str.contains("TV VAS(1/100)", case=False, na=False)
        df["Check_Ponto_Ultra"] = str_hab_trab.str.contains("NETLAR", case=False, na=False)
        df["Check_4K"] = str_produto.str.contains("4K", case=False, na=False)
        df["Check_Soundbox"] = str_produto.str.contains("SOUND", case=False, na=False)
        df["Check_Mesh"] = str_hab_trab.str.contains("Mesh", case=False, na=False)

        # Mapeamento de Períodos
        if "Intervalo de Tempo" in df.columns:
            df["Período"] = df["Intervalo de Tempo"].astype(str).str.strip().map(ConfiguracaoApp.MAPEAMENTO_PERIODOS).fillna("Outros/Sem Período")
        else:
            df["Período"] = "Sem Período"

        return df

    @staticmethod
    def calcular_metricas_monitor(df_periodo: pd.DataFrame):
        if "Monitor" not in df_periodo.columns or df_periodo.empty:
            return pd.DataFrame(), {}

        # Agrupando por monitor e somando os produtos/serviços
        df_resumo = df_periodo.groupby("Monitor").agg(
            WO=("Número da WO", "nunique") if "Número da WO" in df_periodo.columns else ("Login do Técnico", "count"),
            OS=("Total de tarefas", "sum"),
            ND=("Check_ND", "sum"),
            Migração=("Check_Migracao", "sum"),
            GPON=("Check_GPON", "sum"),
            Streaming=("Check_Streaming", "sum"),
            Qtd_4K=("Check_4K", "sum"),
            Soundbox=("Check_Soundbox", "sum"),
            PontoUltra=("Check_Ponto_Ultra", "sum"),
            Mesh=("Check_Mesh", "sum"),
            Equipe=("Login do Técnico", "nunique") if "Login do Técnico" in df_periodo.columns else ("Login do Técnico", "count")
        ).reset_index()

        df_resumo["Média"] = np.where(df_resumo["Equipe"] > 0, df_resumo["OS"] / df_resumo["Equipe"], 0)

        # Totais gerais para os cards
        totais = {
            "WO": df_resumo["WO"].sum(),
            "O.S.": int(df_resumo["OS"].sum()),
            "GPON": df_resumo["GPON"].sum(),
            "ND": df_resumo["ND"].sum(),
            "Migração": df_resumo["Migração"].sum(),
            "Equipe": df_resumo["Equipe"].sum(),
        }
        totais["Média"] = totais["O.S."] / totais["Equipe"] if totais["Equipe"] > 0 else 0

        return df_resumo, totais
    
    @staticmethod
    def gerar_tabela_contratos(df_filtrado: pd.DataFrame) -> pd.DataFrame:
        """Cria um DataFrame apartado apenas com as colunas solicitadas de forma segura."""
        df_resumo = pd.DataFrame()

        # 1. Contrato
        df_resumo["Contrato"] = df_filtrado.get("Contrato", pd.Series(dtype=str))
        
        # 2. Login do Técnico
        df_resumo["Login do Técnico"] = df_filtrado.get("Login do Técnico", pd.Series(dtype=str))
        
        # 3. Técnico (Prioriza o nome do Sheets, se não tiver usa o do Excel)
        if "Nome Oficial (Sheets)" in df_filtrado.columns:
            df_resumo["Técnico"] = df_filtrado["Nome Oficial (Sheets)"]
        else:
            df_resumo["Técnico"] = df_filtrado.get("Técnico (Excel)", df_filtrado.get("Técnico", pd.Series(dtype=str)))
            
        # 4. CEP / Código Postal (Tenta variações de nome de coluna)
        if "CEP/Código Postal" in df_filtrado.columns:
            df_resumo["CEP/Código Postal"] = df_filtrado["CEP/Código Postal"]
        else:
            df_resumo["CEP/Código Postal"] = df_filtrado.get("CEP/Código Postal", pd.Series(dtype=str))
            
        # 5. Área de Trabalho
        df_resumo["Área de Trabalho"] = df_filtrado.get("Área de Trabalho", pd.Series(dtype=str))
        
        # 6. Período (Criado no transformar_base_principal)
        df_resumo["Período"] = df_filtrado.get("Período", pd.Series(dtype=str))

        # Remove linhas onde o Contrato está vazio
        df_resumo = df_resumo.dropna(subset=["Contrato"]).drop_duplicates()

        return df_resumo


# ==========================================
# 4. CLASSE DE COMPONENTES VISUAIS
# ==========================================
class ComponentesVisuais:
    """Gerencia a renderização de elementos HTML e customizados do Streamlit."""
    
    @staticmethod
    def desenhar_upload_arquivo(chave: str):
        st.markdown("""
            <style>
                [data-testid="stFileUploadDropzone"] {
                    border: 2px dashed #0EA5E9 !important; border-radius: 8px !important;
                    padding: 15px !important; background-color: #F0F9FF !important; transition: all 0.3s ease;
                }
                [data-testid="stFileUploadDropzone"]:hover { background-color: #E0F2FE !important; border-color: #0284C7 !important; }
                [data-testid="stFileUploadDropzone"] small { display: none; }
            </style>
        """, unsafe_allow_html=True)
        return st.file_uploader(label="Upload", type=["xlsx"], key=chave, label_visibility="collapsed")

    @staticmethod
    def desenhar_cartao_html(titulo, valor, tema="azul", subtitulo=""):
        cores = ConfiguracaoApp.TEMAS_CARD.get(tema, ConfiguracaoApp.TEMAS_CARD["azul"])
        sub_html = f'<p style="margin: 0; font-size: 13px; color: {cores["titulo"]}; opacity: 0.85; padding-top: 5px;">{subtitulo}</p>' if subtitulo else ""
        return f"""
        <div style="background-color: {cores['fundo']}; padding: 20px; border-radius: 10px; border-left: 8px solid {cores['borda']}; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <p style="margin: 0; font-size: 14px; color: {cores['titulo']}; text-transform: uppercase; font-weight: bold;">{titulo}</p>
            <h1 style="margin: 0; padding-top: 5px; color: {cores['texto']}; font-weight: 900; font-size: 38px;">{valor}</h1>
            {sub_html}
        </div>
        """

    @staticmethod
    def desenhar_mini_cartao_html(titulo, valor, tema="cinza"):
        cores = ConfiguracaoApp.TEMAS_CARD.get(tema, ConfiguracaoApp.TEMAS_CARD["cinza"])
        return f"""
        <div style="background-color: {cores['fundo']}; padding: 10px; border-radius: 6px; border-left: 4px solid {cores['borda']}; text-align: center; margin-bottom: 10px;">
            <p style="margin: 0; font-size: 12px; color: {cores['titulo']}; font-weight: bold; text-transform: uppercase;">{titulo}</p>
            <h3 style="margin: 0; color: {cores['texto']}; font-size: 20px; font-weight: 800;">{valor}</h3>
        </div>
        """

    @staticmethod
    def renderizar_tabela_monitor(titulo: str, df_dados: pd.DataFrame):
        df_resumo, totais = ProcessadorDados.calcular_metricas_monitor(df_dados)
        if df_resumo.empty: return

        st.markdown(f"#### {titulo}")
        
        # Configuração das colunas visuais da Tabela
        st.dataframe(
            df_resumo,
            column_config={
                "Monitor": st.column_config.TextColumn("Nome do Monitor", width="medium"),
                "OS": st.column_config.ProgressColumn("O.S. (Total)", format="%d", min_value=0, max_value=int(df_resumo["OS"].max())),
                "Qtd_4K": st.column_config.NumberColumn("4K"),
                "Média": st.column_config.NumberColumn("Média/Téc.", format="%.2f")
            }, hide_index=True, use_container_width=True
        )
        
        # Mini cards principais de resumo abaixo da tabela
        t1, t2, t3, t4, t5, t6, t7 = st.columns(7)
        with t1: st.markdown(ComponentesVisuais.desenhar_mini_cartao_html("WO", totais['WO'], "cinza"), unsafe_allow_html=True)
        with t2: st.markdown(ComponentesVisuais.desenhar_mini_cartao_html("O.S.", totais['O.S.'], "azul"), unsafe_allow_html=True)
        with t3: st.markdown(ComponentesVisuais.desenhar_mini_cartao_html("GPON", totais['GPON'], "escuro"), unsafe_allow_html=True)
        with t4: st.markdown(ComponentesVisuais.desenhar_mini_cartao_html("Novos Dom.", totais['ND'], "escuro"), unsafe_allow_html=True)
        with t5: st.markdown(ComponentesVisuais.desenhar_mini_cartao_html("Migração", totais['Migração'], "escuro"), unsafe_allow_html=True)
        with t6: st.markdown(ComponentesVisuais.desenhar_mini_cartao_html("Equipe", totais['Equipe'], "roxo"), unsafe_allow_html=True)
        with t7: st.markdown(ComponentesVisuais.desenhar_mini_cartao_html("Média", f"{totais['Média']:.2f}", "azul"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)


# ==========================================
# 5. CLASSE CONTROLADORA DA APLICAÇÃO
# ==========================================
class AplicativoDashboard:
    """Orquestra o fluxo de dados, filtros e gerencia a navegação entre as abas."""
    
    def __init__(self):
        ConfiguracaoApp.configurar_pagina()

    def renderizar_filtros_laterais(self, df: pd.DataFrame) -> pd.DataFrame:
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filtros Operacionais")
        df_filtrado = df.copy()

        # 1. Filtros de Estrutura (Período, Monitor, Cidade)
        with st.sidebar.expander("📍 Estrutura e Localidade", expanded=True):
            if "Período" in df_filtrado.columns:
                periodos = st.multiselect("⏰ Período", sorted(df_filtrado["Período"].unique()))
                if periodos: df_filtrado = df_filtrado[df_filtrado["Período"].isin(periodos)]
                
            if "Monitor" in df_filtrado.columns:
                monitores = st.multiselect("👨‍💼 Monitor", sorted(df_filtrado["Monitor"].dropna().astype(str).unique()))
                if monitores: df_filtrado = df_filtrado[df_filtrado["Monitor"].isin(monitores)]
                
            if "Cidade" in df_filtrado.columns:
                cidades = st.multiselect("📍 Cidade", sorted(df_filtrado["Cidade"].dropna().astype(str).unique()))
                if cidades: df_filtrado = df_filtrado[df_filtrado["Cidade"].isin(cidades)]
        
        # 2. Novos Filtros de Produto / Serviço
        with st.sidebar.expander("🛠️ Filtros de Produto / Serviço", expanded=False):
            f_nd = st.checkbox("🟢 Apenas Adesão (ND)")
            f_migracao = st.checkbox("🔄 Apenas Migração")
            f_gpon = st.checkbox("📡 Requer GPON")
            f_streaming = st.checkbox("📺 Requer Streaming")
            f_ponto = st.checkbox("📶 Requer Ponto Ultra")
            f_4k = st.checkbox("🔌 Possui Equipamento 4K")
            f_soundbox = st.checkbox("🔊 Possui Soundbox")
            f_mesh = st.checkbox("📡 Requer Mesh")

            # Aplicando os filtros booleanos
            if f_nd: df_filtrado = df_filtrado[df_filtrado["Check_ND"] == True]
            if f_migracao: df_filtrado = df_filtrado[df_filtrado["Check_Migracao"] == True]
            if f_gpon: df_filtrado = df_filtrado[df_filtrado["Check_GPON"] == True]
            if f_streaming: df_filtrado = df_filtrado[df_filtrado["Check_Streaming"] == True]
            if f_ponto: df_filtrado = df_filtrado[df_filtrado["Check_Ponto_Ultra"] == True]
            if f_4k: df_filtrado = df_filtrado[df_filtrado["Check_4K"] == True]
            if f_soundbox: df_filtrado = df_filtrado[df_filtrado["Check_Soundbox"] == True]
            if f_mesh: df_filtrado = df_filtrado[df_filtrado["Check_Mesh"] == True]
                
        return df_filtrado

    def renderizar_kpis_cabecalho(self, df: pd.DataFrame):
        soma_os = df["Total de tarefas"].sum()
        total_wo = df["Número da WO"].nunique() if "Número da WO" in df.columns else 0
        tecnicos = df.get("Login do Técnico", pd.Series()).nunique()
        cidades = df.get("Cidade", pd.Series()).nunique()
        monitores = df.get("Monitor", pd.Series()).nunique()

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(ComponentesVisuais.desenhar_cartao_html("Soma de Tarefas (O.S.)", f"{soma_os:,.0f}", "azul", f"{total_wo:,.0f} Contratos"), unsafe_allow_html=True)
        with c2: st.markdown(ComponentesVisuais.desenhar_cartao_html("Técnicos Operando", f"{tecnicos}", "verde"), unsafe_allow_html=True)
        with c3: st.markdown(ComponentesVisuais.desenhar_cartao_html("Cidades Atendidas", f"{cidades}", "amarelo"), unsafe_allow_html=True)
        with c4: st.markdown(ComponentesVisuais.desenhar_cartao_html("Monitores Escalonados", f"{monitores}", "roxo"), unsafe_allow_html=True)

    def renderizar_aba_tecnicos(self, df_filtrado: pd.DataFrame):
        col_nome = "Nome Oficial (Sheets)" if "Nome Oficial (Sheets)" in df_filtrado.columns else "Login do Técnico"
        if col_nome not in df_filtrado.columns: return

        agg_dict = {"Técnico": "first", "Total de tarefas": "sum"}
        if "Número da WO" in df_filtrado.columns: agg_dict["Número da WO"] = "nunique"
            
        prod_df = df_filtrado.groupby(col_nome).agg(agg_dict).reset_index()
        renomes = {col_nome: "Nome do Técnico", "Total de tarefas": "Volume (O.S.)", "Número da WO": "Qtde WO"}
        prod_df = prod_df.rename(columns=renomes).sort_values("Volume (O.S.)", ascending=False)

        ct, cg = st.columns([2, 2]) 
        with ct: 
            st.markdown("#### 📋 Detalhamento")
            st.dataframe(prod_df, use_container_width=True, hide_index=True)
        with cg: 
            st.markdown("#### 📊 Top 10 Técnicos")
            top_10 = prod_df.head(10).sort_values("Volume (O.S.)", ascending=True)
            fig_tec = px.bar(
                top_10, x="Volume (O.S.)", y="Nome do Técnico", orientation='h', 
                color="Volume (O.S.)", color_continuous_scale="Oranges", text_auto=True 
            )
            fig_tec.update_layout(xaxis_title="", yaxis_title="")
            st.plotly_chart(fig_tec, use_container_width=True)

    def renderizar_aba_mapa(self, df_filtrado: pd.DataFrame):
        df_mapa = df_filtrado.dropna(subset=["Coordenada X", "Coordenada Y"]).copy()
        if not df_mapa.empty:
            df_mapa["Coordenada X"] = pd.to_numeric(df_mapa["Coordenada X"].astype(str).str.replace(',', '.'), errors="coerce")
            df_mapa["Coordenada Y"] = pd.to_numeric(df_mapa["Coordenada Y"].astype(str).str.replace(',', '.'), errors="coerce")
            df_mapa = df_mapa.dropna(subset=["Coordenada X", "Coordenada Y"])
            
            fig_mapa = px.scatter_mapbox(df_mapa, lat="Coordenada Y", lon="Coordenada X", color=df_mapa.get("Status da Atividade"), zoom=9, height=500, hover_name="Login do Técnico")
            fig_mapa.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
            st.plotly_chart(fig_mapa, use_container_width=True)

    def executar(self):
        """Ponto de entrada principal do Dashboard."""
        st.subheader("📥 Entrada de Dados")
        arquivo = ComponentesVisuais.desenhar_upload_arquivo(chave="upload_excel")

        if not arquivo:
            st.title("Bem-vindo ao Painel de Rota Inicial Totale 🚀")
            st.info("👆 Aguardando arquivo para iniciar o Dashboard...")
            return 

        with st.spinner("🚀 Processando base de dados e conectando à nuvem..."):
            df_bruto = CarregadorDados.ler_excel(arquivo)
            df_ativos = CarregadorDados.buscar_google_sheets()
            df_master = ProcessadorDados.transformar_base_principal(df_bruto, df_ativos)

        # Aplicando filtros
        df_filtrado = self.renderizar_filtros_laterais(df_master)

        st.title("📈 Rota Inicial")
        self.renderizar_kpis_cabecalho(df_filtrado)

        # --- ADICIONAMOS A NOVA ABA AQUI ---
        aba_dash, aba_tec, aba_rotas, aba_contratos, aba_dados = st.tabs([
            "📋 Dash Monitores", "🏆 Top Técnicos", "🗺️ Mapa", "📄 Lista de Contratos", "🗃️ Base Completa"
        ])

        with aba_dash:
            st.markdown("### 📊 Desempenho Operacional - Resumo de Produção")
            ComponentesVisuais.renderizar_tabela_monitor("🌎 RESUMO GERAL (Consolidado)", df_filtrado)
            
            st.divider()
            st.markdown("### 🕒 Detalhamento por Intervalo de Tempo")
            for periodo in ["Manhã", "Tarde I", "Tarde II", "Imediata"]:
                ComponentesVisuais.renderizar_tabela_monitor(f"🕒 {periodo}", df_filtrado[df_filtrado["Período"] == periodo])

        with aba_tec:
            self.renderizar_aba_tecnicos(df_filtrado)

        with aba_rotas:
            self.renderizar_aba_mapa(df_filtrado)

        # --- CONTEÚDO DA NOVA ABA DE CONTRATOS ---
        with aba_contratos:
            st.markdown("### 📄 Relação de Contratos e Técnicos")
            
            # Gera o DataFrame apartado usando a regra de negócios
            df_contratos = ProcessadorDados.gerar_tabela_contratos(df_filtrado)
            
            # Exibe na tela
            st.dataframe(df_contratos, use_container_width=True, hide_index=True)
            
            # Botão de download
            csv_contratos = df_contratos.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
            st.download_button(
                label="📥 Exportar Lista de Contratos (CSV)", 
                data=csv_contratos, 
                file_name="resumo_contratos.csv", 
                mime="text/csv"
            )

        with aba_dados:
            st.markdown("### 🗃️ Base de Dados Bruta Tratada")
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
            csv_completo = df_filtrado.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
            st.download_button(
                label="📥 Exportar Base Completa", 
                data=csv_completo, 
                file_name="base_totale_completa.csv", 
                mime="text/csv"
            )


# ==========================================
# INICIALIZAÇÃO
# ==========================================
if __name__ == "__main__":
    app = AplicativoDashboard()
    app.executar()