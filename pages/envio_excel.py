"""
envio_excel.py — Central de Atualização de Dados
================================================
Ponto único de atualização das bases do portal: download e tratamento
das planilhas de Produção e Consultivos do Google, publicados na sessão
(``dados_prod`` / ``dados_cons`` / ``dados_ativos``) para os painéis de
Produtividade, Quantidade de O.S. e Consultivos.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO

import numpy as np
import pandas as pd
import requests
import streamlit as st

from components.componentes import (
    aplicar_estilo,
    render_dataframe,
    render_hero,
    render_kpi,
    render_section_header,
)

logger = logging.getLogger(__name__)

# set_page_config deve ser o primeiro comando Streamlit da página.
st.set_page_config(page_title="Atualização de Dados", page_icon="🔁", layout="wide")
aplicar_estilo()


# ════════════════════════════════════════════════════
# CONFIGURAÇÕES E PROCESSAMENTO (BASES EM NUVEM)
# ════════════════════════════════════════════════════
class Configuracoes:
    """Parâmetros e configurações gerais da aplicação."""

    FUSO = timezone(timedelta(hours=-3))  # Fuso horário de Brasília

    # URLs de Exportação
    URL_PROD = "https://docs.google.com/spreadsheets/d/11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v/export?format=xlsx"
    URL_CONS = "https://drive.google.com/uc?id=1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs&export=download"
    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/export?format=csv"

    # Valores considerados "vazios" — centralizado aqui para ser usado em todo o projeto
    VAZIOS = {"-", "nan", "None", "", "NaN"}


class ProcessadorDeDados:
    @staticmethod
    def _normalizar_serie(serie: pd.Series) -> pd.Series:
        """
        Utilitário interno: converte uma Series para string, remove espaços
        e substitui qualquer valor da lista VAZIOS por string vazia ''.
        Garante que np.nan também seja tratado.
        """
        return (
            serie.astype(str)
            .str.strip()
            .replace(
                list(Configuracoes.VAZIOS), ""
            )  # Substitui strings vazias conhecidas
            .fillna("")  # Garante que np.nan vire ""
        )

    @staticmethod
    def tratar_planos_vetorizado(df: pd.DataFrame) -> pd.DataFrame:
        """
        Processa e limpa os nomes dos planos de forma vetorizada.
        Garante contagem correta em QTDE_CONSULTIVO.

        Regras:
        - Se PLANO TV for vazio, tenta extrair do campo PLANO INTERNET (após o ponto)
        - TIPO SERVIÇO = TV & Internet | só TV | só Internet | Sem Tipo
        - QTDE_CONSULTIVO = quantidade de serviços ativos (0, 1 ou 2)
        """
        # 1. Cláusula de guarda
        if not {"PLANO TV", "PLANO INTERNET"}.issubset(df.columns):
            return df

        # ----------------------------------------------------------------
        # 2. Limpeza e normalização do PLANO TV
        # ----------------------------------------------------------------
        tv_bruta = (
            df["PLANO TV"]
            .astype(str)
            .str.strip()
            .replace("SERVIÇOS AVANÇADOS", "CLARO TV+ BOX")  # Substituição de negócio
        )

        # ----------------------------------------------------------------
        # 3. Limpeza e split do PLANO INTERNET
        #    Alguns registros chegam como: "500 MEGA.CLARO TV+ BOX"
        #    → internet_limpa = "500 MEGA"
        #    → tv_do_internet  = "CLARO TV+ BOX"
        # ----------------------------------------------------------------
        internet_bruta = df["PLANO INTERNET"].astype(str).str.strip()
        partes = internet_bruta.str.split(".", n=1, expand=True)

        internet_limpa = ProcessadorDeDados._normalizar_serie(partes[0])

        # TV embutida no campo internet (parte após o ponto), se existir
        tv_do_internet = (
            ProcessadorDeDados._normalizar_serie(partes[1])
            if partes.shape[1] > 1
            else pd.Series("", index=df.index, dtype=str)
        )

        # ----------------------------------------------------------------
        # 4. Resolução final do PLANO TV:
        #    Usa o valor original, mas se for vazio, pega o que veio do campo internet
        # ----------------------------------------------------------------
        tv_normalizada = ProcessadorDeDados._normalizar_serie(tv_bruta)

        tv_limpa = pd.Series(
            np.where(tv_normalizada != "", tv_normalizada, tv_do_internet),
            index=df.index,
            dtype=str,
        )

        # ----------------------------------------------------------------
        # 5. Flags booleanas (base para contagem e tipo de serviço)
        # ----------------------------------------------------------------
        tem_tv = tv_limpa != ""
        tem_internet = internet_limpa != ""

        # ----------------------------------------------------------------
        # 6. QTDE_CONSULTIVO — contagem robusta e explícita
        #    Cada serviço ativo contribui com +1 (máximo 2)
        # ----------------------------------------------------------------
        df["QTDE_CONSULTIVO"] = tem_tv.astype(int) + tem_internet.astype(int)

        # ----------------------------------------------------------------
        # 7. TIPO SERVIÇO — np.select deixa as condições legíveis
        # ----------------------------------------------------------------
        condicoes = [
            tem_tv & tem_internet,  # Tem ambos
            tem_tv & ~tem_internet,  # Só TV
            ~tem_tv & tem_internet,  # Só Internet
        ]
        opcoes = [
            tv_limpa + " & " + internet_limpa,
            tv_limpa,
            internet_limpa,
        ]
        df["TIPO SERVIÇO"] = np.select(condicoes, opcoes, default="Sem Tipo")

        # ----------------------------------------------------------------
        # 8. Persiste as colunas limpas no DataFrame
        # ----------------------------------------------------------------
        df["PLANO TV"] = tv_limpa
        df["PLANO INTERNET"] = internet_limpa

        return df

    # ------------------------------------------------------------------

    @staticmethod
    @st.cache_data(show_spinner=False, ttl=600)
    def baixar_e_processar():
        """Faz o download e processamento matemático dos dados."""

        # 1. Download de Produção
        try:
            prod_raw = pd.read_excel(
                Configuracoes.URL_PROD, sheet_name=None, engine="openpyxl"
            )
        except Exception as e:
            st.error(f"Erro ao baixar Produção: {e}")
            prod_raw = {}

        # 2. Download do CSV Consultivo (Google Drive)
        cons_raw = {}
        try:
            resposta = requests.get(Configuracoes.URL_CONS)
            resposta.raise_for_status()

            if "text/html" in resposta.headers.get("Content-Type", ""):
                st.error(
                    "❌ O Google Drive bloqueou o download automático do CSV "
                    "(Aviso de Antivírus ou Arquivo Restrito)."
                )
            else:
                try:
                    df_csv = pd.read_csv(StringIO(resposta.text), sep=",")
                except Exception:
                    df_csv = pd.read_csv(
                        BytesIO(resposta.content),
                        sep=";",
                        encoding="utf-8",
                        engine="python",
                    )
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

        # Extração segura da aba dinâmica
        if cons_raw and isinstance(cons_raw, dict):
            cons = cons_raw[list(cons_raw.keys())[0]]
        else:
            cons = pd.DataFrame()

        if cons.empty:
            return prod_raw, {"Consultivo": pd.DataFrame()}, ativos

        cons.columns = cons.columns.str.strip()

        # 4. Processamento de Produtos (códigos numéricos na OBSERVACAO)
        if "OBSERVACAO" in cons.columns:
            cons["LISTA_PRODUTOS"] = (
                cons["OBSERVACAO"].fillna("").astype(str).str.findall(r"\b\d{9,12}\b")
            )
            cons["QTDE_PRODUTOS"] = cons["LISTA_PRODUTOS"].apply(len)
        else:
            cons["LISTA_PRODUTOS"] = [[] for _ in range(len(cons))]
            cons["QTDE_PRODUTOS"] = 0

        # 5. Tratamento vetorizado de planos (TV / Internet / Tipo)
        cons = ProcessadorDeDados.tratar_planos_vetorizado(cons)

        # 6. Cálculos de Equipamentos
        tipo_servico = (
            cons.get("TIPO SERVIÇO", pd.Series("", index=cons.index))
            .fillna("")
            .astype(str)
        )
        qtde_prod = cons["QTDE_PRODUTOS"].fillna(0).astype(int)

        is_combinado = tipo_servico.str.contains("&", case=False, regex=False)
        tem_tv = tipo_servico.str.contains("TV", case=False, regex=False)
        tem_virtua = tipo_servico.str.contains(r"MEGA|GIGA", case=False, regex=True)

        # Quando é combinado (TV + Internet), cada serviço conta como 1 equipamento
        # Quando é simples, multiplica pela qtde de produtos (ex: mesh)
        cons["QTDE_TV"] = np.where(
            is_combinado, tem_tv.astype(int), tem_tv.astype(int) * qtde_prod
        )
        cons["QTDE_VIRTUA"] = np.where(
            is_combinado, tem_virtua.astype(int), tem_virtua.astype(int) * qtde_prod
        )
        cons["QTDE_MESH"] = (qtde_prod - cons["QTDE_TV"] - cons["QTDE_VIRTUA"]).clip(
            lower=0
        )

        # 7. Merge com Ativos
        if (
            not ativos.empty
            and "Login" in ativos.columns
            and "LOGIN NETSALES" in cons.columns
        ):
            colunas_ativos = [
                col
                for col in ("Login", "Monitor", "U.N.", "Base")
                if col in ativos.columns
            ]
            ativos_limpo = ativos[colunas_ativos].copy()
            # Chave caixa/espaço-segura dos dois lados: a aba chega com login
            # maiúsculo, mas o CSV do consultivo não garante o mesmo formato.
            ativos_limpo["Login"] = (
                ativos_limpo["Login"].fillna("").astype(str).str.strip().str.upper()
            )
            ativos_limpo = ativos_limpo.drop_duplicates(subset=["Login"])
            cons = cons.copy()
            cons["__LOGIN_ATIVOS"] = (
                cons["LOGIN NETSALES"].fillna("").astype(str).str.strip().str.upper()
            )
            cons = pd.merge(
                cons,
                ativos_limpo,
                left_on="__LOGIN_ATIVOS",
                right_on="Login",
                how="left",
                suffixes=("", "_ativos"),
            ).drop(columns=["Login", "__LOGIN_ATIVOS"])
        if "Monitor" in cons.columns:
            cons["Monitor"] = cons["Monitor"].fillna("Não Identificado")

        return prod_raw, {"Consultivo": cons}, ativos


# ════════════════════════════════════════════════════
# SINCRONIZAÇÃO COM A NUVEM
# ════════════════════════════════════════════════════
def executar_atualizacao() -> bool:
    """Baixa Produção/Consultivos/Ativos e publica o resultado na sessão."""
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
        st.error(f"❌ Ocorreu um erro crítico durante a atualização: {e}")
        return False


def _fmt_int(valor: int) -> str:
    return f"{int(valor):,}".replace(",", ".")


def _render_previa(
    df: pd.DataFrame,
    *,
    titulo: str,
    icone: str,
    data_sync: str,
    hora_sync: str,
    aviso_vazio: str,
) -> None:
    """KPIs + amostra de uma base em nuvem (mesmo layout das duas abas)."""
    render_section_header("table_view", titulo)
    c1, c2, c3 = st.columns(3)
    render_kpi(c1, "Total Registros", _fmt_int(len(df)), tema="azul")
    render_kpi(c2, "Total Colunas", str(len(df.columns)), tema="cinza")
    render_kpi(c3, "Última Sincronização", data_sync, hora_sync, tema="verde")

    if df.empty:
        st.warning(aviso_vazio)
        return
    render_dataframe(
        df.head(100),
        titulo=titulo.replace("Pré-visualização", "Amostra"),
        icone=icone,
        badge=f"Top {min(100, len(df))} de {_fmt_int(len(df))}",
        height=400,
    )


def _render_secao_nuvem() -> None:
    """Bases compartilhadas baixadas do Google (Produção/Consultivos)."""
    render_section_header("cloud_sync", "Bases compartilhadas", "Google Sheets")

    # Carrega automaticamente na primeira visita.
    if "dados_cons" not in st.session_state:
        executar_atualizacao()

    col_btn, _ = st.columns([1, 4])
    with col_btn:
        if st.button("🔄 Atualizar Agora", use_container_width=True, type="primary"):
            if executar_atualizacao():
                st.success(
                    "✅ Dados atualizados com sucesso e disponíveis "
                    "para todas as páginas!"
                )

    dados_prod = st.session_state.get("dados_prod", {})
    df_prod = (
        dados_prod["Prod"]
        if isinstance(dados_prod, dict) and "Prod" in dados_prod
        else pd.DataFrame()
    )

    dados_cons = st.session_state.get("dados_cons", {})
    df_cons = (
        dados_cons["Consultivo"]
        if isinstance(dados_cons, dict) and "Consultivo" in dados_cons
        else pd.DataFrame()
    )

    ultima_data = st.session_state.get("ultima_atualizacao")
    data_sync = (
        ultima_data.strftime("%d/%m/%Y") if isinstance(ultima_data, datetime) else "—"
    )
    hora_sync = (
        ultima_data.strftime("às %H:%M:%S")
        if isinstance(ultima_data, datetime)
        else "Ainda não atualizado"
    )

    aba_prod, aba_cons = st.tabs(
        ["📊 Pré-visualização: Produção", "📋 Pré-visualização: Consultivos"]
    )
    with aba_prod:
        _render_previa(
            df_prod,
            titulo="Pré-visualização da Produção",
            icone="precision_manufacturing",
            data_sync=data_sync,
            hora_sync=hora_sync,
            aviso_vazio="⚠️ Nenhuma aba chamada 'Prod' encontrada.",
        )
    with aba_cons:
        _render_previa(
            df_cons,
            titulo="Pré-visualização de Consultivos",
            icone="shopping_bag",
            data_sync=data_sync,
            hora_sync=hora_sync,
            aviso_vazio="⚠️ Nenhuma aba encontrada ou o arquivo CSV está vazio.",
        )


def main() -> None:
    render_hero(
        "Central de Atualização de Dados",
        "Sincronização das bases compartilhadas de Produção e Consultivos",
        "Bases compartilhadas",
    )
    _render_secao_nuvem()


if __name__ == "__main__":
    main()
