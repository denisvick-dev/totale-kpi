"""
Central de Performance | Qtde. de O.S.
Arquivo: pages/producao.py
"""
from __future__ import annotations

import calendar
import datetime
from dataclasses import dataclass
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import streamlit as st


# ====================================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ====================================================
st.set_page_config(
    page_title="Central de Performance | O.S.",
    page_icon="⚡",
    layout="wide",
)


# ====================================================
# 2. TEMA VISUAL
# ====================================================
class Tema:
    """Paleta de cores e estilos visuais do dashboard."""

    HERO_GRADIENT = (
        "linear-gradient(135deg, #C24400 0%, #E05A00 35%, #F37C04 70%, #FFAB40 100%)"
    )

    CARDS: Dict[str, Dict[str, str]] = {
        "azul": {
            "fundo": "#F0F9FF",
            "texto": "#0369A1",
            "borda": "#0EA5E9",
            "titulo": "#075985",
        },
        "verde": {
            "fundo": "#F0FDF4",
            "texto": "#15803D",
            "borda": "#22C55E",
            "titulo": "#166534",
        },
        "laranja": {
            "fundo": "#FFF7ED",
            "texto": "#C2410C",
            "borda": "#F97316",
            "titulo": "#9A3412",
        },
        "cinza": {
            "fundo": "#F8FAFC",
            "texto": "#334155",
            "borda": "#94A3B8",
            "titulo": "#64748B",
        },
    }

    COR_FUNDO_OS       = "#F8FAFC"
    COR_TEXTO_OS       = "#334155"
    COR_FUNDO_PROJECAO = "#334155"
    COR_TEXTO_PROJECAO = "#FFFFFF"

    @classmethod
    def aplicar_css(cls) -> None:
        """Injeta CSS global do dashboard."""
        st.markdown(
            """
        <style>
    /* CRIAÇÃO DE ESTILOS PARA A HERO (barra de títulos) */
            .hero-corp {
            background: linear-gradient(135deg, #012869 0%, #1E40AF 50%, #F37C04 100%);
            padding: 32px 40px;
            border-radius: 16px;
            color: white;
            box-shadow: 0 10px 40px rgba(1, 40, 105, 0.25);
            margin-bottom: 24px;
            position: relative;
            overflow: hidden;
        }
        .hero-corp::before {
            content: '';
            position: absolute;
            top: -50%; right: -10%;
            width: 400px; height: 400px;
            background: rgba(255,255,255,0.05);
            border-radius: 50%;
        }
        .hero-title {
            font-size: 34px;
            font-weight: 800;
            margin: 0;
            letter-spacing: -0.5px;
            font-family: 'Segoe UI', -apple-system, sans-serif;
        }
        .hero-subtitle {
            font-size: 15px;
            opacity: 0.92;
            margin: 6px 0 0 0;
            font-weight: 400;
        }
        .hero-badge {
            display: inline-block;
            background: rgba(255,255,255,0.18);
            padding: 4px 14px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 12px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        
            .kpi-card {
                padding: 1.4rem 1.6rem; border-radius: 1rem; border-left: 5px solid;
                box-shadow: 0 4px 12px rgba(0,0,0,0.06);
                min-height: 110px; display: flex; flex-direction: column;
                justify-content: center;
            }
            .kpi-val {
                font-size: 1.85rem; font-weight: 800;
                line-height: 1.1; margin: 0.3rem 0;
            }
            .kpi-lab {
                font-size: 0.72rem; text-transform: uppercase;
                font-weight: 700; letter-spacing: 0.05em;
            }
            .kpi-sub { font-size: 0.78rem; margin-top: 0.2rem; }
            .section-header {
                display: flex; align-items: center; gap: 0.6rem;
                margin: 1.5rem 0 0.8rem; padding-bottom: 0.4rem;
                border-bottom: 2px solid #E2E8F0;
            }
            .section-header h3 {
                margin: 0; font-size: 1.1rem; color: #0F172A;
            }
        </style>
        """,
            unsafe_allow_html=True,
        )

    @classmethod
    def render_hero(cls) -> None:
        """Renderiza o banner principal do dashboard."""
        st.markdown(
        f"""
        <div class="hero-corp">
            <div style="position:relative;z-index:2;">
                <h1 class="hero-title">📊 Central de Performance | Qtde. de O.S.</h1>
                <p class="hero-subtitle">
                    Volumetria operacional, projeções de fechamento e metas por supervisor e projeto
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    @classmethod
    def render_card(cls, titulo: str, valor: str, tema: str = "azul") -> str:
        """Retorna HTML de um card de métrica."""
        cores = cls.CARDS.get(tema, cls.CARDS["azul"])
        return f"""
        <div style="
            background-color: {cores['fundo']}; padding: 20px;
            border-radius: 10px; border-left: 6px solid {cores['borda']};
            box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 15px;
        ">
            <p style="margin:0; font-size:14px; color:{cores['titulo']};"><b>{titulo}</b></p>
            <h2 style="margin:0; padding-top:5px; color:{cores['texto']}; font-weight:900;">
                {valor}
            </h2>
        </div>
        """


# ====================================================
# 3. CÁLCULO DE CALENDÁRIO (Exclui apenas domingos)
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
        """
        Calcula dias úteis (Seg–Sáb, excluindo domingos) com base na data de referência.
        Se nenhuma data for informada, usa hoje.
        """
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
# 4. PROCESSAMENTO DE DADOS
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
        """Converte colunas e garante tipos."""
        if self.COL_DATA in self.df.columns:
            self.df[self.COL_DATA] = pd.to_datetime(
                self.df[self.COL_DATA].array, errors="coerce"
            )

    @property
    def total_geral(self) -> int:
        """Total de OS antes de qualquer filtro."""
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

    # ── Filtros ──────────────────────────────────────────────────────

    def filtrar(self, coluna: str, valor: Optional[str]) -> None:
        """Aplica filtro in-place no DataFrame de trabalho."""
        if valor != "Todos" and coluna in self.df.columns:
            self.df = self.df[self.df[coluna] == valor]

    def opcoes_filtro(self, coluna: str) -> list:
        """Retorna lista de opções para selectbox."""
        if coluna not in self.df.columns:
            return ["Todos"]
        return ["Todos"] + sorted(self.df[coluna].dropna().astype(str).unique())

    # ── Tabelas de visão (Cálculo de Projeção Corrigido) ─────────────

    def tabela_supervisor(self, dias_passados: int, dias_faltantes: int) -> pd.DataFrame:
        """Monta tabela de visão por supervisor com metas e projeção baseada em dias úteis reais."""
        if self.COL_SUPERVISOR not in self.df.columns or self.df.empty:
            return pd.DataFrame()

        qtde = (
            self.df
            .groupby(self.COL_SUPERVISOR)[self.COL_OS]
            .count()
            .reset_index(name="Qtde. de O.S.")
        )

        # Média baseada em dias decorridos reais (evita distorções de groupby)
        dias_passados_seguro = max(1, dias_passados)
        media_diaria = qtde["Qtde. de O.S."] / dias_passados_seguro

        qtde["Meta | 2500"] = qtde["Qtde. de O.S."] - 2500
        qtde["Meta | 3000"] = qtde["Qtde. de O.S."] - 3000
        qtde["Meta | 3500"] = qtde["Qtde. de O.S."] - 3500
        qtde["Projeção"]    = (qtde["Qtde. de O.S."] + media_diaria * dias_faltantes).round().astype(int)

        return qtde.sort_values("Qtde. de O.S.", ascending=False)

    def tabela_projeto(self, dias_passados: int, dias_faltantes: int) -> pd.DataFrame:
        """Monta tabela de visão por projeto com metas e projeção baseada em dias úteis reais."""
        if self.COL_PROJETO not in self.df.columns or self.df.empty:
            return pd.DataFrame()

        qtde = (
            self.df
            .groupby(self.COL_PROJETO)[self.COL_OS]
            .count()
            .reset_index(name="Qtde. de O.S.")
        )

        # Média baseada em dias decorridos reais (evita distorções de groupby)
        dias_passados_seguro = max(1, dias_passados)
        media_diaria = qtde["Qtde. de O.S."] / dias_passados_seguro

        qtde["Meta | 9000"]  = qtde["Qtde. de O.S."] - 9000
        qtde["Meta | 10000"] = qtde["Qtde. de O.S."] - 10000
        qtde["Meta | 11000"] = qtde["Qtde. de O.S."] - 11000
        qtde["Projeção"]     = (qtde["Qtde. de O.S."] + media_diaria * dias_faltantes).round().astype(int)

        return qtde.sort_values("Qtde. de O.S.", ascending=False)

    def tabela_tecnico(self) -> pd.DataFrame:
        """Monta tabela de performance por técnico."""
        cols_necessarias = [self.COL_COD_TEC, self.COL_TECNICO,
                           self.COL_SUPERVISOR, self.COL_PROJETO]
        if not all(c in self.df.columns for c in cols_necessarias) or self.df.empty:
            return pd.DataFrame()

        return (
            self.df
            .groupby(cols_necessarias)[self.COL_OS]
            .count()
            .reset_index(name="Qtde. de O.S.")
            .sort_values("Qtde. de O.S.", ascending=False)
        )


# ====================================================
# 5. ESTILIZAÇÃO DE TABELAS
# ====================================================
class EstiloTabela:
    """Funções de estilização condicional para DataFrames."""

    @staticmethod
    def rbg_colorir(valor: Any, fundo: str, texto: str) -> str:
        return f"background-color: {fundo}; color: {texto}; font-weight: bold;"

    @classmethod
    def cor_os(cls, valor: Any) -> str:
        return cls.rbg_colorir(valor, Tema.COR_FUNDO_OS, Tema.COR_TEXTO_OS)

    @classmethod
    def cor_projecao(cls, valor: Any) -> str:
        return cls.rbg_colorir(valor, Tema.COR_FUNDO_PROJECAO, Tema.COR_TEXTO_PROJECAO)


# ====================================================
# 6. COMPONENTES VISUAIS (GRÁFICOS E SEÇÕES)
# ====================================================
class Componentes:
    """Renderiza seções visuais do dashboard."""

    @staticmethod
    def kpis(proc: ProcessadorDados) -> None:
        """Renderiza os 4 KPIs superiores."""
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(
                Tema.render_card(
                    "Total O.S. (Geral)",
                    f"{proc.total_geral:,}".replace(",", "."),
                    "cinza",
                ),
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                Tema.render_card(
                    "Total O.S. (Filtrado)",
                    f"{proc.total_filtrado:,}".replace(",", "."),
                    "azul",
                ),
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(
                Tema.render_card("Projetos Ativos", str(proc.qtd_projetos), "laranja"),
                unsafe_allow_html=True,
            )
        with c4:
            st.markdown(
                Tema.render_card("Supervisores Ativos", str(proc.qtd_supervisores), "verde"),
                unsafe_allow_html=True,
            )

    @staticmethod
    def visao_supervisor(df_sup: pd.DataFrame) -> None:
        """Renderiza tabela de supervisores."""
        st.subheader("👨‍💼 Visão por Supervisor")

        if df_sup.empty:
            st.info("Sem dados de Supervisor.")
            return

        st.dataframe(
            df_sup.style
            .map(EstiloTabela.cor_os, subset=["Qtde. de O.S."])
            .map(EstiloTabela.cor_projecao, subset=["Projeção"]),
            use_container_width=True,
            hide_index=True,
            height="auto",
        )

    @staticmethod
    def visao_projeto(df_proj: pd.DataFrame) -> None:
        """Renderiza tabela + gráfico de projetos."""
        st.subheader("💼 Visão por Projeto")

        if df_proj.empty:
            st.info("Sem dados de Projeto.")
            return

        st.dataframe(
            df_proj.style
            .map(EstiloTabela.cor_os, subset=["Qtde. de O.S."])
            .map(EstiloTabela.cor_projecao, subset=["Projeção"]),
            use_container_width=True,
            hide_index=True,
            height="auto",
        )

    @staticmethod
    def performance_tecnicos(df_tec: pd.DataFrame) -> None:
        """Renderiza tabela geral de técnicos."""
        st.subheader("👷 Performance de Técnicos")

        if df_tec.empty:
            st.info("Sem dados de Técnicos para exibir.")
            return

        st.markdown("**📋 Tabela Geral de Técnicos**")
        st.dataframe(
            df_tec.style.map(EstiloTabela.cor_os, subset=["Qtde. de O.S."]),
            use_container_width=True,
            hide_index=True,
            height=450,
        )

    @staticmethod
    def rodape(ultima_atualizacao: Optional[pd.Timestamp]) -> None:
        """Exibe rodapé com data da última atualização."""
        st.divider()
        if ultima_atualizacao is not None and pd.notna(ultima_atualizacao):
            st.sidebar.divider()
            st.sidebar.caption(
                f"🕒 ***Última Atualização:*** "
                f"{pd.to_datetime(ultima_atualizacao).strftime('%d/%m/%Y')}"
            )


# ====================================================
# 7. APLICAÇÃO PRINCIPAL
# ====================================================
def main() -> None:
    """Orquestra toda a renderização do dashboard."""

    # ── Estilos ──────────────────────────────────────────────────────
    Tema.aplicar_css()
    Tema.render_hero()

    # ── Validação de dados ───────────────────────────────────────────
    if "dados_prod" not in st.session_state:
        st.warning("⚠️ Carregue os dados na página principal primeiro.")
        st.stop()

    try:
        df_raw = st.session_state["dados_prod"]["Prod"].copy()
    except KeyError as e:
        st.error(f"❌ Aba não encontrada na base de dados: {e}")
        st.stop()

    # ── Processamento ────────────────────────────────────────────────
    proc = ProcessadorDados(df_raw)

    # ── Filtros (sidebar) ────────────────────────────────────────────
    st.sidebar.header("🎯 Filtros Avançados")

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

    # ── Calendário ───────────────────────────────────────────────────
    data_ref = (
        proc.ultima_atualizacao.date()
        if proc.ultima_atualizacao is not None
        else None
    )
    cal = InfoCalendario.calcular(data_ref)

    # ── KPIs ─────────────────────────────────────────────────────────
    Componentes.kpis(proc)
    st.divider()

    # ── Supervisor × Projeto ─────────────────────────────────────────
    col_esq, col_dir = st.columns(2)

    with col_esq:
        Componentes.visao_supervisor(proc.tabela_supervisor(cal.dias_passados, cal.dias_faltantes))

    with col_dir:
        Componentes.visao_projeto(proc.tabela_projeto(cal.dias_passados, cal.dias_faltantes))

    st.divider()

    # ── Técnicos ─────────────────────────────────────────────────────
    Componentes.performance_tecnicos(proc.tabela_tecnico())

    # ── Rodapé ───────────────────────────────────────────────────────
    Componentes.rodape(proc.ultima_atualizacao)


# ====================================================
# ENTRY POINT
# ====================================================
if __name__ == "__main__":
    main()
