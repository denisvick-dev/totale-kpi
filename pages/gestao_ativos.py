import pandas as pd
import streamlit as st
import time
from datetime import datetime
import plotly.express as px
from io import BytesIO
from streamlit_gsheets import GSheetsConnection

# ===========================================
# CONFIGURAÇÃO DA PÁGINA E TEMAS VISUAIS
# ===========================================
st.set_page_config(
    page_title="Gestão de Ativos TOTALE",
    page_icon="👷",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    "amarelo": {
        "fundo": "#FEF9C3",
        "texto": "#854D0E",
        "borda": "#EAB308",
        "titulo": "#A16207",
    },
    "cinza": {
        "fundo": "#F8FAFC",
        "texto": "#334155",
        "borda": "#94A3B8",
        "titulo": "#64748B",
    },
    "vermelho": {
        "fundo": "#FEF2F2",
        "texto": "#991B1B",
        "borda": "#EF4444",
        "titulo": "#7F1D1D",
    },
}


def criar_card_metrica(titulo, valor, tema="azul"):
    cores = TEMAS_CARD.get(tema, TEMAS_CARD["azul"])
    return f"""
    <div style="background-color: {cores['fundo']}; padding: 20px; border-radius: 10px;
        border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 15px;">
        <p style="margin: 0; font-size: 14px; color: {cores['titulo']};"><b>{titulo}</b></p>
        <h2 style="margin: 0; padding-top: 5px; color: {cores['texto']}; font-weight: 900;">{valor}</h2>
    </div>
    """


# Adicionado INATIVO (Soft Delete)
LISTA_SITUACOES = [
    "ATIVO",
    "FÉRIAS",
    "INOPERANTE",
    "ETN",
    "DESLIGADO",
    "AFASTADO",
    "INATIVO",
]
URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"


# ===========================================
# ARQUITETURA LIMPA: FUNÇÕES GLOBAIS (DRY)
# ===========================================
def gerar_log_auditoria(usuario: str, acao: str) -> str:
    """Gera string com data, hora, usuário e ação para rastreabilidade."""
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    return f"{agora} | {acao} por {usuario.upper()}"


def atualizar_google_sheets(df_novo: pd.DataFrame, mensagem_sucesso: str):
    """Função única para salvar no Sheets, limpa cache e exibe Toast."""
    try:
        conexao = st.connection("gsheets", type=GSheetsConnection)
        conexao.update(spreadsheet=URL_ATIVOS, data=df_novo)
        carregar_planilha.clear()
        st.toast(mensagem_sucesso, icon="✅")
        time.sleep(1)  # Tempo mínimo para o Toast aparecer antes do reload
        st.rerun()
    except Exception as erro:
        st.error(f"❌ Erro na nuvem: {erro}")


# ===========================================
# SEGURANÇA E LOGIN
# ===========================================
if "logado" not in st.session_state:
    st.session_state.logado = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = ""

# Busca senhas no st.secrets. Se não achar (em testes locais), usa padrão.
try:
    USER_CORRETO = st.secrets["credenciais"]["usuario"]
    PWD_CORRETA = st.secrets["credenciais"]["senha"]
except:
    USER_CORRETO = "denis"
    PWD_CORRETA = "admin"

if not st.session_state.logado:
    st.markdown(
        """<style>[data-testid="collapsedControl"] {display: none}</style>""",
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.write("\n\n")
        st.markdown(
            "<h2 style='text-align: center;'>🔐 Acesso TOTALE</h2>",
            unsafe_allow_html=True,
        )
        with st.form("form_login"):
            usuario = st.text_input("👤 Usuário:")
            senha = st.text_input("🔑 Senha:", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                if usuario == USER_CORRETO and senha == PWD_CORRETA:
                    st.session_state.logado = True
                    st.session_state.usuario_logado = usuario
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos!")
    st.stop()


# ===========================================
# CARREGAMENTO DE DADOS (COM CACHE)
# ===========================================
@st.cache_data(ttl=300)
def carregar_planilha():
    try:
        conexao = st.connection("gsheets", type=GSheetsConnection)
        df = conexao.read(spreadsheet=URL_ATIVOS, ttl=0)
        df.columns = df.columns.str.strip()
        # Garante que a coluna de auditoria exista
        if "Ultima_Modificacao" not in df.columns:
            df["Ultima_Modificacao"] = ""
        return df
    except Exception:
        return pd.DataFrame()


# ===========================================
# ESTRUTURA PRINCIPAL (SISTEMA LOGADO)
# ===========================================
usuario_atual = st.session_state.usuario_logado

st.sidebar.markdown(f"👤 **Logado como:** `{usuario_atual.upper()}`")
col_btn1, col_btn2 = st.sidebar.columns(2)
if col_btn1.button("🔄 Atualizar"):
    carregar_planilha.clear()
    st.rerun()
if col_btn2.button("🚪 Sair"):
    st.session_state.logado = False
    st.rerun()
st.sidebar.divider()

st.title("📊 Gestão de Ativos TOTALE")

with st.spinner("Sincronizando com Google Sheets..."):
    df_ativos_bruto = carregar_planilha()

if not df_ativos_bruto.empty:
    lista_bases = ["Nova Base..."] + sorted(
        df_ativos_bruto["Base"].dropna().astype(str).unique().tolist()
    )
    lista_monitores = ["Novo Monitor..."] + sorted(
        df_ativos_bruto["Monitor"].dropna().astype(str).unique().tolist()
    )

    aba_dashboard, aba_cadastro, aba_edicao = st.tabs(
        ["📈 Dashboard & Relatórios", "➕ Novo / Lote", "✏️ Editar / Excluir"]
    )

    # ===========================================
    # ABA 1: DASHBOARD, GRÁFICOS E EXPORTAÇÃO
    # ===========================================
    with aba_dashboard:
        # Por padrão, não mostrar INATIVOS (Soft Delete)
        df_filtrado = df_ativos_bruto[df_ativos_bruto["Situação"] != "INATIVO"].copy()

        st.sidebar.header("🎯 Filtros")
        opcoes_base = ["Todas"] + sorted(
            df_filtrado["Base"].dropna().astype(str).unique()
        )
        base_sel = st.sidebar.selectbox("Base:", opcoes_base)
        if base_sel != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Base"] == base_sel]

        opcoes_monitor = ["Todos"] + sorted(
            df_filtrado["Monitor"].dropna().astype(str).unique()
        )
        monitor_sel = st.sidebar.selectbox("Monitor:", opcoes_monitor)
        if monitor_sel != "Todos":
            df_filtrado = df_filtrado[df_filtrado["Monitor"] == monitor_sel]

        opcoes_situacao = ["Todas"] + sorted(
            df_filtrado["Situação"].dropna().astype(str).unique()
        )
        situacao_sel = st.sidebar.selectbox("Situação:", opcoes_situacao)
        if situacao_sel != "Todas":
            df_filtrado = df_filtrado[df_filtrado["Situação"] == situacao_sel]

        # Métricas Globais
        qtd_ativos = (df_filtrado["Situação"] == "ATIVO").sum()
        qtd_desligados = (df_filtrado["Situação"] == "DESLIGADO").sum()

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(
                criar_card_metrica("Total (Filtrado)", len(df_filtrado), "cinza"),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                criar_card_metrica("Técnicos Ativos", qtd_ativos, "verde"),
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                criar_card_metrica(
                    "Bases Operadas", df_filtrado["Base"].nunique(), "azul"
                ),
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                criar_card_metrica("Desligados", qtd_desligados, "vermelho"),
                unsafe_allow_html=True,
            )

        # Gráficos Analíticos
        st.write("---")
        g1, g2 = st.columns([2, 1])
        with g1:
            st.markdown("**Volume de Técnicos por Base**")
            df_graf_base = (
                df_filtrado.groupby("Base")
                .size()
                .reset_index(name="Total")
                .sort_values("Total", ascending=False)
            )
            fig_base = px.bar(
                df_graf_base,
                x="Base",
                y="Total",
                color="Total",
                color_continuous_scale="Blues",
                text_auto=True,
            )
            fig_base.update_layout(
                showlegend=False,
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=0, b=0, l=0, r=0),
            )
            st.plotly_chart(fig_base, use_container_width=True)

        with g2:
            st.markdown("**Distribuição de Status**")
            df_graf_sit = (
                df_filtrado.groupby("Situação").size().reset_index(name="Total")
            )
            fig_sit = px.pie(
                df_graf_sit,
                values="Total",
                names="Situação",
                hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_sit.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_sit, use_container_width=True)

        # Tabela e Exportação
        st.write("---")
        col_tab1, col_tab2 = st.columns([4, 1])
        with col_tab1:
            st.subheader("📋 Lista de Técnicos")
        with col_tab2:
            # Exportação Excel
            out = BytesIO()
            with pd.ExcelWriter(out, engine="openpyxl") as w:
                df_filtrado.to_excel(w, index=False, sheet_name="Ativos")
            st.download_button(
                "📥 Exportar Lista (Excel)",
                out.getvalue(),
                "tecnicos_ativos.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        st.dataframe(df_filtrado, use_container_width=True, hide_index=True, height=400)

    # ===========================================
    # ABA 2: CADASTRO MANUAL E LOTE
    # ===========================================
    with aba_cadastro:
        st.subheader("📝 Cadastro Manual")
        with st.form(key="form_novo_ativo", clear_on_submit=True):
            c_form1, c_form2 = st.columns(2)
            with c_form1:
                novo_re = st.text_input("RE *")
                novo_login = st.text_input("Login NETSALES *")
                novo_nome = st.text_input("Nome do Técnico *")
            with c_form2:
                sel_base = st.selectbox("Base *", lista_bases)
                nova_base_input = st.text_input(
                    "Ou Nova Base:", disabled=(sel_base != "Nova Base...")
                )
                sel_monitor = st.selectbox("Monitor *", lista_monitores)
                novo_monitor_input = st.text_input(
                    "Ou Novo Monitor:", disabled=(sel_monitor != "Novo Monitor...")
                )
                nova_situacao = st.selectbox(
                    "Situação *", [s for s in LISTA_SITUACOES if s != "INATIVO"]
                )  # Oculta Inativo

            if st.form_submit_button("💾 Salvar Técnico", type="primary"):
                b_final = (
                    nova_base_input.strip().upper()
                    if sel_base == "Nova Base..."
                    else sel_base
                )
                m_final = (
                    novo_monitor_input.strip().upper()
                    if sel_monitor == "Novo Monitor..."
                    else sel_monitor
                )

                if (
                    not novo_re
                    or not novo_login
                    or not novo_nome
                    or not b_final
                    or not m_final
                ):
                    st.error("⚠️ Preencha todos os campos obrigatórios!")
                else:
                    df_atualizado = df_ativos_bruto.copy()
                    novo_registro = {
                        "RE": novo_re.strip(),
                        "Login": novo_login.strip(),
                        "Técnico": novo_nome.strip().upper(),
                        "Monitor": m_final,
                        "Base": b_final,
                        "Situação": nova_situacao,
                        "Ultima_Modificacao": gerar_log_auditoria(
                            usuario_atual, "CRIADO"
                        ),
                    }
                    df_atualizado = pd.concat(
                        [df_atualizado, pd.DataFrame([novo_registro])],
                        ignore_index=True,
                    )
                    atualizar_google_sheets(
                        df_atualizado, "Técnico cadastrado com sucesso!"
                    )

        st.write("---")
        with st.expander("📁 Importação de Dados em Lote (Excel/CSV)"):
            st.info(
                "O arquivo deve conter exatamente as colunas: RE, Login, Técnico, Monitor, Base, Situação"
            )
            arq_upload = st.file_uploader(
                "Arraste sua planilha aqui", type=["xlsx", "csv"]
            )
            if arq_upload and st.button("🚀 Processar Importação"):
                try:
                    df_lote = (
                        pd.read_excel(arq_upload)
                        if arq_upload.name.endswith("xlsx")
                        else pd.read_csv(arq_upload)
                    )
                    df_lote["Ultima_Modificacao"] = gerar_log_auditoria(
                        usuario_atual, "IMPORT LOTE"
                    )
                    df_final = pd.concat(
                        [df_ativos_bruto, df_lote], ignore_index=True
                    ).drop_duplicates(subset=["RE"], keep="last")
                    atualizar_google_sheets(
                        df_final, f"{len(df_lote)} registros importados com sucesso!"
                    )
                except Exception as e:
                    st.error(f"Erro no arquivo: Verifique as colunas. Detalhe: {e}")

    # ===========================================
    # ABA 3: EDIÇÃO E SOFT DELETE
    # ===========================================
    with aba_edicao:
        st.subheader("🔍 Buscar e Modificar Ativos")
        # Filtra os "Inativos" na busca a menos que se queira restaurar
        df_busca = df_ativos_bruto[df_ativos_bruto["Situação"] != "INATIVO"].copy()
        df_busca["Identificador"] = (
            df_busca["Técnico"].fillna("") + " | RE: " + df_busca["RE"].astype(str)
        )

        tecnico_selecionado = st.selectbox(
            "Selecione o Técnico:", [""] + df_busca["Identificador"].tolist()
        )

        if tecnico_selecionado != "":
            idx = df_busca[df_busca["Identificador"] == tecnico_selecionado].index[0]
            dados_atuais = df_ativos_bruto.loc[idx]

            st.write("---")
            col_edicao, col_exclusao = st.columns([2, 1])

            with col_edicao:
                st.markdown("#### ✏️ Atualizar Dados")
                with st.form("form_editar"):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        st.text_input(
                            "RE (Bloqueado)",
                            value=dados_atuais.get("RE", ""),
                            disabled=True,
                        )
                        st.text_input(
                            "Login (Bloqueado)",
                            value=dados_atuais.get("Login", ""),
                            disabled=True,
                        )
                        edit_nome = st.text_input(
                            "Técnico", value=dados_atuais.get("Técnico", "")
                        )
                    with e_col2:
                        edit_base = st.text_input(
                            "Base", value=dados_atuais.get("Base", "")
                        )
                        edit_monitor = st.text_input(
                            "Monitor", value=dados_atuais.get("Monitor", "")
                        )
                        idx_sit = (
                            LISTA_SITUACOES.index(dados_atuais.get("Situação", "ATIVO"))
                            if dados_atuais.get("Situação", "ATIVO") in LISTA_SITUACOES
                            else 0
                        )
                        edit_situacao = st.selectbox(
                            "Situação", LISTA_SITUACOES, index=idx_sit
                        )

                    if st.form_submit_button("💾 Salvar Alterações", type="primary"):
                        df_atualizado = df_ativos_bruto.copy()
                        df_atualizado.at[idx, "Técnico"] = (
                            (edit_nome or "").strip().upper()
                        )
                        df_atualizado.at[idx, "Base"] = (
                            (edit_base or "").strip().upper()
                        )
                        df_atualizado.at[idx, "Monitor"] = (
                            (edit_monitor or "").strip().upper()
                        )
                        df_atualizado.at[idx, "Situação"] = edit_situacao
                        df_atualizado.at[idx, "Ultima_Modificacao"] = (
                            gerar_log_auditoria(usuario_atual, "EDIÇÃO")
                        )

                        atualizar_google_sheets(
                            df_atualizado, "Dados atualizados com sucesso!"
                        )

            with col_exclusao:
                st.markdown("#### 🗑️ Exclusão Segura (Soft Delete)")
                st.info(
                    "A exclusão altera o status para 'INATIVO', mantendo o histórico de vendas do técnico nos relatórios."
                )

                if st.checkbox(
                    f"Sim, desejo inativar o RE: {dados_atuais.get('RE', '')}"
                ):
                    if st.button(
                        "🚨 Inativar Técnico", type="primary", use_container_width=True
                    ):
                        df_atualizado = df_ativos_bruto.copy()
                        df_atualizado.at[idx, "Situação"] = "INATIVO"
                        df_atualizado.at[idx, "Ultima_Modificacao"] = (
                            gerar_log_auditoria(usuario_atual, "INATIVADO")
                        )

                        atualizar_google_sheets(
                            df_atualizado, "Técnico inativado com sucesso!"
                        )

else:
    st.warning("⚠️ Planilha vazia ou não encontrada.")
