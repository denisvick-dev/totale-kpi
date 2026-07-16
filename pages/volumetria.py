from __future__ import annotations

import unicodedata
from io import BytesIO
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from streamlit_gsheets import GSheetsConnection

# ==========================================================
# CONFIGURAÇÃO E CONSTANTES
# ==========================================================
st.set_page_config(
    page_title="Volumetria",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


class Config:
    URL_GSHEETS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    META_EXECUCAO = 0.80
    META_EXECUTADAS_TECNICO = 7

    COL_STATUS  = "STATUS CONTRATO"
    COL_TOTAL   = "TOTAL DE TAREFAS"
    COL_TECNICO = "TÉCNICO"
    COL_MONITOR = "MONITOR"
    COL_REGIAO  = "REGIÃO"

    CORES_STATUS = {
        "Executada":     "#10B981",
        "Não Executada": "#EF4444",
        "Pendente":      "#F59E0B",
    }

    STATUS_ORDEM = ["Executada", "Não Executada", "Pendente"]

    CONTRATO_VALORES_VAZIOS = {"", "NAN", "NONE", "N/A", "NA", "-", "0", "NULL"}

    REGIOES_PRINCIPAIS = ["LESTE", "GRU", "ABCDM"]


# ==========================================================
# TEMAS DE CARDS
# ==========================================================
TEMAS_CARD: Dict[str, Dict[str, str]] = {
    "amarelo": {"fundo": "#FEF9C3", "texto": "#854D0E", "borda": "#EAB308", "titulo": "#A16207"},
    "azul":    {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
    "verde":   {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
    "roxo":    {"fundo": "#FAF5FF", "texto": "#7E22CE", "borda": "#A855F7", "titulo": "#6B21A8"},
    "cinza":   {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
    "escuro":  {"fundo": "#1E293B", "texto": "#FFFFFF", "borda": "#475569", "titulo": "#E2E8F0"},
    "vermelho":{"fundo": "#FEF2F2", "texto": "#B91C1C", "borda": "#EF4444", "titulo": "#991B1B"},
}

CORES_REGIAO: Dict[str, Dict[str, str]] = {
    "LESTE":  {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
    "GRU":    {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
    "ABCDM":  {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
    "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
}

# Mapeamento de nomes internos → títulos amigáveis para exibição
RENOMEAR_COLUNAS: Dict[str, str] = {
    "TÉCNICO":        "Técnico",
    "MONITOR":        "Monitor",
    "REGIÃO":         "Região",
    "STATUS CONTRATO":"Status",
    "TOTAL DE TAREFAS":"Total de O.S.",
    "Executada":      "Executadas",
    "Não Executada":  "Não Exec.",
    "Pendente":       "Pendentes",
    "Baixadas":       "Baixadas",
    "Total Alocado":  "Total Alocado",
    "Taxa Execução":  "Taxa Exec.",
    "Taxa Quebra":    "Taxa Quebra",
    "Projeção":       "Projeção",
}

# Colunas que devem ser convertidas para inteiro antes de exibir
COLUNAS_INTEIRAS = [
    "Executada", "Não Executada", "Pendente",
    "Baixadas", "Total Alocado", "Projeção",
]


# ==========================================================
# UTILITÁRIOS DE PROCESSAMENTO
# ==========================================================
class Utils:
    @staticmethod
    def remover_acentos(valor) -> str:
        if pd.isna(valor):
            return ""
        return (
            unicodedata.normalize("NFKD", str(valor))
            .encode("ASCII", "ignore")
            .decode("ASCII")
        )

    @staticmethod
    def normalizar_chave(serie: pd.Series) -> pd.Series:
        return (
            serie.astype(str)
            .fillna("")
            .str.strip()
            .str.upper()
            .apply(Utils.remover_acentos)
        )

    @staticmethod
    def normalizar_login(serie: pd.Series) -> pd.Series:
        return Utils.normalizar_chave(serie).str.replace(r"\.0$", "", regex=True)

    @staticmethod
    def buscar_coluna(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
        cols_map = {Utils.normalizar_chave(pd.Series([c]))[0]: c for c in df.columns}
        for alias in aliases:
            chave_alias = Utils.normalizar_chave(pd.Series([alias]))[0]
            if chave_alias in cols_map:
                return cols_map[chave_alias]
        return None

    @staticmethod
    def classificar_status(status_os: pd.Series) -> pd.Series:
        s = Utils.normalizar_chave(status_os)
        nao_executada = s.str.contains(
            r"NAO\s*EXECUT|N[AÃ]O\s*EXECUT", regex=True, na=False
        )
        executada = s.str.contains(r"EXECUT", regex=True, na=False) & ~nao_executada
        return pd.Series(
            np.select(
                [executada, nao_executada],
                ["Executada", "Não Executada"],
                default="Pendente",
            ),
            index=status_os.index,
        )

    @staticmethod
    def contrato_valido(serie: pd.Series) -> pd.Series:
        normalizado = (
            serie.astype(str).str.strip().str.upper().apply(Utils.remover_acentos)
        )
        return ~normalizado.isin(Config.CONTRATO_VALORES_VAZIOS)

    @staticmethod
    def resolver_renomeacao(
        df: pd.DataFrame,
        mapa: Dict[str, str],
    ) -> Dict[str, str]:
        """
        Retorna apenas as renomeações seguras — sem gerar duplicatas.
        Lógica:
          1. Só renomeia se o novo nome não existe como outra coluna no df.
          2. Só renomeia se o novo nome ainda não foi usado por outra coluna.
        """
        nomes_existentes = set(df.columns)
        nomes_ja_usados: set[str] = set()
        resultado: Dict[str, str] = {}

        for col_original in df.columns:
            if col_original not in mapa:
                continue
            novo_nome = mapa[col_original]
            if novo_nome == col_original:
                # mesmo nome — não precisa renomear
                continue
            if novo_nome in nomes_existentes or novo_nome in nomes_ja_usados:
                # já existe outra coluna com esse nome — mantém original
                continue
            resultado[col_original] = novo_nome
            nomes_ja_usados.add(novo_nome)

        return resultado


# ==========================================================
# CARREGAMENTO E PREPARAÇÃO DE DADOS
# ==========================================================
class DataLoader:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
        arquivo = BytesIO(file_bytes)
        if filename.lower().endswith((".xlsx", ".xls")):
            return pd.read_excel(arquivo, engine="openpyxl")
        return pd.read_csv(arquivo, sep=None, engine="python")

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_hierarquia_gsheets() -> pd.DataFrame:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            raw = conn.read(spreadsheet=Config.URL_GSHEETS)
            if raw is None or raw.empty:
                return pd.DataFrame()

            col_login = Utils.buscar_coluna(raw, ["LOGIN", "MATRÍCULA", "ID"])
            col_tec   = Utils.buscar_coluna(raw, ["TÉCNICO", "NOME"])
            col_mon   = Utils.buscar_coluna(raw, ["MONITOR", "GESTOR"])

            if not col_login:
                return pd.DataFrame()

            df_gs = pd.DataFrame({
                "__LOGIN_KEY": Utils.normalizar_login(raw[col_login]),
                "__TEC_GS":   raw[col_tec] if col_tec else "",
                "__MON_GS":   raw[col_mon] if col_mon else "",
            })
            return df_gs.drop_duplicates("__LOGIN_KEY")
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def preparar_base(df: pd.DataFrame, df_gs: pd.DataFrame) -> pd.DataFrame:
        df   = df.copy()
        diag = {"Inicial": len(df)}

        # 1. Filtro de Contrato
        col_con = Utils.buscar_coluna(
            df, ["CONTRATO", "Nº CONTRATO", "NUMERO CONTRATO", "NUM CONTRATO"]
        )
        if col_con:
            mascara_valida = Utils.contrato_valido(df[col_con])
            qtd_removidos  = (~mascara_valida).sum()
            df = df[mascara_valida].copy()
            diag["Removidos por contrato vazio"] = int(qtd_removidos)
            if qtd_removidos > 0:
                st.toast(
                    f"🗑️ {qtd_removidos} linha(s) removida(s) por contrato vazio.",
                    icon="⚠️",
                )
        else:
            st.warning(
                "⚠️ Coluna de contrato não encontrada. "
                "Nenhum filtro de contrato foi aplicado."
            )

        # 2. Filtro de Atividades Suspensas
        col_atv = Utils.buscar_coluna(df, ["STATUS DA ATIVIDADE"])
        if col_atv:
            suspensos = Utils.normalizar_chave(df[col_atv]).str.contains("SUSP", na=False)
            df = df[~suspensos].copy()

        # 3. Status e Total
        col_os1 = Utils.buscar_coluna(df, ["STATUS DA O.S 1", "STATUS OS 1"])
        if not col_os1:
            st.error("Coluna 'Status da O.S 1' não encontrada!")
            st.stop()

        df[Config.COL_STATUS] = Utils.classificar_status(df[col_os1])

        col_qtd = Utils.buscar_coluna(df, ["TOTAL DE TAREFAS", "QUANTIDADE"])
        df[Config.COL_TOTAL] = (
            pd.to_numeric(df[col_qtd], errors="coerce").fillna(1) if col_qtd else 1
        )

        # 4. Hierarquia
        col_log = Utils.buscar_coluna(df, ["LOGIN DO TÉCNICO", "LOGIN", "USUÁRIO"])
        if col_log and not df_gs.empty:
            df["__LOGIN_KEY"] = Utils.normalizar_login(df[col_log])
            df = df.merge(df_gs, on="__LOGIN_KEY", how="left")

        for col_gs in ("__TEC_GS", "__MON_GS"):
            if col_gs not in df.columns:
                df[col_gs] = np.nan

        # 5. Técnico e Monitor
        col_tec_base = Utils.buscar_coluna(df, ["TÉCNICO", "NOME"]) or col_log
        col_mon_base = Utils.buscar_coluna(df, ["MONITOR", "GESTOR"]) or col_log

        df[Config.COL_TECNICO] = (
            df["__TEC_GS"]
            .fillna(df[col_tec_base] if col_tec_base else np.nan)
            .fillna("NÃO MAPEADO")
        )
        df[Config.COL_MONITOR] = (
            df["__MON_GS"]
            .fillna(df[col_mon_base] if col_mon_base else np.nan)
            .fillna("SEM MONITOR")
        )

        # 6. Regiões
        col_cid = Utils.buscar_coluna(df, ["CIDADE", "LOCALIDADE"])
        cidade = (
            Utils.normalizar_chave(df[col_cid])
            if col_cid
            else pd.Series("", index=df.index)
        )

        df[Config.COL_REGIAO] = np.select(
            [
                cidade.isin(["SAO PAULO"]),
                cidade.isin([
                    "GUARULHOS", "ARUJA", "MOGI DAS CRUZES", "SUZANO",
                    "ITAQUAQUECETUBA", "FERRAZ DE VASCONCELOS", "POA",
                ]),
                cidade.isin([
                    "SANTO ANDRE", "SAO BERNARDO DO CAMPO", "SAO CAETANO DO SUL",
                    "DIADEMA", "MAUA", "RIBEIRAO PIRES", "RIO GRANDE DA SERRA",
                ]),
            ],
            ["LESTE", "GRU", "ABCDM"],
            default="OUTRAS",
        )

        diag["Final"] = len(df)
        df.attrs["diagnostico"] = diag
        return df


# ==========================================================
# CÁLCULOS E EXPORTAÇÃO
# ==========================================================
def calcular_volumetria(df: pd.DataFrame, grupos: List[str]) -> pd.DataFrame:
    tabela = (
        df.groupby(grupos + [Config.COL_STATUS], observed=True)[Config.COL_TOTAL]
        .sum()
        .unstack(Config.COL_STATUS, fill_value=0)
        .reset_index()
    )
    for s in Config.STATUS_ORDEM:
        if s not in tabela.columns:
            tabela[s] = 0

    for s in Config.STATUS_ORDEM:
        tabela[s] = tabela[s].astype(int)

    tabela["Baixadas"]      = tabela["Executada"] + tabela["Não Executada"]
    tabela["Total Alocado"] = tabela["Baixadas"] + tabela["Pendente"]
    tabela["Taxa Execução"] = np.where(
        tabela["Baixadas"] > 0, tabela["Executada"] / tabela["Baixadas"], 0.0
    )
    tabela["Taxa Quebra"]   = 1.0 - tabela["Taxa Execução"]
    tabela["Projeção"]      = (
        tabela["Executada"] + (tabela["Taxa Execução"] * tabela["Pendente"])
    ).astype(int)

    return tabela.sort_values("Total Alocado", ascending=False)


def gerar_excel(df: pd.DataFrame, nome_aba: str) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=nome_aba[:31])
        ws = writer.sheets[nome_aba[:31]]
        header_fill = PatternFill("solid", fgColor="0F172A")
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = Font(color="FFFFFF", bold=True)
        for i, _ in enumerate(df.columns, 1):
            ws.column_dimensions[get_column_letter(i)].width = 20
    return output.getvalue()


# ==========================================================
# INTERFACE — ESTILOS CSS
# ==========================================================
def aplicar_estilo():
    st.markdown("""
        <style>
            .hero {
                background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);
                padding: 2rem; border-radius: 1rem;
                color: white; margin-bottom: 2rem;
            }
            .kpi-card {
                padding: 1.4rem 1.6rem; border-radius: 1rem; border-left: 5px solid;
                box-shadow: 0 4px 12px rgba(0,0,0,0.06);
                transition: transform 0.15s ease, box-shadow 0.15s ease;
            }
            .kpi-card:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,0.1); }
            .kpi-val  { font-size: 1.85rem; font-weight: 800; line-height: 1.1; margin: 0.3rem 0; }
            .kpi-lab  { font-size: 0.72rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em; }
            .kpi-sub  { font-size: 0.78rem; margin-top: 0.2rem; }

            .resultado-base {
                background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);
                padding: 1rem 1.5rem; border-radius: 0.75rem; margin-bottom: 1.5rem;
                display: flex; align-items: center; flex-wrap: wrap; gap: 0.6rem;
            }
            .resultado-base-label  { color: #94A3B8; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }
            .resultado-base-regiao { padding: 0.3rem 0.9rem; border-radius: 999px; font-size: 0.82rem; font-weight: 700; border: 2px solid; }
            .resultado-base-count  { color: #64748B; font-size: 0.72rem; margin-left: auto; font-weight: 600; }

            .styled-table-wrapper {
                background: #FFFFFF; border-radius: 0.75rem;
                padding: 1rem 1.2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 1rem;
            }
            .styled-table-title { font-size: 1rem; font-weight: 700; color: #0F172A; margin-bottom: 0.6rem; display: flex; align-items: center; gap: 0.5rem; }
            .styled-table-badge { font-size: 0.68rem; background: #E0F2FE; color: #0369A1; padding: 0.15rem 0.5rem; border-radius: 999px; font-weight: 600; }

            div[data-testid="stDataFrame"] > div { border-radius: 0.5rem; overflow: hidden; }

            .section-header { display: flex; align-items: center; gap: 0.6rem; margin: 1.5rem 0 0.8rem; padding-bottom: 0.4rem; border-bottom: 2px solid #E2E8F0; }
            .section-header h3 { margin: 0; font-size: 1.1rem; color: #0F172A; }
        </style>
    """, unsafe_allow_html=True)


# ==========================================================
# COMPONENTES VISUAIS
# ==========================================================
def render_resultado_base(regioes: List[str], total: int):
    badges = ""
    for reg in sorted(regioes):
        c = CORES_REGIAO.get(reg, CORES_REGIAO["OUTRAS"])
        badges += (
            f'<span class="resultado-base-regiao" '
            f'style="background:{c["bg"]};color:{c["text"]};border-color:{c["border"]}">'
            f"{reg}</span>"
        )
    st.markdown(f"""
        <div class="resultado-base">
            <span class="resultado-base-label">📋 Resultado da Base:</span>
            {badges}
            <span class="resultado-base-count">{total:,} registros</span>
        </div>
    """, unsafe_allow_html=True)


def render_kpi(col, label: str, value: str, sub: str, tema: str = "azul"):
    t = TEMAS_CARD.get(tema, TEMAS_CARD["azul"])
    col.markdown(f"""
        <div class="kpi-card" style="background:{t['fundo']};border-left-color:{t['borda']};">
            <div class="kpi-lab" style="color:{t['titulo']}">{label}</div>
            <div class="kpi-val" style="color:{t['texto']}">{value}</div>
            <div class="kpi-sub" style="color:{t['titulo']}">{sub}</div>
        </div>
    """, unsafe_allow_html=True)


def render_section(titulo: str):
    st.markdown(
        f'<div class="section-header"><h3>{titulo}</h3></div>',
        unsafe_allow_html=True,
    )


# ==========================================================
# COMPONENTE — DataFrame Estilizado (Volumetria)
# ==========================================================
def render_dataframe(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "📊",
    badge: str = "",
    fmt: Optional[Dict[str, Any]] = None,
    color_col: Optional[str] = None,
    color_meta: Optional[float] = None,
    height: int | Literal["auto", "stretch", "content"] = "auto",
):
    badge_text = badge or f"{len(df)} registros"
    st.markdown(f"""
        <div class="styled-table-wrapper">
            <div class="styled-table-title">
                <span>{icone}</span>
                <span>{titulo}</span>
                <span class="styled-table-badge">{badge_text}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    df_display = df.copy()

    # ── 1. Resolver renomeação segura (sem duplicatas) ────────────────
    mapa_seguro = Utils.resolver_renomeacao(df_display, RENOMEAR_COLUNAS)
    df_display  = df_display.rename(columns=mapa_seguro)

    # ── 2. Atualizar referências de fmt e color_col pós-renomeação ────
    if fmt:
        fmt = {mapa_seguro.get(k, k): v for k, v in fmt.items()}
    if color_col:
        color_col = mapa_seguro.get(color_col, color_col)

    # ── 3. Float → Int nas colunas de contagem ────────────────────────
    for col_orig in COLUNAS_INTEIRAS:
        col_display = mapa_seguro.get(col_orig, col_orig)
        if col_display in df_display.columns:
            df_display[col_display] = (
                pd.to_numeric(df_display[col_display], errors="coerce")
                .fillna(0)
                .astype(int)
            )

    styler = df_display.style

    # ── 4. Formatação numérica ────────────────────────────────────────
    if fmt:
        styler = styler.format(fmt)

    # ── 5. Cor condicional — Taxa Execução ────────────────────────────
    if color_col and color_col in df_display.columns and color_meta is not None:

        def _cor_taxa(val):
            try:
                v = float(val)
            except (ValueError, TypeError):
                return ""
            if v >= color_meta:
                return "background-color:#DCFCE7;color:#166534;font-weight:600;"
            if v >= color_meta * 0.85:
                return "background-color:#FEF9C3;color:#854D0E;font-weight:600;"
            return "background-color:#FEE2E2;color:#991B1B;font-weight:600;"

        styler = styler.map(_cor_taxa, subset=pd.Index([color_col]))

    # ── 6. Cor fixa — Executadas ≥ meta técnico ───────────────────────
    col_exec_display = mapa_seguro.get("Executada", "Executada")
    if col_exec_display in df_display.columns:

        def _cor_exec(val):
            try:
                v = float(val)
            except (ValueError, TypeError):
                return ""
            if v >= Config.META_EXECUTADAS_TECNICO:
                return "background-color:#DCFCE7;color:#166534;font-weight:600;"
            return ""

        styler = styler.map(_cor_exec, subset=pd.Index([col_exec_display]))

    # ── 7. Header estilizado ──────────────────────────────────────────
    styler = styler.set_table_styles([
        {"selector": "th", "props": [
            ("background-color", "#0F172A"), ("color", "#FFFFFF"),
            ("font-size", "0.78rem"), ("font-weight", "700"),
            ("text-transform", "uppercase"), ("letter-spacing", "0.03em"),
            ("padding", "0.6rem 0.8rem"), ("border", "none"),
        ]},
        {"selector": "td", "props": [
            ("font-size", "0.82rem"), ("padding", "0.5rem 0.8rem"),
            ("border-bottom", "1px solid #F1F5F9"),
        ]},
        {"selector": "tr:hover td", "props": [("background-color", "#F8FAFC")]},
    ])

    st.dataframe(styler, use_container_width=True, hide_index=True, height=height)


# ==========================================================
# GRÁFICOS
# ==========================================================
def plot_status_pie(df: pd.DataFrame):
    res = df.groupby(Config.COL_STATUS)[Config.COL_TOTAL].sum()
    fig = go.Figure(data=[go.Pie(
        labels=res.index, values=res.values, hole=0.5,
        marker=dict(colors=[Config.CORES_STATUS.get(s) for s in res.index]),
        textinfo="label+percent", textfont_size=13,
    )])
    fig.update_layout(
        height=370, margin=dict(t=40, b=10, l=10, r=10),
        title=dict(text="Distribuição de Status", font=dict(size=15)),
        showlegend=False,
    )
    return fig


def plot_ranking_monitor(df: pd.DataFrame):
    tabela = calcular_volumetria(df, [Config.COL_MONITOR]).nlargest(15, "Total Alocado")
    fig = px.bar(
        tabela, x="Taxa Execução", y=Config.COL_MONITOR, orientation="h",
        color="Taxa Execução", color_continuous_scale="RdYlGn", range_color=[0.4, 0.9],
        text=tabela["Taxa Execução"].apply(lambda v: f"{v:.0%}"),
    )
    fig.add_vline(
        x=Config.META_EXECUCAO, line_dash="dash", line_color="#0F172A",
        annotation_text=f"Meta {Config.META_EXECUCAO:.0%}", annotation_position="top",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        height=420,
        title=dict(text="Taxa de Execução por Monitor (Top 15)", font=dict(size=15)),
        margin=dict(l=10, r=10, t=50, b=10),
        yaxis=dict(autorange="reversed"),
    )
    return fig


# ==========================================================
# MAIN APP
# ==========================================================
def main():
    aplicar_estilo()

    st.markdown(
        '<div class="hero">'
        "<h1>📊 Gestão de Volumetria</h1>"
        "<p>Análise executiva de performance e projeções operacionais</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if "base_data" not in st.session_state:
        st.session_state.base_data = None

    # ── Sidebar ───────────────────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configurações")
        if st.button("🔄 Reiniciar Painel", use_container_width=True):
            st.session_state.base_data = None
            st.rerun()

        st.divider()
        if st.session_state.base_data is not None:
            diag = st.session_state.base_data.attrs.get("diagnostico", {})
            st.write(f"📥 **Entrada:** {diag.get('Inicial', 0)}")
            st.write(f"🗑️ **Contratos vazios:** {diag.get('Removidos por contrato vazio', 0)}")
            st.write(f"📈 **Processadas:** {diag.get('Final', 0)}")

    # ── Upload ────────────────────────────────────────────────────────
    if st.session_state.base_data is None:
        render_section("📁 Importação de Dados")
        u_file = st.file_uploader(
            "Selecione a base (Excel/CSV)", type=["xlsx", "xls", "csv"]
        )
        if u_file:
            with st.spinner("Processando..."):
                df_raw = DataLoader.ler_arquivo(u_file.getvalue(), u_file.name)
                df_gs  = DataLoader.buscar_hierarquia_gsheets()
                st.session_state.base_data = DataLoader.preparar_base(df_raw, df_gs)
                st.rerun()
        return

    df_full = st.session_state.base_data

    # ── Filtros ───────────────────────────────────────────────────────
    with st.sidebar:
        st.header("🎯 Filtros")
        mons     = sorted(df_full[Config.COL_MONITOR].unique())
        sel_mons = st.multiselect("Monitor", mons, default=mons)
        df       = df_full[df_full[Config.COL_MONITOR].isin(sel_mons)]

    if df.empty:
        st.warning("Nenhum dado selecionado nos filtros.")
        return

    # ── Resultado da Base ─────────────────────────────────────────────
    render_resultado_base(sorted(df[Config.COL_REGIAO].unique()), len(df))

    # ── KPIs ──────────────────────────────────────────────────────────
    k_tot  = int(df[Config.COL_TOTAL].sum())
    k_exe  = int(df[df[Config.COL_STATUS] == "Executada"][Config.COL_TOTAL].sum())
    k_nex  = int(df[df[Config.COL_STATUS] == "Não Executada"][Config.COL_TOTAL].sum())
    k_pen  = int(df[df[Config.COL_STATUS] == "Pendente"][Config.COL_TOTAL].sum())
    k_bai  = k_exe + k_nex
    k_tx   = k_exe / k_bai if k_bai > 0 else 0
    k_proj = int(k_exe + (k_tx * k_pen))

    c1, c2, c3, c4 = st.columns(4)
    render_kpi(c1, "Total Alocado",  f"{k_tot:,}", f"{k_pen:,} pendentes",        tema="azul")
    render_kpi(c2, "Executadas",     f"{k_exe:,}", f"Taxa: {k_tx:.1%}",            tema="verde")
    render_kpi(c3, "Projeção Final", f"{k_proj:,}", "Baseado na taxa atual",       tema="escuro")
    render_kpi(c4, "Meta",           f"{Config.META_EXECUCAO:.0%}", "Referência",  tema="amarelo")

    st.markdown("")

    s1, s2, s3 = st.columns(3)
    render_kpi(s1, "Não Executadas", f"{k_nex:,}", f"Quebra: {1 - k_tx:.1%}",     tema="vermelho")
    render_kpi(s2, "Baixadas",       f"{k_bai:,}", "Exec + Não Exec",              tema="roxo")
    render_kpi(s3, "Pendentes",      f"{k_pen:,}",
               f"{k_pen / k_tot:.1%} do total" if k_tot else "0%",                 tema="cinza")

    st.markdown("")

    # ── Gráficos ──────────────────────────────────────────────────────
    render_section("📈 Visão Geral")
    g1, g2 = st.columns([1, 2])
    g1.plotly_chart(plot_status_pie(df),      use_container_width=True)
    g2.plotly_chart(plot_ranking_monitor(df), use_container_width=True)

    # ── Tabelas ───────────────────────────────────────────────────────
    t1, t2, t3 = st.tabs(["👥 Equipes", "🧑‍🔧 Técnicos", "📋 Base Completa"])

    fmt_padrao: Dict[str, Any] = {
        "Taxa Execução": "{:.1%}",
        "Taxa Quebra":   "{:.1%}",
        "Projeção":      "{:.0f}",
    }

    with t1:
        tab_eq = calcular_volumetria(df, [Config.COL_REGIAO, Config.COL_MONITOR])
        render_dataframe(
            tab_eq,
            titulo="Volumetria por Equipe",
            icone="👥",
            fmt=fmt_padrao,
            color_col="Taxa Execução",
            color_meta=Config.META_EXECUCAO,
            height=500,
        )
        st.download_button(
            "📥 Baixar Tabela Equipes",
            gerar_excel(tab_eq, "Equipes"),
            "equipes.xlsx",
        )

    with t2:
        mon_detalhe = st.selectbox("Selecione o Monitor para Detalhar Técnicos", sel_mons)
        tab_tec = calcular_volumetria(
            df[df[Config.COL_MONITOR] == mon_detalhe], [Config.COL_TECNICO]
        )
        tab_tec = tab_tec.sort_values(
            by=["Executada", "Taxa Execução", "Total Alocado"],
            ascending=[False, False, False],
        ).reset_index(drop=True)

        render_dataframe(
            tab_tec,
            titulo=f"Técnicos — {mon_detalhe}",
            icone="🧑‍🔧",
            fmt=fmt_padrao,
            color_col="Taxa Execução",
            color_meta=Config.META_EXECUCAO,
            height=500,
        )
        st.download_button(
            "📥 Baixar Tabela Técnicos",
            gerar_excel(tab_tec, "Tecnicos"),
            f"tecnicos_{mon_detalhe}.xlsx",
        )

    with t3:
        render_dataframe(
            df.head(500),
            titulo="Base de Dados (prévia — 500 linhas)",
            icone="📋",
            badge=f"{len(df)} total",
            height=600,
        )


if __name__ == "__main__":
    main()