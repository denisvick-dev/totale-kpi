"""
componentes.py
==============
Módulo central de estilos, fontes e componentes reutilizáveis
para todo o projeto Streamlit.

Uso em qualquer página:
    from componentes import aplicar_estilo, render_kpi, render_insight
    aplicar_estilo()

Características:
- Fonte corporativa global (Inter + Manrope)
- Preservação de ícones Material Icons do Streamlit (com @font-face forçado)
- Tema Plotly global corporativo
- Componentes reutilizáveis (KPIs, insights, seções)
"""

from __future__ import annotations

from typing import Any

import streamlit as st
import streamlit.components.v1 as components
import plotly.io as pio
import plotly.graph_objects as go


# ====================================================
# CONSTANTES GLOBAIS — TIPOGRAFIA
# ====================================================
FONTE_TITULO = "'Manrope', 'Segoe UI', Arial, sans-serif"
FONTE_TEXTO  = "'Inter', 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
FONTE_CODIGO = "'JetBrains Mono', Consolas, 'Courier New', monospace"


# ====================================================
# PALETA CORPORATIVA
# ====================================================
COR_PRIMARIA   = "#012869"      # Azul institucional
COR_SECUNDARIA = "#F37C04"      # Laranja
COR_SUCESSO    = "#059669"      # Verde
COR_ALERTA     = "#DC2626"      # Vermelho
COR_NEUTRO     = "#64748B"      # Cinza slate
COR_TEXTO      = "#1F2937"      # Chumbo
COR_TEXTO_2    = "#374151"      # Cinza escuro
COR_TEXTO_3    = "#6B7280"      # Cinza médio
COR_BORDA      = "#E2E8F0"      # Prata claro
COR_FUNDO      = "#F8FAFC"      # Fundo claro


# ====================================================
# CONFIGURAÇÃO GLOBAL DO PLOTLY
# ====================================================
def _configurar_plotly_global() -> None:
    """Define template global do Plotly com fonte corporativa."""

    template = go.layout.Template(
        layout=go.Layout(
            font=dict(
                family=FONTE_TEXTO,
                size=13,
                color=COR_TEXTO,
            ),
            title=dict(
                font=dict(
                    family=FONTE_TITULO,
                    size=20,
                    color=COR_TEXTO,
                ),
                x=0.02,
                xanchor="left",
            ),
            legend=dict(
                font=dict(
                    family=FONTE_TEXTO,
                    size=12,
                    color=COR_TEXTO_2,
                ),
            ),
            xaxis=dict(
                tickfont=dict(family=FONTE_TEXTO, size=12, color=COR_TEXTO_2),
                title_font=dict(family=FONTE_TEXTO, size=13, color=COR_TEXTO_2),
                gridcolor="#F1F5F9",
                zerolinecolor="#CBD5E1",
            ),
            yaxis=dict(
                tickfont=dict(family=FONTE_TEXTO, size=12, color=COR_TEXTO_2),
                title_font=dict(family=FONTE_TEXTO, size=13, color=COR_TEXTO_2),
                gridcolor="#F1F5F9",
                zerolinecolor="#CBD5E1",
            ),
            hoverlabel=dict(
                font=dict(family=FONTE_TEXTO, size=13),
                bgcolor="white",
                bordercolor=COR_BORDA,
            ),
            paper_bgcolor="white",
            plot_bgcolor="white",
            colorway=[
                COR_PRIMARIA, COR_SECUNDARIA, COR_SUCESSO,
                COR_ALERTA, "#8B5CF6", "#EC4899",
                "#14B8A6", "#F59E0B", "#6366F1", COR_NEUTRO,
            ],
        )
    )

    pio.templates["corporativo"] = template
    pio.templates.default = "plotly_white+corporativo"


# ====================================================
# INJEÇÃO DE FONTES NO <HEAD> DO DOCUMENTO PAI
# ====================================================
def _injetar_fontes_no_head_pai() -> None:
    """
    Usa JavaScript para injetar as fontes DIRETAMENTE no <head>
    do documento pai (contorna restrições de iframe do Streamlit).

    Isso resolve o problema de "keyboard_double" aparecer como texto.
    """
    components.html(
        """
        <script>
            (function() {
                const linksParaInjetar = [
                    'https://fonts.googleapis.com/icon?family=Material+Icons',
                    'https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block',
                    'https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block',
                    'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap',
                    'https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800;900&display=swap',
                    'https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&display=swap'
                ];

                try {
                    const parentDoc = window.parent.document;
                    const parentHead = parentDoc.head;

                    // Preconnect para acelerar
                    const preconnects = [
                        'https://fonts.googleapis.com',
                        'https://fonts.gstatic.com'
                    ];
                    preconnects.forEach(href => {
                        if (!parentHead.querySelector(`link[href="${href}"]`)) {
                            const link = parentDoc.createElement('link');
                            link.rel = 'preconnect';
                            link.href = href;
                            if (href.includes('gstatic')) link.crossOrigin = 'anonymous';
                            parentHead.appendChild(link);
                        }
                    });

                    // Injeta cada link de fonte
                    linksParaInjetar.forEach(href => {
                        const existentes = Array.from(
                            parentHead.querySelectorAll('link[rel="stylesheet"]')
                        );
                        const jaExiste = existentes.some(l => l.href === href);

                        if (!jaExiste) {
                            const link = parentDoc.createElement('link');
                            link.rel = 'stylesheet';
                            link.href = href;
                            parentHead.appendChild(link);
                        }
                    });
                } catch (e) {
                    console.warn('Falha ao injetar fontes no head pai:', e);
                }
            })();
        </script>
        """,
        height=0,
    )


# ====================================================
# CSS GLOBAL — FONTES + ÍCONES + COMPONENTES
# ====================================================
def _injetar_css_global() -> None:
    """
    Injeta CSS global:
    - @font-face para Material Icons (fallback caso <link> falhe)
    - Fonte corporativa em toda interface
    - Preserva Material Icons do Streamlit
    - Estiliza componentes customizados (hero, KPI, seções)
    """

    st.markdown(
        """
        <!-- Preconnect e links de fonte diretos -->
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link rel="stylesheet"
              href="https://fonts.googleapis.com/icon?family=Material+Icons">
        <link rel="stylesheet"
              href="https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block">
        <link rel="stylesheet"
              href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=block">

        <style>
        /* ═══════════════════════════════════════════════════════
           IMPORT DE FONTES DE TEXTO
           ═══════════════════════════════════════════════════════ */
        @import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Manrope:wght@400;600;700;800;900&family=JetBrains+Mono:wght@400;500&display=swap");

        /* ═══════════════════════════════════════════════════════
           🔒 @FONT-FACE FORÇADO — MATERIAL ICONS
           (garantia extra caso os <link> falhem)
           ═══════════════════════════════════════════════════════ */
        @font-face {
            font-family: 'Material Icons';
            font-style: normal;
            font-weight: 400;
            font-display: block;
            src: url(https://fonts.gstatic.com/s/materialicons/v143/flUhRq6tzZclQEJ-Vdg-IuiaDsNc.woff2) format('woff2');
        }

        @font-face {
            font-family: 'Material Symbols Rounded';
            font-style: normal;
            font-weight: 400;
            font-display: block;
            src: url(https://fonts.gstatic.com/s/materialsymbolsrounded/v206/syl0-zNym6YjUruM-QrEh7-nyTnjDwKNJ_190Fjzag.woff2) format('woff2');
        }

        @font-face {
            font-family: 'Material Symbols Outlined';
            font-style: normal;
            font-weight: 400;
            font-display: block;
            src: url(https://fonts.gstatic.com/s/materialsymbolsoutlined/v206/kJEhBvYX7BgnkSrUwT8OhrdQw4oELdPIeeII9v6oDMzByHX9rA6RzaxHMPdY43zj-jCxv3fzvRNU22ZXGJpEpjC_1v-p_4MrImHCIJIZrDCvHOej.woff2) format('woff2');
        }

        /* ═══════════════════════════════════════════════════════
           VARIÁVEIS GLOBAIS
           ═══════════════════════════════════════════════════════ */
        :root {
            --font-titulo: "Manrope", "Segoe UI", Arial, sans-serif;
            --font-texto:  "Inter", "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            --font-codigo: "JetBrains Mono", Consolas, "Courier New", monospace;

            --cor-primaria:   #012869;
            --cor-secundaria: #F37C04;
            --cor-sucesso:    #059669;
            --cor-alerta:     #DC2626;
            --cor-neutro:     #64748B;
            --cor-texto:      #1F2937;
            --cor-texto-2:    #374151;
            --cor-texto-3:    #6B7280;
            --cor-borda:      #E2E8F0;
            --cor-fundo:      #F8FAFC;
        }

        /* ═══════════════════════════════════════════════════════
           APLICAÇÃO GLOBAL DA FONTE
           ═══════════════════════════════════════════════════════ */
        html,
        body,
        .stApp,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        [data-testid="stHeader"],
        [data-testid="stSidebar"],
        [data-testid="stToolbar"],
        section[data-testid="stSidebar"] {
            font-family: var(--font-texto) !important;
        }

        /* ─── TEXTOS GERAIS ────────────────────────────────── */
        p, label, div, li, a,
        button, input, select, textarea {
            font-family: var(--font-texto) !important;
        }

        /* ─── SPAN — CUIDADO com ícones! ───────────────────── */
        /* Aplica Inter apenas em spans que NÃO sejam ícones */
        span:not([class*="material"]):not([class*="Icon"]):not([class*="icon"]):not([data-testid*="Icon"]):not([data-testid*="icon"]) {
            font-family: var(--font-texto) !important;
        }

        /* ─── TÍTULOS ──────────────────────────────────────── */
        h1, h2, h3, h4, h5, h6,
        .hero-title,
        .section-title,
        .kpi-value {
            font-family: var(--font-titulo) !important;
            font-weight: 700;
            letter-spacing: -0.3px;
        }

        h1, .hero-title {
            font-weight: 800;
            letter-spacing: -0.6px;
        }

        /* ═══════════════════════════════════════════════════════
           WIDGETS DO STREAMLIT
           ═══════════════════════════════════════════════════════ */
        [data-testid="stWidgetLabel"],
        [data-testid="stMarkdownContainer"],
        [data-testid="stCaptionContainer"],
        [data-testid="stAlert"],
        [data-testid="stExpander"],
        [data-testid="stTabs"],
        [data-testid="stMetric"],
        [data-testid="stMetricLabel"],
        [data-testid="stMetricDelta"],
        [data-testid="stSelectbox"],
        [data-testid="stMultiSelect"],
        [data-testid="stTextInput"],
        [data-testid="stTextArea"],
        [data-testid="stNumberInput"],
        [data-testid="stDateInput"],
        [data-testid="stFileUploader"],
        [data-testid="stRadio"],
        [data-testid="stCheckbox"],
        [data-testid="stSlider"],
        [data-baseweb="select"],
        [data-baseweb="input"],
        [data-baseweb="textarea"],
        [data-baseweb="tab"],
        [data-baseweb="popover"] {
            font-family: var(--font-texto) !important;
        }

        /* ─── VALOR DAS MÉTRICAS ───────────────────────────── */
        [data-testid="stMetricValue"] {
            font-family: var(--font-titulo) !important;
            font-weight: 700;
            font-variant-numeric: tabular-nums;
        }

        /* ═══════════════════════════════════════════════════════
           BOTÕES
           ═══════════════════════════════════════════════════════ */
        .stButton button,
        .stDownloadButton button,
        .stFormSubmitButton button,
        button[kind] {
            font-family: var(--font-texto) !important;
            font-weight: 600;
            letter-spacing: 0.2px;
        }

        /* ═══════════════════════════════════════════════════════
           TABELAS
           ═══════════════════════════════════════════════════════ */
        .stDataFrame,
        .stTable,
        [data-testid="stDataFrame"],
        [data-testid="stTable"],
        table, thead, tbody, tr, th, td {
            font-family: var(--font-texto) !important;
        }

        th {
            font-weight: 700;
            letter-spacing: 0.4px;
        }

        td {
            font-variant-numeric: tabular-nums;
        }

        /* ═══════════════════════════════════════════════════════
           TABS
           ═══════════════════════════════════════════════════════ */
        button[data-baseweb="tab"] {
            font-family: var(--font-texto) !important;
            font-weight: 600;
            letter-spacing: 0.2px;
        }

        /* ═══════════════════════════════════════════════════════
           CÓDIGO / MONOESPAÇADO
           ═══════════════════════════════════════════════════════ */
        code, pre, kbd, samp,
        [data-testid="stCode"],
        [data-testid="stCodeBlock"] {
            font-family: var(--font-codigo) !important;
        }

        /* ═══════════════════════════════════════════════════════
           TOOLTIPS
           ═══════════════════════════════════════════════════════ */
        [role="tooltip"],
        [data-baseweb="tooltip"] {
            font-family: var(--font-texto) !important;
        }

        /* ═══════════════════════════════════════════════════════
           COMPONENTES CUSTOMIZADOS
           ═══════════════════════════════════════════════════════ */

        /* ─── HERO CORPORATIVO ────────── */
        .hero-corp {
            background: linear-gradient(90deg,
                #1E293B 0%,
                #334155 25%,
                #64748B 55%,
                #94A3B8 75%,
                #CBD5E1 92%,
                #94A3B8 100%
            );
            padding: 32px 48px;
            border-radius: 12px;
            color: white;
            box-shadow:
                0 8px 32px rgba(15, 23, 42, 0.35),
                inset 0 1px 0 rgba(255, 255, 255, 0.20);
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
            border: 1px solid rgba(203, 213, 225, 0.25);
            min-height: 110px;
        }
        .hero-corp::before {
            content: '';
            position: absolute;
            top: 50%;
            right: -80px;
            transform: translateY(-50%);
            width: 380px;
            height: 380px;
            background: radial-gradient(
                circle at center,
                rgba(226, 232, 240, 0.35) 0%,
                rgba(203, 213, 225, 0.20) 30%,
                rgba(148, 163, 184, 0.08) 55%,
                transparent 75%
            );
            border-radius: 50%;
            pointer-events: none;
            filter: blur(2px);
        }
        .hero-corp::after {
            content: '';
            position: absolute;
            top: 0;
            left: 40%;
            width: 30%;
            height: 100%;
            background: linear-gradient(
                90deg,
                transparent 0%,
                rgba(255, 255, 255, 0.06) 40%,
                rgba(255, 255, 255, 0.12) 50%,
                rgba(255, 255, 255, 0.06) 60%,
                transparent 100%
            );
            transform: skewX(-15deg);
            pointer-events: none;
        }
        .hero-title {
            font-size: 36px;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.8px;
            font-family: var(--font-titulo) !important;
            color: #FFFFFF;
            text-shadow:
                0 2px 4px rgba(0, 0, 0, 0.5),
                0 1px 2px rgba(0, 0, 0, 0.3),
                0 0 24px rgba(255, 255, 255, 0.12);
            position: relative;
            z-index: 2;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .hero-subtitle {
            font-size: 14px;
            opacity: 0.90;
            margin: 8px 0 0 0;
            font-weight: 400;
            color: #F1F5F9;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.4);
            position: relative;
            z-index: 2;
            letter-spacing: 0.3px;
        }
        .hero-badge {
            display: inline-block;
            background: linear-gradient(135deg,
                rgba(255, 255, 255, 0.22) 0%,
                rgba(255, 255, 255, 0.10) 100%
            );
            padding: 5px 16px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 12px;
            letter-spacing: 0.6px;
            text-transform: uppercase;
            color: #FFFFFF;
            border: 1px solid rgba(255, 255, 255, 0.25);
            backdrop-filter: blur(10px);
            box-shadow:
                0 2px 8px rgba(0, 0, 0, 0.2),
                inset 0 1px 0 rgba(255, 255, 255, 0.2);
            position: relative;
            z-index: 2;
        }

        /* ─── KPI CARDS ─────────────────────────────────────── */
        .kpi-card {
            background: linear-gradient(180deg, #FFFFFF 0%, #F9FAFB 100%);
            border-radius: 12px;
            padding: 20px 24px;
            box-shadow:
                0 2px 8px rgba(31, 41, 55, 0.08),
                0 1px 2px rgba(31, 41, 55, 0.04);
            border-left: 4px solid var(--cor-primaria);
            border-top: 1px solid #F3F4F6;
            transition: all 0.25s ease;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
            box-shadow:
                0 10px 25px rgba(31, 41, 55, 0.12),
                0 4px 10px rgba(31, 41, 55, 0.06);
        }
        .kpi-label {
            font-family: var(--font-texto) !important;
            font-size: 11px;
            font-weight: 700;
            color: var(--cor-texto-3);
            text-transform: uppercase;
            letter-spacing: 1.2px;
            margin-bottom: 6px;
        }
        .kpi-value {
            font-family: var(--font-titulo) !important;
            font-size: 28px;
            font-weight: 800;
            color: var(--cor-texto);
            line-height: 1;
            font-variant-numeric: tabular-nums;
        }
        .kpi-sub {
            font-family: var(--font-texto) !important;
            font-size: 12px;
            color: var(--cor-texto-3);
            margin-top: 6px;
            font-weight: 500;
        }

        /* ─── SEÇÕES ────────────────────────────────────────── */
        .section-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin: 32px 0 16px 0;
            padding-bottom: 12px;
            border-bottom: 2px solid var(--cor-borda);
        }
        .section-title {
            font-family: var(--font-titulo) !important;
            font-size: 20px;
            font-weight: 700;
            color: var(--cor-primaria);
            margin: 0;
            letter-spacing: -0.3px;
        }
        .section-badge {
            background: linear-gradient(135deg, #F3F4F6 0%, #E5E7EB 100%);
            color: var(--cor-texto-2);
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border: 1px solid #D1D5DB;
        }

        /* ─── INFO CAPTIONS ─────────────────────────────────── */
        .info-caption {
            background: linear-gradient(135deg, #F9FAFB 0%, #F3F4F6 100%);
            border-left: 3px solid var(--cor-neutro);
            padding: 12px 16px;
            border-radius: 4px;
            font-size: 13px;
            color: var(--cor-texto-2);
            margin: 12px 0;
            line-height: 1.6;
        }

        /* ─── FORMULA BOX ───────────────────────────────────── */
        .formula-box {
            background: linear-gradient(135deg, #F3F4F6 0%, #E5E7EB 100%);
            border: 1px solid #D1D5DB;
            border-left: 4px solid var(--cor-neutro);
            border-radius: 8px;
            padding: 14px 20px;
            margin: 12px 0;
            font-size: 14px;
            color: var(--cor-texto);
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .formula-box b {
            color: var(--cor-primaria);
        }

        /* ─── TABLE WRAPPER ─────────────────────────────────── */
        .table-wrapper {
            background: white;
            border-radius: 12px;
            padding: 4px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            overflow-x: auto;
        }

        /* ═══════════════════════════════════════════════════════
           SCROLLBAR CUSTOMIZADA
           ═══════════════════════════════════════════════════════ */
        ::-webkit-scrollbar {
            width: 10px;
            height: 10px;
        }
        ::-webkit-scrollbar-track {
            background: #F1F5F9;
        }
        ::-webkit-scrollbar-thumb {
            background: #CBD5E1;
            border-radius: 5px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #94A3B8;
        }

        /* ═══════════════════════════════════════════════════════
           LAYOUT GERAL
           ═══════════════════════════════════════════════════════ */
        .main .block-container {
            padding-top: 1rem;
            max-width: 1400px;
        }

        /* ═══════════════════════════════════════════════════════
           🔒 OVERRIDE FINAL — MATERIAL ICONS (MÁXIMA PRIORIDADE)
           ⚠️ ESTE BLOCO DEVE FICAR POR ÚLTIMO — NÃO MOVER!
           ═══════════════════════════════════════════════════════ */
        [data-testid="stIconMaterial"],
        [data-testid="stExpanderToggleIcon"],
        [data-testid="stSidebarNavIcon"],
        [data-testid="stSidebarCollapseButton"] span,
        [data-testid="stToolbar"] span,
        [data-testid="collapsedControl"] span,
        [data-testid="stHeaderActionElements"] span,
        [data-testid="stExpander"] summary span,
        [data-testid*="Icon"],
        [data-testid*="icon"],
        .material-icons,
        .material-icons-outlined,
        .material-icons-round,
        .material-icons-sharp,
        .material-icons-two-tone,
        .material-symbols-outlined,
        .material-symbols-rounded,
        .material-symbols-sharp,
        span[class*="material"],
        span[class*="Material"],
        i.material-icons,
        i.material-symbols-rounded {
            font-family: "Material Symbols Rounded",
                         "Material Symbols Outlined",
                         "Material Icons",
                         "Material Icons Outlined" !important;
            font-weight: normal !important;
            font-style: normal !important;
            font-size: 14px;
            line-height: 1 !important;
            letter-spacing: normal !important;
            text-transform: none !important;
            white-space: nowrap !important;
            word-wrap: normal !important;
            direction: ltr !important;
            font-feature-settings: "liga" !important;
            -moz-font-feature-settings: "liga" !important;
            -webkit-font-feature-settings: "liga" !important;
            -webkit-font-smoothing: antialiased !important;
            text-rendering: optimizeLegibility !important;
            font-variation-settings:
                'FILL' 0,
                'wght' 400,
                'GRAD' 0,
                'opsz' 24 !important;
        }

        /* SVG nunca herda font-family de texto */
        svg,
        svg *,
        [data-testid] svg,
        button svg,
        [role="button"] svg {
            font-family: inherit !important;
        }

        /* Ícones DENTRO de botões (setas expand/collapse) */
        .stButton button [class*="material"],
        .stDownloadButton button [class*="material"],
        button [class*="material"],
        button [class*="Material"],
        button [data-testid*="Icon"],
        [data-baseweb="icon"] {
            font-family: "Material Symbols Rounded",
                         "Material Icons" !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ====================================================
# FUNÇÃO PÚBLICA — CHAMAR EM TODAS AS PÁGINAS
# ====================================================
def aplicar_estilo() -> None:
    """
    Aplica fonte corporativa + tema Plotly + componentes globais.

    Uso em qualquer página:
        from componentes import aplicar_estilo
        aplicar_estilo()
    """
    _configurar_plotly_global()
    _injetar_fontes_no_head_pai()   # 🔒 Injeta fontes no head do doc pai
    _injetar_css_global()            # Aplica CSS com @font-face + estilos


# ====================================================
# COMPONENTES REUTILIZÁVEIS
# ====================================================
def render_section(titulo: str, divider: str | None = "gray") -> None:
    """Header de seção com estilo padronizado."""
    st.subheader(titulo, divider=divider)  # type: ignore


def render_section_header(icon: str, title: str, badge: str = "") -> None:
    """
    Header de seção customizado com ícone e badge opcional.

    Exemplo:
        render_section_header("📊", "Indicadores", "KPIs")
    """
    badge_html = (
        f'<span class="section-badge">{badge}</span>' if badge else ""
    )
    st.markdown(
        f"""
        <div class="section-header">
            <span style="font-size:24px;">{icon}</span>
            <h2 class="section-title">{title}</h2>
            {badge_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi(
    col,
    label: str,
    valor: str,
    sub: str = "",
    tema: str = "azul",
) -> None:
    """
    Renderiza card de KPI padronizado.

    Parâmetros
    ----------
    col : streamlit column
        Coluna onde o KPI será renderizado.
    label : str
        Rótulo do KPI (uppercase).
    valor : str
        Valor principal (já formatado).
    sub : str
        Texto complementar abaixo do valor.
    tema : str
        'azul' | 'verde' | 'vermelho' | 'laranja' | 'cinza'
    """
    cores = {
        "azul":     COR_PRIMARIA,
        "verde":    COR_SUCESSO,
        "vermelho": COR_ALERTA,
        "laranja":  COR_SECUNDARIA,
        "cinza":    COR_NEUTRO,
    }
    cor = cores.get(tema, COR_PRIMARIA)

    col.markdown(
        f"""
        <div class="kpi-card" style="border-left-color:{cor};">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value" style="color:{cor};">{valor}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_sm(
    container,
    label: str,
    valor: str,
    sub: str = "",
    tema: str = "azul",
) -> None:
    """
    Versão compacta do KPI para uso em containers menores.
    """
    cores = {
        "azul":     COR_PRIMARIA,
        "verde":    COR_SUCESSO,
        "vermelho": COR_ALERTA,
        "laranja":  COR_SECUNDARIA,
        "cinza":    COR_NEUTRO,
    }
    cor = cores.get(tema, COR_PRIMARIA)

    container.markdown(
        f"""
        <div style="background:white;border-radius:8px;padding:12px 16px;
             border-left:3px solid {cor};margin-bottom:8px;
             box-shadow:0 1px 4px rgba(0,0,0,0.06);">
            <div style="font-family:{FONTE_TEXTO};font-size:10px;
                 color:{COR_TEXTO_3};text-transform:uppercase;
                 letter-spacing:1px;font-weight:700;">{label}</div>
            <div style="font-family:{FONTE_TITULO};font-size:20px;
                 color:{cor};font-weight:800;line-height:1.2;
                 margin-top:4px;font-variant-numeric:tabular-nums;">{valor}</div>
            <div style="font-family:{FONTE_TEXTO};font-size:11px;
                 color:{COR_TEXTO_3};margin-top:2px;">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_insight(msg: str, tipo: str = "info") -> None:
    """
    Renderiza caixa de insight/alerta.

    tipo: 'ok' | 'info' | 'alerta' | 'critico' | 'acao'
    """
    config = {
        "ok":      ("#D1FAE5", "#065F46", "#059669", "✅"),
        "info":    ("#DBEAFE", "#1E40AF", "#3B82F6", "ℹ️"),
        "alerta":  ("#FEF3C7", "#92400E", "#F59E0B", "⚠️"),
        "critico": ("#FEE2E2", "#991B1B", "#DC2626", "🚨"),
        "acao":    ("#EDE9FE", "#5B21B6", "#8B5CF6", "🎯"),
    }
    bg, texto, borda, icone = config.get(tipo, config["info"])

    st.markdown(
        f"""
        <div style="background:{bg};color:{texto};
             border-left:4px solid {borda};
             padding:12px 16px;border-radius:6px;margin:10px 0;
             font-family:{FONTE_TEXTO};font-size:14px;line-height:1.6;">
            <span style="margin-right:8px;">{icone}</span>{msg}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero(
    titulo: str,
    subtitulo: str = "",
    badge: str = "",
) -> None:
    """
    Renderiza o hero corporativo (barra de título gradient prata metálico).

    Exemplo:
        render_hero(
            titulo="📊 Dashboard Principal",
            subtitulo="Análise consolidada de operações",
            badge="Atualizado hoje",
        )
    """
    subtitulo_html = (
        f'<p class="hero-subtitle">{subtitulo}</p>' if subtitulo else ""
    )
    badge_html = (
        f'<span class="hero-badge">{badge}</span>' if badge else ""
    )

    st.markdown(
        f"""
        <div class="hero-corp">
            <div style="position:relative;z-index:2;">
                <h1 class="hero-title">{titulo}</h1>
                {subtitulo_html}
                {badge_html}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_dataframe(
    df,
    titulo: str = "",
    icone: str = "📊",
    height: int = 400,
    fmt: dict | None = None,
    **kwargs: Any,
) -> None:
    """
    Wrapper padronizado para exibir DataFrames.
    """
    if titulo:
        st.markdown(
            f"**{icone} {titulo}**",
            unsafe_allow_html=True,
        )

    if fmt:
        try:
            styler = df.style
            for col, formato in fmt.items():
                if col in df.columns:
                    styler = styler.format(
                        {col: formato}  # type: ignore
                    )
            st.dataframe(styler, height=height, use_container_width=True, **kwargs)
        except Exception:
            st.dataframe(df, height=height, use_container_width=True, **kwargs)
    else:
        st.dataframe(df, height=height, use_container_width=True, **kwargs)