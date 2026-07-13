import streamlit as st
import pandas as pd
import numpy as np
from streamlit_gsheets import GSheetsConnection
from typing import Optional, Dict, List, Mapping
from io import BytesIO

# ====================================================
# CONFIG
# ====================================================
st.set_page_config(page_title="Gestão de Volumetria", page_icon="📊", layout="wide")


class Config:
    URL_ATIVOS: str = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"

    PREPARACAO_BASE_VERSAO = 12  # bump p/ invalidar cache

    TEMAS_CARD: Dict[str, Dict[str, str]] = {
        "azul": {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
        "verde": {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
        "vermelho": {"fundo": "#FEF2F2", "texto": "#B91C1C", "borda": "#EF4444", "titulo": "#991B1B"},
        "escuro": {"fundo": "#1E293B", "texto": "#FFFFFF", "borda": "#475569", "titulo": "#E2E8F0"},
    }


# ====================================================
# CONSTANTES (COLUNAS INTERNAS)
# ====================================================
COL_STATUS_CONTRATO = "Status Contrato"
COL_TOTAL = "TOTAL DE TAREFAS"
COL_TECNICO = "TÉCNICO"
COL_MONITOR = "MONITOR"

FMT_STYLE: Dict[str, str] = {
    "Executada": "{:.0f}",
    "Não Executada": "{:.0f}",
    "Pendente": "{:.0f}",
    "Baixadas": "{:.0f}",
    "Total Alocado": "{:.0f}",
    "Taxa Execução": "{:.1%}",
    "Taxa Quebra": "{:.1%}",
    "Projeção": "{:.0f}",
}


# ====================================================
# UTIL
# ====================================================
class U:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, chaves: List[str]) -> Optional[str]:
        if df is None or df.empty:
            return None
        cols = {str(c).strip().upper(): c for c in df.columns}
        for k in chaves:
            kk = str(k).strip().upper()
            if kk in cols:
                return cols[kk]
        return None

    @staticmethod
    def norm_text(s: pd.Series) -> pd.Series:
        return s.fillna("").astype(str).str.strip().str.upper()

    @staticmethod
    def norm_login(s: pd.Series) -> pd.Series:
        return (
            s.astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
            .str.upper()
        )

    @staticmethod
    def classificar_status_contrato_por_os1(status_os1: pd.Series) -> pd.Series:
        """
        Regra:
        - STATUS DA O.S 1 contém NÃO/NAO EXECUT -> Não Executada
        - STATUS DA O.S 1 contém EXECUT (e não é não-exec) -> Executada
        - vazio/nulo/outros -> Pendente
        """
        s = U.norm_text(status_os1)
        vazio = s.isin(["", "NAN", "NONE", "NULL"])
        nao_exec = s.str.contains(r"(N[AÃ]O|NAO)\s*EXECUT", regex=True, na=False)
        executada = s.str.contains(r"EXECUT", regex=True, na=False) & (~nao_exec)

        return pd.Series(
            np.select([executada, nao_exec, vazio], ["Executada", "Não Executada", "Pendente"], default="Pendente"),
            index=status_os1.index,
        )

    @staticmethod
    def to_excel(df: pd.DataFrame, sheet_name: str) -> bytes:
        output = BytesIO()
        try:
            import importlib.util
            engine = "xlsxwriter" if importlib.util.find_spec("xlsxwriter") else "openpyxl"
        except Exception:
            engine = "openpyxl"

        with pd.ExcelWriter(output, engine=engine) as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        return output.getvalue()


class UI:
    @staticmethod
    def card(titulo: str, valor: str, tema: str, subtitulo: str = "") -> str:
        c = Config.TEMAS_CARD[tema]
        return f"""
        <div style="background-color:{c['fundo']};padding:16px;border-radius:10px;border-left:6px solid {c['borda']};
                    box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);margin-bottom:12px;min-height:110px;
                    display:flex;flex-direction:column;justify-content:center;">
            <p style="margin:0;font-size:11px;color:{c['titulo']};font-weight:700;text-transform:uppercase;letter-spacing:0.5px;">
                {titulo}
            </p>
            <h2 style="margin:4px 0;color:{c['texto']};font-weight:900;font-size:26px;line-height:1.1;">
                {valor}
            </h2>
            <p style="margin:0;font-size:11px;color:#64748B;font-weight:500;">
                {subtitulo}
            </p>
        </div>"""

    @staticmethod
    def colorir_projecao(_):
        return "background-color:#334155; color:white; font-weight:700"

    @staticmethod
    def colorir_executada_meta(x):
        try:
            return "background-color:#C6EFCE; color:#006100; font-weight:700" if float(x) >= 7 else ""
        except Exception:
            return ""


# ====================================================
# DADOS
# ====================================================
class Dados:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
        try:
            name = filename.lower()
            bio = BytesIO(file_bytes)
            if name.endswith((".xlsx", ".xls")):
                return pd.read_excel(bio, engine="openpyxl")
            return pd.read_csv(bio, sep=None, engine="python")
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_gsheets() -> pd.DataFrame:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df_gs = conn.read(spreadsheet=Config.URL_ATIVOS)
            if df_gs is None or df_gs.empty:
                return pd.DataFrame()

            df_gs.columns = df_gs.columns.astype(str).str.strip().str.upper()

            col_login = U.buscar_coluna(df_gs, ["LOGIN", "ID", "MATRÍCULA", "MATRICULA"])
            col_tec = U.buscar_coluna(df_gs, ["TÉCNICO", "TECNICO", "NOME"])
            col_mon = U.buscar_coluna(df_gs, ["MONITOR", "GESTOR"])

            rename = {}
            if col_login: rename[col_login] = "LOGIN"
            if col_tec: rename[col_tec] = COL_TECNICO
            if col_mon: rename[col_mon] = COL_MONITOR

            df_gs = df_gs.rename(columns=rename)

            if "LOGIN" in df_gs.columns:
                df_gs["LOGIN"] = U.norm_login(df_gs["LOGIN"])
                df_gs = df_gs.dropna(subset=["LOGIN"]).drop_duplicates(subset=["LOGIN"], keep="last")

            return df_gs
        except Exception as e:
            st.warning(f"Aviso: falha ao sincronizar Google Sheets ({e}). A hierarquia não será aplicada.")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(show_spinner=False)
    def preparar_base(df: pd.DataFrame, df_gsheets: pd.DataFrame, _version: int) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.astype(str).str.strip().str.upper()

        diag = {
            "linhas_iniciais": len(df),
            "removidos_contrato_vazio": 0,
            "removidos_suspensos": 0,
        }

        # (1) Contrato (opcional) - remove vazios
        col_contrato = U.buscar_coluna(df, ["CONTRATO", "Nº CONTRATO", "NÚMERO DO CONTRATO"])
        if col_contrato:
            s = U.norm_text(df[col_contrato]).replace(["", "NAN", "NONE", "NULL"], pd.NA)
            antes = len(df)
            df[col_contrato] = s
            df = df.dropna(subset=[col_contrato]).copy()
            diag["removidos_contrato_vazio"] = antes - len(df)

            if df.empty:
                st.warning("A base ficou vazia após remover contratos em branco.")
                return pd.DataFrame()

        # (2) Remover suspensos - SOMENTE Status da Atividade
        col_status_atividade = U.buscar_coluna(df, ["STATUS DA ATIVIDADE"])
        if not col_status_atividade:
            st.error("ERRO: coluna obrigatória 'Status da Atividade' não encontrada (para remover suspensos).")
            st.stop()

        s_atv = U.norm_text(df[col_status_atividade])
        antes = len(df)
        df = df[~s_atv.str.contains(r"SUSP", regex=True, na=False)].copy()
        diag["removidos_suspensos"] = antes - len(df)

        if df.empty:
            st.warning("Após remover 'Suspensos' (Status da Atividade), a base ficou vazia.")
            return pd.DataFrame()

        # (3) Status Contrato - SOMENTE por Status da O.S 1
        col_status_os1 = U.buscar_coluna(df, ["STATUS DA O.S 1"])
        if not col_status_os1:
            st.error("ERRO: coluna obrigatória 'Status da O.S 1' não encontrada (para Status Contrato).")
            st.stop()

        df[COL_STATUS_CONTRATO] = U.classificar_status_contrato_por_os1(df[col_status_os1])

        # (4) Total de tarefas
        col_total = U.buscar_coluna(df, ["TOTAL DE TAREFAS"])
        if col_total:
            df[COL_TOTAL] = pd.to_numeric(df[col_total], errors="coerce").fillna(1)
        else:
            df[COL_TOTAL] = 1

        # (5) Merge hierarquia
        col_login_base = U.buscar_coluna(
            df,
            ["LOGIN DO TÉCNICO", "LOGIN DO TECNICO", "LOGIN", "USUÁRIO", "USUARIO", "MATRÍCULA", "MATRICULA"],
        )
        if col_login_base and not df_gsheets.empty and "LOGIN" in df_gsheets.columns:
            df[col_login_base] = U.norm_login(df[col_login_base])
            df = df.merge(df_gsheets, left_on=col_login_base, right_on="LOGIN", how="left")

        # (6) Defaults
        df[COL_TECNICO] = df.get(COL_TECNICO, pd.Series("NÃO MAPEADO", index=df.index)).fillna("NÃO MAPEADO")
        df[COL_MONITOR] = df.get(COL_MONITOR, pd.Series("SEM MONITOR", index=df.index)).fillna("SEM MONITOR")

        # categories (opcional)
        for c in [COL_TECNICO, COL_MONITOR, COL_STATUS_CONTRATO]:
            if c in df.columns:
                df[c] = df[c].astype("category")

        diag["linhas_finais"] = len(df)
        df.attrs["diag"] = diag
        return df


# ====================================================
# MÉTRICAS
# ====================================================
def calcular_volumetria(df: pd.DataFrame, grupo: List[str]) -> pd.DataFrame:
    if df is None or df.empty or not all(g in df.columns for g in grupo):
        return pd.DataFrame()

    agg = (
        df.groupby(grupo + [COL_STATUS_CONTRATO], dropna=False)[COL_TOTAL]
        .sum()
        .unstack(COL_STATUS_CONTRATO, fill_value=0)
        .reset_index()
    )

    for col in ["Executada", "Não Executada", "Pendente"]:
        if col not in agg.columns:
            agg[col] = 0

    agg["Baixadas"] = agg["Executada"] + agg["Não Executada"]
    agg["Total Alocado"] = agg["Baixadas"] + agg["Pendente"]

    agg["Taxa Execução"] = np.where(agg["Baixadas"] > 0, agg["Executada"] / agg["Baixadas"], 0.0)
    agg["Taxa Quebra"] = np.where(agg["Baixadas"] > 0, 1 - agg["Taxa Execução"], 0.0)
    agg["Projeção"] = agg["Executada"] + (agg["Taxa Execução"] * agg["Pendente"])

    return agg.sort_values("Total Alocado", ascending=False).reset_index(drop=True)


def calcular_kpis(df: pd.DataFrame) -> Dict[str, float]:
    executadas = float(df.loc[df[COL_STATUS_CONTRATO] == "Executada", COL_TOTAL].sum())
    nao_executadas = float(df.loc[df[COL_STATUS_CONTRATO] == "Não Executada", COL_TOTAL].sum())
    pendentes = float(df.loc[df[COL_STATUS_CONTRATO] == "Pendente", COL_TOTAL].sum())

    total = executadas + nao_executadas + pendentes
    baixadas = executadas + nao_executadas

    taxa_sucesso = (executadas / baixadas) if baixadas > 0 else 0.0
    taxa_quebra = (nao_executadas / baixadas) if baixadas > 0 else 0.0
    projecao = executadas + taxa_sucesso * pendentes

    return {
        "total": total,
        "executadas": executadas,
        "nao_executadas": nao_executadas,
        "pendentes": pendentes,
        "taxa_sucesso": taxa_sucesso,
        "taxa_quebra": taxa_quebra,
        "projecao": projecao,
    }


# ====================================================
# UI (RENDER)
# ====================================================
def render_kpis(k: Dict[str, float]) -> None:
    st.subheader("Visão Geral (Filtrada)")
    c1, c2, c3, c4 = st.columns(4)

    c1.markdown(UI.card("Total Alocado", f"{k['total']:,.0f}", "azul", f"Pendentes: {k['pendentes']:,.0f}"), unsafe_allow_html=True)
    c2.markdown(UI.card("Executadas", f"{k['executadas']:,.0f}", "verde", f"Execução: {k['taxa_sucesso']:.1%}"), unsafe_allow_html=True)
    c3.markdown(UI.card("Não Executadas", f"{k['nao_executadas']:,.0f}", "vermelho", f"Quebra: {k['taxa_quebra']:.1%}"), unsafe_allow_html=True)
    c4.markdown(UI.card("Projeção", f"{k['projecao']:,.0f}", "escuro", "Projeção de acordo com os pendentes"), unsafe_allow_html=True)


def render_tabela_padrao(df_tabela: pd.DataFrame, titulo: str, excel_nome: str, sheet: str) -> None:
    st.subheader(titulo)
    if df_tabela is None or df_tabela.empty:
        st.info("Sem dados para exibir.")
        return

    styler = df_tabela.style.format(FMT_STYLE)  # type: ignore[reportArgumentType]
    styler = styler.map(UI.colorir_projecao, subset=["Projeção"])
    st.dataframe(styler, use_container_width=True, hide_index=True)

    st.download_button(
        "📥 Baixar Excel",
        U.to_excel(df_tabela, sheet_name=sheet),
        file_name=excel_nome,
        use_container_width=True,
    )


def render_tabela_tecnico_com_meta(df_tabela: pd.DataFrame, titulo: str, excel_nome: str, sheet: str) -> None:
    st.subheader(titulo)
    if df_tabela is None or df_tabela.empty:
        st.info("Sem dados para exibir.")
        return

    styler = (
        df_tabela.style
        .format(FMT_STYLE)  # type: ignore[reportArgumentType]
        .map(UI.colorir_projecao, subset=["Projeção"])
        .map(UI.colorir_executada_meta, subset=["Executada"])  # somente aqui
    )
    st.dataframe(styler, use_container_width=True, hide_index=True)

    st.download_button(
        "📥 Baixar Excel",
        U.to_excel(df_tabela, sheet_name=sheet),
        file_name=excel_nome,
        use_container_width=True,
    )


# ====================================================
# APP
# ====================================================
def main():
    st.title("📊 Painel Executivo: Análise de Volumetria")

    if "df_memoria" not in st.session_state:
        st.session_state.df_memoria = None

    # Sidebar: controles
    with st.sidebar:
        st.header("Controles")
        if st.button("🔄 Substituir Base", use_container_width=True):
            st.session_state.df_memoria = None
            st.rerun()

        if st.button("🧹 Limpar Cache e Reiniciar", use_container_width=True):
            st.cache_data.clear()
            st.session_state.df_memoria = None
            st.rerun()

        st.markdown("---")

    # Upload
    if st.session_state.df_memoria is None:
        st.subheader("Importação de Dados")
        arquivo = st.file_uploader("📥 Envie a base operacional (Excel ou CSV)", type=["xlsx", "xls", "csv"])
        if arquivo:
            with st.spinner("Processando base e hierarquia..."):
                df_base = Dados.ler_arquivo_bytes(arquivo.getvalue(), arquivo.name)
                df_gs = Dados.buscar_gsheets()
                st.session_state.df_memoria = Dados.preparar_base(df_base, df_gs, _version=Config.PREPARACAO_BASE_VERSAO)
            st.rerun()
        return

    df_full = st.session_state.df_memoria
    if df_full is None or df_full.empty:
        st.warning("Nenhum dado válido para exibição.")
        return

    # Sidebar: diagnóstico
    with st.sidebar.expander("Diagnóstico"):
        diag = df_full.attrs.get("diag", {})
        for k, v in diag.items():
            st.write(f"**{k}**: {v}")

    # Sidebar: filtros
    st.sidebar.header("Filtros")
    monitores = sorted([m for m in df_full[COL_MONITOR].unique() if pd.notna(m)])
    sel_monitores = st.sidebar.multiselect("Monitor", options=monitores, default=monitores)

    df = df_full[df_full[COL_MONITOR].isin(sel_monitores)].copy()
    if df.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    # KPIs
    k = calcular_kpis(df)
    render_kpis(k)
    st.markdown("---")

    tabs = st.tabs(["📊 Desempenho por Equipe", "🧑‍🔧 Desempenho por Técnico", "📋 Base Completa"])

    # Aba 1 - Monitor
    with tabs[0]:
        df_monitor = calcular_volumetria(df, grupo=[COL_MONITOR])
        render_tabela_padrao(
            df_monitor,
            titulo="Desempenho Consolidado por Monitor",
            excel_nome="desempenho_equipes.xlsx",
            sheet="Por Monitor",
        )

    # Aba 2 - Técnico (com meta Executada>=7)
    with tabs[1]:
        st.subheader("Desempenho Individual por Técnico")
        monitor_sel = st.selectbox("Selecione um Monitor para detalhar", options=monitores)

        df_m = df[df[COL_MONITOR] == monitor_sel]
        df_tecnico = calcular_volumetria(df_m, grupo=[COL_TECNICO])

        if df_tecnico is not None and not df_tecnico.empty:
            df_tecnico = df_tecnico.sort_values(by=["Executada", "Total Alocado"], ascending=[False, False]).reset_index(drop=True)

        render_tabela_tecnico_com_meta(
            df_tecnico,
            titulo=f"Desempenho por Técnico ({monitor_sel})",
            excel_nome=f"desempenho_{str(monitor_sel).strip()}.xlsx",
            sheet="Por Tecnico",
        )

    # Aba 3 - Base
    with tabs[2]:
        st.subheader("Base Completa (Tratada)")
        st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()