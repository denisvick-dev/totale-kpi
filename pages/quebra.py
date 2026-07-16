from __future__ import annotations

import csv
import unicodedata
from io import BytesIO
from typing import Any, Dict, List, Literal, Optional, Tuple

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
    page_title="Quebra de Agenda",
    page_icon="📉",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "df_memoria" not in st.session_state:
    st.session_state["df_memoria"] = None


# ====================================================
# 2. CONFIGURAÇÕES GLOBAIS
# ====================================================
class Config:
    SLA_QUEBRA_MAXIMA: float = 0.20
    URL_ATIVOS: str = (
        "https://docs.google.com/spreadsheets/d/"
        "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit"
    )
    CONTRATO_VALORES_VAZIOS = {"", "NAN", "NONE", "N/A", "NA", "-", "0", "NULL"}
    STATUS_ORDEM = ["Executada", "Não Executada", "Pendente"]
    CORES_STATUS = {
        "Executada": "#10B981",
        "Não Executada": "#EF4444",
        "Pendente": "#94A3B8",
    }
    COL_REGIAO = "REGIÃO"
    REGIOES_PRINCIPAIS = ["LESTE", "GRU", "ABCDM"]


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
    "TÉCNICO": "Técnico",
    "MONITOR": "Monitor",
    "REGIÃO": "Região",
    "Executada": "Executadas",
    "Não Executada": "Não Exec.",
    "Pendente": "Pendentes",
    "Alocado": "Alocado",
    "Considerado": "Considerado",
    "Quebra Atual": "Quebra Atual",
    "Fechamento Otimista": "Fech. Otimista",
    "Fechamento Base": "Fech. Base",
    "Fechamento Pessimista": "Fech. Pessimista",
}

COLUNAS_INTEIRAS = [
    "Executada", "Não Executada", "Pendente",
    "Alocado", "Considerado",
]


# ====================================================
# 3. ESTILOS CSS
# ====================================================
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
            min-height: 110px; display: flex; flex-direction: column; justify-content: center;
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
            padding: 1rem 1.2rem; box-shadow: 0 2px 8px rgba(0,0,0,0.05); margin-bottom: 0.5rem;
        }
        .styled-table-title { font-size: 1rem; font-weight: 700; color: #0F172A; margin-bottom: 0.4rem; display: flex; align-items: center; gap: 0.5rem; }
        .styled-table-badge { font-size: 0.68rem; background: #E0F2FE; color: #0369A1; padding: 0.15rem 0.5rem; border-radius: 999px; font-weight: 600; }

        div[data-testid="stDataFrame"] > div { border-radius: 0.5rem; overflow: hidden; }

        .section-header { display: flex; align-items: center; gap: 0.6rem; margin: 1.5rem 0 0.8rem; padding-bottom: 0.4rem; border-bottom: 2px solid #E2E8F0; }
        .section-header h3 { margin: 0; font-size: 1.1rem; color: #0F172A; }
    </style>
    """, unsafe_allow_html=True)


# ====================================================
# 4. COMPONENTES VISUAIS
# ====================================================
def render_kpi(col, label: str, value: str, sub: str = "", tema: str = "azul"):
    t = TEMAS_CARD.get(tema, TEMAS_CARD["azul"])
    col.markdown(f"""
    <div class="kpi-card" style="background:{t['fundo']};border-left-color:{t['borda']};">
        <div class="kpi-lab" style="color:{t['titulo']}">{label}</div>
        <div class="kpi-val" style="color:{t['texto']}">{value}</div>
        <div class="kpi-sub" style="color:{t['titulo']}">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


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


def render_section(titulo: str):
    st.markdown(
        f'<div class="section-header"><h3>{titulo}</h3></div>',
        unsafe_allow_html=True,
    )


def resolver_renomeacao(df: pd.DataFrame, mapa: Dict[str, str]) -> Dict[str, str]:
    """Retorna apenas renomeações que não causam duplicatas."""
    nomes_existentes = set(df.columns)
    nomes_ja_usados: set[str] = set()
    resultado: Dict[str, str] = {}

    for col_original in df.columns:
        if col_original not in mapa:
            continue
        novo_nome = mapa[col_original]
        if novo_nome == col_original:
            continue
        if novo_nome in nomes_existentes or novo_nome in nomes_ja_usados:
            continue
        resultado[col_original] = novo_nome
        nomes_ja_usados.add(novo_nome)

    return resultado


def render_dataframe(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "📊",
    badge: str = "",
    fmt: Optional[Dict[str, Any]] = None,
    color_col: Optional[str] = None,
    color_meta: Optional[float] = None,
    color_invertido: bool = True,
    height: int | Literal["auto", "stretch", "content"] = "auto",
):
    badge_text = badge or f"{len(df)} registros"
    st.markdown(f"""
    <div class="styled-table-wrapper">
        <div class="styled-table-title">
            <span>{icone}</span><span>{titulo}</span>
            <span class="styled-table-badge">{badge_text}</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    df_display = df.copy()

    # 1. Renomeação segura
    mapa_seguro = resolver_renomeacao(df_display, RENOMEAR_COLUNAS)
    df_display = df_display.rename(columns=mapa_seguro)

    # 2. Atualizar fmt e color_col pós-renomeação
    if fmt:
        fmt = {mapa_seguro.get(k, k): v for k, v in fmt.items()}
    if color_col:
        color_col = mapa_seguro.get(color_col, color_col)

    col_quebra_display = mapa_seguro.get("Quebra Atual", "Quebra Atual")

    # 3. Float → Int
    for col_orig in COLUNAS_INTEIRAS:
        col_disp = mapa_seguro.get(col_orig, col_orig)
        if col_disp in df_display.columns:
            df_display[col_disp] = (
                pd.to_numeric(df_display[col_disp], errors="coerce")
                .fillna(0).astype(int)
            )

    styler = df_display.style

    # 4. Formatação
    if fmt:
        styler = styler.format(fmt)

    # 5. Cor condicional (exclui Quebra Atual)
    if color_col and color_col in df_display.columns and color_meta is not None:
        colunas_condicionais = [c for c in [color_col] if c != col_quebra_display]
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

    # 6. Estilo fixo — Quebra Atual
    if col_quebra_display in df_display.columns:
        styler = styler.map(
            lambda val: (
                "background-color:#1E293B;color:#FFFFFF;font-weight:600;"
                if not pd.isna(val) and str(val).strip() != "" else ""
            ),
            subset=pd.Index([col_quebra_display]),
        )

    # 7. Header estilizado
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


# ====================================================
# 5. UTILITÁRIOS
# ====================================================
class Utils:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras: list) -> Optional[str]:
        if df is None or df.empty:
            return None

        def norm(t):
            t = str(t).strip().upper()
            t = unicodedata.normalize("NFKD", t).encode("ASCII", "ignore").decode()
            return t.replace(".", "").replace("_", "").replace("  ", " ")

        cols = {norm(c): c for c in df.columns}
        for p in palavras:
            pn = norm(p)
            for cn, co in cols.items():
                if pn in cn:
                    return co
        return None

    @staticmethod
    def classificar_status(serie: pd.Series) -> pd.Series:
        s = serie.fillna("").astype(str).str.strip().str.upper()
        exe = s == "EXECUTADA"
        nex = s.isin(["NÃO EXECUTADA", "NAO EXECUTADA"])
        return pd.Series(
            np.select([exe, nex], ["Executada", "Não Executada"], default="Pendente"),
            index=serie.index,
        )

    @staticmethod
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
# 6. CARREGAMENTO DE DADOS
# ====================================================
class DataLoader:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(file_bytes: bytes, filename: str) -> pd.DataFrame:
        bio = BytesIO(file_bytes)
        try:
            if filename.lower().endswith(".csv"):
                bio.seek(0)
                amostra = bio.read(5000).decode("utf-8", errors="ignore")
                bio.seek(0)
                try:
                    sep = csv.Sniffer().sniff(amostra).delimiter
                except Exception:
                    sep = ";"
                return pd.read_csv(bio, sep=sep, encoding="utf-8", dtype=str, engine="python")
            return pd.read_excel(bio, engine="openpyxl", dtype=str)
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_gsheets() -> pd.DataFrame:
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            raw = conn.read(spreadsheet=Config.URL_ATIVOS)
            if raw is None or raw.empty:
                return pd.DataFrame()

            raw.columns = raw.columns.astype(str).str.strip().str.upper()
            rename = {}
            if c := Utils.buscar_coluna(raw, ["LOGIN", "ID", "MATRÍCULA"]):
                rename[c] = "LOGIN"
            if c := Utils.buscar_coluna(raw, ["TÉCNICO", "NOME"]):
                rename[c] = "TÉCNICO"
            if c := Utils.buscar_coluna(raw, ["MONITOR", "GESTOR"]):
                rename[c] = "MONITOR"

            raw = raw.rename(columns=rename)
            raw = raw[[c for c in ["LOGIN", "TÉCNICO", "MONITOR"] if c in raw.columns]].copy()
            if "LOGIN" in raw.columns:
                raw["LOGIN"] = (
                    raw["LOGIN"].astype(str)
                    .str.replace(r"\.0$", "", regex=True)
                    .str.strip().str.upper()
                )
                raw = raw.drop_duplicates(subset=["LOGIN"], keep="last")
            return raw
        except Exception as e:
            st.warning(f"GSheets falhou ({e}). Usando dados locais.")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(show_spinner=False)
    def preparar_base(df: pd.DataFrame, df_gs: pd.DataFrame) -> pd.DataFrame:
        # Validação sem ambiguidade de truth value
        if not isinstance(df, pd.DataFrame) or df.empty:
            return pd.DataFrame()

        df = df.copy()
        df.columns = df.columns.astype(str).str.strip().str.upper()

        removidos_suspensos = 0
        removidos_contrato = 0

        # Suspensas
        col_atv = Utils.buscar_coluna(df, ["STATUS DA ATIVIDADE"])
        if col_atv:
            susp = df[col_atv].fillna("").astype(str).str.upper().str.contains("SUSP", na=False)
            removidos_suspensos = int(susp.sum())
            df = df[~susp].copy()

        # Total de tarefas
        col_tot = Utils.buscar_coluna(df, ["TOTAL DE TAREFAS"])
        df["TOTAL DE TAREFAS"] = (
            pd.to_numeric(df[col_tot].astype(str).str.replace(",", "."), errors="coerce").fillna(0)
            if col_tot else 0
        )

        # Contrato vazio
        col_con = Utils.buscar_coluna(df, ["CONTRATO", "Nº CONTRATO"])
        if col_con:
            norm = df[col_con].astype(str).str.strip().str.upper()
            valido = ~norm.isin(Config.CONTRATO_VALORES_VAZIOS)
            removidos_contrato = int((~valido).sum())
            df = df[valido].copy()

        # Merge GSheets
        col_login = Utils.buscar_coluna(df, ["LOGIN", "LOGIN DO TÉCNICO", "USUÁRIO", "MATRÍCULA"])
        gs_valido = isinstance(df_gs, pd.DataFrame) and not df_gs.empty
        if col_login and gs_valido and "LOGIN" in df_gs.columns:
            df[col_login] = (
                df[col_login].astype(str)
                .str.replace(r"\.0$", "", regex=True).str.strip().str.upper()
            )
            for c in ["TÉCNICO", "MONITOR"]:
                if c in df.columns:
                    df = df.drop(columns=[c])
            df = df.merge(df_gs, left_on=col_login, right_on="LOGIN", how="left")

        df["TÉCNICO"] = df.get("TÉCNICO", pd.Series("NÃO MAPEADO", index=df.index)).fillna("NÃO MAPEADO")
        df["MONITOR"] = df.get("MONITOR", pd.Series("SEM MONITOR", index=df.index)).fillna("SEM MONITOR")

        # Regiões
        col_cid = Utils.buscar_coluna(df, ["CIDADE", "LOCALIDADE"])
        if col_cid:
            cidade = (
                df[col_cid].fillna("").astype(str).str.strip().str.upper()
                .apply(lambda v: unicodedata.normalize("NFKD", v).encode("ASCII", "ignore").decode())
            )
        else:
            cidade = pd.Series("", index=df.index)

        df["REGIÃO"] = np.select(
            [
                cidade.isin(["SAO PAULO"]),
                cidade.isin(["GUARULHOS", "ARUJA", "MOGI DAS CRUZES", "SUZANO",
                             "ITAQUAQUECETUBA", "FERRAZ DE VASCONCELOS", "POA"]),
                cidade.isin(["SANTO ANDRE", "SAO BERNARDO DO CAMPO", "SAO CAETANO DO SUL",
                             "DIADEMA", "MAUA", "RIBEIRAO PIRES", "RIO GRANDE DA SERRA"]),
            ],
            ["LESTE", "GRU", "ABCDM"],
            default="OUTRAS",
        )

        # ── Status Contrato (classificação da O.S 1) ──────────────────
        col_status = Utils.buscar_coluna(df, ["STATUS DA O.S 1", "STATUS OS 1"])
        if col_status:
            df["Status Contrato"] = Utils.classificar_status(df[col_status])
        else:
            df["Status Contrato"] = "Pendente"
            
                # ── Classificação de Tipo (mesma lógica das flags premium) ───
        col_tipo = Utils.buscar_coluna(df, ["TIPO O.S 1", "TIPO OS 1", "TIPO DE O.S"])
        col_hab  = Utils.buscar_coluna(df, ["HABILIDADE DE TRABALHO", "HABILIDADE"])

        tipo_upper = (
            df[col_tipo]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .apply(lambda v: unicodedata.normalize("NFKD", v).encode("ASCII", "ignore").decode())
            if col_tipo
            else pd.Series("", index=df.index, dtype=str)
        )

        hab_upper = (
            df[col_hab]
            .fillna("")
            .astype(str)
            .str.upper()
            if col_hab
            else pd.Series("", index=df.index, dtype=str)
        )

        # Flags booleanas
        flag_gpon     = hab_upper.str.contains(r"PON\(1/100\)", regex=True, na=False)
        flag_nd       = tipo_upper.str.contains("ADESAO", na=False)
        flag_migracao = (tipo_upper.str.strip() == "24 - MUDANCA DE PACOTE") & flag_gpon
        flag_pme      = hab_upper.str.contains("PME", na=False) & flag_nd

        # ── np.select com default explícito como str ──────────────────
        df["TIPO_SERVICO"] = pd.Series(
            np.select(
                condlist=[flag_nd, flag_migracao, flag_gpon, flag_pme],
                choicelist=["Novos Domicílios", "Migração", "GPON", "PME"],
                default="Outros",          # str explícito evita o TypeError
            ),
            index=df.index,
            dtype=str,                  # força dtype string no resultado
        )

        df.attrs["diagnostico"] = {
            "suspensos": removidos_suspensos,
            "contrato_vazio": removidos_contrato,
            "col_status_encontrada": bool(col_status),
        }
        return df


# ====================================================
# 7. MOTORES DE CÁLCULO
# ====================================================
class Motor:
    @staticmethod
    def quebra_atual(df: pd.DataFrame) -> Tuple[float, float]:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return 0.0, 0.0
        exe = float(df.loc[df["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum())
        nex = float(df.loc[df["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum())
        cons = exe + nex
        return cons, (nex / cons) if cons > 0 else 0.0

    @staticmethod
    def projetar(df: pd.DataFrame, p: float) -> Dict[str, float]:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return dict(alocado=0, exec=0, naoexec=0, pend=0,
                        quebra_atual=0, fechamento_proj=0, naoexec_proj=0)
        aloc = float(df["TOTAL DE TAREFAS"].sum())
        exe = float(df.loc[df["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum())
        nex = float(df.loc[df["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum())
        pen = max(0.0, aloc - exe - nex)
        _, qa = Motor.quebra_atual(df)
        nex_proj = nex + (pen * p)
        return dict(
            alocado=aloc, exec=exe, naoexec=nex, pend=pen,
            quebra_atual=qa,
            fechamento_proj=(nex_proj / aloc) if aloc > 0 else 0,
            naoexec_proj=nex_proj,
        )

    @staticmethod
    def folga_sla(df: pd.DataFrame, sla: float) -> Dict[str, Any]:
        if not isinstance(df, pd.DataFrame) or df.empty:
            return dict(alocado=0, exec=0, naoexec=0, pend=0,
                        limite_ne_total=0, folga_ne_pendente=0,
                        folga_pct_pendente=0, precisa_executar_pendente=0, estourado=False)
        aloc = float(df["TOTAL DE TAREFAS"].sum())
        exe = float(df.loc[df["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum())
        nex = float(df.loc[df["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum())
        pen = max(0.0, aloc - exe - nex)
        limite = sla * aloc
        folga_tot = limite - nex
        folga_pen = max(0.0, min(pen, folga_tot))
        return dict(
            alocado=aloc, exec=exe, naoexec=nex, pend=pen,
            limite_ne_total=limite, folga_ne_pendente=folga_pen,
            folga_pct_pendente=(folga_pen / pen) if pen > 0 else 0,
            precisa_executar_pendente=max(0.0, pen - folga_pen),
            estourado=folga_tot < 0,
        )

    @staticmethod
    def tabela_cenarios(
        df: pd.DataFrame, grupo: str,
        p_ot: float, p_base: float, p_pess: float,
        min_aloc: float = 5,
    ) -> pd.DataFrame:
        if not isinstance(df, pd.DataFrame) or df.empty or grupo not in df.columns:
            return pd.DataFrame()
        pv = pd.pivot_table(
            df, index=grupo, columns="Status Contrato",
            values="TOTAL DE TAREFAS", aggfunc="sum", fill_value=0,
        )
        for c in Config.STATUS_ORDEM:
            if c not in pv.columns:
                pv[c] = 0.0
        out = pv.reset_index()
        out["Considerado"] = out["Executada"] + out["Não Executada"]
        out["Alocado"] = out["Considerado"] + out["Pendente"]
        out["Quebra Atual"] = np.where(
            out["Considerado"] > 0, out["Não Executada"] / out["Considerado"], 0
        )
        for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]:
            out[f"Fechamento {nome}"] = np.where(
                out["Alocado"] > 0,
                (out["Não Executada"] + out["Pendente"] * p) / out["Alocado"], 0,
            )
        return out[out["Alocado"] >= min_aloc].sort_values("Fechamento Base", ascending=False)


# ====================================================
# 8. APLICAÇÃO PRINCIPAL
# ====================================================
def main():
    aplicar_estilo()

    st.markdown(
        '<div class="hero">'
        "<h1>📉 Gestão de Quebra de Agenda</h1>"
        "<p>Análise de quebra, projeções de SLA e plano de ação operacional</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("⚙️ Configurações")
        if st.button("🔄 Reiniciar Painel", use_container_width=True):
            st.session_state["df_memoria"] = None
            st.rerun()
        st.divider()

    # ── Upload ────────────────────────────────────────
    if st.session_state["df_memoria"] is None:
        render_section("📁 Importação de Dados")
        arq = st.file_uploader("Selecione a base (Excel/CSV)", type=["xlsx", "csv"])
        if arq:
            with st.spinner("Processando..."):
                raw = DataLoader.ler_arquivo(arq.getvalue(), arq.name)
                gs = DataLoader.buscar_gsheets()
                df_proc = DataLoader.preparar_base(raw, gs)
                st.session_state["df_memoria"] = df_proc

            diag = df_proc.attrs.get("diagnostico", {})
            if diag.get("contrato_vazio", 0) > 0:
                st.toast(f"🗑️ {diag['contrato_vazio']} linha(s) sem contrato removida(s).", icon="⚠️")
            if diag.get("suspensos", 0) > 0:
                st.toast(f"🗑️ {diag['suspensos']} ordens suspensas removidas.", icon="ℹ️")
            if not diag.get("col_status_encontrada", False):
                st.warning("⚠️ Coluna 'Status da O.S 1' não encontrada. Tudo classificado como Pendente.")

            st.rerun()
        return

    # ── Dados em memória (sem ambiguidade de truth value) ──
    df_mem = st.session_state["df_memoria"]
    df_full = df_mem.copy() if isinstance(df_mem, pd.DataFrame) else pd.DataFrame()

    if df_full.empty:
        st.error("Base carregada está vazia. Envie um novo arquivo.")
        st.session_state["df_memoria"] = None
        return

    # Garante que Status Contrato existe (fallback de segurança)
    if "Status Contrato" not in df_full.columns:
        col_status = Utils.buscar_coluna(df_full, ["STATUS DA O.S 1", "STATUS OS 1"])
        if col_status:
            df_full["Status Contrato"] = Utils.classificar_status(df_full[col_status])
        else:
            df_full["Status Contrato"] = "Pendente"

    # ── Sidebar Filtros ───────────────────────────────
    with st.sidebar:
        st.header("🎯 Filtros")
        monitores = ["Todos"] + sorted([
            str(x) for x in df_full["MONITOR"].dropna().unique()
            if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
        ])
        sel_mon = st.selectbox("👔 Monitor", monitores)

        df_filt = df_full.copy()
        if sel_mon != "Todos":
            df_filt = df_filt[df_filt["MONITOR"] == sel_mon]

        tecnicos = ["Todos"] + sorted([
            str(x) for x in df_filt["TÉCNICO"].dropna().unique()
            if str(x) not in {"nan", "NÃO MAPEADO"}
        ])
        sel_tec = st.selectbox("👤 Técnico", tecnicos)

        df = df_filt.copy()
        if sel_tec != "Todos":
            df = df[df["TÉCNICO"] == sel_tec]

        st.divider()
        st.subheader("🔮 Probabilidade de Quebra")
        p_ot = st.slider("Otimista (%)", 0, 100, 10, 5) / 100.0
        p_base = st.slider("Base (%)", 0, 100, 30, 5) / 100.0
        p_pess = st.slider("Pessimista (%)", 0, 100, 60, 5) / 100.0
        st.divider()
        min_aloc = st.number_input("Mín. OS (Rankings)", min_value=1, value=5)
        top_n = st.number_input("Visualizar Top N", min_value=1, value=10)

    if df.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    # ── Resultado da Base ─────────────────────────────
    render_resultado_base(sorted(df[Config.COL_REGIAO].unique()), len(df))

    # ── KPIs ──────────────────────────────────────────
    cen = {
        "Otimista": Motor.projetar(df, p_ot),
        "Base": Motor.projetar(df, p_base),
        "Pessimista": Motor.projetar(df, p_pess),
    }
    m = cen["Base"]

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    render_kpi(k1, "Alocado", f"{int(m['alocado']):,}", tema="azul")
    render_kpi(k2, "Executadas", f"{int(m['exec']):,}", tema="verde")
    render_kpi(k3, "Não Exec", f"{int(m['naoexec']):,}", tema="laranja")
    render_kpi(k4, "Pendentes", f"{int(m['pend']):,}", tema="cinza")
    render_kpi(k5, "Quebra Atual", f"{m['quebra_atual']:.2%}", tema="cinza")
    render_kpi(
        k6, "Proj. Base", f"{m['fechamento_proj']:.2%}",
        tema="vermelho" if m["fechamento_proj"] > Config.SLA_QUEBRA_MAXIMA else "roxo",
    )

    st.markdown("")

    # ── Abas ──────────────────────────────────────────
    aba_visao, aba_rank, aba_causa, aba_back, aba_tipos = st.tabs(
        ["📊 Visão & Projeções", "🧭 Desempenho", "🔍 Causas", "🚨 Backoffice", "📂 Por Tipo de Serviço"]
    )

    with aba_visao:
        render_section("🔮 Análise e Simulações de SLA")
        c_cards, c_graf = st.columns([3, 2.5])

        with c_cards:
            o1, o2, o3 = st.columns(3)
            for col_ui, nome, tema_d in [
                (o1, "Otimista", "cinza"), (o2, "Base", "roxo"), (o3, "Pessimista", "cinza")
            ]:
                proj = cen[nome]
                cor = "vermelho" if proj["fechamento_proj"] > Config.SLA_QUEBRA_MAXIMA else tema_d
                render_kpi(col_ui, nome, f"{proj['fechamento_proj']:.2%}",
                           sub=f"Vol: {int(proj['naoexec_proj']):,}", tema=cor)

            st.markdown("")
            folga = Motor.folga_sla(df, Config.SLA_QUEBRA_MAXIMA)
            f1, f2 = st.columns(2)
            cor_f = "vermelho" if folga["estourado"] else ("verde" if folga["folga_ne_pendente"] > 0 else "laranja")
            render_kpi(f1, "Folga no SLA", f"{int(np.floor(folga['folga_ne_pendente'])):,}",
                       sub=f"Pendente aceitável: {folga['folga_pct_pendente']:.1%}", tema=cor_f)
            render_kpi(f2, "Garantia Mínima", f"{int(np.ceil(folga['precisa_executar_pendente'])):,}",
                       sub="OS a executar", tema="azul")

            st.progress(min(1.0, max(0.0, float(folga["folga_pct_pendente"]))))
            if folga["estourado"]:
                st.error(f"❌ SLA estourado em {abs(folga['naoexec'] - folga['limite_ne_total']):,.0f} OS.")

        with c_graf:
            df_plot = pd.DataFrame({
                "Cenário": ["Otimista", "Base", "Pessimista"],
                "Fechamento": [cen[s]["fechamento_proj"] for s in ["Otimista", "Base", "Pessimista"]],
            })
            fig = px.bar(df_plot, x="Cenário", y="Fechamento", color="Fechamento",
                         color_continuous_scale="Purples", title="Cenários Projetados")
            fig.update_traces(texttemplate="%{y:.2%}", textposition="outside")
            fig.add_hline(y=Config.SLA_QUEBRA_MAXIMA, line_dash="dash", line_color="red",
                          annotation_text="Meta", annotation_position="top left")
            fig.update_layout(yaxis_tickformat=".0%", coloraxis_showscale=False,
                              height=380, margin=dict(t=40, b=10, l=10, r=10))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    with aba_rank:
        t_mon, t_tec = st.tabs(["👔 Monitores", "👤 Técnicos"])

        fmt_rank: Dict[str, Any] = {
            "Quebra Atual": "{:.2%}",
            "Fechamento Otimista": "{:.2%}",
            "Fechamento Base": "{:.2%}",
            "Fechamento Pessimista": "{:.2%}",
        }

        with t_mon:
            df_rm = Motor.tabela_cenarios(df_full, "MONITOR", p_ot, p_base, p_pess, float(min_aloc))
            if df_rm.empty:
                st.info("Sem dados suficientes.")
            else:
                render_dataframe(
                    df_rm.head(int(top_n)),
                    titulo="Ranking de Monitores", icone="👔",
                    fmt=fmt_rank, color_col="Fechamento Base",
                    color_meta=Config.SLA_QUEBRA_MAXIMA,
                    color_invertido=True, height=500,
                )
                st.download_button("📥 Baixar Ranking Monitores",
                                   Utils.gerar_excel(df_rm, "Monitores"), "ranking_monitores.xlsx")

        with t_tec:
            df_rt = Motor.tabela_cenarios(df, "TÉCNICO", p_ot, p_base, p_pess, float(min_aloc))
            if df_rt.empty:
                st.info("Sem dados suficientes.")
            else:
                df_rt_sorted = df_rt.sort_values(
                    by=["Fechamento Base", "Quebra Atual", "Alocado"],
                    ascending=[False, False, False],
                ).reset_index(drop=True)
                render_dataframe(
                    df_rt_sorted.head(int(top_n)),
                    titulo="Ranking de Técnicos", icone="👤",
                    fmt=fmt_rank, color_col="Fechamento Base",
                    color_meta=Config.SLA_QUEBRA_MAXIMA,
                    color_invertido=True, height=500,
                )
                st.download_button("📥 Baixar Ranking Técnicos",
                                   Utils.gerar_excel(df_rt_sorted, "Tecnicos"), "ranking_tecnicos.xlsx")

    with aba_causa:
        render_section("🔍 Análise de Causa Raiz")

        # Busca específica por coluna de código de baixa
        col_cod_baixa = Utils.buscar_coluna(
            df_full,
            ["CÓD DE BAIXA 1", "COD DE BAIXA 1", "CÓDIGO DE BAIXA 1", "COD BAIXA 1"],
        )

        ca1, ca2 = st.columns([1, 2])

        with ca1:
            df_dist = df.groupby("Status Contrato")["TOTAL DE TAREFAS"].sum().reset_index()
            fig_pie = px.pie(
                df_dist, names="Status Contrato", values="TOTAL DE TAREFAS",
                hole=0.5, color="Status Contrato", color_discrete_map=Config.CORES_STATUS,
            )
            fig_pie.update_layout(
                legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                margin=dict(t=10, b=10, l=10, r=10), height=350,
            )
            st.plotly_chart(fig_pie, use_container_width=True)

        with ca2:
            if col_cod_baixa and col_cod_baixa in df.columns:
                df_cod = (
                    df[df["Status Contrato"] == "Não Executada"]
                    .groupby(col_cod_baixa)["TOTAL DE TAREFAS"]
                    .sum().nlargest(5).reset_index()
                )
                if not df_cod.empty:
                    fig_mot = px.bar(
                        df_cod, x="TOTAL DE TAREFAS", y=col_cod_baixa,
                        orientation="h", text="TOTAL DE TAREFAS",
                        color_discrete_sequence=["#EF4444"],
                    )
                    fig_mot.update_layout(
                        yaxis={"categoryorder": "total ascending"},
                        margin=dict(t=10, b=10, l=5, r=5), height=350,
                    )
                    st.plotly_chart(fig_mot, use_container_width=True)
                else:
                    st.info("Nenhuma OS 'Não Executada' com motivo de baixa.")
            else:
                st.warning("Coluna 'Código de Baixa' não encontrada.")

    with aba_back:
        render_section("🚨 Fila de Tratamento (Backoffice)")
        df_back = df[df["Status Contrato"] == "Não Executada"].copy()
        if not df_back.empty:
            render_dataframe(
                df_back, titulo="Ordens Não Executadas",
                icone="🚨", badge=f"{len(df_back)} ordens", height=600,
            )
            st.download_button("📥 Baixar Fila Excel",
                               Utils.gerar_excel(df_back, "Backoffice"), "backoffice.xlsx")
        else:
            st.success("🎉 Nenhuma quebra para tratamento!")
            
    with aba_tipos:
        render_section("📂 Análise por Tipo de Serviço")

        # ── Verifica se a coluna foi criada ──────────────────────────
        if "TIPO_SERVICO" not in df.columns:
            st.warning("Coluna de tipo de O.S. não encontrada na base.")
        else:
            # Distribuição geral dos tipos
            dist_tipos = df["TIPO_SERVICO"].value_counts().reset_index()
            dist_tipos.columns = ["Tipo", "Quantidade"]

            col_dist, col_pie = st.columns([1, 1])
            with col_dist:
                render_dataframe(
                    dist_tipos,
                    titulo="Distribuição por Tipo",
                    icone="📂",
                    height=250,
                )
            with col_pie:
                fig_tipos = px.pie(
                    dist_tipos,
                    names="Tipo",
                    values="Quantidade",
                    hole=0.5,
                    color_discrete_sequence=["#0EA5E9", "#10B981", "#A855F7", "#94A3B8"],
                )
                fig_tipos.update_layout(
                    height=250,
                    margin=dict(t=20, b=0, l=0, r=0),
                    showlegend=True,
                )
                st.plotly_chart(fig_tipos, use_container_width=True)

            st.markdown("")

            # ── Sub-abas por tipo ────────────────────────────────────
            tipos_disponiveis = [
                t for t in ["PME", "Novos Domicílios", "Migração", "GPON", "Outros"]
                if t in df["TIPO_SERVICO"].unique()
            ]

            if not tipos_disponiveis:
                st.info("Nenhum tipo classificado encontrado.")
            else:
                sub_abas = st.tabs([f"📋 {t}" for t in tipos_disponiveis])

                fmt_rank: Dict[str, Any] = {
                    "Quebra Atual": "{:.2%}",
                    "Fechamento Otimista": "{:.2%}",
                    "Fechamento Base": "{:.2%}",
                    "Fechamento Pessimista": "{:.2%}",
                }

                for sub_aba, tipo in zip(sub_abas, tipos_disponiveis):
                    with sub_aba:
                        df_tipo = df[df["TIPO_SERVICO"] == tipo].copy()

                        if df_tipo.empty:
                            st.info(f"Sem dados para o tipo **{tipo}**.")
                            continue

                        # KPIs do tipo
                        m_tipo = Motor.projetar(df_tipo, p_base)
                        t1, t2, t3, t4 = st.columns(4)
                        render_kpi(t1, "Alocado",      f"{int(m_tipo['alocado']):,}",   tema="azul")
                        render_kpi(t2, "Executadas",   f"{int(m_tipo['exec']):,}",      tema="verde")
                        render_kpi(t3, "Não Exec",     f"{int(m_tipo['naoexec']):,}",   tema="laranja")
                        render_kpi(
                            t4, "Quebra Atual", f"{m_tipo['quebra_atual']:.2%}",
                            tema="vermelho" if m_tipo["quebra_atual"] > Config.SLA_QUEBRA_MAXIMA else "cinza",
                        )

                        st.markdown("")

                        # Ranking de monitores para este tipo
                        df_rank_tipo = Motor.tabela_cenarios(
                            df_tipo, "MONITOR", p_ot, p_base, p_pess, float(min_aloc)
                        )

                        if not df_rank_tipo.empty:
                            render_dataframe(
                                df_rank_tipo.head(int(top_n)),
                                titulo=f"Monitores — {tipo}",
                                icone="👔",
                                fmt=fmt_rank,
                                color_col="Fechamento Base",
                                color_meta=Config.SLA_QUEBRA_MAXIMA,
                                color_invertido=True,
                                height=400,
                            )
                            st.download_button(
                                f"📥 Baixar {tipo}",
                                Utils.gerar_excel(df_rank_tipo, tipo[:31]),
                                f"ranking_{tipo.lower().replace(' ', '_')}.xlsx",
                                key=f"dl_{tipo}",
                            )
                        else:
                            st.info(f"Dados insuficientes para ranking de **{tipo}**.")


if __name__ == "__main__":
    main()