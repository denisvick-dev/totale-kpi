# VERSÃO CLEAN: PROJEÇÕES ORDENADAS (REAIS PRIMEIRO, PROJEÇÕES DEPOIS)
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from plotly.graph_objects import Figure
from io import BytesIO
from typing import Any, Optional, cast
from streamlit_gsheets import GSheetsConnection

# ====================================================
# BLOCO 1: CONFIGURAÇÕES E UTILITÁRIOS
# ====================================================
st.set_page_config(page_title="Total de Consultivos", page_icon="📋", layout="wide")


class Configuracoes:
    url_ativos = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    cores_grafico = ["#0EA5E9", "#22C55E", "#A855F7", "#F97316", "#EF4444", "#3B82F6"]
    temas_card = {
        "amarelo": {
            "fundo": "#FEF9C3",
            "texto": "#854D0E",
            "borda": "#EAB308",
            "titulo": "#A16207",
        },
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
        "vermelho": {
            "fundo": "#FEF2F2",
            "texto": "#B91C1C",
            "borda": "#EF4444",
            "titulo": "#991B1B",
        },
    }


class ComponenteVisual:
    @staticmethod
    def criar_card(
        titulo: str, valor: str, tema: str = "azul", delta: Optional[str] = None
    ) -> str:
        cores = Configuracoes.temas_card.get(tema, Configuracoes.temas_card["azul"])
        delta_html = ""
        if delta:
            cor_delta = (
                "#22c55e"
                if delta.startswith(("+", "▲"))
                else (
                    "#ef4444"
                    if delta.startswith(("-", "▼"))
                    else "#0ea5e9" if "Total" in delta else "#94a3b8"
                )
            )
            simbolo = (
                "▲"
                if delta.startswith("+")
                else "▼" if delta.startswith("-") else "◴" if "Total" in delta else "■"
            )
            delta_html = f'<span style="font-size:13px; color:{cor_delta}; margin-left:10px;">{simbolo} {delta}</span>'

        return f"""
        <div style="background-color:{cores['fundo']}; padding:20px; border-radius:10px; border-left:6px solid {cores['borda']}; box-shadow:0 4px 6px rgba(0,0,0,0.1); margin-bottom:10px;">
            <p style="margin:0; font-size:13px; color:{cores['titulo']};"><b>{titulo}</b></p>
            <h2 style="margin:5px 0 0 0; color:{cores['texto']}; font-weight:900; font-size:28px;">{valor}{delta_html}</h2>
        </div>"""


class Calculos:
    @staticmethod
    def variacao(valor: float, geral: float) -> str:
        if geral == 0 or pd.isna(geral) or abs(valor - geral) < 0.0001:
            return "Visão Geral"
        pct = ((valor - geral) / geral) * 100
        return f"+{pct:.1f}%" if pct > 0 else f"{pct:.1f}%"

    @staticmethod
    def share(valor: float, geral: float) -> str:
        if geral == 0 or pd.isna(geral) or abs(valor - geral) < 0.0001:
            return "Visão Geral"
        return f"{(valor / geral) * 100:.1f}% do Total"

    @staticmethod
    def fator_projecao(df: pd.DataFrame) -> tuple:
        if df.empty or "DATA" not in df.columns or df["DATA"].isna().all():
            return 1.0, 0
        hoje = pd.Timestamp.today().normalize()
        if df["DATA"].max().month != hoje.month or df["DATA"].max().year != hoje.year:
            return 1.0, 0

        inicio_mes = hoje.replace(day=1)
        prox_mes = inicio_mes.replace(day=28) + pd.Timedelta(days=4)
        fim_mes = prox_mes - pd.Timedelta(days=prox_mes.day)

        dias_uteis_total = len(
            [d for d in pd.date_range(inicio_mes, fim_mes) if d.dayofweek < 6]
        )
        dias_decorridos = len(
            [d for d in pd.date_range(inicio_mes, hoje) if d.dayofweek < 6]
        )
        faltantes = dias_uteis_total - dias_decorridos

        return (
            dias_uteis_total / dias_decorridos
            if dias_decorridos > 0 and faltantes > 0
            else 1.0
        ), faltantes


# ====================================================
# BLOCO 2: PREPARAÇÃO DE DADOS
# ====================================================
@st.cache_data(ttl=300)
def carregar_hierarquia():
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(spreadsheet=Configuracoes.url_ativos, ttl=0)
    df.columns = df.columns.str.strip()
    return df[["Login", "Técnico", "Monitor", "Base"]].drop_duplicates(subset=["Login"])


def preparar_ranking(
    df: pd.DataFrame, colunas_grupo: list, fator_proj: float = 1.0
) -> pd.DataFrame:
    colunas_soma = [
        "Qtde. Cons.",
        "Qtde. Prod.",
        "Qtde. Mesh",
        "Qtde. TV",
        "Qtde. Virtua",
    ]
    colunas_soma = [c for c in colunas_soma if c in df.columns]

    # Agrupa os dados e renomeia
    res = df.groupby(colunas_grupo, dropna=False)[colunas_soma].sum().reset_index()
    renomeios = {
        "Qtde. Cons.": "Total Consultivos",
        "Qtde. Prod.": "Total Produtos",
        "Qtde. Mesh": "Mesh",
        "Qtde. TV": "TV Box",
        "Qtde. Virtua": "Virtua",
    }
    res = res.rename(columns=renomeios).fillna(0)

    # Adiciona Posição
    res = res.sort_values(
        "Total Consultivos" if "Total Consultivos" in res.columns else "Total Produtos",
        ascending=False,
    )
    res.insert(0, "Posição", range(1, len(res) + 1))

    # Lógica de Ordenação: 1º Reais, 2º Projeções, 3º Demais Produtos
    nova_ordem = ["Posição"] + colunas_grupo

    # Adiciona os Reais
    if "Total Consultivos" in res.columns:
        nova_ordem.append("Total Consultivos")
    if "Total Produtos" in res.columns:
        nova_ordem.append("Total Produtos")

    # Adiciona as Projeções
    if "Total Consultivos" in res.columns and fator_proj > 1.0:
        res["Proj. Consultivos"] = (res["Total Consultivos"] * fator_proj).astype(int)
        nova_ordem.append("Proj. Consultivos")

    if "Total Produtos" in res.columns and fator_proj > 1.0:
        res["Proj. Produtos"] = (res["Total Produtos"] * fator_proj).astype(int)
        nova_ordem.append("Proj. Produtos")

    # Adiciona os demais produtos (Mesh, TV, Virtua)
    for col in ["Mesh", "TV Box", "Virtua"]:
        if col in res.columns:
            nova_ordem.append(col)

    # Converte métricas para int e aplica nova ordem
    metricas = [c for c in nova_ordem if c not in ["Posição"] + colunas_grupo]
    res[metricas] = res[metricas].astype(int)
    return res[nova_ordem]


# ====================================================
# BLOCO 3: CARREGAMENTO PRINCIPAL E TRATAMENTO
# ====================================================
st.title("📋 Painel de Consultivos e Produtos")

if (
    "dados_cons" not in st.session_state
    or "Consultivo" not in st.session_state["dados_cons"]
):
    st.warning("⚠️ Carregue os dados na aba principal primeiro.")
    st.stop()

df = st.session_state["dados_cons"]["Consultivo"].copy()

# Tratamento de Colunas Numéricas Iniciais
mapa = {
    "QTDE_CONSULTIVO": "Qtde. Cons.",
    "QTDE_PRODUTOS": "Qtde. Prod.",
    "QTDE_MESH": "Qtde. Mesh",
    "QTDE_TV": "Qtde. TV",
    "QTDE_VIRTUA": "Qtde. Virtua",
}
for k, v in mapa.items():
    df[v] = pd.to_numeric(df.get(k, 0), errors="coerce").fillna(0).astype(int)

if "DATA" in df.columns:
    df["DATA"] = pd.to_datetime(df["DATA"], errors="coerce", dayfirst=True)

# Merge com GSheets (Hierarquia)
try:
    df_ativos = carregar_hierarquia()
    df["LOGIN NETSALES"] = df.get("LOGIN NETSALES", "").astype(str).str.strip()
    df = df.drop(columns=["Monitor", "Base"], errors="ignore")
    # Outer merge: traz todos da base + todos da planilha do google (mesmo zerados)
    df = pd.merge(
        df, df_ativos, left_on="LOGIN NETSALES", right_on="Login", how="outer"
    )
except Exception as e:
    st.error(f"Erro ao carregar hierarquia: {e}")

# 1. Arruma os Logins (Se não tem Netsales, pega o Login do GSheets)
df["LOGIN NETSALES"] = df["LOGIN NETSALES"].fillna(df["Login"]).fillna("SEM LOGIN")

# 2. Arruma os Nomes (Se não tem Vendedor na base, pega Técnico do GSheets, senão pega Login)
if "VENDEDOR" not in df.columns:
    df["VENDEDOR"] = np.nan

df["VENDEDOR"] = (
    df["VENDEDOR"]
    .fillna(df["Técnico"])
    .fillna(df["LOGIN NETSALES"])
    .fillna("Nome Não Cadastrado")
)

# 3. Arruma a Hierarquia
df["Monitor"] = df["Monitor"].fillna("Não Identificado")
df["Base"] = df["Base"].fillna("Não Identificada")

# 4. Preenche com ZERO as métricas dos técnicos zerados puxados do GSheets
colunas_metricas = [
    "Qtde. Cons.",
    "Qtde. Prod.",
    "Qtde. Mesh",
    "Qtde. TV",
    "Qtde. Virtua",
]
for col in colunas_metricas:
    if col in df.columns:
        df[col] = df[col].fillna(0).astype(int)

# ====================================================
# BLOCO 4: FILTROS E CÁLCULOS GLOBAIS
# ====================================================
# Memória dos Totais (Sem Filtro) para % de Share
t_cons, t_prod = df["Qtde. Cons."].sum(), df["Qtde. Prod."].sum()
t_mesh, t_tv, t_vir = (
    df["Qtde. Mesh"].sum(),
    df["Qtde. TV"].sum(),
    df["Qtde. Virtua"].sum(),
)

st.sidebar.header("🎯 Filtros Avançados")
base_sel = st.sidebar.selectbox(
    "Base:", ["Todas"] + sorted(df["Base"].dropna().unique().tolist())
)
monitor_opts = ["Todos"] + sorted(
    df[df["Base"] == base_sel]["Monitor"].dropna().unique().tolist()
    if base_sel != "Todas"
    else df["Monitor"].dropna().unique().tolist()
)
monitor_sel = st.sidebar.selectbox("Monitor:", monitor_opts)

if base_sel != "Todas":
    df = df[df["Base"] == base_sel]
if monitor_sel != "Todos":
    df = df[df["Monitor"] == monitor_sel]

# Variáveis Filtradas
f_cons, f_prod = df["Qtde. Cons."].sum(), df["Qtde. Prod."].sum()
f_mesh, f_tv, f_vir = (
    df["Qtde. Mesh"].sum(),
    df["Qtde. TV"].sum(),
    df["Qtde. Virtua"].sum(),
)
eq_ativas = df.groupby("LOGIN NETSALES")["Qtde. Cons."].sum()
eq_total, eq_produtivas = len(eq_ativas), len(eq_ativas[eq_ativas > 0])
eficiencia = (eq_produtivas / eq_total) if eq_total > 0 else 0

fator_proj, falt_dias = Calculos.fator_projecao(df)

# ====================================================
# BLOCO 5: UI - CARDS E PROJEÇÕES
# ====================================================
c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(
        ComponenteVisual.criar_card("Total Equipes", f"{eq_total:,.0f}", "azul"),
        unsafe_allow_html=True,
    )
with c2:
    st.markdown(
        ComponenteVisual.criar_card(
            "Equipes Produtivas", f"{eq_produtivas:,.0f}", "verde"
        ),
        unsafe_allow_html=True,
    )
with c3:
    st.markdown(
        ComponenteVisual.criar_card(
            "Técnicos Zerados", f"{eq_total - eq_produtivas:,.0f}", "vermelho"
        ),
        unsafe_allow_html=True,
    )
with c4:
    st.markdown(
        ComponenteVisual.criar_card(
            "Eficiência (Conversão)", f"{eficiencia:.2%}", "roxo"
        ),
        unsafe_allow_html=True,
    )

st.markdown("#### 📊 Resultado Realizado (Até o momento)")
c5, c6, c7, c8, c9 = st.columns(5)
with c5:
    st.markdown(
        ComponenteVisual.criar_card(
            "Tot. Consultivos", f"{f_cons:,.0f}", "azul", Calculos.share(f_cons, t_cons)
        ),
        unsafe_allow_html=True,
    )
with c6:
    st.markdown(
        ComponenteVisual.criar_card(
            "Tot. Produtos", f"{f_prod:,.0f}", "cinza", Calculos.share(f_prod, t_prod)
        ),
        unsafe_allow_html=True,
    )
with c7:
    st.markdown(
        ComponenteVisual.criar_card("Total Mesh", f"{f_mesh:,.0f}", "escuro"),
        unsafe_allow_html=True,
    )
with c8:
    st.markdown(
        ComponenteVisual.criar_card("Total TV Box", f"{f_tv:,.0f}", "escuro"),
        unsafe_allow_html=True,
    )
with c9:
    st.markdown(
        ComponenteVisual.criar_card("Total Virtua", f"{f_vir:,.0f}", "escuro"),
        unsafe_allow_html=True,
    )

if falt_dias > 0:
    st.markdown(
        f"#### 🔮 Projeção Fim do Mês <span style='font-size:14px; color:#64748B;'> (Faltam {falt_dias} dias úteis)</span>",
        unsafe_allow_html=True,
    )
    p1, p2, _ = st.columns([1, 1, 3])
    with p1:
        st.markdown(
            ComponenteVisual.criar_card(
                "Proj. Consultivos",
                f"{int(f_cons * fator_proj):,}",
                "amarelo",
                f"+ {int((f_cons * fator_proj) - f_cons)} est.",
            ),
            unsafe_allow_html=True,
        )
    with p2:
        st.markdown(
            ComponenteVisual.criar_card(
                "Proj. Produtos",
                f"{int(f_prod * fator_proj):,}",
                "amarelo",
                f"+ {int((f_prod * fator_proj) - f_prod)} est.",
            ),
            unsafe_allow_html=True,
        )

st.divider()

# ====================================================
# BLOCO 6: TABELAS E GRÁFICOS
# ====================================================
col_tit, col_tog, _ = st.columns([3, 1, 1])
with col_tit:
    st.subheader("👷 Visão Consolidada")
with col_tog:
    detalhar_tec = st.toggle("Detalhar por Técnico")

grupo = (
    ["LOGIN NETSALES", "VENDEDOR", "Monitor", "Base"] if detalhar_tec else ["Monitor"]
)
df_exibir = preparar_ranking(df, grupo, fator_proj)

colunas_proj = [c for c in df_exibir.columns if "Proj." in str(c)]
colunas_reais = [
    c for c in ["Total Consultivos", "Total Produtos"] if c in df_exibir.columns
]
todas_num = [c for c in df_exibir.columns if c not in ["Posição"] + grupo]

style_df = df_exibir.style.format(formatter=cast(Any, {c: "{:,}" for c in todas_num}))
if colunas_reais:
    style_df = style_df.set_properties(
        **{"background-color": "#F8FAFC", "font-weight": "bold"},
        subset=cast(Any, colunas_reais),
    )
if colunas_proj:
    style_df = style_df.set_properties(
        **{"background-color": "#FEF9C3", "color": "#854D0E", "font-weight": "bold"},
        subset=cast(Any, colunas_proj),
    )

st.dataframe(style_df, use_container_width=True, height=450, hide_index=True)

# Abas de Gráficos Rápidos e Alertas
aba1, aba2 = st.tabs(["📈 Desempenho e Matriz", "🚫 Equipes sem Consultivos"])

with aba1:
    g1, g2 = st.columns(2)
    with g1:
        if not df_exibir.empty:
            st.plotly_chart(
                px.bar(
                    df_exibir.head(10),
                    x=grupo[1] if detalhar_tec else "Monitor",
                    y="Total Consultivos",
                    title="Top 10 Consultivos (Real)",
                ),
                use_container_width=True,
            )
    with g2:
        df_disp = df_exibir[df_exibir["Total Consultivos"] > 0]
        if not df_disp.empty:
            st.plotly_chart(
                px.scatter(
                    df_disp,
                    x="Total Consultivos",
                    y="Total Produtos",
                    color="Monitor",
                    title="Matriz: Consultivos x Produtos",
                ),
                use_container_width=True,
            )

with aba2:
    st.subheader("🚫 Equipes que ainda não fizeram Consultivos")
    # Filtra quem tem exatamente zero consultivos
    df_zerados = df_exibir[df_exibir["Total Consultivos"] == 0]

    if not df_zerados.empty:
        st.dataframe(df_zerados, use_container_width=True, hide_index=True)
    else:
        st.success(
            "✅ Excelente! 100% da operação possui pelo menos um consultivo registrado."
        )

# Exportação
st.divider()
st.subheader("📥 Exportar Dados (Inclui Projeções)")
c_exp1, c_exp2 = st.columns([1, 4])
tipo_exp = c_exp1.selectbox("Formato:", ["Excel", "CSV"], label_visibility="collapsed")
if tipo_exp == "CSV":
    c_exp2.download_button(
        "Baixar",
        df_exibir.to_csv(index=False, encoding="utf-8-sig"),
        "relatorio.csv",
        "text/csv",
    )
else:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df_exibir.to_excel(w, index=False)
    c_exp2.download_button(
        "Baixar",
        out.getvalue(),
        "relatorio.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
