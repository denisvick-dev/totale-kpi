from __future__ import annotations

import unicodedata
from io import BytesIO
from textwrap import dedent
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from streamlit_gsheets import GSheetsConnection

# ====================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ====================================================
st.set_page_config(
    page_title="Rota Inicial",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "df_master" not in st.session_state:
    st.session_state["df_master"] = None

if "total_montados_manual" not in st.session_state:
    st.session_state["total_montados_manual"] = 0

# ====================================================
# 2. CONFIGURAÇÕES GLOBAIS
# ====================================================
URL_GSHEETS = (
    "https://docs.google.com/spreadsheets/d/"
    "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
)

CONTRATO_VALORES_VAZIOS = {"", "NAN", "NONE", "N/A", "NA", "-", "0", "NULL", "<NA>"}

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

CORES_REGIAO = {
    "LESTE": {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
    "GRU": {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
    "ABCDM": {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
    "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
}

RENOMEAR_COLUNAS: Dict[str, str] = {
    "Monitor": "Monitor",
    "OS": "Volume de O.S.",
    "GPON": "GPON",
    "ND": "Adesão",
    "Migração": "Migração",
    "Qtd_4K": "4K",
    "Ultra": "Ponto Ultra",
    "Soundbox": "Soundbox",
    "Equipe": "Equipe",
    "Média": "Média/Téc.",
    "NOME_OFICIAL": "Técnico",
    "TOTAL_TAREFAS": "Total de O.S.",
    "LOGIN_TECNICO": "Login",
    "STATUS_ATIVIDADE": "Status",
    "PERIODO_TRATADO": "Período",
    "HABILIDADE": "Habilidade",
    "TIPO_OS": "Tipo OS",
    "PRODUTO": "Produto",
    "INTERVALO": "Intervalo",
    "CIDADE": "Cidade",
    "CONTRATO": "Contrato",
    "REGIÃO": "Região",
}


# ====================================================
# 3. ESTILOS CSS
# ====================================================
def aplicar_estilo():
    st.markdown(
        """
    <style>
    .hero-corp {
        background: linear-gradient(135deg, #0F172A 0%, #1E3A8A 50%, #1E40AF 100%);
        padding: 32px 40px; border-radius: 16px; color: white;
        box-shadow: 0 10px 40px rgba(15, 23, 42, 0.15);
        margin-bottom: 24px; position: relative; overflow: hidden;
        border: 1px solid #334155;
    }
    .hero-corp::before {
        content: ''; position: absolute; top: -50%; right: -10%;
        width: 400px; height: 400px;
        background: rgba(255,255,255,0.03); border-radius: 50%;
    }
    .hero-title {
        font-size: 32px; font-weight: 800; margin: 0;
        letter-spacing: -0.5px;
        font-family: 'Segoe UI', -apple-system, sans-serif;
    }
    .hero-subtitle {
        font-size: 15px; opacity: 0.90; margin: 6px 0 0 0; font-weight: 400;
    }
    .kpi-card {
        padding: 1.4rem 1.6rem; border-radius: 1rem; border-left: 5px solid;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        min-height: 110px; display: flex; flex-direction: column; justify-content: center;
        border: 1px solid #E2E8F0;
    }
    .kpi-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.07);
    }
    .kpi-val { font-size: 1.85rem; font-weight: 800; line-height: 1.1; margin: 0.3rem 0; }
    .kpi-lab { font-size: 0.72rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em; }
    .kpi-sub { font-size: 0.78rem; margin-top: 0.2rem; }

    .resultado-base {
        background: linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);
        padding: 1rem 1.5rem;
        border-radius: 0.75rem;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 0.6rem;
        box-shadow: 0 6px 20px rgba(1, 40, 105, 0.20);
        position: relative;
        overflow: hidden;
    }
    .resultado-base::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -5%;
        width: 250px;
        height: 250px;
        background: rgba(255,255,255,0.05);
        border-radius: 50%;
        pointer-events: none;
    }
    .resultado-base-label {
        color: #FFFFFF;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-right: 0.3rem;
        position: relative;
        z-index: 2;
        text-shadow: 0 1px 2px rgba(0,0,0,0.15);
    }
    .resultado-base-regiao {
        padding: 0.35rem 0.95rem;
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        border: 2px solid rgba(255,255,255,0.4);
        position: relative;
        z-index: 2;
        box-shadow: 0 2px 6px rgba(0,0,0,0.10);
    }
    .resultado-base-count {
        color: #FFFFFF;
        font-size: 0.78rem;
        margin-left: auto;
        font-weight: 700;
        opacity: 0.95;
        position: relative;
        z-index: 2;
        text-shadow: 0 1px 2px rgba(0,0,0,0.15);
    }
    .styled-table-wrapper {
        background: #FFFFFF; border-radius: 0.75rem;
        padding: 1rem 1.2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        margin-bottom: 0.5rem;
    }
    .styled-table-title {
        font-size: 1rem; font-weight: 700; color: #0F172A;
        margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.5rem;
    }
    .styled-table-badge {
        font-size: 0.68rem; background: #E0F2FE; color: #0369A1;
        padding: 0.15rem 0.5rem; border-radius: 999px; font-weight: 600;
    }
    div[data-testid="stDataFrame"] > div { border-radius: 0.5rem; overflow: hidden; }
    .section-header {
        display: flex; align-items: center; gap: 0.6rem;
        margin: 1.8rem 0 0.8rem; padding-bottom: 0.5rem;
        border-bottom: 2px solid #E2E8F0;
    }
    .section-header h3 { margin: 0; font-size: 1.15rem; color: #0F172A; font-weight: 700; }

    /* ═══════════════════════════════════════════════════════════
       TABELAS ROTA/TURNO — ESTILO PREMIUM CORPORATIVO (REDIZADO)
       ═══════════════════════════════════════════════════════════ */
    .rota-wrapper {
        margin: 24px 0;
        font-family: 'Segoe UI', -apple-system, sans-serif;
        box-shadow: 0 4px 20px rgba(0,0,0,0.05);
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #E2E8F0;
    }

    .rota-titulo {
        background: #0F172A; /* Slate 900 */
        color: #F8FAFC;
        font-weight: 700;
        font-size: 14px;
        text-align: left;
        padding: 14px 20px;
        letter-spacing: 0.5px;
        text-transform: uppercase;
        border-bottom: 3px solid #312E81; /* Indigo Accent */
    }
    table.rota-tab {
        width: 100%; border-collapse: separate; border-spacing: 0; background: white;
        font-size: 13px;
    }
    table.rota-tab th {
        background: #1E293B; /* Slate 800 */
        color: #F1F5F9;
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 12px 14px;
        text-align: center;
        border-bottom: 1px solid #334155;
    }
    table.rota-tab th.th-os {
        background: #2E2514; color: #FBBF24;
    }
    table.rota-tab th.th-equipe {
        background: #064E3B; color: #6EE7B7;
    }
    table.rota-tab th.th-media {
        background: #1E3A8A; color: #93C5FD;
    }
    table.rota-tab td {
        padding: 10px 14px; text-align: center; border-bottom: 1px solid #F1F5F9;
        color: #334155; font-variant-numeric: tabular-nums;
    }
    table.rota-tab td.col-monitor {
        text-align: left; font-weight: 600; padding-left: 20px; color: #0F172A;
    }
    table.rota-tab td.col-os {
        background: #FFFBEB; font-weight: 700; color: #92400E;
        border-left: 1px solid #FEF3C7; border-right: 1px solid #FEF3C7;
    }
    table.rota-tab td.col-equipe {
        background: #F0FDF4; font-weight: 700; color: #166534;
        border-left: 1px solid #D1FAE5; border-right: 1px solid #D1FAE5;
    }
    table.rota-tab td.col-media {
        background: #F8FAFC; font-weight: 700; color: #1E293B;
    }

    /* Linhas de Total Geral - Escalados */
    table.rota-tab tr.total-escalados td {
        background: #F1F5F9;
        color: #0F172A; font-weight: 700; font-size: 13px;
        border-top: 2px solid #CBD5E1;
        border-bottom: 1px solid #CBD5E1;
    }
    table.rota-tab tr.total-escalados td.col-monitor { color: #0F172A; }
    table.rota-tab tr.total-escalados td.col-os { background: #FEF3C7; color: #92400E; }
    table.rota-tab tr.total-escalados td.col-equipe { background: #D1FAE5; color: #065F46; }
    table.rota-tab tr.total-escalados td.col-media { background: #E2E8F0; color: #0F172A; }

    /* Linhas de Total Geral - Montados */
    table.rota-tab tr.total-montados td {
        background: #E2E8F0;
        color: #0F172A; font-weight: 800; font-size: 13px;
        border-bottom: none;
    }
    table.rota-tab tr.total-montados td.col-monitor { color: #0F172A; }
    table.rota-tab tr.total-montados td.col-os { background: #FDE68A; color: #78350F; }
    table.rota-tab tr.total-montados td.col-equipe { background: #A7F3D0; color: #064E3B; }
    table.rota-tab tr.total-montados td.col-media { background: #CBD5E1; color: #0F172A; }

    /* Estilo de Linhas Alternadas */
    table.rota-tab tbody tr:nth-child(even):not(.total-escalados):not(.total-montados) td {
        background: #FAFAFA;
    }
    table.rota-tab tbody tr:nth-child(even):not(.total-escalados):not(.total-montados) td.col-os {
        background: #FFFDF5;
    }
    table.rota-tab tbody tr:nth-child(even):not(.total-escalados):not(.total-montados) td.col-equipe {
        background: #F4FDF7;
    }
    table.rota-tab tbody tr:hover:not(.total-escalados):not(.total-montados) td {
        background: #F1F5F9;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )


# ====================================================
# 4. COMPONENTES VISUAIS
# ====================================================
def render_kpi(col, label: str, value: str, sub: str = "", tema: str = "azul"):
    t = TEMAS_CARD.get(tema, TEMAS_CARD["azul"])
    col.markdown(
        f"""
    <div class="kpi-card" style="background:{t['fundo']};border-left-color:{t['borda']};">
        <div class="kpi-lab" style="color:{t['titulo']}">{label}</div>
        <div class="kpi-val" style="color:{t['texto']}">{value}</div>
        <div class="kpi-sub" style="color:{t['titulo']}">{sub}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_resultado_base(regioes: List[str], total: int):
    badges = ""
    for reg in sorted(regioes):
        c = CORES_REGIAO.get(reg, CORES_REGIAO["OUTRAS"])
        badges += (
            f'<span class="resultado-base-regiao" '
            f'style="background:{c["bg"]};color:{c["text"]};'
            f'border-color:{c["border"]}">{reg}</span>'
        )
    st.markdown(
        f"""
    <div class="resultado-base">
        <span class="resultado-base-label">📋 Resultado da Base:</span>
        {badges}
        <span class="resultado-base-count">{total:,} registros</span>
    </div>
    """,
        unsafe_allow_html=True,
    )


def render_section(titulo: str):
    st.markdown(
        f'<div class="section-header"><h3>{titulo}</h3></div>',
        unsafe_allow_html=True,
    )


def render_dataframe(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "📊",
    badge: str = "",
    fmt: Optional[Dict[str, Any]] = None,
    color_col: Optional[str] = None,
    color_meta: Optional[float] = None,
    color_invertido: bool = False,
    height: int | Literal["auto", "stretch", "content"] = "auto",
):
    badge_text = badge or f"{len(df)} registros"
    st.markdown(
        f"""
    <div class="styled-table-wrapper">
        <div class="styled-table-title">
            <span>{icone}</span><span>{titulo}</span>
            <span class="styled-table-badge">{badge_text}</span>
        </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    df_display = df.copy()
    colunas_para_renomear = {}
    nomes_existentes = set(df_display.columns)
    nomes_ja_usados = set()

    for col_original in df_display.columns:
        if col_original in RENOMEAR_COLUNAS:
            novo_nome = RENOMEAR_COLUNAS[col_original]
            if novo_nome == col_original or (
                novo_nome not in nomes_existentes and novo_nome not in nomes_ja_usados
            ):
                colunas_para_renomear[col_original] = novo_nome
                nomes_ja_usados.add(novo_nome)

    df_display = df_display.rename(columns=colunas_para_renomear)

    if fmt:
        fmt = {colunas_para_renomear.get(k, k): v for k, v in fmt.items()}
    if color_col:
        color_col = colunas_para_renomear.get(color_col, color_col)

    colunas_int_originais = [
        "Executada",
        "Não Executada",
        "Pendente",
        "Baixadas",
        "Total Alocado",
        "Projeção",
        "Alocado",
        "Considerado",
        "OS",
        "GPON",
        "ND",
        "Migração",
        "Qtd_4K",
        "Ultra",
        "Soundbox",
        "Equipe",
        "TOTAL_TAREFAS",
    ]
    colunas_int = [colunas_para_renomear.get(c, c) for c in colunas_int_originais]
    for c in colunas_int:
        if c in df_display.columns:
            df_display[c] = (
                pd.to_numeric(df_display[c], errors="coerce").fillna(0).astype(int)
            )

    styler = df_display.style
    if fmt:
        styler = styler.format(fmt)

    if color_col and color_col in df_display.columns and color_meta is not None:
        colunas_condicionais = [c for c in [color_col] if c != "Quebra Atual"]
        if colunas_condicionais:

            def _cor(val):
                try:
                    v = float(val)
                except (ValueError, TypeError):
                    return ""
                if color_invertido:
                    if v > color_meta:
                        return "background-color:#FEE2E2;color:#991B1B;font-weight:600;"
                    if v > color_meta * 0.85:
                        return "background-color:#FEF9C3;color:#854D0E;font-weight:600;"
                    return "background-color:#DCFCE7;color:#166534;font-weight:600;"
                else:
                    if v >= color_meta:
                        return "background-color:#DCFCE7;color:#166534;font-weight:600;"
                    if v >= color_meta * 0.85:
                        return "background-color:#FEF9C3;color:#854D0E;font-weight:600;"
                    return "background-color:#FEE2E2;color:#991B1B;font-weight:600;"

            styler = styler.map(_cor, subset=pd.Index(colunas_condicionais))

    if "Quebra Atual" in df_display.columns:
        styler = styler.map(
            lambda val: (
                "background-color:#1E293B;color:#FFFFFF;font-weight:600;"
                if not pd.isna(val) and str(val).strip() != ""
                else ""
            ),
            subset=pd.Index(["Quebra Atual"]),
        )

    styler = styler.set_table_styles(
        [
            {
                "selector": "th",
                "props": [
                    ("background-color", "#0F172A"),
                    ("color", "#FFFFFF"),
                    ("font-size", "0.78rem"),
                    ("font-weight", "700"),
                    ("text-transform", "uppercase"),
                    ("letter-spacing", "0.03em"),
                    ("padding", "0.6rem 0.8rem"),
                    ("border", "none"),
                ],
            },
            {
                "selector": "td",
                "props": [
                    ("font-size", "0.82rem"),
                    ("padding", "0.5rem 0.8rem"),
                    ("border-bottom", "1px solid #F1F5F9"),
                ],
            },
            {"selector": "tr:hover td", "props": [("background-color", "#F8FAFC")]},
        ]
    )

    st.dataframe(styler, use_container_width=True, hide_index=True, height=height)


def gerar_excel(df: pd.DataFrame, aba: str = "Dados") -> bytes:
    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df.to_excel(w, index=False, sheet_name=aba[:31])
        ws = w.sheets[aba[:31]]
        hf = PatternFill("solid", fgColor="0F172A")
        for cell in ws[1]:
            cell.fill = hf
            cell.font = Font(color="FFFFFF", bold=True)
        for i in range(1, len(df.columns) + 1):
            ws.column_dimensions[get_column_letter(i)].width = 20
    return out.getvalue()


# ====================================================
# 5. CARREGAMENTO DE DADOS
# ====================================================
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
                return pd.read_csv(
                    bio, sep=None, engine="python", encoding="utf-8-sig", dtype=str
                )
            except UnicodeDecodeError:
                bio.seek(0)
                return pd.read_csv(
                    bio, sep=None, engine="python", encoding="latin1", dtype=str
                )
        return pd.read_excel(bio, engine="openpyxl", dtype=str)
    except Exception as e:
        st.error(f"Erro ao ler arquivo: {e}")
        return pd.DataFrame()


@st.cache_data(show_spinner=False)
def processar_base(df_bruto: pd.DataFrame, df_ativos: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(df_bruto, pd.DataFrame) or df_bruto.empty:
        return pd.DataFrame()
    df = df_bruto.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()

    mapa = {
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
    for padrao, variacoes in mapa.items():
        col = next((c for c in df.columns if c in variacoes), None)
        if col:
            df = df.rename(columns={col: padrao})
        else:
            df[padrao] = np.nan

    contrato = (
        df["CONTRATO"]
        .astype("string")
        .str.replace("\u00a0", " ", regex=False)
        .str.strip()
    )
    mask_vazio = (
        contrato.isna()
        | contrato.eq("")
        | contrato.str.upper().isin(CONTRATO_VALORES_VAZIOS)
    )
    removidos = int(mask_vazio.sum())
    df = df.loc[~mask_vazio].copy()
    df["CONTRATO"] = contrato.loc[df.index].str.upper()

    if df.empty:
        return pd.DataFrame()

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

    if isinstance(df_ativos, pd.DataFrame) and not df_ativos.empty:
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

    hab = df["HABILIDADE"].astype(str).str.upper()
    tipo = df["TIPO_OS"].astype(str).str.upper()
    prod = df["PRODUTO"].astype(str).str.upper()

    df["Check_GPON"] = hab.str.contains(r"PON\(1/100\)", regex=True, na=False)
    df["Check_ND"] = tipo.str.contains("ADESAO", na=False)
    df["Check_Migracao"] = (tipo.str.strip() == "24 - MUDANCA DE PACOTE") & df[
        "Check_GPON"
    ]
    df["Check_Streaming"] = hab.str.contains("TV VAS(1/100)", na=False)
    df["Check_Ponto_Ultra"] = hab.str.contains("NETLAR", na=False)
    df["Check_4K"] = prod.str.contains("4K", na=False)
    df["Check_Soundbox"] = prod.str.contains("SOUND", na=False)

    df["PERIODO_TRATADO"] = (
        df["INTERVALO"]
        .astype(str)
        .str.strip()
        .map(MAPEAMENTO_PERIODOS)
        .fillna("Outros/Sem Período")
    )

    cidade = (
        df["CIDADE"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .apply(
            lambda v: unicodedata.normalize("NFKD", v)
            .encode("ASCII", "ignore")
            .decode()
        )
    )
    df["REGIÃO"] = np.select(
        [
            cidade.isin(["SAO PAULO"]),
            cidade.isin(
                [
                    "GUARULHOS",
                    "ARUJA",
                    "MOGI DAS CRUZES",
                    "SUZANO",
                    "ITAQUAQUECETUBA",
                    "FERRAZ DE VASCONCELOS",
                    "POA",
                ]
            ),
            cidade.isin(
                [
                    "SANTO ANDRE",
                    "SAO BERNARDO DO CAMPO",
                    "SAO CAETANO DO SUL",
                    "DIADEMA",
                    "MAUA",
                    "RIBEIRAO PIRES",
                    "RIO GRANDE DA SERRA",
                ]
            ),
        ],
        ["LESTE", "GRU", "ABCDM"],
        default="OUTRAS",
    )

    df.attrs["diagnostico"] = {"contrato_vazio": removidos}
    return df


# ====================================================
# 6. TABELAS ROTA/TURNO (Rota Inicial, Manhã, Tarde I, Tarde II)
# ====================================================
def _fmt_num_br(v: Any) -> str:
    try:
        return f"{int(v):,}".replace(",", ".")
    except (ValueError, TypeError):
        return "0"


def _fmt_media_br(v: Any) -> str:
    try:
        return f"{float(v):.2f}".replace(".", ",")
    except (ValueError, TypeError):
        return "0,00"


def calcular_tabela_rota_turno(
    df: pd.DataFrame,
    turno: Optional[str] = None,
    total_equipe_montada: Optional[int] = None,
) -> pd.DataFrame:
    """
    Calcula tabela por Monitor com colunas:
    Monitor · WO · GPON · OS · ND · Migração · Equipe · Média

    - OS       = soma real de TOTAL_TAREFAS (alinhado com o KPI de Volume de O.S.)
    - WO / ND  = quantidade de tarefas de Adesão (Check_ND)
    - GPON     = quantidade de tarefas GPON
    - Migração = quantidade de tarefas de Migração (MP GPON)
    - Média    = OS / Equipe
    """
    if df.empty:
        return pd.DataFrame()

    df_work = df.copy()

    if turno:
        df_work = df_work[df_work["PERIODO_TRATADO"] == turno].copy()

    if df_work.empty:
        return pd.DataFrame()

    df_work = df_work[
        ~df_work["Monitor"]
        .astype(str)
        .str.upper()
        .isin({"NAN", "SEM MONITOR", "NÃO MAPEADO", ""})
    ].copy()

    if df_work.empty:
        return pd.DataFrame()

    df_work["TOTAL_TAREFAS"] = (
        pd.to_numeric(df_work["TOTAL_TAREFAS"], errors="coerce").fillna(1).astype(int)
    )

    monitores = sorted(df_work["Monitor"].unique())
    linhas: List[Dict[str, Any]] = []

    for mon in monitores:
        df_mon = df_work[df_work["Monitor"] == mon]

        total_os = int(df_mon["TOTAL_TAREFAS"].sum())
        wo = int(df_mon["Check_ND"].sum())
        gpon = int(df_mon["Check_GPON"].sum())
        mig = int(df_mon["Check_Migracao"].sum())
        nd = wo

        equipe = int(df_mon["LOGIN_TECNICO"].nunique())
        media = total_os / equipe if equipe > 0 else 0.0

        linhas.append(
            {
                "Monitor": mon,
                "WO": wo,
                "GPON": gpon,
                "OS": total_os,
                "ND": nd,
                "Migração": mig,
                "Equipe": equipe,
                "Média": media,
            }
        )

    df_out = pd.DataFrame(linhas)

    total_wo = int(df_out["WO"].sum())
    total_gpon = int(df_out["GPON"].sum())
    total_os = int(df_out["OS"].sum())
    total_nd = int(df_out["ND"].sum())
    total_mig = int(df_out["Migração"].sum())
    total_eq_escalados = int(df_out["Equipe"].sum())

    if total_equipe_montada is not None:
        total_eq_montados = total_equipe_montada
    else:
        total_eq_montados = int(df_work["LOGIN_TECNICO"].nunique())

    media_escalados = total_os / total_eq_escalados if total_eq_escalados > 0 else 0.0
    media_montados = total_os / total_eq_montados if total_eq_montados > 0 else 0.0

    df_out = pd.concat(
        [
            df_out,
            pd.DataFrame(
                [
                    {
                        "Monitor": "Total Geral | Escalados",
                        "WO": total_wo,
                        "GPON": total_gpon,
                        "OS": total_os,
                        "ND": total_nd,
                        "Migração": total_mig,
                        "Equipe": total_eq_escalados,
                        "Média": media_escalados,
                    },
                    {
                        "Monitor": "Total Geral | Montados",
                        "WO": total_wo,
                        "GPON": total_gpon,
                        "OS": total_os,
                        "ND": total_nd,
                        "Migração": total_mig,
                        "Equipe": total_eq_montados,
                        "Média": media_montados,
                    },
                ]
            ),
        ],
        ignore_index=True,
    )

    return df_out


def render_tabela_rota_turno(df: pd.DataFrame, titulo: str) -> str:
    """
    Gera HTML da tabela no padrão visual definido no CSS corporativo.
    """
    if df.empty:
        return (
            f'<div class="rota-wrapper">'
            f'<div class="rota-titulo">{titulo}</div>'
            f'<table class="rota-tab">'
            f'<tr><td colspan="8" style="padding:20px;color:#64748B;text-align:center;">'
            f"Sem dados disponíveis</td></tr>"
            f"</table></div>"
        )

    linhas_html: List[str] = []
    for _, row in df.iterrows():
        monitor = str(row["Monitor"])
        if "Escalados" in monitor:
            classe_linha = "total-escalados"
        elif "Montados" in monitor:
            classe_linha = "total-montados"
        else:
            classe_linha = ""

        linhas_html.append(
            f'<tr class="{classe_linha}">'
            f'<td class="col-monitor">{monitor}</td>'
            f'<td>{_fmt_num_br(row["WO"])}</td>'
            f'<td>{_fmt_num_br(row["GPON"])}</td>'
            f'<td class="col-os">{_fmt_num_br(row["OS"])}</td>'
            f'<td>{_fmt_num_br(row["ND"])}</td>'
            f'<td>{_fmt_num_br(row["Migração"])}</td>'
            f'<td class="col-equipe">{_fmt_num_br(row["Equipe"])}</td>'
            f'<td class="col-media">{_fmt_media_br(row["Média"])}</td>'
            f"</tr>"
        )

    html = (
        f'<div class="rota-wrapper">'
        f'<div class="rota-titulo">{titulo}</div>'
        f'<table class="rota-tab">'
        f"<thead><tr>"
        f'<th style="width:32%;">Monitor</th>'
        f"<th>WO</th>"
        f"<th>GPON</th>"
        f'<th class="th-os">OS</th>'
        f"<th>ND</th>"
        f"<th>Migração</th>"
        f'<th class="th-equipe">Equipe</th>'
        f'<th class="th-media">Média</th>'
        f"</tr></thead>"
        f'<tbody>{"".join(linhas_html)}</tbody>'
        f"</table>"
        f"</div>"
    )
    return html


def render_bloco_rota_turno(df_master: pd.DataFrame, total_montados: int) -> None:
    """
    Renderiza as 4 tabelas: Rota Inicial + Manhã + Tarde I + Tarde II.

    Parâmetros:
        df_master: base de dados filtrada
        total_montados: total de técnicos montados (informado manualmente pelo usuário)
    """
    from datetime import datetime

    data_hoje = datetime.now().strftime("%d/%m/%Y")

    # Se o usuário não informou (=0), usa a contagem automática
    total_calc_auto = int(df_master["LOGIN_TECNICO"].nunique())
    total_efetivo = total_montados if total_montados > 0 else total_calc_auto

    # 1. Rota Inicial (dia todo)
    df_rota = calcular_tabela_rota_turno(
        df_master, turno=None, total_equipe_montada=total_efetivo
    )
    st.markdown(
        render_tabela_rota_turno(df_rota, f"Rota Inicial - {data_hoje}"),
        unsafe_allow_html=True,
    )

    # 2. Manhã
    df_manha = calcular_tabela_rota_turno(
        df_master, turno="Manhã", total_equipe_montada=total_efetivo
    )
    st.markdown(
        render_tabela_rota_turno(df_manha, f"Manhã - {data_hoje}"),
        unsafe_allow_html=True,
    )

    # 3. Tarde I
    df_t1 = calcular_tabela_rota_turno(
        df_master, turno="Tarde I", total_equipe_montada=total_efetivo
    )
    st.markdown(
        render_tabela_rota_turno(df_t1, f"Tarde I - {data_hoje}"),
        unsafe_allow_html=True,
    )

    # 4. Tarde II
    df_t2 = calcular_tabela_rota_turno(
        df_master, turno="Tarde II", total_equipe_montada=total_efetivo
    )
    st.markdown(
        render_tabela_rota_turno(df_t2, f"Tarde II - {data_hoje}"),
        unsafe_allow_html=True,
    )


# ====================================================
# 7. APLICAÇÃO PRINCIPAL
# ====================================================
def main():
    aplicar_estilo()

    st.markdown(
        dedent("""
            <div class="hero-corp">
                <div style="position:relative;z-index:2;">
                    <h1 class="hero-title">🗺️ Gestão de Rota Inicial</h1>
                    <p class="hero-subtitle">
                        Visão operacional de rotas, serviços premium e distribuição de equipes
                    </p>
                </div>
            </div>
        """).strip(),
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("⚙️ Configurações")
        if st.button("🔄 Reiniciar Painel", use_container_width=True):
            st.session_state["df_master"] = None
            st.rerun()
        st.divider()

    if st.session_state["df_master"] is None:
        render_section("📁 Importação de Dados")
        arq = st.file_uploader("Selecione a base (Excel/CSV)", type=["xlsx", "csv"])
        if arq:
            with st.spinner("Processando..."):
                raw = ler_arquivo(arq.getvalue(), arq.name)
                gs = buscar_google_sheets()
                df_proc = processar_base(raw, gs)
                st.session_state["df_master"] = df_proc

            diag = df_proc.attrs.get("diagnostico", {})
            if diag.get("contrato_vazio", 0) > 0:
                st.toast(
                    f"🗑️ {diag['contrato_vazio']} linha(s) sem contrato removida(s).",
                    icon="⚠️",
                )
            st.rerun()
        return

    df_master = st.session_state["df_master"].copy()

    with st.sidebar:
        st.header("👥 Equipe Montada")
        total_montados_input = st.number_input(
            "Total de Técnicos Montados",
            min_value=0,
            max_value=999,
            value=st.session_state["total_montados_manual"],
            step=1,
            help="Informe o total real de técnicos montados no dia. "
            "Deixe em 0 para usar a contagem automática da base.",
            key="input_total_montados",
        )
        st.session_state["total_montados_manual"] = total_montados_input

        if total_montados_input > 0:
            st.caption(
                f"✅ Usando **{total_montados_input}** técnicos montados (manual)"
            )
        else:
            auto_count = int(df_master["LOGIN_TECNICO"].nunique())
            st.caption(f"🔄 Usando **{auto_count}** técnicos (automático da base)")

        st.divider()
        st.header("🎯 Filtros")

        periodos = st.selectbox(
            "⏰ Período", ["Todos"] + sorted(df_master["PERIODO_TRATADO"].unique())
        )

        st.divider()
        st.subheader("🎛️ Filtros Premium")
        if st.checkbox("🟢 Apenas Adesão (ND)"):
            df_master = df_master[df_master["Check_ND"]]
        if st.checkbox("🔄 Apenas Migração (MP GPON)"):
            df_master = df_master[df_master["Check_Migracao"]]
        if st.checkbox("📡 Requer GPON"):
            df_master = df_master[df_master["Check_GPON"]]
        if st.checkbox("📺 Requer Streaming"):
            df_master = df_master[df_master["Check_Streaming"]]
        if st.checkbox("📺 Requer 4K"):
            df_master = df_master[df_master["Check_4K"]]
        if st.checkbox("🔌 Requer Ponto Ultra"):
            df_master = df_master[df_master["Check_Ponto_Ultra"]]
        if st.checkbox("🔊 Requer Soundbox"):
            df_master = df_master[df_master["Check_Soundbox"]]

    if df_master.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    regioes = (
        sorted(df_master["REGIÃO"].unique()) if "REGIÃO" in df_master.columns else []
    )
    render_resultado_base(regioes, len(df_master))

    # ── KPIs Principais ──────────────────────────────
    soma_os = int(df_master["TOTAL_TAREFAS"].sum())
    tecnicos = df_master["LOGIN_TECNICO"].nunique()
    monitores_qtd = df_master["Monitor"].nunique()

    c1, c2, c3 = st.columns(3)
    render_kpi(c1, "Volume O.S.", f"{soma_os:,}", tema="azul")
    render_kpi(
        c2,
        "Técnicos Operando",
        f"{tecnicos}",
        sub=f"Média: {soma_os / tecnicos:.1f} O.S./Téc." if tecnicos else "",
        tema="escuro",
    )
    render_kpi(c3, "Monitores", f"{monitores_qtd}", tema="roxo")

    st.markdown("")

    s1, s2, s3, s4 = st.columns(4)
    render_kpi(s1, "GPON", f"{int(df_master['Check_GPON'].sum()):,}", tema="verde")
    render_kpi(s2, "Adesão (ND)", f"{int(df_master['Check_ND'].sum()):,}", tema="azul")
    render_kpi(s3, "4K", f"{int(df_master['Check_4K'].sum()):,}", tema="roxo")
    render_kpi(
        s4, "Soundbox", f"{int(df_master['Check_Soundbox'].sum()):,}", tema="cinza"
    )

    st.markdown("")

    # ── ✅ BLOCO: Tabelas Rota Inicial + Turnos ──────────────
    render_section("🗺️ Distribuição por Monitor e Turno")
    render_bloco_rota_turno(df_master, st.session_state["total_montados_manual"])

    # ── Gráficos Executivos ───────────────────────────
    render_section("📈 Visão Executiva")
    g1, g2 = st.columns([1, 1.2])

    with g1:
        df_per = (
            df_master.groupby("PERIODO_TRATADO")["TOTAL_TAREFAS"].sum().reset_index()
        )
        fig_per = px.bar(
            df_per,
            x="PERIODO_TRATADO",
            y="TOTAL_TAREFAS",
            text_auto=True,
            color="PERIODO_TRATADO",
            color_discrete_sequence=["#1E3A8A", "#0EA5E9", "#F59E0B", "#10B981"],
        )
        fig_per.update_layout(
            showlegend=False,
            margin=dict(t=30, b=0, l=0, r=0),
            height=320,
            xaxis_title="",
            yaxis_title="",
            title=dict(text="Pico de Agendamento", font=dict(size=14)),
        )
        st.plotly_chart(fig_per, use_container_width=True)

    with g2:
        df_prem = pd.DataFrame(
            [
                {"Serviço": "GPON", "Qtd": int(df_master["Check_GPON"].sum())},
                {"Serviço": "4K", "Qtd": int(df_master["Check_4K"].sum())},
                {"Serviço": "Soundbox", "Qtd": int(df_master["Check_Soundbox"].sum())},
                {
                    "Serviço": "Ponto Ultra",
                    "Qtd": int(df_master["Check_Ponto_Ultra"].sum()),
                },
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
                margin=dict(t=30, b=0, l=0, r=0),
                height=320,
                xaxis_title="",
                yaxis_title="",
                title=dict(text="Mix Premium", font=dict(size=14)),
            )
            st.plotly_chart(fig_prem, use_container_width=True)
        else:
            st.info("Nenhum serviço premium identificado.")

    # ── Abas de Detalhamento ──────────────────────────
    aba_tec, aba_mapa, aba_base, aba_contratos = st.tabs(
        ["🏆 Top Técnicos", "🗺️ Mapa", "🗃️ Base Completa", "📄 Resumo Contratos"]
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
        fig_tec.update_layout(
            yaxis={"categoryorder": "total ascending"},
            height=500,
            title=dict(text="Top 15 Técnicos por Volume", font=dict(size=15)),
            margin=dict(t=50, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_tec, use_container_width=True)

    with aba_mapa:
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
                    height=550,
                    hover_name="NOME_OFICIAL",
                )
                fig_mapa.update_layout(
                    mapbox_style="open-street-map",
                    margin={"r": 0, "t": 0, "l": 0, "b": 0},
                )
                st.plotly_chart(fig_mapa, use_container_width=True)
            else:
                st.info("Coordenadas GPS não encontradas.")
        else:
            st.info("A planilha não possui coordenadas GPS válidas para o mapa.")

    with aba_base:
        render_dataframe(
            df_master.head(500),
            titulo="Base de Dados (prévia — 500 linhas)",
            icone="🗃️",
            badge=f"{len(df_master)} total",
            height=600,
        )
        st.download_button(
            "📥 Baixar Base Completa",
            gerar_excel(df_master, "Base"),
            "base_completa.xlsx",
        )

    with aba_contratos:
        render_section("📄 Resumo dos Contratos da Rota")

        COLUNAS_CONTRATOS: Dict[str, List[str]] = {
            "CONTRATO": ["CONTRATO"],
            "INTERVALO": ["PERIODO_TRATADO", "INTERVALO"],
            "CEP": ["CEP/CÓDIGO POSTAL", "CEP", "CODIGO POSTAL"],
            "ÁREA TRABALHO": ["ÁREA DE TRABALHO", "AREA DE TRABALHO"],
            "TIPO OS": ["TIPO_OS", "TIPO O.S 1", "TIPO OS 1"],
            "TÉCNICO": ["NOME_OFICIAL"],
            "MONITOR": ["Monitor"],
        }

        colunas_encontradas: Dict[str, str] = {}
        for nome_amigavel, aliases in COLUNAS_CONTRATOS.items():
            for alias in aliases:
                if alias in df_master.columns:
                    colunas_encontradas[alias] = nome_amigavel
                    break

        if not colunas_encontradas:
            st.warning("Nenhuma das colunas esperadas foi encontrada na base.")
        else:
            df_contratos = (
                df_master[list(colunas_encontradas.keys())]
                .rename(columns=colunas_encontradas)
                .copy()
            )

            col_f1, col_f2, col_info = st.columns([2, 2, 3])

            with col_f1:
                mon_contratos = ["Todos"] + sorted(
                    [
                        str(x)
                        for x in df_contratos["MONITOR"].dropna().unique()
                        if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
                    ]
                    if "MONITOR" in df_contratos.columns
                    else []
                )
                sel_mon_contratos = st.selectbox(
                    "👔 Monitor",
                    mon_contratos,
                    key="filtro_mon_contratos",
                )

            df_contratos_filtrado = (
                df_contratos[df_contratos["MONITOR"] == sel_mon_contratos].copy()
                if sel_mon_contratos != "Todos"
                else df_contratos.copy()
            )

            with col_f2:
                tec_contratos = ["Todos"] + sorted(
                    [
                        str(x)
                        for x in df_contratos_filtrado["TÉCNICO"].dropna().unique()
                        if str(x) not in {"nan", "NÃO MAPEADO"}
                    ]
                    if "TÉCNICO" in df_contratos_filtrado.columns
                    else []
                )
                sel_tec_contratos = st.selectbox(
                    "👤 Técnico",
                    tec_contratos,
                    key="filtro_tec_contratos",
                )

            if sel_tec_contratos != "Todos":
                df_contratos_filtrado = df_contratos_filtrado[
                    df_contratos_filtrado["TÉCNICO"] == sel_tec_contratos
                ].copy()

            with col_info:
                st.markdown("")
                st.markdown(
                    f"**{len(df_contratos_filtrado):,}** contratos exibidos "
                    f"de **{len(df_contratos):,}** total"
                )

            render_dataframe(
                df_contratos_filtrado,
                titulo="Resumo Contratos",
                icone="📄",
                badge=f"{len(df_contratos_filtrado)} contratos",
                height=600,
            )

            st.download_button(
                "📥 Baixar Resumo Contratos",
                gerar_excel(df_contratos_filtrado, "Resumo Contratos"),
                "ordens_servico.xlsx",
            )


if __name__ == "__main__":
    main()
