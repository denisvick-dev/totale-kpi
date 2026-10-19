# rota_inicial.py

from __future__ import annotations

from io import BytesIO
from typing import Any, Literal

import pandas as pd
import streamlit as st
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

# ── Componentes corporativos ──────────────────────────────────────────────────
from components.componentes import (
    aplicar_estilo,
    estilizar_dataframe,
    render_hero,
    render_insight,
    render_kpi,
    render_section_header,
)
from components.upload_base import (
    limpar_bases_operacionais,
    render_status_upload,
    render_upload_base_operacional,
)

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

if "_reset_counter" not in st.session_state:
    st.session_state["_reset_counter"] = 0

# ====================================================
# 2. CONFIGURAÇÕES GLOBAIS
# ====================================================
CORES_REGIAO = {
    "LESTE": {"bg": "#DBEAFE", "text": "#1E40AF", "border": "#3B82F6"},
    "GRU": {"bg": "#D1FAE5", "text": "#065F46", "border": "#10B981"},
    "ABCDM": {"bg": "#EDE9FE", "text": "#5B21B6", "border": "#8B5CF6"},
    "OUTRAS": {"bg": "#F1F5F9", "text": "#475569", "border": "#94A3B8"},
}

RENOMEAR_COLUNAS: dict[str, str] = {
    "Monitor": "Monitor",
    "OS": "Volume de O.S.",
    "GPON": "GPON",
    "ND": "Adesão",
    "PME": "PME",
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
# 3. CSS LOCAL
# ====================================================
def _injetar_css_local() -> None:
    st.markdown(
        """
        <style>
        /* ── Resultado da Base ── */
        .resultado-base {
            background: linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);
            padding: 1rem 1.5rem; border-radius: 0.75rem;
            margin-bottom: 1.5rem; display: flex; align-items: center;
            flex-wrap: wrap; gap: 0.6rem;
            box-shadow: 0 6px 20px rgba(1,40,105,0.20);
            position: relative; overflow: hidden;
        }
        .resultado-base::before {
            content:''; position:absolute; top:-50%; right:-5%;
            width:250px; height:250px;
            background:rgba(255,255,255,0.05); border-radius:50%;
            pointer-events:none;
        }
        .resultado-base-label {
            color:#FFFFFF; font-size:0.8rem; font-weight:700;
            text-transform:uppercase; letter-spacing:0.08em;
            margin-right:0.3rem; position:relative; z-index:2;
        }
        .resultado-base-regiao {
            padding:0.35rem 0.95rem; border-radius:999px;
            font-size:0.82rem; font-weight:700; letter-spacing:0.04em;
            border:2px solid rgba(255,255,255,0.4);
            position:relative; z-index:2;
        }
        .resultado-base-count {
            color:#FFFFFF; font-size:0.78rem; margin-left:auto;
            font-weight:700; position:relative; z-index:2;
        }

        /* ── Tabelas Rota/Turno (Visual Corporativo TOTALE) ── */
        .rota-wrapper {
            margin: 22px 0;
            box-shadow: 0 8px 24px rgba(10, 47, 107, 0.08);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #DCE5F0;
            background: #FFFFFF;
        }
        .rota-titulo {
            background: linear-gradient(115deg, #092452 0%, #0A2F6B 65%, #164583 100%);
            color: #FFFFFF;
            font-weight: 800;
            font-size: 13.5px;
            text-align: left;
            padding: 13px 20px;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            border-bottom: 3px solid #E8700A;
        }
        table.rota-tab {
            width: 100%; border-collapse: separate; border-spacing: 0;
            background: white; font-size: 13px;
        }
        table.rota-tab th {
            background: #0F2547; color: #F8FAFC;
            font-weight: 700; font-size: 11px;
            text-transform: uppercase; letter-spacing: 0.05em;
            padding: 11px 14px; text-align: center;
            border-bottom: 1px solid #1E3A6D;
        }
        table.rota-tab th.th-os     { background: #3B2106; color: #FDBA74; }
        table.rota-tab th.th-equipe { background: #064E3B; color: #6EE7B7; }
        table.rota-tab th.th-media  { background: #1E3A8A; color: #93C5FD; }
        table.rota-tab td {
            padding: 10px 14px; text-align: center;
            border-bottom: 1px solid #EEF2F6;
            color: #1E293B; font-variant-numeric: tabular-nums;
        }
        table.rota-tab td.col-monitor {
            text-align: left; font-weight: 700; padding-left: 20px; color: #0A2F6B;
        }
        table.rota-tab td.col-os {
            background: #FFF7ED; font-weight: 700; color: #9A3412;
            border-left: 1px solid #FFEDD5; border-right: 1px solid #FFEDD5;
        }
        table.rota-tab td.col-equipe {
            background: #ECFDF5; font-weight: 700; color: #065F46;
            border-left: 1px solid #D1FAE5; border-right: 1px solid #D1FAE5;
        }
        table.rota-tab td.col-media {
            background: #F8FAFC; font-weight: 700; color: #0A2F6B;
        }
        table.rota-tab tr.total-escalados td {
            background: #EAF2FC; color: #0A2F6B; font-weight: 700; font-size: 13px;
            border-top: 2px solid #0A2F6B; border-bottom: 1px solid #C8DCF5;
        }
        table.rota-tab tr.total-escalados td.col-os     { background: #FEF3C7; color: #92400E; }
        table.rota-tab tr.total-escalados td.col-equipe { background: #D1FAE5; color: #065F46; }
        table.rota-tab tr.total-escalados td.col-media  { background: #DBEAFE; color: #0A2F6B; }
        table.rota-tab tr.total-montados td {
            background: #DCE8F8; color: #092452; font-weight: 800; font-size: 13px;
            border-bottom: none;
        }
        table.rota-tab tr.total-montados td.col-os     { background: #FDE68A; color: #78350F; }
        table.rota-tab tr.total-montados td.col-equipe { background: #A7F3D0; color: #064E3B; }
        table.rota-tab tr.total-montados td.col-media  { background: #BFDBFE; color: #092452; }
        table.rota-tab tbody tr:nth-child(even):not(.total-escalados):not(.total-montados) td
            { background: #F8FAFC; }
        table.rota-tab tbody tr:nth-child(even):not(.total-escalados):not(.total-montados) td.col-os
            { background: #FFFBEB; }
        table.rota-tab tbody tr:nth-child(even):not(.total-escalados):not(.total-montados) td.col-equipe
            { background: #F0FDF4; }
        table.rota-tab tbody tr:hover:not(.total-escalados):not(.total-montados) td
            { background: #EFF6FF; }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ====================================================
# 4. COMPONENTES LOCAIS
# ====================================================
def render_resultado_base(regioes: list[str], total: int) -> None:
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


def render_dataframe_local(
    df: pd.DataFrame,
    titulo: str = "",
    icone: str = "📊",
    badge: str = "",
    fmt: dict[str, Any] | None = None,
    color_col: str | None = None,
    color_meta: float | None = None,
    color_invertido: bool = False,
    height: int | Literal["auto", "stretch", "content"] = "auto",
) -> None:
    badge_text = badge or f"{len(df)} registros"
    render_section_header(icone, titulo, badge_text)

    df_display = df.copy()
    colunas_para_renomear: dict[str, str] = {}
    nomes_existentes = set(df_display.columns)
    nomes_ja_usados: set[str] = set()

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
        "PME",
        "Migração",
        "Qtd_4K",
        "Ultra",
        "Soundbox",
        "Equipe",
        "TOTAL_TAREFAS",
    ]
    for c in [colunas_para_renomear.get(c, c) for c in colunas_int_originais]:
        if c in df_display.columns:
            df_display[c] = (
                pd.to_numeric(df_display[c], errors="coerce").fillna(0).astype(int)
            )

    styler = estilizar_dataframe(df_display, fmt)

    if color_col and color_col in df_display.columns and color_meta is not None:

        def _cor(val: Any) -> str:
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

        styler = styler.map(_cor, subset=pd.Index([color_col]))

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


# A leitura e o tratamento da base vivem em components/base_operacional
# (preparar_base_rota_inicial); o envio usa components/upload_base.


# ====================================================
# 5. TABELAS ROTA/TURNO
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
    turno: str | None = None,
    total_equipe_montada: int | None = None,
) -> pd.DataFrame:
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

    linhas: list[dict[str, Any]] = []
    for mon in sorted(df_work["Monitor"].unique()):
        df_mon = df_work[df_work["Monitor"] == mon]
        total_os = int(df_mon["TOTAL_TAREFAS"].sum())
        equipe = int(df_mon["LOGIN_TECNICO"].nunique())
        linhas.append(
            {
                "Monitor": mon,
                "WO": int(df_mon["Check_ND"].sum()),
                "GPON": int(df_mon["Check_GPON"].sum()),
                "OS": total_os,
                "ND": int(df_mon["Check_ND"].sum()),
                "Migração": int(df_mon["Check_Migracao"].sum()),
                "Equipe": equipe,
                "Média": total_os / equipe if equipe > 0 else 0.0,
            }
        )

    df_out = pd.DataFrame(linhas)
    total_os_g = int(df_out["OS"].sum())
    total_eq_escalados = int(df_out["Equipe"].sum())
    total_eq_montados = (
        total_equipe_montada
        if total_equipe_montada is not None
        else int(df_work["LOGIN_TECNICO"].nunique())
    )

    df_out = pd.concat(
        [
            df_out,
            pd.DataFrame(
                [
                    {
                        "Monitor": "Total Geral | Escalados",
                        "WO": int(df_out["WO"].sum()),
                        "GPON": int(df_out["GPON"].sum()),
                        "OS": total_os_g,
                        "ND": int(df_out["ND"].sum()),
                        "Migração": int(df_out["Migração"].sum()),
                        "Equipe": total_eq_escalados,
                        "Média": total_os_g / total_eq_escalados
                        if total_eq_escalados
                        else 0.0,
                    },
                    {
                        "Monitor": "Total Geral | Montados",
                        "WO": int(df_out["WO"].sum()),
                        "GPON": int(df_out["GPON"].sum()),
                        "OS": total_os_g,
                        "ND": int(df_out["ND"].sum()),
                        "Migração": int(df_out["Migração"].sum()),
                        "Equipe": total_eq_montados,
                        "Média": total_os_g / total_eq_montados
                        if total_eq_montados
                        else 0.0,
                    },
                ]
            ),
        ],
        ignore_index=True,
    )

    return df_out


def render_tabela_rota_turno(df: pd.DataFrame, titulo: str) -> str:
    if df.empty:
        return (
            f'<div class="rota-wrapper"><div class="rota-titulo">{titulo}</div>'
            f'<table class="rota-tab"><tr>'
            f'<td colspan="8" style="padding:20px;color:#64748B;text-align:center;">'
            f"Sem dados disponíveis</td></tr></table></div>"
        )

    linhas_html: list[str] = []
    for _, row in df.iterrows():
        monitor = str(row["Monitor"])
        classe = (
            "total-escalados"
            if "Escalados" in monitor
            else "total-montados"
            if "Montados" in monitor
            else ""
        )
        linhas_html.append(
            f'<tr class="{classe}">'
            f'<td class="col-monitor">{monitor}</td>'
            f"<td>{_fmt_num_br(row['WO'])}</td>"
            f"<td>{_fmt_num_br(row['GPON'])}</td>"
            f'<td class="col-os">{_fmt_num_br(row["OS"])}</td>'
            f"<td>{_fmt_num_br(row['ND'])}</td>"
            f"<td>{_fmt_num_br(row['Migração'])}</td>"
            f'<td class="col-equipe">{_fmt_num_br(row["Equipe"])}</td>'
            f'<td class="col-media">{_fmt_media_br(row["Média"])}</td>'
            f"</tr>"
        )

    return (
        f'<div class="rota-wrapper">'
        f'<div class="rota-titulo">{titulo}</div>'
        f'<table class="rota-tab"><thead><tr>'
        f'<th style="width:32%;">Monitor</th>'
        f"<th>WO</th><th>GPON</th>"
        f'<th class="th-os">OS</th>'
        f"<th>ND</th><th>Migração</th>"
        f'<th class="th-equipe">Equipe</th>'
        f'<th class="th-media">Média</th>'
        f"</tr></thead>"
        f"<tbody>{''.join(linhas_html)}</tbody>"
        f"</table></div>"
    )


def render_bloco_rota_turno(df_master: pd.DataFrame, total_montados: int) -> None:
    from datetime import datetime

    data_hoje = datetime.now().strftime("%d/%m/%Y")
    total_efetivo = (
        total_montados
        if total_montados > 0
        else int(df_master["LOGIN_TECNICO"].nunique())
    )
    for turno, label in [
        (None, f"Rota Inicial — {data_hoje}"),
        ("Manhã", f"Manhã — {data_hoje}"),
        ("Tarde I", f"Tarde I — {data_hoje}"),
        ("Tarde II", f"Tarde II — {data_hoje}"),
    ]:
        df_t = calcular_tabela_rota_turno(
            df_master, turno=turno, total_equipe_montada=total_efetivo
        )
        st.markdown(render_tabela_rota_turno(df_t, label), unsafe_allow_html=True)


# ====================================================
# 6. APLICAÇÃO PRINCIPAL
# ====================================================
def main() -> None:
    aplicar_estilo()
    _injetar_css_local()

    render_hero(
        titulo="🗺️ Gestão de Rota Inicial",
        subtitulo="Visão operacional de rotas, serviços premium e distribuição de equipes",
    )

    # ── Sidebar — base de dados ──────────────────────
    with st.sidebar:
        st.header("⚙️ Base de dados")
        render_status_upload()
        if st.button(
            "📁 Trocar base",
            use_container_width=True,
            help=(
                "Limpa as bases operacionais da sessão e volta ao envio "
                "manual. Vale para Quebra, Volumetria e Rota Inicial, "
                "que compartilham o mesmo arquivo."
            ),
        ):
            limpar_bases_operacionais()
            st.session_state.pop("sim_equipe", None)
            st.session_state["total_montados_manual"] = 0
            st.session_state["_reset_counter"] = (
                int(st.session_state.get("_reset_counter", 0)) + 1
            )
            st.rerun()
        st.divider()

    reset_key = int(st.session_state.get("_reset_counter", 0))

    # ── Upload manual ────────────────────────────────
    if st.session_state["df_master"] is None:
        render_upload_base_operacional(
            "rota_inicial",
            titulo="Importação de Dados",
            recarregar_apos_envio=True,
        )
        return

    df_master = st.session_state["df_master"].copy()

    # ── Sidebar — equipe + filtros ───────────────────
    with st.sidebar:
        st.header("👥 Equipe Montada")
        total_montados_input = st.number_input(
            "Total de Técnicos Montados",
            min_value=0,
            max_value=999,
            value=st.session_state["total_montados_manual"],
            step=1,
            help="Deixe em 0 para usar a contagem automática da base.",
            key=f"input_total_montados_{reset_key}",
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
            "⏰ Período",
            ["Todos"] + sorted(df_master["PERIODO_TRATADO"].unique()),
            key=f"filtro_periodo_{reset_key}",
        )
        if periodos != "Todos":
            df_master = df_master[df_master["PERIODO_TRATADO"] == periodos]

        st.divider()
        st.subheader("🎛️ Filtros Premium")

        if st.checkbox("🟢 Apenas Adesão (ND)", key=f"chk_nd_{reset_key}"):
            df_master = df_master[df_master["Check_ND"]]

        if st.checkbox(
            "🏢 Apenas PME (Empresarial)",
            help="Adesões (ND) cuja habilidade contém 'PME'.",
            key=f"chk_pme_{reset_key}",
        ):
            df_master = df_master[df_master["Check_PME"]]

        if st.checkbox("🔄 Apenas Migração (MP GPON)", key=f"chk_mig_{reset_key}"):
            df_master = df_master[df_master["Check_Migracao"]]

        if st.checkbox("📡 Requer GPON", key=f"chk_gpon_{reset_key}"):
            df_master = df_master[df_master["Check_GPON"]]

        if st.checkbox("📺 Requer Streaming", key=f"chk_stream_{reset_key}"):
            df_master = df_master[df_master["Check_Streaming"]]

        if st.checkbox("📺 Requer 4K", key=f"chk_4k_{reset_key}"):
            df_master = df_master[df_master["Check_4K"]]

        if st.checkbox("🔌 Requer Ponto Ultra", key=f"chk_ultra_{reset_key}"):
            df_master = df_master[df_master["Check_Ponto_Ultra"]]

        if st.checkbox("🔊 Requer Soundbox", key=f"chk_sound_{reset_key}"):
            df_master = df_master[df_master["Check_Soundbox"]]

    # ── Guard ────────────────────────────────────────
    if df_master.empty:
        render_insight("Nenhum dado para os filtros selecionados.", tipo="alerta")
        return

    # ── Resultado da base ────────────────────────────
    regioes = (
        sorted(df_master["REGIÃO"].unique()) if "REGIÃO" in df_master.columns else []
    )
    render_resultado_base(regioes, len(df_master))

    # ── KPIs Principais ─────────────────────────────
    soma_os = int(df_master["TOTAL_TAREFAS"].sum())
    tecnicos = df_master["LOGIN_TECNICO"].nunique()
    monitores_qtd = df_master["Monitor"].nunique()

    render_section_header("📊", "Indicadores Operacionais")
    c1, c2, c3 = st.columns(3)
    render_kpi(c1, "Volume O.S.", f"{soma_os:,}", tema="azul")
    render_kpi(
        c2,
        "Técnicos Operando",
        f"{tecnicos}",
        sub=f"Média: {soma_os / tecnicos:.1f} O.S./Téc." if tecnicos else "",
        tema="cinza",
    )
    render_kpi(c3, "Monitores", f"{monitores_qtd}", tema="azul")

    st.markdown("")

    # ── KPIs Secundários ────────────────────────────
    qtd_gpon = int(df_master["Check_GPON"].sum())
    qtd_nd = int(df_master["Check_ND"].sum())
    qtd_pme = int(df_master["Check_PME"].sum())
    qtd_4k = int(df_master["Check_4K"].sum())
    qtd_sound = int(df_master["Check_Soundbox"].sum())

    s1, s2, s3, s4, s5 = st.columns(5)
    render_kpi(s1, "GPON", f"{qtd_gpon:,}", tema="verde")
    render_kpi(s2, "Adesão (ND)", f"{qtd_nd:,}", tema="azul")
    render_kpi(
        s3,
        "PME",
        f"{qtd_pme:,}",
        sub=f"{qtd_pme / qtd_nd:.1%} das ND" if qtd_nd > 0 else "sem ND",
        tema="azul",
    )
    render_kpi(s4, "4K", f"{qtd_4k:,}", tema="laranja")
    render_kpi(s5, "Soundbox", f"{qtd_sound:,}", tema="cinza")

    st.markdown("")

    # ── Tabelas Rota / Turnos ────────────────────────
    render_section_header("🗺️", "Distribuição por Monitor e Turno")
    render_bloco_rota_turno(df_master, st.session_state["total_montados_manual"])

    # ── Abas de Detalhamento ─────────────────────────
    aba_base, aba_contratos = st.tabs(["🗃️ Base Completa", "📄 Resumo Contratos"])

    # ============================================================
    # ABA — BASE COMPLETA
    # ============================================================
    with aba_base:
        render_dataframe_local(
            df_master.head(500),
            titulo="Base de Dados (prévia — 500 linhas)",
            icone="🗃️",
            badge=f"{len(df_master)} total",
            height="auto",
        )
        st.download_button(
            "📥 Baixar Base Completa",
            gerar_excel(df_master, "Base"),
            "base_completa.xlsx",
        )

    # ============================================================
    # ABA — RESUMO CONTRATOS
    # ============================================================
    with aba_contratos:
        render_section_header("📄", "Resumo dos Contratos da Rota")

        COLUNAS_CONTRATOS: dict[str, list[str]] = {
            "CONTRATO": ["CONTRATO"],
            "INTERVALO": ["PERIODO_TRATADO", "INTERVALO"],
            "CEP": ["CEP/CÓDIGO POSTAL", "CEP", "CODIGO POSTAL"],
            "ÁREA TRABALHO": ["ÁREA DE TRABALHO", "AREA DE TRABALHO"],
            "TIPO OS": ["TIPO_OS", "TIPO O.S 1", "TIPO OS 1"],
            "TÉCNICO": ["NOME_OFICIAL"],
            "MONITOR": ["Monitor"],
        }

        colunas_encontradas: dict[str, str] = {}
        for nome_amigavel, aliases in COLUNAS_CONTRATOS.items():
            for alias in aliases:
                if alias in df_master.columns:
                    colunas_encontradas[alias] = nome_amigavel
                    break

        if not colunas_encontradas:
            render_insight(
                "Nenhuma das colunas esperadas foi encontrada na base.", tipo="alerta"
            )
        else:
            df_contratos = (
                df_master[list(colunas_encontradas.keys())]
                .rename(columns=colunas_encontradas)
                .copy()
            )

            col_f1, col_f2, col_info = st.columns([2, 2, 3])

            with col_f1:
                mon_contratos = ["Todos"] + sorted(
                    str(x)
                    for x in df_contratos.get("MONITOR", pd.Series()).dropna().unique()
                    if str(x) not in {"nan", "SEM MONITOR", "NÃO MAPEADO"}
                )
                sel_mon = st.selectbox(
                    "👔 Monitor",
                    mon_contratos,
                    key=f"filtro_mon_contratos_{reset_key}",
                )

            df_cf = (
                df_contratos[df_contratos["MONITOR"] == sel_mon].copy()
                if sel_mon != "Todos"
                else df_contratos.copy()
            )

            with col_f2:
                tec_contratos = ["Todos"] + sorted(
                    str(x)
                    for x in df_cf.get("TÉCNICO", pd.Series()).dropna().unique()
                    if str(x) not in {"nan", "NÃO MAPEADO"}
                )
                sel_tec = st.selectbox(
                    "👤 Técnico",
                    tec_contratos,
                    key=f"filtro_tec_contratos_{reset_key}",
                )

            if sel_tec != "Todos":
                df_cf = df_cf[df_cf["TÉCNICO"] == sel_tec].copy()

            with col_info:
                st.markdown("")
                st.markdown(
                    f"**{len(df_cf):,}** contratos exibidos de **{len(df_contratos):,}** total"
                )

            render_dataframe_local(
                df_cf,
                titulo="Resumo Contratos",
                icone="📄",
                badge=f"{len(df_cf)} contratos",
                height="auto",
            )
            st.download_button(
                "📥 Baixar Resumo Contratos",
                gerar_excel(df_cf, "Resumo Contratos"),
                "resumo_contratos.xlsx",
            )


if __name__ == "__main__":
    main()
