import pandas as pd
import streamlit as st
import time
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

# Temas para os Cards
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
    html = f"""
    <div style="
        background-color: {cores['fundo']}; padding: 20px; border-radius: 10px;
        border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 15px;
    ">
        <p style="margin: 0; font-size: 14px; color: {cores['titulo']};"><b>{titulo}</b></p>
        <h2 style="margin: 0; padding-top: 5px; color: {cores['texto']}; font-weight: 900;">{valor}</h2>
    </div>
    """
    return html


# Lista padrão de Situações (Sem o INATIVO)
LISTA_SITUACOES = ["ATIVO", "FÉRIAS", "INOPERANTE", "ETN", "DESLIGADO", "AFASTADO"]

# ===========================================
# PROCESSO DE LOGIN
# ===========================================
if "logado" not in st.session_state:
    st.session_state.logado = False

# Credenciais de acesso
USER_CORRETO = "denis"
PWD_CORRETA = "admin"

if not st.session_state.logado:
    st.markdown(
        """<style>[data-testid="collapsedControl"] {display: none}</style>""",
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.write("")
        st.write("")
        st.markdown(
            "<h2 style='text-align: center;'>🔐 Acesso TOTALE</h2>",
            unsafe_allow_html=True,
        )

        with st.form("form_login"):
            usuario = st.text_input("👤 Usuário:")
            senha = st.text_input("🔑 Senha:", type="password")
            logar = st.form_submit_button("Entrar", use_container_width=True)

            if logar:
                if usuario == USER_CORRETO and senha == PWD_CORRETA:
                    st.session_state.logado = True
                    st.rerun()
                else:
                    st.error("❌ Usuário ou senha incorretos!")
    st.stop()

# ===========================================
# CARREGAMENTO DE DADOS (COM CACHE)
# ===========================================
URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"


@st.cache_data(ttl=300)
def carregar_planilha():
    # Tenta usar a conexão com Google Sheets (quando disponível/configurada)
    try:
        conexao = st.connection("gsheets", type=GSheetsConnection)
        df = conexao.read(spreadsheet=URL_ATIVOS, ttl=0)
        df.columns = df.columns.str.strip()
        return df
    except Exception:
        # Fallback para CSV local (útil para desenvolvimento offline)
        try:
            df = pd.read_csv("exports/ativos.csv")
            df.columns = df.columns.str.strip()
            return df
        except Exception:
            return pd.DataFrame()


# ===========================================
# ESTRUTURA PRINCIPAL (SISTEMA LOGADO)
# ===========================================

st.sidebar.markdown(f"👤 **Logado como:** `{USER_CORRETO.upper()}`")
col_btn1, col_btn2 = st.sidebar.columns(2)
if col_btn1.button("🔄 Atualizar"):
    carregar_planilha.clear()
    st.rerun()
if col_btn2.button("🚪 Sair"):
    st.session_state.logado = False
    st.rerun()
st.sidebar.divider()

st.title("📊 Gestão de Ativos TOTALE")

try:
    with st.spinner("Sincronizando com Google Sheets..."):
        df_ativos_bruto = carregar_planilha()
except Exception as erro:
    st.error(f"❌ Falha crítica ao conectar com a planilha: {erro}")
    df_ativos_bruto = pd.DataFrame()

if not df_ativos_bruto.empty:

    lista_bases = (
        ["Nova Base..."]
        + sorted(df_ativos_bruto["Base"].dropna().astype(str).unique().tolist())
        if "Base" in df_ativos_bruto.columns
        else ["Nova Base..."]
    )
    lista_monitores = (
        ["Novo Monitor..."]
        + sorted(df_ativos_bruto["Monitor"].dropna().astype(str).unique().tolist())
        if "Monitor" in df_ativos_bruto.columns
        else ["Novo Monitor..."]
    )

    # Criação das 3 Abas
    aba_dashboard, aba_cadastro, aba_edicao = st.tabs(
        ["📈 Dashboard & Lista", "➕ Cadastrar Novo", "✏️ Editar / Excluir"]
    )

    # ===========================================
    # ABA 1: DASHBOARD E TABELA FILTRADA
    # ===========================================
    with aba_dashboard:
        df_filtrado = df_ativos_bruto.copy()

        st.sidebar.header("🎯 Filtros do Dashboard")

        if "Base" in df_filtrado.columns:
            opcoes_base = ["Todas"] + sorted(
                df_filtrado["Base"].dropna().astype(str).unique()
            )
            base_sel = st.sidebar.selectbox("Filtrar por Base:", opcoes_base)
            if base_sel != "Todas":
                df_filtrado = df_filtrado[df_filtrado["Base"] == base_sel]

        if "Monitor" in df_filtrado.columns:
            opcoes_monitor = ["Todos"] + sorted(
                df_filtrado["Monitor"].dropna().astype(str).unique()
            )
            monitor_sel = st.sidebar.selectbox("Filtrar por Monitor:", opcoes_monitor)
            if monitor_sel != "Todos":
                df_filtrado = df_filtrado[df_filtrado["Monitor"] == monitor_sel]

        if "Situação" in df_filtrado.columns:
            opcoes_situacao = ["Todas"] + sorted(
                df_filtrado["Situação"].dropna().astype(str).unique()
            )
            situacao_sel = st.sidebar.selectbox(
                "Filtrar por Situação:", opcoes_situacao
            )
            if situacao_sel != "Todas":
                df_filtrado = df_filtrado[df_filtrado["Situação"] == situacao_sel]

        total_registros = len(df_filtrado)
        if "Situação" in df_filtrado.columns:
            situacoes_limpas = (
                df_filtrado["Situação"].dropna().astype(str).str.strip().str.upper()
            )
            qtd_ativos = (situacoes_limpas == "ATIVO").sum()
            qtd_desligados = (situacoes_limpas == "DESLIGADO").sum()
        else:
            qtd_ativos, qtd_desligados = 0, 0

        qtd_bases = (
            df_filtrado["Base"].nunique() if "Base" in df_filtrado.columns else 0
        )

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(
                criar_card_metrica("Total (Filtrado)", f"{total_registros}", "cinza"),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                criar_card_metrica("Técnicos Ativos", f"{qtd_ativos}", "verde"),
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                criar_card_metrica("Bases Operadas", f"{qtd_bases}", "azul"),
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                criar_card_metrica("Desligados", f"{qtd_desligados}", "vermelho"),
                unsafe_allow_html=True,
            )

        st.subheader("📋 Detalhamento dos Técnicos")
        st.dataframe(df_filtrado, use_container_width=True, hide_index=True, height=500)

    # ===========================================
    # ABA 2: FORMULÁRIO DE CADASTRO
    # ===========================================
    with aba_cadastro:
        st.subheader("Preencha os dados do novo Técnico")

        with st.form(key="form_novo_ativo", clear_on_submit=True):
            c_form1, c_form2 = st.columns(2)
            with c_form1:
                novo_re = st.text_input(
                    "RE (Registro de Empregado) *", placeholder="Ex: 123456"
                )
                novo_login = st.text_input(
                    "Login NETSALES *", placeholder="Ex: TEC12345"
                )
                novo_nome = st.text_input(
                    "Nome do Técnico / Equipe *", placeholder="Ex: João da Silva"
                )
            with c_form2:
                sel_base = st.selectbox("Base Operacional *", lista_bases)
                nova_base_input = st.text_input(
                    "Ou digite a Nova Base:", disabled=(sel_base != "Nova Base...")
                )
                sel_monitor = st.selectbox("Monitor / Supervisor *", lista_monitores)
                novo_monitor_input = st.text_input(
                    "Ou digite o Novo Monitor:",
                    disabled=(sel_monitor != "Novo Monitor..."),
                )
                nova_situacao = st.selectbox("Situação Atual *", LISTA_SITUACOES)

            st.markdown("*Campos obrigatórios")
            btn_salvar = st.form_submit_button(
                "💾 Salvar no Google Sheets", type="primary"
            )

            if btn_salvar:
                base_final = nova_base_input if sel_base == "Nova Base..." else sel_base
                monitor_final = (
                    novo_monitor_input
                    if sel_monitor == "Novo Monitor..."
                    else sel_monitor
                )

                if (
                    not novo_re
                    or not novo_login
                    or not novo_nome
                    or not base_final
                    or not monitor_final
                ):
                    st.error("⚠️ Por favor, preencha todos os campos obrigatórios!")
                elif (
                    "RE" in df_ativos_bruto.columns
                    and novo_re.strip()
                    in df_ativos_bruto["RE"].dropna().astype(str).str.strip().values
                ):
                    st.error(f"⚠️ O RE '{novo_re}' já existe na base de dados!")
                elif (
                    "Login" in df_ativos_bruto.columns
                    and novo_login.strip()
                    in df_ativos_bruto["Login"].dropna().astype(str).str.strip().values
                ):
                    st.error(f"⚠️ O Login '{novo_login}' já existe na base de dados!")
                else:
                    with st.spinner("Salvando na nuvem..."):
                        try:
                            conexao = st.connection("gsheets", type=GSheetsConnection)
                            df_atualizado = df_ativos_bruto.copy()
                            novo_registro = {
                                "RE": novo_re.strip(),
                                "Login": novo_login.strip(),
                                "Técnico": novo_nome.strip().upper(),
                                "Monitor": monitor_final.strip().upper(),
                                "Base": base_final.strip().upper(),
                                "Situação": nova_situacao,
                            }
                            df_atualizado = pd.concat(
                                [df_atualizado, pd.DataFrame([novo_registro])],
                                ignore_index=True,
                            )
                            conexao.update(spreadsheet=URL_ATIVOS, data=df_atualizado)
                            carregar_planilha.clear()
                            st.success(f"✅ Técnico cadastrado com sucesso!")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as erro:
                            st.error(f"❌ Erro ao salvar: {erro}")

    # ===========================================
    # ABA 3: EDITAR E EXCLUIR REGISTROS
    # ===========================================
    with aba_edicao:
        st.subheader("Buscar e Modificar Ativos")

        # Cria um identificador único para o dropdown (Nome + RE + Login)
        df_busca = df_ativos_bruto.copy()
        df_busca["Identificador"] = (
            df_busca["Técnico"].fillna("")
            + " | RE: "
            + df_busca["RE"].astype(str).fillna("")
            + " | "
            + df_busca["Login"].fillna("")
        )

        # Selectbox de busca
        tecnico_selecionado = st.selectbox(
            "🔍 Selecione o Técnico que deseja modificar:",
            [""] + df_busca["Identificador"].tolist(),
        )

        if tecnico_selecionado != "":
            # Pega o índice real da linha no dataframe
            idx = df_busca[df_busca["Identificador"] == tecnico_selecionado].index[0]
            dados_atuais = df_ativos_bruto.loc[idx]

            st.divider()
            col_edicao, col_exclusao = st.columns([2, 1])

            # --- ÁREA DE ATUALIZAÇÃO ---
            with col_edicao:
                st.markdown("#### ✏️ Atualizar Dados")
                with st.form("form_editar"):
                    e_col1, e_col2 = st.columns(2)
                    with e_col1:
                        # RE e Login bloqueados para evitar quebra de chave primária
                        edit_re = st.text_input(
                            "RE", value=dados_atuais.get("RE", ""), disabled=True
                        )
                        edit_login = st.text_input(
                            "Login", value=dados_atuais.get("Login", ""), disabled=True
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

                        # Pega o valor atual para definir o index do selectbox
                        sit_atual = (
                            str(dados_atuais.get("Situação", "")).strip().upper()
                        )
                        idx_sit = (
                            LISTA_SITUACOES.index(sit_atual)
                            if sit_atual in LISTA_SITUACOES
                            else 0
                        )
                        edit_situacao = st.selectbox(
                            "Situação", LISTA_SITUACOES, index=idx_sit
                        )

                    btn_atualizar = st.form_submit_button(
                        "💾 Salvar Alterações", type="primary"
                    )
                    if btn_atualizar:
                        with st.spinner("Atualizando base de dados..."):
                            try:
                                conexao = st.connection("gsheets", type=GSheetsConnection)
                                df_atualizado = df_ativos_bruto.copy()

                                # 🔒 Função segura para tratar texto
                                def tratar_texto(valor):
                                    return (valor or "").strip().upper()

                                # ✅ Aplica as alterações com segurança
                                df_atualizado.at[idx, "Técnico"] = tratar_texto(edit_nome)
                                df_atualizado.at[idx, "Base"] = tratar_texto(edit_base)
                                df_atualizado.at[idx, "Monitor"] = tratar_texto(edit_monitor)
                                df_atualizado.at[idx, "Situação"] = edit_situacao or ""

                                # ✅ Atualiza planilha
                                conexao.update(spreadsheet=URL_ATIVOS, data=df_atualizado)

                                carregar_planilha.clear()
                                st.success("✅ Dados atualizados com sucesso!")
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as erro:
                                st.error(f"❌ Erro ao atualizar: {erro}")

                    # --- ÁREA DE EXCLUSÃO ---
                    with col_exclusao:
                        st.markdown("#### 🗑️ Excluir Registro")
                        st.warning(
                            "⚠️ **Atenção:** Esta ação apagará o técnico definitivamente da base do Google Sheets e não pode ser desfeita."
                        )

                        # Checkbox de segurança
                        confirmar = st.checkbox(
                            f"Sim, desejo excluir o RE: {dados_atuais.get('RE', '')}"
                        )

                        if confirmar:
                            if st.button("🚨 Apagar Definitivamente", type="primary"):
                                with st.spinner("Apagando registro da nuvem..."):
                                    try:
                                        conexao = st.connection(
                                            "gsheets", type=GSheetsConnection
                                        )
                                        # Remove a linha pelo index
                                        df_atualizado = df_ativos_bruto.drop(idx)

                                        conexao.update(
                                            spreadsheet=URL_ATIVOS, data=df_atualizado
                                        )
                                        carregar_planilha.clear()
                                        st.success("✅ Registro excluído com sucesso!")
                                        time.sleep(1.5)
                                        st.rerun()
                                    except Exception as erro:
                                        st.error(f"❌ Erro ao excluir: {erro}")

else:
    st.warning("⚠️ Nenhum dado foi carregado da planilha para construir o sistema.")
