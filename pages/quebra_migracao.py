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
    page_title="Migração — Quebra de Agenda",
    page_icon="🔄",
    layout="wide",
)
st.session_state.setdefault("df_memoria", None)

# ====================================================
# CONSTANTES DO SEGMENTO
# ====================================================
TIPO        = "Migração"
SLA_DEFAULT = Config.SLA_MIGRACAO

ACOES_MIGRACAO: List[tuple] = [
    (
        "ALTA",
        "Verificar estoque de equipamentos GPON nos almoxarifados das regiões "
        "com maior quebra — falta de material é causa frequente em migrações.",
        "alerta",
    ),
    (
        "MÉDIA",
        "Confirmar certificação dos técnicos em instalação GPON. "
        "Migrações exigem habilitação técnica específica.",
        "acao",
    ),
    (
        "MÉDIA",
        "Priorizar agendamentos de migração no início do turno — "
        "instalações GPON têm tempo médio maior e impactam mais a quebra "
        "quando reagendadas.",
        "acao",
    ),
    (
        "BAIXA",
        "Validar se ordens de Migração com status 'Pendente' possuem "
        "pré-vistoria aprovada. Evita quebra por impedimento técnico "
        "no dia do atendimento.",
        "info",
    ),
]

FMT_QUEBRA: Dict[str, str] = {
    "Quebra Atual":          "{:.2%}",
    "Fechamento Otimista":   "{:.2%}",
    "Fechamento Base":       "{:.2%}",
    "Fechamento Pessimista": "{:.2%}",
}


# ====================================================
# PDF EXECUTIVO MIGRAÇÃO
# ====================================================
class PDFExecutivoMigracao:
    """Relatório executivo em PDF dedicado ao segmento Migração."""

    # ── Paleta de cores (azul petróleo) ─────────────────────────────
    COR_PRIMARIA:   str = "#0C4A6E"
    COR_SECUNDARIA: str = "#0369A1"
    COR_TEXTO:      str = "#0F172A"
    COR_SUBTEXTO:   str = "#6B7280"
    COR_OK:         str = "#059669"
    COR_ALERTA:     str = "#D97706"
    COR_CRITICO:    str = "#DC2626"
    COR_LINHA:      str = "#E5E7EB"
    COR_LINHA_ALT:  str = "#F0F9FF"

    # ── Dimensões (landscape A4) ─────────────────────────────────────
    LARGURA_UTIL: float = 27.7
    MARGEM_H:     float = 0.8
    MARGEM_TOP:   float = 0.8
    MARGEM_BOT:   float = 1.3

    # ── Caminho do logo ──────────────────────────────────────────────
    LOGO_PATH: Path = (
        Path(__file__).resolve().parent.parent
        / "assets" / "images" / "novo-logo-totale.png"
    )

    # ================================================================
    # HELPERS PRIVADOS
    # ================================================================

    @classmethod
    def _fmt(cls, v: Any, col: str = "") -> str:
        """Formata um valor para exibição em célula de tabela PDF."""
        if pd.isna(v):
            return "—"
        col_u    = str(col).upper()
        pct_keys = {"QUEBRA", "FECHAMENTO", "META", "PROBAB", "%", "ACUMULADO", "TOTAL"}

        if isinstance(v, (float, np.floating)):
            if any(k in col_u for k in pct_keys):
                return f"{v:.2%}"
            if float(v).is_integer():
                return f"{int(v):,}".replace(",", ".")
            return (
                f"{v:,.2f}"
                .replace(",", "X")
                .replace(".", ",")
                .replace("X", ".")
            )
        if isinstance(v, (int, np.integer)):
            return f"{v:,}".replace(",", ".")
        return escape(str(v))

    @classmethod
    def _calcular_larguras(cls, df: pd.DataFrame) -> List[float]:
        """
        Calcula larguras proporcionais em cm pelo conteúdo real.
        A soma sempre resulta em LARGURA_UTIL cm.
        """
        if df.empty:
            return [cls.LARGURA_UTIL]

        pesos: List[float] = []
        for col in df.columns:
            max_len = len(str(col))
            for val in df[col].head(50):
                max_len = max(max_len, len(cls._fmt(val, col)))
            pesos.append(min(max(max_len, 5), 30))

        total = sum(pesos)
        return [(p / total) * cls.LARGURA_UTIL for p in pesos]

    @classmethod
    def _estilos(cls) -> Any:
        """Cria e retorna o stylesheet ReportLab do relatório."""
        s = getSampleStyleSheet()

        defs = [
            ("MIG_Titulo", {
                "fontName": "Helvetica-Bold", "fontSize": 22, "leading": 28,
                "textColor": colors.white, "alignment": TA_CENTER, "spaceAfter": 2,
            }),
            ("MIG_Subtitulo", {
                "fontName": "Helvetica", "fontSize": 9, "leading": 13,
                "textColor": colors.HexColor("#BAE6FD"),
                "alignment": TA_CENTER, "spaceAfter": 0,
            }),
            ("MIG_Secao", {
                "fontName": "Helvetica-Bold", "fontSize": 11, "leading": 15,
                "textColor": colors.HexColor(cls.COR_PRIMARIA),
                "spaceBefore": 8, "spaceAfter": 4, "alignment": TA_LEFT,
            }),
            ("MIG_Texto", {
                "fontName": "Helvetica", "fontSize": 8, "leading": 11,
                "textColor": colors.HexColor(cls.COR_TEXTO),
                "alignment": TA_LEFT, "spaceAfter": 3,
            }),
            ("MIG_Destaque", {
                "fontName": "Helvetica-Bold", "fontSize": 8, "leading": 11,
                "textColor": colors.HexColor(cls.COR_PRIMARIA),
                "alignment": TA_LEFT, "spaceAfter": 2,
            }),
            ("MIG_Alerta", {
                "fontName": "Helvetica-Bold", "fontSize": 8, "leading": 11,
                "textColor": colors.HexColor(cls.COR_CRITICO),
                "alignment": TA_LEFT, "spaceAfter": 2,
            }),
            ("MIG_OK", {
                "fontName": "Helvetica-Bold", "fontSize": 8, "leading": 11,
                "textColor": colors.HexColor(cls.COR_OK),
                "alignment": TA_LEFT, "spaceAfter": 2,
            }),
        ]
        for nome, props in defs:
            s.add(ParagraphStyle(name=nome, parent=s["Normal"], **props))
        return s

    @classmethod
    def _tab(
        cls,
        df: pd.DataFrame,
        limite: Optional[int] = None,
        larguras: Optional[List[float]] = None,
        cor_col_quebra: Optional[str] = None,
        sla_meta: float = 0.25,
    ) -> Table:
        """
        Constrói Table ReportLab centralizada e auto-ajustada.
        Usa wrapper de largura total para garantir centralização real.
        """

        def _interna() -> Table:
            # ── Vazio ────────────────────────────────────────────────
            if df is None or df.empty:
                vazio: List[List[Any]] = [["Sem dados disponíveis"]]
                t = Table(vazio, colWidths=[cls.LARGURA_UTIL * cm])
                t.setStyle(TableStyle([
                    ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor(cls.COR_LINHA_ALT)),
                    ("TEXTCOLOR",     (0, 0), (-1, -1), colors.HexColor(cls.COR_SUBTEXTO)),
                    ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                    ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
                    ("FONTSIZE",      (0, 0), (-1, -1), 8),
                    ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor(cls.COR_LINHA)),
                    ("TOPPADDING",    (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]))
                return t

            # ── Dados ────────────────────────────────────────────────
            base = df.head(limite) if limite else df.copy()

            st_h = ParagraphStyle(
                "mig_th", fontName="Helvetica-Bold", fontSize=6.5,
                leading=8, textColor=colors.white, alignment=TA_CENTER,
            )
            st_c = ParagraphStyle(
                "mig_tc", fontName="Helvetica", fontSize=6.5,
                leading=8.5, textColor=colors.HexColor(cls.COR_TEXTO),
                alignment=TA_CENTER,
            )
            st_c_left = ParagraphStyle(
                "mig_tc_left", fontName="Helvetica", fontSize=6.5,
                leading=8.5, textColor=colors.HexColor(cls.COR_TEXTO),
                alignment=TA_LEFT,
            )

            dados: List[List[Any]] = [
                [Paragraph(str(c), st_h) for c in base.columns]
            ]
            for _, row in base.iterrows():
                linha: List[Any] = [
                    Paragraph(cls._fmt(row[c], c), st_c_left if i == 0 else st_c)
                    for i, c in enumerate(base.columns)
                ]
                dados.append(linha)

            # ── Larguras ─────────────────────────────────────────────
            if larguras:
                col_widths = [w * cm for w in larguras]
            else:
                col_widths = [w * cm for w in cls._calcular_larguras(base)]

            soma = sum(col_widths)
            if soma > cls.LARGURA_UTIL * cm:
                fator = (cls.LARGURA_UTIL * cm) / soma
                col_widths = [w * fator for w in col_widths]

            tab = Table(dados, colWidths=col_widths, repeatRows=1)

            style: List[Any] = [
                ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor(cls.COR_PRIMARIA)),
                ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
                ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
                ("FONTSIZE",      (0, 0), (-1, 0),  6.5),
                ("LINEBELOW",     (0, 0), (-1, 0),  1.5, colors.HexColor(cls.COR_SECUNDARIA)),
                ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE",      (0, 1), (-1, -1), 6.5),
                ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
                ("ALIGN",         (0, 1), (0, -1),  "LEFT"),
                ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
                ("BOX",           (0, 0), (-1, -1), 0.75, colors.HexColor(cls.COR_PRIMARIA)),
                ("INNERGRID",     (0, 0), (-1, -1), 0.25, colors.HexColor(cls.COR_LINHA)),
                ("TOPPADDING",    (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING",   (0, 0), (-1, -1), 5),
                ("RIGHTPADDING",  (0, 0), (-1, -1), 5),
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
                            bg_c  = colors.HexColor("#FEE2E2")
                            txt_c = colors.HexColor(cls.COR_CRITICO)
                        elif val > sla_meta * 0.85:
                            bg_c  = colors.HexColor("#FEF9C3")
                            txt_c = colors.HexColor(cls.COR_ALERTA)
                        else:
                            bg_c  = colors.HexColor("#DCFCE7")
                            txt_c = colors.HexColor(cls.COR_OK)
                        style += [
                            ("BACKGROUND", (col_idx, row_i), (col_idx, row_i), bg_c),
                            ("TEXTCOLOR",  (col_idx, row_i), (col_idx, row_i), txt_c),
                            ("FONTNAME",   (col_idx, row_i), (col_idx, row_i), "Helvetica-Bold"),
                        ]
                    except (ValueError, TypeError):
                        pass

            tab.setStyle(TableStyle(style))
            return tab

        # ── Wrapper de centralização ──────────────────────────────────
        wrapper_data: List[List[Any]] = [[_interna()]]
        wrapper = Table(
            wrapper_data,
            colWidths=[cls.LARGURA_UTIL * cm],
            hAlign="CENTER",
        )
        wrapper.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return wrapper

    @classmethod
    def _tab_acoes(cls, acoes_pdf: List[tuple], s: Any) -> Table:
        """Tabela de plano de ação com coloração por prioridade."""
        header: List[Any] = ["#", "Prioridade", "Ação Recomendada"]
        dados: List[List[Any]] = [header]

        for i, (pri, ac, _) in enumerate(acoes_pdf, 1):
            linha: List[Any] = [
                str(i),
                pri,
                Paragraph(
                    escape(ac),
                    ParagraphStyle(
                        f"ac_mig_{i}", fontName="Helvetica", fontSize=7,
                        leading=9.5, textColor=colors.HexColor(cls.COR_TEXTO),
                    ),
                ),
            ]
            dados.append(linha)

        tab = Table(
            dados,
            colWidths=[1.2 * cm, 3.5 * cm, (cls.LARGURA_UTIL - 4.7) * cm],
            hAlign="CENTER",
            repeatRows=1,
        )

        style: List[Any] = [
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor(cls.COR_PRIMARIA)),
            ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, 0),  7),
            ("FONTNAME",      (0, 1), (1, -1),  "Helvetica"),
            ("FONTSIZE",      (0, 1), (1, -1),  7),
            ("ALIGN",         (0, 0), (1, -1),  "CENTER"),
            ("ALIGN",         (2, 1), (2, -1),  "LEFT"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("BOX",           (0, 0), (-1, -1), 0.75, colors.HexColor(cls.COR_PRIMARIA)),
            ("INNERGRID",     (0, 0), (-1, -1), 0.25, colors.HexColor(cls.COR_LINHA)),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 4),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 4),
        ]

        _cor_pri = {
            "IMEDIATA": ("#FEE2E2", cls.COR_CRITICO),
            "ALTA":     ("#FFF7ED", cls.COR_ALERTA),
            "MÉDIA":    ("#FEF9C3", "#92400E"),
            "MEDIA":    ("#FEF9C3", "#92400E"),
            "BAIXA":    ("#DCFCE7", cls.COR_OK),
        }
        for row_i, (pri, _, _) in enumerate(acoes_pdf, 1):
            pri_u = pri.upper()
            bg_p, tx_p = "#F0F9FF", cls.COR_SUBTEXTO
            for chave, (bg, tx) in _cor_pri.items():
                if chave in pri_u:
                    bg_p, tx_p = bg, tx
                    break
            style += [
                ("BACKGROUND", (1, row_i), (1, row_i), colors.HexColor(bg_p)),
                ("TEXTCOLOR",  (1, row_i), (1, row_i), colors.HexColor(tx_p)),
                ("FONTNAME",   (1, row_i), (1, row_i), "Helvetica-Bold"),
            ]
            if row_i % 2 == 0:
                style += [
                    ("BACKGROUND", (0, row_i), (0, row_i), colors.HexColor(cls.COR_LINHA_ALT)),
                    ("BACKGROUND", (2, row_i), (2, row_i), colors.HexColor(cls.COR_LINHA_ALT)),
                ]

        tab.setStyle(TableStyle(style))
        return tab

    @classmethod
    def _secao(cls, el: List[Any], titulo: str, s: Any, espessa: bool = False) -> None:
        """Adiciona cabeçalho de seção com linha HR."""
        el.append(HRFlowable(
            width="100%",
            thickness=1.5 if espessa else 0.5,
            color=colors.HexColor(cls.COR_SECUNDARIA if espessa else cls.COR_LINHA),
            spaceAfter=2,
        ))
        el.append(Paragraph(titulo, s["MIG_Secao"]))

    @classmethod
    def _rodape(cls, canvas: Any, doc: Any) -> None:
        """Rodapé com logo, linha, texto e paginação."""
        canvas.saveState()

        page_w, _ = landscape(A4)
        x_esq   = cls.MARGEM_H * cm
        x_dir   = page_w - cls.MARGEM_H * cm
        y_linha = 1.05 * cm
        y_txt   = 0.52 * cm

        canvas.setStrokeColor(colors.HexColor(cls.COR_LINHA))
        canvas.setLineWidth(0.5)
        canvas.line(x_esq, y_linha, x_dir, y_linha)

        x_txt = x_esq
        if cls.LOGO_PATH.exists():
            try:
                logo_h = 0.50 * cm
                reader = ImageReader(str(cls.LOGO_PATH))
                iw, ih = reader.getSize()
                logo_w = logo_h * (iw / ih) if ih > 0 else logo_h * 3.5
                canvas.drawImage(
                    str(cls.LOGO_PATH),
                    x_esq, y_txt - 0.02 * cm,
                    width=logo_w, height=logo_h,
                    preserveAspectRatio=True, mask="auto",
                )
                x_txt = x_esq + logo_w + 0.25 * cm
            except Exception:
                pass

        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(colors.HexColor(cls.COR_SUBTEXTO))
        canvas.drawString(
            x_txt, y_txt,
            f"Migração — Gestão de Quebra de Agenda  |  "
            f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}  |  Confidencial",
        )
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
        """Capa: logo + banner azul + badge SLA + KPIs."""
        el: List[Any] = []

        # ── Logo ─────────────────────────────────────────────────────
        if cls.LOGO_PATH.exists():
            try:
                reader = ImageReader(str(cls.LOGO_PATH))
                iw, ih = reader.getSize()
                logo_h = 1.5 * cm
                logo_w = logo_h * (iw / ih) if ih > 0 else logo_h * 3.5

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

        # ── Banner azul ───────────────────────────────────────────────
        banner_data: List[List[Any]] = [
            [Paragraph("RELATÓRIO EXECUTIVO — MIGRAÇÃO", s["MIG_Titulo"])],
            [Paragraph(
                f"Mudança de Pacote + GPON  •  "
                f"Gerado em {datetime.now().strftime('%d/%m/%Y às %H:%M')}  •  "
                f"{total_registros:,} registros analisados".replace(",", "."),
                s["MIG_Subtitulo"],
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

        # ── Badge SLA ────────────────────────────────────────────────
        dentro_sla = m["quebra_atual"] <= sla_meta
        status_txt = "DENTRO DO SLA" if dentro_sla else "FORA DO SLA"
        icone      = "✅" if dentro_sla else "❌"
        cor_status = cls.COR_OK if dentro_sla else cls.COR_CRITICO

        st_status = ParagraphStyle(
            "mig_st_status", fontName="Helvetica-Bold", fontSize=11,
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

        # ── KPIs 4 × 2 ───────────────────────────────────────────────
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
            while len(chunk) < 4:
                chunk.append(("", "", cls.COR_SUBTEXTO))

            linha_lbl: List[Any] = [
                Paragraph(k[0], ParagraphStyle(
                    f"mig_kl_{i}_{j}", fontName="Helvetica", fontSize=7,
                    leading=9, textColor=colors.HexColor(cls.COR_SUBTEXTO),
                    alignment=TA_CENTER,
                ))
                for j, k in enumerate(chunk)
            ]
            linha_val: List[Any] = [
                Paragraph(k[1], ParagraphStyle(
                    f"mig_kv_{i}_{j}", fontName="Helvetica-Bold", fontSize=17,
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
            ("LINEBELOW",     (0, 0), (-1, 0),  0.5, colors.HexColor(cls.COR_LINHA)),
            ("LINEBELOW",     (0, 2), (-1, 2),  0.5, colors.HexColor(cls.COR_LINHA)),
        ]))
        el.append(tab_kpi)
        return el

    # ================================================================
    # GERADOR PRINCIPAL
    # ================================================================
    @classmethod
    def gerar(
        cls,
        df: pd.DataFrame,
        sla_meta: float,
        p_ot: float,
        p_base: float,
        p_pess: float,
        min_aloc: float = 1.0,
        top_n: int = 10,
    ) -> bytes:
        """Gera o PDF completo e retorna bytes para st.download_button."""
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=landscape(A4),
            rightMargin=cls.MARGEM_H  * cm,
            leftMargin=cls.MARGEM_H   * cm,
            topMargin=cls.MARGEM_TOP  * cm,
            bottomMargin=cls.MARGEM_BOT * cm,
        )

        s      = cls._estilos()
        df_seg = df[df["TIPO_SERVICO"] == TIPO].copy()
        m      = Motor.projetar(df_seg, p_base)
        folga  = Motor.folga_sla(df_seg, sla_meta)
        el: List[Any] = []

        # ── CAPA ────────────────────────────────────────────────────
        el += cls._capa(s, m, sla_meta, len(df_seg))
        el.append(Spacer(1, 0.35 * cm))

        # ── SEÇÃO 1 — Cenários ───────────────────────────────────────
        cls._secao(el, "1 ─ Cenários de Fechamento", s, espessa=True)

        cenarios: List[Dict[str, Any]] = []
        for nome, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]:
            proj = Motor.projetar(df_seg, p)
            cenarios.append({
                "Cenário":           nome,
                "Probab. Pendente":  p,
                "Fechamento Proj.":  proj["fechamento_proj"],
                "Não Exec. Proj.":   proj["naoexec_proj"],
                "vs Meta":           proj["fechamento_proj"] - sla_meta,
            })

        el.append(cls._tab(
            pd.DataFrame(cenarios),
            cor_col_quebra="Fechamento Proj.",
            sla_meta=sla_meta,
        ))
        el.append(Spacer(1, 0.12 * cm))

        if m["fechamento_proj"] > sla_meta:
            diag = (
                f"O cenário base projeta fechamento de {m['fechamento_proj']:.2%}, "
                f"excedendo a meta em {m['fechamento_proj'] - sla_meta:.2%}. "
                f"São necessárias ao menos "
                f"{int(np.ceil(folga['precisa_executar_pendente'])):,} "
                f"execuções nos pendentes para retornar ao SLA."
            )
            el.append(Paragraph(escape(diag), s["MIG_Alerta"]))
        else:
            diag = (
                f"Cenário base projeta {m['fechamento_proj']:.2%}, "
                f"com folga de {sla_meta - m['fechamento_proj']:.2%}. "
                f"A operação suporta até "
                f"{int(np.floor(folga['folga_ne_pendente'])):,} "
                f"OS adicionais como não executadas dentro do SLA."
            )
            el.append(Paragraph(escape(diag), s["MIG_OK"]))

        el.append(Spacer(1, 0.25 * cm))

        # ── SEÇÃO 2 — Técnicos Críticos ──────────────────────────────
        cls._secao(el, "2 ─ Técnicos Críticos", s)

        df_tec = Motor.tecnicos_criticos(
            df_seg, TIPO, p_base, float(min_aloc), int(top_n)
        )
        cols_tec = [c for c in [
            "TÉCNICO", "Alocado", "Executada", "Não Executada", "Pendente",
            "Quebra Atual", "Fechamento Otimista", "Fechamento Base", "Fechamento Pessimista",
        ] if c in df_tec.columns]

        el.append(cls._tab(
            df_tec[cols_tec] if not df_tec.empty else df_tec,
            limite=15,
            cor_col_quebra="Fechamento Base",
            sla_meta=sla_meta,
        ))

        if not df_tec.empty:
            acima     = int((df_tec["Fechamento Base"] > sla_meta).sum())
            total_tec = len(df_tec)
            txt = (
                f"{acima} de {total_tec} técnicos ({acima / total_tec:.0%}) "
                f"projetam fechamento acima da meta de {sla_meta:.2%}."
            ) if total_tec > 0 else ""
            el.append(Spacer(1, 0.1 * cm))
            el.append(Paragraph(
                escape(txt),
                s["MIG_Alerta"] if acima > 0 else s["MIG_OK"],
            ))

        el.append(Spacer(1, 0.3 * cm))

        # ── SEÇÃO 3 — Causas de Quebra ────────────────────────────────
        cls._secao(el, "3 ─ Principais Causas de Quebra", s)
        
        df_causa = Motor.causa_raiz_segmento(df_seg, TIPO, "_COL_BAIXA", top_n=8)
        el.append(cls._tab(df_causa, limite=8))

        if not df_causa.empty and len(df_causa) >= 2:
            t1, t2  = df_causa.iloc[0], df_causa.iloc[1]
            insight = (
                f"Os 2 principais motivos ('{t1['Motivo de Baixa']}' e "
                f"'{t2['Motivo de Baixa']}') representam "
                f"{t2['Acumulado']:.1%} do total de quebras."
            )
            el.append(Spacer(1, 0.1 * cm))
            el.append(Paragraph(escape(insight), s["MIG_Destaque"]))

        el.append(Spacer(1, 0.3 * cm))

        # ── SEÇÃO 4 — Monitores ───────────────────────────────────────
        cls._secao(el, "4 ─ Monitores do Segmento Migração", s)

        df_mon  = Motor.tabela_cenarios(df_seg, "MONITOR", p_ot, p_base, p_pess, float(min_aloc))
        cols_mon = [c for c in [
            "MONITOR", "Alocado", "Executada", "Não Executada",
            "Pendente", "Quebra Atual", "Fechamento Base",
        ] if c in df_mon.columns]

        el.append(cls._tab(
            df_mon[cols_mon] if not df_mon.empty else df_mon,
            limite=10,
            cor_col_quebra="Fechamento Base",
            sla_meta=sla_meta,
        ))

        doc.build(el, onFirstPage=cls._rodape, onLaterPages=cls._rodape)
        buf.seek(0)
        return buf.getvalue()
    
# ====================================================
# UTILITÁRIO — DataFrame de Pendentes Migração
# ====================================================

def _build_df_pendentes(df_seg: pd.DataFrame) -> pd.DataFrame:
    """
    Retorna um DataFrame com as OS pendentes do segmento Migração,
    contendo as colunas: Contrato, Login, Técnico, Monitor e Qtde. de O.S.

    Faz busca tolerante aos nomes de coluna reais do DataFrame.
    """

    # ── Mapeamento tolerante de colunas ────────────────────────────
    MAPA_COLUNAS = {
        "Contrato": [
            "CONTRATO", "Nº CONTRATO", "NUM_CONTRATO",
            "NUMERO CONTRATO", "NÚMERO CONTRATO", "CONTRATO_ID",
            "COD_CONTRATO", "CÓDIGO CONTRATO",
        ],
        "Login": [
            "LOGIN", "LOGIN TÉCNICO", "LOGIN_TECNICO",
            "USER", "USUÁRIO", "USERNAME",
        ],
        "Técnico": [
            "TÉCNICO", "TECNICO", "NOME TÉCNICO",
            "NOME_TECNICO", "NOME DO TÉCNICO",
        ],
        "Monitor": [
            "MONITOR", "SUPERVISOR", "NOME MONITOR",
            "NOME_MONITOR",
        ],
        "Qtde. O.S.": [
            "TOTAL DE TAREFAS"
        ],
    }

    def _encontrar_coluna(df: pd.DataFrame, candidatos: list[str]) -> str | None:
        """Retorna o primeiro nome de coluna que existir no DataFrame."""
        cols_upper = {c.upper(): c for c in df.columns}
        for cand in candidatos:
            if cand.upper() in cols_upper:
                return cols_upper[cand.upper()]
        return None

    # ── Filtrar apenas pendentes ────────────────────────────────────
    if "Status Contrato" in df_seg.columns:
        mask_pend = df_seg["Status Contrato"].str.upper().isin(
            ["PENDENTE", "PENDING", "ABERTO", "EM ABERTO", "NÃO EXECUTADO"]
        )
    else:
        # Fallback: usa classificar_status se disponível
        mask_pend = pd.Series([True] * len(df_seg), index=df_seg.index)

    df_pend = df_seg[mask_pend].copy()

    if df_pend.empty:
        return pd.DataFrame(
            columns=["Contrato", "Login", "Técnico", "Monitor", "Qtde. de O.S."]
        )

    # ── Montar DataFrame de saída ───────────────────────────────────
    df_out = pd.DataFrame(index=df_pend.index)

    for nome_saida, candidatos in MAPA_COLUNAS.items():
        col_real = _encontrar_coluna(df_pend, candidatos)

        if col_real:
            df_out[nome_saida] = df_pend[col_real].values
        else:
            df_out[nome_saida] = "N/D"   # coluna não encontrada na base
            
    if "Qtde. O.S." in df_out.columns:
        df_out["Qtde. O.S."] = (
            pd.to_numeric(df_out["Qtde. O.S."], errors="coerce")
            .fillna(0)                                                # NaN → 0
            .astype(int)                                            # float → int
    )

    # Remove duplicatas, ordena por Técnico
    df_out = (
        df_out
        .drop_duplicates()
        .sort_values(["Técnico"], na_position="last")
        .reset_index(drop=True)
    )

    # Índice começando em 1 para exibição
    df_out.index = df_out.index + 1

    return df_out


# ====================================================
# SUB-ABAS (específicas de Migração)
# ====================================================
def _sub_visao_geral(
    df_seg: pd.DataFrame,
    m_seg: dict,
    p_ot: float,
    p_base: float,
    p_pess: float,
    sla_meta: float,
) -> None:
    render_section(f"📊 Resumo Operacional — {TIPO}")

    c1, c2, c3, c4, c5 = st.columns(5)
    render_kpi(c1, "Alocado",    f"{int(m_seg['alocado']):,}", tema="azul")
    render_kpi(c2, "Executadas", f"{int(m_seg['exec']):,}",   tema="verde")
    render_kpi(c3, "Não Exec.",  f"{int(m_seg['naoexec']):,}",tema="laranja")
    render_kpi(c4, "Pendentes",  f"{int(m_seg['pend']):,}",   tema="cinza")
    render_kpi(
        c5, "Quebra Atual", f"{m_seg['quebra_atual']:.2%}",
        sub=f"Meta: {sla_meta:.0%}",
        tema="vermelho" if m_seg["quebra_atual"] > sla_meta else "verde",
    )

    st.markdown("")
    render_section("🔮 Projeções de Fechamento")

    cen = {
        n: Motor.projetar(df_seg, p)
        for n, p in [("Otimista", p_ot), ("Base", p_base), ("Pessimista", p_pess)]
    }

    c_cen, c_gauge = st.columns([2, 3])
    with c_cen:
        for nome, cd in cen.items():
            render_kpi_sm(
                st, nome, f"{cd['fechamento_proj']:.2%}",
                sub=f"Não Exec. proj.: {int(cd['naoexec_proj']):,}",
                tema="vermelho" if cd["fechamento_proj"] > sla_meta else "verde",
            )

    with c_gauge:
        cor_bar = "#EF4444" if m_seg["quebra_atual"] > sla_meta else "#10B981"
        fig = go.Figure(go.Indicator(
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
                    {"range": [0,              sla_meta * 100], "color": "#DCFCE7"},
                    {"range": [sla_meta * 100, sla_meta * 120], "color": "#FEF9C3"},
                    {"range": [sla_meta * 120, 50],             "color": "#FEE2E2"},
                ],
                "threshold": {
                    "line": {"color": "#DC2626", "width": 3},
                    "thickness": 0.85,
                    "value": sla_meta * 100,
                },
            },
            title={"text": f"Quebra vs. Meta {sla_meta:.0%}", "font": {"size": 14}},
        ))
        fig.update_layout(height=280, margin=dict(t=40, b=10, l=20, r=20))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("")
    render_section("🛡️ Folga de SLA")

    folga = Motor.folga_sla(df_seg, sla_meta)
    f1, f2, f3 = st.columns(3)
    cor_f = (
        "vermelho" if folga["estourado"]
        else ("verde" if folga["folga_ne_pendente"] > 0 else "laranja")
    )
    render_kpi(f1, "Folga (OS)",
               f"{int(np.floor(folga['folga_ne_pendente'])):,}",
               sub="Não Exec. ainda permitidas", tema=cor_f)
    render_kpi(f2, "Execução Mínima",
               f"{int(np.ceil(folga['precisa_executar_pendente'])):,}",
               sub="Pendentes a executar para atingir meta", tema="azul")
    render_kpi(f3, "Limite NE Total",
               f"{int(folga['limite_ne_total']):,}",
               sub=f"= {sla_meta:.0%} × {int(folga['alocado']):,}", tema="cinza")

    st.progress(min(1.0, max(0.0, float(m_seg["quebra_atual"] / (sla_meta * 2)))))


def _sub_causa_raiz(df_seg: pd.DataFrame) -> None:
    render_section(f"🔍 Causa Raiz — {TIPO}")
    df_c = Motor.causa_raiz_segmento(df_seg, TIPO, "_COL_BAIXA", top_n=8)

    if df_c.empty:
        render_insight(
            "Coluna de código/motivo de baixa não identificada. "
            "Verifique se a base contém 'CÓD DE BAIXA 1'.",
            tipo="alerta",
        )
        return

    c_tab, c_chart = st.columns([1.2, 2])
    with c_tab:
        render_dataframe(
            df_c, titulo=f"Top Motivos — {TIPO}", icone="🔍",
            fmt={"% do Total": "{:.2%}", "Acumulado": "{:.2%}"},
            height=350,
        )

    with c_chart:
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=df_c["Motivo de Baixa"], y=df_c["Volume"],
            name="Volume", marker_color="#0369A1",
            text=df_c["Volume"], textposition="outside",
        ))
        fig.add_trace(go.Scatter(
            x=df_c["Motivo de Baixa"], y=df_c["Acumulado"],
            name="Acumulado %", yaxis="y2",
            mode="lines+markers",
            line=dict(color="#0C4A6E", width=2),
            marker=dict(size=7),
        ))
        fig.update_layout(
            title=f"Pareto de Motivos — {TIPO}",
            yaxis=dict(title="Volume"),
            yaxis2=dict(
                title="Acumulado %", overlaying="y", side="right",
                tickformat=".0%", range=[0, 1.1],
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
            height=380,
            xaxis=dict(tickangle=-30),
        )
        fig.add_hline(
            y=0.8, line_dash="dot", line_color="#F59E0B",
            yref="y2", annotation_text="80%",
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


def _sub_tecnicos(
    df_seg: pd.DataFrame,
    p_base: float,
    min_aloc: float,
    top_n: int,
    sla_meta: float,
) -> None:
    render_section(f"👤 Técnicos com Maior Quebra — {TIPO}")
    df_tec = Motor.tecnicos_criticos(df_seg, TIPO, p_base, min_aloc, top_n)

    if df_tec.empty:
        render_insight("Não há técnicos com volume suficiente.", tipo="info")
        return

    render_dataframe(
        df_tec, titulo=f"Técnicos Críticos — {TIPO}", icone="🚨",
        fmt=FMT_QUEBRA, color_col="Fechamento Base",
        color_meta=sla_meta, color_invertido=True, height=450,
    )
    st.download_button(
        f"📥 Exportar Técnicos {TIPO}",
        Utils.gerar_excel(df_tec, f"Tec_{TIPO[:25]}"),
        f"tecnicos_{TIPO.lower()}.xlsx",
        key="dl_tec_mig",
    )

    df_plot = df_tec.head(10).sort_values("Fechamento Base")
    cores   = ["#EF4444" if v > sla_meta else "#10B981" for v in df_plot["Fechamento Base"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df_plot["TÉCNICO"], x=df_plot["Fechamento Base"],
        orientation="h", marker_color=cores,
        text=[f"{v:.1%}" for v in df_plot["Fechamento Base"]],
        textposition="outside",
    ))
    fig.add_vline(
        x=sla_meta, line_dash="dash", line_color="#DC2626",
        annotation_text=f"Meta {sla_meta:.0%}",
    )
    fig.update_layout(
        title=f"Quebra Projetada por Técnico — {TIPO}",
        xaxis_tickformat=".1%",
        height=max(300, len(df_plot) * 36),
        margin=dict(t=40, b=20, l=10, r=60),
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    acima = int((df_tec["Fechamento Base"] > sla_meta).sum())
    pct   = acima / len(df_tec) if len(df_tec) > 0 else 0
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
        render_insight(f"Todos os técnicos dentro da meta em {TIPO}. ✅", tipo="ok")


def _sub_plano_acao(
    df_seg: pd.DataFrame,
    p_base: float,
    sla_meta: float,
) -> None:
    render_section(f"🎯 Plano de Ação — {TIPO}")

    folga     = Motor.folga_sla(df_seg, sla_meta)
    cen       = Motor.projetar(df_seg, p_base)
    excesso   = max(0.0, folga["naoexec"] - folga["limite_ne_total"])
    pend_exec = folga["precisa_executar_pendente"]

    col_d, col_a = st.columns([1, 1.5])

    with col_d:
        render_section("📋 Diagnóstico")
        render_kpi_sm(
            st, "Excesso de NE", f"{int(excesso):,}",
            sub="OS além do permitido pela meta",
            tema="vermelho" if excesso > 0 else "verde",
        )
        render_kpi_sm(
            st, "Pendentes a Executar", f"{int(np.ceil(pend_exec)):,}",
            sub=f"Mínimo para meta {sla_meta:.0%}",
            tema="azul",
        )
        render_kpi_sm(
            st, "Proj. Base", f"{cen['fechamento_proj']:.2%}",
            sub=f"c/ {p_base:.0%} de quebra nos pendentes",
            tema="vermelho" if cen["fechamento_proj"] > sla_meta else "verde",
        )
        st.markdown("")
        if folga["pend"] > 0:
            tx = 1.0 - (folga["folga_ne_pendente"] / folga["pend"])
            st.markdown(f"**Taxa mínima de execução:** `{max(0.0, tx):.1%}`")
            st.progress(min(1.0, max(0.0, float(tx))))

    with col_a:
        render_section("✅ Ações Recomendadas")
        acoes: List[tuple] = []

        if folga["estourado"]:
            acoes.append((
                "🔴 IMEDIATA",
                f"Acionar plantão para recuperar {int(excesso):,} OS não executadas "
                f"acima do limite do SLA.",
                "critico",
            ))
        if pend_exec > 0:
            acoes.append((
                "🟠 ALTA",
                f"Garantir execução de pelo menos {int(np.ceil(pend_exec)):,} "
                f"OS pendentes de {TIPO} para atingir a meta de {sla_meta:.0%}.",
                "alerta",
            ))

        for pri, ac, tp in ACOES_MIGRACAO:
            acoes.append((f"🔵 {pri}", ac, tp))

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
            key="dl_plano_mig",
        )
        
def _sub_pendentes(df_seg: pd.DataFrame, sla_meta: float) -> None:
    """
    Exibe tabela de contratos pendentes com:
    Contrato · Login · Técnico · Monitor · Qtde. de O.S.
    + métricas rápidas + exportação Excel.
    """

    render_section(f"📋 Contratos Pendentes — {TIPO}")

    # ── Gera o DataFrame ────────────────────────────────────────────
    df_pend = _build_df_pendentes(df_seg)

    # ── Métricas rápidas ────────────────────────────────────────────
    total_pend = len(df_pend)

    m1, m2, m3 = st.columns(3)

    render_kpi(
        m1,
        "Total Pendentes",
        f"{total_pend:,}",
        sub="contratos sem execução",
        tema="laranja" if total_pend > 0 else "verde",
    )

    # Técnicos únicos com pendência
    tec_unicos = (
        df_pend["Técnico"]
        .replace("N/D", pd.NA)
        .dropna()
        .nunique()
    )
    render_kpi(
        m2,
        "Técnicos Envolvidos",
        f"{tec_unicos:,}",
        sub="com contrato pendente",
        tema="azul",
    )

    # Monitores únicos
    mon_unicos = (
        df_pend["Monitor"]
        .replace("N/D", pd.NA)
        .dropna()
        .nunique()
    )
    render_kpi(
        m3,
        "Monitores Envolvidos",
        f"{mon_unicos:,}",
        sub="supervisionando pendências",
        tema="cinza",
    )

    st.markdown("")

    if df_pend.empty:
        render_insight(
            "✅ Nenhum contrato pendente encontrado para os filtros atuais.",
            tipo="ok",
        )
        return

    # ── Filtros rápidos dentro da aba ───────────────────────────────
    with st.expander("🔎 Filtros rápidos na tabela de pendentes", expanded=False):
        fc1, fc2 = st.columns(2)

        with fc1:
            opts_tec = ["Todos"] + sorted(
                str(x)
                for x in df_pend["Técnico"].dropna().unique()
                if str(x) not in {"N/D", "nan"}
            )
            f_tec = st.selectbox(
                "Técnico", opts_tec, key="pend_f_tec"
            )

        with fc2:
            opts_mon = ["Todos"] + sorted(
                str(x)
                for x in df_pend["Monitor"].dropna().unique()
                if str(x) not in {"N/D", "nan"}
            )
            f_mon = st.selectbox(
                "Monitor", opts_mon, key="pend_f_mon"
            )

    # Aplica filtros rápidos
    df_view = df_pend.copy()
    if f_tec != "Todos":
        df_view = df_view[df_view["Técnico"] == f_tec]
    if f_mon != "Todos":
        df_view = df_view[df_view["Monitor"] == f_mon]

    # ── Exibição da tabela ──────────────────────────────────────────
    st.markdown(
        f"**Exibindo {len(df_view):,} de {total_pend:,} contratos pendentes**"
    )

    render_dataframe(
        df_view.reset_index(drop=True),
        titulo=f"Contratos Pendentes — {TIPO}",
        icone="📋",
        height=480,
    )

    # ── Gráficos auxiliares ─────────────────────────────────────────
    st.markdown("")
    render_section("📊 Distribuição das Pendências")
    
    df_top_mon = (
        df_view[df_view["Monitor"] != "N/D"]
        .groupby("Monitor")
        .size()
        .reset_index(name="Pendentes")
        .sort_values("Pendentes")
    )

    if not df_top_mon.empty:
        fig_mon = go.Figure(
            go.Bar(
                x=df_top_mon["Pendentes"],
                y=df_top_mon["Monitor"],
                orientation="h",
                marker_color="#7C3AED",
                text=df_top_mon["Pendentes"],
                textposition="outside",
            )
        )
        fig_mon.update_layout(
            title="Pendentes por Monitor",
            xaxis_title="Contratos Pendentes",
            yaxis=dict(autorange="reversed"),
            height=max(300, len(df_top_mon) * 38),
            margin=dict(l=10, r=30, t=40, b=10),
        )
        st.plotly_chart(
            fig_mon,
            use_container_width=True,
            config={"displayModeBar": False},
        )
    else:
        st.info("Sem dados de monitor para exibir.")

    # ── Exportação ──────────────────────────────────────────────────
    st.markdown("")
    col_exp1, col_exp2, _ = st.columns([1, 1, 2])

    with col_exp1:
        st.download_button(
            label="📥 Exportar Pendentes (filtrado)",
            data=Utils.gerar_excel(
                df_view.reset_index(drop=True),
                f"Pendentes_{TIPO[:20]}_filtrado",
            ),
            file_name=(
                f"pendentes_pme_filtrado_"
                f"{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            ),
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
            key="dl_pend_pme_filtrado",
        )

    with col_exp2:
        st.download_button(
            label="📥 Exportar Pendentes (completo)",
            data=Utils.gerar_excel(
                df_pend.reset_index(drop=True),
                f"Pendentes_{TIPO[:20]}_completo",
            ),
            file_name=(
                f"pendentes_pme_completo_"
                f"{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
            ),
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
            key="dl_pend_pme_completo",
        )

# ====================================================
# APLICAÇÃO PRINCIPAL
# ====================================================
def main() -> None:
    aplicar_estilo()

    st.markdown(
        '<div class="hero" style="background:linear-gradient(135deg,#0C4A6E 0%,#0369A1 100%);">'
        "<h1>🔄 Migração — Quebra de Agenda</h1>"
        "<p>Análise estratégica de Mudança de Pacote + GPON</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.get("df_memoria") is None:
        st.warning("⚠️ Nenhuma base carregada.")
        st.info("👈 Volte ao **Dashboard Geral** no menu lateral e faça o upload.")
        return

    df_full: pd.DataFrame = st.session_state["df_memoria"].copy()
    if "Status Contrato" not in df_full.columns:
        col_s = Utils.buscar_coluna(df_full, ["STATUS DA O.S 1", "STATUS OS 1"])
        df_full["Status Contrato"] = (
            Utils.classificar_status(df_full[col_s]) if col_s else "Pendente"
        )

    # ── Sidebar ─────────────────────────────────────────────────────
    with st.sidebar:
        st.header("🎯 Filtros Migração")

        monitores = ["Todos"] + sorted(
            str(x) for x in df_full["MONITOR"].dropna().unique()
            if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
        )
        sel_mon  = st.selectbox("👔 Monitor", monitores, key="mon_mig")
        df_filt  = df_full if sel_mon == "Todos" else df_full[df_full["MONITOR"] == sel_mon]

        tecnicos = ["Todos"] + sorted(
            str(x) for x in df_filt["TÉCNICO"].dropna().unique()
            if str(x) not in {"nan", "NÃO MAPEADO"}
        )
        sel_tec = st.selectbox("👤 Técnico", tecnicos, key="tec_mig")
        df      = df_filt if sel_tec == "Todos" else df_filt[df_filt["TÉCNICO"] == sel_tec]

        st.divider()
        st.subheader("🔮 Probabilidades")
        p_ot   = st.slider("Otimista (%)",   0, 100, 15, 5, key="pot_mig")   / 100.0
        p_base = st.slider("Base (%)",        0, 100, 25, 5, key="pbase_mig") / 100.0
        p_pess = st.slider("Pessimista (%)", 0, 100, 50, 5, key="ppess_mig") / 100.0

        st.divider()
        sla_meta = (
            st.number_input(
                "Meta SLA Migração (%)", 0.0, 100.0,
                float(SLA_DEFAULT * 100), 0.5, key="sla_mig_v",
            )
            / 100.0
        )

        min_aloc: float = 1.0
        top_n: int      = 999_999

    # ── Validações ──────────────────────────────────────────────────
    if df.empty:
        st.warning("Nenhum dado para os filtros selecionados.")
        return

    render_resultado_base(sorted(df[Config.COL_REGIAO].unique()), len(df))

    df_seg = df[df["TIPO_SERVICO"] == TIPO].copy()
    if df_seg.empty:
        st.info(f"⚠️ Nenhum registro classificado como {TIPO} nos filtros atuais.")
        return

    m_seg = Motor.projetar(df_seg, p_base)
    render_segmento_header(TIPO, m_seg["quebra_atual"], sla_meta)
    render_alerta_sla(m_seg["quebra_atual"], sla_meta, TIPO)
    st.markdown("")

    # ── Botão PDF ────────────────────────────────────────────────────
    col_btn, col_desc = st.columns([1, 3])
    with col_btn:
        with st.spinner("Gerando PDF..."):
            pdf_bytes = PDFExecutivoMigracao.gerar(
                df       = df,
                sla_meta = sla_meta,
                p_ot     = p_ot,
                p_base   = p_base,
                p_pess   = p_pess,
                min_aloc = min_aloc,
                top_n    = min(top_n, 15),
            )
        st.download_button(
            label               = "📄 Baixar PDF Executivo Migração",
            data                = pdf_bytes,
            file_name           = f"relatorio_migracao_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
            mime                = "application/pdf",
            key                 = "pdf_mig_dl",
            use_container_width = True,
            type                = "primary",
        )

    with col_desc:
        st.info(
            "**Conteúdo do PDF:**  \n"
            "Capa com KPIs executivos · Cenários Otimista / Base / Pessimista "
            "· Plano de ação com coloração por prioridade · Top 15 Técnicos Críticos "
            "· Performance Regional · Pareto de Causas · Ranking de Monitores"
        )

    st.divider()

    # ── Sub-abas ─────────────────────────────────────────────────────
    sub1, sub2, sub3, sub4, sub5 = st.tabs(
        ["📊 Visão Geral", "🔍 Causa Raiz", "👤 Técnicos", "🎯 Plano de Ação", "📋 Pendentes"]
    )
    with sub1:
        _sub_visao_geral(df_seg, m_seg, p_ot, p_base, p_pess, sla_meta)
    with sub2:
        _sub_causa_raiz(df_seg)
    with sub3:
        _sub_tecnicos(df_seg, p_base, min_aloc, top_n, sla_meta)
    with sub4:
        _sub_plano_acao(df_seg, p_base, sla_meta)
    with sub5:
        _sub_pendentes(df_seg, sla_meta)


# ====================================================
# ENTRY POINT
# ====================================================
if __name__ == "__main__":
    main()