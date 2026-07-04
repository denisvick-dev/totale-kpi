# VERSÃO REFATORADA E CORRIGIDA
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
    
    TEMAS_CARD = {
        "amarelo": {"fundo": "#FEF9C3", "texto": "#854D0E", "borda": "#EAB308", "titulo": "#A16207"},
        "azul":    {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
        "verde":   {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
        "roxo":    {"fundo": "#FAF5FF", "texto": "#7E22CE", "borda": "#A855F7", "titulo": "#6B21A8"},
        "cinza":   {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
        "escuro":  {"fundo": "#1E293B", "texto": "#FFFFFF", "borda": "#475569", "titulo": "#E2E8F0"},
    }
    
    CORES_GRAFICO = ["#0EA5E9", "#22C55E", "#A855F7", "#F97316", "#EF4444", "#3B82F6"]
    
    PAGINA = {
        "titulo": "📋 Total de Consultivos",
        "icon": "📋"
    }
    
    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"


# ====================================================
# BLOCO 2: COMPONENTES VISUAIS
# ====================================================

class ComponenteVisual:
    """Componentes visuais HTML/CSS customizados."""
    
    @staticmethod
    def criar_card(titulo: str, valor: str, tema: str = "azul", delta: Optional[str] = None) -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        
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
        # Filtra apenas as colunas que realmente existem no DF para evitar erros
        colunas_soma = [col for col in colunas_soma if col in df.columns]
        
        resultado = df.groupby(colunas_grupo)[colunas_soma].sum().reset_index().sort_values(coluna_ordenacao, ascending=False)
        resultado.insert(0, "Posição", range(1, len(resultado) + 1))
        
        renomeios = {"Qtde. Cons.": "Total Consultivos", "Qtde. Prod.": "Total Produtos", "Qtde. Mesh": "Mesh", "Qtde. TV": "TV Box", "Qtde. Virtua": "Virtua"}
        resultado = resultado.rename(columns=renomeios)
        
        # Converte as colunas numéricas para inteiro de forma segura
        col_ints = [renomeios.get(c, c) for c in colunas_soma] + ["Posição"]
        resultado[col_ints] = resultado[col_ints].astype(int)
        
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
        fig = px.pie(df, names=names, values=values, hole=hole_size, color_discrete_sequence=Configuracoes.CORES_GRAFICO)
        fig.update_layout(font=dict(family="Roboto"), paper_bgcolor="rgba(0,0,0,0)")
        if tipo == "rosca":
            fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
        return fig


# ====================================================
# BLOCO 5: INÍCIO DA PÁGINA E PREPARAÇÃO DOS DADOS
# ====================================================
st.set_page_config(page_title=Configuracoes.PAGINA["titulo"], page_icon=Configuracoes.PAGINA["icon"], layout=cast(Literal["wide"], "wide"))
st.title(Configuracoes.PAGINA["titulo"])

if "dados_cons" not in st.session_state or "Consultivo" not in st.session_state["dados_cons"]:
    st.warning("⚠️ Carregue os dados na aba principal primeiro.")
    st.stop()

df = st.session_state["dados_cons"]["Consultivo"].copy()

# Padronização de Colunas Numéricas
mapa_colunas = {
    "QTDE_CONSULTIVO": "Qtde. Cons.", "QTDE_PRODUTOS": "Qtde. Prod.",
    "QTDE_MESH": "Qtde. Mesh", "QTDE_TV": "Qtde. TV", "QTDE_VIRTUA": "Qtde. Virtua",
}
for origem, destino in mapa_colunas.items():
    if origem in df.columns:
        df[destino] = pd.to_numeric(df[origem], errors="coerce").fillna(0).astype(int)
    else:
        df[destino] = 0

# ====================================================
# BLOCO 6: INTEGRAÇÃO COM GOOGLE SHEETS
# ====================================================
try:
    df_ativos = ProcessamentoDados.carregar_ativos(Configuracoes.URL_ATIVOS)
except Exception as erro:
    st.error(f"❌ Falha ao conectar com as planilhas: {erro}")
    st.stop()

df = ProcessamentoDados.limpar_strings(df, ["LOGIN NETSALES"])
df_ativos = ProcessamentoDados.limpar_strings(df_ativos, ["Login", "Monitor", "Base"])

df_ativos_subset = df_ativos[["Login", "Monitor", "Base"]].drop_duplicates(subset=["Login"])
df = df.drop(columns=["Monitor", "Base"], errors="ignore")
df = pd.merge(df, df_ativos_subset, left_on="LOGIN NETSALES", right_on="Login", how="left")

df["Monitor"] = df["Monitor"].fillna("Não Identificado")
df["Base"] = df["Base"].fillna("Não Identificado")


# ====================================================
# BLOCO 7: CÁLCULO DOS INDICADORES GLOBAIS (BASE)
# ====================================================
# Proteção contra ausência de colunas específicas
colunas_tv_net = [c for c in ["PLANO TV", "PLANO INTERNET"] if c in df.columns]

TOTAL_GERAL_CONS = int(df["Qtde. Cons."].sum()) if "Qtde. Cons." in df.columns else 0

# ✅ CORREÇÃO: Utilizando a coluna já convertida para int em vez de re-aplicar o len() na lista original
TOTAL_GERAL_PROD = int(df["Qtde. Prod."].sum()) if "Qtde. Prod." in df.columns else 0
TOTAL_GERAL_MESH = int(df["Qtde. Mesh"].sum()) if "Qtde. Mesh" in df.columns else 0
TOTAL_GERAL_TV = int(df["Qtde. TV"].sum()) if "Qtde. TV" in df.columns else 0
TOTAL_GERAL_VIRTUA = int(df["Qtde. Virtua"].sum()) if "Qtde. Virtua" in df.columns else 0

if not df_ativos.empty:
    TOTAL_EQUIPES_GERAL = df_ativos["Login"].dropna().nunique()
else:
    TOTAL_EQUIPES_GERAL = 0

if "VENDEDOR" in df.columns and not df.empty:
    eq_cons_geral = df.groupby("VENDEDOR")["Qtde. Cons."].sum()
    eq_ativas_geral = eq_cons_geral[eq_cons_geral > 0].shape[0]
else:
    eq_ativas_geral = 0

TOTAL_EFIC_GERAL = (eq_ativas_geral / TOTAL_EQUIPES_GERAL) if TOTAL_EQUIPES_GERAL > 0 else 0


# ====================================================
# BLOCO 8: FILTROS GLOBAIS (SIDEBAR)
# ====================================================
st.sidebar.header("🎯 Filtros Avançados")

if not df.empty and "Base" in df.columns:
    opcoes_base = ["Todas"] + sorted(df["Base"].dropna().unique().tolist())
    base_sel = st.sidebar.selectbox("Filtrar por Base:", opcoes_base)
else:
    base_sel = "Todas"

if base_sel != "Todas" and not df.empty:
    df_temp = df[df["Base"] == base_sel]
    if not df_temp.empty and "Monitor" in df_temp.columns:
        opcoes_monitor = ["Todos"] + sorted(df_temp["Monitor"].dropna().unique().tolist())
        monitor_sel = st.sidebar.selectbox("Filtrar por Monitor:", opcoes_monitor)
    else:
        monitor_sel = "Todos"
else:
    monitor_sel = "Todos"
    df_temp = df

intervalo_datas = None
if not df.empty and "DATA" in df.columns:
    df = df.assign(DATA=pd.to_datetime(df["DATA"], errors="coerce", dayfirst=True))
    datas_validas = df["DATA"].dropna()
    if not datas_validas.empty:
        intervalo_datas = st.sidebar.date_input(
            "Selecione o período:", 
            value=(datas_validas.min().date(), datas_validas.max().date()),
            min_value=datas_validas.min().date(), 
            max_value=datas_validas.max().date(), 
            format="DD/MM/YYYY"
        )

if st.sidebar.button("🔄 Limpar Filtros"):
    st.rerun()

# Aplicação dos Filtros
if base_sel != "Todas" and not df.empty: 
    df = df[df["Base"] == base_sel]
    if not df_ativos.empty and "Base" in df_ativos.columns: 
        df_ativos = df_ativos[df_ativos["Base"] == base_sel]

if monitor_sel != "Todos" and not df.empty: 
    df = df[df["Monitor"] == monitor_sel]
    if not df_ativos.empty and "Monitor" in df_ativos.columns: 
        df_ativos = df_ativos[df_ativos["Monitor"] == monitor_sel]

if intervalo_datas and isinstance(intervalo_datas, tuple) and len(intervalo_datas) == 2:
    df = df[(df["DATA"].dt.date >= intervalo_datas[0]) & (df["DATA"].dt.date <= intervalo_datas[1])]


# ====================================================
# BLOCO 9: MÉTRICAS FILTRADAS, TICKER E CARDS
# ====================================================
if not df.empty and "VENDEDOR" in df.columns:
    equipes_cons = df.groupby("VENDEDOR")["Qtde. Cons."].sum().reset_index()
    equipes_ativas = equipes_cons[equipes_cons["Qtde. Cons."] > 0].shape[0]
else:
    equipes_ativas = 0

if not df_ativos.empty:
    total_equipes_filtro = df_ativos["Login"].dropna().nunique()
else:
    total_equipes_filtro = 0

qtde_cons = int(df["Qtde. Cons."].sum()) if "Qtde. Cons." in df.columns else 0

# ✅ CORREÇÃO: Utilizando a coluna já convertida de forma eficiente
qtde_prod = int(df["Qtde. Prod."].sum()) if "Qtde. Prod." in df.columns else 0
qtde_mesh = int(df["Qtde. Mesh"].sum()) if "Qtde. Mesh" in df.columns else 0
qtde_tv = int(df["Qtde. TV"].sum()) if "Qtde. TV" in df.columns else 0
qtde_virtua = int(df["Qtde. Virtua"].sum()) if "Qtde. Virtua" in df.columns else 0

eficiencia = (equipes_ativas / total_equipes_filtro) if total_equipes_filtro > 0 else 0

var_efic = Utilitarios.calcular_variacao(eficiencia, TOTAL_EFIC_GERAL)
var_cons = Utilitarios.calcular_share(qtde_cons, TOTAL_GERAL_CONS)
var_prod = Utilitarios.calcular_share(qtde_prod, TOTAL_GERAL_PROD)
var_mesh = Utilitarios.calcular_share(qtde_mesh, TOTAL_GERAL_MESH)
var_tv = Utilitarios.calcular_share(qtde_tv, TOTAL_GERAL_TV)
var_virtua = Utilitarios.calcular_share(qtde_virtua, TOTAL_GERAL_VIRTUA)

# Renderizando Ticker
dados_ticker = [
    {"label": "Consultivos", "valor": Utilitarios.formatar_numero(qtde_cons), "variacao": var_cons[0], "delta": var_cons[1]},
    {"label": "Eficiência", "valor": f"{eficiencia:.1%}", "variacao": var_efic[0], "delta": var_efic[1]},
    {"label": "Produtos", "valor": Utilitarios.formatar_numero(qtde_prod), "variacao": var_prod[0], "delta": var_prod[1]},
    {"label": "Mesh", "valor": Utilitarios.formatar_numero(qtde_mesh), "variacao": var_mesh[0], "delta": var_mesh[1]},
    {"label": "TV Box", "valor": Utilitarios.formatar_numero(qtde_tv), "variacao": var_tv[0], "delta": var_tv[1]},
    {"label": "Virtua", "valor": Utilitarios.formatar_numero(qtde_virtua), "variacao": var_virtua[0], "delta": var_virtua[1]},
]
st.markdown(ComponenteVisual.exibir_ticker(dados_ticker), unsafe_allow_html=True)

# Renderizando Cards
c1, c2, c3, c4, c5 = st.columns(5)
with c1: 
    var_eq = Utilitarios.calcular_variacao(equipes_ativas, eq_ativas_geral)
    st.markdown(ComponenteVisual.criar_card("Eq. c/ Consultivo", Utilitarios.formatar_numero(equipes_ativas), "amarelo", var_eq[1]), unsafe_allow_html=True)
with c2: 
    var_tot_eq = Utilitarios.calcular_variacao(total_equipes_filtro, TOTAL_EQUIPES_GERAL)
    st.markdown(ComponenteVisual.criar_card("Total Equipes", Utilitarios.formatar_numero(total_equipes_filtro), "azul", var_tot_eq[1]), unsafe_allow_html=True)
with c3: st.markdown(ComponenteVisual.criar_card("Eficiência", f"{eficiencia:.1%}", "verde", var_efic[1]), unsafe_allow_html=True)
with c4: st.markdown(ComponenteVisual.criar_card("Tot. Consultivos", Utilitarios.formatar_numero(qtde_cons), "azul", var_cons[1]), unsafe_allow_html=True)
with c5: st.markdown(ComponenteVisual.criar_card("Tot. Produtos", Utilitarios.formatar_numero(qtde_prod), "cinza", var_prod[1]), unsafe_allow_html=True)

st.write("")

c6, c7, c8 = st.columns(3)
with c6: st.markdown(ComponenteVisual.criar_card("Total de Mesh", Utilitarios.formatar_numero(qtde_mesh), "roxo", var_mesh[1]), unsafe_allow_html=True)
with c7: st.markdown(ComponenteVisual.criar_card("Total de TV Box", Utilitarios.formatar_numero(qtde_tv), "roxo", var_tv[1]), unsafe_allow_html=True)
with c8: st.markdown(ComponenteVisual.criar_card("Total de Virtua", Utilitarios.formatar_numero(qtde_virtua), "roxo", var_virtua[1]), unsafe_allow_html=True)

st.divider()


# ====================================================
# BLOCO 10: TABELAS
# ====================================================
colunas_necessarias = ["LOGIN NETSALES", "VENDEDOR", "Monitor", "Base", "Qtde. Cons.", "Qtde. Prod."]
if all(col in df.columns for col in colunas_necessarias):
    total_consultivos = ProcessamentoDados.preparar_ranking(df, ["LOGIN NETSALES", "VENDEDOR", "Monitor", "Base"], "Qtde. Cons.")
    total_por_monitor = ProcessamentoDados.preparar_ranking(df, ["Monitor"], "Qtde. Prod.")
else:
    st.error("⚠️ Faltam colunas necessárias no DataFrame para gerar as tabelas.")
    st.stop()

col_tit, col_tog, _ = st.columns([3, 1, 1])
with col_tit: st.subheader("👷 Visão por Técnico")
with col_tog: modo_visao = st.toggle("Modo Detalhado", help="Ative para ver dados por técnico individualmente")

df_visao = total_consultivos # Por padrão usa a mesma estrutura resumida
if modo_visao:
    df_visao = ProcessamentoDados.preparar_ranking(df, ["LOGIN NETSALES", "VENDEDOR", "Monitor", "Base"], "Qtde. Cons.")

if not df_visao.empty:
    st.dataframe(
        df_visao.style.format(formatter=cast(Any, {c: "{:,}" for c in ["Total Consultivos", "Total Produtos", "Mesh", "TV Box", "Virtua"] if c in df_visao.columns}))
               .map(Utilitarios.colorir_celula, subset=["Total Consultivos", "Total Produtos"]),
        use_container_width=True, height=400, hide_index=True
    )

st.subheader("👨‍💼 Visão por Monitor")
if not total_por_monitor.empty:
    st.dataframe(
        total_por_monitor.style.format(formatter=cast(Any, {c: "{:,}" for c in ["Total Consultivos", "Total Produtos", "Mesh", "TV Box", "Virtua"] if c in total_por_monitor.columns}))
                        .map(Utilitarios.colorir_celula, subset=["Total Consultivos", "Total Produtos"]),
        use_container_width=True, height=400, hide_index=True
    )

st.divider()


# ====================================================
# BLOCO 11: GRÁFICOS E EXPORTAÇÃO CORRIGIDA
# ====================================================
st.subheader("📊 Top 10 Equipes por Consultivos")
if not total_consultivos.empty and "VENDEDOR" in total_consultivos.columns:
    st.plotly_chart(Graficos.grafico_barras(total_consultivos.head(10), "VENDEDOR", "Total Consultivos"), use_container_width=True)

st.divider()

col_graf, col_opc = st.columns([3, 1])

with col_graf:
    st.subheader("🥧 Distribuição de Produtos por Base")
    opcoes_map = {"Produtos": "Total Produtos", "Mesh": "Mesh", "TV Box": "TV Box", "Virtua": "Virtua"}
    col_sel = st.selectbox("Escolha o tipo de produto:", list(opcoes_map.keys()))
    tipo_graf = st.radio("Tipo de gráfico:", ["Pizza", "Rosca"], horizontal=True, label_visibility="collapsed")
    
    if not total_consultivos.empty and "Base" in total_consultivos.columns:
        st.plotly_chart(Graficos.grafico_pizza(total_consultivos, "Base", opcoes_map[col_sel], "rosca" if tipo_graf == "Rosca" else "pizza"), use_container_width=True)

with col_opc:
    st.subheader("📥 Exportar Dados")
    formato = st.selectbox("Formato:", ["Excel", "CSV"])
    
    # IMPORTANTE: No Streamlit, botões de download NÃO podem ficar dentro de um `if st.button:`
    if formato == "CSV":
        csv_data = df_visao.to_csv(index=False, encoding='utf-8-sig')
        st.download_button(label="Baixar Tabela Técnicos", data=csv_data, file_name="consultivos.csv", mime="text/csv", use_container_width=True)
    else:
        out = BytesIO()
        with pd.ExcelWriter(out, engine="openpyxl") as w: 
            df_visao.to_excel(w, index=False, sheet_name="Consultivos")
        st.download_button(label="Baixar Tabela Técnicos", data=out.getvalue(), file_name="consultivos.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)