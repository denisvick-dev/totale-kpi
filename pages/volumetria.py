from __future__ import annotations

import html
import textwrap
import re
import unicodedata
from io import BytesIO
from typing import Any, Dict, List, Literal, Optional

import numpy as np
import pandas as pd
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from streamlit_gsheets import GSheetsConnection
import streamlit as st

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

    COL_STATUS = "STATUS CONTRATO"
    COL_TOTAL = "TOTAL DE TAREFAS"
    COL_TECNICO = "TÉCNICO"
    COL_MONITOR = "MONITOR"
    COL_REGIAO = "REGIÃO"

    CORES_STATUS = {
        "Executada": "#10B981",
        "Não Executada": "#EF4444",
        "Pendente": "#F59E0B",
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
    "laranja": {"fundo": "#FFF7ED", "texto": "#C2410C", "borda": "#F97316", "titulo": "#9A3412"},
}

CORES_REGIAO: Dict[str, Dict[str, str]] = {
    "LESTE":  {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
    "GRU":    {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
    "ABCDM":  {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
    "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
}

RENOMEAR_COLUNAS: Dict[str, str] = {
    "TÉCNICO": "Técnico", "MONITOR": "Monitor", "REGIÃO": "Região",
    "STATUS CONTRATO": "Status", "TOTAL DE TAREFAS": "Total de O.S.",
    "Executada": "Executadas", "Não Executada": "Não Exec.",
    "Pendente": "Pendentes", "Baixadas": "Baixadas",
    "Total Alocado": "Total Alocado", "Taxa Execução": "Taxa Exec.",
    "Taxa Quebra": "Taxa Quebra", "Projeção": "Projeção",
    "Nao_Executadas": "Não Exec.", "Executadas": "Executadas",
    "Pendentes": "Pendentes", "Total_Alocado": "Total Alocado",
    "Técnicos": "Técnicos", "OS/Técnico": "OS/Técnico",
    "Exec/Técnico": "Exec/Técnico",
}

COLUNAS_INTEIRAS = [
    "Executada", "Não Executada", "Pendente", "Baixadas",
    "Total Alocado", "Projeção", "Executadas", "Não Exec.",
    "Pendentes", "Técnicos",
]


# ==========================================================
# UTILITÁRIOS
# ==========================================================
class Utils:
    @staticmethod
    def remover_acentos(valor) -> str:
        if pd.isna(valor):
            return ""
        return unicodedata.normalize("NFKD", str(valor)).encode("ASCII", "ignore").decode("ASCII")

    @staticmethod
    def normalizar_chave(serie: pd.Series) -> pd.Series:
        s = serie.copy()
        return (
            s.where(s.notna(), "")
            .astype(str)
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
            chave = Utils.normalizar_chave(pd.Series([alias]))[0]
            if chave in cols_map:
                return cols_map[chave]
        return None

    @staticmethod
    def classificar_status(status_os: pd.Series) -> pd.Series:
        s = Utils.normalizar_chave(status_os)
        nao_exec = s.str.contains(r"NAO\s*EXECUT", regex=True, na=False)
        exec_ = s.str.contains(r"EXECUT", regex=True, na=False) & ~nao_exec
        return pd.Series(
            np.select(
                [exec_, nao_exec],
                ["Executada", "Não Executada"],
                default="Pendente",
            ),
            index=status_os.index,
            dtype="object",
        )

    @staticmethod
    def contrato_valido(serie: pd.Series) -> pd.Series:
        norm = serie.astype(str).str.strip().str.upper().apply(Utils.remover_acentos)
        return ~norm.isin(Config.CONTRATO_VALORES_VAZIOS)

    @staticmethod
    def resolver_renomeacao(df: pd.DataFrame, mapa: Dict[str, str]) -> Dict[str, str]:
        existentes = set(df.columns)
        usados: set[str] = set()
        resultado: Dict[str, str] = {}
        for col in df.columns:
            if col not in mapa:
                continue
            novo = mapa[col]
            if novo == col or novo in existentes or novo in usados:
                continue
            resultado[col] = novo
            usados.add(novo)
        return resultado


# ==========================================================
# CARREGAMENTO
# ==========================================================
class DataLoader:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
        if not file_bytes:
            raise ValueError("O arquivo enviado está vazio.")

        nome = filename.lower()
        if nome.endswith(".xlsx"):
            return pd.read_excel(BytesIO(file_bytes), engine="openpyxl")
        if nome.endswith(".xls"):
            return pd.read_excel(BytesIO(file_bytes))
        if nome.endswith(".csv"):
            try:
                return pd.read_csv(BytesIO(file_bytes), sep=None, engine="python", encoding="utf-8-sig")
            except UnicodeDecodeError:
                return pd.read_csv(BytesIO(file_bytes), sep=None, engine="python", encoding="latin1")
        raise ValueError("Formato não suportado. Use .xlsx, .xls ou .csv.")

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_hierarquia_gsheets() -> pd.DataFrame:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            raw = conn.read(spreadsheet=Config.URL_GSHEETS)
            if raw is None or raw.empty:
                return pd.DataFrame()
            col_login = Utils.buscar_coluna(raw, ["LOGIN", "MATRÍCULA", "ID"])
            col_tec = Utils.buscar_coluna(raw, ["TÉCNICO", "NOME"])
            col_mon = Utils.buscar_coluna(raw, ["MONITOR", "GESTOR"])
            if not col_login:
                return pd.DataFrame()
            df_gs = pd.DataFrame({
                "__LOGIN_KEY": Utils.normalizar_login(raw[col_login]),
                "__TEC_GS": raw[col_tec] if col_tec else "",
                "__MON_GS": raw[col_mon] if col_mon else "",
            })
            return df_gs.drop_duplicates("__LOGIN_KEY")
        except Exception:
            return pd.DataFrame()

    @staticmethod
    def preparar_base(df: pd.DataFrame, df_gs: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        diag = {"Inicial": len(df)}

        col_con = Utils.buscar_coluna(df, ["CONTRATO", "Nº CONTRATO", "NUMERO CONTRATO", "NUM CONTRATO"])
        if col_con:
            valida = Utils.contrato_valido(df[col_con])
            rem = (~valida).sum()
            df = df[valida].copy()
            diag["Removidos por contrato vazio"] = int(rem)
            if rem > 0:
                st.toast(f"🗑️ {rem} linha(s) removida(s) por contrato vazio.", icon="⚠️")
        else:
            st.warning("⚠️ Coluna de contrato não encontrada.")

        col_atv = Utils.buscar_coluna(df, ["STATUS DA ATIVIDADE"])
        if col_atv:
            susp = Utils.normalizar_chave(df[col_atv]).str.contains("SUSP", na=False)
            df = df[~susp].copy()

        col_os1 = Utils.buscar_coluna(df, ["STATUS DA O.S 1", "STATUS OS 1"])
        if not col_os1:
            st.error("Coluna 'Status da O.S 1' não encontrada!")
            st.stop()
        df[Config.COL_STATUS] = Utils.classificar_status(df[col_os1])

        col_qtd = Utils.buscar_coluna(df, ["TOTAL DE TAREFAS", "QUANTIDADE"])
        if col_qtd:
            df[Config.COL_TOTAL] = pd.to_numeric(df[col_qtd], errors="coerce").fillna(1)
        else:
            df[Config.COL_TOTAL] = 1
        df[Config.COL_TOTAL] = df[Config.COL_TOTAL].clip(lower=0)

        col_log = Utils.buscar_coluna(df, ["LOGIN DO TÉCNICO", "LOGIN", "USUÁRIO"])
        if col_log and not df_gs.empty:
            df["__LOGIN_KEY"] = Utils.normalizar_login(df[col_log])
            df = df.merge(df_gs, on="__LOGIN_KEY", how="left")
        for c in ("__TEC_GS", "__MON_GS"):
            if c not in df.columns:
                df[c] = np.nan

        col_tec_b = Utils.buscar_coluna(df, ["TÉCNICO", "NOME"]) or col_log
        col_mon_b = Utils.buscar_coluna(df, ["MONITOR", "GESTOR"])

        base_tec = df[col_tec_b] if col_tec_b else pd.Series(np.nan, index=df.index)
        base_mon = df[col_mon_b] if col_mon_b else pd.Series(np.nan, index=df.index)

        tec_gs = df["__TEC_GS"].where(df["__TEC_GS"].notna(), "")
        mon_gs = df["__MON_GS"].where(df["__MON_GS"].notna(), "")
        df[Config.COL_TECNICO] = tec_gs.mask(tec_gs.astype(str).str.strip().eq(""), base_tec)
        df[Config.COL_MONITOR] = mon_gs.mask(mon_gs.astype(str).str.strip().eq(""), base_mon)
        df[Config.COL_TECNICO] = df[Config.COL_TECNICO].where(
            df[Config.COL_TECNICO].notna() & df[Config.COL_TECNICO].astype(str).str.strip().ne(""),
            "NÃO MAPEADO",
        )
        df[Config.COL_MONITOR] = df[Config.COL_MONITOR].where(
            df[Config.COL_MONITOR].notna() & df[Config.COL_MONITOR].astype(str).str.strip().ne(""),
            "SEM MONITOR",
        )

        col_cid = Utils.buscar_coluna(df, ["CIDADE", "LOCALIDADE"])
        cidade = Utils.normalizar_chave(df[col_cid]) if col_cid else pd.Series("", index=df.index)
        df[Config.COL_REGIAO] = np.select(
            [
                cidade.isin(["SAO PAULO"]),
                cidade.isin(["GUARULHOS", "ARUJA", "MOGI DAS CRUZES", "SUZANO", "ITAQUAQUECETUBA", "FERRAZ DE VASCONCELOS", "POA"]),
                cidade.isin(["SANTO ANDRE", "SAO BERNARDO DO CAMPO", "SAO CAETANO DO SUL", "DIADEMA", "MAUA", "RIBEIRAO PIRES", "RIO GRANDE DA SERRA"]),
            ],
            ["LESTE", "GRU", "ABCDM"],
            default="OUTRAS",
        )

        diag["Final"] = len(df)
        df.attrs["diagnostico"] = diag
        return df


# ==========================================================
# CÁLCULOS
# ==========================================================
def calcular_kpis(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {
            "total": 0, "executadas": 0, "nao_executadas": 0,
            "pendentes": 0, "baixadas": 0, "taxa": 0.0,
            "quebra": 0.0, "projecao": 0,
        }
    k_tot = int(round(df[Config.COL_TOTAL].sum()))
    k_exe = int(df[df[Config.COL_STATUS] == "Executada"][Config.COL_TOTAL].sum())
    k_nex = int(df[df[Config.COL_STATUS] == "Não Executada"][Config.COL_TOTAL].sum())
    k_pen = int(df[df[Config.COL_STATUS] == "Pendente"][Config.COL_TOTAL].sum())
    k_bai = k_exe + k_nex
    k_tx = k_exe / k_bai if k_bai > 0 else 0.0
    k_proj = int(k_exe + k_tx * k_pen)
    return {
        "total": k_tot, "executadas": k_exe, "nao_executadas": k_nex,
        "pendentes": k_pen, "baixadas": k_bai, "taxa": k_tx,
        "quebra": 1.0 - k_tx, "projecao": k_proj,
    }


def calcular_volumetria(df: pd.DataFrame, grupos: List[str]) -> pd.DataFrame:
    tabela = (
        df.groupby(grupos + [Config.COL_STATUS], observed=True)[Config.COL_TOTAL]
        .sum().unstack(Config.COL_STATUS, fill_value=0).reset_index()
    )
    for s in Config.STATUS_ORDEM:
        if s not in tabela.columns:
            tabela[s] = 0
        tabela[s] = tabela[s].astype(int)
    tabela["Baixadas"] = tabela["Executada"] + tabela["Não Executada"]
    tabela["Total Alocado"] = tabela["Baixadas"] + tabela["Pendente"]
    tabela["Taxa Execução"] = np.where(tabela["Baixadas"] > 0, tabela["Executada"] / tabela["Baixadas"], 0.0)
    tabela["Taxa Quebra"] = 1.0 - tabela["Taxa Execução"]
    tabela["Projeção"] = (tabela["Executada"] + tabela["Taxa Execução"] * tabela["Pendente"]).astype(int)
    if Config.COL_TECNICO in df.columns:
        n_tec = df.groupby(grupos, observed=True)[Config.COL_TECNICO].nunique().reset_index(name="Técnicos")
        tabela = tabela.merge(n_tec, on=grupos, how="left")
        tabela["Técnicos"] = tabela["Técnicos"].fillna(0).astype(int)
        tabela["OS/Técnico"] = np.where(tabela["Técnicos"] > 0, tabela["Total Alocado"] / tabela["Técnicos"], 0.0)
        tabela["Exec/Técnico"] = np.where(tabela["Técnicos"] > 0, tabela["Executada"] / tabela["Técnicos"], 0.0)
    return tabela.sort_values("Total Alocado", ascending=False)


def gerar_excel(df: pd.DataFrame, nome_aba: str) -> bytes:
    output = BytesIO()
    export = df.copy()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        export.to_excel(writer, index=False, sheet_name=nome_aba[:31])
        ws = writer.sheets[nome_aba[:31]]
        hf = PatternFill("solid", fgColor="0F172A")

        ws.freeze_panes = "A2"
        ws.auto_filter.ref = ws.dimensions

        for cell in ws[1]:
            cell.fill = hf
            cell.font = Font(color="FFFFFF", bold=True)

        for i, col in enumerate(export.columns, 1):
            valores = export[col].head(500).astype(str)
            maior = max([len(str(col))] + [len(v) for v in valores], default=10)
            ws.column_dimensions[get_column_letter(i)].width = min(max(maior + 2, 12), 40)

    output.seek(0)
    return output.getvalue()


# ==========================================================
# ESTILOS CSS
# ==========================================================
def aplicar_estilo():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"], .stApp {
        font-family: 'Manrope', 'Inter', -apple-system, sans-serif !important;
    }
    [data-testid="stDataFrame"] * {
        font-variant-numeric: tabular-nums !important;
    }

    .hero-corp {
        background: linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);
        padding: 32px 40px; border-radius: 16px; color: white;
        box-shadow: 0 10px 40px rgba(1,40,105,0.25); margin-bottom: 24px;
        position: relative; overflow: hidden;
    }
    .hero-corp::before {
        content:''; position:absolute; top:-50%; right:-10%;
        width:400px; height:400px; background:rgba(255,255,255,0.05); border-radius:50%;
    }
    .hero-title { font-size:34px; font-weight:800; margin:0; letter-spacing:-0.8px; }
    .hero-subtitle { font-size:15px; opacity:0.92; margin:6px 0 0; font-weight:400; }

    /* ── KPI / BADGES / RESULTADO ── */
    .kpi-card {
        padding: 1.4rem 1.6rem; border-radius: 1rem;
        border-left: 5px solid;
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .kpi-card:hover { transform: translateY(-3px); box-shadow: 0 8px 20px rgba(0,0,0,0.1); }
    .kpi-val { font-size: 1.95rem; font-weight: 800; line-height: 1.1; margin: 0.3rem 0; letter-spacing: -0.5px; font-variant-numeric: tabular-nums; }
    .kpi-lab { font-size: 0.72rem; text-transform: uppercase; font-weight: 700; letter-spacing: 0.08em; }
    .kpi-sub { font-size: 0.78rem; margin-top: 0.2rem; font-weight: 500; }

    .resultado-base { background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%); padding: 1rem 1.5rem; border-radius: 0.75rem; margin-bottom: 1.5rem; display: flex; align-items: center; flex-wrap: wrap; gap: 0.6rem; box-shadow: 0 4px 16px rgba(15,23,42,0.15); }
    .resultado-base-label { color: #94A3B8; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }
    .resultado-base-regiao { padding: 0.3rem 0.9rem; border-radius: 999px; font-size: 0.82rem; font-weight: 700; border: 2px solid; }
    .resultado-base-count { color: #64748B; font-size: 0.72rem; margin-left: auto; font-weight: 600; font-variant-numeric: tabular-nums; }

    .section-header { display: flex; align-items: center; gap: 0.6rem; margin: 1.5rem 0 0.8rem; padding-bottom: 0.4rem; border-bottom: 2px solid #E2E8F0; }
    .section-header h3 { margin: 0; font-size: 1.1rem; color: #0F172A; font-weight: 700; letter-spacing: -0.2px; }

    .stButton > button { font-family: 'Manrope', 'Inter', sans-serif !important; font-weight: 600 !important; border-radius: 0.5rem !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { font-weight: 600; border-radius: 8px 8px 0 0; }
    </style>
    """, unsafe_allow_html=True)


# ==========================================================
# COMPONENTES VISUAIS
# ==========================================================
def render_resultado_base(regioes: List[str], total: int):
    badges = "".join(
        f'<span class="resultado-base-regiao" style="background:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["bg"]};color:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["text"]};border-color:{CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])["border"]}">{html.escape(str(r))}</span>'
        for r in sorted(regioes)
    )
    st.markdown(f'<div class="resultado-base"><span class="resultado-base-label">📋 Resultado da Base:</span>{badges}<span class="resultado-base-count">{total:,} registros</span></div>', unsafe_allow_html=True)


def render_kpi(col, label: str, value: str, sub: str, tema: str = "azul"):
    t = TEMAS_CARD.get(tema, TEMAS_CARD["azul"])
    col.markdown(f'<div class="kpi-card" style="background:{t["fundo"]};border-left-color:{t["borda"]};"><div class="kpi-lab" style="color:{t["titulo"]}">{label}</div><div class="kpi-val" style="color:{t["texto"]}">{value}</div><div class="kpi-sub" style="color:{t["titulo"]}">{sub}</div></div>', unsafe_allow_html=True)


def render_section(titulo: str):
    st.markdown(f'<div class="section-header"><h3>{titulo}</h3></div>', unsafe_allow_html=True)


# ==========================================================
# DATAFRAME ESTILIZADO
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
    adicionar_totais: bool = True,
):
    df_d = df.copy()
    mapa = Utils.resolver_renomeacao(df_d, RENOMEAR_COLUNAS)
    df_d = df_d.rename(columns=mapa)

    ce = mapa.get("Executada", "Executadas")
    cn = mapa.get("Não Executada", "Não Exec.")
    cp = mapa.get("Pendente", "Pendentes")
    cb = mapa.get("Baixadas", "Baixadas")
    ct = mapa.get("Total Alocado", "Total Alocado")
    cta = mapa.get("Taxa Execução", "Taxa Exec.")
    cq = mapa.get("Taxa Quebra", "Taxa Quebra")
    cpr = mapa.get("Projeção", "Projeção")

    for co in COLUNAS_INTEIRAS:
        cd = mapa.get(co, co)
        if cd in df_d.columns:
            df_d[cd] = pd.to_numeric(df_d[cd], errors="coerce").fillna(0).astype(int)

    ranking: Dict[float, float] = {}
    if cta in df_d.columns and len(df_d):
        valores = pd.to_numeric(df_d[cta], errors="coerce")
        n = len(valores.dropna())
        if n:
            ranks = valores.rank(method="average", ascending=False, pct=True)
            ranking = {
                float(v): float(p)
                for v, p in zip(valores, ranks)
                if pd.notna(v) and pd.notna(p)
            }

    if adicionar_totais and len(df_d):
        tr: Dict[str, Any] = {c: (0 if pd.api.types.is_numeric_dtype(df_d[c]) else "") for c in df_d.columns}
        cn2 = df_d.columns[1] if len(df_d.columns) > 1 else df_d.columns[0]
        tr[cn2] = "TOTAL GERAL"
        for c in [ce, cn, cp, cb, ct, cpr, "Técnicos"]:
            if c in df_d.columns:
                tr[c] = int(df_d[c].sum())
        if cb in df_d.columns and ce in df_d.columns:
            bt = df_d[cb].sum()
            et = df_d[ce].sum()
            if cta in df_d.columns:
                tr[cta] = et / bt if bt else 0.0
            if cq in df_d.columns:
                tr[cq] = 1 - et / bt if bt else 0.0
        nt = tr.get("Técnicos", 0) or 0
        for cc in ["OS/Técnico", "Exec/Técnico"]:
            if cc in df_d.columns:
                ref = ct if "OS" in cc else ce
                tr[cc] = tr.get(ref, 0) / nt if nt else 0.0
        df_d = pd.concat([df_d, pd.DataFrame([tr])], ignore_index=True)

    data = pd.Timestamp.now().strftime("%d/%m/%Y")
    st.markdown(f'<div style="background:#0B1739;padding:16px 24px;border-radius:12px 12px 0 0;color:#F9FAFB;margin-bottom:0;border-bottom:2px solid #1E3A8A;font-family:Manrope,Inter,sans-serif;"><span style="font-weight:700;font-size:0.85rem;letter-spacing:1.2px;">{icone}  {titulo.upper()} — {data}</span></div>', unsafe_allow_html=True)

    sty = df_d.style

    def fp(v):
        if v == "" or v is None or pd.isna(v):
            return ""
        try:
            return f"{float(v)*100:.1f}%".replace(".", ",")
        except (ValueError, TypeError):
            return str(v)

    def fi(v):
        if v == "" or v is None or pd.isna(v):
            return ""
        try:
            return f"{int(v):,}".replace(",", ".")
        except (ValueError, TypeError):
            return str(v)

    def fd(v):
        if v == "" or v is None or pd.isna(v):
            return ""
        try:
            return f"{float(v):.1f}".replace(".", ",")
        except (ValueError, TypeError):
            return str(v)

    fm: Dict[str, Any] = {}
    if cta in df_d.columns: fm[cta] = fp
    if cq in df_d.columns: fm[cq] = fp
    for c in [ce, cn, cp, cb, ct, cpr, "Técnicos"]:
        if c in df_d.columns: fm[c] = fi
    for c in ["OS/Técnico", "Exec/Técnico"]:
        if c in df_d.columns: fm[c] = fd
    if fm:
        sty = sty.format(fm)

    if cta in df_d.columns:
        def _ct(v):
            if v == "" or pd.isna(v): return ""
            try:
                vv = float(v)
                p = ranking.get(vv, 0.5)
                if p <= 0.2: bg, fg = "#D1FAE5", "#047857"
                elif p <= 0.4: bg, fg = "#ECFDF5", "#059669"
                elif p <= 0.6: bg, fg = "#FEF3C7", "#B45309"
                elif p <= 0.8: bg, fg = "#FFEDD5", "#C2410C"
                else: bg, fg = "#FEE2E2", "#B91C1C"
                return f"background-color:{bg};color:{fg};font-weight:700;text-align:center;"
            except (ValueError, TypeError): return ""
        sty = sty.map(_ct, subset=[cta])

    if cq in df_d.columns:
        def _cq(v):
            if v == "" or pd.isna(v): return ""
            try:
                vv = float(v)
                if vv >= 0.25: return "color:#B91C1C;font-weight:600;"
                elif vv >= 0.15: return "color:#B45309;font-weight:600;"
                return "color:#047857;font-weight:600;"
            except (ValueError, TypeError): return ""
        sty = sty.map(_cq, subset=[cq])

    if ce in df_d.columns:
        sty = sty.set_properties(**{"background-color": "#FEF9C3", "color": "#854D0E", "font-weight": "700"}, subset=[ce])
    if ct in df_d.columns:
        sty = sty.set_properties(**{"background-color": "#D1FAE5", "color": "#065F46", "font-weight": "700"}, subset=[ct])
    if cpr in df_d.columns:
        sty = sty.set_properties(**{"background": "#1E293B", "color": "#FFFFFF", "font-weight": "800"}, subset=[cpr])

    def _et(row):
        for v in row:
            if isinstance(v, str) and "TOTAL GERAL" in str(v).upper():
                return ["background-color:#E2E8F0;font-weight:800;color:#0F172A;border-top:2px solid #64748B;"] * len(row)
        return [""] * len(row)
    sty = sty.apply(_et, axis=1)

    sty = sty.set_table_styles([
        {"selector": "thead th", "props": [("background-color", "#1E293B"), ("color", "#F1F5F9"), ("font-weight", "600"), ("text-align", "center"), ("padding", "13px 12px"), ("border", "none"), ("font-size", "0.72rem"), ("text-transform", "uppercase"), ("letter-spacing", "1px")]},
        {"selector": "tbody td", "props": [("padding", "12px 15px"), ("border-bottom", "1px solid #F1F5F9"), ("font-size", "0.85rem"), ("text-align", "center"), ("color", "#334155"), ("font-variant-numeric", "tabular-nums")]},
        {"selector": "tbody td:nth-child(1)", "props": [("text-align", "left"), ("font-weight", "600"), ("color", "#475569"), ("padding-left", "18px")]},
        {"selector": "tbody td:nth-child(2)", "props": [("text-align", "left"), ("font-weight", "600"), ("color", "#0F172A"), ("padding-left", "15px")]},
        {"selector": "tbody tr:nth-child(even) td", "props": [("background-color", "#FAFBFC")]},
        {"selector": "", "props": [("border-radius", "0 0 12px 12px"), ("overflow", "hidden"), ("box-shadow", "0 4px 16px rgba(15,23,42,0.1)"), ("border", "1px solid #E2E8F0"), ("border-top", "none")]},
    ])

    st.dataframe(sty, use_container_width=True, hide_index=True, height=height)


# ==========================================================
# MAIN
# ==========================================================
def main():
    aplicar_estilo()

    st.markdown("""
    <div class="hero-corp">
        <div style="position:relative;z-index:2;">
            <h1 class="hero-title">📊 Gestão de Volumetria</h1>
            <p class="hero-subtitle">Análise executiva de performance e projeções operacionais</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    if "base_data" not in st.session_state:
        st.session_state.base_data = None

    # ── SIDEBAR ──────────────────────────────────────────
    with st.sidebar:
        st.header("⚙️ Configurações")
        if st.button("🔄 Reiniciar Painel", use_container_width=True):
            st.session_state.base_data = None
            st.rerun()

        st.divider()

        if st.session_state.base_data is not None:
            diag = st.session_state.base_data.attrs.get("diagnostico", {})
            st.write(f"📥 **Entrada:** {diag.get('Inicial', 0)}")
            st.write(f"🗑️ **Vazios:** {diag.get('Removidos por contrato vazio', 0)}")
            st.write(f"📈 **Processadas:** {diag.get('Final', 0)}")

    # ── UPLOAD ───────────────────────────────────────────
    if st.session_state.base_data is None:
        render_section("📁 Importação de Dados")
        u = st.file_uploader("Selecione a base (Excel/CSV)", type=["xlsx", "xls", "csv"])
        if u:
            try:
                with st.spinner("Processando..."):
                    arquivo = DataLoader.ler_arquivo(u.getvalue(), u.name)
                    if arquivo.empty:
                        st.error("O arquivo não possui registros.")
                        return

                    st.session_state.base_data = DataLoader.preparar_base(
                        arquivo,
                        DataLoader.buscar_hierarquia_gsheets(),
                    )
                    st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível processar o arquivo: {exc}")
                st.exception(exc)
        return

    df_full = st.session_state.base_data

    # ── FILTROS ──────────────────────────────────────────
    with st.sidebar:
        st.header("🎯 Filtros")
        mons = sorted(df_full[Config.COL_MONITOR].dropna().astype(str).unique())
        sel_m = st.multiselect("Monitor", mons, default=mons)
        regs = sorted(df_full[Config.COL_REGIAO].dropna().astype(str).unique())
        sel_r = st.multiselect("Região", regs, default=regs)

        tecnicos = sorted(df_full[Config.COL_TECNICO].dropna().astype(str).unique())
        sel_t = st.multiselect("Técnico", tecnicos, default=tecnicos)

        statuses = Config.STATUS_ORDEM
        sel_s = st.multiselect("Status", statuses, default=statuses)

        if st.button("↩️ Limpar filtros", use_container_width=True):
            st.rerun()

    df = df_full[
        df_full[Config.COL_MONITOR].isin(sel_m)
        & df_full[Config.COL_REGIAO].isin(sel_r)
        & df_full[Config.COL_TECNICO].isin(sel_t)
        & df_full[Config.COL_STATUS].isin(sel_s)
    ]
    if df.empty:
        st.warning("Nenhum dado selecionado.")
        return

    # ── RESULTADO DA BASE ────────────────────────────────
    render_resultado_base(sorted(df[Config.COL_REGIAO].unique()), len(df))

    # ── KPIs DE VOLUME ───────────────────────────────────
    kpis = calcular_kpis(df)

    c1, c2, c3, c4 = st.columns(4)
    render_kpi(c1, "Total Alocado", f"{kpis['total']:,}", f"{kpis['pendentes']:,} pendentes", "azul")
    render_kpi(c2, "Executadas", f"{kpis['executadas']:,}", f"Taxa: {kpis['taxa']:.1%}", "verde")
    render_kpi(c3, "Projeção Final", f"{kpis['projecao']:,}", "Baseado na taxa atual", "escuro")
    render_kpi(c4, "Meta", f"{Config.META_EXECUCAO:.0%}", "Referência", "amarelo")

    st.markdown("")
    s1, s2, s3 = st.columns(3)
    render_kpi(s1, "Não Executadas", f"{kpis['nao_executadas']:,}", f"Quebra: {kpis['quebra']:.1%}", "vermelho")
    render_kpi(s2, "Baixadas", f"{kpis['baixadas']:,}", "Exec + Não Exec", "roxo")
    render_kpi(s3, "Pendentes", f"{kpis['pendentes']:,}", f"{kpis['pendentes']/kpis['total']:.1%} do total" if kpis["total"] else "0%", "cinza")

    st.markdown("")

    # ── ABAS PRINCIPAIS ─────────────────────────────────
    t1, t2 = st.tabs(["👥 Equipes", "📋 Base"])

    with t1:
        te = calcular_volumetria(df, [Config.COL_REGIAO, Config.COL_MONITOR])
        render_dataframe(te, titulo="Volumetria por Equipe", icone="👥", color_col="Taxa Execução", color_meta=Config.META_EXECUCAO)
        st.download_button("📥 Baixar Equipes", gerar_excel(te, "Equipes"), "equipes.xlsx")

    with t2:
        render_dataframe(df.head(500), titulo="Base de Dados (prévia — 500 linhas)", icone="📋", badge=f"{len(df)} total", height=600)


if __name__ == "__main__":
    main()