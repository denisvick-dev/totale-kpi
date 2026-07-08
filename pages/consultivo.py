# VERSÃO REFATORADA, CORRIGIDA E COM NOVOS RELATÓRIOS GERENCIAIS
import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.graph_objects import Figure
from io import BytesIO
from typing import Any, Optional, Literal, cast
from streamlit_gsheets import GSheetsConnection

# ====================================================
# BLOCO 1: CONFIGURAÇÕES GLOBAIS
# ====================================================

class Configuracoes:
    """Configurações globais e paleta de cores do sistema."""
    
    temas_card = {
        "amarelo":  {"fundo": "#FEF9C3", "texto": "#854D0E", "borda": "#EAB308", "titulo": "#A16207"},
        "azul":     {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
        "verde":    {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
        "roxo":     {"fundo": "#FAF5FF", "texto": "#7E22CE", "borda": "#A855F7", "titulo": "#6B21A8"},
        "cinza":    {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
        "escuro":   {"fundo": "#1E293B", "texto": "#FFFFFF", "borda": "#475569", "titulo": "#E2E8F0"},
        "vermelho": {"fundo": "#FEF2F2", "texto": "#B91C1C", "borda": "#EF4444", "titulo": "#991B1B"}, 
    }
    
    cores_grafico = ["#0EA5E9", "#22C55E", "#A855F7", "#F97316", "#EF4444", "#3B82F6"]
    
    pagina = {
        "titulo": "📋 Total de Consultivos",
        "icon": "📋"
    }
    
    url_ativos = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"


# ====================================================
# BLOCO 2: COMPONENTES VISUAIS
# ====================================================

class ComponenteVisual:
    """Componentes visuais HTML/CSS customizados."""
    
    @staticmethod
    def criar_card(titulo: str, valor: str, tema: str = "azul", delta: Optional[str] = None) -> str:
        cores = Configuracoes.temas_card.get(tema, Configuracoes.temas_card["azul"])
        
        delta_html = ""
        if delta:
            if delta.startswith("+") or delta.startswith("▲"):
                cor_delta, simbolo = "#22c55e", "▲"
            elif delta.startswith("-") or delta.startswith("▼"):
                cor_delta, simbolo = "#ef4444", "▼"
            elif "do Total" in delta: 
                cor_delta, simbolo = "#0ea5e9", "◴"
            else:
                cor_delta, simbolo = "#94a3b8", "■"
            
            delta_html = f'<span style="font-size: 13px; color: {cor_delta}; margin-left: 10px;">{simbolo} {delta}</span>'
        
        return f"""
        <div style="
            background-color: {cores['fundo']}; padding: 20px; border-radius: 10px;
            border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.1); 
            margin-bottom: 10px; transition: transform 0.2s;
        " onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
            <p style="margin: 0; font-size: 13px; color: {cores['titulo']};"><b>{titulo}</b></p>
            <h2 style="margin: 5px 0 0 0; color: {cores['texto']}; font-weight: 900; font-size: 28px;">
                {valor}{delta_html}
            </h2>
        </div>
        """
    
    @staticmethod
    def exibir_ticker(dados: list) -> str:
        if not dados: return ""
        html_itens = ""
        for item in dados:
            if item.get("variacao") == "positiva":
                cor, simbolo = "#22c55e", "▲"
            elif item.get("variacao") == "negativa":
                cor, simbolo = "#ef4444", "▼"
            elif item.get("variacao") == "share": 
                cor, simbolo = "#38bdf8", "◴"
            else:
                cor, simbolo = "#94a3b8", "■"
            
            html_itens += f'<span style="margin: 0 40px; font-family: \'Roboto\', sans-serif; font-size: 15px; white-space: nowrap;"><span style="color: #94a3b8; font-weight: 500;">{item.get("label", "")}:</span><span style="font-weight: 700; color: #FFFFFF; margin-left: 8px;">{item.get("valor", "")}</span><span style="color: {cor}; font-weight: 700; margin-left: 6px; font-size: 13px;">{simbolo} {item.get("delta", "")}</span></span><span style="color: #334155; margin: 0 15px;">|</span>'
        
        return f"""<style>
.ticker-wrapper {{ width: 100%; overflow: hidden; background: linear-gradient(90deg, #0f172a 0%, #1e293b 50%, #0f172a 100%); padding: 12px 0; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); margin-bottom: 25px; position: relative; }}
.ticker-wrapper::before, .ticker-wrapper::after {{ content: ''; position: absolute; top: 0; bottom: 0; width: 60px; z-index: 2; }}
.ticker-wrapper::before {{ left: 0; background: linear-gradient(90deg, #0f172a, transparent); }}
.ticker-wrapper::after {{ right: 0; background: linear-gradient(90deg, transparent, #0f172a); }}
.ticker-content {{ display: flex; width: max-content; animation: scroll 35s linear infinite; }}
.ticker-wrapper:hover .ticker-content {{ animation-play-state: paused; }}
@keyframes scroll {{ 0% {{ transform: translate3d(0, 0, 0); }} 100% {{ transform: translate3d(-50%, 0, 0); }} }}
</style>
<div class="ticker-wrapper"><div class="ticker-content">{html_itens}{html_itens}</div></div>"""


# ====================================================
# BLOCO 3: FUNÇÕES MATEMÁTICAS E DE FORMATAÇÃO
# ====================================================

class Utilitarios:
    
    @staticmethod
    def calcular_variacao(valor_filtrado: float, valor_geral: float) -> tuple:
        if valor_geral == 0 or pd.isna(valor_geral): return "neutra", "0%"
        if abs(valor_filtrado - valor_geral) < 0.0001: return "neutra", "Visão Geral"
            
        percentual = ((valor_filtrado - valor_geral) / valor_geral) * 100
        if percentual > 0: return "positiva", f"+{percentual:.1f}%"
        elif percentual < 0: return "negativa", f"{percentual:.1f}%"
        return "neutra", "0%"
    
    @staticmethod
    def calcular_share(valor_filtrado: float, valor_geral: float) -> tuple:
        if valor_geral == 0 or pd.isna(valor_geral): return "neutra", "0%"
        if abs(valor_filtrado - valor_geral) < 0.0001: return "neutra", "Visão Geral"
            
        share = (valor_filtrado / valor_geral) * 100
        return "share", f"{share:.1f}% do Total"
    
    @staticmethod
    def formatar_numero(valor: int) -> str:
        return f"{int(valor):,}".replace(",", ".")
    
    @staticmethod
    def colorir_celula(valor) -> str:
        return "background-color: #F8FAFC; font-weight: bold; color: #334155"


# ====================================================
# BLOCO 4: PROCESSAMENTO DE DADOS E GRÁFICOS
# ====================================================

class ProcessamentoDados:
    
    @staticmethod
    @st.cache_data(ttl=300)
    def carregar_ativos(url: str) -> pd.DataFrame:
        conexao = st.connection("gsheets", type=GSheetsConnection)
        df_ativos = conexao.read(spreadsheet=url, ttl=0)
        df_ativos.columns = df_ativos.columns.str.strip()
        return df_ativos

    @staticmethod
    def limpar_strings(df: pd.DataFrame, colunas: list) -> pd.DataFrame:
        for col in colunas:
            if col in df.columns:
                df[col] = df[col].astype(str).str.strip()
        return df
    
    @staticmethod
    def preparar_ranking(df: pd.DataFrame, colunas_grupo: list, coluna_ordenacao: str) -> pd.DataFrame:
        colunas_soma = ["Qtde. Cons.", "Qtde. Prod.", "Qtde. Mesh", "Qtde. TV", "Qtde. Virtua"]
        colunas_soma = [col for col in colunas_soma if col in df.columns]
        
        resultado = df.groupby(colunas_grupo, dropna=False)[colunas_soma].sum().reset_index().sort_values(coluna_ordenacao, ascending=False)
        resultado.insert(0, "Posição", range(1, len(resultado) + 1))
        
        renomeios = {"Qtde. Cons.": "Total Consultivos", "Qtde. Prod.": "Total Produtos", "Qtde. Mesh": "Mesh", "Qtde. TV": "TV Box", "Qtde. Virtua": "Virtua"}
        resultado = resultado.rename(columns=renomeios)
        
        col_ints = [renomeios.get(c, c) for c in colunas_soma] + ["Posição"]
        resultado[col_ints] = resultado[col_ints].fillna(0).astype(int)
        
        return resultado

class Graficos:
    
    @staticmethod
    def grafico_barras(df: pd.DataFrame, x: str, y: str) -> Figure:
        fig = px.bar(df, x=x, y=y, text_auto=True, color=y, color_continuous_scale="Oryel")
        fig.update_layout(
            showlegend=False, plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Roboto"), xaxis=dict(showgrid=False, title=""), yaxis=dict(showgrid=True, gridcolor="rgba(0,0,0,0.1)", title="")
        )
        fig.update_traces(textposition="outside", textfont_size=12, textfont_color="#334155")
        return fig
    
    @staticmethod
    def grafico_pizza(df: pd.DataFrame, names: str, values: str, tipo: str = "pizza") -> Figure:
        hole_size = 0.4 if tipo == "rosca" else 0
        fig = px.pie(df, names=names, values=values, hole=hole_size, color_discrete_sequence=Configuracoes.cores_grafico)
        fig.update_layout(font=dict(family="Roboto"), paper_bgcolor="rgba(0,0,0,0)")
        if tipo == "rosca":
            fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
        return fig

    @staticmethod
    def grafico_evolucao_temporal(df: pd.DataFrame) -> Figure:
        df_tempo = df.groupby(df['DATA'].dt.date)[['Qtde. Cons.', 'Qtde. Prod.']].sum().reset_index()
        fig = px.line(df_tempo, x='DATA', y=['Qtde. Cons.', 'Qtde. Prod.'], 
                      labels={'value': 'Quantidade', 'variable': 'Métrica'},
                      markers=True, color_discrete_sequence=['#0EA5E9', '#22C55E'])
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                          legend_title_text='', hovermode="x unified", title="Evolução de Consultivos vs Produtos Fechados")
        return fig

    @staticmethod
    def grafico_mix_produtos(df: pd.DataFrame) -> Figure:
        df_mix = df.groupby('Monitor')[['Qtde. Mesh', 'Qtde. TV', 'Qtde. Virtua']].sum().reset_index()
        fig = px.bar(df_mix, x='Monitor', y=['Qtde. Mesh', 'Qtde. TV', 'Qtde. Virtua'],
                     title="Mix de Produtos Vendidos por Monitor",
                     labels={'value': 'Quantidade', 'variable': 'Produto'},
                     color_discrete_sequence=['#A855F7', '#F97316', '#3B82F6'])
        fig.update_layout(barmode='stack', plot_bgcolor="rgba(0,0,0,0)")
        return fig

    @staticmethod
    def grafico_dispersao_eficiencia(df_ranking: pd.DataFrame) -> Figure:
        df_disp = df_ranking[df_ranking['Total Consultivos'] > 0]
        fig = px.scatter(df_disp, x='Total Consultivos', y='Total Produtos', 
                         color='Monitor', hover_name='VENDEDOR',
                         size='Total Produtos', size_max=20,
                         title="Matriz de Eficiência (Consultivos x Vendas)")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        return fig

    @staticmethod
    def grafico_heatmap_semana(df: pd.DataFrame) -> Figure:
        df_heat = df.copy()
        dias_map = {0: '1-Seg', 1: '2-Ter', 2: '3-Qua', 3: '4-Qui', 4: '5-Sex', 5: '6-Sáb', 6: '7-Dom'}
        df_heat['Dia da Semana'] = df_heat['DATA'].dt.dayofweek.map(dias_map)
        
        df_resumo = df_heat.groupby(['Base', 'Dia da Semana'])['Qtde. Cons.'].sum().reset_index()
        fig = px.density_heatmap(df_resumo, x='Dia da Semana', y='Base', z='Qtde. Cons.', 
                                 color_continuous_scale="Blues", title="Mapa de Calor de Oportunidades (Base x Dia)")
        fig.update_layout(plot_bgcolor="rgba(0,0,0,0)")
        return fig


# ====================================================
# BLOCO 5: INÍCIO DA PÁGINA E PREPARAÇÃO DOS DADOS
# ====================================================
st.set_page_config(page_title=Configuracoes.pagina["titulo"], page_icon=Configuracoes.pagina["icon"], layout=cast(Literal["wide"], "wide"))
st.title(Configuracoes.pagina["titulo"])

if "dados_cons" not in st.session_state or "Consultivo" not in st.session_state["dados_cons"]:
    st.warning("⚠️ Carregue os dados na aba principal primeiro.")
    st.stop()

df = st.session_state["dados_cons"]["Consultivo"].copy()

mapa_colunas = {
    "QTDE_CONSULTIVO": "Qtde. Cons.", "QTDE_PRODUTOS": "Qtde. Prod.",
    "QTDE_MESH": "Qtde. Mesh", "QTDE_TV": "Qtde. TV", "QTDE_VIRTUA": "Qtde. Virtua",
}
for origem, destino in mapa_colunas.items():
    if origem in df.columns:
        df[destino] = pd.to_numeric(df[origem], errors="coerce").fillna(0).astype(int)
    else:
        df[destino] = 0

if "DATA" in df.columns:
    df["DATA"] = pd.to_datetime(df["DATA"], errors="coerce", dayfirst=True)


# ====================================================
# BLOCO 6: INTEGRAÇÃO COM GOOGLE SHEETS
# ====================================================
try:
    df_ativos = ProcessamentoDados.carregar_ativos(Configuracoes.url_ativos)
except Exception as erro:
    st.error(f"❌ Falha ao conectar com as planilhas: {erro}")
    st.stop()

df = ProcessamentoDados.limpar_strings(df, ["LOGIN NETSALES"])
df_ativos = ProcessamentoDados.limpar_strings(df_ativos, ["Login", "Técnico", "Monitor", "Base"])

df_ativos_subset = df_ativos[["Login", "Técnico", "Monitor", "Base"]].drop_duplicates(subset=["Login"])
df = df.drop(columns=["Monitor", "Base"], errors="ignore")

df = pd.merge(df, df_ativos_subset, left_on="LOGIN NETSALES", right_on="Login", how="outer")

df["LOGIN NETSALES"] = df["LOGIN NETSALES"].fillna(df["Login"]).fillna("SEM LOGIN")

if "VENDEDOR" in df.columns:
    df["VENDEDOR"] = df["VENDEDOR"].fillna(df["Técnico"]).fillna(df["LOGIN NETSALES"]).fillna("Nome Não Cadastrado")
else:
    df["VENDEDOR"] = df.get("Técnico", pd.Series(dtype=str)).fillna(df["LOGIN NETSALES"]).fillna("Nome Não Cadastrado")

df["Monitor"] = df["Monitor"].fillna("Não Identificado")
df["Base"] = df["Base"].fillna("Não Identificada")

colunas_metricas = ["Qtde. Cons.", "Qtde. Prod.", "Qtde. Mesh", "Qtde. TV", "Qtde. Virtua"]
for col in colunas_metricas:
    if col in df.columns:
        df[col] = df[col].fillna(0)


# ====================================================
# BLOCO 7: CÁLCULO DOS INDICADORES GLOBAIS
# ====================================================
total_geral_cons = int(df["Qtde. Cons."].sum())
total_geral_prod = int(df["Qtde. Prod."].sum())
total_geral_mesh = int(df["Qtde. Mesh"].sum())
total_geral_tv = int(df["Qtde. TV"].sum())
total_geral_virtua = int(df["Qtde. Virtua"].sum())

eq_cons_geral = df.groupby("LOGIN NETSALES")["Qtde. Cons."].sum()
total_equipes_geral = eq_cons_geral.shape[0]
eq_ativas_geral = eq_cons_geral[eq_cons_geral > 0].shape[0]
eq_zeradas_geral = total_equipes_geral - eq_ativas_geral

total_efic_geral = (eq_ativas_geral / total_equipes_geral) if total_equipes_geral > 0 else 0


# ====================================================
# BLOCO 8: FILTROS GLOBAIS (SIDEBAR)
# ====================================================
st.sidebar.header("🎯 Filtros Avançados")

base_sel = st.sidebar.selectbox("Filtrar por Base:", ["Todas"] + sorted(df["Base"].dropna().unique().tolist()))

if base_sel != "Todas":
    df_temp = df[df["Base"] == base_sel]
    monitor_sel = st.sidebar.selectbox("Filtrar por Monitor:", ["Todos"] + sorted(df_temp["Monitor"].dropna().unique().tolist()))
else:
    monitor_sel = st.sidebar.selectbox("Filtrar por Monitor:", ["Todos"] + sorted(df["Monitor"].dropna().unique().tolist()))

intervalo_datas = None
if "DATA" in df.columns:
    datas_validas = df["DATA"].dropna()
    if not datas_validas.empty:
        intervalo_datas = st.sidebar.date_input(
            "Selecione o período (Apenas para Oportunidades com Data):", 
            value=(datas_validas.min().date(), datas_validas.max().date()),
            min_value=datas_validas.min().date(), 
            max_value=datas_validas.max().date(), 
            format="DD/MM/YYYY"
        )

if st.sidebar.button("🔄 Limpar Filtros"):
    st.rerun()

if base_sel != "Todas": 
    df = df[df["Base"] == base_sel]
if monitor_sel != "Todos": 
    df = df[df["Monitor"] == monitor_sel]
if intervalo_datas and isinstance(intervalo_datas, tuple) and len(intervalo_datas) == 2:
    df = df[(df["DATA"].isnull()) | ((df["DATA"].dt.date >= intervalo_datas[0]) & (df["DATA"].dt.date <= intervalo_datas[1]))]


# ====================================================
# BLOCO 9: MÉTRICAS FILTRADAS E CARDS
# ====================================================
eq_cons_filtro = df.groupby("LOGIN NETSALES")["Qtde. Cons."].sum()
total_equipes_filtro = eq_cons_filtro.shape[0]
equipes_ativas = eq_cons_filtro[eq_cons_filtro > 0].shape[0]
equipes_sem_cons = total_equipes_filtro - equipes_ativas

qtde_cons = int(df["Qtde. Cons."].sum())
qtde_prod = int(df["Qtde. Prod."].sum())
qtde_mesh = int(df["Qtde. Mesh"].sum())
qtde_tv = int(df["Qtde. TV"].sum())
qtde_virtua = int(df["Qtde. Virtua"].sum())

eficiencia = (equipes_ativas / total_equipes_filtro) if total_equipes_filtro > 0 else 0

var_cons = Utilitarios.calcular_share(qtde_cons, total_geral_cons)
var_efic = Utilitarios.calcular_variacao(eficiencia, total_efic_geral)
var_prod = Utilitarios.calcular_share(qtde_prod, total_geral_prod)
var_mesh = Utilitarios.calcular_share(qtde_mesh, total_geral_mesh)
var_tv = Utilitarios.calcular_share(qtde_tv, total_geral_tv)
var_virtua = Utilitarios.calcular_share(qtde_virtua, total_geral_virtua)

st.markdown(ComponenteVisual.exibir_ticker([
    {"label": "Consultivos", "valor": Utilitarios.formatar_numero(qtde_cons), "variacao": var_cons[0], "delta": var_cons[1]},
    {"label": "Eficiência", "valor": f"{eficiencia:.1%}", "variacao": var_efic[0], "delta": var_efic[1]},
    {"label": "Produtos", "valor": Utilitarios.formatar_numero(qtde_prod), "variacao": var_prod[0], "delta": var_prod[1]},
    {"label": "Mesh", "valor": Utilitarios.formatar_numero(qtde_mesh), "variacao": var_mesh[0], "delta": var_mesh[1]},
    {"label": "TV Box", "valor": Utilitarios.formatar_numero(qtde_tv), "variacao": var_tv[0], "delta": var_tv[1]},
    {"label": "Virtua", "valor": Utilitarios.formatar_numero(qtde_virtua), "variacao": var_virtua[0], "delta": var_virtua[1]},
]), unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1: st.markdown(ComponenteVisual.criar_card("Total Equipes", Utilitarios.formatar_numero(total_equipes_filtro), "azul", Utilitarios.calcular_variacao(total_equipes_filtro, total_equipes_geral)[1]), unsafe_allow_html=True)
with c2: st.markdown(ComponenteVisual.criar_card("Equipes Produtivas", Utilitarios.formatar_numero(equipes_ativas), "verde", Utilitarios.calcular_variacao(equipes_ativas, eq_ativas_geral)[1]), unsafe_allow_html=True)
with c3: st.markdown(ComponenteVisual.criar_card("Técnicos Sem Consultivo", Utilitarios.formatar_numero(equipes_sem_cons), "vermelho", Utilitarios.calcular_variacao(equipes_sem_cons, eq_zeradas_geral)[1]), unsafe_allow_html=True)
with c4: st.markdown(ComponenteVisual.criar_card("Eficiência (Conversão)", f"{eficiencia:.1%}", "roxo", var_efic[1]), unsafe_allow_html=True)

st.write("")

c5, c6, c7, c8, c9 = st.columns(5)
with c5: st.markdown(ComponenteVisual.criar_card("Tot. Consultivos", Utilitarios.formatar_numero(qtde_cons), "azul", var_cons[1]), unsafe_allow_html=True)
with c6: st.markdown(ComponenteVisual.criar_card("Tot. Produtos", Utilitarios.formatar_numero(qtde_prod), "cinza", var_prod[1]), unsafe_allow_html=True)
with c7: st.markdown(ComponenteVisual.criar_card("Total de Mesh", Utilitarios.formatar_numero(qtde_mesh), "escuro", var_mesh[1]), unsafe_allow_html=True)
with c8: st.markdown(ComponenteVisual.criar_card("Total de TV Box", Utilitarios.formatar_numero(qtde_tv), "escuro", var_tv[1]), unsafe_allow_html=True)
with c9: st.markdown(ComponenteVisual.criar_card("Total de Virtua", Utilitarios.formatar_numero(qtde_virtua), "escuro", var_virtua[1]), unsafe_allow_html=True)
st.divider()


# ====================================================
# BLOCO 10: TABELAS DE DADOS
# ====================================================
total_consultivos = ProcessamentoDados.preparar_ranking(df, ["LOGIN NETSALES", "VENDEDOR", "Monitor", "Base"], "Qtde. Cons.")
total_por_monitor = ProcessamentoDados.preparar_ranking(df, ["Monitor"], "Qtde. Prod.")

col_tit, col_tog, _ = st.columns([3, 1, 1])
with col_tit: st.subheader("👷 Visão por Técnico e Monitor")
with col_tog: modo_visao = st.toggle("Expandir Detalhes por Técnico", help="Ver dados individuais (Incluindo Zerados)")

if modo_visao:
    st.dataframe(total_consultivos.style.format(formatter=cast(Any, {c: "{:,}" for c in ["Total Consultivos", "Total Produtos", "Mesh", "TV Box", "Virtua"] if c in total_consultivos.columns}))
                 .map(Utilitarios.colorir_celula, subset=["Total Consultivos", "Total Produtos"]), use_container_width=True, height=400, hide_index=True)
else:
    st.dataframe(total_por_monitor.style.format(formatter=cast(Any, {c: "{:,}" for c in ["Total Consultivos", "Total Produtos", "Mesh", "TV Box", "Virtua"] if c in total_por_monitor.columns}))
                 .map(Utilitarios.colorir_celula, subset=["Total Consultivos", "Total Produtos"]), use_container_width=True, height=400, hide_index=True)

st.divider()


# ====================================================
# BLOCO 11: GRÁFICOS GERENCIAIS E ALERTAS
# ====================================================
aba1, aba2, aba3 = st.tabs(["📈 Desempenho e Evolução", "📦 Mix de Produtos", "🎯 Eficiência e Alertas"])

with aba1:
    col_t1, col_t2 = st.columns([1, 1])
    with col_t1:
        st.subheader("Top 10 Técnicos (Consultivos)")
        st.plotly_chart(Graficos.grafico_barras(total_consultivos.head(10), "VENDEDOR", "Total Consultivos"), use_container_width=True)
    with col_t2:
        if "DATA" in df.columns and not df["DATA"].isnull().all():
            st.subheader("Evolução Temporal")
            st.plotly_chart(Graficos.grafico_evolucao_temporal(df), use_container_width=True)
        else:
            st.info("Sem dados de data suficientes para traçar evolução.")

with aba2:
    col_m1, col_m2 = st.columns([1, 1])
    with col_m1:
        st.subheader("Distribuição por Base")
        opcoes_map = {"Produtos": "Total Produtos", "Mesh": "Mesh", "TV Box": "TV Box", "Virtua": "Virtua"}
        col_sel = st.selectbox("Escolha a métrica:", list(opcoes_map.keys()), key="sel_pizza")
        st.plotly_chart(Graficos.grafico_pizza(total_consultivos, "Base", opcoes_map[col_sel], "rosca"), use_container_width=True)
    with col_m2:
        st.subheader("Mix Vendido por Monitor")
        st.plotly_chart(Graficos.grafico_mix_produtos(df), use_container_width=True)

with aba3:
    col_e1, col_e2 = st.columns([1.5, 1])
    with col_e1:
        st.subheader("Matriz de Conversão (Técnicos)")
        st.plotly_chart(Graficos.grafico_dispersao_eficiencia(total_consultivos), use_container_width=True)
    
    with col_e2:
        st.subheader("🚨 Alerta: Oportunidades Desperdiçadas")
        st.markdown("<p style='font-size:13px; color:#64748B;'>Fizeram Consultivo mas NENHUM fechamento:</p>", unsafe_allow_html=True)
        
        # Alerta 1: Fez Consultivo, mas 0 produtos fechados (REMOVIDO .style para evitar erro do matplotlib)
        df_alerta = total_consultivos[(total_consultivos['Total Consultivos'] > 0) & (total_consultivos['Total Produtos'] == 0)].sort_values(by='Total Consultivos', ascending=False)
        st.dataframe(df_alerta[['VENDEDOR', 'Monitor', 'Total Consultivos']].head(10), use_container_width=True, hide_index=True)
        
        st.write("")
        st.subheader("🛑 Alerta Crítico: Inativos")
        st.markdown("<p style='font-size:13px; color:#64748B;'>Técnicos com ZERO Consultivos e ZERO Vendas:</p>", unsafe_allow_html=True)
        df_zerados = total_consultivos[total_consultivos['Total Consultivos'] == 0]
        st.dataframe(df_zerados[['VENDEDOR', 'Monitor', 'Base']], use_container_width=True, hide_index=True, height=200)

with aba3:
    if "DATA" in df.columns and not df["DATA"].isnull().all():
        st.write("")
        st.plotly_chart(Graficos.grafico_heatmap_semana(df.dropna(subset=['DATA'])), use_container_width=True)


# ====================================================
# EXPORTAÇÃO
# ====================================================
st.divider()
st.subheader("📥 Exportar Dados Atuais")
col_exp1, col_exp2 = st.columns([1, 3])
with col_exp1:
    formato = st.selectbox("Formato do Arquivo:", ["Excel", "CSV"])

with col_exp2:
    st.write("")
    if formato == "CSV":
        csv_data = total_consultivos.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(label="Baixar Relatório Completo", data=csv_data, file_name="relatorio_consultivos.csv", mime="text/csv")
    else:
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w: 
            total_consultivos.to_excel(w, index=False, sheet_name="Consultivos")
        st.download_button(label="Baixar Relatório Completo", data=out.getvalue(), file_name="relatorio_consultivos.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")