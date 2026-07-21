from __future__ import annotations

import csv
import unicodedata
from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any, Dict, List, Literal, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)
from streamlit_gsheets import GSheetsConnection

# ============================================================
# 1. CONFIGURAÇÃO
# ============================================================
st.set_page_config(page_title="Quebra de Agenda", page_icon="📉",
                   layout="wide", initial_sidebar_state="expanded")

for k in ("df_memoria", "pdf_executivo"):
    st.session_state.setdefault(k, None)


class Config:
    SLA_QUEBRA_MAXIMA = 0.20
    SLA_PME = 0.20
    SLA_MIGRACAO = 0.25
    URL_ATIVOS = ("https://docs.google.com/spreadsheets/d/"
                  "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/edit")
    CONTRATO_VALORES_VAZIOS = {"", "NAN", "NONE", "N/A", "NA", "-", "0", "NULL"}
    STATUS_ORDEM = ["Executada", "Não Executada", "Pendente"]
    CORES_STATUS = {"Executada": "#10B981", "Não Executada": "#EF4444", "Pendente": "#94A3B8"}
    COL_REGIAO = "REGIÃO"
    REGIOES_PRINCIPAIS = ["LESTE", "GRU", "ABCDM"]
    SEGMENTOS_CONFIG = {
        "PME": {"icone": "🏢", "cor": "#7C3AED", "cor_clara": "#EDE9FE",
                "sla": 0.20, "descricao": "Pequenas e Médias Empresas"},
        "Migração": {"icone": "🔄", "cor": "#0369A1", "cor_clara": "#E0F2FE",
                     "sla": 0.25, "descricao": "Mudança de Pacote + GPON"},
    }


# ── Temas de cores ─────────────────────────────────────────
def _tema(fundo, texto, borda, titulo):
    return {"fundo": fundo, "texto": texto, "borda": borda, "titulo": titulo}

TEMAS_CARD = {
    "amarelo":  _tema("#FEF9C3", "#854D0E", "#EAB308", "#A16207"),
    "azul":     _tema("#F0F9FF", "#0369A1", "#0EA5E9", "#075985"),
    "verde":    _tema("#F0FDF4", "#15803D", "#22C55E", "#166534"),
    "roxo":     _tema("#FAF5FF", "#7E22CE", "#A855F7", "#6B21A8"),
    "cinza":    _tema("#F8FAFC", "#334155", "#94A3B8", "#64748B"),
    "escuro":   _tema("#1E293B", "#FFFFFF", "#475569", "#E2E8F0"),
    "vermelho": _tema("#FEF2F2", "#B91C1C", "#EF4444", "#991B1B"),
    "laranja":  _tema("#FFF7ED", "#C2410C", "#F97316", "#9A3412"),
    "indigo":   _tema("#EEF2FF", "#3730A3", "#6366F1", "#312E81"),
    "teal":     _tema("#F0FDFA", "#0F766E", "#14B8A6", "#0D9488"),
}

CORES_REGIAO = {
    "LESTE":  {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
    "GRU":    {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
    "ABCDM":  {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
    "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
}

RENOMEAR_COLUNAS = {
    "TÉCNICO": "Técnico", "MONITOR": "Monitor", "REGIÃO": "Região",
    "Executada": "Executadas", "Não Executada": "Não Exec.", "Pendente": "Pendentes",
    "Alocado": "Alocado", "Considerado": "Considerado", "Quebra Atual": "Quebra Atual",
    "Fechamento Otimista": "Fech. Otimista", "Fechamento Base": "Fech. Base",
    "Fechamento Pessimista": "Fech. Pessimista",
}

COLUNAS_INTEIRAS = ["Executada", "Não Executada", "Pendente", "Alocado", "Considerado"]

FMT_QUEBRA = {"Quebra Atual": "{:.2%}", "Fechamento Otimista": "{:.2%}",
              "Fechamento Base": "{:.2%}", "Fechamento Pessimista": "{:.2%}"}


# ============================================================
# 2. ESTILO CSS
# ============================================================
def aplicar_estilo():
    st.markdown("""
    <style>
      .hero { background: linear-gradient(135deg,#0F172A 0%,#1E3A5F 100%);
              padding:2rem; border-radius:1rem; color:white; margin-bottom:2rem; }
      .kpi-card { padding:1.4rem 1.6rem; border-radius:1rem; border-left:5px solid;
                  box-shadow:0 4px 12px rgba(0,0,0,.06); min-height:110px;
                  display:flex; flex-direction:column; justify-content:center;
                  transition:transform .15s ease, box-shadow .15s ease; }
      .kpi-card:hover { transform:translateY(-3px); box-shadow:0 8px 20px rgba(0,0,0,.1); }
      .kpi-val { font-size:1.85rem; font-weight:800; line-height:1.1; margin:.3rem 0; }
      .kpi-lab { font-size:.72rem; text-transform:uppercase; font-weight:700; letter-spacing:.05em; }
      .kpi-sub { font-size:.78rem; margin-top:.2rem; }
      .kpi-card-sm { padding:1rem 1.2rem; border-radius:.75rem; border-left:4px solid;
                     box-shadow:0 2px 8px rgba(0,0,0,.05); min-height:80px;
                     display:flex; flex-direction:column; justify-content:center; margin-bottom:.5rem; }
      .kpi-val-sm { font-size:1.4rem; font-weight:800; line-height:1.1; }
      .kpi-lab-sm { font-size:.68rem; text-transform:uppercase; font-weight:700; letter-spacing:.05em; }
      .kpi-sub-sm { font-size:.72rem; margin-top:.15rem; }
      .segmento-header { padding:1rem 1.5rem; border-radius:.75rem; margin-bottom:1rem;
                         display:flex; align-items:center; gap:1rem; border-left:6px solid; }
      .segmento-titulo { font-size:1.3rem; font-weight:800; }
      .segmento-desc { font-size:.82rem; opacity:.75; }
      .segmento-sla { margin-left:auto; font-size:.78rem; font-weight:700;
                      padding:.3rem .8rem; border-radius:999px; }
      .alerta-sla-critico, .alerta-sla-ok, .alerta-sla-atencao {
          border-radius:.75rem; padding:1rem 1.5rem; color:white; margin:.5rem 0;
          display:flex; align-items:center; gap:.8rem; border:1px solid; }
      .alerta-sla-critico { background:linear-gradient(135deg,#450A0A,#7F1D1D); border-color:#EF4444; }
      .alerta-sla-ok      { background:linear-gradient(135deg,#052E16,#14532D); border-color:#22C55E; }
      .alerta-sla-atencao { background:linear-gradient(135deg,#422006,#7C2D12); border-color:#F97316; }
      .resultado-base { background:linear-gradient(135deg,#0F172A 0%,#1E3A5F 100%);
                        padding:1rem 1.5rem; border-radius:.75rem; margin-bottom:1.5rem;
                        display:flex; align-items:center; flex-wrap:wrap; gap:.6rem; }
      .resultado-base-label { color:#94A3B8; font-size:.8rem; font-weight:700;
                              text-transform:uppercase; letter-spacing:.08em; }
      .resultado-base-regiao { padding:.3rem .9rem; border-radius:999px; font-size:.82rem;
                               font-weight:700; border:2px solid; }
      .resultado-base-count { color:#64748B; font-size:.72rem; margin-left:auto; font-weight:600; }
      .styled-table-wrapper { background:#FFFFFF; border-radius:.75rem; padding:1rem 1.2rem;
                              box-shadow:0 2px 8px rgba(0,0,0,.05); margin-bottom:.5rem; }
      .styled-table-title { font-size:1rem; font-weight:700; color:#0F172A;
                            margin-bottom:.4rem; display:flex; align-items:center; gap:.5rem; }
      .styled-table-badge { font-size:.68rem; background:#E0F2FE; color:#0369A1;
                            padding:.15rem .5rem; border-radius:999px; font-weight:600; }
      div[data-testid="stDataFrame"] > div { border-radius:.5rem; overflow:hidden; }
      .section-header { display:flex; align-items:center; gap:.6rem; margin:1.5rem 0 .8rem;
                        padding-bottom:.4rem; border-bottom:2px solid #E2E8F0; }
      .section-header h3 { margin:0; font-size:1.1rem; color:#0F172A; }
      .insight-box { border-radius:.75rem; padding:1rem 1.2rem; margin:.5rem 0; border-left:4px solid; }
      .insight-titulo { font-size:.82rem; font-weight:700; text-transform:uppercase;
                        letter-spacing:.05em; margin-bottom:.3rem; }
      .insight-texto { font-size:.85rem; line-height:1.5; }
    </style>
    """, unsafe_allow_html=True)


# ============================================================
# 3. COMPONENTES VISUAIS
# ============================================================
def _render_card(target, tema, label, value, sub, tam="lg"):
    t = TEMAS_CARD.get(tema, TEMAS_CARD["azul"])
    sfx = "-sm" if tam == "sm" else ""
    target.markdown(f"""
      <div class="kpi-card{sfx}" style="background:{t['fundo']};border-left-color:{t['borda']};">
        <div class="kpi-lab{sfx}" style="color:{t['titulo']}">{label}</div>
        <div class="kpi-val{sfx}" style="color:{t['texto']}">{value}</div>
        <div class="kpi-sub{sfx}" style="color:{t['titulo']}">{sub}</div>
      </div>""", unsafe_allow_html=True)


def render_kpi(col, label, value, sub="", tema="azul"):
    _render_card(col, tema, label, value, sub, "lg")


def render_kpi_sm(col, label, value, sub="", tema="azul"):
    _render_card(col, tema, label, value, sub, "sm")


def render_segmento_header(tipo, sla_atual, sla_meta):
    cfg = Config.SEGMENTOS_CONFIG.get(tipo, {})
    icone = cfg.get("icone", "📋"); cor = cfg.get("cor", "#334155")
    cor_clara = cfg.get("cor_clara", "#F8FAFC"); desc = cfg.get("descricao", tipo)
    dentro = sla_atual <= sla_meta
    status = "✅ Dentro do SLA" if dentro else "❌ Fora do SLA"
    bg, tx = ("#DCFCE7", "#166534") if dentro else ("#FEE2E2", "#991B1B")
    st.markdown(f"""
      <div class="segmento-header" style="background:{cor_clara};border-left-color:{cor};">
        <span style="font-size:2rem">{icone}</span>
        <div>
          <div class="segmento-titulo" style="color:{cor}">{tipo}</div>
          <div class="segmento-desc" style="color:{cor}">{desc}</div>
        </div>
        <div class="segmento-sla" style="background:{bg};color:{tx}">
          {status} &nbsp;|&nbsp; Quebra: {sla_atual:.2%} &nbsp;|&nbsp; Meta: {sla_meta:.2%}
        </div>
      </div>""", unsafe_allow_html=True)


def render_alerta_sla(quebra, meta, tipo):
    if quebra > meta * 1.2:
        classe, icone = "alerta-sla-critico", "🚨"
        msg = f"<strong>CRÍTICO:</strong> {tipo} está {quebra-meta:.2%} acima da meta. Acione plano de contingência imediato."
    elif quebra > meta:
        classe, icone = "alerta-sla-atencao", "⚠️"
        msg = f"<strong>ATENÇÃO:</strong> {tipo} ultrapassou a meta em {quebra-meta:.2%}. Reforce a execução de pendentes."
    else:
        classe, icone = "alerta-sla-ok", "✅"
        msg = f"<strong>SLA OK:</strong> {tipo} com folga de {meta-quebra:.2%}. Manter ritmo de execução."
    st.markdown(f'<div class="{classe}"><span style="font-size:1.5rem">{icone}</span><span>{msg}</span></div>',
                unsafe_allow_html=True)


INSIGHT_ESTILOS = {
    "info":    ("#EFF6FF", "#3B82F6", "#1D4ED8", "💡 INSIGHT"),
    "alerta":  ("#FFFBEB", "#F59E0B", "#B45309", "⚠️ ATENÇÃO"),
    "critico": ("#FFF1F2", "#EF4444", "#991B1B", "🚨 CRÍTICO"),
    "ok":      ("#F0FDF4", "#22C55E", "#166534", "✅ POSITIVO"),
    "acao":    ("#F5F3FF", "#8B5CF6", "#6D28D9", "🎯 AÇÃO"),
}

def render_insight(texto, tipo="info"):
    bg, bd, tc, tt = INSIGHT_ESTILOS.get(tipo, INSIGHT_ESTILOS["info"])
    st.markdown(f"""
      <div class="insight-box" style="background:{bg};border-left-color:{bd};">
        <div class="insight-titulo" style="color:{tc}">{tt}</div>
        <div class="insight-texto" style="color:#1E293B">{texto}</div>
      </div>""", unsafe_allow_html=True)


def render_resultado_base(regioes, total):
    badges = "".join(
        f'<span class="resultado-base-regiao" style="background:{c["bg"]};color:{c["text"]};border-color:{c["border"]}">{r}</span>'
        for r in sorted(regioes) for c in [CORES_REGIAO.get(r, CORES_REGIAO["OUTRAS"])]
    )
    st.markdown(f"""
      <div class="resultado-base">
        <span class="resultado-base-label">📋 Resultado da Base:</span>
        {badges}
        <span class="resultado-base-count">{total:,} registros</span>
      </div>""", unsafe_allow_html=True)


def render_section(titulo):
    st.markdown(f'<div class="section-header"><h3>{titulo}</h3></div>', unsafe_allow_html=True)


def resolver_renomeacao(df, mapa):
    existentes = set(df.columns); usados = set(); res = {}
    for c in df.columns:
        if c in mapa and mapa[c] != c and mapa[c] not in existentes and mapa[c] not in usados:
            res[c] = mapa[c]; usados.add(mapa[c])
    return res


def render_dataframe(df, titulo="", icone="📊", badge="", fmt=None,
                     color_col=None, color_meta=None, color_invertido=True, height: int | Literal["auto"] = "auto"):
    st.markdown(f"""
      <div class="styled-table-wrapper">
        <div class="styled-table-title">
          <span>{icone}</span><span>{titulo}</span>
          <span class="styled-table-badge">{badge or f"{len(df)} registros"}</span>
        </div>
      </div>""", unsafe_allow_html=True)

    d = df.copy()
    mapa = resolver_renomeacao(d, RENOMEAR_COLUNAS)
    d = d.rename(columns=mapa)
    if fmt: fmt = {mapa.get(k, k): v for k, v in fmt.items()}
    if color_col: color_col = mapa.get(color_col, color_col)
    col_quebra = mapa.get("Quebra Atual", "Quebra Atual")

    for c_orig in COLUNAS_INTEIRAS:
        c_disp = mapa.get(c_orig, c_orig)
        if c_disp in d.columns:
            d[c_disp] = pd.to_numeric(d[c_disp], errors="coerce").fillna(0).astype(int)

    styler = d.style
    if fmt: styler = styler.format(fmt)

    if color_col and color_col in d.columns and color_meta is not None and color_col != col_quebra:
        def _cor(v):
            try: v = float(v)
            except (ValueError, TypeError): return ""
            if color_invertido:
                if v > color_meta: return "background-color:#FEE2E2;color:#991B1B;font-weight:600;"
                if v > color_meta * 0.85: return "background-color:#FEF9C3;color:#854D0E;font-weight:600;"
                return "background-color:#DCFCE7;color:#166534;font-weight:600;"
            if v >= color_meta: return "background-color:#DCFCE7;color:#166534;font-weight:600;"
            if v >= color_meta * 0.85: return "background-color:#FEF9C3;color:#854D0E;font-weight:600;"
            return "background-color:#FEE2E2;color:#991B1B;font-weight:600;"
        styler = styler.map(_cor, subset=pd.Index([color_col]))

    if col_quebra in d.columns:
        styler = styler.map(
            lambda v: "background-color:#1E293B;color:#FFFFFF;font-weight:600;" if not pd.isna(v) and str(v).strip() else "",
            subset=pd.Index([col_quebra]))

    styler = styler.set_table_styles([
        {"selector": "th", "props": [
            ("background-color", "#0F172A"), ("color", "#FFFFFF"), ("font-size", "0.78rem"),
            ("font-weight", "700"), ("text-transform", "uppercase"),
            ("letter-spacing", "0.03em"), ("padding", "0.6rem 0.8rem"), ("border", "none")]},
        {"selector": "td", "props": [
            ("font-size", "0.82rem"), ("padding", "0.5rem 0.8rem"),
            ("border-bottom", "1px solid #F1F5F9")]},
        {"selector": "tr:hover td", "props": [("background-color", "#F8FAFC")]},
    ])
    st.dataframe(styler, use_container_width=True, hide_index=True, height=height)


# ============================================================
# 4. UTILITÁRIOS
# ============================================================
def _norm(t):
    t = str(t).strip().upper()
    t = unicodedata.normalize("NFKD", t).encode("ASCII", "ignore").decode()
    return t.replace(".", "").replace("_", "").replace("  ", " ")


class Utils:
    @staticmethod
    def buscar_coluna(df, palavras):
        if df is None or df.empty: return None
        cols = {_norm(c): c for c in df.columns}
        for p in palavras:
            pn = _norm(p)
            for cn, co in cols.items():
                if pn in cn: return co
        return None

    @staticmethod
    def classificar_status(serie):
        s = serie.fillna("").astype(str).str.strip().str.upper()
        exe = s == "EXECUTADA"
        nex = s.isin(["NÃO EXECUTADA", "NAO EXECUTADA"])
        return pd.Series(np.select([exe, nex], ["Executada", "Não Executada"], default="Pendente"),
                         index=serie.index)

    @staticmethod
    def gerar_excel(df, aba="Dados"):
        out = BytesIO()
        aba = aba[:31]
        with pd.ExcelWriter(out, engine="openpyxl") as w:
            df.to_excel(w, index=False, sheet_name=aba)
            ws = w.sheets[aba]
            for cell in ws[1]:
                cell.fill = PatternFill("solid", fgColor="0F172A")
                cell.font = Font(color="FFFFFF", bold=True)
            for i in range(1, len(df.columns) + 1):
                ws.column_dimensions[get_column_letter(i)].width = 20
        return out.getvalue()


# ============================================================
# 5. CARREGAMENTO DE DADOS
# ============================================================
class DataLoader:
    @staticmethod
    @st.cache_data(show_spinner=False)
    def ler_arquivo(file_bytes, filename):
        bio = BytesIO(file_bytes)
        try:
            if filename.lower().endswith(".csv"):
                bio.seek(0); amostra = bio.read(5000).decode("utf-8", errors="ignore"); bio.seek(0)
                try: sep = csv.Sniffer().sniff(amostra).delimiter
                except Exception: sep = ";"
                return pd.read_csv(bio, sep=sep, encoding="utf-8", dtype=str, engine="python")
            return pd.read_excel(bio, engine="openpyxl", dtype=str)
        except Exception as e:
            st.error(f"Erro ao ler arquivo: {e}")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(ttl=600, show_spinner=False)
    def buscar_gsheets():
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            raw = conn.read(spreadsheet=Config.URL_ATIVOS)
            if raw is None or raw.empty: return pd.DataFrame()
            raw.columns = raw.columns.astype(str).str.strip().str.upper()
            rename = {}
            for pals, alvo in [(["LOGIN", "ID", "MATRÍCULA"], "LOGIN"),
                               (["TÉCNICO", "NOME"], "TÉCNICO"),
                               (["MONITOR", "GESTOR"], "MONITOR")]:
                if c := Utils.buscar_coluna(raw, pals): rename[c] = alvo
            raw = raw.rename(columns=rename)
            raw = raw[[c for c in ["LOGIN", "TÉCNICO", "MONITOR"] if c in raw.columns]].copy()
            if "LOGIN" in raw.columns:
                raw["LOGIN"] = raw["LOGIN"].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.upper()
                raw = raw.drop_duplicates(subset=["LOGIN"], keep="last")
            return raw
        except Exception as e:
            st.warning(f"GSheets falhou ({e}). Usando dados locais.")
            return pd.DataFrame()

    @staticmethod
    @st.cache_data(show_spinner=False)
    def preparar_base(df, df_gs):
        if not isinstance(df, pd.DataFrame) or df.empty: return pd.DataFrame()
        df = df.copy(); df.columns = df.columns.astype(str).str.strip().str.upper()
        rem_susp = rem_con = 0

        col_atv = Utils.buscar_coluna(df, ["STATUS DA ATIVIDADE"])
        if col_atv:
            susp = df[col_atv].fillna("").astype(str).str.upper().str.contains("SUSP", na=False)
            rem_susp = int(susp.sum()); df = df[~susp].copy()

        col_tot = Utils.buscar_coluna(df, ["TOTAL DE TAREFAS"])
        df["TOTAL DE TAREFAS"] = (pd.to_numeric(df[col_tot].astype(str).str.replace(",", "."),
                                                errors="coerce").fillna(0) if col_tot else 0)

        col_con = Utils.buscar_coluna(df, ["CONTRATO", "Nº CONTRATO"])
        if col_con:
            norm = df[col_con].astype(str).str.strip().str.upper()
            valido = ~norm.isin(Config.CONTRATO_VALORES_VAZIOS)
            rem_con = int((~valido).sum()); df = df[valido].copy()

        col_login = Utils.buscar_coluna(df, ["LOGIN", "LOGIN DO TÉCNICO", "USUÁRIO", "MATRÍCULA"])
        gs_ok = isinstance(df_gs, pd.DataFrame) and not df_gs.empty
        if col_login and gs_ok and "LOGIN" in df_gs.columns:
            df[col_login] = df[col_login].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.upper()
            for c in ["TÉCNICO", "MONITOR"]:
                if c in df.columns: df = df.drop(columns=[c])
            df = df.merge(df_gs, left_on=col_login, right_on="LOGIN", how="left")

        df["TÉCNICO"] = df.get("TÉCNICO", pd.Series("NÃO MAPEADO", index=df.index)).fillna("NÃO MAPEADO")
        df["MONITOR"] = df.get("MONITOR", pd.Series("SEM MONITOR", index=df.index)).fillna("SEM MONITOR")

        col_cid = Utils.buscar_coluna(df, ["CIDADE", "LOCALIDADE"])
        if col_cid:
            cidade = (df[col_cid].fillna("").astype(str).str.strip().str.upper()
                      .apply(lambda v: unicodedata.normalize("NFKD", v).encode("ASCII", "ignore").decode()))
        else:
            cidade = pd.Series("", index=df.index)

        df["REGIÃO"] = np.select(
            [cidade.isin(["SAO PAULO"]),
             cidade.isin(["GUARULHOS", "ARUJA", "MOGI DAS CRUZES", "SUZANO",
                          "ITAQUAQUECETUBA", "FERRAZ DE VASCONCELOS", "POA"]),
             cidade.isin(["SANTO ANDRE", "SAO BERNARDO DO CAMPO", "SAO CAETANO DO SUL",
                          "DIADEMA", "MAUA", "RIBEIRAO PIRES", "RIO GRANDE DA SERRA"])],
            ["LESTE", "GRU", "ABCDM"], default="OUTRAS")

        col_status = Utils.buscar_coluna(df, ["STATUS DA O.S 1", "STATUS OS 1"])
        df["Status Contrato"] = Utils.classificar_status(df[col_status]) if col_status else "Pendente"

        col_tipo = Utils.buscar_coluna(df, ["TIPO O.S 1"])
        col_hab = Utils.buscar_coluna(df, ["HABILIDADE DE TRABALHO", "HABILIDADE"])
        tipo_upper = (df[col_tipo].fillna("").astype(str).str.strip().str.upper()
                      .apply(lambda v: unicodedata.normalize("NFKD", v).encode("ASCII", "ignore").decode())
                      if col_tipo else pd.Series("", index=df.index, dtype=str))
        hab_upper = (df[col_hab].fillna("").astype(str).str.upper()
                     if col_hab else pd.Series("", index=df.index, dtype=str))

        flag_gpon = hab_upper.str.contains(r"PON", regex=True, na=False)
        flag_nd = tipo_upper.str.contains("ADESAO", na=False)
        flag_migracao = tipo_upper.str.contains("MUDANCA DE PACOTE", na=False) & flag_gpon
        flag_pme = flag_nd & hab_upper.str.contains("PME", na=False)

        df["TIPO_SERVICO"] = pd.Series(np.select(
            [flag_pme, flag_migracao, flag_gpon, flag_nd],
            ["PME", "Migração", "GPON", "Novos Domicílios"], default="Outros"),
            index=df.index, dtype=str)

        col_cod = Utils.buscar_coluna(df, ["CÓD DE BAIXA 1", "COD DE BAIXA 1", "CÓDIGO DE BAIXA 1"])
        df["_COL_BAIXA"] = df[col_cod].astype(str) if col_cod else ""

        col_data = Utils.buscar_coluna(df, ["DATA", "DT AGENDA", "DATA AGENDA"])
        df["_DATA_AGENDA"] = (pd.to_datetime(df[col_data], errors="coerce", dayfirst=True)
                              if col_data else pd.NaT)

        df.attrs["diagnostico"] = {"suspensos": rem_susp, "contrato_vazio": rem_con,
                                   "col_status_encontrada": bool(col_status),
                                   "col_baixa": col_cod or ""}
        return df


# ============================================================
# 6. MOTORES DE CÁLCULO
# ============================================================
def _sum_status(df, status):
    return float(df.loc[df["Status Contrato"] == status, "TOTAL DE TAREFAS"].sum())


class Motor:
    @staticmethod
    def quebra_atual(df):
        if not isinstance(df, pd.DataFrame) or df.empty: return 0.0, 0.0
        exe = _sum_status(df, "Executada"); nex = _sum_status(df, "Não Executada")
        cons = exe + nex
        return cons, (nex / cons) if cons > 0 else 0.0

    @staticmethod
    def projetar(df, p):
        keys = ["alocado", "exec", "naoexec", "pend", "quebra_atual",
                "fechamento_proj", "naoexec_proj"]
        if not isinstance(df, pd.DataFrame) or df.empty:
            return dict.fromkeys(keys, 0)
        aloc = float(df["TOTAL DE TAREFAS"].sum())
        exe = _sum_status(df, "Executada"); nex = _sum_status(df, "Não Executada")
        pen = max(0.0, aloc - exe - nex)
        _, qa = Motor.quebra_atual(df)
        nex_proj = nex + (pen * p)
        return dict(alocado=aloc, exec=exe, naoexec=nex, pend=pen, quebra_atual=qa,
                    fechamento_proj=(nex_proj / aloc) if aloc > 0 else 0, naoexec_proj=nex_proj)

    @staticmethod
    def folga_sla(df, sla):
        keys = ["alocado", "exec", "naoexec", "pend", "limite_ne_total",
                "folga_ne_pendente", "folga_pct_pendente", "precisa_executar_pendente", "estourado"]
        if not isinstance(df, pd.DataFrame) or df.empty:
            return {**dict.fromkeys(keys[:-1], 0), "estourado": False}
        aloc = float(df["TOTAL DE TAREFAS"].sum())
        exe = _sum_status(df, "Executada"); nex = _sum_status(df, "Não Executada")
        pen = max(0.0, aloc - exe - nex)
        limite = sla * aloc; folga_tot = limite - nex; folga_pen = max(0.0, min(pen, folga_tot))
        return dict(alocado=aloc, exec=exe, naoexec=nex, pend=pen, limite_ne_total=limite,
                    folga_ne_pendente=folga_pen,
                    folga_pct_pendente=(folga_pen / pen) if pen > 0 else 0,
                    precisa_executar_pendente=max(0.0, pen - folga_pen),
                    estourado=folga_tot < 0)

    @staticmethod
    def tabela_cenarios(df, grupo, p_ot, p_base, p_pess, min_aloc=5):
        if not isinstance(df, pd.DataFrame) or df.empty or grupo not in df.columns:
            return pd.DataFrame()
        pv = pd.pivot_table(df, index=grupo, columns="Status Contrato",
                            values="TOTAL DE TAREFAS", aggfunc="sum", fill_value=0)
        for c in Config.STATUS_ORDEM:
            if c not in pv.columns: pv[c] = 0.0
        out = pv.reset_index()
        out["Considerado"] = out["Executada"] + out["Não Executada"]
        out["Alocado"] = out["Considerado"] + out["Pendente"]
        out["Quebra Atual"] = np.where(out["Considerado"] > 0,
                                        out["Não Executada"] / out["Considerado"], 0)
        for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]:
            out[f"Fechamento {nome}"] = np.where(out["Alocado"] > 0,
                (out["Não Executada"] + out["Pendente"] * p) / out["Alocado"], 0)
        return out[out["Alocado"] >= min_aloc].sort_values("Fechamento Base", ascending=False)

    @staticmethod
    def causa_raiz_segmento(df, tipo, col_baixa, top_n=8):
        df_seg = df[df["TIPO_SERVICO"] == tipo].copy()
        if df_seg.empty or col_baixa not in df_seg.columns: return pd.DataFrame()
        df_nex = df_seg[df_seg["Status Contrato"] == "Não Executada"].copy()
        if df_nex.empty: return pd.DataFrame()
        df_nex["_baixa_norm"] = (df_nex[col_baixa].fillna("Sem Registro").astype(str)
                                 .str.strip().str.upper()
                                 .replace({"NAN": "Sem Registro", "": "Sem Registro"}))
        resumo = (df_nex.groupby("_baixa_norm")["TOTAL DE TAREFAS"].sum()
                  .nlargest(top_n).reset_index())
        resumo.columns = ["Motivo de Baixa", "Volume"]
        total = resumo["Volume"].sum()
        resumo["% do Total"] = resumo["Volume"] / total if total > 0 else 0
        resumo["Acumulado"] = resumo["% do Total"].cumsum()
        return resumo

    @staticmethod
    def evolucao_temporal(df, tipo):
        df_seg = df[(df["TIPO_SERVICO"] == tipo) & (df["_DATA_AGENDA"].notna())].copy()
        if df_seg.empty: return pd.DataFrame()
        df_seg["_dia"] = df_seg["_DATA_AGENDA"].dt.date
        pv = (df_seg.groupby(["_dia", "Status Contrato"])["TOTAL DE TAREFAS"]
              .sum().unstack(fill_value=0))
        for c in ["Executada", "Não Executada", "Pendente"]:
            if c not in pv.columns: pv[c] = 0
        pv["Considerado"] = pv["Executada"] + pv["Não Executada"]
        pv["Quebra"] = np.where(pv["Considerado"] > 0, pv["Não Executada"] / pv["Considerado"], 0)
        return pv.reset_index().rename(columns={"_dia": "Data"})

    @staticmethod
    def comparativo_regioes(df, tipo):
        df_seg = df[df["TIPO_SERVICO"] == tipo].copy()
        if df_seg.empty: return pd.DataFrame()
        pv = pd.pivot_table(df_seg, index="REGIÃO", columns="Status Contrato",
                            values="TOTAL DE TAREFAS", aggfunc="sum", fill_value=0)
        for c in ["Executada", "Não Executada", "Pendente"]:
            if c not in pv.columns: pv[c] = 0
        pv = pv.reset_index()
        pv["Alocado"] = pv["Executada"] + pv["Não Executada"] + pv["Pendente"]
        pv["Considerado"] = pv["Executada"] + pv["Não Executada"]
        pv["Quebra"] = np.where(pv["Considerado"] > 0, pv["Não Executada"] / pv["Considerado"], 0)
        return pv.sort_values("Quebra", ascending=False)

    @staticmethod
    def tecnicos_criticos(df, tipo, p_base, min_aloc=3, top_n=10):
        df_seg = df[df["TIPO_SERVICO"] == tipo].copy()
        return Motor.tabela_cenarios(df_seg, "TÉCNICO", 0.1, p_base, 0.6, min_aloc).head(top_n)


# ============================================================
# 7. PDF EXECUTIVO
# ============================================================
class RelatorioPDF:
    @staticmethod
    def _fmt(v, col=""):
        if pd.isna(v): return "-"
        col_u = str(col).upper()
        if isinstance(v, (float, np.floating)):
            if any(x in col_u for x in ["QUEBRA", "FECHAMENTO", "PERCENTUAL", "%", "FOLGA_PCT"]):
                return f"{v:.2%}"
            if float(v).is_integer(): return f"{int(v):,}".replace(",", ".")
            return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if isinstance(v, (int, np.integer)): return f"{v:,}".replace(",", ".")
        return str(v)

    @staticmethod
    def _tab(df, colunas=None, limite=None, larguras=None):
        if df is None or df.empty: return Table([["Sem dados disponíveis"]])
        base = df.copy()
        if colunas: base = base[[c for c in colunas if c in base.columns]]
        if limite: base = base.head(limite)
        dados = [list(base.columns)]
        for _, ln in base.iterrows():
            dados.append([RelatorioPDF._fmt(ln[c], c) for c in base.columns])
        if larguras is None:
            larguras = [(26.5 * cm) / max(len(base.columns), 1)] * len(base.columns)
        else:
            larguras = [w * cm for w in larguras]
        tab = Table(dados, colWidths=larguras, repeatRows=1, hAlign="LEFT")
        tab.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F172A")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, 0), 7),
            ("FONTSIZE", (0, 1), (-1, -1), 6.5),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        return tab

    @staticmethod
    def _rodape(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7); canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(1.2 * cm, 0.7 * cm, "Gestão de Quebra de Agenda")
        canvas.drawRightString(28.5 * cm, 0.7 * cm, f"Página {doc.page}")
        canvas.restoreState()

    @staticmethod
    def _bloco_segmento(el, styles, titulo, num, df_seg, tipo, sla, p_base, min_aloc, top_n):
        el.append(PageBreak())
        el.append(Paragraph(escape(f"{num}. Análise Estratégica — {titulo}"), styles["Heading2"]))
        if df_seg.empty:
            el.append(Paragraph(f"Não foram encontrados registros {titulo} nos filtros aplicados.",
                                styles["TextoPDF"]))
            return
        m = Motor.projetar(df_seg, p_base); folga = Motor.folga_sla(df_seg, sla)
        resumo = pd.DataFrame([{"Alocado": m["alocado"], "Executadas": m["exec"],
                                "Não Executadas": m["naoexec"], "Pendentes": m["pend"],
                                "Quebra Atual": m["quebra_atual"], "Proj. Base": m["fechamento_proj"],
                                f"Meta {titulo}": sla,
                                "Pendentes a Executar": folga["precisa_executar_pendente"]}])
        el.append(Paragraph(escape(f"Resumo {titulo}"), styles["Heading3"]))
        el.append(RelatorioPDF._tab(resumo))
        el.append(Spacer(1, 0.3 * cm))
        df_tec = Motor.tecnicos_criticos(df_seg, tipo, p_base, int(min_aloc), int(top_n))
        el.append(Paragraph(escape(f"Técnicos Críticos {titulo}"), styles["Heading3"]))
        if not df_tec.empty:
            el.append(RelatorioPDF._tab(df_tec, limite=int(top_n),
                                        larguras=[5.0, 2.5, 2.5, 2.8, 2.5, 3.0, 3.0, 3.0, 3.0]))
        else:
            el.append(Paragraph(f"Sem dados suficientes para ranking {titulo}.", styles["TextoPDF"]))
        el.append(Spacer(1, 0.3 * cm))
        df_causa = Motor.causa_raiz_segmento(df_seg, tipo, "_COL_BAIXA", top_n=8)
        el.append(Paragraph(escape(f"Principais Motivos de Baixa {titulo}"), styles["Heading3"]))
        if not df_causa.empty:
            el.append(RelatorioPDF._tab(df_causa))
        else:
            el.append(Paragraph(f"Motivos de baixa não identificados para {titulo}.", styles["TextoPDF"]))

    @staticmethod
    def gerar(df, p_ot, p_base, p_pess, sla_pme, sla_mig, min_aloc, top_n,
              incluir_base_detalhada=False):
        buf = BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=landscape(A4),
                                rightMargin=1.0 * cm, leftMargin=1.0 * cm,
                                topMargin=1.0 * cm, bottomMargin=1.2 * cm)
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="TituloExecutivo", parent=styles["Title"],
                                  fontName="Helvetica-Bold", fontSize=22, leading=26,
                                  textColor=colors.HexColor("#0F172A"),
                                  alignment=TA_CENTER, spaceAfter=6))
        styles.add(ParagraphStyle(name="SubtituloExecutivo", parent=styles["Normal"],
                                  fontName="Helvetica", fontSize=10, leading=14,
                                  textColor=colors.HexColor("#475569"),
                                  alignment=TA_CENTER, spaceAfter=18))
        for h, sz, cor, sa in [("Heading2", 14, "#1E3A5F", 8), ("Heading3", 10, "#334155", 5)]:
            styles[h].fontName = "Helvetica-Bold"; styles[h].fontSize = sz
            styles[h].leading = sz + 4; styles[h].textColor = colors.HexColor(cor)
            styles[h].spaceBefore = 12 if h == "Heading2" else 10
            styles[h].spaceAfter = sa
        styles.add(ParagraphStyle(name="TextoPDF", parent=styles["Normal"], fontSize=8,
                                  leading=11, textColor=colors.HexColor("#334155"), alignment=TA_LEFT))

        el = []
        el.append(Paragraph("RELATÓRIO EXECUTIVO<br/>GESTÃO DE QUEBRA DE AGENDA", styles["TituloExecutivo"]))
        el.append(Paragraph(f"Base analisada: {len(df):,} registros | Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
                            styles["SubtituloExecutivo"]))

        # ── Resumo Executivo
        m = Motor.projetar(df, p_base); folga = Motor.folga_sla(df, Config.SLA_QUEBRA_MAXIMA)
        resumo = pd.DataFrame([{"Alocado": m["alocado"], "Executadas": m["exec"],
                                "Não Executadas": m["naoexec"], "Pendentes": m["pend"],
                                "Quebra Atual": m["quebra_atual"], "Projeção Base": m["fechamento_proj"],
                                "Meta Geral": Config.SLA_QUEBRA_MAXIMA,
                                "Folga SLA": folga["folga_ne_pendente"]}])
        el.append(Paragraph("1. Resumo Executivo", styles["Heading2"]))
        el.append(RelatorioPDF._tab(resumo, larguras=[3.2, 3.2, 3.2, 3.0, 3.2, 3.4, 2.8, 3.0]))
        el.append(Spacer(1, 0.4 * cm))
        status = "FORA DO SLA" if m["fechamento_proj"] > Config.SLA_QUEBRA_MAXIMA else "DENTRO DO SLA"
        el.append(Paragraph(
            f"<b>Status projetado:</b> {status}<br/>"
            f"<b>Quebra atual:</b> {m['quebra_atual']:.2%}<br/>"
            f"<b>Projeção cenário base:</b> {m['fechamento_proj']:.2%}<br/>"
            f"<b>Meta global:</b> {Config.SLA_QUEBRA_MAXIMA:.2%}<br/>"
            f"<b>Pendentes que precisam ser executadas para garantir a meta:</b> "
            f"{int(np.ceil(folga['precisa_executar_pendente'])):,}", styles["TextoPDF"]))
        el.append(Spacer(1, 0.4 * cm))

        # ── Cenários
        el.append(Paragraph("2. Cenários de Fechamento", styles["Heading2"]))
        df_cen = pd.DataFrame([
            {"Cenário": nome, "Probabilidade de Quebra Pendentes": p,
             "Fechamento Projetado": Motor.projetar(df, p)["fechamento_proj"],
             "Não Executadas Projetadas": Motor.projetar(df, p)["naoexec_proj"]}
            for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]])
        el.append(RelatorioPDF._tab(df_cen, larguras=[6.0, 7.0, 7.0, 7.0]))

        # ── Tipos de Serviço
        el.append(Paragraph("3. Performance por Tipo de Serviço", styles["Heading2"]))
        linhas = []
        for tipo in ["PME", "Migração", "GPON", "Novos Domicílios", "Outros"]:
            df_t = df[df["TIPO_SERVICO"] == tipo].copy()
            if df_t.empty: continue
            meta = sla_pme if tipo == "PME" else (sla_mig if tipo == "Migração" else Config.SLA_QUEBRA_MAXIMA)
            mt = Motor.projetar(df_t, p_base)
            linhas.append({"Tipo de Serviço": tipo, "Alocado": mt["alocado"],
                           "Executadas": mt["exec"], "Não Executadas": mt["naoexec"],
                           "Pendentes": mt["pend"], "Quebra Atual": mt["quebra_atual"],
                           "Proj. Base": mt["fechamento_proj"], "Meta SLA": meta,
                           "Status": "Fora do SLA" if mt["fechamento_proj"] > meta else "Dentro do SLA"})
        df_tp = pd.DataFrame(linhas)
        if not df_tp.empty:
            el.append(RelatorioPDF._tab(df_tp, larguras=[4.0, 2.7, 2.7, 3.0, 2.7, 3.0, 3.0, 2.7, 3.2]))

        # ── PME e Migração
        RelatorioPDF._bloco_segmento(el, styles, "PME", 4, df[df["TIPO_SERVICO"] == "PME"].copy(),
                                     "PME", sla_pme, p_base, min_aloc, top_n)
        RelatorioPDF._bloco_segmento(el, styles, "Migração", 5, df[df["TIPO_SERVICO"] == "Migração"].copy(),
                                     "Migração", sla_mig, p_base, min_aloc, top_n)

        # ── Rankings
        el.append(PageBreak())
        el.append(Paragraph("6. Rankings Operacionais", styles["Heading2"]))
        for tit, grp in [("Ranking de Monitores", "MONITOR"), ("Ranking de Técnicos", "TÉCNICO")]:
            df_r = Motor.tabela_cenarios(df, grp, p_ot, p_base, p_pess, int(min_aloc))
            el.append(Paragraph(tit, styles["Heading3"]))
            if not df_r.empty:
                el.append(RelatorioPDF._tab(df_r.head(int(top_n)),
                                            larguras=[5.0, 2.5, 2.5, 2.8, 2.5, 3.0, 3.0, 3.0, 3.0]))
            else:
                el.append(Paragraph(f"Sem dados para {tit.lower()}.", styles["TextoPDF"]))
            el.append(Spacer(1, 0.5 * cm))

        # ── Regiões
        el.append(PageBreak())
        el.append(Paragraph("7. Performance Regional", styles["Heading2"]))
        for tipo in ["PME", "Migração"]:
            df_reg = Motor.comparativo_regioes(df, tipo)
            el.append(Paragraph(f"Regiões — {tipo}", styles["Heading3"]))
            if not df_reg.empty:
                el.append(RelatorioPDF._tab(df_reg))
            else:
                el.append(Paragraph(f"Sem dados regionais para {tipo}.", styles["TextoPDF"]))
            el.append(Spacer(1, 0.4 * cm))

        # ── Causas Gerais
        el.append(PageBreak())
        el.append(Paragraph("8. Principais Causas de Quebra", styles["Heading2"]))
        if "_COL_BAIXA" in df.columns:
            dfc = (df[df["Status Contrato"] == "Não Executada"]
                   .assign(Motivo=lambda x: x["_COL_BAIXA"].fillna("SEM REGISTRO").astype(str).str.strip().str.upper())
                   .groupby("Motivo")["TOTAL DE TAREFAS"].sum().nlargest(15).reset_index()
                   .rename(columns={"TOTAL DE TAREFAS": "Volume"}))
            tot = dfc["Volume"].sum()
            if tot > 0:
                dfc["% do Total"] = dfc["Volume"] / tot; dfc["Acumulado"] = dfc["% do Total"].cumsum()
            el.append(RelatorioPDF._tab(dfc))
        else:
            el.append(Paragraph("A coluna de motivo/código de baixa não foi encontrada.", styles["TextoPDF"]))

        # ── Base detalhada
        if incluir_base_detalhada:
            el.append(PageBreak())
            el.append(Paragraph("9. Apêndice — Base Detalhada Filtrada", styles["Heading2"]))
            prefer = ["LOGIN", "TÉCNICO", "MONITOR", "REGIÃO", "TIPO_SERVICO",
                      "Status Contrato", "TOTAL DE TAREFAS", "_COL_BAIXA", "_DATA_AGENDA"]
            existentes = [c for c in prefer if c in df.columns]
            dfd = df[existentes].copy().rename(columns={"_COL_BAIXA": "Motivo Baixa", "_DATA_AGENDA": "Data Agenda"})
            el.append(Paragraph(f"Total de registros incluídos no apêndice: {len(dfd):,}", styles["TextoPDF"]))
            el.append(Spacer(1, 0.3 * cm))
            el.append(RelatorioPDF._tab(dfd, larguras=[2.2] * len(dfd.columns)))

        doc.build(el, onFirstPage=RelatorioPDF._rodape, onLaterPages=RelatorioPDF._rodape)
        buf.seek(0)
        return buf.getvalue()


# ============================================================
# 8. ABA SEGMENTO DETALHADO (PME / MIGRAÇÃO)
# ============================================================
ACOES_SEGMENTO = {
    "PME": [
        ("🟡 MÉDIA", "Verificar disponibilidade de técnicos habilitados em PME para redistribuição de carteira nas regiões críticas.", "acao"),
        ("🟡 MÉDIA", "Acionar equipe comercial PME para comunicação proativa com clientes com agenda em risco de quebra.", "acao"),
        ("🟢 BAIXA", "Revisar janelas de atendimento PME — clientes empresariais têm menor flexibilidade de horário. Ajustar agendamentos para períodos de maior disponibilidade.", "info"),
    ],
    "Migração": [
        ("🟠 ALTA", "Verificar estoque de equipamentos GPON nos almoxarifados das regiões com maior quebra — falta de material é causa frequente em migrações.", "alerta"),
        ("🟡 MÉDIA", "Confirmar certificação dos técnicos em instalação GPON. Migrações exigem habilitação técnica específica.", "acao"),
        ("🟡 MÉDIA", "Priorizar agendamentos de migração no início do turno — instações GPON têm tempo médio maior e impactam mais a quebra quando reagendadas.", "acao"),
        ("🟢 BAIXA", "Validar se ordens de Migração com status 'Pendente' possuem pré-vistoria aprovada. Evita quebra por impedimento técnico no dia do atendimento.", "info"),
    ],
}


def render_aba_segmento(df, tipo, p_ot, p_base, p_pess, min_aloc, top_n, col_baixa, sla_meta):
    df_seg = df[df["TIPO_SERVICO"] == tipo].copy()
    if df_seg.empty:
        st.info(f"Nenhum dado para o segmento **{tipo}** nos filtros selecionados."); return

    m_seg = Motor.projetar(df_seg, p_base)
    render_segmento_header(tipo, m_seg["quebra_atual"], sla_meta)
    render_alerta_sla(m_seg["quebra_atual"], sla_meta, tipo)
    st.markdown("")

    sub1, sub2, sub3, sub4, sub5 = st.tabs(
        ["📊 Visão Geral", "🔍 Causa Raiz", "👤 Técnicos Críticos", "🗺️ Por Região", "🎯 Plano de Ação"])

    # ── Sub-aba 1: Visão Geral
    with sub1:
        render_section(f"📊 Resumo Operacional — {tipo}")
        cols = st.columns(5)
        for c, (lab, val, tema, sub) in zip(cols, [
            ("Alocado", f"{int(m_seg['alocado']):,}", "azul", ""),
            ("Executadas", f"{int(m_seg['exec']):,}", "verde", ""),
            ("Não Exec.", f"{int(m_seg['naoexec']):,}", "laranja", ""),
            ("Pendentes", f"{int(m_seg['pend']):,}", "cinza", ""),
            ("Quebra Atual", f"{m_seg['quebra_atual']:.2%}",
             "vermelho" if m_seg["quebra_atual"] > sla_meta else "verde", f"Meta: {sla_meta:.0%}")
        ]):
            render_kpi(c, lab, val, sub=sub, tema=tema)

        st.markdown("")
        render_section("🔮 Projeções de Fechamento")
        cen_seg = {n: Motor.projetar(df_seg, p) for n, p in
                   [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]}
        c_cen, c_gauge = st.columns([2, 3])
        with c_cen:
            for nome, cd in cen_seg.items():
                cor = "vermelho" if cd["fechamento_proj"] > sla_meta else "verde"
                render_kpi_sm(st, nome, f"{cd['fechamento_proj']:.2%}",
                              sub=f"Não Exec. proj.: {int(cd['naoexec_proj']):,}", tema=cor)
        with c_gauge:
            cor_bar = "#EF4444" if m_seg["quebra_atual"] > sla_meta else "#10B981"
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta", value=m_seg["quebra_atual"] * 100,
                delta={"reference": sla_meta * 100, "increasing": {"color": "#EF4444"},
                       "decreasing": {"color": "#10B981"}, "suffix": "%"},
                number={"suffix": "%", "font": {"size": 40, "color": "#0F172A"}},
                gauge={"axis": {"range": [0, 50], "ticksuffix": "%"},
                       "bar": {"color": cor_bar},
                       "steps": [{"range": [0, sla_meta * 100], "color": "#DCFCE7"},
                                 {"range": [sla_meta * 100, sla_meta * 120], "color": "#FEF9C3"},
                                 {"range": [sla_meta * 120, 50], "color": "#FEE2E2"}],
                       "threshold": {"line": {"color": "#DC2626", "width": 3},
                                     "thickness": 0.85, "value": sla_meta * 100}},
                title={"text": f"Quebra Atual vs. Meta {sla_meta:.0%}", "font": {"size": 14}}))
            fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

        st.markdown(""); render_section("🛡️ Folga de SLA")
        folga = Motor.folga_sla(df_seg, sla_meta)
        f1, f2, f3 = st.columns(3)
        cor_f = "vermelho" if folga["estourado"] else ("verde" if folga["folga_ne_pendente"] > 0 else "laranja")
        render_kpi(f1, "Folga (OS)", f"{int(np.floor(folga['folga_ne_pendente'])):,}",
                   sub="Não Exec. ainda permitidas", tema=cor_f)
        render_kpi(f2, "Execução Mínima", f"{int(np.ceil(folga['precisa_executar_pendente'])):,}",
                   sub="Pendentes que devem ser executadas", tema="azul")
        render_kpi(f3, "Limite NE Total", f"{int(folga['limite_ne_total']):,}",
                   sub=f"= {sla_meta:.0%} × {int(folga['alocado']):,}", tema="cinza")
        st.progress(min(1.0, max(0.0, float(m_seg["quebra_atual"] / (sla_meta * 2)))))

        df_ev = Motor.evolucao_temporal(df_seg, tipo)
        if not df_ev.empty:
            st.markdown(""); render_section("📅 Evolução Diária")
            fig_ev = go.Figure()
            fig_ev.add_trace(go.Scatter(x=df_ev["Data"], y=df_ev["Quebra"], mode="lines+markers",
                                        name="Quebra", line=dict(color="#EF4444", width=2),
                                        fill="tozeroy", fillcolor="rgba(239,68,68,0.08)"))
            fig_ev.add_hline(y=sla_meta, line_dash="dash", line_color="#DC2626",
                             annotation_text=f"Meta {sla_meta:.0%}", annotation_position="top left")
            fig_ev.update_layout(yaxis_tickformat=".1%", height=280,
                                 margin=dict(t=20, b=20, l=10, r=10), legend=dict(orientation="h"))
            st.plotly_chart(fig_ev, use_container_width=True, config={"displayModeBar": False})
        else:
            render_insight("Data de agenda não encontrada na base — análise temporal indisponível. "
                           "Certifique-se de que a coluna 'DATA AGENDA' está presente.", tipo="alerta")

    # ── Sub-aba 2: Causa Raiz
    with sub2:
        render_section(f"🔍 Causa Raiz — {tipo}")
        df_c = Motor.causa_raiz_segmento(df_seg, tipo, "_COL_BAIXA", top_n=8)
        if df_c.empty:
            render_insight("Coluna de código/motivo de baixa não identificada. "
                           "Verifique se a base contém 'CÓD DE BAIXA 1' ou similar.", tipo="alerta")
        else:
            c_tab, c_chart = st.columns([1.2, 2])
            with c_tab:
                render_dataframe(df_c, titulo=f"Top Motivos — {tipo}", icone="🔍",
                                 fmt={"% do Total": "{:.2%}", "Acumulado": "{:.2%}"}, height=350)
            with c_chart:
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_c["Motivo de Baixa"], y=df_c["Volume"], name="Volume",
                                     marker_color="#EF4444", text=df_c["Volume"], textposition="outside"))
                fig.add_trace(go.Scatter(x=df_c["Motivo de Baixa"], y=df_c["Acumulado"],
                                         name="Acumulado %", yaxis="y2", mode="lines+markers",
                                         line=dict(color="#0EA5E9", width=2), marker=dict(size=7)))
                fig.update_layout(title=f"Pareto de Motivos de Quebra — {tipo}",
                                  yaxis=dict(title="Volume de OS"),
                                  yaxis2=dict(title="Acumulado %", overlaying="y", side="right",
                                              tickformat=".0%", range=[0, 1.1]),
                                  legend=dict(orientation="h", yanchor="bottom", y=1.02),
                                  height=380, margin=dict(t=50, b=80, l=10, r=60),
                                  xaxis=dict(tickangle=-30))
                fig.add_hline(y=0.8, line_dash="dot", line_color="#F59E0B", yref="y2",
                              annotation_text="80%", annotation_position="top right")
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            if len(df_c) >= 2:
                t1, t2 = df_c.iloc[0], df_c.iloc[1]
                render_insight(
                    f"Os 2 principais motivos (<strong>{t1['Motivo de Baixa']}</strong> e "
                    f"<strong>{t2['Motivo de Baixa']}</strong>) respondem por "
                    f"<strong>{t2['Acumulado']:.1%}</strong> do total de quebras em {tipo}. "
                    f"Focar nesses pontos é o caminho mais rápido para redução de SLA.", tipo="acao")

    # ── Sub-aba 3: Técnicos Críticos
    with sub3:
        render_section(f"👤 Técnicos com Maior Quebra — {tipo}")
        df_tec = Motor.tecnicos_criticos(df_seg, tipo, p_base, int(min_aloc), int(top_n))
        if df_tec.empty:
            render_insight(f"Não há técnicos com volume mínimo de {int(min_aloc)} OS neste segmento.", tipo="info")
        else:
            render_dataframe(df_tec, titulo=f"Técnicos Críticos — {tipo}", icone="🚨",
                             fmt=FMT_QUEBRA, color_col="Fechamento Base",
                             color_meta=sla_meta, color_invertido=True, height=450)
            st.download_button(f"📥 Exportar Técnicos {tipo}",
                               Utils.gerar_excel(df_tec, f"Tec_{tipo[:25]}"),
                               f"tecnicos_criticos_{tipo.lower().replace(' ', '_')}.xlsx",
                               key=f"dl_tec_{tipo}")
            df_plot = df_tec.head(10).sort_values("Fechamento Base")
            cores = ["#EF4444" if v > sla_meta else "#10B981" for v in df_plot["Fechamento Base"]]
            fig = go.Figure()
            fig.add_trace(go.Bar(y=df_plot["TÉCNICO"], x=df_plot["Fechamento Base"],
                                 orientation="h", marker_color=cores,
                                 text=[f"{v:.1%}" for v in df_plot["Fechamento Base"]],
                                 textposition="outside"))
            fig.add_vline(x=sla_meta, line_dash="dash", line_color="#DC2626",
                          annotation_text=f"Meta {sla_meta:.0%}")
            fig.update_layout(title=f"Quebra Projetada (Base) por Técnico — {tipo}",
                              xaxis_tickformat=".1%", height=max(300, len(df_plot) * 36),
                              margin=dict(t=40, b=20, l=10, r=60))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

            acima = (df_tec["Fechamento Base"] > sla_meta).sum(); pct = acima / len(df_tec)
            if pct > 0.5:
                render_insight(f"<strong>{acima} de {len(df_tec)}</strong> técnicos ({pct:.0%}) "
                               f"estão acima da meta de {sla_meta:.0%} no segmento {tipo}. "
                               f"Avalie redistribuição de carteira e suporte técnico especializado.", tipo="critico")
            elif acima > 0:
                render_insight(f"<strong>{acima} técnico(s)</strong> com quebra acima da meta. "
                               f"Ação individual recomendada: feedback + acompanhamento de campo.", tipo="alerta")
            else:
                render_insight(f"Todos os técnicos com quebra dentro da meta no segmento {tipo}. "
                               f"Mantenha o monitoramento preventivo.", tipo="ok")

    # ── Sub-aba 4: Regiões
    with sub4:
        render_section(f"🗺️ Performance por Região — {tipo}")
        df_reg = Motor.comparativo_regioes(df_seg, tipo)
        if df_reg.empty:
            render_insight("Coluna de região não encontrada.", tipo="alerta")
        else:
            c_mapa, c_tab = st.columns([2, 1.5])
            with c_mapa:
                cores = ["#EF4444" if v > sla_meta else "#10B981" for v in df_reg["Quebra"]]
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_reg["REGIÃO"], y=df_reg["Quebra"], marker_color=cores,
                                     text=[f"{v:.1%}" for v in df_reg["Quebra"]],
                                     textposition="outside", name="Quebra"))
                fig.add_hline(y=sla_meta, line_dash="dash", line_color="#DC2626",
                              annotation_text=f"Meta {sla_meta:.0%}")
                fig.add_trace(go.Scatter(x=df_reg["REGIÃO"], y=df_reg["Alocado"],
                                         mode="lines+markers", name="Alocado", yaxis="y2",
                                         line=dict(color="#0EA5E9", width=2, dash="dot")))
                fig.update_layout(title=f"Quebra e Volume por Região — {tipo}",
                                  yaxis=dict(tickformat=".1%", title="Quebra"),
                                  yaxis2=dict(title="Alocado", overlaying="y", side="right"),
                                  height=320, margin=dict(t=40, b=20, l=10, r=60),
                                  legend=dict(orientation="h"))
                st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            with c_tab:
                render_dataframe(df_reg[["REGIÃO", "Alocado", "Executada", "Não Executada", "Pendente", "Quebra"]],
                                 titulo="Detalhamento Regional", icone="🗺️",
                                 fmt={"Quebra": "{:.2%}"}, color_col="Quebra",
                                 color_meta=sla_meta, color_invertido=True, height=300)
            pior = df_reg.loc[df_reg["Quebra"].idxmax()]; melhor = df_reg.loc[df_reg["Quebra"].idxmin()]
            render_insight(
                f"Região mais crítica: <strong>{pior['REGIÃO']}</strong> com quebra de "
                f"<strong>{pior['Quebra']:.2%}</strong> ({int(pior['Alocado'].item()):,} OS alocadas). "
                f"Melhor desempenho: <strong>{melhor['REGIÃO']}</strong> ({melhor['Quebra']:.2%}). "
                f"Diferença de <strong>{(pior['Quebra'] - melhor['Quebra']):.2%}</strong> entre as regiões.",
                tipo="info")

            st.markdown(""); render_section("👔 Monitores × Região")
            if "MONITOR" in df_seg.columns:
                df_mr = Motor.tabela_cenarios(df_seg, "MONITOR", p_ot, p_base, p_pess, int(min_aloc))
                if not df_mr.empty:
                    render_dataframe(df_mr.head(int(top_n)), titulo=f"Monitores — {tipo}", icone="👔",
                                     fmt=FMT_QUEBRA, color_col="Fechamento Base",
                                     color_meta=sla_meta, color_invertido=True, height=380)

    # ── Sub-aba 5: Plano de Ação
    with sub5:
        render_section(f"🎯 Plano de Ação — {tipo}")
        folga_pa = Motor.folga_sla(df_seg, sla_meta); cen_pa = Motor.projetar(df_seg, p_base)
        excesso_ne = max(0.0, folga_pa["naoexec"] - folga_pa["limite_ne_total"])
        pend_exec = folga_pa["precisa_executar_pendente"]

        col_d, col_a = st.columns([1, 1.5])
        with col_d:
            render_section("📋 Diagnóstico")
            render_kpi_sm(st, "Excesso de NE vs. Limite", f"{int(excesso_ne):,}",
                          sub="OS além do permitido pela meta",
                          tema="vermelho" if excesso_ne > 0 else "verde")
            render_kpi_sm(st, "Pendentes a Executar", f"{int(np.ceil(pend_exec)):,}",
                          sub=f"Mínimo para atingir meta {sla_meta:.0%}", tema="azul")
            render_kpi_sm(st, "Proj. Cenário Base", f"{cen_pa['fechamento_proj']:.2%}",
                          sub=f"c/ {p_base:.0%} de quebra nos pendentes",
                          tema="vermelho" if cen_pa["fechamento_proj"] > sla_meta else "verde")
            st.markdown("")
            if folga_pa["pend"] > 0:
                tx = 1 - (folga_pa["folga_ne_pendente"] / folga_pa["pend"])
                st.markdown(f"**Taxa mínima de execução nos pendentes:** `{max(0, tx):.1%}`")
                st.progress(min(1.0, max(0.0, float(tx))))

        with col_a:
            render_section("✅ Ações Recomendadas")
            acoes = []
            if folga_pa["estourado"]:
                acoes.append(("🔴 IMEDIATA",
                              f"Acionar equipe de plantão para recuperação das {int(excesso_ne):,} OS não executadas acima do limite.",
                              "critico"))
            if pend_exec > 0:
                acoes.append(("🟠 ALTA",
                              f"Garantir execução de pelo menos {int(np.ceil(pend_exec)):,} das OS pendentes de {tipo} para atingir a meta de {sla_meta:.0%}.",
                              "alerta"))
            acoes.extend(ACOES_SEGMENTO.get(tipo, []))
            for pri, ac, tp in acoes:
                render_insight(f"<strong>{pri}</strong> — {ac}", tipo=tp)

        st.markdown("")
        df_plano = pd.DataFrame([{"Segmento": tipo, "Prioridade": p, "Ação": a} for p, a, _ in acoes])
        if not df_plano.empty:
            st.download_button(f"📥 Exportar Plano de Ação — {tipo}",
                               Utils.gerar_excel(df_plano, f"Plano_{tipo[:25]}"),
                               f"plano_acao_{tipo.lower().replace(' ', '_')}.xlsx",
                               key=f"dl_plano_{tipo}")


# ============================================================
# 9. APLICAÇÃO PRINCIPAL
# ============================================================
def _upload_inicial():
    render_section("📁 Importação de Dados")
    arq = st.file_uploader("Selecione a base (Excel/CSV)", type=["xlsx", "csv"])
    if not arq: return
    with st.spinner("Processando..."):
        raw = DataLoader.ler_arquivo(arq.getvalue(), arq.name)
        gs = DataLoader.buscar_gsheets()
        df_proc = DataLoader.preparar_base(raw, gs)
        st.session_state["df_memoria"] = df_proc
    diag = df_proc.attrs.get("diagnostico", {})
    if diag.get("contrato_vazio", 0):
        st.toast(f"🗑️ {diag['contrato_vazio']} linha(s) sem contrato removida(s).", icon="⚠️")
    if diag.get("suspensos", 0):
        st.toast(f"🗑️ {diag['suspensos']} ordens suspensas removidas.", icon="ℹ️")
    if not diag.get("col_status_encontrada", False):
        st.warning("⚠️ Coluna 'Status da O.S 1' não encontrada.")
    st.rerun()


def _sidebar_filtros(df_full):
    with st.sidebar:
        st.header("🎯 Filtros")
        monitores = ["Todos"] + sorted(str(x) for x in df_full["MONITOR"].dropna().unique()
                                        if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"})
        sel_mon = st.selectbox("👔 Monitor", monitores)
        df_filt = df_full if sel_mon == "Todos" else df_full[df_full["MONITOR"] == sel_mon]

        tecnicos = ["Todos"] + sorted(str(x) for x in df_filt["TÉCNICO"].dropna().unique()
                                       if str(x) not in {"nan", "NÃO MAPEADO"})
        sel_tec = st.selectbox("👤 Técnico", tecnicos)
        df = df_filt if sel_tec == "Todos" else df_filt[df_filt["TÉCNICO"] == sel_tec]

        st.divider(); st.subheader("🔮 Probabilidade de Quebra")
        p_ot = st.slider("Otimista (%)", 0, 100, 10, 5) / 100.0
        p_base = st.slider("Base (%)", 0, 100, 30, 5) / 100.0
        p_pess = st.slider("Pessimista (%)", 0, 100, 60, 5) / 100.0

        st.divider(); st.subheader("⚙️ SLA por Segmento")
        sla_pme = st.number_input("Meta SLA PME (%)", 0.0, 100.0, 15.0, 1.0) / 100
        sla_mig = st.number_input("Meta SLA Migração (%)", 0.0, 100.0, 18.0, 1.0) / 100

        st.divider()
        min_aloc = st.number_input("Mín. OS (Rankings)", min_value=1, value=5)
        top_n = st.number_input("Visualizar Top N", min_value=1, value=10)

    return df, p_ot, p_base, p_pess, sla_pme, sla_mig, min_aloc, top_n


def _sidebar_pdf(df, p_ot, p_base, p_pess, sla_pme, sla_mig, min_aloc, top_n):
    with st.sidebar:
        st.divider(); st.subheader("📄 Relatório Executivo")
        incluir = st.checkbox("Incluir base detalhada no PDF", value=False,
                              help="Pode gerar um arquivo grande caso existam muitos registros.")
        if st.button("📄 Gerar PDF Executivo", use_container_width=True):
            with st.spinner("Gerando relatório executivo em PDF..."):
                st.session_state["pdf_executivo"] = RelatorioPDF.gerar(
                    df=df, p_ot=p_ot, p_base=p_base, p_pess=p_pess,
                    sla_pme=sla_pme, sla_mig=sla_mig, min_aloc=min_aloc,
                    top_n=top_n, incluir_base_detalhada=incluir)
        if st.session_state.get("pdf_executivo"):
            st.download_button(
                label="⬇️ Baixar PDF Executivo",
                data=st.session_state["pdf_executivo"],
                file_name=f"relatorio_quebra_agenda_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf", use_container_width=True)


def _aba_visao(df, p_ot, p_base, p_pess):
    render_section("🔮 Análise e Simulações de SLA")
    cen = {n: Motor.projetar(df, p) for n, p in
           [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]}
    c1, c2 = st.columns([3, 2.5])
    with c1:
        cols = st.columns(3)
        for c, (n, tema_d) in zip(cols, [("Otimista", "cinza"), ("Base", "roxo"), ("Pessimista", "cinza")]):
            proj = cen[n]
            cor = "vermelho" if proj["fechamento_proj"] > Config.SLA_QUEBRA_MAXIMA else tema_d
            render_kpi(c, n, f"{proj['fechamento_proj']:.2%}",
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
    with c2:
        df_plot = pd.DataFrame({"Cenário": ["Otimista", "Base", "Pessimista"],
                                "Fechamento": [cen[s]["fechamento_proj"] for s in ["Otimista", "Base", "Pessimista"]]})
        fig = px.bar(df_plot, x="Cenário", y="Fechamento", color="Fechamento",
                     color_continuous_scale="Purples", title="Cenários Projetados")
        fig.update_traces(texttemplate="%{y:.2%}", textposition="outside")
        fig.add_hline(y=Config.SLA_QUEBRA_MAXIMA, line_dash="dash", line_color="red",
                      annotation_text="Meta", annotation_position="top left")
        fig.update_layout(yaxis_tickformat=".0%", coloraxis_showscale=False,
                          height=380, margin=dict(t=40, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _aba_desempenho(df, df_full, p_ot, p_base, p_pess, min_aloc, top_n):
    t_mon, t_tec = st.tabs(["👔 Monitores", "👤 Técnicos"])
    for tab, dfr, tit, arq_nome, key_grp in [
        (t_mon, Motor.tabela_cenarios(df_full, "MONITOR", p_ot, p_base, p_pess, int(min_aloc)),
         "Ranking de Monitores", "ranking_monitores.xlsx", "Monitores"),
        (t_tec, Motor.tabela_cenarios(df, "TÉCNICO", p_ot, p_base, p_pess, int(min_aloc)),
         "Ranking de Técnicos", "ranking_tecnicos.xlsx", "Tecnicos"),
    ]:
        with tab:
            if dfr.empty:
                st.info("Sem dados suficientes.")
            else:
                if key_grp == "Tecnicos":
                    dfr = dfr.sort_values(by=["Fechamento Base", "Quebra Atual", "Alocado"],
                                          ascending=[False, False, False]).reset_index(drop=True)
                render_dataframe(dfr.head(int(top_n)), titulo=tit,
                                 icone="👔" if "Monitor" in tit else "👤",
                                 fmt=FMT_QUEBRA, color_col="Fechamento Base",
                                 color_meta=Config.SLA_QUEBRA_MAXIMA,
                                 color_invertido=True, height=500)
                st.download_button(f"📥 Baixar {tit}", Utils.gerar_excel(dfr, key_grp), arq_nome)


def _aba_causas(df, df_full):
    render_section("🔍 Análise de Causa Raiz")
    col_cod = Utils.buscar_coluna(df_full, ["CÓD DE BAIXA 1", "COD DE BAIXA 1", "CÓDIGO DE BAIXA 1", "COD BAIXA 1"])
    c1, c2 = st.columns([1, 2])
    with c1:
        df_dist = df.groupby("Status Contrato")["TOTAL DE TAREFAS"].sum().reset_index()
        fig = px.pie(df_dist, names="Status Contrato", values="TOTAL DE TAREFAS", hole=0.5,
                     color="Status Contrato", color_discrete_map=Config.CORES_STATUS)
        fig.update_layout(legend=dict(orientation="h", yanchor="bottom", y=-0.2),
                          margin=dict(t=10, b=10, l=10, r=10), height=350)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        if col_cod and col_cod in df.columns:
            df_c = (df[df["Status Contrato"] == "Não Executada"]
                    .groupby(col_cod)["TOTAL DE TAREFAS"].sum().nlargest(5).reset_index())
            if not df_c.empty:
                fig = px.bar(df_c, x="TOTAL DE TAREFAS", y=col_cod, orientation="h",
                             text="TOTAL DE TAREFAS", color_discrete_sequence=["#EF4444"])
                fig.update_layout(yaxis={"categoryorder": "total ascending"},
                                  margin=dict(t=10, b=10, l=5, r=5), height=350)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Nenhuma OS 'Não Executada' com motivo.")
        else:
            st.warning("Coluna 'Código de Baixa' não encontrada.")


def _aba_backoffice(df):
    render_section("🚨 Fila de Tratamento (Backoffice)")
    df_back = df[df["Status Contrato"] == "Não Executada"].copy()
    if df_back.empty:
        st.info("Sem dados de Backoffice para 'Não Executada'."); return
    resumo = (df_back.groupby(["MONITOR", "TÉCNICO", "TIPO_SERVICO"])["TOTAL DE TAREFAS"].sum()
              .reset_index().sort_values("TOTAL DE TAREFAS", ascending=False))
    resumo.columns = ["Monitor", "Técnico", "Tipo", "Qtd Não Executadas"]
    render_dataframe(resumo, titulo="Resumo Backoffice — Não Executadas", icone="🚨",
                     badge=f"{int(df_back['TOTAL DE TAREFAS'].sum()):,} OS", height=500)
    st.download_button("📥 Baixar Resumo Backoffice",
                       Utils.gerar_excel(resumo, "Backoffice_Resumo"), "backoffice_resumo.xlsx")


def _aba_tipos(df, p_ot, p_base, p_pess, min_aloc, top_n):
    render_section("📂 Análise por Tipo de Serviço")
    if "TIPO_SERVICO" not in df.columns:
        st.warning("Coluna de tipo não encontrada."); return
    disponiveis = [t for t in ["PME", "Novos Domicílios", "Migração", "GPON", "Outros"]
                   if t in df["TIPO_SERVICO"].unique()]
    if not disponiveis:
        st.info("Nenhum tipo disponível encontrado."); return
    st.markdown("")
    for sub, tipo in zip(st.tabs([f"📋 {t}" for t in disponiveis]), disponiveis):
        with sub:
            df_t = df[df["TIPO_SERVICO"] == tipo].copy()
            if df_t.empty:
                st.info(f"Sem dados para **{tipo}**."); continue
            m_t = Motor.projetar(df_t, p_base)
            cols = st.columns(4)
            for c, (lab, val, tema) in zip(cols, [
                ("Alocado", f"{int(m_t['alocado']):,}", "azul"),
                ("Executadas", f"{int(m_t['exec']):,}", "verde"),
                ("Não Exec", f"{int(m_t['naoexec']):,}", "laranja"),
                ("Quebra Atual", f"{m_t['quebra_atual']:.2%}",
                 "vermelho" if m_t["quebra_atual"] > Config.SLA_QUEBRA_MAXIMA else "cinza"),
            ]):
                render_kpi(c, lab, val, tema=tema)
            st.markdown("")
            df_r = Motor.tabela_cenarios(df_t, "MONITOR", p_ot, p_base, p_pess, int(min_aloc))
            if not df_r.empty:
                render_dataframe(df_r.head(int(top_n)), titulo=f"Monitores — {tipo}", icone="👔",
                                 fmt=FMT_QUEBRA, color_col="Fechamento Base",
                                 color_meta=Config.SLA_QUEBRA_MAXIMA,
                                 color_invertido=True, height=400)
                st.download_button(f"📥 Baixar {tipo}",
                                   Utils.gerar_excel(df_r, tipo[:31]),
                                   f"ranking_{tipo.lower().replace(' ', '_')}.xlsx",
                                   key=f"dl_tipo_{tipo}")


def main():
    aplicar_estilo()
    st.markdown('<div class="hero"><h1>📉 Gestão de Quebra de Agenda</h1>'
                "<p>Análise de quebra, projeções de SLA e plano de ação operacional</p></div>",
                unsafe_allow_html=True)

    with st.sidebar:
        st.header("⚙️ Configurações")
        if st.button("🔄 Reiniciar Painel", use_container_width=True):
            st.session_state["df_memoria"] = None
            st.session_state["pdf_executivo"] = None
            st.rerun()
        st.divider()

    if st.session_state["df_memoria"] is None:
        _upload_inicial(); return

    df_mem = st.session_state["df_memoria"]
    df_full = df_mem.copy() if isinstance(df_mem, pd.DataFrame) else pd.DataFrame()
    if df_full.empty:
        st.error("Base carregada está vazia. Envie um novo arquivo.")
        st.session_state["df_memoria"] = None; return

    if "Status Contrato" not in df_full.columns:
        col_status = Utils.buscar_coluna(df_full, ["STATUS DA O.S 1", "STATUS OS 1"])
        df_full["Status Contrato"] = (Utils.classificar_status(df_full[col_status])
                                       if col_status else "Pendente")

    df, p_ot, p_base, p_pess, sla_pme, sla_mig, min_aloc, top_n = _sidebar_filtros(df_full)
    _sidebar_pdf(df, p_ot, p_base, p_pess, sla_pme, sla_mig, min_aloc, top_n)

    if df.empty:
        st.warning("Nenhum dado para os filtros selecionados."); return

    render_resultado_base(sorted(df[Config.COL_REGIAO].unique()), len(df))

    # ── KPIs Globais
    m = Motor.projetar(df, p_base)
    cols = st.columns(6)
    for c, (lab, val, tema) in zip(cols, [
        ("Alocado", f"{int(m['alocado']):,}", "azul"),
        ("Executadas", f"{int(m['exec']):,}", "verde"),
        ("Não Exec", f"{int(m['naoexec']):,}", "laranja"),
        ("Pendentes", f"{int(m['pend']):,}", "cinza"),
        ("Quebra Atual", f"{m['quebra_atual']:.2%}", "cinza"),
        ("Proj. Base", f"{m['fechamento_proj']:.2%}",
         "vermelho" if m["fechamento_proj"] > Config.SLA_QUEBRA_MAXIMA else "roxo"),
    ]):
        render_kpi(c, lab, val, tema=tema)
    st.markdown("")

    col_baixa = "_COL_BAIXA" if "_COL_BAIXA" in df.columns else ""
    tabs = st.tabs(["📊 Visão & Projeções", "🧭 Desempenho", "🔍 Causas",
                    "🚨 Backoffice", "📂 Por Tipo de Serviço", "🏢 PME", "🔄 Migração"])

    with tabs[0]: _aba_visao(df, p_ot, p_base, p_pess)
    with tabs[1]: _aba_desempenho(df, df_full, p_ot, p_base, p_pess, min_aloc, top_n)
    with tabs[2]: _aba_causas(df, df_full)
    with tabs[3]: _aba_backoffice(df)
    with tabs[4]: _aba_tipos(df, p_ot, p_base, p_pess, min_aloc, top_n)
    with tabs[5]: render_aba_segmento(df, "PME", p_ot, p_base, p_pess, min_aloc, top_n, col_baixa, sla_pme)
    with tabs[6]: render_aba_segmento(df, "Migração", p_ot, p_base, p_pess, min_aloc, top_n, col_baixa, sla_mig)


if __name__ == "__main__":
    main()