import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
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
        "roxo": {"fundo": "#FAF5FF", "texto": "#7E22CE", "borda": "#A855F7", "titulo": "#581C87"}
    }

    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"

# ====================================================
# BLOCO 2: COMPONENTES VISUAIS
# ====================================================
class ComponenteVisual:
    @staticmethod
    def criar_card(titulo: str, valor: str, tema: str = "azul", subtitulo: str = "", icone: str = "") -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        titulo_formatado = f"{icone} {titulo}" if icone else titulo

        return f"""
        <div style="background-color: {cores['fundo']}; padding: 20px; border-radius: 10px; border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.05); height: 100%; display: flex; flex-direction: column; justify-content: center;">
            <p style="margin: 0; font-size: 14px; color: {cores['titulo']}; font-weight: bold;">{titulo_formatado}</p>
            <h2 style="margin: 5px 0 0 0; color: {cores['texto']}; font-weight: 900; font-size: 32px;">{valor}</h2>
            <p style="margin: 5px 0 0 0; font-size: 13px; color: #64748B; font-weight: 500;">{subtitulo}</p>
        </div>
        """

# ====================================================
# BLOCO 3: UTILITÁRIOS
# ====================================================
class Utilitarios:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras_chave: List[str]) -> Optional[str]:
        if df.empty: return None
        cols_upper = {c.upper().strip(): c for c in df.columns}
        for palavra in palavras_chave:
            chave = palavra.upper().strip()
            if chave in cols_upper: return cols_upper[chave]
        return None

    @staticmethod
    def padronizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return df
        df = df.copy()
        df.columns = df.columns.str.upper().str.strip()
        return df

    @staticmethod
    def normalizar_login(serie: pd.Series) -> pd.Series:
        return serie.astype(str).str.replace(".0", "", regex=False).str.strip().str.upper()

# ====================================================
# BLOCO 4: DADOS MOCK (TESTE)
# ====================================================
@st.cache_data(show_spinner=False)
def gerar_dados_teste() -> pd.DataFrame:
    import numpy as np
    datas = pd.date_range(start="2023-10-01", periods=15, freq="D").tolist() * 3
    logins = ["1001", "1002", "1003"] * 15
    return pd.DataFrame({
        "DATA": datas,
        "LOGIN": logins,
        "BASE": ["SP", "SP", "CAMPINAS"] * 15,
        "STATUS": ["CONCLUÍDO", "PENDENTE", "CONCLUÍDO"] * 15
    })

# ====================================================
# BLOCO 5: CARREGAMENTO E PREPARAÇÃO
# ====================================================
class CarregadorDados:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(arquivo_enviado) -> pd.DataFrame:
        try:
            nome_arquivo = arquivo_enviado.name.lower()
            if nome_arquivo.endswith(".csv"): return pd.read_csv(arquivo_enviado, sep=None, engine="python", encoding="utf-8")
            if nome_arquivo.endswith((".xlsx", ".xls")): return pd.read_excel(arquivo_enviado, engine="openpyxl")
            return pd.DataFrame()
        except Exception: return pd.DataFrame()

    @staticmethod
    @st.cache_data(ttl=300, show_spinner=False)
    def carregar_ativos(url: str) -> pd.DataFrame:
        conn = st.connection("gsheets", type=GSheetsConnection)
        return conn.read(spreadsheet=url, ttl=0)

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_dados_gsheets() -> pd.DataFrame:
        try:
            df_gs = CarregadorDados.carregar_ativos(Configuracoes.URL_ATIVOS)
            if df_gs.empty: return df_gs

            df_gs = Utilitarios.padronizar_colunas(df_gs)

            col_login = Utilitarios.buscar_coluna(df_gs, ["LOGIN", "ID", "MATRÍCULA", "MATRICULA", "USUARIO"])
            col_tec = Utilitarios.buscar_coluna(df_gs, ["TÉCNICO", "TECNICO", "NOME", "VENDEDOR"])
            col_mon = Utilitarios.buscar_coluna(df_gs, ["MONITOR", "GESTOR", "SUPERVISOR"])

            renomear = {}
            if col_login: renomear[col_login] = "LOGIN"
            if col_tec: renomear[col_tec] = "TÉCNICO"
            if col_mon: renomear[col_mon] = "MONITOR"

            df_gs = df_gs.rename(columns=renomear)

            if "LOGIN" in df_gs.columns: df_gs["LOGIN"] = Utilitarios.normalizar_login(df_gs["LOGIN"])
            if "TÉCNICO" in df_gs.columns: df_gs["TÉCNICO"] = df_gs["TÉCNICO"].astype(str).str.strip().str.upper()
            if "MONITOR" in df_gs.columns: df_gs["MONITOR"] = df_gs["MONITOR"].astype(str).str.strip().str.upper()

            colunas_validas = [c for c in ["LOGIN", "TÉCNICO", "MONITOR"] if c in df_gs.columns]
            return df_gs[colunas_validas].drop_duplicates()
        except Exception: return pd.DataFrame()

@st.cache_data(show_spinner=False)
def preparar_base_cache(df: pd.DataFrame, df_hierarquia: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()

    df = df.copy()
    df = Utilitarios.padronizar_colunas(df)

    # Tenta localizar login da base enviada
    col_login_upload = Utilitarios.buscar_coluna(df, ["LOGIN", "LOGIN DO TÉCNICO", "USUÁRIO", "MATRÍCULA", "ID"])

    # Cruzamento com Google Sheets
    if col_login_upload and not df_hierarquia.empty and "LOGIN" in df_hierarquia.columns:
        df[col_login_upload] = Utilitarios.normalizar_login(df[col_login_upload])
        df_hierarquia = df_hierarquia.copy()
        df_hierarquia["LOGIN"] = Utilitarios.normalizar_login(df_hierarquia["LOGIN"])

        colunas_remover = [c for c in ["TÉCNICO", "MONITOR"] if c in df.columns]
        if colunas_remover: df = df.drop(columns=colunas_remover)

        df = df.merge(
            df_hierarquia[["LOGIN", "TÉCNICO", "MONITOR"]].drop_duplicates(subset=["LOGIN"], keep="last"),
            left_on=col_login_upload, right_on="LOGIN", how="left"
        )

        df["TÉCNICO"] = df["TÉCNICO"].fillna("NÃO MAPEADO NO SHEETS")
        df["MONITOR"] = df["MONITOR"].fillna("SEM MONITOR")
        if col_login_upload != "LOGIN": df = df.drop(columns=["LOGIN"], errors="ignore")

    # Se não conseguiu merge, garante colunas
    if "TÉCNICO" not in df.columns:
        col_tec_existente = Utilitarios.buscar_coluna(df, ["TÉCNICO", "TECNICO", "NOME EQUIPE"])
        if col_tec_existente: df = df.rename(columns={col_tec_existente: "TÉCNICO"})
        else: df["TÉCNICO"] = "NÃO INFORMADO"

    if "MONITOR" not in df.columns:
        col_monitor_existente = Utilitarios.buscar_coluna(df, ["MONITOR", "GESTOR", "SUPERVISOR"])
        if col_monitor_existente: df = df.rename(columns={col_monitor_existente: "MONITOR"})
        else: df["MONITOR"] = "SEM MONITOR"

    df["TÉCNICO"] = df["TÉCNICO"].astype(str).str.strip().str.upper()
    df["MONITOR"] = df["MONITOR"].astype(str).str.strip().str.upper()

    col_data = Utilitarios.buscar_coluna(df, ["DATA", "DATA AGENDAMENTO", "DATE"])
    if col_data: df[col_data] = pd.to_datetime(df[col_data], errors="coerce").dt.date

    return df

# ====================================================
# BLOCO 6: FRONT-END (PÁGINA)
# ====================================================
st.set_page_config(page_title="Dashboard Base", page_icon="📊", layout="wide")
st.title("📊 Dashboard: Análise de Dados")
st.markdown("Visualização e tratamento da base cruzada com a hierarquia atual.")

CHAVE_MEMORIA = "df_geral_upload"

if CHAVE_MEMORIA not in st.session_state:
    st.session_state[CHAVE_MEMORIA] = None

# ====================================================
# BLOCO 7: UPLOADER OCULTO
# ====================================================
if st.session_state[CHAVE_MEMORIA] is None:
    arquivo = st.file_uploader("📥 Envie sua base de dados (Excel/CSV)", type=["xlsx", "xls", "csv"])

    col_mock1, col_mock2 = st.columns([1, 5])
    with col_mock1: usar_mock = st.button("🧪 Testar demo")

    if usar_mock:
        st.session_state[CHAVE_MEMORIA] = preparar_base_cache(gerar_dados_teste(), CarregadorDados.buscar_dados_gsheets())
        st.rerun()

    if arquivo is not None:
        with st.spinner("Processando base e cruzando com Google Sheets..."):
            df_bruto = CarregadorDados.ler_arquivo(arquivo)
            df_gsheets = CarregadorDados.buscar_dados_gsheets()
            df_full = preparar_base_cache(df_bruto, df_gsheets)
            st.session_state[CHAVE_MEMORIA] = df_full
        st.rerun()

else:
    df_full = st.session_state[CHAVE_MEMORIA]

    col_aviso, col_btn = st.columns([4, 1])
    with col_aviso: st.success("✅ Base carregada e cruzada com sucesso!")
    with col_btn:
        if st.button("🔄 Enviar outra base", use_container_width=True):
            st.session_state[CHAVE_MEMORIA] = None
            st.rerun()

    if df_full is None or df_full.empty:
        st.warning("⚠️ A base carregada está vazia.")
        st.stop()

    # ====================================================
    # BLOCO 8: IDENTIFICAÇÃO DE COLUNAS & AUDITORIA
    # ====================================================
    col_data = Utilitarios.buscar_coluna(df_full, ["DATA", "DATA AGENDAMENTO", "DATE"])
    col_base = Utilitarios.buscar_coluna(df_full, ["BASE", "PROJETO", "FILIAL", "CIDADE"])

    qtd_nao_mapeados = 0
    if "TÉCNICO" in df_full.columns:
        qtd_nao_mapeados = len(df_full[df_full["TÉCNICO"] == "NÃO MAPEADO NO SHEETS"])

    # ====================================================
    # BLOCO 9: SIDEBAR (FILTROS)
    # ====================================================
    with st.sidebar:
        st.header("🎯 Filtros")

        if qtd_nao_mapeados > 0:
            st.error(f"⚠️ {qtd_nao_mapeados} registros sem cadastro no Google Sheets.")
            st.divider()

        mask = pd.Series(True, index=df_full.index)

        # Filtro Data
        if col_data and not df_full[col_data].dropna().empty:
            min_date, max_date = df_full[col_data].min(), df_full[col_data].max()
            datas_sel = st.date_input("📅 Período:", [min_date, max_date], min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
            if len(datas_sel) == 2: mask &= (df_full[col_data] >= datas_sel[0]) & (df_full[col_data] <= datas_sel[1])

        # Filtro Base
        if col_base:
            bases = ["Todas"] + sorted([str(b) for b in df_full.loc[mask, col_base].dropna().unique() if str(b).strip() != "" and str(b).lower() != "nan"])
            base_sel = st.selectbox("📍 Base:", bases)
            if base_sel != "Todas": mask &= (df_full[col_base] == base_sel)

        # Filtro Monitor
        if "MONITOR" in df_full.columns:
            monitores = ["Todos"] + sorted([str(m) for m in df_full.loc[mask, "MONITOR"].dropna().unique() if str(m).strip() != "" and str(m).lower() != "nan"])
            monitor_sel = st.selectbox("👔 Monitor:", monitores)
            if monitor_sel != "Todos": mask &= (df_full["MONITOR"] == monitor_sel)

        st.divider()

        # Filtro Técnico
        tecnicos_filtrados = sorted([str(t) for t in df_full.loc[mask, "TÉCNICO"].dropna().unique() if str(t).strip() != "" and str(t).lower() != "nan"])
        if not tecnicos_filtrados:
            st.warning("⚠️ Nenhum dado encontrado com os filtros atuais.")
            st.stop()

        tec_selecionado = st.selectbox("🔎 Analisar Técnico:", options=["(Visão Geral)"] + tecnicos_filtrados)

    # ====================================================
    # BLOCO 10: RENDERIZAÇÃO DE DADOS
    # ====================================================
    df_filtrado = df_full[mask].copy()
    if tec_selecionado != "(Visão Geral)": df_filtrado = df_filtrado[df_filtrado["TÉCNICO"] == tec_selecionado]

    st.divider()
    
    # Card Simples
    st.markdown("### 📊 Resumo")
    c1, c2, c3 = st.columns(3)
    with c1: 
        st.markdown(ComponenteVisual.criar_card("Total de Registros", f"{len(df_filtrado):,}".replace(",", "."), "azul", "Linhas Filtradas", "📋"), unsafe_allow_html=True)

    st.write("---")

    # Tabela e Download
    st.markdown("#### 🧾 Base de Dados Processada")
    
    if col_data and col_data in df_filtrado.columns:
        df_filtrado = df_filtrado.sort_values(by=col_data, ascending=False)

    st.dataframe(df_filtrado, use_container_width=True, hide_index=True)

    csv_bytes = df_filtrado.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
    st.download_button(label="📥 Baixar Base (.CSV)", data=csv_bytes, file_name="base_tratada.csv", mime="text/csv", type="primary")