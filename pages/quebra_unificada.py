"""
quebra_unificada.py
===================
Análise de Quebra por Segmento (Migração / PME) - Versão Simplificada e Corrigida
"""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple, cast

import numpy as np
import pandas as pd
import streamlit as st

# ── Componentes corporativos padronizados ─────────────────────────────
from components.componentes import (
    aplicar_estilo as _aplicar_estilo_global,
    render_kpi,
    render_kpi_sm,
    render_insight,
    render_section,
    TemaKPI,
    TipoInsight,
)

# ── Critérios de classificação centralizados ──────────────────────────
from components.criterios import (
    classificar_tipo_servico,
    render_debug_criterios,
)

# =====================================================================
# CONFIGURAÇÃO DA PÁGINA
# =====================================================================
st.set_page_config(
    page_title="Análise de Quebra | TOTALE",
    page_icon="📊",
    layout="wide",
)
_aplicar_estilo_global()

if "df_memoria" not in st.session_state:
    st.session_state["df_memoria"] = None


# =====================================================================
# CONSTANTES E CONFIGURAÇÕES LOCAIS
# =====================================================================
class Config:
    SLA_MIGRACAO: float = 0.25
    SLA_PME: float = 0.20
    COL_REGIAO: str = "REGIÃO"


class Utils:
    @staticmethod
    def buscar_coluna(df: pd.DataFrame, palavras: list) -> Optional[str]:
        if df is None or df.empty:
            return None
        cols = {
            str(c).strip().upper().replace(".", "").replace("_", "").replace("  ", " "): c
            for c in df.columns
        }
        for p in palavras:
            pn = str(p).strip().upper().replace(".", "").replace("_", "").replace("  ", " ")
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


# =====================================================================
# CONFIGURAÇÕES DINÂMICAS POR SEGMENTO
# =====================================================================
SEGMENTOS_CONFIG: Dict[str, Any] = {
    "Migração": {
        "icone": "🔄",
        "subtitulo": "Análise estratégica dedicada às mudanças de pacotes com tecnologia GPON",
        "cor_primaria": "#0369A1",
        "cor_secundaria": "#0C4A6E",
        "grad_hero": "linear-gradient(135deg, #0C4A6E 0%, #0369A1 55%, #0284C7 100%)",
        "sombra_hero": "rgba(12, 74, 110, 0.25)",
        "sla_default": Config.SLA_MIGRACAO,
    },
    "PME": {
        "icone": "🏢",
        "subtitulo": "Análise estratégica dedicada às Pequenas e Médias Empresas",
        "cor_primaria": "#7C3AED",
        "cor_secundaria": "#4C1D95",
        "grad_hero": "linear-gradient(135deg, #4C1D95 0%, #7C3AED 55%, #A855F7 100%)",
        "sombra_hero": "rgba(76, 29, 149, 0.25)",
        "sla_default": Config.SLA_PME,
    },
}


# =====================================================================
# COMPONENTES VISUAIS AUXILIARES
# =====================================================================
def _injetar_css_dinamico(segmento: str) -> None:
    conf = SEGMENTOS_CONFIG[segmento]
    st.markdown(
        f"""
<style>
div[data-testid="stElementContainer"]:has(.topo-fixo-dinamico) {{
    position: sticky !important; top: 0.75rem !important; z-index: 1000 !important;
}}
.topo-fixo-dinamico {{
    background: rgba(248,250,252,0.96); backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px); padding: 0.5rem 0; border-radius: 16px;
}}
.hero-dinamico {{
    background: {conf["grad_hero"]}; padding: 32px 40px; border-radius: 16px;
    color: white; box-shadow: 0 10px 40px {conf["sombra_hero"]};
    margin-bottom: 12px; position: relative; overflow: hidden;
}}
.hero-dinamico::before {{
    content: ""; position: absolute; top: -55%; right: -8%;
    width: 390px; height: 390px; background: rgba(255,255,255,0.07);
    border-radius: 50%; pointer-events: none;
}}
.hero-dinamico h1 {{
    position: relative; z-index: 2; color: white !important;
    font-family: "Manrope", sans-serif !important;
    font-size: 34px; font-weight: 800; margin: 0; letter-spacing: -0.5px;
    text-shadow: 0 2px 4px rgba(0,0,0,0.28);
}}
.hero-dinamico p {{
    position: relative; z-index: 2; color: rgba(255,255,255,0.92) !important;
    font-family: "Inter", sans-serif !important; font-size: 15px;
    margin: 8px 0 0; font-weight: 400;
}}
.resultado-base {{
    margin-bottom: 0 !important;
    background: linear-gradient(135deg, #0F172A 0%, #1E3A5F 100%);
    padding: 1rem 1.5rem; border-radius: 0.75rem; display: flex;
    align-items: center; flex-wrap: wrap; gap: 0.6rem;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}}
.resultado-base-label {{
    color: #94A3B8; font-size: 0.8rem; font-weight: 700;
    text-transform: uppercase; letter-spacing: 0.08em;
}}
.resultado-base-regiao {{
    padding: 0.3rem 0.9rem; border-radius: 999px;
    font-size: 0.82rem; font-weight: 700; border: 2px solid;
}}
.resultado-base-count {{
    color: #64748B; font-size: 0.72rem; margin-left: auto; font-weight: 600;
}}
</style>""",
        unsafe_allow_html=True,
    )


def _html_resultado_base(regioes: List[str], total: int) -> str:
    cores_regiao = {
        "LESTE": {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
        "GRU": {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
        "ABCDM": {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
        "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
    }
    badges = ""
    for regiao in sorted(regioes):
        r = str(regiao).strip().upper()
        if not r or r in {"NAN", "NONE"}:
            continue
        cor = cores_regiao.get(r, cores_regiao["OUTRAS"])
        badges += (
            f'<span class="resultado-base-regiao" '
            f'style="background:{cor["bg"]};color:{cor["text"]};'
            f'border-color:{cor["border"]};">{r}</span>'
        )
    if not badges:
        cor = cores_regiao["OUTRAS"]
        badges = (
            f'<span class="resultado-base-regiao" '
            f'style="background:{cor["bg"]};color:{cor["text"]};'
            f'border-color:{cor["border"]};">OUTRAS</span>'
        )
    return (
        f'<div class="resultado-base">'
        f'<span class="resultado-base-label">📋 Resultado da Base:</span>'
        f"{badges}"
        f'<span class="resultado-base-count">{total:,} registros</span>'
        f"</div>"
    ).replace(",", ".")


def _render_topo_fixo(segmento: str, regioes: List[str], total: int) -> None:
    conf = SEGMENTOS_CONFIG[segmento]
    st.markdown(
        f"""
<div class="topo-fixo-dinamico">
    <div class="hero-dinamico">
        <h1>{conf["icone"]} {segmento} — Quebra de Agenda</h1>
        <p>{conf["subtitulo"]}</p>
    </div>
    {_html_resultado_base(regioes, total)}
</div>""",
        unsafe_allow_html=True,
    )


def _render_card_status(
    segmento: str,
    realizados: Dict[str, Any],
    sla_meta: float,
) -> None:
    conf = SEGMENTOS_CONFIG[segmento]
    quebra_atual = float(realizados["quebra_atual"])
    dentro_sla = quebra_atual <= sla_meta

    if dentro_sla:
        status_label = "DENTRO DO SLA"
        status_icone = "✓"
        cor_status = "#059669"
        cor_bg = "#D1FAE5"
        cor_txt = "#065F46"
        mensagem = (
            f"{segmento} com folga de "
            f"<strong>{sla_meta - quebra_atual:.2%}</strong> em relação à meta."
        )
        icone_mensagem = "✅"
    else:
        status_label = "FORA DO SLA"
        status_icone = "!"
        cor_status = "#DC2626"
        cor_bg = "#FEE2E2"
        cor_txt = "#991B1B"
        mensagem = (
            f"{segmento} acima da meta em "
            f"<strong>{quebra_atual - sla_meta:.2%}</strong>. "
            "Ação corretiva imediata necessária."
        )
        icone_mensagem = "🚨"

    html = f"""
<div style="background:white;border:1px solid #E5E7EB;border-radius:14px;
            padding:20px 24px;box-shadow:0 2px 8px rgba(0,0,0,0.04);
            margin:16px 0 24px 0;border-top:3px solid {conf['cor_primaria']};">
    <div style="display:flex;align-items:center;justify-content:space-between;
                flex-wrap:wrap;gap:16px;">
        <div style="display:flex;align-items:center;gap:14px;">
            <div style="width:44px;height:44px;background:{conf['grad_hero']};
                        border-radius:10px;display:flex;align-items:center;
                        justify-content:center;
                        box-shadow:0 4px 12px {conf['sombra_hero']};">
                <span style="font-size:22px;">{conf['icone']}</span>
            </div>
            <div>
                <div style="font-family:'Manrope',sans-serif;font-size:18px;
                            font-weight:800;color:#1F2937;">{segmento}</div>
                <div style="font-family:'Inter',sans-serif;font-size:12px;
                            color:#6B7280;font-weight:500;">Análise de Quebra Real</div>
            </div>
        </div>
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
            <div style="display:inline-flex;align-items:center;gap:6px;
                        padding:6px 14px;background:{cor_bg};
                        border-radius:999px;border:1px solid {cor_status};">
                <span style="display:inline-flex;align-items:center;
                             justify-content:center;width:18px;height:18px;
                             background:{cor_status};color:white;border-radius:50%;
                             font-size:11px;font-weight:800;">{status_icone}</span>
                <span style="font-family:'Inter',sans-serif;font-size:11px;
                             font-weight:700;color:{cor_txt};
                             text-transform:uppercase;">{status_label}</span>
            </div>
            <div style="display:inline-flex;flex-direction:column;padding:6px 14px;
                        background:#F0F9FF;border-radius:8px;border:1px solid #BAE6FD;">
                <span style="font-size:10px;color:#6B7280;font-weight:600;
                             text-transform:uppercase;">Quebra Atual</span>
                <span style="font-family:'Manrope',sans-serif;font-size:16px;
                             color:{cor_status};font-weight:800;">{quebra_atual:.2%}</span>
            </div>
            <div style="display:inline-flex;flex-direction:column;padding:6px 14px;
                        background:#F0F9FF;border-radius:8px;border:1px solid #BAE6FD;">
                <span style="font-size:10px;color:#6B7280;font-weight:600;
                             text-transform:uppercase;">Meta SLA</span>
                <span style="font-family:'Manrope',sans-serif;font-size:16px;
                             color:{conf['cor_secundaria']};
                             font-weight:800;">{sla_meta:.2%}</span>
            </div>
        </div>
    </div>
    <div style="display:flex;align-items:flex-start;gap:10px;padding:12px 14px;
                background:{cor_bg};border-left:3px solid {cor_status};
                border-radius:6px;margin-top:16px;">
        <span style="font-size:16px;line-height:1;flex-shrink:0;">{icone_mensagem}</span>
        <div style="font-family:'Inter',sans-serif;font-size:13px;color:{cor_txt};
                    line-height:1.55;font-weight:500;">{mensagem}</div>
    </div>
</div>"""
    st.markdown(html.replace(".", ","), unsafe_allow_html=True)


# =====================================================================
# RENDERIZADOR DE DATAFRAME ROBUSTO (SEM ERROS DE ARGUMENTO)
# =====================================================================
def render_dataframe_local(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "📊",
    badge: str = "",
    fmt: Optional[Dict[str, Any]] = None,
    color_col: Optional[str] = None,
    color_meta: Optional[float] = None,
    color_invertido: bool = False,
    height: int = 450,
) -> None:
    badge_text = badge or f"{len(df)} registros"
    st.markdown(
        f"""
        <div style="background:#FFFFFF;border-radius:10px 10px 0 0;padding:12px 16px;
                    border:1px solid #E2E8F0;border-bottom:none;display:flex;
                    align-items:center;justify-content:space-between;margin-top:10px;">
            <div style="font-weight:700;color:#0F172A;font-size:14px;display:flex;align-items:center;gap:8px;">
                <span>{icone}</span><span>{titulo}</span>
            </div>
            <span style="background:#F1F5F9;color:#475569;font-size:11px;font-weight:600;padding:2px 8px;border-radius:12px;">
                {badge_text}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_disp = df.copy()
    styler = df_disp.style

    if fmt:
        styler = styler.format(fmt)

    if color_col and color_col in df_disp.columns and color_meta is not None:
        def _cor(val: Any) -> str:
            try:
                v = float(val)
            except (ValueError, TypeError):
                return ""
            if color_invertido:
                if v > color_meta:
                    return "background-color:#FEE2E2;color:#991B1B;font-weight:700;"
                if v > color_meta * 0.85:
                    return "background-color:#FEF9C3;color:#854D0E;font-weight:600;"
                return "background-color:#DCFCE7;color:#166534;font-weight:600;"
            else:
                if v >= color_meta:
                    return "background-color:#DCFCE7;color:#166534;font-weight:700;"
                if v >= color_meta * 0.85:
                    return "background-color:#FEF9C3;color:#854D0E;font-weight:600;"
                return "background-color:#FEE2E2;color:#991B1B;font-weight:600;"

        styler = styler.map(_cor, subset=[color_col])

    styler = styler.set_table_styles([
        {"selector": "th", "props": [
            ("background-color", "#0F172A"),
            ("color", "#FFFFFF"),
            ("font-size", "11px"),
            ("font-weight", "700"),
            ("text-transform", "uppercase"),
            ("padding", "8px 10px"),
        ]},
        {"selector": "td", "props": [
            ("font-size", "12px"),
            ("padding", "8px 10px"),
            ("border-bottom", "1px solid #F1F5F9"),
        ]},
        {"selector": "tr:hover td", "props": [("background-color", "#F8FAFC")]},
    ])

    st.dataframe(styler, use_container_width=True, hide_index=True, height=height)


# =====================================================================
# PROCESSADORES DE DADOS LOCAIS
# =====================================================================
def calcular_metricas_realizadas(df_seg: pd.DataFrame) -> Dict[str, Any]:
    aloc = float(df_seg["TOTAL DE TAREFAS"].sum()) if not df_seg.empty else 0.0
    exe = float(df_seg.loc[df_seg["Status Contrato"] == "Executada", "TOTAL DE TAREFAS"].sum()) if not df_seg.empty else 0.0
    nex = float(df_seg.loc[df_seg["Status Contrato"] == "Não Executada", "TOTAL DE TAREFAS"].sum()) if not df_seg.empty else 0.0
    pen = max(0.0, aloc - exe - nex)
    considerado = exe + nex
    quebra_atual = (nex / considerado) if considerado > 0 else 0.0
    return {
        "alocado": aloc,
        "exec": exe,
        "naoexec": nex,
        "pend": pen,
        "quebra_atual": quebra_atual,
    }


def obter_ranking_tecnicos_realizados(df_seg: pd.DataFrame) -> pd.DataFrame:
    if df_seg.empty:
        return pd.DataFrame()
    
    df_work = df_seg.copy()
    
    df_work["_exec"] = np.where(df_work["Status Contrato"] == "Executada", df_work["TOTAL DE TAREFAS"], 0)
    df_work["_nao_exec"] = np.where(df_work["Status Contrato"] == "Não Executada", df_work["TOTAL DE TAREFAS"], 0)
    df_work["_pend"] = np.where(df_work["Status Contrato"] == "Pendente", df_work["TOTAL DE TAREFAS"], 0)
    
    df_tec = df_work.groupby("TÉCNICO").agg(
        Alocado=("TOTAL DE TAREFAS", "sum"),
        Executadas=("_exec", "sum"),
        Nao_Executadas=("_nao_exec", "sum"),
        Pendentes=("_pend", "sum"),
    ).reset_index()
    
    df_tec["Considerado"] = df_tec["Executadas"] + df_tec["Nao_Executadas"]
    df_tec["Quebra Atual"] = np.where(
        df_tec["Considerado"] > 0,
        df_tec["Nao_Executadas"] / df_tec["Considerado"],
        0.0
    )
    
    for col in ["Alocado", "Executadas", "Nao_Executadas", "Pendentes", "Considerado"]:
        df_tec[col] = pd.to_numeric(df_tec[col], errors="coerce").fillna(0).astype(int)
        
    return df_tec.sort_values("Nao_Executadas", ascending=False).reset_index(drop=True)


def _build_df_pendentes(df_seg: pd.DataFrame) -> pd.DataFrame:
    if df_seg.empty:
        return pd.DataFrame(columns=["Contrato", "Técnico", "Monitor"])

    mask = df_seg["Status Contrato"].str.upper().isin(["PENDENTE", "PENDING", "ABERTO", "EM ABERTO"])
    df_p = df_seg[mask].copy()
    
    if df_p.empty:
        return pd.DataFrame(columns=["Contrato", "Técnico", "Monitor"])

    df_out = pd.DataFrame()
    df_out["Contrato"] = df_p["CONTRATO"].fillna("Sem Contrato")
    df_out["Técnico"] = df_p["TÉCNICO"].fillna("NÃO MAPEADO")
    df_out["Monitor"] = df_p["MONITOR"].fillna("SEM MONITOR")
    
    return df_out.drop_duplicates().sort_values("Técnico").reset_index(drop=True)


# =====================================================================
# SUB-ABAS DE CONTEÚDO
# =====================================================================
def _sub_visao_geral(
    segmento: str,
    m_seg: Dict[str, Any],
    sla_meta: float,
) -> None:
    render_section(f"📊 Resumo Operacional — {segmento}")
    tema_q: TemaKPI = "vermelho" if m_seg["quebra_atual"] > sla_meta else "verde"
    c1, c2, c3, c4, c5 = st.columns(5)
    render_kpi(c1, "Alocado", f"{int(m_seg['alocado']):,}", tema="azul")
    render_kpi(c2, "Executadas", f"{int(m_seg['exec']):,}", tema="verde")
    render_kpi(c3, "Não Exec.", f"{int(m_seg['naoexec']):,}", tema="laranja")
    render_kpi(c4, "Pendentes", f"{int(m_seg['pend']):,}", tema="cinza")
    render_kpi(
        c5,
        "Quebra Atual",
        f"{m_seg['quebra_atual']:.2%}",
        sub=f"Meta: {sla_meta:.0%}",
        tema=tema_q,
    )


def _sub_causa_raiz(segmento: str, df_seg: pd.DataFrame) -> None:
    render_section(f"🔍 Causa Raiz — {segmento}")
    col_baixa = "_COL_BAIXA" if "_COL_BAIXA" in df_seg.columns else Utils.buscar_coluna(df_seg, ["MOTIVO DE BAIXA", "CÓD DE BAIXA 1", "COD DE BAIXA 1"])
    
    df_ne = df_seg[df_seg["Status Contrato"] == "Não Executada"].copy()
    if not df_ne.empty and col_baixa and col_baixa in df_ne.columns:
        df_c = df_ne.groupby(col_baixa)["TOTAL DE TAREFAS"].sum().reset_index()
        df_c.columns = ["Motivo de Baixa", "Volume"]
        df_c = df_c.sort_values("Volume", ascending=False).head(10).reset_index(drop=True)
        total_vol = df_c["Volume"].sum()
        df_c["% do Total"] = df_c["Volume"] / total_vol if total_vol > 0 else 0.0
        df_c["Acumulado"] = df_c["% do Total"].cumsum()
    else:
        df_c = pd.DataFrame()

    if df_c.empty:
        render_insight("Nenhum motivo de baixa registrado para as ordens não executadas deste segmento.", tipo="info")
        return

    render_dataframe_local(
        df_c,
        titulo=f"Pareto de Motivos de Baixa — {segmento}",
        icone="🔍",
        fmt={"% do Total": "{:.2%}", "Acumulado": "{:.2%}"},
        height=400,
    )

    if len(df_c) >= 2:
        t1, t2 = df_c.iloc[0], df_c.iloc[1]
        render_insight(
            f"Os 2 principais motivos (**{t1['Motivo de Baixa']}** e "
            f"**{t2['Motivo de Baixa']}**) respondem por "
            f"**{t2['Acumulado']:.1%}** das quebras identificadas no segmento.",
            tipo="acao",
        )


def _sub_tecnicos(
    segmento: str,
    df_seg: pd.DataFrame,
    sla_meta: float,
) -> None:
    render_section(f"👤 Técnicos com Maior Quebra — {segmento}")
    df_tec = obter_ranking_tecnicos_realizados(df_seg)
    
    if df_tec.empty:
        render_insight("Sem dados de técnicos para exibir.", tipo="info")
        return

    render_dataframe_local(
        df_tec,
        titulo=f"Ranking de Quebra por Técnico — {segmento}",
        icone="🚨",
        fmt={
            "Quebra Atual": "{:.2%}",
        },
        color_col="Quebra Atual",
        color_meta=sla_meta,
        color_invertido=True,
        height=450,
    )

    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df_tec.to_excel(w, index=False, sheet_name="Técnicos")

    st.download_button(
        label="📥 Exportar Ranking de Técnicos (Excel)",
        data=out.getvalue(),
        file_name=f"ranking_tecnicos_quebra_{segmento.lower()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_tec_xlsx_{segmento}",
        use_container_width=True,
    )


def _sub_pendentes(segmento: str, df_seg: pd.DataFrame) -> None:
    render_section(f"📋 Contratos Pendentes — {segmento}")
    df_pend = _build_df_pendentes(df_seg)
    total_pend = len(df_pend)

    m1, m2, m3 = st.columns(3)
    render_kpi(
        m1,
        "Total Pendentes",
        f"{total_pend:,}",
        sub="contratos sem execução",
        tema="laranja" if total_pend > 0 else "verde",
    )
    render_kpi(
        m2,
        "Técnicos Envolvidos",
        f"{df_pend['Técnico'].nunique():,}" if total_pend > 0 else "0",
        sub="com contrato pendente",
        tema="azul",
    )
    render_kpi(
        m3,
        "Monitores Envolvidos",
        f"{df_pend['Monitor'].nunique():,}" if total_pend > 0 else "0",
        sub="supervisionando pendências",
        tema="cinza",
    )

    st.markdown("")
    if df_pend.empty:
        render_insight("Excelente! Nenhum contrato pendente encontrado neste segmento.", tipo="ok")
        return

    with st.expander("🔎 Filtros Rápidos", expanded=False):
        fc1, fc2 = st.columns(2)
        with fc1:
            f_tec = st.selectbox(
                "Técnico",
                ["Todos"] + sorted(df_pend["Técnico"].dropna().unique().tolist()),
                key=f"pend_f_tec_{segmento}",
            )
        with fc2:
            f_mon = st.selectbox(
                "Monitor",
                ["Todos"] + sorted(df_pend["Monitor"].dropna().unique().tolist()),
                key=f"pend_f_mon_{segmento}",
            )

    df_view = df_pend.copy()
    if f_tec != "Todos":
        df_view = df_view[df_view["Técnico"] == f_tec]
    if f_mon != "Todos":
        df_view = df_view[df_view["Monitor"] == f_mon]

    st.markdown(f"**Exibindo {len(df_view):,} de {total_pend:,} contratos pendentes**")
    render_dataframe_local(
        df_view.reset_index(drop=True), titulo="Fila de Pendentes", icone="📋", height=450
    )

    out = BytesIO()
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        df_view.to_excel(w, index=False, sheet_name="Pendentes")

    st.markdown("")
    st.download_button(
        label="📥 Exportar Lista de Pendentes (Excel)",
        data=out.getvalue(),
        file_name=f"contratos_pendentes_{segmento.lower()}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key=f"dl_pend_xlsx_{segmento}",
        use_container_width=True,
    )


# =====================================================================
# PONTO DE ENTRADA PRINCIPAL
# =====================================================================
def main() -> None:
    if st.session_state.get("df_memoria") is None:
        render_insight(
            "Nenhuma base carregada. Volte ao **Dashboard Geral** e faça o upload.",
            tipo="alerta",
        )
        return

    df_full = st.session_state["df_memoria"].copy()

    # ── Status Contrato ────────────────────────────────────────────────
    if "Status Contrato" not in df_full.columns:
        col_s = Utils.buscar_coluna(df_full, ["STATUS DA O.S 1", "STATUS OS 1", "STATUS CONTRATO"])
        df_full["Status Contrato"] = (
            Utils.classificar_status(df_full[col_s]) if col_s else "Pendente"
        )

    # ── ✅ Classificação centralizada ─────────────────────────────────
    df_full, df_full["TIPO_SERVICO"] = classificar_tipo_servico(df_full)

    # ── Sidebar ────────────────────────────────────────────────────────
    with st.sidebar:
        st.markdown("### 🔍 Escolha a Carteira")
        segmento_selecionado = st.radio(
            "Segmento:",
            ["Migração", "PME"],
            index=0,
            horizontal=True,
        )
        st.divider()
        st.header(f"🎯 Filtros {segmento_selecionado}")

        monitores = ["Todos"] + sorted(
            str(x)
            for x in df_full["MONITOR"].dropna().unique()
            if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
        )
        sel_mon = st.selectbox(
            "👔 Monitor", monitores, key=f"mon_{segmento_selecionado}"
        )
        df_filt = (
            df_full if sel_mon == "Todos" else df_full[df_full["MONITOR"] == sel_mon]
        )

        tecnicos = ["Todos"] + sorted(
            str(x)
            for x in df_filt["TÉCNICO"].dropna().unique()
            if str(x) not in {"nan", "NÃO MAPEADO"}
        )
        sel_tec = st.selectbox(
            "👤 Técnico", tecnicos, key=f"tec_{segmento_selecionado}"
        )
        df = df_filt if sel_tec == "Todos" else df_filt[df_filt["TÉCNICO"] == sel_tec]

        st.divider()
        padrao_sla = float(SEGMENTOS_CONFIG[segmento_selecionado]["sla_default"] * 100)
        sla_meta = (
            st.number_input(
                "Meta SLA (%)",
                0.0,
                100.0,
                padrao_sla,
                0.5,
                key=f"sla_v_{segmento_selecionado}",
            )
            / 100.0
        )

        st.divider()
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("🔄 Reiniciar", use_container_width=True):
                st.session_state["df_memoria"] = None
                st.rerun()
        with col_r2:
            if st.button("🗑️ Limpar Cache", use_container_width=True):
                st.cache_data.clear()
                st.session_state["df_memoria"] = None
                st.rerun()

        st.divider()
        render_debug_criterios(df_full, expanded=False)

    if df.empty:
        render_insight("Nenhum dado encontrado para os filtros selecionados.", tipo="alerta")
        return

    # ── CSS dinâmico ───────────────────────────────────────────────────
    _injetar_css_dinamico(segmento_selecionado)

    regioes = (
        [
            str(r).strip().upper()
            for r in df[Config.COL_REGIAO].dropna().unique()
            if str(r).strip()
        ]
        if Config.COL_REGIAO in df.columns
        else ["OUTRAS"]
    )
    _render_topo_fixo(segmento_selecionado, regioes, len(df))

    # ── Filtra pelo segmento selecionado ──────────────────────────────
    df_seg = df[df["TIPO_SERVICO"] == segmento_selecionado].copy()
    if df_seg.empty:
        render_insight(
            f"Nenhum registro classificado como **{segmento_selecionado}** "
            "nos filtros atuais.  \n"
            "Verifique o painel auxiliar de auditoria na sidebar.",
            tipo="info",
        )
        return

    m_seg = calcular_metricas_realizadas(df_seg)
    _render_card_status(segmento_selecionado, m_seg, sla_meta)
    st.markdown("")

    # ── Sub-abas de Diagnóstico Operacional Real ───────────────────────────
    sub1, sub2, sub3, sub4 = st.tabs(
        [
            "📊 Visão Geral",
            "🔍 Causa Raiz",
            "👤 Técnicos",
            "📋 Pendentes",
        ]
    )
    with sub1:
        _sub_visao_geral(
            segmento_selecionado,
            m_seg,
            sla_meta,
        )
    with sub2:
        _sub_causa_raiz(segmento_selecionado, df_seg)
    with sub3:
        _sub_tecnicos(
            segmento_selecionado,
            df_seg,
            sla_meta,
        )
    with sub4:
        _sub_pendentes(segmento_selecionado, df_seg)


if __name__ == "__main__":
    main()