from __future__ import annotations

import sys
from pathlib import Path

# ── Adiciona pages/ ao sys.path (onde quebra.py está) ───────────────
_DIR = Path(__file__).resolve().parent   # .../projeto/pages/
if str(_DIR) not in sys.path:
    sys.path.insert(0, str(_DIR))

# ── Raiz do projeto (um nível acima de pages/) ───────────────────────
_ROOT = _DIR.parent                      # .../projeto/

from datetime import datetime
from html import escape
from io import BytesIO
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from quebra import (
    Config,
    Motor,
    Utils,
    aplicar_estilo,
    render_alerta_sla,
    render_dataframe,
    render_insight,
    render_kpi,
    render_kpi_sm,
    render_resultado_base,
    render_section,
    render_segmento_header,
)

# ====================================================
# CONFIGURAÇÃO DA PÁGINA
# ====================================================
st.set_page_config(
    page_title="PME — Quebra de Agenda",
    page_icon="🏢",
    layout="wide",
)

for k in ("df_memoria",):
    st.session_state.setdefault(k, None)

# ====================================================
# CONSTANTES
# ====================================================
TIPO = "PME"
SLA_DEFAULT = Config.SLA_PME

ACOES_PME: List[tuple] = [
    (
        "🟡 MÉDIA",
        "Verificar disponibilidade de técnicos habilitados em PME para "
        "redistribuição de carteira nas regiões críticas.",
        "acao",
    ),
    (
        "🟡 MÉDIA",
        "Acionar equipe comercial PME para comunicação proativa com "
        "clientes com agenda em risco de quebra.",
        "acao",
    ),
    (
        "🟢 BAIXA",
        "Revisar janelas de atendimento PME — clientes empresariais têm "
        "menor flexibilidade de horário. Ajustar agendamentos para períodos "
        "de maior disponibilidade.",
        "info",
    ),
]

FMT_QUEBRA: Dict[str, str] = {
    "Quebra Atual": "{:.2%}",
    "Fechamento Otimista": "{:.2%}",
    "Fechamento Base": "{:.2%}",
    "Fechamento Pessimista": "{:.2%}",
}


# ====================================================
# GERAÇÃO DE PDF EXECUTIVO PME
# ====================================================
class PDFExecutivoPME:
    """Relatório executivo em PDF dedicado ao segmento PME."""

    # ── Paleta de cores ─────────────────────────────────────────────
    COR_PRIMARIA:   str = "#4C1D95"
    COR_SECUNDARIA: str = "#7C3AED"
    COR_TEXTO:      str = "#1E1B4B"
    COR_SUBTEXTO:   str = "#6B7280"
    COR_OK:         str = "#059669"
    COR_ALERTA:     str = "#D97706"
    COR_CRITICO:    str = "#DC2626"
    COR_LINHA:      str = "#E5E7EB"
    COR_LINHA_ALT:  str = "#F9FAFB"

    # ── Dimensões (landscape A4) ─────────────────────────────────────
    LARGURA_UTIL: float = 27.7
    MARGEM_H:     float = 0.8
    MARGEM_TOP:   float = 0.8
    MARGEM_BOT:   float = 1.3

    # ── Caminho do logo (relativo ao próprio arquivo) ────────────────
    LOGO_PATH: Path = Path(__file__).resolve().parent.parent / "assets" / "images" / "novo-logo-totale.png"

    @classmethod
    def _fmt(cls, v: Any, col: str = "") -> str:
        """Formata valor para célula da tabela."""
        if pd.isna(v):
            return "—"
        col_u = str(col).upper()
        pct_keys = {"QUEBRA", "FECHAMENTO", "META", "PROBAB", "%", "ACUMULADO", "TOTAL"}
        if isinstance(v, (float, np.floating)):
            if any(k in col_u for k in pct_keys):
                return f"{v:.2%}"
            return (
                f"{int(v):,}".replace(",", ".")
                if float(v).is_integer()
                else f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            )
        if isinstance(v, (int, np.integer)):
            return f"{v:,}".replace(",", ".")
        return escape(str(v))

    @classmethod
    def _estilos(cls) -> Any:
        """Configura e retorna o stylesheet do PDF."""
        s = getSampleStyleSheet()

        s.add(
            ParagraphStyle(
                name="PME_Titulo",
                fontName="Helvetica-Bold",
                fontSize=24,
                leading=30,
                textColor=colors.white,
                alignment=TA_CENTER,
                spaceAfter=4,
            )
        )
        s.add(
            ParagraphStyle(
                name="PME_Subtitulo",
                fontName="Helvetica",
                fontSize=10,
                leading=14,
                textColor=colors.HexColor("#DDD6FE"),
                alignment=TA_CENTER,
                spaceAfter=0,
            )
        )
        s.add(
            ParagraphStyle(
                name="PME_Secao",
                fontName="Helvetica-Bold",
                fontSize=11,
                leading=15,
                textColor=colors.HexColor(cls.COR_PRIMARIA),
                spaceBefore=10,
                spaceAfter=4,
            )
        )
        s.add(
            ParagraphStyle(
                name="PME_Texto",
                fontName="Helvetica",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor(cls.COR_TEXTO),
                alignment=TA_LEFT,
                spaceAfter=3,
            )
        )
        s.add(
            ParagraphStyle(
                name="PME_Destaque",
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor(cls.COR_PRIMARIA),
                alignment=TA_LEFT,
                spaceAfter=2,
            )
        )
        s.add(
            ParagraphStyle(
                name="PME_Alerta",
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor(cls.COR_CRITICO),
                alignment=TA_LEFT,
                spaceAfter=2,
            )
        )
        s.add(
            ParagraphStyle(
                name="PME_OK",
                fontName="Helvetica-Bold",
                fontSize=8,
                leading=11,
                textColor=colors.HexColor(cls.COR_OK),
                alignment=TA_LEFT,
                spaceAfter=2,
            )
        )
        return s

    @classmethod
    def _tab(
        cls,
        df: pd.DataFrame,
        limite: Optional[int] = None,
        larguras: Optional[List[float]] = None,
        cor_col_quebra: Optional[str] = None,
        sla_meta: float = 0.20,
    ) -> Table:
        def _fazer_tabela_interna() -> Table:
            # ── DataFrame vazio ──────────────────────────────────────
            if df is None or df.empty:
                vazio: List[List[Any]] = [["Sem dados disponíveis"]]
                t = Table(vazio, colWidths=[cls.LARGURA_UTIL * cm])
                t.setStyle(
                    TableStyle(
                        [
                            (
                                "BACKGROUND",
                                (0, 0),
                                (-1, -1),
                                colors.HexColor(cls.COR_LINHA_ALT),
                            ),
                            (
                                "TEXTCOLOR",
                                (0, 0),
                                (-1, -1),
                                colors.HexColor(cls.COR_SUBTEXTO),
                            ),
                            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                            ("FONTSIZE", (0, 0), (-1, -1), 8),
                            (
                                "BOX",
                                (0, 0),
                                (-1, -1),
                                0.5,
                                colors.HexColor(cls.COR_LINHA),
                            ),
                            ("TOPPADDING", (0, 0), (-1, -1), 8),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                        ]
                    )
                )
                return t

            # ── Preparar base ────────────────────────────────────────
            base = df.head(limite) if limite else df.copy()

            st_h = ParagraphStyle(
                "th",
                fontName="Helvetica-Bold",
                fontSize=6.5,
                leading=8,
                textColor=colors.white,
                alignment=TA_CENTER,
            )
            st_c = ParagraphStyle(
                "tc",
                fontName="Helvetica",
                fontSize=6.5,
                leading=8.5,
                textColor=colors.HexColor(cls.COR_TEXTO),
                alignment=TA_CENTER,
            )
            st_c_left = ParagraphStyle(
                "tc_left",
                fontName="Helvetica",
                fontSize=6.5,
                leading=8.5,
                textColor=colors.HexColor(cls.COR_TEXTO),
                alignment=TA_LEFT,
            )

            # ── Dados ────────────────────────────────────────────────
            dados: List[List[Any]] = [[Paragraph(str(c), st_h) for c in base.columns]]
            for _, row in base.iterrows():
                linha: List[Any] = []
                for idx_c, c in enumerate(base.columns):
                    cell_st = st_c_left if idx_c == 0 else st_c
                    linha.append(Paragraph(cls._fmt(row[c], c), cell_st))
                dados.append(linha)

            # ── Larguras ─────────────────────────────────────────────
            if larguras:
                col_widths = [w * cm for w in larguras]
            else:
                col_widths = [w * cm for w in cls._calcular_larguras(base)]

            # Garante que a soma não ultrapasse LARGURA_UTIL
            soma = sum(col_widths)
            if soma > cls.LARGURA_UTIL * cm:
                fator = (cls.LARGURA_UTIL * cm) / soma
                col_widths = [w * fator for w in col_widths]

            tab = Table(dados, colWidths=col_widths, repeatRows=1)

            # ── Estilo ───────────────────────────────────────────────
            style: List[Any] = [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(cls.COR_PRIMARIA)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 6.5),
                (
                    "LINEBELOW",
                    (0, 0),
                    (-1, 0),
                    1.5,
                    colors.HexColor(cls.COR_SECUNDARIA),
                ),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 1), (-1, -1), 6.5),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("ALIGN", (0, 1), (0, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor(cls.COR_PRIMARIA)),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor(cls.COR_LINHA)),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]

            # Zebra
            for i in range(1, len(dados)):
                bg = colors.white if i % 2 == 1 else colors.HexColor(cls.COR_LINHA_ALT)
                style.append(("BACKGROUND", (0, i), (-1, i), bg))

            # Coloração condicional
            if cor_col_quebra and cor_col_quebra in base.columns:
                col_idx = list(base.columns).index(cor_col_quebra)
                for row_i, (_, row) in enumerate(base.iterrows(), start=1):
                    try:
                        val = float(row[cor_col_quebra])
                        if val > sla_meta:
                            bg_c = colors.HexColor("#FEE2E2")
                            txt_c = colors.HexColor(cls.COR_CRITICO)
                        elif val > sla_meta * 0.85:
                            bg_c = colors.HexColor("#FEF9C3")
                            txt_c = colors.HexColor(cls.COR_ALERTA)
                        else:
                            bg_c = colors.HexColor("#DCFCE7")
                            txt_c = colors.HexColor(cls.COR_OK)
                        style += [
                            ("BACKGROUND", (col_idx, row_i), (col_idx, row_i), bg_c),
                            ("TEXTCOLOR", (col_idx, row_i), (col_idx, row_i), txt_c),
                            (
                                "FONTNAME",
                                (col_idx, row_i),
                                (col_idx, row_i),
                                "Helvetica-Bold",
                            ),
                        ]
                    except (ValueError, TypeError):
                        pass

            tab.setStyle(TableStyle(style))
            return tab

        # ── Wrapper de centralização ─────────────────────────────────────
        # Envolve a tabela interna em uma tabela de largura total
        # com célula única centralizada — garante alinhamento real.
        tabela_interna = _fazer_tabela_interna()
        wrapper_data: List[List[Any]] = [[tabela_interna]]
        wrapper = Table(
            wrapper_data,
            colWidths=[cls.LARGURA_UTIL * cm],
            hAlign="CENTER",
        )
        wrapper.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        return wrapper
    
    @classmethod
    def _calcular_larguras(cls, df: pd.DataFrame) -> List[float]:
        """
        Calcula larguras proporcionais em cm pelo conteúdo real de cada coluna.
        A soma sempre resulta em LARGURA_UTIL cm.
        """
        if df.empty:
            return [cls.LARGURA_UTIL]

        pesos: List[float] = []
        for col in df.columns:
            # Comprimento do header
            max_len = len(str(col))
            # Comprimento máximo dos dados (amostra de 50 linhas)
            for val in df[col].head(50):
                max_len = max(max_len, len(cls._fmt(val, col)))
            # Mínimo de 5 e máximo de 30 caracteres de peso
            pesos.append(min(max(max_len, 5), 30))

        total = sum(pesos)
        return [(p / total) * cls.LARGURA_UTIL for p in pesos]

    @classmethod
    def _rodape(cls, canvas: Any, doc: Any) -> None:
        """Rodapé com logo, linha separadora, texto institucional e paginação."""
        canvas.saveState()

        page_w, _ = landscape(A4)
        x_esq   = cls.MARGEM_H * cm
        x_dir   = page_w - cls.MARGEM_H * cm
        y_linha = 1.05 * cm
        y_txt   = 0.52 * cm

        # ── Linha separadora ─────────────────────────────────────────
        canvas.setStrokeColor(colors.HexColor(cls.COR_LINHA))
        canvas.setLineWidth(0.5)
        canvas.line(x_esq, y_linha, x_dir, y_linha)

        # ── Logo à esquerda ──────────────────────────────────────────
        x_txt = x_esq   # posição do texto (ajustada se logo existir)
        if cls.LOGO_PATH.exists():
            try:
                logo_h = 0.50 * cm
                # Lê dimensões reais para calcular largura proporcional
                reader  = ImageReader(str(cls.LOGO_PATH))
                iw, ih  = reader.getSize()
                logo_w  = logo_h * (iw / ih) if ih > 0 else logo_h * 3.5

                canvas.drawImage(
                    str(cls.LOGO_PATH),
                    x_esq,
                    y_txt - 0.02 * cm,
                    width=logo_w,
                    height=logo_h,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                x_txt = x_esq + logo_w + 0.25 * cm
            except Exception:
                pass   # continua sem logo em caso de erro

        # ── Texto central ────────────────────────────────────────────
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor(cls.COR_SUBTEXTO))
        canvas.drawString(
            x_txt, y_txt,
            f"PME — Gestão de Quebra de Agenda  |  "
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Confidencial",
        )

        # ── Paginação à direita ───────────────────────────────────────
        canvas.drawRightString(x_dir, y_txt, f"Página {doc.page}")
        canvas.restoreState()

    @classmethod
    def _capa(
        cls,
        s: Any,
        m: dict,
        sla_meta: float,
        total_registros: int,
    ) -> List[Any]:
        """Monta a capa: logo centralizado + banner roxo + badge SLA + KPIs."""
        el: List[Any] = []

        # ── Logo centralizado no topo ────────────────────────────────
        if cls.LOGO_PATH.exists():
            try:
                reader  = ImageReader(str(cls.LOGO_PATH))
                iw, ih  = reader.getSize()
                logo_h  = 1.5 * cm
                logo_w  = logo_h * (iw / ih) if ih > 0 else logo_h * 3.5

                # Centraliza via tabela wrapper
                logo_img = RLImage(str(cls.LOGO_PATH), width=logo_w, height=logo_h)
                logo_wrapper_data: List[List[Any]] = [[logo_img]]
                logo_wrapper = Table(
                    logo_wrapper_data,
                    colWidths=[cls.LARGURA_UTIL * cm],
                    hAlign="CENTER",
                )
                logo_wrapper.setStyle(TableStyle([
                    ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING",   (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
                    ("TOPPADDING",    (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ]))
                el.append(logo_wrapper)
            except Exception:
                pass

        # ── Banner roxo ──────────────────────────────────────────────
        banner_data: List[List[Any]] = [
            [Paragraph("RELATÓRIO EXECUTIVO — PME", s["PME_Titulo"])],
            [Paragraph(
                f"Quebra de Agenda  •  "
                f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}  •  "
                f"{total_registros:,} registros analisados".replace(",", "."),
                s["PME_Subtitulo"],
            )],
        ]
        tab_banner = Table(
            banner_data,
            colWidths=[cls.LARGURA_UTIL * cm],
            hAlign="CENTER",
        )
        tab_banner.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor(cls.COR_PRIMARIA)),
            ("TOPPADDING",    (0, 0), (0, 0),   20),
            ("BOTTOMPADDING", (0, 0), (0, 0),   6),
            ("TOPPADDING",    (0, 1), (0, 1),   4),
            ("BOTTOMPADDING", (0, 1), (0, 1),   20),
            ("LEFTPADDING",   (0, 0), (-1, -1), 20),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 20),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("BOX",           (0, 0), (-1, -1), 3, colors.HexColor(cls.COR_SECUNDARIA)),
        ]))
        el.append(tab_banner)
        el.append(Spacer(1, 0.3 * cm))

        # ── Badge de status SLA ──────────────────────────────────────
        dentro_sla = m["quebra_atual"] <= sla_meta
        status_txt = "DENTRO DO SLA" if dentro_sla else "FORA DO SLA"
        icone      = "✅" if dentro_sla else "❌"
        cor_status = cls.COR_OK if dentro_sla else cls.COR_CRITICO

        st_status = ParagraphStyle(
            "st_status", fontName="Helvetica-Bold", fontSize=11,
            leading=15, textColor=colors.white, alignment=TA_CENTER,
        )
        badge_data: List[List[Any]] = [[Paragraph(f"{icone}  {status_txt}", st_status)]]
        tab_badge = Table(
            badge_data,
            colWidths=[cls.LARGURA_UTIL * cm],
            hAlign="CENTER",
        )
        tab_badge.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor(cor_status)),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("BOX",           (0, 0), (-1, -1), 1, colors.HexColor(cor_status)),
        ]))
        el.append(tab_badge)
        el.append(Spacer(1, 0.3 * cm))

        # ── Grade de KPIs 4 × 2 ─────────────────────────────────────
        kpis: List[tuple] = [
            ("Alocado",      cls._fmt(m["alocado"]),        cls.COR_PRIMARIA),
            ("Executadas",   cls._fmt(m["exec"]),           cls.COR_OK),
            ("Não Exec.",    cls._fmt(m["naoexec"]),        cls.COR_CRITICO),
            ("Pendentes",    cls._fmt(m["pend"]),           cls.COR_SUBTEXTO),
            ("Quebra Atual", f"{m['quebra_atual']:.2%}",
            cls.COR_CRITICO if m["quebra_atual"] > sla_meta else cls.COR_OK),
            ("Meta SLA",     f"{sla_meta:.2%}",             cls.COR_PRIMARIA),
            ("Proj. Base",   f"{m['fechamento_proj']:.2%}",
            cls.COR_CRITICO if m["fechamento_proj"] > sla_meta else cls.COR_OK),
            ("Status",       status_txt,                     cor_status),
        ]

        kpi_col_w = cls.LARGURA_UTIL / 4
        kpi_rows: List[List[Any]] = []

        for i in range(0, len(kpis), 4):
            chunk = kpis[i : i + 4]
            # Preenche com células vazias se chunk < 4
            while len(chunk) < 4:
                chunk.append(("", "", cls.COR_SUBTEXTO))

            linha_lbl: List[Any] = [
                Paragraph(k[0], ParagraphStyle(
                    f"kl_{i}_{j}", fontName="Helvetica", fontSize=7,
                    leading=9, textColor=colors.HexColor(cls.COR_SUBTEXTO),
                    alignment=TA_CENTER,
                ))
                for j, k in enumerate(chunk)
            ]
            linha_val: List[Any] = [
                Paragraph(k[1], ParagraphStyle(
                    f"kv_{i}_{j}", fontName="Helvetica-Bold", fontSize=17,
                    leading=21, textColor=colors.HexColor(k[2]),
                    alignment=TA_CENTER,
                ))
                for j, k in enumerate(chunk)
            ]
            kpi_rows.append(linha_lbl)
            kpi_rows.append(linha_val)

        tab_kpi = Table(
            kpi_rows,
            colWidths=[kpi_col_w * cm] * 4,
            hAlign="CENTER",
        )
        tab_kpi.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor(cls.COR_LINHA_ALT)),
            ("BOX",           (0, 0), (-1, -1), 1.5, colors.HexColor(cls.COR_PRIMARIA)),
            ("INNERGRID",     (0, 0), (-1, -1), 0.5, colors.HexColor(cls.COR_LINHA)),
            ("TOPPADDING",    (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            # Linha de separação entre label e valor
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, colors.HexColor(cls.COR_LINHA)),
            ("LINEBELOW",     (0, 2), (-1, 2),  0.5, colors.HexColor(cls.COR_LINHA)),
        ]))
        el.append(tab_kpi)
        return el

    @classmethod
    def gerar(
        cls,
        df: pd.DataFrame,
        sla_meta: float,
        p_ot: float,
        p_base: float,
        p_pess: float,
        min_aloc: float = 1,
        top_n: int = 10,
    ) -> bytes:
        """Gera o PDF e retorna os bytes prontos para download."""
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            rightMargin=1.0 * cm,
            leftMargin=1.0 * cm,
            topMargin=1.0 * cm,
            bottomMargin=1.3 * cm,
        )

        s = cls._estilos()
        df_seg = df[df["TIPO_SERVICO"] == TIPO].copy()
        m = Motor.projetar(df_seg, p_base)
        folga = Motor.folga_sla(df_seg, sla_meta)

        el: List[Any] = []

        # ── CAPA ────────────────────────────────────────────────────
        el += cls._capa(s, m, sla_meta, len(df_seg))
        el.append(Spacer(1, 0.4 * cm))

        # ── SEÇÃO 1 — Cenários ──────────────────────────────────────
        el.append(
            HRFlowable(
                width="100%", thickness=1, color=colors.HexColor(cls.COR_SECUNDARIA)
            )
        )
        el.append(Spacer(1, 0.15 * cm))
        el.append(Paragraph("1. Cenários de Fechamento", s["PME_Secao"]))

        cenarios = []
        for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]:
            proj = Motor.projetar(df_seg, p)
            cenarios.append(
                {
                    "Cenário": nome,
                    "Probab. Pend.": p,
                    "Fechamento": proj["fechamento_proj"],
                    "Não Exec. Proj.": proj["naoexec_proj"],
                    "vs Meta": proj["fechamento_proj"] - sla_meta,
                }
            )
        el.append(
            cls._tab(
                pd.DataFrame(cenarios),
                larguras=[4.5, 4.5, 5.5, 5.5, 5.0],
                cor_col_quebra="Fechamento",
                sla_meta=sla_meta,
            )
        )
        el.append(Spacer(1, 0.2 * cm))

        # Texto diagnóstico
        if m["fechamento_proj"] > sla_meta:
            diag = (
                f"O cenário base projeta fechamento de {m['fechamento_proj']:.2%}, "
                f"{m['fechamento_proj'] - sla_meta:.2%} acima da meta de {sla_meta:.2%}. "
                f"Serão necessárias ao menos "
                f"{int(np.ceil(folga['precisa_executar_pendente'])):,} execuções "
                f"nos pendentes para retornar ao SLA."
            )
            el.append(Paragraph(escape(diag), s["PME_Alerta"]))
        else:
            diag = (
                f"O cenário base projeta fechamento de {m['fechamento_proj']:.2%}, "
                f"com folga de {sla_meta - m['fechamento_proj']:.2%}. "
                f"Ainda é possível ter até "
                f"{int(np.floor(folga['folga_ne_pendente'])):,} OS adicionais "
                f"como não executadas dentro do SLA."
            )
            el.append(Paragraph(escape(diag), s["PME_OK"]))

        el.append(Spacer(1, 0.3 * cm))

        # ── SEÇÃO 2 — Técnicos Críticos ──────────────────────────────
        el.append(Paragraph("2. Técnicos Críticos", s["PME_Secao"]))
        el.append(
            HRFlowable(
                width="100%", thickness=0.5, color=colors.HexColor(cls.COR_LINHA)
            )
        )
        el.append(Spacer(1, 0.15 * cm))

        df_tec = Motor.tecnicos_criticos(
            df_seg, TIPO, p_base, float(min_aloc), int(top_n)
        )
        cols_tec = [
            c
            for c in [
                "TÉCNICO",
                "Alocado",
                "Executada",
                "Não Executada",
                "Pendente",
                "Quebra Atual",
                "Fechamento Otimista",
                "Fechamento Base",
                "Fechamento Pessimista",
            ]
            if c in df_tec.columns
        ]

        el.append(
            cls._tab(
                df_tec[cols_tec] if not df_tec.empty else df_tec,
                limite=10,
                cor_col_quebra="Fechamento Base",
                sla_meta=sla_meta,
            )
        )

        if not df_tec.empty:
            acima = int((df_tec["Fechamento Base"] > sla_meta).sum())
            txt_tec = (
                f"{acima} de {len(df_tec)} técnicos projetam fechamento "
                f"acima da meta de {sla_meta:.2%}."
            )
            el.append(Spacer(1, 0.15 * cm))
            el.append(
                Paragraph(
                    escape(txt_tec),
                    s["PME_Alerta"] if acima > 0 else s["PME_OK"],
                )
            )

        el.append(Spacer(1, 0.4 * cm))


        # ── SEÇÃO 3 — Causas de Quebra ────────────────────────────────
        el.append(Paragraph("3. Principais Causas de Quebra (Pareto)", s["PME_Secao"]))
        el.append(
            HRFlowable(
                width="100%", thickness=0.5, color=colors.HexColor(cls.COR_LINHA)
            )
        )
        el.append(Spacer(1, 0.15 * cm))
        
        df_causa = Motor.causa_raiz_segmento(df_seg, TIPO, "_COL_BAIXA", top_n=8)

        el.append(
            cls._tab(
                df_causa,
                limite=8,
                larguras=[9.0, 4.5, 4.5, 4.5],
            )
        )

        el.append(Spacer(1, 0.4 * cm))

        # ── SEÇÃO 4 — Monitores ───────────────────────────────────────
        el.append(Paragraph("4. Monitores do Segmento PME", s["PME_Secao"]))
        el.append(
            HRFlowable(
                width="100%", thickness=0.5, color=colors.HexColor(cls.COR_LINHA)
            )
        )
        el.append(Spacer(1, 0.15 * cm))

        df_mon = Motor.tabela_cenarios(
            df_seg, "MONITOR", p_ot, p_base, p_pess, float(min_aloc)
        )
        cols_mon = [
            c
            for c in [
                "MONITOR",
                "Alocado",
                "Executada",
                "Não Executada",
                "Pendente",
                "Quebra Atual",
                "Fechamento Base",
            ]
            if c in df_mon.columns
        ]

        el.append(
            cls._tab(
                df_mon[cols_mon] if not df_mon.empty else df_mon,
                limite=10,
                cor_col_quebra="Fechamento Base",
                sla_meta=sla_meta,
            )
        )

        doc.build(
            el,
            onFirstPage=cls._rodape,
            onLaterPages=cls._rodape,
        )
        buf.seek(0)
        return buf.getvalue()


# ====================================================
# FUNÇÃO PRINCIPAL
# ====================================================
def main():
    aplicar_estilo()

    st.markdown(
        '<div class="hero" style="background:linear-gradient(135deg,#4C1D95 0%,#7C3AED 100%);">'
        "<h1>🏢 PME — Quebra de Agenda</h1>"
        "<p>Análise estratégica dedicada às Pequenas e Médias Empresas</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    # ── Guarda de estado ────────────────────────────────────────────
    if st.session_state.get("df_memoria") is None:
        st.warning("⚠️ Nenhuma base carregada.")
        st.info("👈 Volte ao **Dashboard Geral** no menu lateral e faça o upload.")
        return

    df_full = st.session_state["df_memoria"].copy()
    if "Status Contrato" not in df_full.columns:
        col_s = Utils.buscar_coluna(df_full, ["STATUS DA O.S 1", "STATUS OS 1"])
        df_full["Status Contrato"] = (
            Utils.classificar_status(df_full[col_s]) if col_s else "Pendente"
        )

    # ── Sidebar ─────────────────────────────────────────────────────
    with st.sidebar:
        st.header("🎯 Filtros PME")

        monitores = ["Todos"] + sorted(
            str(x)
            for x in df_full["MONITOR"].dropna().unique()
            if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
        )
        sel_mon = st.selectbox("👔 Monitor", monitores, key="mon_pme")
        df_filt = (
            df_full if sel_mon == "Todos" else df_full[df_full["MONITOR"] == sel_mon]
        )

        tecnicos = ["Todos"] + sorted(
            str(x)
            for x in df_filt["TÉCNICO"].dropna().unique()
            if str(x) not in {"nan", "NÃO MAPEADO"}
        )
        sel_tec = st.selectbox("👤 Técnico", tecnicos, key="tec_pme")
        df = df_filt if sel_tec == "Todos" else df_filt[df_filt["TÉCNICO"] == sel_tec]

        st.divider()
        st.subheader("🔮 Probabilidades")
        p_ot = st.slider("Otimista (%)", 0, 100, 15, 5, key="pot_pme") / 100.0
        p_base = st.slider("Base (%)", 0, 100, 20, 5, key="pbase_pme") / 100.0
        p_pess = st.slider("Pessimista (%)", 0, 100, 50, 5, key="ppess_pme") / 100.0

        st.divider()
        sla_meta = (
            st.number_input(
                "Meta SLA PME (%)",
                0.0,
                100.0,
                float(SLA_DEFAULT * 100),
                1.0,
                key="sla_pme_v",
            )
            / 100
        )

        min_aloc = 1
        top_n = 999_999

    # ── Validações ──────────────────────────────────────────────────
    if df.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    render_resultado_base(sorted(df[Config.COL_REGIAO].unique()), len(df))

    df_seg = df[df["TIPO_SERVICO"] == TIPO].copy()
    if df_seg.empty:
        st.info("⚠️ Nenhum registro classificado como PME nos filtros atuais.")
        return

    m_seg = Motor.projetar(df_seg, p_base)
    render_segmento_header(TIPO, m_seg["quebra_atual"], sla_meta)
    render_alerta_sla(m_seg["quebra_atual"], sla_meta, TIPO)
    st.markdown("")

    # ── Botão de PDF Executivo ────────────────────────────────────────
    with st.container():
        col_btn, col_desc = st.columns([1, 3])

        with col_btn:
            with st.spinner("Gerando PDF..."):
                pdf_bytes = PDFExecutivoPME.gerar(
                    df=df,
                    sla_meta=sla_meta,
                    p_ot=p_ot,
                    p_base=p_base,
                    p_pess=p_pess,
                    min_aloc=float(min_aloc),
                    top_n=min(int(top_n), 10),
                )

            st.download_button(
                label="📄 Baixar PDF Executivo PME",
                data=pdf_bytes,
                file_name=f"relatorio_pme_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                key="pdf_pme_dl",
                use_container_width=True,
                type="primary",
            )

        with col_desc:
            st.info(
                "**O relatório PDF inclui:**  \n"
                "Capa com métricas executivas · Cenários de fechamento (Otimista / Base / Pessimista) "
                "· Plano de ação prioritário automático · Top 10 Técnicos Críticos com coloração por SLA "
                "· Performance por Região · Pareto de causas de quebra · Ranking de Monitores"
            )

    st.divider()

    # ── Sub-abas ─────────────────────────────────────────────────────
    sub1, sub2, sub3, sub4 = st.tabs(
        ["📊 Visão Geral", "🔍 Causa Raiz", "👤 Técnicos", "🎯 Plano de Ação"]
    )

    with sub1:
        _sub_visao_geral(df_seg, m_seg, p_ot, p_base, p_pess, sla_meta)

    with sub2:
        _sub_causa_raiz(df_seg)

    with sub3:
        _sub_tecnicos(df_seg, p_base, min_aloc, top_n, sla_meta)

    with sub4:
        _sub_plano_acao(df_seg, p_base, sla_meta)


# ====================================================
# SUB-ABAS
# ====================================================
def _sub_visao_geral(df_seg, m_seg, p_ot, p_base, p_pess, sla_meta):
    render_section(f"📊 Resumo Operacional — {TIPO}")

    cols = st.columns(5)
    kpis = [
        ("Alocado", f"{int(m_seg['alocado']):,}", "azul", ""),
        ("Executadas", f"{int(m_seg['exec']):,}", "verde", ""),
        ("Não Exec.", f"{int(m_seg['naoexec']):,}", "laranja", ""),
        ("Pendentes", f"{int(m_seg['pend']):,}", "cinza", ""),
        (
            "Quebra Atual",
            f"{m_seg['quebra_atual']:.2%}",
            "vermelho" if m_seg["quebra_atual"] > sla_meta else "verde",
            f"Meta: {sla_meta:.0%}",
        ),
    ]
    for c, (lab, val, tema, sub) in zip(cols, kpis):
        render_kpi(c, lab, val, sub=sub, tema=tema)

    st.markdown("")
    render_section("🔮 Projeções de Fechamento")

    cen = {
        n: Motor.projetar(df_seg, p)
        for n, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]
    }

    c_cen, c_gauge = st.columns([2, 3])
    with c_cen:
        for nome, cd in cen.items():
            cor = "vermelho" if cd["fechamento_proj"] > sla_meta else "verde"
            render_kpi_sm(
                st,
                nome,
                f"{cd['fechamento_proj']:.2%}",
                sub=f"Não Exec. proj.: {int(cd['naoexec_proj']):,}",
                tema=cor,
            )

    with c_gauge:
        cor_bar = "#EF4444" if m_seg["quebra_atual"] > sla_meta else "#10B981"
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number+delta",
                value=m_seg["quebra_atual"] * 100,
                delta={
                    "reference": sla_meta * 100,
                    "increasing": {"color": "#EF4444"},
                    "decreasing": {"color": "#10B981"},
                    "suffix": "%",
                },
                number={"suffix": "%", "font": {"size": 40}},
                gauge={
                    "axis": {"range": [0, 50], "ticksuffix": "%"},
                    "bar": {"color": cor_bar},
                    "steps": [
                        {"range": [0, sla_meta * 100], "color": "#DCFCE7"},
                        {"range": [sla_meta * 100, sla_meta * 120], "color": "#FEF9C3"},
                        {"range": [sla_meta * 120, 50], "color": "#FEE2E2"},
                    ],
                    "threshold": {
                        "line": {"color": "#DC2626", "width": 3},
                        "thickness": 0.85,
                        "value": sla_meta * 100,
                    },
                },
                title={"text": f"Quebra vs. Meta {sla_meta:.0%}", "font": {"size": 14}},
            )
        )
        fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("")
    render_section("🛡️ Folga de SLA")

    folga = Motor.folga_sla(df_seg, sla_meta)
    f1, f2, f3 = st.columns(3)
    cor_f = (
        "vermelho"
        if folga["estourado"]
        else ("verde" if folga["folga_ne_pendente"] > 0 else "laranja")
    )
    render_kpi(
        f1,
        "Folga (OS)",
        f"{int(np.floor(folga['folga_ne_pendente'])):,}",
        sub="Não Exec. ainda permitidas",
        tema=cor_f,
    )
    render_kpi(
        f2,
        "Execução Mínima",
        f"{int(np.ceil(folga['precisa_executar_pendente'])):,}",
        sub="Pendentes que devem ser executadas",
        tema="azul",
    )
    render_kpi(
        f3,
        "Limite NE Total",
        f"{int(folga['limite_ne_total']):,}",
        sub=f"= {sla_meta:.0%} × {int(folga['alocado']):,}",
        tema="cinza",
    )

    st.progress(min(1.0, max(0.0, float(m_seg["quebra_atual"] / (sla_meta * 2)))))


def _sub_causa_raiz(df_seg):
    render_section(f"🔍 Causa Raiz — {TIPO}")
    df_c = Motor.causa_raiz_segmento(df_seg, TIPO, "_COL_BAIXA", top_n=8)

    if df_c.empty:
        render_insight(
            "Coluna de código/motivo de baixa não identificada.",
            tipo="alerta",
        )
        return

    c_tab, c_chart = st.columns([1.2, 2])

    with c_tab:
        render_dataframe(
            df_c,
            titulo=f"Top Motivos — {TIPO}",
            icone="🔍",
            fmt={"% do Total": "{:.2%}", "Acumulado": "{:.2%}"},
            height=350,
        )

    with c_chart:
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=df_c["Motivo de Baixa"],
                y=df_c["Volume"],
                name="Volume",
                marker_color="#EF4444",
                text=df_c["Volume"],
                textposition="outside",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df_c["Motivo de Baixa"],
                y=df_c["Acumulado"],
                name="Acumulado %",
                yaxis="y2",
                mode="lines+markers",
                line=dict(color="#7C3AED", width=2),
                marker=dict(size=7),
            )
        )
        fig.update_layout(
            title=f"Pareto de Motivos — {TIPO}",
            yaxis=dict(title="Volume"),
            yaxis2=dict(
                title="Acumulado %",
                overlaying="y",
                side="right",
                tickformat=".0%",
                range=[0, 1.1],
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=380,
            xaxis=dict(tickangle=-30),
        )
        fig.add_hline(
            y=0.8,
            line_dash="dot",
            line_color="#F59E0B",
            yref="y2",
            annotation_text="80%",
            annotation_position="top right",
        )
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    if len(df_c) >= 2:
        t1, t2 = df_c.iloc[0], df_c.iloc[1]
        render_insight(
            f"Os 2 principais motivos (<strong>{t1['Motivo de Baixa']}</strong> e "
            f"<strong>{t2['Motivo de Baixa']}</strong>) respondem por "
            f"<strong>{t2['Acumulado']:.1%}</strong> das quebras em {TIPO}.",
            tipo="acao",
        )


def _sub_tecnicos(df_seg, p_base, min_aloc, top_n, sla_meta):
    render_section(f"👤 Técnicos com Maior Quebra — {TIPO}")
    df_tec = Motor.tecnicos_criticos(df_seg, TIPO, p_base, float(min_aloc), int(top_n))

    if df_tec.empty:
        render_insight(
            f"Não há técnicos com volume mínimo de {int(min_aloc)} OS.",
            tipo="info",
        )
        return

    render_dataframe(
        df_tec,
        titulo=f"Técnicos Críticos — {TIPO}",
        icone="🚨",
        fmt=FMT_QUEBRA,
        color_col="Fechamento Base",
        color_meta=sla_meta,
        color_invertido=True,
        height=450,
    )
    st.download_button(
        f"📥 Exportar Técnicos {TIPO}",
        Utils.gerar_excel(df_tec, f"Tec_{TIPO[:25]}"),
        f"tecnicos_{TIPO.lower()}.xlsx",
        key="dl_tec_pme",
    )

    df_plot = df_tec.head(10).sort_values("Fechamento Base")
    cores = [
        "#EF4444" if v > sla_meta else "#10B981" for v in df_plot["Fechamento Base"]
    ]
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df_plot["TÉCNICO"],
            x=df_plot["Fechamento Base"],
            orientation="h",
            marker_color=cores,
            text=[f"{v:.1%}" for v in df_plot["Fechamento Base"]],
            textposition="outside",
        )
    )
    fig.add_vline(
        x=sla_meta,
        line_dash="dash",
        line_color="#DC2626",
        annotation_text=f"Meta {sla_meta:.0%}",
    )
    fig.update_layout(
        title=f"Quebra Projetada por Técnico — {TIPO}",
        xaxis_tickformat=".1%",
        height=max(300, len(df_plot) * 36),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    acima = int((df_tec["Fechamento Base"] > sla_meta).sum())
    pct = acima / len(df_tec)
    if pct > 0.5:
        render_insight(
            f"<strong>{acima} de {len(df_tec)}</strong> técnicos ({pct:.0%}) "
            f"estão acima da meta. Avalie redistribuição de carteira.",
            tipo="critico",
        )
    elif acima > 0:
        render_insight(
            f"<strong>{acima} técnico(s)</strong> com quebra acima da meta.",
            tipo="alerta",
        )
    else:
        render_insight(f"Todos os técnicos dentro da meta em {TIPO}.", tipo="ok")


def _sub_plano_acao(df_seg, p_base, sla_meta):
    render_section(f"🎯 Plano de Ação — {TIPO}")

    folga = Motor.folga_sla(df_seg, sla_meta)
    cen = Motor.projetar(df_seg, p_base)
    excesso = max(0.0, folga["naoexec"] - folga["limite_ne_total"])
    pend_exec = folga["precisa_executar_pendente"]

    col_d, col_a = st.columns([1, 1.5])

    with col_d:
        render_section("📋 Diagnóstico")
        render_kpi_sm(
            st,
            "Excesso de NE",
            f"{int(excesso):,}",
            sub="OS além do permitido",
            tema="vermelho" if excesso > 0 else "verde",
        )
        render_kpi_sm(
            st,
            "Pendentes a Executar",
            f"{int(np.ceil(pend_exec)):,}",
            sub=f"Mínimo para meta {sla_meta:.0%}",
            tema="azul",
        )
        render_kpi_sm(
            st,
            "Proj. Base",
            f"{cen['fechamento_proj']:.2%}",
            sub=f"c/ {p_base:.0%} de quebra nos pendentes",
            tema="vermelho" if cen["fechamento_proj"] > sla_meta else "verde",
        )
        st.markdown("")
        if folga["pend"] > 0:
            tx = 1 - (folga["folga_ne_pendente"] / folga["pend"])
            st.markdown(f"**Taxa mínima de execução:** `{max(0, tx):.1%}`")
            st.progress(min(1.0, max(0.0, float(tx))))

    with col_a:
        render_section("✅ Ações Recomendadas")
        acoes: List[tuple] = []

        if folga["estourado"]:
            acoes.append(
                (
                    "🔴 IMEDIATA",
                    f"Acionar plantão para recuperar {int(excesso):,} OS não executadas "
                    f"acima do limite do SLA.",
                    "critico",
                )
            )
        if pend_exec > 0:
            acoes.append(
                (
                    "🟠 ALTA",
                    f"Garantir execução de pelo menos {int(np.ceil(pend_exec)):,} "
                    f"OS pendentes de {TIPO} para atingir a meta de {sla_meta:.0%}.",
                    "alerta",
                )
            )

        acoes.extend(ACOES_PME)

        for pri, ac, tp in acoes:
            render_insight(f"<strong>{pri}</strong> — {ac}", tipo=tp)

    st.markdown("")
    df_plano = pd.DataFrame(
        [{"Segmento": TIPO, "Prioridade": p, "Ação": a} for p, a, _ in acoes]
    )
    if not df_plano.empty:
        st.download_button(
            f"📥 Exportar Plano — {TIPO}",
            Utils.gerar_excel(df_plano, f"Plano_{TIPO[:25]}"),
            f"plano_{TIPO.lower()}.xlsx",
            key="dl_plano_pme",
        )


if __name__ == "__main__":
    main()
