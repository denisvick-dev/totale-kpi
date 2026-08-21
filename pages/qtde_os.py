"""
Central de Performance | Qtde. de O.S.
Arquivo: pages/producao.py
"""
from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np
import pandas as pd
import streamlit as st

# ====================================================
# IMPORTAÇÃO DOS COMPONENTES CORPORATIVOS
# ====================================================
from components.componentes import (
    aplicar_estilo,
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
# 2. CÁLCULO DE CALENDÁRIO (Exclui apenas domingos)
# ====================================================
@dataclass
class InfoCalendario:
    """Informações de dias úteis (Seg–Sáb) do mês de referência."""

    ano: int
    mes: int
    data_ref: datetime.date
    total_dias_uteis: int
    dias_passados: int
    dias_faltantes: int

    @classmethod
    def calcular(cls, data_referencia: Optional[datetime.date] = None) -> "InfoCalendario":
        data_ref = data_referencia or datetime.date.today()
        ano, mes = data_ref.year, data_ref.month
        _, ultimo_dia_num = calendar.monthrange(ano, mes)

        primeiro = np.datetime64(datetime.date(ano, mes, 1))
        ultimo   = np.datetime64(datetime.date(ano, mes, ultimo_dia_num))
        ref      = np.datetime64(data_ref)

        mask = "1111110"  # Segunda a Sábado ativos, Domingo (0) inativo
        total = int(np.busday_count(primeiro, ultimo + np.timedelta64(1, "D"), weekmask=mask))
        passados = int(np.busday_count(primeiro, ref + np.timedelta64(1, "D"), weekmask=mask))
        faltantes = max(0, total - passados)

        return cls(
            ano=ano,
            mes=mes,
            data_ref=data_ref,
            total_dias_uteis=total,
            dias_passados=passados,
            dias_faltantes=faltantes,
        )


# ====================================================
# 3. PROCESSAMENTO DE DADOS
# ====================================================
class ProcessadorDados:
    """Carrega, valida e processa o DataFrame de produção."""

    COL_DATA       = "Data Agendamento"
    COL_OS         = "OS"
    COL_SUPERVISOR = "Supervisor"
    COL_PROJETO    = "Projeto"
    COL_TECNICO    = "Nome Equipe"
    COL_COD_TEC    = "CódAuxEquipe"

    def __init__(self, df: pd.DataFrame):
        self.df_original = df.copy()
        self.df          = df.copy()
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
    def ultima_atualizacao(self) -> Optional[pd.Timestamp]:
        if self.COL_DATA in self.df.columns and not self.df.empty:
            return self.df[self.COL_DATA].max()
        return None

    def filtrar(self, coluna: str, valor: Optional[str]) -> None:
        if valor != "Todos" and coluna in self.df.columns:
            self.df = self.df[self.df[coluna] == valor]

    def opcoes_filtro(self, coluna: str) -> list:
        if coluna not in self.df.columns:
            return ["Todos"]
        return ["Todos"] + sorted(self.df[coluna].dropna().astype(str).unique())

    def tabela_supervisor(self, dias_passados: int, dias_faltantes: int) -> pd.DataFrame:
        if self.COL_SUPERVISOR not in self.df.columns or self.df.empty:
            return pd.DataFrame()

        qtde = self.df.groupby(self.COL_SUPERVISOR)[self.COL_OS].count().reset_index(name="Qtde. de O.S.")
        dias_passados_seguro = max(1, dias_passados)
        media_diaria = qtde["Qtde. de O.S."] / dias_passados_seguro

        qtde["Meta | 2500"] = qtde["Qtde. de O.S."] - 2500
        qtde["Meta | 3000"] = qtde["Qtde. de O.S."] - 3000
        qtde["Meta | 3500"] = qtde["Qtde. de O.S."] - 3500
        qtde["Projeção"]    = (qtde["Qtde. de O.S."] + media_diaria * dias_faltantes).round().astype(int)

        return qtde.sort_values("Qtde. de O.S.", ascending=False)

    def tabela_projeto(self, dias_passados: int, dias_faltantes: int) -> pd.DataFrame:
        if self.COL_PROJETO not in self.df.columns or self.df.empty:
            return pd.DataFrame()

        qtde = self.df.groupby(self.COL_PROJETO)[self.COL_OS].count().reset_index(name="Qtde. de O.S.")
        dias_passados_seguro = max(1, dias_passados)
        media_diaria = qtde["Qtde. de O.S."] / dias_passados_seguro

        qtde["Meta | 9000"]  = qtde["Qtde. de O.S."] - 9000
        qtde["Meta | 10000"] = qtde["Qtde. de O.S."] - 10000
        qtde["Meta | 11000"] = qtde["Qtde. de O.S."] - 11000
        qtde["Projeção"]     = (qtde["Qtde. de O.S."] + media_diaria * dias_faltantes).round().astype(int)

        return qtde.sort_values("Qtde. de O.S.", ascending=False)

    def tabela_tecnico(self) -> pd.DataFrame:
        cols_necessarias = [self.COL_COD_TEC, self.COL_TECNICO, self.COL_SUPERVISOR, self.COL_PROJETO]
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
        # Fundo azul claro, texto azul escuro
        return "background-color: #EFF6FF; color: #1E40AF; font-weight: 700;"

    @staticmethod
    def cor_projecao(valor: Any) -> str:
        # Fundo laranja claro, texto laranja escuro
        return "background-color: #FFF7ED; color: #C2410C; font-weight: 700;"


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
        badge="Operação e Metas"
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
    data_ref = proc.ultima_atualizacao.date() if proc.ultima_atualizacao is not None else None
    cal = InfoCalendario.calcular(data_ref)
    
    # Exibe um alerta dinâmico com o status do mês
    render_insight(
        f"**Status do Mês:** Já se passaram **{cal.dias_passados} dias úteis** e restam **{cal.dias_faltantes} dias úteis** para o fechamento.", 
        tipo="info"
    )

    # ── KPIs ─────────────────────────────────────────────────────────
    render_section_header("analytics", "Resumo Operacional")
    c1, c2, c3, c4 = st.columns(4)
    
    render_kpi(c1, "Total O.S. (Geral)", f"{proc.total_geral:,}".replace(",", "."), tema="cinza")
    render_kpi(c2, "Total O.S. (Filtrado)", f"{proc.total_filtrado:,}".replace(",", "."), tema="azul")
    render_kpi(c3, "Projetos Ativos", str(proc.qtd_projetos), tema="laranja")
    render_kpi(c4, "Supervisores", str(proc.qtd_supervisores), tema="verde")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabelas Supervisor × Projeto ─────────────────────────────────
    col_esq, col_dir = st.columns(2)

    with col_esq:
        render_section_header("groups", "Visão por Supervisor")
        df_sup = proc.tabela_supervisor(cal.dias_passados, cal.dias_faltantes)
        if df_sup.empty:
            st.info("Sem dados de Supervisor.")
        else:
            styled_sup = (
                df_sup.style
                .map(EstiloTabela.cor_os, subset=["Qtde. de O.S."])
                .map(EstiloTabela.cor_projecao, subset=["Projeção"])
            )
            st.dataframe(styled_sup, use_container_width=True, hide_index=True)

    with col_dir:
        render_section_header("business_center", "Visão por Projeto")
        df_proj = proc.tabela_projeto(cal.dias_passados, cal.dias_faltantes)
        if df_proj.empty:
            st.info("Sem dados de Projeto.")
        else:
            styled_proj = (
                df_proj.style
                .map(EstiloTabela.cor_os, subset=["Qtde. de O.S."])
                .map(EstiloTabela.cor_projecao, subset=["Projeção"])
            )
            st.dataframe(styled_proj, use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Técnicos ─────────────────────────────────────────────────────
    render_section_header("engineering", "Performance de Técnicos")
    df_tec = proc.tabela_tecnico()
    if df_tec.empty:
        st.info("Sem dados de Técnicos para exibir.")
    else:
        styled_tec = df_tec.style.map(EstiloTabela.cor_os, subset=["Qtde. de O.S."])
        st.dataframe(styled_tec, use_container_width=True, hide_index=True, height=400)

    # ── Rodapé no Sidebar ────────────────────────────────────────────
    if proc.ultima_atualizacao is not None and pd.notna(proc.ultima_atualizacao):
        st.sidebar.divider()
        st.sidebar.markdown(
            f"**🕒 Última Atualização:**<br>{pd.to_datetime(proc.ultima_atualizacao).strftime('%d/%m/%Y às %H:%M')}",
            unsafe_allow_html=True
        )


if __name__ == "__main__":
    main()