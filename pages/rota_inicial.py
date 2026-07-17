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
    # Rota Inicial
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
        .hero {
            background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);
            padding: 2rem; border-radius: 1rem;
            color: white; margin-bottom: 2rem;
        }

        .kpi-card {
            padding: 1.4rem 1.6rem; border-radius: 1rem;
            border-left: 5px solid;
            box-shadow: 0 4px 12px rgba(0,0,0,0.06);
            transition: transform 0.15s ease, box-shadow 0.15s ease;
            min-height: 110px;
            display: flex; flex-direction: column; justify-content: center;
        }
        .kpi-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 8px 20px rgba(0,0,0,0.1);
        }
        .kpi-val { font-size: 1.85rem; font-weight: 800; line-height: 1.1; margin: 0.3rem 0; }
        .kpi-lab { font-size: 0.72rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em; }
        .kpi-sub { font-size: 0.78rem; margin-top: 0.2rem; }

        .resultado-base {
            background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);
            padding: 1rem 1.5rem; border-radius: 0.75rem;
            margin-bottom: 1.5rem;
            display: flex; align-items: center; flex-wrap: wrap; gap: 0.6rem;
        }
        .resultado-base-label {
            color: #94A3B8; font-size: 0.8rem; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.08em; margin-right: 0.3rem;
        }
        .resultado-base-regiao {
            padding: 0.3rem 0.9rem; border-radius: 999px;
            font-size: 0.82rem; font-weight: 700;
            letter-spacing: 0.04em; border: 2px solid;
        }
        .resultado-base-count {
            color: #64748B; font-size: 0.72rem;
            margin-left: auto; font-weight: 600;
        }

        .styled-table-wrapper {
            background: #FFFFFF; border-radius: 0.75rem;
            padding: 1rem 1.2rem;
            box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            margin-bottom: 0.5rem;
        }
        .styled-table-title {
            font-size: 1rem; font-weight: 700; color: #0F172A;
            margin-bottom: 0.4rem;
            display: flex; align-items: center; gap: 0.5rem;
        }
        .styled-table-badge {
            font-size: 0.68rem; background: #E0F2FE; color: #0369A1;
            padding: 0.15rem 0.5rem; border-radius: 999px; font-weight: 600;
        }

        div[data-testid="stDataFrame"] > div {
            border-radius: 0.5rem; overflow: hidden;
        }

        .section-header {
            display: flex; align-items: center; gap: 0.6rem;
            margin: 1.5rem 0 0.8rem; padding-bottom: 0.4rem;
            border-bottom: 2px solid #E2E8F0;
        }
        .section-header h3 { margin: 0; font-size: 1.1rem; color: #0F172A; }
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

    # ── Renomear colunas para títulos amigáveis (sem duplicatas) ─────
    colunas_para_renomear = {}
    nomes_existentes = set(df_display.columns)
    nomes_ja_usados = set()

    for col_original in df_display.columns:
        if col_original in RENOMEAR_COLUNAS:
            novo_nome = RENOMEAR_COLUNAS[col_original]
            # Só renomeia se o novo nome não já existir como outra coluna
            # e se não foi usado por outra renomeação anterior
            if novo_nome == col_original or (  # mesmo nome, ignora
                novo_nome not in nomes_existentes and novo_nome not in nomes_ja_usados
            ):
                colunas_para_renomear[col_original] = novo_nome
                nomes_ja_usados.add(novo_nome)

    df_display = df_display.rename(columns=colunas_para_renomear)

    # Atualizar referências de fmt e color_col com os novos nomes
    if fmt:
        fmt = {colunas_para_renomear.get(k, k): v for k, v in fmt.items()}
    if color_col:
        color_col = colunas_para_renomear.get(color_col, color_col)

    # ── Converter colunas numéricas float → int ─────────────────────
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
    # Mapear nomes originais para renomeados
    colunas_int = [colunas_para_renomear.get(c, c) for c in colunas_int_originais]
    for c in colunas_int:
        if c in df_display.columns:
            df_display[c] = (
                pd.to_numeric(df_display[c], errors="coerce").fillna(0).astype(int)
            )

    styler = df_display.style

    if fmt:
        styler = styler.format(fmt)

    # ── Cor condicional ─────────────────────────────────────────────
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

    # ── Estilo fixo Quebra Atual ────────────────────────────────────
    if "Quebra Atual" in df_display.columns:
        styler = styler.map(
            lambda val: (
                "background-color:#1E293B;color:#FFFFFF;font-weight:600;"
                if not pd.isna(val) and str(val).strip() != ""
                else ""
            ),
            subset=pd.Index(["Quebra Atual"]),
        )

    # ── Header estilizado ───────────────────────────────────────────
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

    # Mapeamento de colunas
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

    # Contratos vazios
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

    # ❌ REMOVIDO daqui: st.toast(...) — não pode existir em função cacheada

    if df.empty:
        return pd.DataFrame()

    # Limpeza
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

    # Merge GSheets
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

    # Flags premium
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

    # Período
    df["PERIODO_TRATADO"] = (
        df["INTERVALO"]
        .astype(str)
        .str.strip()
        .map(MAPEAMENTO_PERIODOS)
        .fillna("Outros/Sem Período")
    )

    # Regiões
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

    # ✅ Contagem transportada via attrs (seguro no cache)
    df.attrs["diagnostico"] = {"contrato_vazio": removidos}
    return df


# ====================================================
# 6. APLICAÇÃO PRINCIPAL
# ====================================================
def main():
    aplicar_estilo()

    # ── Hero ──────────────────────────────────────────
    st.markdown(
        '<div class="hero">'
        "<h1>🗺️ Gestão de Rota Inicial</h1>"
        "<p>Visão operacional de rotas, serviços premium e distribuição de equipes</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Sidebar ───────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configurações")
        if st.button("🔄 Reiniciar Painel", use_container_width=True):
            st.session_state["df_master"] = None
            st.rerun()
        st.divider()

    # ── Upload ────────────────────────────────────────
    if st.session_state["df_master"] is None:
        render_section("📁 Importação de Dados")
        arq = st.file_uploader("Selecione a base (Excel/CSV)", type=["xlsx", "csv"])
        if arq:
            with st.spinner("Processando..."):
                raw = ler_arquivo(arq.getvalue(), arq.name)
                gs = buscar_google_sheets()
                df_proc = processar_base(raw, gs)
                st.session_state["df_master"] = df_proc

            # ✅ Toast fora da função cacheada
            diag = df_proc.attrs.get("diagnostico", {})
            if diag.get("contrato_vazio", 0) > 0:
                st.toast(
                    f"🗑️ {diag['contrato_vazio']} linha(s) sem contrato removida(s).",
                    icon="⚠️",
                )

            st.rerun()
        return

    df_master = st.session_state["df_master"].copy()

    # ── Sidebar Filtros ───────────────────────────────
    with st.sidebar:
        st.header("🎯 Filtros")

        periodos = st.selectbox(
            "⏰ Período", ["Todos"] + sorted(df_master["PERIODO_TRATADO"].unique())
        )
        if periodos != "Todos":
            df_master = df_master[df_master["PERIODO_TRATADO"] == periodos]

        monitores_lista = sorted(df_master["Monitor"].dropna().unique())
        monitores = st.multiselect("👨‍💼 Monitor", monitores_lista)
        if monitores:
            df_master = df_master[df_master["Monitor"].isin(monitores)]

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

    # ── Subheader Resultado da Base ───────────────────
    regioes = (
        sorted(df_master["REGIÃO"].unique()) if "REGIÃO" in df_master.columns else []
    )
    render_resultado_base(regioes, len(df_master))

    # ── KPIs Principais ──────────────────────────────
    soma_os = int(df_master["TOTAL_TAREFAS"].sum())
    tecnicos = df_master["LOGIN_TECNICO"].nunique()
    monitores_qtd = df_master["Monitor"].nunique()
    os_concluidas = int(
        df_master[
            df_master["STATUS_ATIVIDADE"].isin(
                ["CONCLUÍDO", "CONCLUIDO", "EXECUTADA", "BAIXADA", "REALIZADA"]
            )
        ]["TOTAL_TAREFAS"].sum()
    )
    tx = os_concluidas / soma_os if soma_os > 0 else 0
    tema_tx = "verde" if tx > 0.5 else "laranja" if tx > 0.2 else "vermelho"

    c1, c2, c3, c4 = st.columns(4)
    render_kpi(c1, "Volume O.S.", f"{soma_os:,}", tema="azul")
    render_kpi(
        c2,
        "Técnicos Operando",
        f"{tecnicos}",
        sub=f"Média: {soma_os / tecnicos:.1f} O.S./Téc." if tecnicos else "",
        tema="escuro",
    )
    render_kpi(c3, "Monitores", f"{monitores_qtd}", tema="roxo")
    render_kpi(
        c4,
        "Andamento do Dia",
        f"{os_concluidas:,}",
        sub=f"{tx:.1%} concluídas",
        tema=tema_tx,
    )

    st.markdown("")

    # KPIs Premium
    s1, s2, s3, s4 = st.columns(4)
    render_kpi(s1, "GPON", f"{int(df_master['Check_GPON'].sum()):,}", tema="verde")
    render_kpi(s2, "Adesão (ND)", f"{int(df_master['Check_ND'].sum()):,}", tema="azul")
    render_kpi(s3, "4K", f"{int(df_master['Check_4K'].sum()):,}", tema="roxo")
    render_kpi(
        s4, "Soundbox", f"{int(df_master['Check_Soundbox'].sum()):,}", tema="cinza"
    )

    st.markdown("")

    # ── Gráficos Executivos ───────────────────────────
    render_section("📈 Visão Executiva")
    g1, g2, g3 = st.columns([1, 1, 1.2])

    with g1:
        df_status = (
            df_master.groupby("STATUS_ATIVIDADE")["TOTAL_TAREFAS"].sum().reset_index()
        )
        fig_stat = px.pie(
            df_status,
            names="STATUS_ATIVIDADE",
            values="TOTAL_TAREFAS",
            hole=0.5,
            color_discrete_sequence=px.colors.qualitative.Prism,
        )
        fig_stat.update_layout(
            showlegend=False,
            margin=dict(t=30, b=0, l=0, r=0),
            height=300,
            title=dict(text="Status da Frota", font=dict(size=14)),
        )
        st.plotly_chart(fig_stat, use_container_width=True)

    with g2:
        df_per = (
            df_master.groupby("PERIODO_TRATADO")["TOTAL_TAREFAS"].sum().reset_index()
        )
        fig_per = px.bar(
            df_per,
            x="PERIODO_TRATADO",
            y="TOTAL_TAREFAS",
            text_auto=True,
            color="PERIODO_TRATADO",
            color_discrete_sequence=["#0EA5E9", "#F59E0B", "#F97316", "#8B5CF6"],
        )
        fig_per.update_layout(
            showlegend=False,
            margin=dict(t=30, b=0, l=0, r=0),
            height=300,
            xaxis_title="",
            yaxis_title="",
            title=dict(text="Pico de Agendamento", font=dict(size=14)),
        )
        st.plotly_chart(fig_per, use_container_width=True)

    with g3:
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
                height=300,
                xaxis_title="",
                yaxis_title="",
                title=dict(text="Mix Premium", font=dict(size=14)),
            )
            st.plotly_chart(fig_prem, use_container_width=True)
        else:
            st.info("Nenhum serviço premium identificado.")

    # ── Abas de Detalhamento ──────────────────────────
    aba_mon, aba_tec, aba_mapa, aba_base, aba_contratos = st.tabs(
        [
            "📋 Monitores",
            "🏆 Top Técnicos",
            "🗺️ Mapa",
            "🗃️ Base Completa",
            "📄 Resumo Contratos",
        ]
    )

    with aba_mon:
        df_resumo = (
            df_master.groupby("Monitor")
            .agg(
                OS=("TOTAL_TAREFAS", "sum"),
                GPON=("Check_GPON", "sum"),
                ND=("Check_ND", "sum"),
                Migração=("Check_Migracao", "sum"),
                Qtd_4K=("Check_4K", "sum"),
                Ultra=("Check_Ponto_Ultra", "sum"),
                Soundbox=("Check_Soundbox", "sum"),
                Equipe=("LOGIN_TECNICO", "nunique"),
            )
            .reset_index()
        )
        df_resumo["Média"] = np.where(
            df_resumo["Equipe"] > 0, df_resumo["OS"] / df_resumo["Equipe"], 0
        )
        df_resumo = df_resumo.sort_values("OS", ascending=False).reset_index(drop=True)

        render_dataframe(
            df_resumo,
            titulo="Volumetria por Monitor",
            icone="📋",
            fmt={"Média": "{:.1f}"},
            height=150,
        )
        st.download_button(
            "📥 Baixar Tabela Monitores",
            gerar_excel(df_resumo, "Monitores"),
            "monitores.xlsx",
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

        # ── Mapeamento das colunas necessárias ────────────────────────
        # Os aliases devem refletir os nomes APÓS processar_base()
        COLUNAS_CONTRATOS: Dict[str, List[str]] = {
            "CONTRATO": ["CONTRATO"],
            "INTERVALO": ["PERIODO_TRATADO", "INTERVALO"],
            "CEP": ["CEP/CÓDIGO POSTAL", "CEP", "CODIGO POSTAL"],
            "ÁREA TRABALHO": ["ÁREA DE TRABALHO", "AREA DE TRABALHO"],
            "TIPO OS": ["TIPO_OS", "TIPO O.S 1", "TIPO OS 1"],
            "TÉCNICO": ["NOME_OFICIAL"],
            "MONITOR": ["Monitor"],
        }

        # ── Montar DataFrame apenas com as colunas disponíveis ────────
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

            # ── Filtros em cascata: Monitor → Técnico ─────────────────
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
