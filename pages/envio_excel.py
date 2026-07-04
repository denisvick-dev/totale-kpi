import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
from io import BytesIO, StringIO
from datetime import datetime, timezone, timedelta

# ====================================================
# BLOCO 1: CONFIGURAÇÕES GLOBAIS
# ====================================================

class Configuracoes:
    """Parâmetros e configurações gerais da aplicação."""
    FUSO = timezone(timedelta(hours=-3)) # Fuso horário de Brasília
    
    TEMAS_CARD = {
        "azul":   {"fundo": "#F0F9FF", "texto": "#0369A1", "borda": "#0EA5E9", "titulo": "#075985"},
        "verde":  {"fundo": "#F0FDF4", "texto": "#15803D", "borda": "#22C55E", "titulo": "#166534"},
        "cinza":  {"fundo": "#F8FAFC", "texto": "#334155", "borda": "#94A3B8", "titulo": "#64748B"},
    }
    
    # URLs de Exportação
    URL_PROD = "https://docs.google.com/spreadsheets/d/11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v/export?format=xlsx"
    URL_CONS = "https://drive.google.com/uc?id=1VEeL3fV8SyKo9j5YMqvjUu98dZxtMtKA&export=download"
    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/export?format=csv"


# ====================================================
# BLOCO 2: COMPONENTES VISUAIS
# ====================================================

class Visual:
    """Responsável por renderizar componentes na tela."""
    
    @staticmethod
    def criar_card(titulo: str, valor: str, tema: str = "azul") -> str:
        cores = Configuracoes.TEMAS_CARD.get(tema, Configuracoes.TEMAS_CARD["azul"])
        return f"""
        <div style="
            background-color: {cores['fundo']}; padding: 20px; border-radius: 10px;
            border-left: 6px solid {cores['borda']}; box-shadow: 0 4px 6px rgba(0,0,0,0.1); margin-bottom: 15px;
            transition: transform 0.2s;" 
            onmouseover="this.style.transform='scale(1.02)'" onmouseout="this.style.transform='scale(1)'">
            <p style="margin: 0; font-size: 14px; color: {cores['titulo']};"><b>{titulo}</b></p>
            <h2 style="margin: 0; padding-top: 5px; color: {cores['texto']}; font-weight: 900;">{valor}</h2>
        </div>
        """


# ====================================================
# BLOCO 3: PROCESSAMENTO DE DADOS (VETORIZADO)
# ====================================================

class ProcessadorDeDados:
    
    @staticmethod
    def tratar_planos_vetorizado(df: pd.DataFrame) -> pd.DataFrame:
        """Processa os nomes dos planos de forma vetorizada."""
        if not {"PLANO TV", "PLANO INTERNET"}.issubset(df.columns):
            return df
            
        vazios = ["-", "nan", "None", "", "NaN"]
        
        tv = df["PLANO TV"].astype(str).str.strip().replace("SERVIÇOS AVANÇADOS", "CLARO TV+ BOX")
        
        internet = df["PLANO INTERNET"].astype(str).str.strip()
        partes = internet.str.split(".", n=1, expand=True)
        internet_tratada = partes[0].str.strip()
        
        tv_extraida = partes[1].str.strip() if partes.shape[1] > 1 else pd.Series([""] * len(df))
        tv_final = np.where(tv.isin(vazios), tv_extraida, tv)
        
        tv_is_empty = pd.Series(tv_final).isin(vazios)
        int_is_empty = internet_tratada.isin(vazios)
        
        nome_final = np.where(
            ~tv_is_empty & ~int_is_empty, tv_final + " & " + internet_tratada,
            np.where(~tv_is_empty, tv_final,
            np.where(~int_is_empty, internet_tratada, "Sem Tipo"))
        )
        
        df["PLANO TV"] = tv_final
        df["PLANO INTERNET"] = internet_tratada
        df["TIPO SERVIÇO"] = nome_final
        df["QTDE_CONSULTIVO"] = (~df[["PLANO TV", "PLANO INTERNET"]].isin(vazios)).sum(axis=1)
        
        return df

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=600)
    def baixar_e_processar():
        """Faz o download e processamento matematico dos dados."""
        
        # 1. Download de Produção
        try: 
            prod_raw = pd.read_excel(Configuracoes.URL_PROD, sheet_name=None, engine="openpyxl")
        except Exception as e: 
            st.error(f"Erro ao baixar Produção: {e}")
            prod_raw = {}
        
        # 2. Download do CSV do Google Drive (ROBUSTO)
        cons_raw = {}
        try:
            resposta = requests.get(Configuracoes.URL_CONS)
            resposta.raise_for_status() # Verifica se a URL não está quebrada (erro 404/403)
            
            # Se o Google enviou uma tela de aviso HTML em vez do CSV
            if "text/html" in resposta.headers.get("Content-Type", ""):
                st.error("❌ O Google Drive bloqueou o download automático do CSV (Aviso de Antivírus ou Arquivo Restrito).")
            else:
                try:
                    # Tenta ler no padrão internacional (Vírgula e UTF-8)
                    df_csv = pd.read_csv(StringIO(resposta.text), sep=",")
                except:
                    # Se falhar, tenta no padrão brasileiro (Ponto e Vírgula e UTF-8)
                    df_csv = pd.read_csv(BytesIO(resposta.content), sep=";", encoding="utf-8", engine="python")
                
                cons_raw = {"Aba_Dinamica": df_csv}
                
        except Exception as e: 
            st.error(f"❌ Erro ao baixar ou ler o arquivo CSV do Google Drive: {e}")
        
        # 3. Download da Lista de Ativos
        try: 
            ativos = pd.read_csv(Configuracoes.URL_ATIVOS)
            ativos.columns = ativos.columns.str.strip()
        except Exception as e: 
            st.error(f"Erro ao baixar ATIVOS: {e}")
            ativos = pd.DataFrame()

        # Extração Segura da Aba Dinâmica
        if cons_raw and isinstance(cons_raw, dict):
            nome_aba_existente = list(cons_raw.keys())[0]
            cons = cons_raw[nome_aba_existente]
        else:
            cons = pd.DataFrame()

        if cons.empty:
            return prod_raw, {"Consultivo": pd.DataFrame()}, ativos
            
        cons.columns = cons.columns.str.strip()

        # 4. Processamento de Produtos
        if "OBSERVACAO" in cons.columns:
            cons["LISTA_PRODUTOS"] = cons["OBSERVACAO"].fillna("").astype(str).str.findall(r"\b\d{9,12}\b")
            cons["QTDE_PRODUTOS"] = cons["LISTA_PRODUTOS"].apply(len)
        else:
            cons["LISTA_PRODUTOS"] = [[] for _ in range(len(cons))]
            cons["QTDE_PRODUTOS"] = 0

        # 5. Tratamento Vetorizado de Serviços
        cons = ProcessadorDeDados.tratar_planos_vetorizado(cons)

        # 6. Cálculos Matemáticos (Equipamentos)
        if "TIPO SERVIÇO" in cons.columns:
            tipo_servico = cons["TIPO SERVIÇO"].fillna("").astype(str)
        else:
            tipo_servico = pd.Series([""] * len(cons), dtype=str)

        qtde_prod = cons["QTDE_PRODUTOS"].fillna(0).astype(int)
        
        is_combinado = tipo_servico.str.contains("&", case=False, regex=False)
        tem_tv = tipo_servico.str.contains("TV", case=False, regex=False)
        tem_virtua = tipo_servico.str.contains("MEGA|GIGA", case=False, regex=True)
        
        cons["QTDE_TV"] = np.where(is_combinado, tem_tv.astype(int), tem_tv.astype(int) * qtde_prod)
        cons["QTDE_VIRTUA"] = np.where(is_combinado, tem_virtua.astype(int), tem_virtua.astype(int) * qtde_prod)
        cons["QTDE_MESH"] = qtde_prod - cons["QTDE_TV"] - cons["QTDE_VIRTUA"]
        cons["QTDE_MESH"] = cons["QTDE_MESH"].clip(lower=0)

        # 7. Merge com Ativos
        if not ativos.empty and "Login" in ativos.columns and "LOGIN NETSALES" in cons.columns:
            ativos_limpo = ativos[["Login", "Monitor", "U.N.", "Base"]].drop_duplicates(subset=["Login"])
            cons = pd.merge(cons, ativos_limpo, left_on="LOGIN NETSALES", right_on="Login", how="left").drop(columns=["Login"])
            cons["Monitor"] = cons["Monitor"].fillna("Não Identificado")

        return prod_raw, {"Consultivo": cons}, ativos


# ====================================================
# BLOCO 4: INTERFACE E LÓGICA DE ATUALIZAÇÃO
# ====================================================

st.set_page_config(page_title="Atualização de Dados", page_icon="🔁", layout="wide")
st.title("🔁 Central de Atualização de Dados")

def executar_atualizacao():
    status = st.empty()
    barra = st.progress(0)
    
    try:
        status.info("⏳ Fazendo download e processando dados em nuvem. Aguarde...")
        barra.progress(20)
        
        ProcessadorDeDados.baixar_e_processar.clear()
        
        p_raw, c_raw, a_raw = ProcessadorDeDados.baixar_e_processar()
        barra.progress(90)
        
        st.session_state["dados_prod"] = p_raw
        st.session_state["dados_cons"] = c_raw
        st.session_state["dados_ativos"] = a_raw
        st.session_state["ultima_atualizacao"] = datetime.now(Configuracoes.FUSO)
        
        barra.progress(100)
        time.sleep(0.5)
        
        status.empty()
        barra.empty()
        return True
        
    except Exception as e:
        status.empty()
        barra.empty()
        st.error(f"❌ Ocorreu um erro crítico durante a atualização: {str(e)}")
        return False

if "dados_cons" not in st.session_state:
    executar_atualizacao()

col_btn, _ = st.columns([1, 4])
with col_btn:
    if st.button("🔄 Atualizar Agora", use_container_width=True, type="primary"):
        if executar_atualizacao():
            st.success("✅ Dados atualizados com sucesso e disponíveis para todas as páginas!")

st.divider()

# ====================================================
# BLOCO 5: EXIBIÇÃO EM TABS (ABAS)
# ====================================================

dados_prod = st.session_state.get("dados_prod", {})
df_prod = dados_prod["Prod"] if isinstance(dados_prod, dict) and "Prod" in dados_prod else pd.DataFrame()

dados_cons = st.session_state.get("dados_cons", {})
df_cons = dados_cons["Consultivo"] if isinstance(dados_cons, dict) and "Consultivo" in dados_cons else pd.DataFrame()

ultima_data = st.session_state.get("ultima_atualizacao")
hora_str = ultima_data.strftime("%d/%m/%Y às %H:%M:%S") if isinstance(ultima_data, datetime) else "Nunca atualizado"

aba1, aba2 = st.tabs(["📊 Pré-visualização: Produção", "📋 Pré-visualização: Consultivos"])

with aba1:
    c1, c2, c3 = st.columns(3)
    with c1: st.markdown(Visual.criar_card("Total Registros", f"{len(df_prod):,}".replace(",", "."), "azul"), unsafe_allow_html=True)
    with c2: st.markdown(Visual.criar_card("Total Colunas", f"{len(df_prod.columns)}", "cinza"), unsafe_allow_html=True)
    with c3: st.markdown(Visual.criar_card("Última Sincronização", hora_str, "verde"), unsafe_allow_html=True)
    
    if not df_prod.empty:
        st.dataframe(df_prod.head(100), use_container_width=True, height=400, hide_index=True)
    else:
        st.warning("⚠️ Nenhuma aba chamada 'Prod' encontrada.")

with aba2:
    c4, c5, c6 = st.columns(3)
    with c4: st.markdown(Visual.criar_card("Total Registros", f"{len(df_cons):,}".replace(",", "."), "azul"), unsafe_allow_html=True)
    with c5: st.markdown(Visual.criar_card("Total Colunas", f"{len(df_cons.columns)}", "cinza"), unsafe_allow_html=True)
    with c6: st.markdown(Visual.criar_card("Última Sincronização", hora_str, "verde"), unsafe_allow_html=True)
        
    if not df_cons.empty:
        st.dataframe(df_cons.head(100), use_container_width=True, height=400, hide_index=True)
    else:
        st.warning("⚠️ Nenhuma aba encontrada ou o arquivo CSV está vazio.")