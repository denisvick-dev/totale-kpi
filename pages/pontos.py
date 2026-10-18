import datetime
from io import BytesIO
from typing import Any

import pandas as pd
import streamlit as st
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from components.calendario import InfoCalendario
from components.componentes import (
    COR_TEXTO_3,
    FONTE_TEXTO,
    aplicar_estilo,
    estilizar_dataframe,
    render_hero,
    render_insight,
    render_kpi,
    render_section_header,
)

# ⚠️ set_page_config DEVE ser a primeira chamada Streamlit
st.set_page_config(
    page_title="Central de Performance",
    page_icon="📈",
    layout="wide",
)

# Aplica CSS/tema/fontes ANTES de qualquer outro st.*
aplicar_estilo()


# ====================================================
# BLOCO 2: COMPONENTES VISUAIS
# ====================================================
class ComponenteVisual:
    @staticmethod
    def gerar_insight_ia(media: float, dias_brutos: int) -> None:
        dias_txt = (
            f"Restam {dias_brutos} dia(s) útil(is) para o fechamento. "
            if dias_brutos > 0
            else "Último dia do período. "
        )
        if media >= 400:
            render_insight(
                f"**Visão da IA:** Operação em Alta Performance! "
                f"A média de {media:.1f} pts/equipe ultrapassa o teto máximo. "
                f"{dias_txt}Mantenha o ritmo para fechar o mês com recorde.",
                tipo="ok",
            )
        elif media >= 300:
            render_insight(
                f"**Visão da IA:** Operação Estável. "
                f"Média de {media:.1f} pts garante o atingimento da meta base. "
                f"{dias_txt}Foco em puxar os retardatários para garantir a projeção.",
                tipo="info",
            )
        else:
            render_insight(
                f"**Visão da IA:** Alerta de Performance! "
                f"A média de {media:.1f} pts está abaixo da linha de corte (300). "
                f"{dias_txt}Ação imediata necessária para reverter a tendência.",
                tipo="alerta",
            )

    @staticmethod
    def render_dataframe_corporativo(
        df: pd.DataFrame,
        titulo: str = "",
        icone: str = "📊",
        badge: str = "",
        modo_diario: bool = False,
    ) -> None:
        if df.empty:
            render_insight("Nenhum dado disponível.", tipo="info")
            return

        badge_txt = badge or f"{len(df)} equipes"
        modo_txt = "Meta Diária" if modo_diario else "Acumulado do Mês"
        render_section_header(icone, titulo, f"{modo_txt} · {badge_txt}")

        df_display = df.copy()
        renomear = {
            "Posição": "Rank",
            "CódAuxEquipe": "Cód. Equipe",
            "Nome Equipe": "Equipe",
            "Supervisor": "Supervisor",
            "Projeto": "Projeto",
            "Pontos": "Pontos",
            "Projeção": "Proj. Fechamento",
        }
        df_display = df_display.rename(
            columns={k: v for k, v in renomear.items() if k in df_display.columns}
        )

        if "Rank" in df_display.columns:
            df_display["Rank"] = df_display["Rank"].apply(Utilitarios.formatar_posicao)

        cols_meta = [c for c in df_display.columns if "Meta" in c]
        formatos: dict[str, Any] = {c: "{:+,.1f}" for c in cols_meta}
        if "Pontos" in df_display.columns:
            formatos["Pontos"] = "{:,.1f}"
        if "Proj. Fechamento" in df_display.columns:
            formatos["Proj. Fechamento"] = "{:,.1f}"

        styler = estilizar_dataframe(df_display, formatos)

        if cols_meta:
            styler = styler.map(Utilitarios.colorir_delta_meta, subset=cols_meta)  # type: ignore[arg-type]
        if "Pontos" in df_display.columns:
            styler = styler.map(Utilitarios.colorir_metas, subset=["Pontos"])  # type: ignore[arg-type]
        if "Proj. Fechamento" in df_display.columns:
            styler = styler.map(
                Utilitarios.colorir_projecao, subset=["Proj. Fechamento"]
            )  # type: ignore[arg-type]

        st.dataframe(styler, use_container_width=True, hide_index=True, height=450)


# ====================================================
# BLOCO 3: UTILITÁRIOS
# ====================================================
class Utilitarios:
    @staticmethod
    def encontrar_coluna_data(df: pd.DataFrame) -> str | None:
        for c in [
            "Data Agendamento",
            "Data Conclusão",
            "Data",
            "Date",
            "Data_Execucao",
        ]:
            if c in df.columns:
                return c
        return None

    @staticmethod
    def calcular_variacao(vf: float, vg: float) -> tuple[str, str]:
        if vg == 0 or pd.isna(vg):
            return "neutra", "S/D"
        if abs(vf - vg) < 0.0001:
            return "neutra", "Visão Geral"
        p = ((vf - vg) / vg) * 100
        if p > 0:
            return "positiva", f"+{p:.1f}%"
        if p < 0:
            return "negativa", f"{p:.1f}%"
        return "neutra", "0%"

    @staticmethod
    def calcular_share(vf: float, vg: float) -> tuple[str, str]:
        if vg == 0 or pd.isna(vg):
            return "neutra", "0%"
        if abs(vf - vg) < 0.0001:
            return "neutra", "Visão Geral"
        return "share", f"{(vf / vg) * 100:.1f}% do Total"

    @staticmethod
    def formatar_numero(v: float) -> str:
        return f"{v:,.0f}".replace(",", ".")

    @staticmethod
    def formatar_posicao(valor: Any) -> str:
        try:
            v = int(valor)
            return {1: f"🥇 {v}º", 2: f"🥈 {v}º", 3: f"🥉 {v}º"}.get(v, f"{v}º")
        except (ValueError, TypeError):
            return str(valor)

    @staticmethod
    def colorir_metas(valor: Any) -> str:
        try:
            v = float(valor)
        except (ValueError, TypeError):
            return ""
        if v >= 400:
            return (
                "background-color:#1E3A8A;color:#FFFFFF;font-weight:800;"
                "border-left:3px solid #0F172A;text-align:center;"
            )
        if v >= 300:
            return (
                "background-color:#DCFCE7;color:#166534;font-weight:700;"
                "border-left:3px solid #22C55E;text-align:center;"
            )
        if v >= 275:
            return (
                "background-color:#FEF9C3;color:#854D0E;font-weight:700;"
                "border-left:3px solid #EAB308;text-align:center;"
            )
        return (
            "background-color:#FEF2F2;color:#991B1B;font-weight:700;"
            "border-left:3px solid #EF4444;text-align:center;"
        )

    @staticmethod
    def colorir_delta_meta(valor: Any) -> str:
        try:
            v = float(valor)
        except (ValueError, TypeError):
            return ""
        if v >= 0:
            return (
                "background-color:#ECFDF5;color:#065F46;font-weight:700;"
                "text-align:center;"
            )
        return "color:#B4232E;font-weight:600;text-align:center;"

    @staticmethod
    def colorir_projecao(valor: Any) -> str:
        return (
            "background-color:#0A2F6B;color:#FFFFFF;font-weight:800;"
            "text-align:center;border-left:3px solid #E8700A;"
        )

    @staticmethod
    def calcular_dias_uteis(df: pd.DataFrame) -> tuple[int, int, Any, int]:
        """
        Dias úteis do mês de referência.

        Segunda a sábado, **sem domingos e sem feriados**
        (``components.calendario`` — mesma regra das projeções).
        """
        col_data = Utilitarios.encontrar_coluna_data(df)
        data_max: datetime.date = (
            pd.to_datetime(df[col_data].max()).date()
            if col_data and pd.notna(df[col_data].max())
            else datetime.date.today()
        )

        calendario = InfoCalendario.calcular(data_max)
        brutos = max(0, calendario.dias_faltantes)
        seguros = max(1, brutos)
        return brutos, seguros, data_max, calendario.dias_passados

    @staticmethod
    def exportar_excel(dataframe: pd.DataFrame) -> bytes:
        output = BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            dataframe.to_excel(writer, index=False, sheet_name="Ranking")
            ws = writer.sheets["Ranking"]

            cor_cab = PatternFill("solid", fgColor="012869")
            cor_par = PatternFill("solid", fgColor="F8FAFC")
            cor_impar = PatternFill("solid", fgColor="FFFFFF")
            cor_proj = PatternFill("solid", fgColor="303030")
            cor_alta = PatternFill("solid", fgColor="1F497D")
            cor_ok = PatternFill("solid", fgColor="C6EFCE")
            cor_proximo = PatternFill("solid", fgColor="FFEB9C")

            f_cab = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            f_branca = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
            f_preta = Font(name="Calibri", size=11, bold=True, color="000000")
            f_verde = Font(name="Calibri", size=11, bold=True, color="006100")
            f_amarela = Font(name="Calibri", size=11, bold=True, color="9C5700")

            borda = Border(
                left=Side(style="thin", color="D9D9D9"),
                right=Side(style="thin", color="D9D9D9"),
                top=Side(style="thin", color="D9D9D9"),
                bottom=Side(style="thin", color="D9D9D9"),
            )
            centro = Alignment(horizontal="center", vertical="center")

            cols = list(dataframe.columns)
            col_int = [
                i + 1 for i, c in enumerate(cols) if c.lower() in ("posição", "posicao")
            ]
            col_dec = [
                i + 1
                for i, c in enumerate(cols)
                if c.lower() not in ("posição", "posicao")
                and pd.api.types.is_numeric_dtype(dataframe[c])
            ]
            idx_proj = cols.index("Projeção") + 1 if "Projeção" in cols else -1
            idx_pontos = cols.index("Pontos") + 1 if "Pontos" in cols else -1

            for row in ws.iter_rows(
                min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column
            ):
                for cel in row:
                    cel.border = borda
                    if cel.row == 1:
                        cel.fill = cor_cab
                        cel.font = f_cab
                        cel.alignment = centro
                        continue

                    cel.fill = cor_par if cel.row % 2 == 0 else cor_impar

                    if cel.column == idx_proj:
                        cel.fill = cor_proj
                        cel.font = f_branca
                    elif cel.column == idx_pontos:
                        try:
                            v = float(cel.value or 0)
                            if v >= 400:
                                cel.fill = cor_alta
                                cel.font = f_branca
                            elif v >= 300:
                                cel.fill = cor_ok
                                cel.font = f_verde
                            elif v >= 275:
                                cel.fill = cor_proximo
                                cel.font = f_amarela
                            else:
                                cel.font = f_preta
                        except (ValueError, TypeError):
                            pass

                    if cel.column in col_int:
                        cel.number_format = "#,##0"
                    elif cel.column in col_dec:
                        cel.number_format = "#,##0.0"

            for col in ws.columns:
                letra = get_column_letter(col[0].column)
                max_len = max((len(str(c.value)) for c in col if c.value), default=0)
                ws.column_dimensions[letra].width = max(max_len + 3, 12)

            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions

        return output.getvalue()


# ====================================================
# BLOCO 4: PROCESSAMENTO
# ====================================================
class ProcessamentoDados:
    @staticmethod
    def calcular_rankings(
        df: pd.DataFrame, dias_brutos: int, dias_seguros: int, dias_passados: int
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        base = (
            df.groupby(["CódAuxEquipe", "Nome Equipe", "Supervisor", "Projeto"])[
                "Pontos"
            ]
            .sum()
            .reset_index()
            .sort_values("Pontos", ascending=False)
        )

        if "Dias Trab Tecnico" in df.columns:
            dias_trab = (
                base["Nome Equipe"]
                .map(df.groupby("Nome Equipe")["Dias Trab Tecnico"].max())
                .fillna(dias_passados)
                .astype(int)
            )
        else:
            dias_trab = pd.Series(dias_passados, index=base.index)

        dias_trab = dias_trab.replace(0, 1)
        media_pts = base["Pontos"] / dias_trab
        projecao = base["Pontos"] + (media_pts * dias_brutos)

        def _montar(modo_dia: bool) -> pd.DataFrame:
            r = base.copy()
            r.insert(0, "Posição", range(1, len(r) + 1))
            for m in [300, 350, 375, 400]:
                label = f"Meta Dia | {m}" if modo_dia else f"Meta | {m}"
                r[label] = (
                    (r["Pontos"] - m) / dias_seguros if modo_dia else r["Pontos"] - m
                )
            r["Projeção"] = projecao.values
            return r

        return _montar(False), _montar(True)


# ====================================================
# BLOCO 5: HERO + DADOS
# ====================================================
render_hero(
    titulo="📈 Central de Performance | Produtividade",
    subtitulo="Acompanhamento individual de execução, produtividade e performance em campo",
    badge="Atualização em tempo real",
)

if "dados_prod" not in st.session_state:
    render_insight("Carregue os dados na página principal primeiro.", tipo="alerta")
    st.stop()

prod = st.session_state["dados_prod"]["Prod"].copy()
gpon = st.session_state["dados_prod"]["Gpon"].copy()
prod["Pontos"] = pd.to_numeric(prod["Pontos"], errors="coerce").fillna(0)
gpon["Pontos"] = pd.to_numeric(gpon["Pontos"], errors="coerce").fillna(0)
df = pd.concat([prod, gpon], ignore_index=True)

TOTAL_GERAL_PONTOS = df["Pontos"].sum()
TOTAL_GERAL_OS = len(df)
TOTAL_GERAL_EQUIPES = df["Nome Equipe"].nunique() if "Nome Equipe" in df.columns else 0
MEDIA_GERAL_PONTOS = (
    TOTAL_GERAL_PONTOS / TOTAL_GERAL_EQUIPES if TOTAL_GERAL_EQUIPES > 0 else 0.0
)


# ====================================================
# BLOCO 6: FILTROS
# ====================================================
st.sidebar.header("🎯 Filtros Avançados")

for col_nome, label in [
    ("Projeto", "Projeto:"),
    ("Supervisor", "Supervisor:"),
    ("Nome Equipe", "Equipe:"),
]:
    if col_nome in df.columns:
        opcoes = ["Todos"] + sorted(df[col_nome].dropna().astype(str).unique())
        sel = st.sidebar.selectbox(label, opcoes, key=f"sel_{col_nome}")
        if sel != "Todos":
            df = df[df[col_nome] == sel]

if st.sidebar.button("🔄 Limpar Filtros"):
    st.rerun()


# ====================================================
# BLOCO 7: CÁLCULOS + KPIs
# ====================================================
dias_brutos, dias_seguros, ultima_atualizacao, dias_passados = (
    Utilitarios.calcular_dias_uteis(df)
)

total_equipes_filtro = df["Nome Equipe"].nunique() if "Nome Equipe" in df.columns else 0
total_os_filtro = len(df)
total_pontos_filtro = df["Pontos"].sum() if "Pontos" in df.columns else 0.0
media_pontos_filtro = (
    total_pontos_filtro / total_equipes_filtro if total_equipes_filtro > 0 else 0.0
)

var_pontos = Utilitarios.calcular_share(total_pontos_filtro, TOTAL_GERAL_PONTOS)
var_os = Utilitarios.calcular_share(total_os_filtro, TOTAL_GERAL_OS)
var_equipes = Utilitarios.calcular_share(total_equipes_filtro, TOTAL_GERAL_EQUIPES)

ComponenteVisual.gerar_insight_ia(media_pontos_filtro, dias_brutos)

c1, c2, c3, c4 = st.columns(4)
render_kpi(
    c1,
    "Total Pontos · Geral",
    Utilitarios.formatar_numero(TOTAL_GERAL_PONTOS),
    tema="cinza",
)
render_kpi(
    c2,
    "Total Pontos · Filtro",
    Utilitarios.formatar_numero(total_pontos_filtro),
    sub=var_pontos[1],
    tema="azul",
)
render_kpi(
    c3, "Equipes · Filtro", str(total_equipes_filtro), sub=var_equipes[1], tema="verde"
)
render_kpi(
    c4,
    "Total O.S. · Filtro",
    Utilitarios.formatar_numero(total_os_filtro),
    sub=var_os[1],
    tema="laranja",
)

st.divider()


# ====================================================
# BLOCO 8: RANKING & METAS (CONTEÚDO PRINCIPAL)
# ====================================================
ranking = pd.DataFrame()
ranking_dia = pd.DataFrame()
if "Nome Equipe" in df.columns:
    ranking, ranking_dia = ProcessamentoDados.calcular_rankings(
        df, dias_brutos, dias_seguros, dias_passados
    )

col_t, col_tg = st.columns([3, 1])
with col_t:
    render_section_header("📊", "PRODUTIVIDADE · Metas & Projeção")
with col_tg:
    st.write("")
    por_dia = st.toggle("📅 **Modo Meta Diária**", key="tg_meta_dia")

df_exibir = ranking_dia if por_dia else ranking
modo_txt = "Meta Diária" if por_dia else "Meta Mensal"

ComponenteVisual.render_dataframe_corporativo(
    df_exibir,
    titulo=f"Performance por Equipe — {modo_txt}",
    icone="🏆",
    badge=f"{len(df_exibir)} equipes ativas",
    modo_diario=por_dia,
)

col_dl, _ = st.columns([2.5, 7.5])
nome_arq = "ranking_diario.xlsx" if por_dia else "ranking_geral.xlsx"

with col_dl:
    st.download_button(
        "📥 **Exportar para Excel**",
        data=Utilitarios.exportar_excel(df_exibir),
        file_name=nome_arq,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

st.markdown(
    f"""
    <div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:16px;
         padding:12px 16px;background:#F8FAFC;border-radius:10px;
         border:1px solid #DCE5F0;font-size:0.78rem;
         font-family:{FONTE_TEXTO};align-items:center;">
        <span style="font-weight:700;color:{COR_TEXTO_3};
             text-transform:uppercase;letter-spacing:0.05em;">🎨 Legenda:</span>
        <span style="background:#1E3A8A;color:white;padding:3px 10px;
             border-radius:6px;font-weight:700;">🏆 400+ pts — Alta Performance</span>
        <span style="background:#DCFCE7;color:#166534;padding:3px 10px;
             border-radius:6px;font-weight:700;">✅ 300–399 — Na Meta</span>
        <span style="background:#FEF9C3;color:#854D0E;padding:3px 10px;
             border-radius:6px;font-weight:700;">⚠️ 275–299 — Próximo da Meta</span>
        <span style="background:#FEF2F2;color:#991B1B;padding:3px 10px;
             border-radius:6px;font-weight:700;">🚨 &lt; 275 — Abaixo da Meta</span>
        <span style="background:#0A2F6B;color:white;padding:3px 10px;
             border-radius:6px;font-weight:700;border-left:3px solid #E8700A;">🎯 Proj. Fechamento</span>
    </div>
    """,
    unsafe_allow_html=True,
)

# ── Rodapé ──────────────────────────────────────────
if pd.notna(ultima_atualizacao):
    st.sidebar.divider()
    st.sidebar.caption(
        f"🕒 **Última Atualização:**\n"
        f"{pd.to_datetime(ultima_atualizacao).strftime('%d/%m/%Y')}"
    )
