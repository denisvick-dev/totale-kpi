"""
Central de Performance | Qtde. de O.S.
Arquivo: pages/producao.py
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

# ====================================================
# IMPORTAÇÃO DOS COMPONENTES CORPORATIVOS
# ====================================================
from components.calendario import InfoCalendario
from components.componentes import (
    aplicar_estilo,
    estilizar_dataframe,
    render_hero,
    render_insight,
    render_kpi,
    render_section_header,
)

# ====================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ====================================================
st.set_page_config(
    page_title="Central de Performance | O.S.",
    page_icon="⚡",
    layout="wide",
)


# ====================================================
# 2. CALENDÁRIO (Seg–Sáb, sem domingos nem feriados)
# ====================================================
# Regra única do projeto: InfoCalendario vem de components/calendario.py e
# desconta domingos e feriados (nacionais + estaduais de SP).


# ====================================================
# 3. PROCESSAMENTO DE DADOS
# ====================================================
class ProcessadorDados:
    """Carrega, valida e processa o DataFrame de produção."""

    COL_DATA = "Data Agendamento"
    COL_OS = "OS"
    COL_SUPERVISOR = "Supervisor"
    COL_PROJETO = "Projeto"
    COL_TECNICO = "Nome Equipe"
    COL_COD_TEC = "CódAuxEquipe"

    def __init__(self, df: pd.DataFrame):
        self.df_original = df.copy()
        self.df = df.copy()
        self._preparar()

    def _preparar(self) -> None:
        if self.COL_DATA in self.df.columns:
            self.df[self.COL_DATA] = pd.to_datetime(
                self.df[self.COL_DATA].array, errors="coerce"
            )

    @property
    def total_geral(self) -> int:
        return len(self.df_original)

    @property
    def total_filtrado(self) -> int:
        return len(self.df)

    @property
    def qtd_projetos(self) -> int:
        if self.COL_PROJETO not in self.df.columns:
            return 0
        return int(self.df[self.COL_PROJETO].nunique())

    @property
    def qtd_supervisores(self) -> int:
        if self.COL_SUPERVISOR not in self.df.columns:
            return 0
        return int(self.df[self.COL_SUPERVISOR].nunique())

    @property
    def ultima_atualizacao(self) -> pd.Timestamp | None:
        if self.COL_DATA in self.df.columns and not self.df.empty:
            return self.df[self.COL_DATA].max()
        return None

    def filtrar(self, coluna: str, valor: str | None) -> None:
        if valor != "Todos" and coluna in self.df.columns:
            self.df = self.df[self.df[coluna] == valor]

    def opcoes_filtro(self, coluna: str) -> list:
        if coluna not in self.df.columns:
            return ["Todos"]
        return ["Todos"] + sorted(self.df[coluna].dropna().astype(str).unique())

    def tabela_supervisor(
        self, dias_passados: int, dias_faltantes: int
    ) -> pd.DataFrame:
        if self.COL_SUPERVISOR not in self.df.columns or self.df.empty:
            return pd.DataFrame()

        qtde = (
            self.df.groupby(self.COL_SUPERVISOR)[self.COL_OS]
            .count()
            .reset_index(name="Qtde. de O.S.")
        )
        dias_passados_seguro = max(1, dias_passados)
        media_diaria = qtde["Qtde. de O.S."] / dias_passados_seguro

        qtde["Meta | 2500"] = qtde["Qtde. de O.S."] - 2500
        qtde["Meta | 3000"] = qtde["Qtde. de O.S."] - 3000
        qtde["Meta | 3500"] = qtde["Qtde. de O.S."] - 3500
        qtde["Projeção"] = (
            (qtde["Qtde. de O.S."] + media_diaria * dias_faltantes).round().astype(int)
        )

        return qtde.sort_values("Qtde. de O.S.", ascending=False)

    def tabela_projeto(self, dias_passados: int, dias_faltantes: int) -> pd.DataFrame:
        if self.COL_PROJETO not in self.df.columns or self.df.empty:
            return pd.DataFrame()

        qtde = (
            self.df.groupby(self.COL_PROJETO)[self.COL_OS]
            .count()
            .reset_index(name="Qtde. de O.S.")
        )
        dias_passados_seguro = max(1, dias_passados)
        media_diaria = qtde["Qtde. de O.S."] / dias_passados_seguro

        qtde["Meta | 9000"] = qtde["Qtde. de O.S."] - 9000
        qtde["Meta | 10000"] = qtde["Qtde. de O.S."] - 10000
        qtde["Meta | 11000"] = qtde["Qtde. de O.S."] - 11000
        qtde["Projeção"] = (
            (qtde["Qtde. de O.S."] + media_diaria * dias_faltantes).round().astype(int)
        )

        return qtde.sort_values("Qtde. de O.S.", ascending=False)

    def tabela_tecnico(self) -> pd.DataFrame:
        cols_necessarias = [
            self.COL_COD_TEC,
            self.COL_TECNICO,
            self.COL_SUPERVISOR,
            self.COL_PROJETO,
        ]
        if not all(c in self.df.columns for c in cols_necessarias) or self.df.empty:
            return pd.DataFrame()

        return (
            self.df.groupby(cols_necessarias)[self.COL_OS]
            .count()
            .reset_index(name="Qtde. de O.S.")
            .sort_values("Qtde. de O.S.", ascending=False)
        )


# ====================================================
# 4. ESTILIZAÇÃO DE TABELAS (Pandas Styler)
# ====================================================
class EstiloTabela:
    """Aplica cores de fundo em colunas específicas dos DataFrames para destacar métricas."""

    @staticmethod
    def cor_os(valor: Any) -> str:
        return (
            "background-color: #EAF2FC; color: #0A2F6B; font-weight: 700; "
            "border-left: 3px solid #0A2F6B; text-align: center;"
        )

    @staticmethod
    def cor_projecao(valor: Any) -> str:
        return (
            "background-color: #FFF7ED; color: #C2410C; font-weight: 700; "
            "border-left: 3px solid #E8700A; text-align: center;"
        )

    @staticmethod
    def cor_meta(valor: Any) -> str:
        try:
            v = float(valor)
        except (ValueError, TypeError):
            return ""
        if v >= 0:
            return (
                "background-color: #ECFDF5; color: #065F46; font-weight: 700; "
                "text-align: center;"
            )
        return "color: #B4232E; font-weight: 600; text-align: center;"

    @staticmethod
    def estilizar_resumo(df: pd.DataFrame) -> pd.io.formats.style.Styler:
        cols_meta = [c for c in df.columns if str(c).startswith("Meta")]
        fmt: dict[str, Any] = {c: "{:+,}" for c in cols_meta}
        if "Qtde. de O.S." in df.columns:
            fmt["Qtde. de O.S."] = "{:,}"
        if "Projeção" in df.columns:
            fmt["Projeção"] = "{:,}"
        styler = estilizar_dataframe(df, fmt)
        if cols_meta:
            styler = styler.map(EstiloTabela.cor_meta, subset=cols_meta)  # type: ignore[arg-type]
        if "Qtde. de O.S." in df.columns:
            styler = styler.map(EstiloTabela.cor_os, subset=["Qtde. de O.S."])  # type: ignore[arg-type]
        if "Projeção" in df.columns:
            styler = styler.map(EstiloTabela.cor_projecao, subset=["Projeção"])  # type: ignore[arg-type]
        return styler


# ====================================================
# 5. APLICAÇÃO PRINCIPAL
# ====================================================
def main() -> None:
    # ── Aplica Estilo Corporativo Global ──────────────────────────────
    aplicar_estilo()

    # ── Hero / Cabeçalho ─────────────────────────────────────────────
    render_hero(
        titulo="Qtde. de O.S.",
        subtitulo="Volumetria operacional, projeções de fechamento e metas por supervisor e projeto.",
        badge="Operação e Metas",
    )

    # ── Validação de Dados ───────────────────────────────────────────
    if "dados_prod" not in st.session_state:
        st.warning("⚠️ Carregue os dados na página principal primeiro.")
        st.stop()

    try:
        df_raw = st.session_state["dados_prod"]["Prod"].copy()
    except KeyError as e:
        st.error(f"❌ Aba não encontrada na base de dados: {e}")
        st.stop()

    proc = ProcessadorDados(df_raw)

    # ── Filtros (Sidebar) ────────────────────────────────────────────
    st.sidebar.markdown("### 🎯 Filtros Avançados")

    proj_sel = st.sidebar.selectbox(
        "Filtrar por Projeto:",
        proc.opcoes_filtro(ProcessadorDados.COL_PROJETO),
    )
    proc.filtrar(ProcessadorDados.COL_PROJETO, proj_sel)

    sup_sel = st.sidebar.selectbox(
        "Filtrar por Supervisor:",
        proc.opcoes_filtro(ProcessadorDados.COL_SUPERVISOR),
    )
    proc.filtrar(ProcessadorDados.COL_SUPERVISOR, sup_sel)

    # ── Calendário e Insight ─────────────────────────────────────────
    data_ref = (
        proc.ultima_atualizacao.date() if proc.ultima_atualizacao is not None else None
    )
    cal = InfoCalendario.calcular(data_ref)

    # Exibe um alerta dinâmico com o status do mês
    feriados_txt = ", ".join(
        f"{d.strftime('%d/%m')} ({nome})" for d, nome in cal.feriados_restantes[:4]
    )
    render_insight(
        f"**Status do Mês ({cal.nome_mes}):** Já se passaram **{cal.dias_passados} dias úteis** "
        f"e restam **{cal.dias_faltantes} dias úteis** para o fechamento "
        f"(segunda a sábado, sem domingos nem feriados)."
        + (f" Feriados restantes: {feriados_txt}." if feriados_txt else ""),
        tipo="info",
    )

    # ── KPIs ─────────────────────────────────────────────────────────
    render_section_header("analytics", "Resumo Operacional")
    c1, c2, c3, c4 = st.columns(4)

    render_kpi(
        c1,
        "Total O.S. (Geral)",
        f"{proc.total_geral:,}".replace(",", "."),
        tema="cinza",
    )
    render_kpi(
        c2,
        "Total O.S. (Filtrado)",
        f"{proc.total_filtrado:,}".replace(",", "."),
        tema="azul",
    )
    render_kpi(c3, "Projetos Ativos", str(proc.qtd_projetos), tema="laranja")
    render_kpi(c4, "Supervisores", str(proc.qtd_supervisores), tema="verde")

    # ── Tabelas em abas (largura cheia para cada visão) ──────────────
    aba_sup, aba_proj, aba_tec = st.tabs(
        ["👥 Por Supervisor", "🏢 Por Projeto", "🔧 Técnicos"]
    )

    with aba_sup:
        df_sup = proc.tabela_supervisor(cal.dias_passados, cal.dias_faltantes)
        render_section_header(
            "groups", "Visão por Supervisor", f"{len(df_sup)} supervisores"
        )
        if df_sup.empty:
            st.info("Sem dados de Supervisor.")
        else:
            st.dataframe(
                EstiloTabela.estilizar_resumo(df_sup),
                use_container_width=True,
                hide_index=True,
                height=420,
            )

    with aba_proj:
        df_proj = proc.tabela_projeto(cal.dias_passados, cal.dias_faltantes)
        render_section_header(
            "business_center", "Visão por Projeto", f"{len(df_proj)} projetos"
        )
        if df_proj.empty:
            st.info("Sem dados de Projeto.")
        else:
            st.dataframe(
                EstiloTabela.estilizar_resumo(df_proj),
                use_container_width=True,
                hide_index=True,
                height=420,
            )

    with aba_tec:
        df_tec = proc.tabela_tecnico()
        render_section_header(
            "engineering", "Performance de Técnicos", f"{len(df_tec)} equipes"
        )
        if df_tec.empty:
            st.info("Sem dados de Técnicos para exibir.")
        else:
            df_tec_display = df_tec.copy().reset_index(drop=True)
            df_tec_display.insert(0, "Posição", range(1, len(df_tec_display) + 1))
            df_tec_display = df_tec_display.rename(
                columns={"CódAuxEquipe": "Cód. Equipe", "Nome Equipe": "Equipe"}
            )
            styled_tec = estilizar_dataframe(
                df_tec_display, {"Qtde. de O.S.": "{:,}"}
            ).map(EstiloTabela.cor_os, subset=["Qtde. de O.S."])  # type: ignore[arg-type]
            st.dataframe(
                styled_tec, use_container_width=True, hide_index=True, height=420
            )

    # ── Rodapé no Sidebar ────────────────────────────────────────────
    if proc.ultima_atualizacao is not None and pd.notna(proc.ultima_atualizacao):
        st.sidebar.divider()
        st.sidebar.markdown(
            f"**🕒 Última Atualização:**<br>{pd.to_datetime(proc.ultima_atualizacao).strftime('%d/%m/%Y às %H:%M')}",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
