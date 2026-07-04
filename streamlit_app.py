import streamlit as st
import pandas as pd

# Injeção de CSS para personalizar a aparência da Sidebar e dos widgets
st.html("""
    <style>
    
    /* CRIAÇÃO DE ESTILOS PARA A SIDEBAR */
    
    /* Altera a cor do texto "Filtros" no topo da Sidebar */
    .stSidebar h2 {
        color: #012869 !important; /* Azul escuro */
        font-size: 26px !important;
        font-weight: 700 !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.5); /* Sombra suave para ajudar a leitura no fundo claro */
    }

    /* Altera a cor das etiquetas (labels) dos widgets na Sidebar */
    .stSidebar [data-testid="stWidgetLabel"] p {
        color: #000047 !important; /* Azul escuro */
        font-size: 16px !important;
        font-weight: 600 !important;
    }

    /* Altera a cor de fundo e do texto das TAGS SELECIONADAS no multiselect */
    .stSidebar [data-baseweb="tag"] {
        background-color: #012869 !important; /* Fundo laranja */
        color: #FFFFFF !important; /* Texto branco */
        border-radius: 4px !important;
    }

    /* Altera a cor do ícone de "X" para fechar a tag */
    .stSidebar [data-baseweb="tag"] svg {
        fill: #FFFFFF !important;
    }
    
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgb(255, 190, 100) 0%, rgb(243, 124, 4) 100%) !important;
    }
    
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h3, 
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] a {
        color: white !important;
        text-shadow: 1px 1px 2px rgba(0,0,0,0.3); /* Sombra suave para ajudar a leitura no fundo claro */
    }
    
    [data-testid="stSidebar"] .stButton button {
        background-color: #012869 !important; /* Azul escuro */
        color: white !important;
        border-radius: 4px !important;
        border: none !important;    
    }
    
    [data-testid="stSidebar"] .stButton button:hover {
        background-color: #FFC48A !important;
        border-color: #FFC48A !important;
    }
    
    /* CRIAÇÃO DE ESTILOS PARA O SELECTBOX */
    
    [data-testid="stSelectbox"] label p {
        color: #012869 !important; /* Azul Escuro */
        font-weight: bold !important;
    }

    /* Borda padrão da caixa */
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div {
        border: 2px solid #012869 !important; /* Borda Azul Escuro */
        border-radius: 6px !important;
        background-color: white !important;
    }

    /* Borda e sombra quando passa o mouse ou clica (Foco) */
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div:hover,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div:focus-within {
        border-color: #F37C04 !important; /* Borda fica Laranja */
        box-shadow: 0 0 0 1px #F37C04 !important;
    }

    /* Cor do texto da opção que está aparecendo na caixa */
    [data-testid="stSelectbox"] div[data-baseweb="select"] div {
        color: #012869 !important; /* Azul escuro */
        font-weight: 500 !important;
    }

    /* Setinha para baixo (Dropdown icon) */
    [data-testid="stSelectbox"] div[data-baseweb="select"] svg {
        fill: #F37C04 !important; /* Setinha Laranja */
    }

    /* Fundo e borda da lista */
    ul[role="listbox"] {
        background-color: white !important;
        border: 2px solid #012869 !important;
        border-radius: 6px !important;
    }

    /* Cor do texto dos itens da lista */
    ul[role="listbox"] li {
        color: #012869 !important; /* Azul escuro */
    }

    /* Cor do item ao passar o mouse E do item que está selecionado */
    ul[role="listbox"] li:hover, 
    ul[role="listbox"] li[aria-selected="true"] {
        background-color: #F37C04 !important; /* Fundo Laranja */
        color: white !important; /* Texto Branco para dar leitura */
        font-weight: bold !important;
    }
    
    /* CRIAÇÃO DE ESTILOS PARA O DATE INPUT */
    
    [data-testid="stDateInput"] label p {
        color: #012869 !important; /* Azul Escuro */
        font-weight: bold !important;
    }

    [data-testid="stDateInput"] div[data-baseweb="input"] > div {
        background-color: white !important;
        border: 2px solid #012869 !important; /* Borda Azul Escura */
        border-radius: 6px !important;
    }

    [data-testid="stDateInput"] div[data-baseweb="input"] > div:hover,
    [data-testid="stDateInput"] div[data-baseweb="input"] > div:focus-within {
        border-color: #F37C04 !important; /* Borda fica Laranja */
        box-shadow: 0 0 0 1px #F37C04 !important;
    }

    [data-testid="stDateInput"] input {
        color: #012869 !important; /* Letras Azul Escuro */
        font-weight: 500 !important;
    }
    
    [data-testid="stDateInput"] svg {
        fill: #F37C04 !important; /* Ícone Laranja */
        color: #F37C04 !important;
    }
    </style>
    """)

st.set_page_config(
    page_title="Painéis de Produção TOTALE",
    page_icon="assets/images/icons/totale.ico",
    layout="wide"
)

def main():

    st.image("assets/images/novo-logo-totale.png", width=200)

    home_page = st.Page("pages/home.py", title="Home", icon="🏠", default=True)
    envio_excel = st.Page("pages/envio_excel.py", title="Atualização de Dados", icon="🔁")
    ranking_pontos = st.Page("pages/pontos.py", title="Ranking de Pontos", icon="📈")
    qtde_os = st.Page("pages/qtde_os.py", title="Quantidade de O.S.", icon="📊")
    consultivo = st.Page("pages/consultivo.py", title="Consultivos", icon="📋")
    gestao_ativos = st.Page(page="pages/gestao_ativos.py", title="Gestão de Ativos", icon="👷")
    # jogo_da_velha = st.Page(page="pages/jogodavelha.py", title="Jogo da Velha IA", icon="🕹️")


    # 2. Configurar a navegação passando a lista de páginas
    pg = st.logo("assets/images/novo-logo-totale.png")
    pg = st.navigation([home_page, envio_excel, ranking_pontos, qtde_os, consultivo, gestao_ativos])

    pg.run()

if __name__ == "__main__":
    main()