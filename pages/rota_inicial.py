import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from io import BytesIO
from typing import Any

# ==========================================
# 1. CONFIGURAÇÕES E ESTILOS
# ==========================================
st.set_page_config(
    page_title="Painel Operacional Totale",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

URL_GSHEETS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit?usp=drive_link"

MAPEAMENTO_PERIODOS = {
    "08:00 - 10:00": "Manhã",
    "08:00 - 11:00": "Manhã",
    "08:00 - 12:00": "Manhã",
    "10:00 - 12:00": "Manhã",
    "11:00 - 14:00": "Manhã",
    "12:00 - 14:00": "Tarde I",
    "12:00 - 15:00": "Tarde I",
    "12:00 - 18:00": "Tarde II",
    "14:00 - 16:00": "Tarde II",
    "14:00 - 17:00": "Tarde II",
    "15:00 - 18:00": "Tarde II",
    "16:00 - 18:00": "Tarde II",
    "17:00 - 20:00": "Tarde II",
    "Imediata": "Imediata",
}

TEMAS_CARD = {
    "azul": {
        "fundo": "#F0F9FF",
        "texto": "#0369A1",
        "borda": "#0EA5E9",
        "titulo": "#075985",
    },
    "verde": {
        "fundo": "#F0FDF4",
        "texto": "#15803D",
        "borda": "#22C55E",
        "titulo": "#166534",
    },
    "roxo": {
        "fundo": "#FAF5FF",
        "texto": "#7E22CE",
        "borda": "#A855F7",
        "titulo": "#6B21A8",
    },
    "cinza": {
        "fundo": "#F8FAFC",
        "texto": "#334155",
        "borda": "#94A3B8",
        "titulo": "#64748B",
    },
    "escuro": {
        "fundo": "#1E293B",
        "texto": "#FFFFFF",
        "borda": "#475569",
        "titulo": "#E2E8F0",
    },
    "laranja": {
        "fundo": "#FFF7ED",
        "texto": "#C2410C",
        "borda": "#F97316",
        "titulo": "#9A3412",
    },
    "vermelho": {
        "fundo": "#FEF2F2",
        "texto": "#B91C1C",
        "borda": "#EF4444",
        "titulo": "#991B1B",
    },
}


def renderizar_card(
    titulo: str, valor: str, tema: str = "azul", subtitulo: str = ""
) -> str:
    cores = TEMAS_CARD.get(tema, TEMAS_CARD["azul"])
    sub_html = (
        f'<p style="margin: 0; font-size: 13px; color: {cores["titulo"]}; opacity: 0.85; padding-top: 5px; font-weight: 600;">{subtitulo}</p>'
        if subtitulo
        else ""
    )
    return f"""
    <div style="background-color: {cores['fundo']}; padding: 20px; border-radius: 10px; border-left: 8px solid {cores['borda']}; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
        <p style="margin: 0; font-size: 13px; color: {cores['titulo']}; text-transform: uppercase; font-weight: bold;">{titulo}</p>
        <h1 style="margin: 0; padding-top: 5px; color: {cores['texto']}; font-weight: 900; font-size: 34px;">{valor}</h1>
        {sub_html}
    </div>
    """


def renderizar_mini_card(titulo: str, valor: Any, tema: str = "cinza") -> str:
    cores = TEMAS_CARD.get(tema, TEMAS_CARD["cinza"])
    return f"""
    <div style="background-color: {cores['fundo']}; padding: 10px; border-radius: 6px; border-left: 4px solid {cores['borda']}; text-align: center; margin-bottom: 10px;">
        <p style="margin: 0; font-size: 11px; color: {cores['titulo']}; font-weight: bold; text-transform: uppercase;">{titulo}</p>
        <h3 style="margin: 0; color: {cores['texto']}; font-size: 18px; font-weight: 800;">{valor}</h3>
    </div>
    """


# ==========================================
# 2. EXTRAÇÃO E TRATAMENTO DE DADOS
# ==========================================
@st.cache_data(ttl=600, show_spinner=False)
def buscar_google_sheets() -> pd.DataFrame:
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(
            spreadsheet=URL_GSHEETS, usecols=["Login", "Técnico", "Monitor", "Base"]
        )
        df = df.dropna(subset=["Login"])
        df["Login"] = (
            df["Login"]
            .astype(str)
            .str.replace(r"\.0$", "", regex=True)
            .str.strip()
            .str.upper()
        )
        return df
    except Exception:
        return pd.DataFrame(columns=["Login", "Técnico", "Monitor", "Base"])


@st.cache_data(show_spinner=False)
def ler_arquivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
    bio = BytesIO(file_bytes)
    try:
        if filename.lower().endswith(".csv"):
            try:
                # sep=None com engine='python' faz o Pandas descobrir o separador automaticamente
                return pd.read_csv(
                    bio, sep=None, engine="python", encoding="utf-8-sig", dtype=str
                )
            except UnicodeDecodeError:
                # Se falhar por causa de acentos (Windows antigo), tenta com 'latin1'
                bio.seek(0)
                return pd.read_csv(
                    bio, sep=None, engine="python", encoding="latin1", dtype=str
                )
        else:
            return pd.read_excel(bio, engine="openpyxl", dtype=str)

    except Exception as e:
        st.error(
            f"Erro ao ler o arquivo. Certifique-se de que é um Excel ou CSV válido. Detalhe: {e}"
        )
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def processar_base_principal(
    df_bruto: pd.DataFrame, df_ativos: pd.DataFrame
) -> pd.DataFrame:
    if df_bruto.empty:
        return pd.DataFrame()
    df = df_bruto.copy()

    # Padronizar nomes das colunas para letras maiúsculas para facilitar a busca
    df.columns = df.columns.astype(str).str.strip().str.upper()

    # --- MAPEAMENTO INTELIGENTE DE COLUNAS ---
    mapa_colunas = {
        "CONTRATO": ["CONTRATO"],
        "LOGIN_TECNICO": ["LOGIN DO TÉCNICO", "LOGIN DO TECNICO"],
        "STATUS_ATIVIDADE": ["STATUS DA ATIVIDADE"],
        "TOTAL_TAREFAS": ["TOTAL DE TAREFAS"],
        "TIPO_OS": ["TIPO O.S 1"],
        "HABILIDADE": ["HABILIDADE DE TRABALHO"],
        "PRODUTO": ["PRODUTO"],
        "INTERVALO": ["INTERVALO DE TEMPO", "INTERVALO"],
        "CIDADE": ["CIDADE"],
        "COORD_X": ["COORDENADA X", "LONGITUDE", "LON"],
        "COORD_Y": ["COORDENADA Y", "LATITUDE", "LAT"],
    }

    # Renomear colunas dinamicamente
    for padrao, variacoes in mapa_colunas.items():
        col_encontrada = next((c for c in df.columns if c in variacoes), None)
        if col_encontrada:
            df = df.rename(columns={col_encontrada: padrao})
        else:
            df[padrao] = (
                np.nan
            )  # Cria a coluna vazia caso não exista para não quebrar o código

    # --- LIMPEZA DE DADOS E EXCLUSÃO DE VAZIOS ---

    # 1. Excluir contratos vazios com tratamento robusto
    contrato = (
        df["CONTRATO"].astype("string").str.replace("\u00a0", " ", regex=False).str.strip()
    )

    mask_contrato_vazio = (
        contrato.isna()
        | contrato.eq("")
        | contrato.str.upper().isin(["NAN", "NONE", "NULL", "<NA>"])
    )

    removidos = int(mask_contrato_vazio.sum())

    df = df.loc[~mask_contrato_vazio].copy()
    df["CONTRATO"] = contrato.loc[df.index].str.upper()

    st.sidebar.info(f"Contratos vazios removidos: {removidos}")

    if df.empty:
        st.warning("⚠️ A base de dados ficou vazia após a remoção de contratos em branco.")
        return pd.DataFrame()

    # 2. Demais limpezas
    df["LOGIN_TECNICO"] = (
        df["LOGIN_TECNICO"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.upper()
    )
    df["TOTAL_TAREFAS"] = (
        pd.to_numeric(
            df["TOTAL_TAREFAS"].astype(str).str.replace(",", "."), errors="coerce"
        )
        .fillna(1)
        .astype(int)
    )
    df["STATUS_ATIVIDADE"] = df["STATUS_ATIVIDADE"].astype(str).str.strip().str.upper()

    # --- MERGE COM GOOGLE SHEETS ---
    if not df_ativos.empty:
        # Remove colunas antigas caso existam na base para não duplicar
        df = df.drop(
            columns=[
                c for c in ["Técnico", "Monitor", "Base"] if c.upper() in df.columns
            ],
            errors="ignore",
        )
        df = df.merge(df_ativos, left_on="LOGIN_TECNICO", right_on="Login", how="left")
        df = df.rename(columns={"Técnico": "NOME_OFICIAL"})

    df["NOME_OFICIAL"] = df.get("NOME_OFICIAL", df["LOGIN_TECNICO"]).fillna(
        df["LOGIN_TECNICO"]
    )
    df["Monitor"] = df.get("Monitor", pd.Series(dtype=str)).fillna("SEM MONITOR")

    # --- FLAGS BOOLEANAS (SERVIÇOS PREMIUM E TIPOS) ---
    hab = df["HABILIDADE"].astype(str).str.upper()
    tipo = df["TIPO_OS"].astype(str).str.upper()
    prod = df["PRODUTO"].astype(str).str.upper()

    df["Check_GPON"] = hab.str.contains(r"PON\(1/100\)", regex=True, na=False)
    df["Check_ND"] = tipo.str.contains("ADESAO", na=False)
    df["Check_Migracao"] = (tipo.str.strip() == "24 - MUDANCA DE PACOTE") & df["Check_GPON"]
    df["Check_Streaming"] = hab.str.contains("TV VAS(1/100)", na=False)
    df["Check_Ponto_Ultra"] = hab.str.contains("NETLAR", na=False)
    df["Check_4K"] = prod.str.contains("4K", na=False)
    df["Check_Soundbox"] = prod.str.contains("SOUND", na=False)

    # --- MAPEAR PERÍODO ---
    df["PERIODO_TRATADO"] = (
        df["INTERVALO"]
        .astype(str)
        .str.strip()
        .map(MAPEAMENTO_PERIODOS)
        .fillna("Outros/Sem Período")
    )

    return df


# ==========================================
# 3. INTERFACE E APLICAÇÃO PRINCIPAL
# ==========================================
def main():
    if "df_master" not in st.session_state:
        st.session_state["df_master"] = None

    # TELA DE UPLOAD
    if st.session_state["df_master"] is None:
        st.title("Bem-vindo ao Painel Operacional Totale 🚀")
        st.subheader("📥 Entrada de Dados")

        st.markdown(
            """<style>[data-testid="stFileUploadDropzone"] {border: 2px dashed #0EA5E9; border-radius: 8px; padding: 15px; background-color: #F0F9FF;}</style>""",
            unsafe_allow_html=True,
        )
        arquivo = st.file_uploader(
            "Envie a planilha extraída do sistema (Excel ou CSV):", type=["xlsx", "csv"]
        )

        if arquivo is not None:
            with st.spinner("🚀 Processando dados e conectando à nuvem..."):
                df_bruto = ler_arquivo(arquivo.getvalue(), arquivo.name)
                df_ativos = buscar_google_sheets()
                df_processado = processar_base_principal(df_bruto, df_ativos)

                if not df_processado.empty:
                    st.session_state["df_master"] = df_processado
                    st.rerun()
        return

    # TELA DO DASHBOARD
    df_master = st.session_state["df_master"].copy()

    # --- BARRA LATERAL ---
    with st.sidebar:
        st.success("✅ Base carregada com sucesso!")
        if st.button("🔄 Substituir Base", use_container_width=True):
            st.session_state["df_master"] = None
            st.rerun()

        st.markdown("---")
        st.header("🔍 Filtros")

        periodos = st.selectbox(
            "⏰ Período", ["Todos"] + sorted(df_master["PERIODO_TRATADO"].unique())
        )
        if periodos != "Todos":
            df_master = df_master[df_master["PERIODO_TRATADO"] == periodos]

        monitores = st.multiselect(
            "👨‍💼 Monitor", sorted(df_master["Monitor"].dropna().unique())
        )
        if monitores:
            df_master = df_master[df_master["Monitor"].isin(monitores)]

        if st.checkbox("🟢 Apenas Adesão (Novos Dom.)"):
            df_master = df_master[df_master["Check_ND"]]
        if st.checkbox("🔄 Apenas Migração (MP GPON)"):
            df_master = df_master[df_master["Check_Migracao"]]
        if st.checkbox("📡 Requer GPON"):
            df_master = df_master[df_master["Check_GPON"]]
        if st.checkbox("📡 Requer Streaming"):
            df_master = df_master[df_master["Check_Streaming"]]
        if st.checkbox("📡 Requer 4K"):
            df_master = df_master[df_master["Check_4K"]]
        if st.checkbox("📡 Requer Ponto Ultra"):
            df_master = df_master[df_master["Check_Ponto_Ultra"]]
        if st.checkbox("📡 Requer Soundbox"):
            df_master = df_master[df_master["Check_Soundbox"]]

    # --- CABEÇALHO (KPIs) ---
    st.title("📈 Dashboard Totale: Visão Geral")

    soma_os = df_master["TOTAL_TAREFAS"].sum()
    tecnicos = df_master["LOGIN_TECNICO"].nunique()
    monitores_qtd = df_master["Monitor"].nunique()

    os_concluidas = df_master[
        df_master["STATUS_ATIVIDADE"].isin(
            ["CONCLUÍDO", "EXECUTADA", "BAIXADA", "REALIZADA"]
        )
    ]["TOTAL_TAREFAS"].sum()
    tx_conclusao = (os_concluidas / soma_os) if soma_os > 0 else 0
    tema_status = (
        "verde"
        if tx_conclusao > 0.5
        else "laranja" if tx_conclusao > 0.2 else "vermelho"
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            renderizar_card("Volume O.S.", f"{soma_os:,.0f}", "azul"),
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            renderizar_card(
                "Técnicos Operando",
                f"{tecnicos}",
                "escuro",
                f"Média: {soma_os/tecnicos:.1f} O.S./Téc." if tecnicos > 0 else "",
            ),
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            renderizar_card("Monitores (Gestão)", f"{monitores_qtd}", "roxo"),
            unsafe_allow_html=True,
        )
    with c4:
        st.markdown(
            renderizar_card(
                "Andamento do Dia",
                f"{os_concluidas:,.0f} O.S.",
                tema_status,
                f"{tx_conclusao:.1%} Concluídas",
            ),
            unsafe_allow_html=True,
        )

    # --- GRÁFICOS EXECUTIVOS ---
    st.markdown("### 📈 Visão Executiva")
    g1, g2, g3 = st.columns([1, 1, 1.2])

    with g1:
        st.markdown("##### 🚦 Status da Frota")
        df_status = (
            df_master.groupby("STATUS_ATIVIDADE")["TOTAL_TAREFAS"].sum().reset_index()
        )
        fig_stat = px.pie(
            df_status,
            names="STATUS_ATIVIDADE",
            values="TOTAL_TAREFAS",
            hole=0.5,
            color_discrete_sequence=px.colors.qualitative.Prism,
        )
        fig_stat.update_layout(
            showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=250
        )
        st.plotly_chart(fig_stat, use_container_width=True)

    with g2:
        st.markdown("##### ⏰ Pico de Agendamento")
        df_per = (
            df_master.groupby("PERIODO_TRATADO")["TOTAL_TAREFAS"].sum().reset_index()
        )
        fig_per = px.bar(
            df_per,
            x="PERIODO_TRATADO",
            y="TOTAL_TAREFAS",
            text_auto=True,
            color="PERIODO_TRATADO",
            color_discrete_sequence=["#0EA5E9", "#F59E0B", "#F97316", "#8B5CF6"],
        )
        fig_per.update_layout(
            showlegend=False,
            margin=dict(t=0, b=0, l=0, r=0),
            height=250,
            xaxis_title="",
            yaxis_title="",
        )
        st.plotly_chart(fig_per, use_container_width=True)

    with g3:
        st.markdown("##### 💎 Mix de Serviços Premium")
        df_prem = pd.DataFrame(
            [
                {"Serviço": "GPON", "Qtd": df_master["Check_GPON"].sum()},
                {"Serviço": "4K", "Qtd": df_master["Check_4K"].sum()},
                {"Serviço": "Soundbox", "Qtd": df_master["Check_Soundbox"].sum()},
                {"Serviço": "Ponto Ultra", "Qtd": df_master["Check_Ponto_Ultra"].sum()},
            ]
        )
        df_prem = df_prem[df_prem["Qtd"] > 0]
        if not df_prem.empty:
            fig_prem = px.bar(
                df_prem,
                x="Qtd",
                y="Serviço",
                orientation="h",
                text_auto=True,
                color_discrete_sequence=["#10B981"],
            )
            fig_prem.update_layout(
                showlegend=False,
                margin=dict(t=0, b=0, l=0, r=0),
                height=250,
                xaxis_title="",
                yaxis_title="",
            )
            st.plotly_chart(fig_prem, use_container_width=True)
        else:
            st.info("Nenhum serviço premium.")

    st.divider()

    # --- ABAS DE DETALHAMENTO ---
    aba_dash, aba_tec, aba_rotas, aba_dados = st.tabs(
        [
            "📋 Dash Monitores",
            "🏆 Top Técnicos",
            "🗺️ Mapa Geográfico",
            "🗃️ Base de Dados",
        ]
    )

    with aba_dash:
        df_resumo = (
            df_master.groupby("Monitor")
            .agg(
                OS=("TOTAL_TAREFAS", "sum"),
                GPON=("Check_GPON", "sum"),
                ND=("Check_ND", "sum"),
                Migração=("Check_Migracao", "sum"),
                Qtd_4K=("Check_4K", "sum"),
                Ultra=("Check_Ponto_Ultra", "sum"),
                Soundbox=("Check_Soundbox", "sum"),
                Equipe=("LOGIN_TECNICO", "nunique"),
            )
            .reset_index()
        )
        df_resumo["Média"] = np.where(
            df_resumo["Equipe"] > 0, df_resumo["OS"] / df_resumo["Equipe"], 0
        )

        if not df_resumo.empty:
            st.dataframe(
                df_resumo,
                column_config={
                    "Monitor": st.column_config.TextColumn("Monitor", width="medium"),
                    "OS": st.column_config.ProgressColumn(
                        "Volume OS",
                        format="%d",
                        min_value=0,
                        max_value=int(df_resumo["OS"].max()),
                    ),
                    "Média": st.column_config.NumberColumn("Média/Téc.", format="%.1f"),
                },
                hide_index=True,
                use_container_width=True,
            )

    with aba_tec:
        prod_df = (
            df_master.groupby("NOME_OFICIAL")
            .agg({"TOTAL_TAREFAS": "sum"})
            .reset_index()
            .sort_values("TOTAL_TAREFAS", ascending=False)
            .head(15)
        )
        fig_tec = px.bar(
            prod_df,
            x="TOTAL_TAREFAS",
            y="NOME_OFICIAL",
            orientation="h",
            color="TOTAL_TAREFAS",
            color_continuous_scale="Blues",
            text_auto=True,
        )
        fig_tec.update_layout(yaxis={"categoryorder": "total ascending"}, height=500)
        st.plotly_chart(fig_tec, use_container_width=True)

    with aba_rotas:
        df_mapa = df_master.dropna(subset=["COORD_X", "COORD_Y"]).copy()
        if (
            not df_mapa.empty
            and df_mapa["COORD_X"].astype(str).str.contains(r"\d").any()
        ):
            df_mapa["COORD_X"] = pd.to_numeric(
                df_mapa["COORD_X"].astype(str).str.replace(",", "."), errors="coerce"
            )
            df_mapa["COORD_Y"] = pd.to_numeric(
                df_mapa["COORD_Y"].astype(str).str.replace(",", "."), errors="coerce"
            )
            df_mapa = df_mapa.dropna(subset=["COORD_X", "COORD_Y"])

            if not df_mapa.empty:
                fig_mapa = px.scatter_mapbox(
                    df_mapa,
                    lat="COORD_Y",
                    lon="COORD_X",
                    color="STATUS_ATIVIDADE",
                    zoom=9,
                    height=500,
                    hover_name="NOME_OFICIAL",
                )
                fig_mapa.update_layout(
                    mapbox_style="open-street-map",
                    margin={"r": 0, "t": 0, "l": 0, "b": 0},
                )
                st.plotly_chart(fig_mapa, use_container_width=True)
        else:
            st.info(
                "Sua planilha não possui coordenadas GPS válidas para desenhar o mapa."
            )

    with aba_dados:
        st.dataframe(df_master, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
