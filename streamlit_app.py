import streamlit as st

from components.componentes import aplicar_estilo
from components.sidebar import render_seletor_tema_sidebar

# Configuração global da aplicação — deve ser a primeira chamada do Streamlit.
st.set_page_config(
    page_title="Painéis de Produção TOTALE",
    page_icon="assets/icons/totale.ico",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Seletor global: uma instância, compartilhada por todas as páginas.
render_seletor_tema_sidebar()

# Mantém navegação, componentes e gráficos com a mesma identidade visual.
aplicar_estilo()


def main() -> None:
    st.logo("assets/images/novo-logo-totale.png", size="medium")

    # Páginas declaradas explicitamente para manter uma navegação previsível.
    home_page = st.Page(
        "pages/home.py",
        title="Visão Geral",
        icon="🏠",
        default=True,
    )
    ranking_pontos = st.Page(
        "pages/pontos.py",
        title="Ranking de Pontos",
        icon="🏆",
    )
    qtde_os = st.Page(
        "pages/qtde_os.py",
        title="Quantidade de O.S.",
        icon="📊",
    )
    consultivos = st.Page(
        "pages/consultivo.py",
        title="Consultivos e Produtos",
        icon="🛍️",
    )
    rota_inicial = st.Page(
        "pages/rota_inicial.py",
        title="Rota Inicial",
        icon="🗺️",
    )
    volumetria = st.Page(
        "pages/volumetria.py",
        title="Volumetria de O.S.",
        icon="📦",
    )
    quebra = st.Page(
        "pages/quebra.py",
        title="Quebra de Agenda",
        icon="📉",
    )
    atualizacao = st.Page(
        "pages/envio_excel.py",
        title="Atualização de Dados",
        icon="🔄",
    )

    paginas_agrupadas = {
        "INÍCIO": [home_page],
        "PERFORMANCE E METAS": [ranking_pontos, qtde_os, consultivos],
        "OPERAÇÃO DIÁRIA": [rota_inicial, volumetria, quebra],
        "DADOS": [atualizacao],
    }

    pagina = st.navigation(paginas_agrupadas)
    pagina.run()


if __name__ == "__main__":
    main()
