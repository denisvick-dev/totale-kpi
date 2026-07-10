import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. CLASSE DE CONFIGURAÇÃO GLOBAL
# ==========================================
class ConfiguracaoApp:
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
        "vermelho":{"fundo": "#FEF2F2", "texto": "#B91C1C", "borda": "#EF4444", "titulo": "#991B1B"},
    }

    @staticmethod
    def configurar_pagina():
        st.set_page_config(page_title="Painel Operacional Totale", page_icon="📊", layout="wide", initial_sidebar_state="expanded")


# ==========================================
# 2. CLASSE DE EXTRAÇÃO DE DADOS
# ==========================================
class CarregadorDados:
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
    @staticmethod
    @st.cache_data(show_spinner=False)
    def transformar_base_principal(df_bruto: pd.DataFrame, df_ativos: pd.DataFrame) -> pd.DataFrame:
        df = df_bruto.copy()

        # Padronização Global
        df.columns = df.columns.str.strip()

        if "Contrato" in df.columns:
            df = df[~df["Contrato"].astype(str).str.fullmatch(r'^\s*$|nan', case=False, na=True)]
        if "Login do Técnico" in df.columns:
            df["Login do Técnico"] = df["Login do Técnico"].astype(str).str.replace(".0", "", regex=False).str.strip()
        
        # Numéricos
        if "Total de tarefas" in df.columns:
            df["Total de tarefas"] = pd.to_numeric(df["Total de tarefas"].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
        else:
            df["Total de tarefas"] = 1 

        # Merge (PROCV) com Google Sheets
        if not df_ativos.empty and "Login do Técnico" in df.columns:
            df = df.merge(df_ativos, left_on="Login do Técnico", right_on="Login", how="left")
            df = df.rename(columns={"Técnico": "Nome Oficial (Sheets)"})

        # Preenchimento Padrão para Falhas no Merge
        if "Monitor" not in df.columns: df["Monitor"] = "SEM MONITOR"
        else: df["Monitor"] = df["Monitor"].fillna("SEM MONITOR")

        # Tipificação e Limpeza de Strings
        str_tipo_os = df.get("Tipo O.S 1", pd.Series(dtype=str)).astype(str).str.upper()
        str_hab_trab = df.get("Habilidade de Trabalho", pd.Series(dtype=str)).astype(str).str.upper()
        str_produto = df.get("Produto", pd.Series(dtype=str)).astype(str).str.upper()
        
        if "Status da Atividade" in df.columns:
            df["Status da Atividade"] = df["Status da Atividade"].astype(str).str.strip().str.upper()
        else:
            df["Status da Atividade"] = "NÃO INFORMADO"

        # Flags Booleanas (Corrigido para usar & com parênteses)
        df["Check_GPON"] = str_hab_trab.str.contains(r"PON\(1/100\)", regex=True, na=False)
        df["Check_ND"] = str_tipo_os.str.contains("ADESAO", na=False)
        df["Check_Migracao"] = (str_tipo_os.str.strip() == "24 - MUDANCA DE PACOTE") & (df["Check_GPON"] == True)
        df["Check_Streaming"] = str_hab_trab.str.strip() == "TV VAS(1/100)"
        df["Check_Ponto_Ultra"] = str_hab_trab.str.strip() == "NETLAR"
        df["Check_4K"] = str_produto.str.strip() == "4K"
        df["Check_Soundbox"] = str_produto.str.strip() == "SOUND"

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
            Equipe=("Login do Técnico", "nunique") if "Login do Técnico" in df_periodo.columns else ("Login do Técnico", "count")
        ).reset_index()

        df_resumo["Média"] = np.where(df_resumo["Equipe"] > 0, df_resumo["OS"] / df_resumo["Equipe"], 0)

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


# ==========================================
# 4. CLASSE DE COMPONENTES VISUAIS
# ==========================================
class ComponentesVisuais:
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
        return st.file_uploader(label="Upload", type=["xlsx", "csv"], key=chave, label_visibility="collapsed")

    @staticmethod
    def desenhar_cartao_html(titulo, valor, tema="azul", subtitulo=""):
        cores = ConfiguracaoApp.TEMAS_CARD.get(tema, ConfiguracaoApp.TEMAS_CARD["azul"])
        sub_html = f'<p style="margin: 0; font-size: 13px; color: {cores["titulo"]}; opacity: 0.85; padding-top: 5px; font-weight: 600;">{subtitulo}</p>' if subtitulo else ""
        return f"""
        <div style="background-color: {cores['fundo']}; padding: 20px; border-radius: 10px; border-left: 8px solid {cores['borda']}; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <p style="margin: 0; font-size: 13px; color: {cores['titulo']}; text-transform: uppercase; font-weight: bold;">{titulo}</p>
            <h1 style="margin: 0; padding-top: 5px; color: {cores['texto']}; font-weight: 900; font-size: 34px;">{valor}</h1>
            {sub_html}
        </div>
        """

    @staticmethod
    def desenhar_mini_cartao_html(titulo, valor, tema="cinza"):
        cores = ConfiguracaoApp.TEMAS_CARD.get(tema, ConfiguracaoApp.TEMAS_CARD["cinza"])
        return f"""
        <div style="background-color: {cores['fundo']}; padding: 10px; border-radius: 6px; border-left: 4px solid {cores['borda']}; text-align: center; margin-bottom: 10px;">
            <p style="margin: 0; font-size: 11px; color: {cores['titulo']}; font-weight: bold; text-transform: uppercase;">{titulo}</p>
            <h3 style="margin: 0; color: {cores['texto']}; font-size: 18px; font-weight: 800;">{valor}</h3>
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
    def __init__(self):
        ConfiguracaoApp.configurar_pagina()
        
        # Inicialização do Session State para ocultar o Uploader
        if "df_master" not in st.session_state:
            st.session_state["df_master"] = None

    def renderizar_filtros_laterais(self, df: pd.DataFrame) -> pd.DataFrame:
        st.sidebar.markdown("---")
        st.sidebar.header("🔍 Filtros Operacionais")
        df_filtrado = df.copy()

        with st.sidebar.expander("📍 Estrutura e Localidade", expanded=True):
            if "Período" in df_filtrado.columns:
                periodos = st.selectbox("⏰ Período", ["Todos"] + sorted(df_filtrado["Período"].unique()))
                if periodos != "Todos": df_filtrado = df_filtrado[df_filtrado["Período"] == periodos]
                
            if "Monitor" in df_filtrado.columns:
                monitores = st.multiselect("👨‍💼 Monitor", sorted(df_filtrado["Monitor"].dropna().astype(str).unique()))
                if monitores: df_filtrado = df_filtrado[df_filtrado["Monitor"].isin(monitores)]
                
            if "Cidade" in df_filtrado.columns:
                cidades = st.multiselect("📍 Cidade", sorted(df_filtrado["Cidade"].dropna().astype(str).unique()))
                if cidades: df_filtrado = df_filtrado[df_filtrado["Cidade"].isin(cidades)]
        
        with st.sidebar.expander("🛠️ Filtros Especiais", expanded=False):
            if st.checkbox("🟢 Apenas Adesão (ND)"): df_filtrado = df_filtrado[df_filtrado["Check_ND"] == True]
            if st.checkbox("🔄 Apenas Migração"): df_filtrado = df_filtrado[df_filtrado["Check_Migracao"] == True]
            if st.checkbox("📡 Requer GPON"): df_filtrado = df_filtrado[df_filtrado["Check_GPON"] == True]
                
        return df_filtrado

    def renderizar_kpis_cabecalho(self, df: pd.DataFrame):
        soma_os = df["Total de tarefas"].sum()
        tecnicos = df.get("Login do Técnico", pd.Series()).nunique()
        monitores = df.get("Monitor", pd.Series()).nunique()
        
        status_concluidos = ["CONCLUÍDO", "EXECUTADA", "BAIXADA", "REALIZADA"]
        if "Status da Atividade" in df.columns:
            os_concluidas = df[df["Status da Atividade"].isin(status_concluidos)]["Total de tarefas"].sum()
            tx_conclusao = (os_concluidas / soma_os) if soma_os > 0 else 0
            texto_status = f"{tx_conclusao:.1%} Concluídas"
            tema_status = "verde" if tx_conclusao > 0.5 else ("laranja" if tx_conclusao > 0.2 else "vermelho")
        else:
            os_concluidas = 0
            texto_status = "Status Não Informado"
            tema_status = "cinza"

        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(ComponentesVisuais.desenhar_cartao_html("Volume O.S.", f"{soma_os:,.0f}", "azul"), unsafe_allow_html=True)
        with c2: st.markdown(ComponentesVisuais.desenhar_cartao_html("Técnicos Operando", f"{tecnicos}", "escuro", f"Média: {soma_os/tecnicos:.1f} OS/Téc" if tecnicos > 0 else ""), unsafe_allow_html=True)
        with c3: st.markdown(ComponentesVisuais.desenhar_cartao_html("Monitores (Gestão)", f"{monitores}", "roxo"), unsafe_allow_html=True)
        with c4: st.markdown(ComponentesVisuais.desenhar_cartao_html("Andamento do Dia", f"{os_concluidas:,.0f} OS", tema_status, texto_status), unsafe_allow_html=True)

    def renderizar_graficos_executivos(self, df: pd.DataFrame):
        st.markdown("### 📈 Visão Executiva")
        g1, g2, g3 = st.columns([1, 1, 1.2])

        with g1:
            st.markdown("##### 🚦 Status da Frota")
            if "Status da Atividade" in df.columns:
                df_status = df.groupby("Status da Atividade")["Total de tarefas"].sum().reset_index()
                fig_stat = px.pie(df_status, names="Status da Atividade", values="Total de tarefas", hole=0.5,
                                  color_discrete_sequence=px.colors.qualitative.Prism)
                fig_stat.update_traces(textposition='inside', textinfo='percent')
                fig_stat.update_layout(showlegend=False, margin=dict(t=10, b=10, l=0, r=0), height=250)
                st.plotly_chart(fig_stat, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Sem dados de Status.")

        with g2:
            st.markdown("##### ⏰ Pico de Agendamento")
            if "Período" in df.columns:
                df_per = df.groupby("Período")["Total de tarefas"].sum().reset_index()
                fig_per = px.bar(df_per, x="Período", y="Total de tarefas", text_auto=True, color="Período",
                                 color_discrete_sequence=["#0EA5E9", "#F59E0B", "#F97316", "#8B5CF6"])
                fig_per.update_layout(showlegend=False, margin=dict(t=10, b=10, l=0, r=0), height=250, xaxis_title="", yaxis_title="")
                st.plotly_chart(fig_per, use_container_width=True, config={'displayModeBar': False})

        with g3:
            st.markdown("##### 💎 Mix de Serviços Premium")
            dados_premium = {
                "Tecnologia GPON": df["Check_GPON"].sum(),
                "Instalação 4K": df["Check_4K"].sum(),
                "Soundbox": df["Check_Soundbox"].sum(),
                "Ponto Ultra": df["Check_Ponto_Ultra"].sum(),
            }
            df_prem = pd.DataFrame(list(dados_premium.items()), columns=["Serviço", "Qtd"])
            df_prem = df_prem[df_prem["Qtd"] > 0]
            
            if not df_prem.empty:
                fig_prem = px.bar(df_prem, x="Qtd", y="Serviço", orientation='h', text_auto=True, color_discrete_sequence=["#10B981"])
                fig_prem.update_layout(showlegend=False, margin=dict(t=10, b=10, l=0, r=0), height=250, xaxis_title="", yaxis_title="")
                st.plotly_chart(fig_prem, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Nenhum serviço premium escalado para hoje.")

        st.divider()

    def executar(self):
        # 1. Verifica se não há dados na memória (Exibe o Uploader)
        if st.session_state["df_master"] is None:
            st.title("Bem-vindo ao Painel Operacional Totale 🚀")
            st.subheader("📥 Entrada de Dados")
            
            arquivo = ComponentesVisuais.desenhar_upload_arquivo(chave="upload_excel")

            if arquivo is not None:
                with st.spinner("🚀 Processando base de dados e conectando à nuvem..."):
                    df_bruto = CarregadorDados.ler_excel(arquivo)
                    df_ativos = CarregadorDados.buscar_google_sheets()
                    df_master = ProcessadorDados.transformar_base_principal(df_bruto, df_ativos)
                    
                    # Salva o resultado processado na memória e recarrega a página (para o uploader sumir)
                    st.session_state["df_master"] = df_master
                    st.rerun()
            else:
                st.info("👆 Faça o upload da planilha (Excel) para iniciar o Dashboard...")
                return

        # 2. Se já houver dados na memória (Oculta Uploader e Mostra Dashboard)
        else:
            df_master = st.session_state["df_master"]
            
            # Botão de Reset
            col_msg, col_btn = st.columns([4, 1])
            with col_msg:
                st.success("✅ Base processada e cruzada com sucesso!")
            with col_btn:
                if st.button("🔄 Enviar outro arquivo", use_container_width=True):
                    st.session_state["df_master"] = None
                    st.rerun()

            # Renderiza a Sidebar
            df_filtrado = self.renderizar_filtros_laterais(df_master)

            # Renderiza o Dashboard
            st.title("📈 Dashboard Totale: Visão Geral")
            
            self.renderizar_kpis_cabecalho(df_filtrado)
            self.renderizar_graficos_executivos(df_filtrado)

            aba_dash, aba_tec, aba_rotas, aba_dados = st.tabs([
                "📋 Dash Monitores", "🏆 Top Técnicos", "🗺️ Mapa Geográfico", "🗃️ Base de Dados"
            ])

            with aba_dash:
                ComponentesVisuais.renderizar_tabela_monitor("🌎 RESUMO GERAL (Consolidado)", df_filtrado)
                st.markdown("<br>", unsafe_allow_html=True)
                
                for periodo in ["Manhã", "Tarde I", "Tarde II", "Imediata"]:
                    ComponentesVisuais.renderizar_tabela_monitor(f"🕒 {periodo}", df_filtrado[df_filtrado["Período"] == periodo])

            with aba_tec:
                col_nome = "Nome Oficial (Sheets)" if "Nome Oficial (Sheets)" in df_filtrado.columns else "Login do Técnico"
                prod_df = df_filtrado.groupby(col_nome).agg({"Total de tarefas": "sum"}).reset_index()
                prod_df = prod_df.sort_values("Total de tarefas", ascending=False).head(15)
                
                st.markdown("#### 🚀 Top 15 Técnicos com Maior Carga")
                fig_tec = px.bar(prod_df, x="Total de tarefas", y=col_nome, orientation='h', color="Total de tarefas", color_continuous_scale="Blues", text_auto=True)
                fig_tec.update_layout(yaxis={'categoryorder':'total ascending'}, height=500)
                st.plotly_chart(fig_tec, use_container_width=True)

            with aba_rotas:
                df_mapa = df_filtrado.dropna(subset=["Coordenada X", "Coordenada Y"]).copy()
                if not df_mapa.empty:
                    df_mapa["Coordenada X"] = pd.to_numeric(df_mapa["Coordenada X"].astype(str).str.replace(',', '.'), errors="coerce")
                    df_mapa["Coordenada Y"] = pd.to_numeric(df_mapa["Coordenada Y"].astype(str).str.replace(',', '.'), errors="coerce")
                    
                    fig_mapa = px.scatter_mapbox(df_mapa, lat="Coordenada Y", lon="Coordenada X", color="Status da Atividade", zoom=9, height=550, hover_name="Login do Técnico")
                    fig_mapa.update_layout(mapbox_style="open-street-map", margin={"r":0,"t":0,"l":0,"b":0})
                    st.plotly_chart(fig_mapa, use_container_width=True)

            with aba_dados:
                st.dataframe(df_filtrado, use_container_width=True, hide_index=True)
                csv = df_filtrado.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
                st.download_button("📥 Exportar Base Consolidada", data=csv, file_name="base_totale_processada.csv", mime="text/csv")


if __name__ == "__main__":
    app = AplicativoDashboard()
    app.executar()