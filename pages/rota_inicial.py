import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. CLASSE DE CONFIGURAÇÃO GLOBAL
# ==========================================
class AppConfig:
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
# 2. CLASSE DE EXTRAÇÃO DE DADOS (DATA LAYER)
# ==========================================
class DataLoader:
    """Responsável por conectar com fontes externas e ler dados brutos."""
    
    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def fetch_google_sheets() -> pd.DataFrame:
        colunas = ["Login", "Técnico", "Monitor", "Base"]
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df = conn.read(spreadsheet=AppConfig.URL_GSHEETS, usecols=colunas)
            df = df.dropna(subset=["Login"])
            df["Login"] = df["Login"].astype(str).str.strip()
            return df
        except Exception:
            st.sidebar.error("⚠️ Falha ao sincronizar com Google Sheets.")
            return pd.DataFrame(columns=colunas)

    @staticmethod
    @st.cache_data(show_spinner=False)
    def fetch_excel(uploaded_file) -> pd.DataFrame:
        return pd.read_excel(uploaded_file, engine="openpyxl")


# ==========================================
# 3. CLASSE DE REGRAS DE NEGÓCIO (BUSINESS LOGIC)
# ==========================================
class DataProcessor:
    """Aplica tipificações, cruzamentos e cálculos matemáticos."""
    
    @staticmethod
    @st.cache_data(show_spinner=False)
    def transform_main_dataset(df_bruto: pd.DataFrame, df_ativos: pd.DataFrame) -> pd.DataFrame:
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

        # Merge (PROCV)
        if not df_ativos.empty and "Login do Técnico" in df.columns:
            df = df.merge(df_ativos, left_on="Login do Técnico", right_on="Login", how="left")
            df = df.rename(columns={"Técnico_y": "Nome Oficial (Sheets)", "Técnico_x": "Técnico (Excel)"})

        # Tipificação
        str_tipo_os = df.get("Tipo O.S 1", pd.Series(dtype=str)).astype(str)
        str_hab_trab = df.get("Habilidade de Trabalho", pd.Series(dtype=str)).astype(str)

        df["Check_ND"] = str_tipo_os.str.contains("ADESAO", case=False, na=False)
        df["Check_Migracao"] = str_tipo_os.str.strip().str.upper() == "24 - MUDANCA DE PACOTE"
        df["Check_GPON"] = str_hab_trab.str.contains(r"PON\(1/100\)", regex=True, case=False, na=False)

        # Períodos
        if "Intervalo de Tempo" in df.columns:
            df["Período"] = df["Intervalo de Tempo"].astype(str).str.strip().map(AppConfig.MAPEAMENTO_PERIODOS).fillna("Outros/Sem Período")
        else:
            df["Período"] = "Sem Período"

        return df

    @staticmethod
    def calculate_monitor_metrics(df_periodo: pd.DataFrame):
        if "Monitor" not in df_periodo.columns or df_periodo.empty:
            return pd.DataFrame(), {}

        df_resumo = df_periodo.groupby("Monitor").agg(
            WO=("Número da WO", "nunique") if "Número da WO" in df_periodo.columns else ("Login do Técnico", "count"),
            GPON=("Check_GPON", "sum"),
            OS=("Total de tarefas", "sum"),
            ND=("Check_ND", "sum"),
            Migração=("Check_Migracao", "sum"),
            Equipe=("Login do Técnico", "nunique") if "Login do Técnico" in df_periodo.columns else ("Login do Técnico", "count")
        ).reset_index()

        df_resumo["Média"] = np.where(df_resumo["Equipe"] > 0, df_resumo["OS"] / df_resumo["Equipe"], 0)

        totais = {
            "WO": df_resumo["WO"].sum(),
            "GPON": df_resumo["GPON"].sum(),
            "O.S.": int(df_resumo["OS"].sum()),
            "ND": df_resumo["ND"].sum(),
            "Migração": df_resumo["Migração"].sum(),
            "Equipe": df_resumo["Equipe"].sum(),
        }
        totais["Média"] = totais["O.S."] / totais["Equipe"] if totais["Equipe"] > 0 else 0

        return df_resumo, totais


# ==========================================
# 4. CLASSE DE COMPONENTES VISUAIS (VIEW / UI)
# ==========================================
class UIComponents:
    """Gerencia a renderização de elementos HTML e customizados do Streamlit."""
    
    @staticmethod
    def draw_file_uploader(key: str):
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
        return st.file_uploader(label="Upload", type=["xlsx"], key=key, label_visibility="collapsed")

    @staticmethod
    def draw_html_card(titulo, valor, tema="azul", subtitulo=""):
        cores = AppConfig.TEMAS_CARD.get(tema, AppConfig.TEMAS_CARD["azul"])
        sub_html = f'<p style="margin: 0; font-size: 13px; color: {cores["titulo"]}; opacity: 0.85; padding-top: 5px;">{subtitulo}</p>' if subtitulo else ""
        return f"""
        <div style="background-color: {cores['fundo']}; padding: 20px; border-radius: 10px; border-left: 8px solid {cores['borda']}; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <p style="margin: 0; font-size: 14px; color: {cores['titulo']}; text-transform: uppercase; font-weight: bold;">{titulo}</p>
            <h1 style="margin: 0; padding-top: 5px; color: {cores['texto']}; font-weight: 900; font-size: 38px;">{valor}</h1>
            {sub_html}
        </div>
        """

    @staticmethod
    def draw_html_mini_card(titulo, valor, tema="cinza"):
        cores = AppConfig.TEMAS_CARD.get(tema, AppConfig.TEMAS_CARD["cinza"])
        return f"""
        <div style="background-color: {cores['fundo']}; padding: 10px; border-radius: 6px; border-left: 4px solid {cores['borda']}; text-align: center; margin-bottom: 10px;">
            <p style="margin: 0; font-size: 12px; color: {cores['titulo']}; font-weight: bold; text-transform: uppercase;">{titulo}</p>
            <h3 style="margin: 0; color: {cores['texto']}; font-size: 20px; font-weight: 800;">{valor}</h3>
        </div>
        """

    @staticmethod
    def render_monitor_table(titulo: str, df_dados: pd.DataFrame):
        df_resumo, totais = DataProcessor.calculate_monitor_metrics(df_dados)
        if df_resumo.empty: return

        st.markdown(f"#### {titulo}")
        st.dataframe(
            df_resumo,
            column_config={
                "Monitor": st.column_config.TextColumn("Nome do Monitor", width="large"),
                "OS": st.column_config.ProgressColumn("O.S. (Tarefas)", format="%d", min_value=0, max_value=int(df_resumo["OS"].max())),
                "Média": st.column_config.NumberColumn("Média/Téc.", format="%.2f")
            }, hide_index=True, use_container_width=True
        )
        
        t1, t2, t3, t4, t5, t6, t7 = st.columns(7)
        with t1: st.markdown(UIComponents.draw_html_mini_card("WO", totais['WO'], "cinza"), unsafe_allow_html=True)
        with t2: st.markdown(UIComponents.draw_html_mini_card("O.S.", totais['O.S.'], "azul"), unsafe_allow_html=True)
        with t3: st.markdown(UIComponents.draw_html_mini_card("GPON", totais['GPON'], "escuro"), unsafe_allow_html=True)
        with t4: st.markdown(UIComponents.draw_html_mini_card("Novos Dom.", totais['ND'], "escuro"), unsafe_allow_html=True)
        with t5: st.markdown(UIComponents.draw_html_mini_card("Migração", totais['Migração'], "escuro"), unsafe_allow_html=True)
        with t6: st.markdown(UIComponents.draw_html_mini_card("Equipe", totais['Equipe'], "roxo"), unsafe_allow_html=True)
        with t7: st.markdown(UIComponents.draw_html_mini_card("Média", f"{totais['Média']:.2f}", "azul"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)


# ==========================================
# 5. CLASSE CONTROLADORA DA APLICAÇÃO (APP)
# ==========================================
class DashboardApp:
    """Orquestra o fluxo de dados, filtros e gerencia a navegação entre as abas."""
    
    def __init__(self):
        AppConfig.configurar_pagina()

    def render_sidebar_filters(self, df: pd.DataFrame) -> pd.DataFrame:
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filtros Operacionais")
        df_filtrado = df.copy()

        with st.sidebar.expander("Aplicar Filtros", expanded=True):
            if "Período" in df_filtrado.columns:
                periodos = st.multiselect("⏰ Período", sorted(df_filtrado["Período"].unique()))
                if periodos: df_filtrado = df_filtrado[df_filtrado["Período"].isin(periodos)]
                
            if "Monitor" in df_filtrado.columns:
                monitores = st.multiselect("👨‍💼 Monitor", sorted(df_filtrado["Monitor"].dropna().astype(str).unique()))
                if monitores: df_filtrado = df_filtrado[df_filtrado["Monitor"].isin(monitores)]
                
            if "Cidade" in df_filtrado.columns:
                cidades = st.multiselect("📍 Cidade", sorted(df_filtrado["Cidade"].dropna().astype(str).unique()))
                if cidades: df_filtrado = df_filtrado[df_filtrado["Cidade"].isin(cidades)]
                
        return df_filtrado

    def render_header_kpis(self, df: pd.DataFrame):
        soma_os = df["Total de tarefas"].sum()
        total_wo = df["Número da WO"].nunique() if "Número da WO" in df.columns else 0
        tecnicos = df.get("Login do Técnico", pd.Series()).nunique()
        cidades = df.get("Cidade", pd.Series()).nunique()
        monitores = df.get("Monitor", pd.Series()).nunique()

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(UIComponents.draw_html_card("Soma de Tarefas (O.S.)", f"{soma_os:,.0f}", "azul", f"{total_wo:,.0f} Contratos"), unsafe_allow_html=True)
        with c2: st.markdown(UIComponents.draw_html_card("Técnicos Operando", f"{tecnicos}", "verde"), unsafe_allow_html=True)
        with c3: st.markdown(UIComponents.draw_html_card("Cidades Atendidas", f"{cidades}", "amarelo"), unsafe_allow_html=True)
        with c4: st.markdown(UIComponents.draw_html_card("Monitores Escalonados", f"{monitores}", "roxo"), unsafe_allow_html=True)

    def render_tab_technicians(self, df_filtrado: pd.DataFrame):
        col_nome = "Nome Oficial (Sheets)" if "Nome Oficial (Sheets)" in df_filtrado.columns else "Login do Técnico"
        if col_nome not in df_filtrado.columns: return

        agg_dict = {"Técnico": "first", "Total de tarefas": "sum"}
        if "Número da WO" in df_filtrado.columns: agg_dict["Número da WO"] = pd.Series.nunique
            
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

    def render_tab_map(self, df_filtrado: pd.DataFrame):
        df_mapa = df_filtrado.dropna(subset=["Coordenada X", "Coordenada Y"]).copy()
        if not df_mapa.empty:
            df_mapa["Coordenada X"] = pd.to_numeric(df_mapa["Coordenada X"].astype(str).str.replace(',', '.'), errors="coerce")
            df_mapa["Coordenada Y"] = pd.to_numeric(df_mapa["Coordenada Y"].astype(str).str.replace(',', '.'), errors="coerce")
            df_mapa = df_mapa.dropna(subset=["Coordenada X", "Coordenada Y"])
            
            fig_mapa = px.scatter_mapbox(df_mapa, lat="Coordenada Y", lon="Coordenada X", color=df_mapa.get("Status da Atividade"), zoom=9, height=500, hover_name="Login do Técnico")
            fig_mapa.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
            st.plotly_chart(fig_mapa, use_container_width=True)

    def run(self):
        """Ponto de entrada principal do Dashboard."""
        st.subheader("📥 Entrada de Dados")
        arquivo = UIComponents.draw_file_uploader(key="upload_excel")

        if not arquivo:
            st.title("Bem-vindo ao Painel de Rota Inicial Totale 🚀")
            st.info("👆 Aguardando arquivo para iniciar o Dashboard...")
            return 

        with st.spinner("🚀 Processando base de dados e conectando à nuvem..."):
            df_bruto = DataLoader.fetch_excel(arquivo)
            df_ativos = DataLoader.fetch_google_sheets()
            df_master = DataProcessor.transform_main_dataset(df_bruto, df_ativos)

        df_filtrado = self.render_sidebar_filters(df_master)

        st.title("📈 Rota Inicial")
        self.render_header_kpis(df_filtrado)

        aba_dash, aba_tec, aba_rotas, aba_dados = st.tabs([
            "📋 Dash Monitores", "🏆 Top Técnicos", "🗺️ Mapa", "🗃️ Base de Dados"
        ])

        with aba_dash:
            st.markdown("### 📊 Desempenho Operacional - Resumo de Produção")
            UIComponents.render_monitor_table("🌎 RESUMO GERAL (Consolidado)", df_filtrado)
            
            st.divider()
            st.markdown("### 🕒 Detalhamento por Intervalo de Tempo")
            for periodo in ["Manhã", "Tarde I", "Tarde II", "Imediata"]:
                UIComponents.render_monitor_table(f"🕒 {periodo}", df_filtrado[df_filtrado["Período"] == periodo])

        with aba_tec:
            self.render_tab_technicians(df_filtrado)

        with aba_rotas:
            self.render_tab_map(df_filtrado)

        with aba_dados:
            st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
            csv = df_filtrado.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
            st.download_button("📥 Exportar Base Consolidada", data=csv, file_name="base_totale.csv", mime="text/csv")


# ==========================================
# INICIALIZAÇÃO
# ==========================================
if __name__ == "__main__":
    app = DashboardApp()
    app.run()