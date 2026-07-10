import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from streamlit_gsheets import GSheetsConnection
from typing import Optional, Tuple, Dict, Any
from io import BytesIO

# ====================================================
# CONFIGURAÇÕES GLOBAIS E ESTILOS
# ====================================================
st.set_page_config(
    page_title="Gestão de Quebra de Agenda", page_icon="📊", layout="wide"
)


class Configuracoes:
    SLA_QUEBRA_MAXIMA: float = 0.20  # 20%
    URL_ATIVOS: str = (
        "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    )

    TEMAS_CARD: Dict[str, Dict[str, str]] = {
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
        "laranja": {
            "fundo": "#FFF7ED",
            "texto": "#C2410C",
            "borda": "#F97316",
            "titulo": "#9A3412",
        },
        "roxo": {
            "fundo": "#FAF5FF",
            "texto": "#7E22CE",
            "borda": "#A855F7",
            "titulo": "#581C87",
        },
        "vermelho": {
            "fundo": "#FEF2F2",
            "texto": "#B91C1C",
            "borda": "#EF4444",
            "titulo": "#991B1B",
        },
        "cinza": {
            "fundo": "#F8FAFC",
            "texto": "#334155",
            "borda": "#94A3B8",
            "titulo": "#64748B",
        },
    }


# ====================================================
# UTILITÁRIOS E COMPONENTES VISUAIS
# ====================================================
class Utilitarios:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras_chave: list) -> Optional[str]:
        if df is None or df.empty:
            return None
        cols_upper = {c.upper(): c for c in df.columns}
        for p in palavras_chave:
            if p.upper() in cols_upper:
                return cols_upper[p.upper()]
        return None

    @staticmethod
    def classificar_os_series(status_series: pd.Series) -> pd.Series:
        s = status_series.fillna("").astype(str).str.strip().str.upper()
        executada = s == "EXECUTADA"
        nao_exec = s.isin(["NÃO EXECUTADA", "NAO EXECUTADA"])

        return pd.Series(
            np.select(
                [executada, nao_exec],
                ["Executada", "Não Executada"],
                default="Pendente",
            ),
            index=status_series.index,
        )


class ComponenteVisual:
    @staticmethod
    def criar_card(
        titulo: str, valor: str, tema: str = "azul", subtitulo: str = ""
    ) -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        return f"""
        <div style="
            background-color: {cores['fundo']}; 
            padding: 16px; 
            border-radius: 10px; 
            border-left: 6px solid {cores['borda']}; 
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
            margin-bottom: 12px;
            min-height: 110px;
            display: flex;
            flex-direction: column;
            justify-content: center;
        ">
            <p style="margin: 0; font-size: 11px; color: {cores['titulo']}; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">{titulo}</p>
            <h2 style="margin: 4px 0; color: {cores['texto']}; font-weight: 900; font-size: 26px; line-height: 1.1;">{valor}</h2>
            <p style="margin: 0; font-size: 11px; color: #64748B; font-weight: 500;">{subtitulo}</p>
        </div>
        """


# ====================================================
# CAMADA DE DADOS E PROCESSAMENTO
# ====================================================
class DadosManager:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo_bytes(file_bytes: bytes, filename: str) -> pd.DataFrame:
        try:
            name = filename.lower()
            bio = BytesIO(file_bytes)
            if name.endswith(".csv"):
                return pd.read_csv(bio, sep=None, engine="python", encoding="utf-8")
            if name.endswith((".xlsx", ".xls")):
                return pd.read_excel(bio, engine="openpyxl")
            return pd.DataFrame()
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_gsheets() -> pd.DataFrame:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            df_gs = conn.read(spreadsheet=Configuracoes.URL_ATIVOS)
            if df_gs is None or df_gs.empty:
                return pd.DataFrame()

            df_gs.columns = df_gs.columns.astype(str).str.strip().str.upper()
            col_log = Utilitarios.buscar_coluna(
                df_gs, ["LOGIN", "ID", "MATRÍCULA", "MATRICULA"]
            )
            col_tec = Utilitarios.buscar_coluna(df_gs, ["TÉCNICO", "NOME"])
            col_mon = Utilitarios.buscar_coluna(df_gs, ["MONITOR", "GESTOR"])

            rename = {}
            if col_log:
                rename[col_log] = "LOGIN"
            if col_tec:
                rename[col_tec] = "TÉCNICO"
            if col_mon:
                rename[col_mon] = "MONITOR"

            df_gs = df_gs.rename(columns=rename)
            keep = [c for c in ["LOGIN", "TÉCNICO", "MONITOR"] if c in df_gs.columns]
            df_gs = df_gs[keep].copy()

            if "LOGIN" in df_gs.columns:
                df_gs["LOGIN"] = (
                    df_gs["LOGIN"]
                    .astype(str)
                    .str.replace(".0", "", regex=False)
                    .str.strip()
                    .str.upper()
                )
                df_gs = df_gs.drop_duplicates(subset=["LOGIN"], keep="last")

            return df_gs
        except Exception as e:
            st.warning(
                f"Não foi possível sincronizar com o Google Sheets ({e}). Usando dados locais."
            )
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(show_spinner=False)
    def preparar_base(df: pd.DataFrame, df_gsheets: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.astype(str).str.strip().str.upper()

        excluir_suspensos = Utilitarios.buscar_coluna(df, ["STATUS DA ATIVIDADE"])

        if excluir_suspensos:
            status_limpo = (
                df[excluir_suspensos].fillna("").astype(str).str.strip().str.upper()
            )
            # Identifica linhas contendo variações de SUSPENSO
            mascara_suspensos = status_limpo.str.contains(
                "SUSPENSO|SUSPENSA|SUSPENSE|SUSP", regex=True, na=False
            )

            # Registra no log do Streamlit a remoção para transparência operacional
            qtd_removidos = int(mascara_suspensos.sum())
            if qtd_removidos > 0:
                st.toast(
                    f"ℹ️ {qtd_removidos} ordens suspensas foram removidas da análise.",
                    icon="🗑️",
                )

            # Remove as linhas suspensas da base principal
            df = df[~mascara_suspensos].copy()

        if "TOTAL DE TAREFAS" not in df.columns:
            df["TOTAL DE TAREFAS"] = 0
        df["TOTAL DE TAREFAS"] = pd.to_numeric(
            df["TOTAL DE TAREFAS"], errors="coerce"
        ).fillna(0)

        if "CONTRATO" in df.columns:
            df = df.dropna(subset=["CONTRATO"])

        # Identificação de Regras de Serviços
        tipo_os = (
            df.get("TIPO DE O.S 1", df.get("TIPO O.S 1", pd.Series("", index=df.index)))
            .astype(str)
            .str.upper()
        )
        hab_trab = (
            df.get("HABILIDADE DE TRABALHO", pd.Series("", index=df.index))
            .astype(str)
            .str.upper()
        )

        df["Check_GPON"] = hab_trab.str.contains(r"PON\(1/100\)", regex=True, na=False)
        df["Check_ND"] = tipo_os.str.contains("ADESAO", na=False)
        df["Check_Migracao"] = (tipo_os.str.contains("MUDANCA DE PACOTE", na=False)) & (
            df["Check_GPON"] == True
        )
        df["Check_PME"] = hab_trab.str.contains("PME", na=False)

        # Higienização de login e junção da hierarquia
        col_login = Utilitarios.buscar_coluna(
            df,
            [
                "LOGIN",
                "LOGIN DO TÉCNICO",
                "USUÁRIO",
                "USUARIO",
                "MATRÍCULA",
                "MATRICULA",
            ],
        )

        if (
            col_login
            and df_gsheets is not None
            and not df_gsheets.empty
            and "LOGIN" in df_gsheets.columns
        ):
            df[col_login] = (
                df[col_login]
                .astype(str)
                .str.replace(".0", "", regex=False)
                .str.strip()
                .str.upper()
            )
            df_gsheets2 = df_gsheets[["LOGIN", "TÉCNICO", "MONITOR"]].drop_duplicates(
                "LOGIN", keep="last"
            )

            for c in ["TÉCNICO", "MONITOR"]:
                if c in df.columns:
                    df = df.drop(columns=[c])

            df = df.merge(df_gsheets2, left_on=col_login, right_on="LOGIN", how="left")

        df["TÉCNICO"] = df.get(
            "TÉCNICO", pd.Series("NÃO MAPEADO", index=df.index)
        ).fillna("NÃO MAPEADO")
        df["MONITOR"] = df.get(
            "MONITOR", pd.Series("SEM MONITOR", index=df.index)
        ).fillna("SEM MONITOR")

        return df


# ====================================================
# MOTORES METRICOS (CÁLCULOS FINANCEIROS/SLA)
# ====================================================
class MotorCalculo:
    @staticmethod
    def calcular_quebra_atual(df_alvo: pd.DataFrame) -> Tuple[float, float]:
        if df_alvo is None or df_alvo.empty:
            return 0.0, 0.0
        exec_ = float(
            df_alvo.loc[
                df_alvo["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"
            ].sum()
        )
        naoexec = float(
            df_alvo.loc[
                df_alvo["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"
            ].sum()
        )
        considerado = exec_ + naoexec
        taxa = (naoexec / considerado) if considerado > 0 else 0.0
        return considerado, taxa

    @staticmethod
    def projetar_fechamento(
        df_alvo: pd.DataFrame, p_pendente: float
    ) -> Dict[str, float]:
        if df_alvo is None or df_alvo.empty:
            return {
                "alocado": 0.0,
                "exec": 0.0,
                "naoexec": 0.0,
                "pend": 0.0,
                "quebra_atual": 0.0,
                "fechamento_proj": 0.0,
                "naoexec_proj": 0.0,
            }

        alocado = float(df_alvo["TOTAL DE TAREFAS"].sum())
        exec_ = float(
            df_alvo.loc[
                df_alvo["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"
            ].sum()
        )
        naoexec = float(
            df_alvo.loc[
                df_alvo["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"
            ].sum()
        )
        pend = max(0.0, alocado - exec_ - naoexec)

        _, quebra_atual = MotorCalculo.calcular_quebra_atual(df_alvo)
        naoexec_proj = naoexec + (pend * float(p_pendente))
        fechamento_proj = (naoexec_proj / alocado) if alocado > 0 else 0.0

        return {
            "alocado": alocado,
            "exec": exec_,
            "naoexec": naoexec,
            "pend": pend,
            "quebra_atual": quebra_atual,
            "fechamento_proj": fechamento_proj,
            "naoexec_proj": naoexec_proj,
        }

    @staticmethod
    def folga_sla_fechamento(df_alvo: pd.DataFrame, sla: float) -> Dict[str, Any]:
        if df_alvo is None or df_alvo.empty:
            return {
                "alocado": 0.0,
                "exec": 0.0,
                "naoexec": 0.0,
                "pend": 0.0,
                "limite_ne_total": 0.0,
                "folga_ne_pendente": 0.0,
                "folga_pct_pendente": 0.0,
                "precisa_executar_pendente": 0.0,
                "estourado": False,
            }

        alocado = float(df_alvo["TOTAL DE TAREFAS"].sum())
        exec_ = float(
            df_alvo.loc[
                df_alvo["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"
            ].sum()
        )
        naoexec = float(
            df_alvo.loc[
                df_alvo["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"
            ].sum()
        )
        pend = max(0.0, alocado - exec_ - naoexec)

        limite_ne_total = sla * alocado
        folga_total = limite_ne_total - naoexec
        estourado = folga_total < 0

        folga_ne_pendente = max(0.0, min(pend, folga_total))
        folga_pct_pendente = (folga_ne_pendente / pend) if pend > 0 else 0.0
        precisa_executar_pendente = max(0.0, pend - folga_ne_pendente)

        return {
            "alocado": alocado,
            "exec": exec_,
            "naoexec": naoexec,
            "pend": pend,
            "limite_ne_total": limite_ne_total,
            "folga_ne_pendente": folga_ne_pendente,
            "folga_pct_pendente": folga_pct_pendente,
            "precisa_executar_pendente": precisa_executar_pendente,
            "estourado": estourado,
        }

    @staticmethod
    def gerar_tabela_cenarios(
        df: pd.DataFrame,
        grupo: str,
        p_ot: float,
        p_base: float,
        p_pess: float,
        min_alocado: float = 5,
    ) -> pd.DataFrame:
        if (
            df is None
            or df.empty
            or grupo not in df.columns
            or "Status Contrato" not in df.columns
        ):
            return pd.DataFrame()

        pv = pd.pivot_table(
            df,
            index=grupo,
            columns="Status Contrato",
            values="TOTAL DE TAREFAS",
            aggfunc="sum",
            fill_value=0,
        )

        for c in ["Executada", "Não Executada", "Pendente"]:
            if c not in pv.columns:
                pv[c] = 0.0

        out = pv.reset_index().copy()
        out["Executada"] = out["Executada"].astype(float)
        out["Não Executada"] = out["Não Executada"].astype(float)
        out["Pendente"] = out["Pendente"].astype(float)
        out["Considerado"] = out["Executada"] + out["Não Executada"]
        out["Alocado"] = out["Considerado"] + out["Pendente"]

        out["Quebra Atual"] = np.where(
            out["Considerado"] > 0, out["Não Executada"] / out["Considerado"], 0.0
        )
        out["Fechamento Otimista"] = np.where(
            out["Alocado"] > 0,
            (out["Não Executada"] + out["Pendente"] * p_ot) / out["Alocado"],
            0.0,
        )
        out["Fechamento Base"] = np.where(
            out["Alocado"] > 0,
            (out["Não Executada"] + out["Pendente"] * p_base) / out["Alocado"],
            0.0,
        )
        out["Fechamento Pessimista"] = np.where(
            out["Alocado"] > 0,
            (out["Não Executada"] + out["Pendente"] * p_pess) / out["Alocado"],
            0.0,
        )

        out = out[out["Alocado"] >= float(min_alocado)].copy()
        return out.sort_values("Fechamento Base", ascending=False)


# ====================================================
# ESTADO DE SESSÃO E CARGA DE ARQUIVOS
# ====================================================
if "df_memoria" not in st.session_state:
    st.session_state["df_memoria"] = None

st.title("🗣️ Painel Executivo: Quebra de Agenda")

# Fluxo de Upload
if st.session_state["df_memoria"] is None:
    st.subheader("Importação de Dados")
    arquivo = st.file_uploader(
        "📥 Envie a base de dados operacional (Excel ou CSV)",
        type=["xlsx", "xls", "csv"],
    )
    if arquivo:
        with st.spinner(
            "Analisando dados e cruzando hierarquias de técnicos/monitores..."
        ):
            df_base = DadosManager.ler_arquivo_bytes(arquivo.getvalue(), arquivo.name)
            df_gs = DadosManager.buscar_gsheets()
            st.session_state["df_memoria"] = DadosManager.preparar_base(df_base, df_gs)
        st.rerun()

# Fluxo com Dados Carregados
else:
    df_full = st.session_state["df_memoria"]

    # Barra superior de controle rápido
    col_aviso, col_btn = st.columns([5, 1.2])
    with col_aviso:
        st.success("✅ Base ativa processada!")
    with col_btn:
        if st.button(
            "🔄 Substituir Base de Dados", use_container_width=True, type="secondary"
        ):
            st.session_state["df_memoria"] = None
            st.rerun()

    # Mapeamento dinâmico de colunas essenciais
    col_status = Utilitarios.buscar_coluna(
        df_full, ["STATUS DA O.S 1", "STATUS OS", "STATUS"]
    )
    col_cod_baixa = Utilitarios.buscar_coluna(
        df_full,
        ["CÓD DE BAIXA 1", "COD DE BAIXA 1", "CÓDIGO DE BAIXA 1", "CODIGO DE BAIXA 1"],
    )

    if not col_status:
        st.error(
            "⚠️ Coluna identificadora de 'Status' não encontrada na planilha carregada."
        )
        st.stop()

    df_full["Status Contrato"] = Utilitarios.classificar_os_series(df_full[col_status])

    # ====================================================
    # SIDEBAR DE CONFIGURAÇÃO DE CENÁRIOS E FILTROS
    # ====================================================
    with st.sidebar:
        st.header("🎯 Painel de Filtros")

        # Alerta de órfãos (logins ausentes no GSheets)
        qtd_orfaos = (
            int((df_full["TÉCNICO"] == "NÃO MAPEADO").sum())
            if "TÉCNICO" in df_full.columns
            else 0
        )
        if qtd_orfaos > 0:
            st.warning(f"⚠️ {qtd_orfaos} logins não estão mapeados no Google Sheets.")

        df_filtrado = df_full.copy()

        # Filtros de Hierarquia
        for col, titulo in [
            ("MONITOR", "👔 Filtrar por Monitor"),
            ("TÉCNICO", "👤 Filtrar por Técnico"),
        ]:
            if col in df_filtrado.columns:
                ignorar = {"nan", "SEM MONITOR", "NÃO MAPEADO"}
                opcoes = ["Todos"] + sorted(
                    [str(x) for x in df_filtrado[col].unique() if str(x) not in ignorar]
                )
                selecao = st.selectbox(titulo, opcoes)
                if selecao != "Todos":
                    df_filtrado = df_filtrado[df_filtrado[col] == selecao]

        st.divider()
        st.subheader("🔮 Probabilidade de Quebra (Pendente → Não Executada)")
        p_ot = (
            st.slider(
                "Cenário Otimista",
                0,
                100,
                10,
                5,
                help="Percentual dos pendentes que virarão quebra",
            )
            / 100
        )
        p_base = (
            st.slider(
                "Cenário Base", 0, 100, 30, 5, help="Comportamento médio esperado"
            )
            / 100
        )
        p_pess = (
            st.slider(
                "Cenário Pessimista",
                0,
                100,
                60,
                5,
                help="Caso ocorra cenário severo de quebra",
            )
            / 100
        )

        st.divider()
        st.subheader("⚙️ Parâmetros de Rankings")
        min_alocado_rank = st.number_input(
            "Mínimo de OS alocadas (Filtro)", min_value=1, value=5, step=1
        )
        top_n = st.number_input("Visualizar Top N", min_value=5, value=10, step=1)

    # DataFrame de Trabalho
    df = df_filtrado.copy()

    # Cálculo Central de Métricas Gerais
    cen_geral = {
        "Otimista": MotorCalculo.projetar_fechamento(df, p_ot),
        "Base": MotorCalculo.projetar_fechamento(df, p_base),
        "Pessimista": MotorCalculo.projetar_fechamento(df, p_pess),
    }

    m_base = cen_geral["Base"]
    atual = m_base["quebra_atual"]
    fech_base = m_base["fechamento_proj"]
    pendentes_vol = m_base["pend"]

    # ====================================================
    # RENDERIZAÇÃO DE KPIs GLOBAIS
    # ====================================================
    st.write("")
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        st.markdown(
            ComponenteVisual.criar_card(
                "Alocado Geral", f"{m_base['alocado']:,.0f}", "azul", "Vol. Total Rota"
            ),
            unsafe_allow_html=True,
        )
    with k2:
        st.markdown(
            ComponenteVisual.criar_card(
                "Executadas", f"{m_base['exec']:,.0f}", "verde", "Baixadas com sucesso"
            ),
            unsafe_allow_html=True,
        )
    with k3:
        st.markdown(
            ComponenteVisual.criar_card(
                "Não Executadas",
                f"{m_base['naoexec']:,.0f}",
                "laranja",
                "Quebras registradas",
            ),
            unsafe_allow_html=True,
        )
    with k4:
        st.markdown(
            ComponenteVisual.criar_card(
                "Pendentes", f"{pendentes_vol:,.0f}", "cinza", "OS ainda abertas"
            ),
            unsafe_allow_html=True,
        )
    with k5:
        st.markdown(
            ComponenteVisual.criar_card(
                "Quebra Atual", f"{atual:.2%}", "cinza", "Fórmula: NE / (E + NE)"
            ),
            unsafe_allow_html=True,
        )
    with k6:
        cor_sla = "vermelho" if fech_base > Configuracoes.SLA_QUEBRA_MAXIMA else "roxo"
        st.markdown(
            ComponenteVisual.criar_card(
                "Fechamento (Base)",
                f"{fech_base:.2%}",
                cor_sla,
                f"Meta de SLA: {Configuracoes.SLA_QUEBRA_MAXIMA:.0%}",
            ),
            unsafe_allow_html=True,
        )

    # ====================================================
    # INTERFACE PRINCIPAL POR ABAS (ORGANIZAÇÃO E FLUXO)
    # ====================================================
    aba_visao, aba_rankings, aba_causa, aba_acoes = st.tabs(
        [
            "📊 Visão Geral & Projeções",
            "🧭 Desempenho & Rankings",
            "🔍 Causa Raiz & Códigos",
            "🚨 Fila de Tratamento & Dados",
        ]
    )

    # ----------------------------------------------------
    # TAB 1: VISÃO GERAL & PROJEÇÕES
    # ----------------------------------------------------
    with aba_visao:
        st.markdown("### 🔮 Análise e Simulações de SLA para Fechamento")

        c_cards, c_grafico = st.columns([3, 2.5])

        with c_cards:
            st.caption("Projeção do % Final de Quebra conforme conversão de pendentes")
            o1, o2, o3 = st.columns(3)

            with o1:
                tx_ot = cen_geral["Otimista"]["fechamento_proj"]
                tema_ot = (
                    "vermelho" if tx_ot > Configuracoes.SLA_QUEBRA_MAXIMA else "cinza"
                )
                st.markdown(
                    ComponenteVisual.criar_card(
                        "Projeção Otimista",
                        f"{tx_ot:.2%}",
                        tema_ot,
                        f"Vol. final NE: {cen_geral['Otimista']['naoexec_proj']:,.0f}",
                    ),
                    unsafe_allow_html=True,
                )
            with o2:
                tx_ba = cen_geral["Base"]["fechamento_proj"]
                tema_ba = (
                    "vermelho" if tx_ba > Configuracoes.SLA_QUEBRA_MAXIMA else "roxo"
                )
                st.markdown(
                    ComponenteVisual.criar_card(
                        "Projeção Base",
                        f"{tx_ba:.2%}",
                        tema_ba,
                        f"Vol. final NE: {cen_geral['Base']['naoexec_proj']:,.0f}",
                    ),
                    unsafe_allow_html=True,
                )
            with o3:
                tx_pe = cen_geral["Pessimista"]["fechamento_proj"]
                tema_pe = (
                    "vermelho" if tx_pe > Configuracoes.SLA_QUEBRA_MAXIMA else "cinza"
                )
                st.markdown(
                    ComponenteVisual.criar_card(
                        "Projeção Pessimista",
                        f"{tx_pe:.2%}",
                        tema_pe,
                        f"Vol. final NE: {cen_geral['Pessimista']['naoexec_proj']:,.0f}",
                    ),
                    unsafe_allow_html=True,
                )

            # Bloco informativo de Folga de SLA
            st.write("---")
            folga = MotorCalculo.folga_sla_fechamento(
                df, Configuracoes.SLA_QUEBRA_MAXIMA
            )

            cc1, cc2 = st.columns(2)
            with cc1:
                tema_folga = (
                    "vermelho"
                    if folga["estourado"]
                    else ("verde" if folga["folga_ne_pendente"] > 0 else "laranja")
                )
                st.markdown(
                    ComponenteVisual.criar_card(
                        "Folga no SLA (Qtd OS)",
                        f"{np.floor(folga['folga_ne_pendente']):,.0f}",
                        tema_folga,
                        f"Pendente limite aceitável: {folga['folga_pct_pendente']:.1%}",
                    ),
                    unsafe_allow_html=True,
                )
            with cc2:
                st.markdown(
                    ComponenteVisual.criar_card(
                        "Garantia Mínima de Execução",
                        f"{np.ceil(folga['precisa_executar_pendente']):,.0f}",
                        "azul",
                        "Qtd mínima dos pendentes que deve ser executada",
                    ),
                    unsafe_allow_html=True,
                )

            st.caption("Capacidade de absorção de quebras no cenário pendente")
            st.progress(min(1.0, max(0.0, float(folga["folga_pct_pendente"]))))

            if folga["estourado"]:
                st.error(
                    f"❌ SLA já estourado! Limite ultrapassado em {abs(folga['naoexec'] - folga['limite_ne_total']):,.1f} OS."
                )

        with c_grafico:
            # Histograma comparativo de cenários
            df_plot = pd.DataFrame(
                {
                    "Cenário": ["Otimista", "Base", "Pessimista"],
                    "Fechamento": [tx_ot, tx_ba, tx_pe],
                }
            )
            fig = px.bar(
                df_plot,
                x="Cenário",
                y="Fechamento",
                text=df_plot["Fechamento"].map(lambda x: f"{x:.2%}"),
                color="Fechamento",
                color_continuous_scale="Purples",
                title="Cenários Projetados de Quebra de Agenda",
            )
            fig.add_hline(
                y=Configuracoes.SLA_QUEBRA_MAXIMA,
                line_width=2,
                line_dash="dash",
                line_color="red",
                annotation_text="Meta Max SLA",
            )
            fig.update_layout(
                yaxis_tickformat=".0%",
                coloraxis_showscale=False,
                height=340,
                margin=dict(t=40, b=10, l=10, r=10),
            )
            st.plotly_chart(
                fig, use_container_width=True, config={"displayModeBar": False}
            )

        # Projeção por tipos específicos de serviços
        st.write("---")
        st.markdown("### 📊 Performance e Fechamento por Linha de Serviço")

        servicos = {
            "ND (Adesão)": df[df.get("Check_ND", False) == True],
            "Migração": df[df.get("Check_Migracao", False) == True],
            "Tecnologia GPON": df[df.get("Check_GPON", False) == True],
            "Cliente PME": df[df.get("Check_PME", False) == True],
        }

        rows_svc = []
        for nome, dfx in servicos.items():
            if dfx.empty:
                continue
            cs = {
                "Otimista": MotorCalculo.projetar_fechamento(dfx, p_ot),
                "Base": MotorCalculo.projetar_fechamento(dfx, p_base),
                "Pessimista": MotorCalculo.projetar_fechamento(dfx, p_pess),
            }
            vol_cons, tx_at = MotorCalculo.calcular_quebra_atual(dfx)
            rows_svc.append(
                {
                    "Serviço": nome,
                    "Otimista": float(cs["Otimista"]["fechamento_proj"]),
                    "Base": float(cs["Base"]["fechamento_proj"]),
                    "Pessimista": float(cs["Pessimista"]["fechamento_proj"]),
                    "Atual": float(tx_at),
                    "Volume": float(vol_cons),
                }
            )

        if not rows_svc:
            st.info(
                "Volume de amostragem insuficiente para análises segmentadas por serviços."
            )
        else:
            df_svc = pd.DataFrame(rows_svc)

            # Cards Rápidos por Serviço (Projeção Base)
            cols_svc = st.columns(min(4, len(df_svc)))
            for idx, r in enumerate(df_svc.to_dict("records")):
                if idx >= len(cols_svc):
                    break
                with cols_svc[idx]:
                    tema_s = (
                        "vermelho"
                        if r["Base"] > Configuracoes.SLA_QUEBRA_MAXIMA
                        else "cinza"
                    )
                    st.markdown(
                        ComponenteVisual.criar_card(
                            r["Serviço"],
                            f"{r['Base']:.2%}",
                            tema_s,
                            f"Atual: {r['Atual']:.2%} | Vol: {r['Volume']:,.0f}",
                        ),
                        unsafe_allow_html=True,
                    )

            # Gráfico de barras horizontal por serviço
            df_svc = df_svc.sort_values("Base", ascending=True)
            fig_svc = go.Figure()
            fig_svc.add_trace(
                go.Bar(
                    y=df_svc["Serviço"],
                    x=df_svc["Base"],
                    orientation="h",
                    text=df_svc["Base"].map(lambda x: f"{x:.2%}"),
                    textposition="outside",
                    marker_color="#4F46E5",
                    error_x=dict(
                        type="data",
                        symmetric=False,
                        array=(df_svc["Pessimista"] - df_svc["Base"]),
                        arrayminus=(df_svc["Base"] - df_svc["Otimista"]),
                    ),
                )
            )
            fig_svc.add_vline(
                x=Configuracoes.SLA_QUEBRA_MAXIMA,
                line_width=2,
                line_dash="dash",
                line_color="red",
            )
            fig_svc.update_layout(
                xaxis_tickformat=".0%", height=280, margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(
                fig_svc, use_container_width=True, config={"displayModeBar": False}
            )

    # ----------------------------------------------------
    # TAB 2: DESEMPENHO & RANKINGS
    # ----------------------------------------------------
    with aba_rankings:
        st.markdown("### 🧭 Desempenho Crítico por Grupos")

        t_mon, t_tec = st.tabs(["👔 Ranking de Monitores", "👤 Ranking de Técnicos"])

        def render_estrutura_ranking(df_rank: pd.DataFrame, grupo_label: str):
            if df_rank.empty:
                st.info(
                    "Não há dados elegíveis para o ranking sob os filtros estabelecidos."
                )
                return

            df_rank_limitado = df_rank.head(int(top_n)).copy()

            # Efetuar multiplicação por 100 para exibição
            df_rank_disp = df_rank_limitado.copy()
            colunas_pct = [
                "Quebra Atual",
                "Fechamento Otimista",
                "Fechamento Base",
                "Fechamento Pessimista",
            ]
            for col in colunas_pct:
                if col in df_rank_disp.columns:
                    df_rank_disp[col] = df_rank_disp[col] * 100

            st.dataframe(
                df_rank_disp[
                    [
                        grupo_label,
                        "Alocado",
                        "Pendente",
                        "Quebra Atual",
                        "Fechamento Otimista",
                        "Fechamento Base",
                        "Fechamento Pessimista",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Quebra Atual": st.column_config.ProgressColumn(
                        "Quebra Atual",
                        min_value=0,
                        max_value=100,
                        format="%.2f%%",
                    ),
                    "Fechamento Otimista": st.column_config.ProgressColumn(
                        "Fech. Otimista", min_value=0, max_value=100, format="%.2f%%"
                    ),
                    "Fechamento Base": st.column_config.ProgressColumn(
                        "Fech. Base", min_value=0, max_value=100, format="%.2f%%"
                    ),
                    "Fechamento Pessimista": st.column_config.ProgressColumn(
                        "Fech. Pessimista", min_value=0, max_value=100, format="%.2f%%"
                    ),
                },
            )

            # Prospecção Gráfica
            df_g_plot = df_rank_limitado.sort_values("Fechamento Base", ascending=True)
            fig_r = go.Figure()
            fig_r.add_trace(
                go.Bar(
                    y=df_g_plot[grupo_label],
                    x=df_g_plot["Fechamento Base"],
                    orientation="h",
                    marker_color="#8B5CF6",
                    text=df_g_plot["Fechamento Base"].map(lambda x: f"{x:.2%}"),
                    textposition="outside",
                    error_x=dict(
                        type="data",
                        symmetric=False,
                        array=(
                            df_g_plot["Fechamento Pessimista"]
                            - df_g_plot["Fechamento Base"]
                        ),
                        arrayminus=(
                            df_g_plot["Fechamento Base"]
                            - df_g_plot["Fechamento Otimista"]
                        ),
                    ),
                )
            )
            fig_r.add_vline(
                x=Configuracoes.SLA_QUEBRA_MAXIMA,
                line_width=2,
                line_dash="dash",
                line_color="red",
            )
            fig_r.update_layout(
                xaxis_tickformat=".0%", height=380, margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(
                fig_r, use_container_width=True, config={"displayModeBar": False}
            )

        with t_mon:
            if "MONITOR" in df.columns:
                rk_mon = MotorCalculo.gerar_tabela_cenarios(
                    df, "MONITOR", p_ot, p_base, p_pess, float(min_alocado_rank)
                )
                render_estrutura_ranking(rk_mon, "MONITOR")
            else:
                st.warning("Indicador hierárquico 'MONITOR' indisponível.")

        with t_tec:
            if "TÉCNICO" in df.columns:
                rk_tec = MotorCalculo.gerar_tabela_cenarios(
                    df, "TÉCNICO", p_ot, p_base, p_pess, float(min_alocado_rank)
                )
                render_estrutura_ranking(rk_tec, "TÉCNICO")
            else:
                st.warning("Indicador individual 'TÉCNICO' indisponível.")

    # ----------------------------------------------------
    # TAB 3: CAUSA RAIZ & CÓDIGOS (ORGANIZADO)
    # ----------------------------------------------------
    with aba_causa:
        st.markdown("### 🔍 Diagnóstico e Ofensores Principais")

        ca1, ca2, ca3 = st.columns([1.2, 1.5, 1.5])

        with ca1:
            st.markdown("#### 📉 Distribuição Operacional")
            df_dist = (
                df.groupby("Status Contrato")["TOTAL DE TAREFAS"].sum().reset_index()
            )
            fig_pie = px.pie(
                df_dist,
                names="Status Contrato",
                values="TOTAL DE TAREFAS",
                hole=0.5,
                color="Status Contrato",
                color_discrete_map={
                    "Executada": "#10B981",
                    "Não Executada": "#EF4444",
                    "Pendente": "#94A3B8",
                },
            )
            fig_pie.update_layout(
                legend=dict(orientation="h", y=-0.1),
                margin=dict(t=10, b=10, l=10, r=10),
                height=300,
            )
            st.plotly_chart(
                fig_pie, use_container_width=True, config={"displayModeBar": False}
            )

        with ca2:
            st.markdown("#### 🔎 Top Motivos (Não Executada)")
            if col_cod_baixa and col_cod_baixa in df.columns:
                df_cod_baixa = (
                    df[df["Status Contrato"] == "Não Executada"]
                    .groupby(col_cod_baixa)["TOTAL DE TAREFAS"]
                    .sum()
                    .reset_index()
                )
                df_cod_baixa = df_cod_baixa.sort_values(
                    "TOTAL DE TAREFAS", ascending=False
                ).head(5)

                if not df_cod_baixa.empty:
                    fig_mot = px.bar(
                        df_cod_baixa,
                        x="TOTAL DE TAREFAS",
                        y=col_cod_baixa,
                        orientation="h",
                        color_discrete_sequence=["#EF4444"],
                        text="TOTAL DE TAREFAS",
                    )
                    fig_mot.update_layout(
                        yaxis={"categoryorder": "total ascending"},
                        margin=dict(t=10, b=10, l=5, r=5),
                        height=300,
                        xaxis_title="",
                        yaxis_title="",
                    )
                    st.plotly_chart(
                        fig_mot,
                        use_container_width=True,
                        config={"displayModeBar": False},
                    )
                else:
                    st.info("Nenhum motivo de 'Não Executada' registrado.")
            else:
                st.info("Coluna de motivos de baixa indisponível.")

        with ca3:
            st.markdown("#### 👔 Maiores Quebras por Monitor")
            if "MONITOR" in df.columns:
                p_mon = pd.crosstab(
                    df["MONITOR"],
                    df["Status Contrato"],
                    values=df["TOTAL DE TAREFAS"],
                    aggfunc="sum",
                ).fillna(0)
                if "Não Executada" in p_mon.columns:
                    if "Executada" not in p_mon.columns:
                        p_mon["Executada"] = 0.0
                    p_mon["Considerado"] = p_mon["Executada"] + p_mon["Não Executada"]
                    p_mon["% Quebra Atual"] = np.where(
                        p_mon["Considerado"] > 0,
                        p_mon["Não Executada"] / p_mon["Considerado"],
                        0.0,
                    )

                    rk_mon_at = (
                        p_mon[p_mon["Considerado"] >= 5]
                        .sort_values("% Quebra Atual", ascending=False)
                        .head(5)
                        .reset_index()
                    )

                    # Cópia para exibição multiplicada por 100
                    rk_mon_at_disp = rk_mon_at.copy()
                    rk_mon_at_disp["% Quebra Atual"] = (
                        rk_mon_at_disp["% Quebra Atual"] * 100
                    )

                    st.dataframe(
                        rk_mon_at_disp[["MONITOR", "Não Executada", "% Quebra Atual"]],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "% Quebra Atual": st.column_config.ProgressColumn(
                                "Tx Atual", min_value=0, max_value=100, format="%.2f%%"
                            )
                        },
                    )
                else:
                    st.info("Sem quebras mapeadas para o grupo hierárquico.")

        # --- SEÇÃO DO CÓDIGO DE BAIXA (Mapeada com segurança dentro dos dados de trabalho) ---
        st.write("---")
        st.markdown("### 🧾 Códigos Ofensores Principais")

        if not col_cod_baixa or col_cod_baixa not in df.columns:
            st.info(
                "A coluna mapeada para 'CÓD DE BAIXA 1' não foi encontrada neste arquivo."
            )
        else:
            df_cb = df.copy()
            df_cb[col_cod_baixa] = (
                df_cb[col_cod_baixa].fillna("SEM CÓDIGO").astype(str).str.strip()
            )

            pv_cb = pd.pivot_table(
                df_cb,
                index=col_cod_baixa,
                columns="Status Contrato",
                values="TOTAL DE TAREFAS",
                aggfunc="sum",
                fill_value=0,
            )
            for c in ["Executada", "Não Executada", "Pendente"]:
                if c not in pv_cb.columns:
                    pv_cb[c] = 0.0

            tab_cb = (
                pv_cb.reset_index().rename(columns={col_cod_baixa: "Cód. Baixa"}).copy()
            )
            for c in ["Executada", "Não Executada", "Pendente"]:
                tab_cb[c] = pd.to_numeric(tab_cb[c], errors="coerce").fillna(0.0)

            tab_cb["Considerado"] = tab_cb["Executada"] + tab_cb["Não Executada"]
            tab_cb["Quebra Atual"] = np.where(
                tab_cb["Considerado"] > 0,
                tab_cb["Não Executada"] / tab_cb["Considerado"],
                0.0,
            )

            total_ne_global = float(tab_cb["Não Executada"].sum())
            tab_cb["% do Total NE"] = np.where(
                total_ne_global > 0, tab_cb["Não Executada"] / total_ne_global, 0.0
            )

            cx1, cx2 = st.columns(2)
            with cx1:
                min_cons_cod = st.number_input(
                    "Mínimo de amostragem (OS Consideradas)",
                    min_value=1,
                    value=5,
                    key="min_cons_cod",
                )
            with cx2:
                topn_cod = st.number_input(
                    "Mostrar Top N Códigos", min_value=5, value=10, key="topn_cod"
                )

            tab_cb_filtrada = tab_cb[
                tab_cb["Considerado"] >= float(min_cons_cod)
            ].copy()

            col_esq, = st.columns(1)

            with col_esq:
                st.markdown("#### 🔥 Maiores por Volume Real")
                v_mostra = tab_cb_filtrada.sort_values(
                    "Não Executada", ascending=False
                ).head(int(topn_cod))

                # Transforma para escala 0-100 na exibição
                v_mostra_disp = v_mostra.copy()
                v_mostra_disp["Quebra Atual"] = v_mostra_disp["Quebra Atual"] * 100
                v_mostra_disp["% do Total NE"] = v_mostra_disp["% do Total NE"] * 100

                st.dataframe(
                    v_mostra_disp[
                        [
                            "Cód. Baixa",
                            "Não Executada",
                            "% do Total NE",
                            "Considerado",
                        ]
                    ],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "% do Total NE": st.column_config.ProgressColumn(
                            "% Representativo",
                            min_value=0,
                            max_value=100,
                            format="%.2f%%",
                        ),
                    },
                )

    # ----------------------------------------------------
    # TAB 4: FILA DE TRATAMENTO & DADOS (BACKOFFICE)
    # ----------------------------------------------------
    with aba_acoes:
        st.markdown("### 🚨 Painel Operacional e Fila de Tratamento")

        f_tratamento, f_base = st.tabs(
            ["📋 Fila de Ação Crítica", "📂 Base Geral de Dados"]
        )

        with f_tratamento:
            df_back = df[df["Status Contrato"] == "Não Executada"].copy()
            if not df_back.empty:
                cols_visualizacao = [
                    c
                    for c in [
                        "CONTRATO",
                        "TÉCNICO",
                        "MONITOR",
                        col_cod_baixa,
                        "TOTAL DE TAREFAS",
                    ]
                    if c and c in df_back.columns
                ]
                st.dataframe(
                    df_back[cols_visualizacao] if cols_visualizacao else df_back,
                    use_container_width=True,
                    hide_index=True,
                )

                # Exportação
                csv_fila = df_back.to_csv(index=False, sep=";", encoding="utf-8-sig")
                st.download_button(
                    "📥 Exportar Fila para CSV",
                    data=csv_fila,
                    file_name="fila_tratamento_backoffice.csv",
                    mime="text/csv",
                )
            else:
                st.success(
                    "🎉 Ótimo! Nenhuma quebra para tratamento operacional no momento."
                )

        with f_base:
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "STATUS DA ATIVIDADE": st.column_config.TextColumn(width="large")
                },
            )
            csv_completo = df.to_csv(index=False, sep=";", encoding="utf-8-sig")
            st.download_button(
                "📥 Baixar Base Higienizada e Cruzada",
                data=csv_completo,
                file_name="base_higienizada_quebra.csv",
                mime="text/csv",
            )