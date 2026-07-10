import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from typing import Optional, Tuple, Dict, Any, List
from io import BytesIO

# ====================================================
# CONFIGURAÇÕES GLOBAIS
# ====================================================
st.set_page_config(page_title="Gestão de Volumetria", page_icon="📊", layout="wide")

class Configuracoes:
    URL_ATIVOS: str = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    TEMAS_CARD: Dict[str, Dict[str, str]] = {
        "azul": {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
        "verde": {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
        "laranja": {"fundo": "#FFF7ED", "texto": "#C2410C", "borda": "#F97316", "titulo": "#9A3412"},
        "vermelho": {"fundo": "#FEF2F2", "texto": "#B91C1C", "borda": "#EF4444", "titulo": "#991B1B"},
        "cinza": {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
    }
    # Versão da lógica de preparação. Mude este número se alterar a função preparar_base.
    PREPARACAO_BASE_VERSAO = 2

# ====================================================
# UTILITÁRIOS E COMPONENTES
# ====================================================
class Utilitarios:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras_chave: List[str]) -> Optional[str]:
        if df is None or df.empty: return None
        cols_upper = {c.upper(): c for c in df.columns}
        for p in palavras_chave:
            if p.upper() in cols_upper: return cols_upper[p.upper()]
        return None

    @staticmethod
    def classificar_os_series(status_series: pd.Series) -> pd.Series:
        s = status_series.fillna("").astype(str).str.strip().str.upper()
        executada = s == "EXECUTADA"
        nao_exec = s.isin(["NÃO EXECUTADA", "NAO EXECUTADA"])
        return pd.Series(np.select([executada, nao_exec], ["Executada", "Não Executada"], default="Pendente"), index=status_series.index)

    @staticmethod
    def to_excel(df: pd.DataFrame) -> bytes:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Relatorio')
        return output.getvalue()

class ComponenteVisual:
    @staticmethod
    def criar_card(titulo: str, valor: str, tema: str = "azul", subtitulo: str = "") -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        return f"""
        <div style="background-color:{cores['fundo']};padding:16px;border-radius:10px;border-left:6px solid {cores['borda']};box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);margin-bottom:12px;min-height:110px;display:flex;flex-direction:column;justify-content:center;">
            <p style="margin:0;font-size:11px;color:{cores['titulo']};font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">{titulo}</p>
            <h2 style="margin:4px 0;color:{cores['texto']};font-weight:900;font-size:26px;line-height:1.1;">{valor}</h2>
            <p style="margin:0;font-size:11px;color:#64748B;font-weight:500;">{subtitulo}</p>
        </div>"""

# ====================================================
# CAMADA DE DADOS E PROCESSAMENTO
# ====================================================
class DadosManager:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
        try:
            name, bio = filename.lower(), BytesIO(file_bytes)
            engine = "openpyxl" if name.endswith((".xlsx", ".xls")) else "python"
            read_func = pd.read_excel if engine == "openpyxl" else pd.read_csv
            return read_func(bio, engine=engine, sep=None if engine == 'python' else None)
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_gsheets() -> pd.DataFrame:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df_gs = conn.read(spreadsheet=Configuracoes.URL_ATIVOS, usecols=list(range(3)))
            if df_gs is None or df_gs.empty: return pd.DataFrame()
            df_gs.columns = df_gs.columns.astype(str).str.strip().str.upper()
            rename_map = {
                Utilitarios.buscar_coluna(df_gs, ["LOGIN", "ID", "MATRÍCULA"]): "LOGIN",
                Utilitarios.buscar_coluna(df_gs, ["TÉCNICO", "NOME"]): "TÉCNICO",
                Utilitarios.buscar_coluna(df_gs, ["MONITOR", "GESTOR"]): "MONITOR",
            }
            df_gs = df_gs.rename(columns={k: v for k, v in rename_map.items() if k})
            if "LOGIN" in df_gs.columns:
                df_gs["LOGIN"] = df_gs["LOGIN"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.upper()
                df_gs = df_gs.dropna(subset=["LOGIN"]).drop_duplicates(subset=["LOGIN"], keep="last")
            return df_gs
        except Exception as e:
            st.warning(f"Falha ao sincronizar com Google Sheets: {e}. A hierarquia pode não ser carregada.")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(show_spinner=False)
    def preparar_base(df: pd.DataFrame, df_gsheets: pd.DataFrame, _version: int) -> pd.DataFrame:
        if df is None or df.empty: return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.astype(str).str.strip().str.upper()

        col_status = Utilitarios.buscar_coluna(df, ["STATUS DA O.S 1"])
        if not col_status:
            st.error("ERRO CRÍTICO: Nenhuma coluna de status ('Status da Atividade' ou 'Status') encontrada na base. A análise não pode continuar.")
            st.stop()
        
        df["Status Contrato"] = Utilitarios.classificar_os_series(df[col_status])
        df["TOTAL DE TAREFAS"] = pd.to_numeric(df.get("TOTAL DE TAREFAS", 1), errors="coerce").fillna(1)

        col_login = Utilitarios.buscar_coluna(df, ["LOGIN", "LOGIN DO TÉCNICO", "USUÁRIO", "MATRÍCULA"])
        if col_login and not df_gsheets.empty and "LOGIN" in df_gsheets.columns:
            df[col_login] = df[col_login].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.upper()
            df = df.merge(df_gsheets, left_on=col_login, right_on="LOGIN", how="left")

        df["TÉCNICO"] = df.get("TÉCNICO", "NÃO MAPEADO").fillna("NÃO MAPEADO")
        df["MONITOR"] = df.get("MONITOR", "SEM MONITOR").fillna("SEM MONITOR")
        return df

def calcular_volumetria(df: pd.DataFrame, grupo: List[str]) -> pd.DataFrame:
    if df is None or df.empty or not all(g in df.columns for g in grupo):
        return pd.DataFrame()
    
    pv = pd.pivot_table(df, index=grupo, columns="Status Contrato", values="TOTAL DE TAREFAS", aggfunc="sum", fill_value=0)
    for col in ["Executada", "Não Executada", "Pendente"]:
        if col not in pv: pv[col] = 0.0
    
    df_vol = pv.reset_index().copy()
    df_vol["Baixadas"] = df_vol["Executada"] + df_vol["Não Executada"]
    df_vol["Total Alocado"] = df_vol["Baixadas"] + df_vol["Pendente"]
    df_vol["Taxa Execução"] = np.where(df_vol["Baixadas"] > 0, df_vol["Executada"] / df_vol["Baixadas"], 0.0)
    df_vol["Taxa Quebra"] = 1 - df_vol["Taxa Execução"]
    
    return df_vol.sort_values("Total Alocado", ascending=False).reset_index(drop=True)

# ====================================================
# APLICAÇÃO PRINCIPAL
# ====================================================
def main():
    st.title("🗣️ Painel Executivo: Análise de Volumetria")

    if "df_memoria" not in st.session_state: st.session_state.df_memoria = None

    # --- Barra Lateral ---
    with st.sidebar:
        st.header("Controles")
        if st.button("🔄 Substituir Base de Dados", use_container_width=True, type="secondary"):
            st.session_state.df_memoria = None
            st.rerun()
        if st.button("🧹 Limpar Cache e Reiniciar", use_container_width=True):
            st.cache_data.clear()
            st.session_state.df_memoria = None
            st.rerun()
        st.markdown("---")

    # --- Fluxo de Upload ou Exibição ---
    if st.session_state.df_memoria is None:
        st.subheader("Importação de Dados")
        arquivo = st.file_uploader("📥 Envie a base de dados operacional (Excel ou CSV)", type=["xlsx", "xls", "csv"])
        if arquivo:
            with st.spinner("Analisando dados e cruzando hierarquias..."):
                df_base = DadosManager.ler_arquivo_bytes(arquivo.getvalue(), arquivo.name)
                df_gs = DadosManager.buscar_gsheets()
                st.session_state.df_memoria = DadosManager.preparar_base(df_base, df_gs, _version=Configuracoes.PREPARACAO_BASE_VERSAO)
            st.rerun()
        return

    df_full = st.session_state.df_memoria
    
    # --- Filtros na Barra Lateral ---
    st.sidebar.header("Filtros")
    monitores_disponiveis = sorted(df_full["MONITOR"].unique())
    monitores_selecionados = st.sidebar.multiselect("Filtrar por Monitor", options=monitores_disponiveis, default=monitores_disponiveis)
    df_filtrado = df_full[df_full["MONITOR"].isin(monitores_selecionados)]

    # --- KPIs Globais ---
    total_os = df_filtrado['TOTAL DE TAREFAS'].sum()
    executadas = df_filtrado[df_filtrado['Status Contrato'] == 'Executada']['TOTAL DE TAREFAS'].sum()
    nao_executadas = df_filtrado[df_filtrado['Status Contrato'] == 'Não Executada']['TOTAL DE TAREFAS'].sum()
    pendentes = total_os - executadas - nao_executadas
    taxa_quebra = (nao_executadas / (executadas + nao_executadas)) if (executadas + nao_executadas) > 0 else 0

    st.subheader("Visão Geral da Operação (Filtrada)")
    kpi1, kpi2, kpi3 = st.columns(3)
    kpi1.markdown(ComponenteVisual.criar_card("Total de OS Alocadas", f"{total_os:,.0f}", "azul", f"Pendentes: {pendentes:,.0f}"), unsafe_allow_html=True)
    kpi2.markdown(ComponenteVisual.criar_card("OS Executadas", f"{executadas:,.0f}", "verde", f"{1-taxa_quebra:.1%} de Sucesso"), unsafe_allow_html=True)
    kpi3.markdown(ComponenteVisual.criar_card("OS Não Executadas", f"{nao_executadas:,.0f}", "vermelho", f"{taxa_quebra:.1%} de Quebra"), unsafe_allow_html=True)    
    st.markdown("---")

    # --- Abas para Análise Detalhada ---
    tabs = st.tabs(["📊 Desempenho por Equipe", "🧑‍🔧 Análise por Técnico"])

    with tabs[0]:
        df_vol_monitor = calcular_volumetria(df_filtrado, grupo=["MONITOR"])
        st.subheader("Desempenho Consolidado por Monitor")
        st.dataframe(df_vol_monitor, use_container_width=True, hide_index=True)
        st.download_button("📥 Baixar Relatório por Equipe", Utilitarios.to_excel(df_vol_monitor), "desempenho_equipes.xlsx")

    with tabs[1]:
        st.subheader("Desempenho Individual por Técnico")
        monitor_selecionado = st.selectbox("Selecione um Monitor para detalhar", options=monitores_disponiveis)
        if monitor_selecionado:
            df_tecnicos_monitor = df_filtrado[df_filtrado["MONITOR"] == monitor_selecionado]
            df_vol_tecnico = calcular_volumetria(df_tecnicos_monitor, grupo=["TÉCNICO"])
            st.dataframe(df_vol_tecnico, use_container_width=True, hide_index=True)
            st.download_button(f"📥 Baixar Relatório de Técnicos ({monitor_selecionado})", Utilitarios.to_excel(df_vol_tecnico), f"desempenho_tecnicos_{monitor_selecionado}.xlsx")

if __name__ == "__main__":
    main()