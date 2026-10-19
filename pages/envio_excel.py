import logging
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO, StringIO
from pathlib import Path

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
from components.robo_local import renderizar_robo_local

logger = logging.getLogger(__name__)

# ====================================================
# BLOCO 1: CONFIGURAÇÕES GLOBAIS
# ====================================================

# ✅ set_page_config SEMPRE deve ser o primeiro comando Streamlit
st.set_page_config(page_title="Atualização de Dados", page_icon="🔁", layout="wide")

# ✅ aplicar_estilo() DEPOIS do set_page_config
aplicar_estilo()


class Configuracoes:
    """Parâmetros e configurações gerais da aplicação."""

    FUSO = timezone(timedelta(hours=-3))  # Fuso horário de Brasília

    # URLs de Exportação
    URL_PROD = "https://docs.google.com/spreadsheets/d/11Dp9WdZYUrT_LBvfo07Mi8muKXZykU7v/export?format=xlsx"
    URL_CONS = "https://drive.google.com/uc?id=1YOWJ0HuGcEP2vJaZwl2kcgrtNgsoMBDs&export=download"
    URL_ATIVOS = "https://docs.google.com/spreadsheets/d/1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg/export?format=csv"

    # Valores considerados "vazios" — centralizado aqui para ser usado em todo o projeto
    VAZIOS = {"-", "nan", "None", "", "NaN"}


# ====================================================
# BLOCO 3: PROCESSAMENTO DE DADOS (VETORIZADO)
# ====================================================


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


# ====================================================
# BLOCO 4: INTERFACE E LÓGICA DE ATUALIZAÇÃO
# ====================================================
render_hero(
    "Central de Atualização de Dados",
    "Sincronização e gestão de bases operacionais",
    "Bases compartilhadas",
)


# ====================================================
# BLOCO 4.1: ROBÔ LOCAL (PASTA MONITORADA)
# ====================================================


def _lista_ativos_para_etl() -> pd.DataFrame:
    """Lista de ativos usada pelo ETL do robô — sessão primeiro, Sheets depois.

    O robô publica ``df_memoria`` assim que a pasta monitorada muda, quase
    sempre antes de qualquer download da nuvem nesta sessão. Quando a lista
    vinha somente de ``session_state["dados_ativos"]``, o merge rodava vazio e
    a base era publicada com ``SEM MONITOR``/``NÃO MAPEADO`` — e a Quebra de
    Agenda reutilizava essa base sem vínculo. Com o fallback, o ETL busca a
    mesma aba ``lista_ativos`` das demais páginas (cache de 5 min) e só
    degrada quando a planilha está realmente inacessível.
    """
    ativos = st.session_state.get("dados_ativos")
    if isinstance(ativos, pd.DataFrame) and not ativos.empty:
        return ativos
    try:
        from pages.quebra import DataLoader as DataLoaderQuebra

        buscados = DataLoaderQuebra.buscar_gsheets()
    except Exception:
        logger.exception("Falha ao buscar a lista_ativos para o ETL local.")
        return pd.DataFrame()
    return buscados if isinstance(buscados, pd.DataFrame) else pd.DataFrame()


def _etl_base_local(bruto: pd.DataFrame, ativos: pd.DataFrame) -> pd.DataFrame | None:
    """Reaproveita o pipeline da Quebra para publicar uma base pronta.

    A base bruta continua disponível em ``df_memoria_raw``; ``df_memoria`` recebe
    a versão tratada que os painéis operacionais consomem.
    """
    if bruto is None or bruto.empty:
        return None
    try:
        from components import base_operacional as bo

        return bo.preparar_base_quebra(
            bruto,
            ativos,
            ativos.attrs.get("fonte_ativos", ""),
            ativos.attrs.get("erro_ativos", ""),
        )
    except Exception:
        # Nunca derrubar a Central por causa de uma base fora do layout da Quebra.
        logger.exception("ETL local falhou; publicando a base bruta.")
        return bruto


with st.expander("Conectar o Downloads deste computador", expanded=False):
    st.info(
        "Por segurança, o navegador não permite que o app publicado leia pastas "
        "do seu computador. O agente local monitora o Downloads no Windows e "
        "envia a exportação para esta Central."
    )
    st.markdown(
        "**Configuração inicial (uma vez):** instale o projeto no computador, "
        "instale `requirements-agent.txt` e o Chromium do Playwright conforme o "
        "guia `docs/AGENTE_DOWNLOADS.md`.\n\n"
        "**Para iniciar o monitoramento:** execute "
        "`scripts\\iniciar_agente_downloads.bat` e mantenha a janela do agente "
        "aberta. Entre no app na janela do navegador que abrir; os arquivos "
        "`Atividades-*.csv` ou Excel serão enviados quando estiverem completos."
    )

renderizar_robo_local(
    etl_fn=_etl_base_local,
    gsheets_fn=_lista_ativos_para_etl,
    ciclos_estabilidade=2,
)

# Prévia imediata do que o robô publicou para os demais painéis.
df_local = st.session_state.get("df_memoria")
if (
    isinstance(df_local, pd.DataFrame)
    and not df_local.empty
    and st.session_state.get("robo_ultimo_processado_path")
):
    caminho_local = Path(st.session_state["robo_ultimo_processado_path"])
    render_section_header(
        "table_view",
        "Prévia da base local",
        f"{len(df_local):,} linhas".replace(",", "."),
    )
    st.caption(
        f"Última leitura: `{caminho_local.name}` · "
        f"{len(df_local.columns)} coluna(s) · publicada em `df_memoria`."
    )
    # Vínculo vazio não pode passar despercebido: é exatamente o sintoma de
    # "tudo SEM MONITOR" que o merge da lista_ativos produzia em silêncio.
    if not int(df_local.attrs.get("diag_vinculados", 0) or 0):
        erro_local = str(df_local.attrs.get("erro_ativos", "") or "").strip()
        st.warning(
            "⚠️ A base publicada não vinculou nenhum login à `lista_ativos`"
            + (f" — {erro_local}" if erro_local else ".")
            + " Monitores e técnicos aparecem como `SEM MONITOR`/`NÃO MAPEADO` "
            "até o vínculo ser concluído; use **🔗 Atualizar Lista de Ativos** "
            "na Quebra de Agenda ou refaça a sincronização."
        )
    render_dataframe(
        df_local.head(50),
        titulo="Amostra da Base Publicada pelo Robô",
        icone="smart_toy",
        badge=f"Top {min(50, len(df_local))} de {len(df_local):,}".replace(",", "."),
        height=340,
    )

st.divider()
render_section_header("cloud_sync", "Bases compartilhadas", "Google Sheets")


def executar_atualizacao() -> bool:
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


# Carrega automaticamente na primeira visita
if "dados_cons" not in st.session_state:
    executar_atualizacao()

col_btn, _ = st.columns([1, 4])
with col_btn:
    if st.button("🔄 Atualizar Agora", use_container_width=True, type="primary"):
        if executar_atualizacao():
            st.success(
                "✅ Dados atualizados com sucesso e disponíveis para todas as páginas!"
            )

st.divider()

# ====================================================
# BLOCO 5: EXIBIÇÃO EM TABS
# ====================================================

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

aba1, aba2 = st.tabs(
    ["📊 Pré-visualização: Produção", "📋 Pré-visualização: Consultivos"]
)

# ---------- Aba Produção ----------
with aba1:
    render_section_header("table_view", "Pré-visualização da Produção")
    c1, c2, c3 = st.columns(3)
    render_kpi(
        c1, "Total Registros", f"{len(df_prod):,}".replace(",", "."), tema="azul"
    )
    render_kpi(c2, "Total Colunas", str(len(df_prod.columns)), tema="cinza")
    render_kpi(c3, "Última Sincronização", data_sync, hora_sync, tema="verde")

    if not df_prod.empty:
        render_dataframe(
            df_prod.head(100),
            titulo="Amostra da Base de Produção",
            icone="precision_manufacturing",
            badge=f"Top {min(100, len(df_prod))} de {len(df_prod):,}".replace(",", "."),
            height=400,
        )
    else:
        st.warning("⚠️ Nenhuma aba chamada 'Prod' encontrada.")

# ---------- Aba Consultivo ----------
with aba2:
    render_section_header("table_view", "Pré-visualização de Consultivos")
    c4, c5, c6 = st.columns(3)
    render_kpi(
        c4, "Total Registros", f"{len(df_cons):,}".replace(",", "."), tema="azul"
    )
    render_kpi(c5, "Total Colunas", str(len(df_cons.columns)), tema="cinza")
    render_kpi(c6, "Última Sincronização", data_sync, hora_sync, tema="verde")

    if not df_cons.empty:
        render_dataframe(
            df_cons.head(100),
            titulo="Amostra da Base de Consultivos",
            icone="shopping_bag",
            badge=f"Top {min(100, len(df_cons))} de {len(df_cons):,}".replace(",", "."),
            height=400,
        )
    else:
        st.warning("⚠️ Nenhuma aba encontrada ou o arquivo CSV está vazio.")
