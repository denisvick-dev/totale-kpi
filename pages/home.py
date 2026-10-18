"""Página inicial do Portal TOTALE: status das bases e acesso aos painéis."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from components.componentes import (
    aplicar_estilo,
    render_hero,
    render_insight,
    render_kpi,
    render_painel_link,
    render_section_header,
)

VERSAO_SISTEMA = "2.2"
AMBIENTE = "Produção"
FUSO_HORARIO = ZoneInfo("America/Sao_Paulo")


PAINEIS_PERFORMANCE = [
    (
        "pages/pontos.py",
        "🏆 Ranking de Pontos",
        "Acompanhe metas, desempenho e projeções por equipe.",
    ),
    (
        "pages/qtde_os.py",
        "📊 Quantidade de O.S.",
        "Compare o volume de ordens por projeto, supervisor e técnico.",
    ),
    (
        "pages/consultivo.py",
        "🛍️ Consultivos e Produtos",
        "Explore conversão, consultivos realizados e mix de produtos.",
    ),
]

PAINEIS_OPERACAO = [
    (
        "pages/rota_inicial.py",
        "🗺️ Rota Inicial",
        "Visualize rotas, turnos, serviços e distribuição das equipes.",
    ),
    (
        "pages/volumetria.py",
        "📦 Volumetria de O.S.",
        "Monitore tarefas executadas, pendentes e projeções operacionais.",
    ),
    (
        "pages/quebra.py",
        "📉 Quebra de Agenda",
        "Identifique quebras por segmento, monitor e técnico.",
    ),
]


def _status_base_producao() -> str:
    """Indica se as planilhas exigidas pelos painéis foram carregadas na sessão."""
    dados = st.session_state.get("dados_prod")
    if not isinstance(dados, dict) or "Prod" not in dados:
        return "Aguardando"
    return "Pronta" if "Gpon" in dados else "Parcial"


def _texto_ultima_atualizacao() -> str:
    ultima = st.session_state.get("ultima_atualizacao")
    if ultima is None or not hasattr(ultima, "strftime"):
        return "Não informada"
    return ultima.strftime("%d/%m/%Y às %H:%M")


def _render_card_painel(painel: tuple[str, str, str]) -> None:
    render_painel_link(*painel)


def _render_grupo_paineis(
    titulo: str, icone: str, paineis: list[tuple[str, str, str]]
) -> None:
    render_section_header(icone, titulo, f"{len(paineis)} painéis")
    colunas = st.columns(len(paineis))
    for coluna, painel in zip(colunas, paineis):
        with coluna:
            _render_card_painel(painel)


def main() -> None:
    st.set_page_config(
        page_title="Portal TOTALE | Visão Geral",
        page_icon="📊",
        layout="wide",
    )
    aplicar_estilo()

    render_hero(
        titulo="Portal TOTALE",
        subtitulo="Um ponto de entrada para acompanhar produção, metas e operação diária.",
        badge="Central de indicadores",
    )

    status_base = _status_base_producao()
    hora_atualizacao = _texto_ultima_atualizacao()

    total_paineis = len(PAINEIS_PERFORMANCE) + len(PAINEIS_OPERACAO)
    k1, k2, k3 = st.columns(3)
    render_kpi(
        k1,
        "Painéis analíticos",
        f"{total_paineis:02d}",
        "Performance e operação",
        tema="azul",
    )
    render_kpi(
        k2,
        "Base de produção",
        status_base,
        {
            "Pronta": "Planilhas Prod e Gpon carregadas",
            "Parcial": "Planilha Prod carregada; Gpon pendente",
            "Aguardando": "Atualize os dados para começar",
        }[status_base],
        tema="verde" if status_base == "Pronta" else "laranja",
    )
    render_kpi(
        k3,
        "Última atualização",
        hora_atualizacao,
        "Horário de Brasília",
        tema="cinza",
    )

    if status_base == "Pronta":
        render_insight(
            "As bases Prod e Gpon estão carregadas. Os painéis de pontos e O.S. já podem ser consultados.",
            tipo="ok",
        )
    elif status_base == "Parcial":
        render_insight(
            "A planilha Prod está carregada, mas Gpon ainda não foi localizada. "
            "Atualize as bases para liberar todos os painéis de produção.",
            tipo="info",
        )
    else:
        render_insight(
            "Os dados de produção ainda não foram carregados nesta sessão. "
            "Comece pela atualização para habilitar os indicadores compartilhados.",
            tipo="info",
        )

    render_section_header(
        "space_dashboard", "Explore os painéis", f"{total_paineis} análises"
    )
    _render_grupo_paineis("Performance e metas", "trending_up", PAINEIS_PERFORMANCE)
    _render_grupo_paineis("Operação diária", "engineering", PAINEIS_OPERACAO)

    render_section_header("sync", "Dados e atualização")
    with st.container(border=True):
        col_info, col_acao = st.columns([3, 1])
        with col_info:
            st.markdown("#### 🔄 Atualizar as bases compartilhadas")
            st.caption(
                "Sincronize os dados de produção e consultivos antes de iniciar "
                "a análise. A atualização fica disponível durante esta sessão."
            )
        with col_acao:
            st.markdown("")
            st.page_link(
                "pages/envio_excel.py",
                label="Ir para atualização",
                icon="➡️",
            )

    agora = datetime.now(FUSO_HORARIO).strftime("%d/%m/%Y • %H:%M BRT")
    st.divider()
    st.caption(f"Portal TOTALE · {AMBIENTE} · v{VERSAO_SISTEMA} · Acesso em {agora}")


if __name__ == "__main__":
    main()
