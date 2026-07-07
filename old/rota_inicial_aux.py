import pandas as pd
import streamlit as st
import time
from datetime import datetime
import plotly.express as px
from io import BytesIO
from streamlit_gsheets import GSheetsConnection

# ===========================================
# BLOCO 1: CONFIGURAÇÃO E ESTILOS VISUAIS
# ===========================================
st.set_page_config(
    page_title="Gestão de Ativos TOTALE",
    page_icon="👷",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Paleta de Cores para Cards
TEMAS_CARD = {
    "azul": {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
    "verde": {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
    "amarelo": {"fundo": "#FEF9C3", "texto": "#854D0E", "borda": "#EAB308", "titulo": "#A16207"},
    "cinza": {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
    "vermelho": {"fundo": "#FEF2F2", "texto": "#991B1B", "borda": "#EF4444", "titulo": "#7F1D1D"},
    "roxo": {"fundo": "#FAF5FF", "texto": "#6B21A8", "borda": "#A855F7", "titulo": "#581C87"},
}

def criar_card_metrica(titulo, valor, tema="azul"):
    """Gera HTML para cards de métricas estilizados."""
    cores = TEMAS_CARD.get(tema, TEMAS_CARD["azul"])
    return f"""
    <div style="background-color: {cores['fundo']}; padding: 20px; border-radius: 10px;
        border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 15px;">
        <p style="margin: 0; font-size: 14px; color: {cores['titulo']};"><b>{titulo}</b></p>
        <h2 style="margin: 0; padding-top: 5px; color: {cores['texto']}; font-weight: 900;">{valor}</h2>
    </div>
    """

# ===========================================
# BLOCO 2: CLASSE DE GESTÃO DE DADOS (LÓGICA)
# ===========================================
class GestaoAtivos:
    """Classe estática para centralizar regras de negócio e acesso a dados."""

    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    
    # Lista Expandida de Colunas para Gestão Patrimonial Completa
    COLUNAS_PADRAO = [
        "RE", "Login", "Técnico", "Base", "Monitor", "Situação", 
        "Data_Admissao", "Tipo_Contrato", "Valor_Hora", "Custo_Mensal", 
        "Ultima_Manutencao", "Proxima_Manutencao", "Observacoes", "Ultima_Modificacao"
    ]

    LISTA_SITUACOES = ["ATIVO", "FÉRIAS", "INOPERANTE", "ETN", "DESLIGADO", "AFASTADO", "INATIVO"]
    LISTA_CONTRATOS = ["CLT", "PJ", "ESTÁGIO", "TERCEIRIZADO"]

    @staticmethod
    @st.cache_data(ttl=300)
    def carregar_ativos(url: str) -> pd.DataFrame:
        """
        Carrega dados do Google Sheets com tratamento de erros e padronização.
        """
        try:
            conexao = st.connection("gsheets", type=GSheetsConnection)
            df = conexao.read(spreadsheet=url, ttl=0)
            
            if df.empty:
                return pd.DataFrame(columns=GestaoAtivos.COLUNAS_PADRAO)
            
            # Padroniza nomes das colunas (remove espaços, maiúsculas)
            df.columns = df.columns.str.strip()
            
            # Garante existência de todas as colunas padrão (caso a planilha esteja desatualizada)
            for col in GestaoAtivos.COLUNAS_PADRAO:
                if col not in df.columns:
                    df[col] = "" if col != "Valor_Hora" and col != "Custo_Mensal" else 0.0
            
            return df
        except Exception as e:
            st.error(f"Erro ao conectar com a nuvem: {e}")
            return pd.DataFrame(columns=GestaoAtivos.COLUNAS_PADRAO)

    @staticmethod
    def gerar_log_auditoria(usuario: str, acao: str) -> str:
        """Gera string de auditoria com timestamp."""
        agora = datetime.now().strftime("%d/%m/%Y %H:%M")
        return f"{agora} | {acao} por {usuario.upper()}"

    @staticmethod
    def salvar_no_sheets(df_novo: pd.DataFrame, mensagem: str):
        """Envia dados para o Sheets e força atualização."""
        try:
            conexao = st.connection("gsheets", type=GSheetsConnection)
            conexao.update(spreadsheet=GestaoAtivos.URL_ATIVOS, data=df_novo)
            GestaoAtivos.carregar_ativos.clear()  # Limpa cache
            st.toast(mensagem, icon="✅")
            time.sleep(0.5)
            st.rerun()
        except Exception as erro:
            st.error(f"❌ Erro na gravação: {erro}")

    @staticmethod
    def formatar_moeda(valor):
        """Formata numérico para Real Brasileiro."""
        try:
            return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return "R$ 0,00"

# ===========================================
# BLOCO 3: SEGURANÇA E LOGIN
# ===========================================
if "logado" not in st.session_state:
    st.session_state.logado = False
if "usuario_logado" not in st.session_state:
    st.session_state.usuario_logado = ""

# Credenciais (Secrets ou Fallback)
try:
    USER_CORRETO = st.secrets["credenciais"]["usuario"]
    PWD_CORRETA = st.secrets["credenciais"]["senha"]
except:
    USER_CORRETO = "denis"
    PWD_CORRETA = "admin"

if not st.session_state.logado:
    st.markdown("""<style>[data-testid="collapsedControl"] {display: none}</style>""", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("<h2 style='text-align: center;'>🔐 Acesso TOTALE</h2>", unsafe_allow_html=True)
        with st.form("form_login"):
            usuario = st.text_input("👤 Usuário:")
            senha = st.text_input("🔑 Senha:", type="password")
            if st.form_submit_button("Entrar", use_container_width=True):
                if usuario == USER_CORRETO and senha == PWD_CORRETA:
                    st.session_state.logado = True
                    st.session_state.usuario_logado = usuario
                    st.rerun()
                else:
                    st.error("❌ Credenciais inválidas!")
    st.stop()

# ===========================================
# BLOCO 4: INTERFACE PRINCIPAL
# ===========================================
usuario_atual = st.session_state.usuario_logado

# Sidebar de Controle
with st.sidebar:
    st.markdown(f"👤 **Logado:** `{usuario_atual.upper()}`")
    st.divider()
    if st.button("🔄 Atualizar Dados", use_container_width=True):
        GestaoAtivos.carregar_ativos.clear()
        st.rerun()
    if st.button("🚪 Sair do Sistema", use_container_width=True, type="secondary"):
        st.session_state.logado = False
        st.rerun()
    st.divider()
    st.info("💡 Dica: Use a aba 'Relatórios' para exportar a base completa com custos.")

st.title("📊 Gestão de Ativos e Patrimônio TOTALE")

# Carregamento Inicial
with st.spinner("Sincronizando base de dados..."):
    df_bruto = GestaoAtivos.carregar_ativos(GestaoAtivos.URL_ATIVOS)

if not df_bruto.empty:
    # Listas Dinâmicas para Formulários
    lista_bases = ["Nova Base..."] + sorted(df_bruto["Base"].dropna().astype(str).unique().tolist())
    lista_monitores = ["Novo Monitor..."] + sorted(df_bruto["Monitor"].dropna().astype(str).unique().tolist())

    aba_dash, aba_cad, aba_edit, aba_rel = st.tabs([
        "📈 Dashboard Operacional", 
        "➕ Cadastro de Ativos", 
        "✏️ Manutenção de Registro", 
        "📑 Relatórios Gerenciais"
    ])

    # ===========================================
    # ABA 1: DASHBOARD OPERACIONAL
    # ===========================================
    with aba_dash:
        # Filtros Globais (Exclui Inativos por padrão)
        df_view = df_bruto[df_bruto["Situação"] != "INATIVO"].copy()
        
        c_f1, c_f2, c_f3 = st.columns(3)
        with c_f1:
            filtro_base = st.selectbox("Filtrar por Base", ["Todas"] + sorted(df_view["Base"].unique()))
            if filtro_base != "Todas": df_view = df_view[df_view["Base"] == filtro_base]
        with c_f2:
            filtro_sit = st.selectbox("Filtrar por Situação", ["Todas"] + sorted(df_view["Situação"].unique()))
            if filtro_sit != "Todas": df_view = df_view[df_view["Situação"] == filtro_sit]
        with c_f3:
            filtro_cont = st.selectbox("Tipo de Contrato", ["Todos"] + sorted(df_view["Tipo_Contrato"].unique()))
            if filtro_cont != "Todos": df_view = df_view[df_view["Tipo_Contrato"] == filtro_cont]

        # KPIs Financeiros e Operacionais
        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        total_ativos = len(df_view)
        ativos_operando = len(df_view[df_view["Situação"] == "ATIVO"])
        custo_mensal = df_view["Custo_Mensal"].sum() if "Custo_Mensal" in df_view.columns else 0
        manutencao_pendente = len(df_view[df_view["Proxima_Manutencao"] < str(datetime.now().date())]) if "Proxima_Manutencao" in df_view.columns else 0

        with kpi1: st.markdown(criar_card_metrica("Total Ativos", total_ativos, "cinza"), unsafe_allow_html=True)
        with kpi2: st.markdown(criar_card_metrica("Em Operação", ativos_operando, "verde"), unsafe_allow_html=True)
        with kpi3: st.markdown(criar_card_metrica("Custo Mensal", GestaoAtivos.formatar_moeda(custo_mensal), "vermelho"), unsafe_allow_html=True)
        with kpi4: st.markdown(criar_card_metrica("Manutenção Atrasada", manutencao_pendente, "amarelo"), unsafe_allow_html=True)
        with kpi5: st.markdown(criar_card_metrica("Bases Ativas", df_view["Base"].nunique(), "azul"), unsafe_allow_html=True)

        # Gráficos
        g1, g2 = st.columns([2, 1])
        with g1:
            df_graf_base = df_view.groupby('Base').size().reset_index(name='Qtd').sort_values('Qtd', ascending=False)
            fig_base = px.bar(df_graf_base, x='Base', y='Qtd', title="Distribuição por Base", color='Qtd', color_continuous_scale="Blues")
            st.plotly_chart(fig_base, use_container_width=True)
        with g2:
            df_graf_sit = df_view.groupby('Situação').size().reset_index(name='Qtd')
            fig_sit = px.pie(df_graf_sit, values='Qtd', names='Situação', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig_sit, use_container_width=True)

        st.dataframe(df_view, use_container_width=True, hide_index=True, height=400)

    # ===========================================
    # ABA 2: CADASTRO (COM NOVAS COLUNAS)
    # ===========================================
    with aba_cad:
        st.subheader("📝 Novo Registro de Ativo/Técnico")
        with st.form("form_novo_ativo", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                novo_re = st.text_input("RE *")
                novo_login = st.text_input("Login NETSALES *")
                novo_nome = st.text_input("Nome do Técnico *")
            with c2:
                sel_base = st.selectbox("Base *", lista_bases)
                nova_base_input = st.text_input("Ou Nova Base:", disabled=(sel_base != "Nova Base..."))
                sel_monitor = st.selectbox("Monitor *", lista_monitores)
                novo_monitor_input = st.text_input("Ou Novo Monitor:", disabled=(sel_monitor != "Novo Monitor..."))
            with c3:
                nova_situacao = st.selectbox("Situação *", [s for s in GestaoAtivos.LISTA_SITUACOES if s != "INATIVO"])
                novo_contrato = st.selectbox("Tipo Contrato *", GestaoAtivos.LISTA_CONTRATOS)
                novo_valor_hora = st.number_input("Valor Hora (R$)", min_value=0.0, step=0.50)
                novo_custo = st.number_input("Custo Mensal Estimado (R$)", min_value=0.0, step=50.00)
                data_admissao = st.date_input("Data Admissão", value=datetime.now())

            if st.form_submit_button("💾 Salvar Registro", type="primary"):
                b_final = nova_base_input.strip().upper() if sel_base == "Nova Base..." else sel_base
                m_final = novo_monitor_input.strip().upper() if sel_monitor == "Novo Monitor..." else sel_monitor

                if not novo_re or not novo_login or not novo_nome:
                    st.error("⚠️ Preencha RE, Login e Nome!")
                else:
                    novo_registro = {
                        "RE": novo_re.strip(), "Login": novo_login.strip(), "Técnico": novo_nome.strip().upper(),
                        "Monitor": m_final, "Base": b_final, "Situação": nova_situacao,
                        "Tipo_Contrato": novo_contrato, "Valor_Hora": novo_valor_hora, "Custo_Mensal": novo_custo,
                        "Data_Admissao": data_admissao.strftime("%d/%m/%Y"),
                        "Ultima_Manutencao": "", "Proxima_Manutencao": "", "Observacoes": "",
                        "Ultima_Modificacao": GestaoAtivos.gerar_log_auditoria(usuario_atual, "CRIADO")
                    }
                    df_atualizado = pd.concat([df_bruto, pd.DataFrame([novo_registro])], ignore_index=True)
                    GestaoAtivos.salvar_no_sheets(df_atualizado, "Registro criado com sucesso!")

    # ===========================================
    # ABA 3: EDIÇÃO E MANUTENÇÃO
    # ===========================================
    with aba_edit:
        st.subheader("🔍 Buscar e Editar Registro")
        df_busca = df_bruto[df_bruto["Situação"] != "INATIVO"].copy()
        df_busca["Identificador"] = df_busca["Técnico"].fillna("") + " | RE: " + df_busca["RE"].astype(str)
        
        tecnico_sel = st.selectbox("Selecione o Técnico:", [""] + df_busca["Identificador"].tolist())

        if tecnico_sel != "":
            idx = df_busca[df_busca["Identificador"] == tecnico_sel].index[0]
            dados = df_bruto.loc[idx]

            col_ed, col_ex = st.columns([2, 1])
            with col_ed:
                with st.form("form_editar"):
                    st.markdown("#### ✏️ Dados Cadastrais")
                    ec1, ec2 = st.columns(2)
                    with ec1:
                        st.text_input("RE", value=dados.get("RE", ""), disabled=True)
                        st.text_input("Login", value=dados.get("Login", ""), disabled=True)
                        edit_nome = st.text_input("Técnico", value=dados.get("Técnico", ""))
                        edit_base = st.text_input("Base", value=dados.get("Base", ""))
                    with ec2:
                        edit_monitor = st.text_input("Monitor", value=dados.get("Monitor", ""))
                        edit_situacao = st.selectbox("Situação", GestaoAtivos.LISTA_SITUACOES, index=GestaoAtivos.LISTA_SITUACOES.index(dados.get("Situação", "ATIVO")) if dados.get("Situação") in GestaoAtivos.LISTA_SITUACOES else 0)
                        edit_contrato = st.selectbox("Contrato", GestaoAtivos.LISTA_CONTRATOS, index=GestaoAtivos.LISTA_CONTRATOS.index(dados.get("Tipo_Contrato", "CLT")) if dados.get("Tipo_Contrato") in GestaoAtivos.LISTA_CONTRATOS else 0)
                        edit_custo = st.number_input("Custo Mensal", value=float(dados.get("Custo_Mensal", 0)))
                    
                    st.markdown("#### 🛠️ Controle de Manutenção")
                    em1, em2 = st.columns(2)
                    with em1:
                        edit_ult_man = st.date_input("Última Manutenção", value=None)
                    with em2:
                        edit_prox_man = st.date_input("Próxima Manutenção", value=None)

                    if st.form_submit_button("💾 Atualizar Registro", type="primary"):
                        df_atualizado = df_bruto.copy()
                        df_atualizado.at[idx, "Técnico"] = edit_nome.strip().upper()
                        df_atualizado.at[idx, "Base"] = edit_base.strip().upper()
                        df_atualizado.at[idx, "Monitor"] = edit_monitor.strip().upper()
                        df_atualizado.at[idx, "Situação"] = edit_situacao
                        df_atualizado.at[idx, "Tipo_Contrato"] = edit_contrato
                        df_atualizado.at[idx, "Custo_Mensal"] = edit_custo
                        df_atualizado.at[idx, "Ultima_Manutencao"] = edit_ult_man.strftime("%d/%m/%Y") if edit_ult_man else ""
                        df_atualizado.at[idx, "Proxima_Manutencao"] = edit_prox_man.strftime("%d/%m/%Y") if edit_prox_man else ""
                        df_atualizado.at[idx, "Ultima_Modificacao"] = GestaoAtivos.gerar_log_auditoria(usuario_atual, "EDIÇÃO")
                        GestaoAtivos.salvar_no_sheets(df_atualizado, "Registro atualizado!")

            with col_ex:
                st.markdown("#### 🗑️ Zona de Perigo")
                st.warning("Inativar remove o técnico das listas operacionais, mas mantém o histórico.")
                if st.checkbox(f"Confirmar inativação do RE {dados.get('RE')}"):
                    if st.button("🚨 INATIVAR", type="primary", use_container_width=True):
                        df_atualizado = df_bruto.copy()
                        df_atualizado.at[idx, "Situação"] = "INATIVO"
                        df_atualizado.at[idx, "Ultima_Modificacao"] = GestaoAtivos.gerar_log_auditoria(usuario_atual, "INATIVADO")
                        GestaoAtivos.salvar_no_sheets(df_atualizado, "Técnico inativado.")

    # ===========================================
    # ABA 4: RELATÓRIOS GERENCIAIS
    # ===========================================
    with aba_rel:
        st.subheader("📑 Exportação e Análise de Custos")
        
        # Filtro para relatório
        rel_tipo = st.selectbox("Tipo de Relatório", ["Completo", "Apenas Ativos", "Apenas Inativos", "Manutenção Pendente"])
        
        df_rel = df_bruto.copy()
        if rel_tipo == "Apenas Ativos":
            df_rel = df_rel[df_rel["Situação"] == "ATIVO"]
        elif rel_tipo == "Apenas Inativos":
            df_rel = df_rel[df_rel["Situação"] == "INATIVO"]
        elif rel_tipo == "Manutenção Pendente":
             # Lógica simples de comparação de string de data
            hoje = datetime.now().strftime("%d/%m/%Y")
            df_rel = df_rel[df_rel["Proxima_Manutencao"] < hoje]

        st.dataframe(df_rel, use_container_width=True, height=400)
        
        # Exportação Excel Formatada
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df_rel.to_excel(w, index=False, sheet_name="Relatorio")
        
        st.download_button("📥 Baixar Relatório (Excel)", out.getvalue(), f"relatorio_{rel_tipo}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

else:
    st.warning("⚠️ Planilha vazia ou erro de conexão.")