import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Optional, List


# ====================================================
# BLOCO 1: CONFIGURAÇÕES GLOBAIS
# ====================================================
class Configuracoes:
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
        "laranja": {
            "fundo": "#FFF7ED",
            "texto": "#C2410C",
            "borda": "#F97316",
            "titulo": "#9A3412",
        },
        "cinza": {
            "fundo": "#F8FAFC",
            "texto": "#334155",
            "borda": "#94A3B8",
            "titulo": "#64748B",
        },
        "roxo": {
            "fundo": "#FAF5FF",
            "texto": "#7E22CE",
            "borda": "#A855F7",
            "titulo": "#581C87",
        },
    }


# ====================================================
# BLOCO 2: COMPONENTES VISUAIS (FRONT-END)
# ====================================================
class ComponenteVisual:

    @staticmethod
    def injetar_css():
        """Injeta o CSS necessário para animar e estilizar os tooltips premium."""
        st.markdown(
            """
        <style>
        /* Container principal do card */
        .card-premium {
            position: relative;
            cursor: help; /* Muda a setinha do mouse para interrogação */
        }
        
        /* A caixa preta do tooltip */
        .tooltip-premium {
            visibility: hidden;
            background-color: #1E293B; /* Fundo escuro elegante (Slate 800) */
            color: #F8FAFC; /* Texto branco */
            text-align: center;
            border-radius: 8px;
            padding: 8px 12px;
            position: absolute;
            z-index: 999;
            bottom: 115%; /* Fica acima do card */
            left: 50%;
            transform: translateX(-50%);
            opacity: 0;
            transition: opacity 0.3s ease, bottom 0.3s ease; /* Animação suave */
            font-size: 10px;
            font-weight: 500;
            min-width: 180px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
            pointer-events: none; /* Evita que o tooltip pisque ao passar o mouse nele */
        }

        /* A setinha (triângulo) apontando para baixo */
        .tooltip-premium::after {
            content: "";
            position: absolute;
            top: 100%;
            left: 50%;
            margin-left: -6px;
            border-width: 6px;
            border-style: solid;
            border-color: #1E293B transparent transparent transparent;
        }

        /* O que acontece quando passa o mouse no card */
        .card-premium:hover .tooltip-premium {
            visibility: visible;
            opacity: 1;
            bottom: 105%; /* Efeito de "deslizar para baixo" ao aparecer */
        }
        </style>
        """,
            unsafe_allow_html=True,
        )

    @staticmethod
    def criar_card(
        titulo: str,
        valor: str,
        tema: str = "azul",
        subtitulo: str = "",
        icone: str = "",
        tooltip: str = "",
    ) -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        titulo_formatado = f"{icone} {titulo}" if icone else titulo

        # Cria a div do tooltip apenas se um texto de tooltip for enviado
        html_tooltip = (
            f'<div class="tooltip-premium">{tooltip}</div>' if tooltip else ""
        )

        return f"""
        <div class="card-premium" style="background-color: {cores['fundo']}; padding: 20px; border-radius: 10px; border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.05); height: 100%; display: flex; flex-direction: column; justify-content: center; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
            <p style="margin: 0; font-size: 14px; color: {cores['titulo']}; font-weight: bold;">{titulo_formatado}</p>
            <h2 style="margin: 5px 0 0 0; color: {cores['texto']}; font-weight: 900; font-size: 32px;">{valor}</h2>
            <p style="margin: 5px 0 0 0; font-size: 13px; color: #64748B; font-weight: 500;">{subtitulo}</p>
            {html_tooltip}
        </div>
        """


# ====================================================
# BLOCO 3: FUNÇÕES UTILITÁRIAS
# ====================================================
class Utilitarios:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras_chave: List[str]) -> Optional[str]:
        """Busca genérica de colunas baseada em palavras-chave."""
        cols_upper = {c.upper(): c for c in df.columns}
        for palavra in palavras_chave:
            if palavra in cols_upper:
                return cols_upper[palavra]
        return None

    @staticmethod
    def formatar_numero(valor: float, casas_decimais: int = 2) -> str:
        """Formata número com casas decimais no padrão brasileiro (1.234,56)."""
        if pd.isna(valor):
            return "0" + "," + "0" * casas_decimais
        formatado = f"{valor:,.{casas_decimais}f}"
        return formatado.replace(",", "X").replace(".", ",").replace("X", ".")

    @staticmethod
    def formatar_dataframe_para_download(df: pd.DataFrame) -> bytes:
        """Converte DataFrame para CSV com formato brasileiro (separador ; e decimais ,)."""
        df_export = df.copy()
        for col in df_export.select_dtypes(
            include=["float", "float64", "float32"]
        ).columns:
            df_export[col] = df_export[col].apply(
                lambda x: Utilitarios.formatar_numero(x) if pd.notna(x) else "0,00"
            )
        return df_export.to_csv(index=False, sep=";", encoding="utf-8-sig").encode(
            "utf-8-sig"
        )


# ====================================================
# BLOCO 4: GRÁFICOS E VISUAIS
# ====================================================
class Graficos:
    @staticmethod
    def grafico_combo_raiox(
        df: pd.DataFrame, x_col: str, y_bar: str, y_line: str
    ) -> go.Figure:
        """Gráfico Misto: Barras de OS e Linha de Pontos."""
        fig = go.Figure()

        # Barras de Volume de O.S.
        fig.add_trace(
            go.Bar(
                x=df[x_col],
                y=df[y_bar],
                name="Volume O.S.",
                marker_color="#CBD5E1",
                opacity=0.8,
                hovertemplate="<b>%{x}</b><br>O.S.: %{y}<extra></extra>",
            )
        )

        # Linha de Pontuação
        fig.add_trace(
            go.Scatter(
                x=df[x_col],
                y=df[y_line],
                name="Pontos",
                mode="lines+markers",
                line=dict(color="#0EA5E9", width=3),
                marker=dict(size=8, color="#0284C7"),
                yaxis="y2",
                hovertemplate="<b>%{x}</b><br>Pontos: %{y:.2f}<extra></extra>",
            )
        )

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=50, t=30, b=0),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
            hovermode="x unified",
            yaxis=dict(
                title="Quantidade O.S.", showgrid=True, gridcolor="rgba(0,0,0,0.05)"
            ),
            yaxis2=dict(
                title="Pontos",
                overlaying="y",
                side="right",
                showgrid=False,
                tickformat=".1f",
            ),
            xaxis=dict(showgrid=False),
        )
        return fig


# ====================================================
# BLOCO 5: MOCK DE DADOS (CACHE PARA PERFORMANCE)
# ====================================================
@st.cache_data(show_spinner=False)
def gerar_dados_teste() -> pd.DataFrame:
    """Gera dados falsos para Production caso a sessão esteja vazia."""
    import numpy as np

    datas = pd.date_range(start="2023-10-01", periods=15, freq="D").tolist() * 3
    tecnicos = ["JOAO SILVA", "MARIA SOUZA", "CARLOS ALBERTO"] * 15

    return pd.DataFrame(
        {
            "Data": datas,
            "Técnico": tecnicos,
            "Supervisor": ["SUP A", "SUP B", "SUP A"] * 15,
            "Base": ["SÃO PAULO", "SÃO PAULO", "CAMPINAS"] * 15,
            "Pontos": np.random.uniform(10.5, 50.8, size=45),
            "Status": ["CONCLUÍDO"] * 45,
        }
    )


@st.cache_data(show_spinner=False)
def preparar_base_cache(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara e limpa a base de dados (executado apenas uma vez na memória)."""
    df = df.copy()

    if "Pontos" in df.columns:
        df["Pontos"] = pd.to_numeric(df["Pontos"], errors="coerce").fillna(0.0)

    return df


# ====================================================
# BLOCO 6: INICIALIZAÇÃO E TRATAMENTO DE BASES
# ====================================================
st.set_page_config(page_title="Raio-X do Técnico", page_icon="🔍", layout="wide")

st.title("🔍 Raio-X: Desempenho Operacional")
st.markdown(
    "Auditoria detalhada de **Execução Física** (O.S. e Pontuação) por técnico/equipe."
)

# Carregamento Seguro da Base de Produção
df_prod = pd.DataFrame()

if "dados_prod" in st.session_state:
    try:
        p1 = st.session_state["dados_prod"].get("Prod", pd.DataFrame())
        p2 = st.session_state["dados_prod"].get("Gpon", pd.DataFrame())
        if not p1.empty and not p2.empty:
            df_prod = pd.concat([p1, p2], ignore_index=True)
        elif not p1.empty:
            df_prod = p1.copy()
        elif not p2.empty:
            df_prod = p2.copy()
    except Exception:
        pass

if df_prod.empty:
    st.warning("⚠️ Base de Produção não encontrada. Carregando dados de demonstração.")
    df_prod = gerar_dados_teste()

# 🔥 APLICA O CACHE DE PREPARAÇÃO
df_prod = preparar_base_cache(df_prod)

# Identificação de colunas (genérico para qualquer nome deplanilha)
col_tec = Utilitarios.buscar_coluna(
    df_prod, ["TÉCNICO", "TECNICO", "VENDEDOR", "NOME EQUIPE", "NOME", "LOGIN"]
)
col_sup = Utilitarios.buscar_coluna(
    df_prod, ["SUPERVISOR", "MONITOR", "GESTOR", "COORDENADOR", "LÍDER", "LIDER"]
)
col_base = Utilitarios.buscar_coluna(
    df_prod, ["BASE", "PROJETO", "CIDADE", "FILIAL", "LOCALIDADE"]
)
col_data = Utilitarios.buscar_coluna(
    df_prod, ["DATA", "DATA AGENDAMENTO", "DATA CONCLUSÃO", "DATA_EXECUCAO", "DATE"]
)

if not col_tec:
    st.error(
        "❌ Não foi possível encontrar a coluna de Técnico/Equipe na base de dados."
    )
    st.stop()

# Limpeza do nome do Técnico antes dos filtros
df_prod[col_tec] = df_prod[col_tec].astype(str).str.strip().str.upper()

# Preparação segura da coluna de data (se existir)
if col_data:
    df_prod[col_data] = pd.to_datetime(df_prod[col_data], errors="coerce").dt.date

# ====================================================
# BLOCO 7: MOTOR DE BUSCA EM CASCATA COM FILTRO DE DATAS
# ====================================================
with st.container(border=True):
    st.markdown("#### 🎯 Localizar Técnico/Equipe")

    # 🔥 NOVO: Layout com 3 colunas incluindo Filtro de Período
    f_data, f_base, f_sup = st.columns([1.5, 1, 1])
    mask = pd.Series(True, index=df_prod.index)

    # 1. Filtro de Período de Datas
    with f_data:
        if col_data and not df_prod[col_data].dropna().empty:
            min_date = df_prod[col_data].min()
            max_date = df_prod[col_data].max()

            datas_selecionadas = st.date_input(
                "📅 Período:",
                [min_date, max_date],
                min_value=min_date,
                max_value=max_date,
                format="DD/MM/YYYY",
            )

            if len(datas_selecionadas) == 2:
                mask &= (df_prod[col_data] >= datas_selecionadas[0]) & (
                    df_prod[col_data] <= datas_selecionadas[1]
                )
        else:
            st.info("📅 Sem coluna de data")

    # 2. Filtro de Base
    with f_base:
        if col_base:
            bases = ["Todas"] + sorted(
                [
                    str(b)
                    for b in df_prod.loc[mask, col_base].dropna().unique()
                    if str(b).strip() != ""
                ]
            )
            base_sel = st.selectbox("📍 Base:", bases)
            if base_sel != "Todas":
                mask &= df_prod[col_base] == base_sel
        else:
            base_sel = "Todas"

    # 3. Filtro de Supervisor
    with f_sup:
        if col_sup:
            supervisores = ["Todos"] + sorted(
                [
                    str(s)
                    for s in df_prod.loc[mask, col_sup].dropna().unique()
                    if str(s).strip() != ""
                ]
            )
            sup_sel = st.selectbox("👤 Supervisor:", supervisores)
            if sup_sel != "Todos":
                mask &= df_prod[col_sup] == sup_sel
        else:
            sup_sel = "Todos"

    st.divider()

    # 🔥 PROTEÇÃO: Verifica se há técnicos após os filtros
    tecnicos_filtrados = sorted(
        [t for t in df_prod.loc[mask, col_tec].unique() if t and t != "NAN"]
    )

    if not tecnicos_filtrados:
        st.warning(
            "⚠️ Nenhum técnico encontrado para o período/base/supervisor selecionados."
        )
        st.stop()

    col_busca, col_info = st.columns([1, 2], gap="large")

    with col_busca:
        tec_selecionado = st.selectbox(
            "🔎 Selecione a Equipe/Técnico:", options=[""] + tecnicos_filtrados
        )

    df_tec_prod = pd.DataFrame()
    if tec_selecionado:
        # 🔥 USA A MÁSCARA PARA FILTRAR JÁ PELO PERÍODO SELECIONADO
        df_tec_prod = df_prod[(df_prod[col_tec] == tec_selecionado) & mask].copy()

        # Usa .mode() para pegar o valor mais frequente (protege contra trocas de supervisor)
        sup_tec = (
            df_tec_prod[col_sup].mode()[0]
            if col_sup and not df_tec_prod[col_sup].empty
            else "Não Atribuído"
        )
        base_tec = (
            df_tec_prod[col_base].mode()[0]
            if col_base and not df_tec_prod[col_base].empty
            else "Não Atribuída"
        )

        with col_info:
            st.markdown("<br>", unsafe_allow_html=True)
            st.info(
                f"**👤 Supervisor:** {sup_tec} ㅤ|ㅤ **📍 Projeto/Base:** {base_tec}"
            )

# ====================================================
# BLOCO 8: RENDERIZAÇÃO DO RELATÓRIO OPERACIONAL
# ====================================================
if tec_selecionado and not df_tec_prod.empty:
    st.divider()

    if "Pontos" not in df_tec_prod.columns:
        st.error("Coluna 'Pontos' não encontrada na base de dados.")
        st.stop()

    t_pontos = df_tec_prod["Pontos"].sum()
    t_os = len(df_tec_prod)
    pontos_por_os = (t_pontos / t_os) if t_os > 0 else 0.0
    media_pontos = df_tec_prod["Pontos"].mean()

    # 1. CARDS DE KPI
    st.markdown(f"### ⚙️ Execução Física de **{tec_selecionado}**")
    kr1, kr2, kr3, kr4 = st.columns(4)

    with kr1:
        st.markdown(
            ComponenteVisual.criar_card(
                "O.S. Realizadas",
                str(t_os),
                "cinza",
                "Total de visitas executadas",
                "📋",
                # tooltip="Quantidade total de Ordens de Serviço executadas no período selecionado",
            ),
            unsafe_allow_html=True,
        )

    with kr2:
        st.markdown(
            ComponenteVisual.criar_card(
                "Pontuação Total",
                Utilitarios.formatar_numero(t_pontos),
                "azul",
                "Soma dos pontos",
                "🎯",
                # tooltip="Soma de toda a pontuação acumulada no período",
            ),
            unsafe_allow_html=True,
        )

    with kr3:
        st.markdown(
            ComponenteVisual.criar_card(
                "Ticket Médio",
                Utilitarios.formatar_numero(pontos_por_os),
                "roxo",
                "Pts médio por O.S.",
                "🔌",
                # tooltip="Média de pontos por cada Ordem de Serviço executada",
            ),
            unsafe_allow_html=True,
        )

    with kr4:
        st.markdown(
            ComponenteVisual.criar_card(
                "Média por O.S.",
                Utilitarios.formatar_numero(media_pontos),
                "verde",
                "Pontos por visita",
                "📊",
                # tooltip="Média aritmética de pontos por visita executada",
            ),
            unsafe_allow_html=True,
        )

    st.write("---")

    # 2. GRÁFICO DE PRODUÇÃO
    if col_data:
        st.markdown("#### 📊 Evolução Diária (Volume vs Qualidade)")

        df_grafico = df_tec_prod.dropna(subset=[col_data]).copy()

        if not df_grafico.empty:
            df_tempo_prod = (
                df_grafico.groupby(col_data)
                .agg(Pontos=("Pontos", "sum"), Qtd_OS=("Pontos", "count"))
                .reset_index()
            )

            # 🔥 UI LIMPA: Remove a barra de ferramentas do Plotly
            st.plotly_chart(
                Graficos.grafico_combo_raiox(
                    df_tempo_prod, col_data, "Qtd_OS", "Pontos"
                ),
                use_container_width=True,
                config={"displayModeBar": False},
            )
        else:
            st.info("⚠️ Nenhuma data válida encontrada para exibir o gráfico.")
    else:
        st.info("⚠️ Coluna de data não disponível para plotar o gráfico.")

    st.write("---")

    # 3. TABELA DE EXTRATO OPERACIONAL
    st.markdown("#### 🧾 Extrato Operacional Detalhado")

    # Colunas a ignorar na exibição
    col_ignorar = {
        "lat",
        "lon",
        "latitude",
        "longitude",
        "Posição",
        "Cidade",
        "Unnamed: 0",
    }
    colunas_exibir = [c for c in df_tec_prod.columns if c not in col_ignorar]

    # Preparação do DataFrame para exibição
    df_exibir = df_tec_prod[colunas_exibir].copy()

    if col_data:
        df_exibir = df_exibir.sort_values(by=col_data, ascending=False)

    # Configuração das colunas da tabela
    config_colunas = {}

    if "Pontos" in df_exibir.columns:
        max_pontos = float(df_exibir["Pontos"].max()) if not df_exibir.empty else 100.0
        config_colunas["Pontos"] = st.column_config.NumberColumn(
            "🎯 Pontos", format="%.2f", help="Pontuação obtida nesta O.S."
        )

    if col_data and col_data in df_exibir.columns:
        config_colunas[col_data] = st.column_config.DateColumn(
            "📅 Data", format="DD/MM/YYYY", help="Data de execução da O.S."
        )

    if col_tec and col_tec in df_exibir.columns:
        config_colunas[col_tec] = st.column_config.TextColumn(
            "👤 Técnico", help="Nome do técnico responsável"
        )

    if col_sup and col_sup in df_exibir.columns:
        config_colunas[col_sup] = st.column_config.TextColumn("👔 Supervisor")

    if col_base and col_base in df_exibir.columns:
        config_colunas[col_base] = st.column_config.TextColumn("📍 Base/Projeto")

    st.dataframe(
        df_exibir,
        use_container_width=True,
        hide_index=True,
        column_config=config_colunas,
    )

    # 🔥 BOTÃO DE DOWNLOAD (Exportação para Excel/CSV)
    if not df_exibir.empty:
        csv_bytes = Utilitarios.formatar_dataframe_para_download(df_exibir)

        st.download_button(
            label="📥 Baixar Extrato Operacional",
            data=csv_bytes,
            file_name=f"extrato_operacional_{tec_selecionado.replace(' ', '_')}.csv",
            mime="text/csv",
            type="primary",
        )

        # Métricas rápidas de resumo
        col_met1, col_met2, col_met3 = st.columns(3)
        with col_met1:
            st.metric(
                "📅 Período",
                (
                    f"{df_exibir[col_data].min()} até {df_exibir[col_data].max()}"
                    if col_data
                    else "N/A"
                ),
            )
        with col_met2:
            st.metric(
                "🏆 Maior Pontuação",
                Utilitarios.formatar_numero(df_exibir["Pontos"].max()),
            )
        with col_met3:
            st.metric(
                "📉 Menor Pontuação",
                Utilitarios.formatar_numero(df_exibir["Pontos"].min()),
            )
