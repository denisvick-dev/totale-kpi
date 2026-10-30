"""
components/base_operacional.py
==============================
Fonte única do tratamento da base operacional (exportação "Atividades")
consumida por **rota_inicial.py**.

Fluxo (upload manual):
    1. o usuário envia o arquivo (.xlsx/.xls/.csv) na Central de
       Atualização (``envio_excel.py``) ou direto no painel;
    2. :func:`gerar_bases_upload` lê o arquivo e gera a base tratada,
       vinculada à aba ``lista_ativos``;
    3. ``components/upload_base.py`` publica a base na sessão, na
       chave que o painel já consome.

O módulo não depende de Streamlit para ler/tratar dados — a interface
de upload vive em ``components/upload_base.py``. Quando o Streamlit
está disponível, a leitura da lista de ativos tenta a conta de serviço,
depois a conexão nativa e, por fim, o CSV público da planilha.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
import unicodedata
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTES COMPARTILHADAS
# ═══════════════════════════════════════════════════════════════════════
COL_TOTAL = "TOTAL DE TAREFAS"
COL_TECNICO = "TÉCNICO"
COL_MONITOR = "MONITOR"
COL_REGIAO = "REGIÃO"
COL_STATUS = "STATUS CONTRATO"
COL_CONTRATO = "CONTRATO"
COL_LOGIN = "LOGIN"

EXTENSOES_ACEITAS: tuple[str, ...] = (".xlsx", ".xls", ".csv")

# ═══════════════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════════════
class Utils:
    """Normalização e busca de colunas usadas por todas as bases."""

    @staticmethod
    def remover_acentos(valor: Any) -> str:
        if valor is None or (isinstance(valor, float) and pd.isna(valor)):
            return ""
        return (
            unicodedata.normalize("NFKD", str(valor))
            .encode("ASCII", "ignore")
            .decode("ASCII")
        )

    @staticmethod
    def normalizar_chave(serie: pd.Series) -> pd.Series:
        s = serie.copy()
        return (
            s.where(s.notna(), "")
            .astype(str)
            .str.strip()
            .str.upper()
            .map(Utils.remover_acentos)
        )

    @staticmethod
    def normalizar_login(serie: pd.Series) -> pd.Series:
        return Utils.normalizar_chave(serie).str.replace(r"\.0$", "", regex=True)

    @staticmethod
    def buscar_coluna(df: pd.DataFrame, aliases: Sequence[str]) -> str | None:
        if df is None or df.empty:
            return None
        cols_map = {Utils.normalizar_chave(pd.Series([c]))[0]: c for c in df.columns}
        for alias in aliases:
            chave = Utils.normalizar_chave(pd.Series([alias]))[0]
            if chave in cols_map:
                return cols_map[chave]
        return None


# ╀═════════════════════════════════════════════════════════════════════
# LEITURA DE ARQUIVOS
# ╀═════════════════════════════════════════════════════════════════════
def ler_arquivo_bytes(
    conteudo: bytes, nome: str, dtype: Any | None = None
) -> pd.DataFrame:
    """Lê Excel/CSV a partir de bytes (upload manual)."""
    if not conteudo:
        raise ValueError("O arquivo enviado está vazio.")

    nome = (nome or "").lower()
    buffer = io.BytesIO(conteudo)

    if nome.endswith((".xlsx", ".xlsm")):
        return pd.read_excel(buffer, engine="openpyxl", dtype=dtype)
    if nome.endswith(".xls"):
        try:
            return pd.read_excel(buffer, dtype=dtype)
        except Exception:
            buffer.seek(0)
            return pd.read_excel(buffer, engine="openpyxl", dtype=dtype)
    if nome.endswith(".csv"):
        return _ler_csv(buffer, dtype=dtype)

    raise ValueError(
        f"Formato não suportado: {nome or '(sem nome)'}. Use .xlsx, .xls ou .csv."
    )


def _ler_csv(buffer: io.BytesIO, dtype: Any | None = None) -> pd.DataFrame:
    buffer.seek(0)
    amostra = buffer.read(8192)
    buffer.seek(0)

    separadores: list[str | None] = []
    try:
        separadores.append(
            csv.Sniffer().sniff(amostra.decode("utf-8", "ignore")).delimiter
        )
    except Exception:
        pass
    separadores.extend([None, ";", ",", "\t"])

    erros: list[Exception] = []
    for sep in separadores:
        for encoding in ("utf-8-sig", "latin1"):
            try:
                buffer.seek(0)
                return pd.read_csv(
                    buffer,
                    sep=sep,
                    encoding=encoding,
                    engine="python" if sep is None else "c",
                    dtype=dtype,
                )
            except Exception as exc:  # tenta a próxima combinação
                erros.append(exc)
                continue
    raise ValueError(
        f"Não foi possível interpretar o CSV: {erros[-1] if erros else 'erro desconhecido'}"
    )


# ═══════════════════════════════════════════════════════════════════════
# LISTA DE ATIVOS (GOOGLE SHEETS)
# ═══════════════════════════════════════════════════════════════════════
def normalizar_lista_ativos(raw: pd.DataFrame) -> pd.DataFrame:
    """Padroniza a aba ``lista_ativos`` em Login / Técnico / Monitor / Base."""
    if raw is None or raw.empty:
        return pd.DataFrame()

    raw = raw.copy()
    raw.columns = raw.columns.astype(str).str.strip()

    rename_map: dict[str, str] = {}
    for col in raw.columns:
        cu = col.upper().strip().replace(".", "").replace("_", " ")
        if cu in (
            "LOGIN",
            "LOGIN DO TÉCNICO",
            "LOGIN DO TECNICO",
            "MATRICULA",
            "MATRÍCULA",
            "ID",
            "USUARIO",
            "USUÁRIO",
        ):
            rename_map[col] = "Login"
        elif cu in ("TECNICO", "TÉCNICO", "NOME", "NOME TECNICO", "NOME DO TECNICO"):
            rename_map[col] = "Técnico"
        elif cu in ("MONITOR", "GESTOR", "SUPERVISOR", "COORDENADOR", "NOME MONITOR"):
            rename_map[col] = "Monitor"
        elif cu in ("BASE", "REGIAO", "REGIÃO", "CIDADE"):
            rename_map[col] = "Base"
        elif cu in ("SITUACAO", "SITUAÇÃO"):
            rename_map[col] = "Situação"

    # Colunas alternativas podem coexistir com as oficiais (ex.: Login e RE).
    usados = set()
    for col, destino in list(rename_map.items()):
        if (destino != col and destino in raw.columns) or destino in usados:
            del rename_map[col]
        else:
            usados.add(destino)
    raw = raw.rename(columns=rename_map)
    if "Login" not in raw.columns:
        return pd.DataFrame()

    if "Situação" in raw.columns:
        situacao = raw["Situação"].fillna("").astype(str).str.strip().str.upper()
        raw = raw[~situacao.isin(["DESLIGADO", "INATIVO"])]

    cols = [c for c in ["Login", "Técnico", "Monitor", "Base"] if c in raw.columns]
    raw = raw[cols].copy()
    raw["Login"] = (
        raw["Login"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.upper()
    )
    invalidos = ["NAN", "NONE", "NULL", "N/A", "<NA>", "0", "-", ""]
    raw = raw[~raw["Login"].isin(invalidos)]
    return raw.drop_duplicates(subset=["Login"], keep="last").reset_index(drop=True)


def _conexao_gsheets_configurada() -> bool:
    try:
        import streamlit as st
        from streamlit.errors import StreamlitSecretNotFoundError
    except ImportError:
        return False

    try:
        return bool(st.secrets.get("connections", {}).get("gsheets"))
    except StreamlitSecretNotFoundError:
        return False


def carregar_lista_ativos(
    sheet_id: str | None = None,
    worksheet: str = "lista_ativos",
    url: str | None = None,
    segredos: Callable[[], dict[str, Any]] | None = None,
    credenciais: Callable[..., Any] | None = None,
    autorizar: Callable[[Any], Any] | None = None,
    conexao: Callable[[], Any] | None = None,
    read_csv: Callable[..., pd.DataFrame] | None = None,
) -> pd.DataFrame:
    """
    Carrega a aba ``lista_ativos`` da planilha de ativos.

    Ordem: conta de serviço (gspread) → conexão nativa configurada → CSV público.
    As dependências podem ser injetadas (páginas passam ``st`` e ``gspread``).
    """
    default_sheet = "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
    sheet_id = resolver_sheet_id(sheet_id, default=default_sheet)
    if not sheet_id:
        vazia = pd.DataFrame()
        vazia.attrs["erro_ativos"] = (
            "Nenhum ID da planilha foi configurado. Defina SHEET_ID/GSHEETS_ID ou TOTALE_SHEET_ID."
        )
        return vazia
    url = url or f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

    def validar(raw: pd.DataFrame, fonte: str) -> pd.DataFrame:
        ativos = normalizar_lista_ativos(raw)
        if ativos.empty:
            raise ValueError("A aba não contém uma coluna Login com registros válidos")
        ativos.attrs["fonte_ativos"] = fonte
        return ativos

    # 1) Conta de serviço (funciona também fora do Streamlit)
    try:
        info = (segredos() if segredos else _segredos_padrao()) or {}
        if info:
            if credenciais is None or autorizar is None:
                import gspread
                from google.oauth2.service_account import Credentials

                credenciais = credenciais or Credentials.from_service_account_info
                autorizar = autorizar or gspread.authorize
            escopos = [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ]
            cliente = autorizar(credenciais(dict(info), scopes=escopos))
            planilha = cliente.open_by_key(sheet_id).worksheet(worksheet)
            registros = pd.DataFrame(planilha.get_all_records(default_blank=""))
            return validar(registros, "Google Sheets (autenticado)")
    except Exception as exc:
        logger.warning("Falha na leitura autenticada da lista_ativos: %s", normalizar_erro_worksheet(exc, worksheet))

    # O modo público do conector exige o GID numérico da aba; sem uma conexão
    # configurada, use o CSV público, que aceita o nome da aba.
    if conexao is not None or _conexao_gsheets_configurada():
        try:
            if conexao is None:
                import streamlit as st
                from streamlit_gsheets import GSheetsConnection

                def criar_conexao() -> Any:
                    return st.connection("gsheets", type=GSheetsConnection)

                conexao = criar_conexao
            conn = conexao()
            raw = conn.read(spreadsheet=url, worksheet=worksheet, ttl=0)
            return validar(pd.DataFrame(raw), "Google Sheets (conexão)")
        except Exception as exc:
            logger.warning("Falha na conexão da lista_ativos: %s", normalizar_erro_worksheet(exc, worksheet))

    # 3) CSV público
    try:
        leitor = read_csv or pd.read_csv
        csv_url = (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}"
            f"/gviz/tq?tqx=out:csv&sheet={worksheet}"
        )
        return validar(leitor(csv_url), "Google Sheets (CSV público)")
    except Exception as exc:
        logger.warning("Falha na leitura pública da lista_ativos: %s", normalizar_erro_worksheet(exc, worksheet))

    vazia = pd.DataFrame()
    vazia.attrs["erro_ativos"] = (
        "Não foi possível ler a aba lista_ativos. Verifique a conta de serviço, "
        "o compartilhamento da planilha e a coluna Login."
    )
    return vazia


def resolver_sheet_id(
    sheet_id: str | None = None,
    *aliases: str,
    default: str | None = None,
) -> str:
    """Resolve o ID da planilha a partir de secrets/ambiente ou de uma URL."""
    candidates: list[str] = []
    if sheet_id:
        candidates.append(str(sheet_id))

    for alias in aliases:
        if alias:
            candidates.append(alias)

    for key in (
        "TOTALE_SHEET_ID",
        "GSHEETS_ID",
        "SHEET_ID",
        "SHEET_ID_ATIVOS",
        "SHEET_ID_PROD",
    ):
        value = os.getenv(key, "")
        if value:
            candidates.append(value)

    try:
        import streamlit as st

        for key in ("SHEET_ID", "GSHEETS_ID", "SHEET_ID_ATIVOS", "SHEET_ID_PROD"):
            value = st.secrets.get(key, "")
            if value:
                candidates.append(str(value))
    except Exception:
        pass

    for value in candidates:
        texto = str(value).strip()
        if not texto:
            continue
        if texto.startswith("http://") or texto.startswith("https://"):
            match = re.search(r"/d/([A-Za-z0-9_-]+)", texto)
            if match:
                return match.group(1)
            continue
        if texto.startswith("{"):
            continue
        return texto

    return default or ""


def normalizar_erro_worksheet(exc: Exception, worksheet_name: str) -> str:
    """Remove HTML bruto do Google e converte 404/403/400 em mensagem útil."""
    texto = str(exc).strip().replace("\n", " ")
    texto = re.sub(r"\s+", " ", texto)
    texto_norm = texto.lower()

    if "<!DOCTYPE html>" in texto or "404 (not found)" in texto_norm or "error 404" in texto_norm or "not found" in texto_norm:
        return (
            f"Planilha ou aba '{worksheet_name}' não encontrada (HTTP 404). "
            "Verifique o ID da planilha, o nome da aba e o compartilhamento com a conta de serviço."
        )
    if "403" in texto or "forbidden" in texto_norm:
        return (
            f"Sem permissão para acessar '{worksheet_name}' (HTTP 403). "
            "Compartilhe a planilha com a conta de serviço e confirme as permissões do Google Drive."
        )
    if "400" in texto or "bad request" in texto_norm:
        return (
            f"A aba '{worksheet_name}' não pôde ser lida (HTTP 400). "
            "Verifique se o nome da aba coincide com o configurado no código."
        )
    return texto[:500] if texto else "Erro desconhecido ao ler a aba."


def _segredos_padrao() -> dict[str, Any]:
    """Credenciais da conta de serviço (Streamlit secrets ou arquivo local)."""
    try:
        import streamlit as st

        return dict(st.secrets["gcp_service_account"])
    except Exception:
        pass

    caminho = os.getenv("TOTALE_GCP_SERVICE_ACCOUNT_JSON", "")
    if caminho and Path(caminho).exists():
        try:
            return json.loads(Path(caminho).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Falha ao ler a conta de serviço local: %s", exc)
    return {}


def carregar_hierarquia(**kwargs: Any) -> pd.DataFrame:
    """
    Lista de ativos no formato usado pelo upload
    (``__LOGIN_KEY``, ``__TEC_GS``, ``__MON_GS``).
    """
    ativos = carregar_lista_ativos(**kwargs)
    if ativos.empty or "Login" not in ativos.columns:
        return pd.DataFrame()

    return pd.DataFrame(
        {
            "__LOGIN_KEY": Utils.normalizar_login(ativos["Login"]),
            "__TEC_GS": ativos["Técnico"] if "Técnico" in ativos.columns else "",
            "__MON_GS": ativos["Monitor"] if "Monitor" in ativos.columns else "",
        }
    ).drop_duplicates("__LOGIN_KEY")


def hierarquia_de(ativos: pd.DataFrame) -> pd.DataFrame:
    """
    Converte uma lista de ativos já carregada no formato usado pela
    vínculo (``__LOGIN_KEY``, ``__TEC_GS``, ``__MON_GS``).

    Aceita a lista bruta ou normalizada — a normalização é reaplicada
    para o vínculo não depender da fonte (sessão, Sheets ou CSV).
    """
    if ativos is None or not isinstance(ativos, pd.DataFrame) or ativos.empty:
        return pd.DataFrame()
    norm = normalizar_lista_ativos(ativos)
    if norm.empty or "Login" not in norm.columns:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "__LOGIN_KEY": Utils.normalizar_login(norm["Login"]),
            "__TEC_GS": norm["Técnico"] if "Técnico" in norm.columns else "",
            "__MON_GS": norm["Monitor"] if "Monitor" in norm.columns else "",
        }
    ).drop_duplicates("__LOGIN_KEY")


# ═══════════════════════════════════════════════════════════════════════
# PREPARAÇÃO — ROTA INICIAL
# ═══════════════════════════════════════════════════════════════════════
#: Intervalo da exportação → turno exibido no painel de Rota Inicial.
MAPEAMENTO_PERIODOS: dict[str, str] = {
    "08:00 - 10:00": "Manhã",
    "08:00 - 11:00": "Manhã",
    "08:00 - 12:00": "Manhã",
    "10:00 - 12:00": "Manhã",
    "11:00 - 14:00": "Manhã",
    "12:00 - 14:00": "Tarde I",
    "12:00 - 15:00": "Tarde I",
    "12:00 - 18:00": "Tarde II",
    "14:00 - 16:00": "Tarde II",
    "14:00 - 17:00": "Tarde II",
    "15:00 - 18:00": "Tarde II",
    "16:00 - 18:00": "Tarde II",
    "17:00 - 20:00": "Tarde II",
    "Imediata": "Imediata",
}

_VAZIOS_CONTRATO_ROTA = {"", "NAN", "NONE", "N/A", "NA", "-", "0", "NULL", "<NA>"}


def preparar_base_rota_inicial(
    df_bruto: pd.DataFrame, df_ativos: pd.DataFrame
) -> pd.DataFrame:
    if not isinstance(df_bruto, pd.DataFrame) or df_bruto.empty:
        return pd.DataFrame()

    _RE_REMOVER_FID = re.compile(r"\bFID\s*(12M|24M)\b", re.IGNORECASE)

    df = df_bruto.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()

    mapa = {
        "CONTRATO": ["CONTRATO"],
        "LOGIN_TECNICO": ["LOGIN DO TÉCNICO", "LOGIN DO TECNICO"],
        "STATUS_ATIVIDADE": ["STATUS DA ATIVIDADE"],
        "STATUS_PRODUTO": [
            "STATUS DO PRODUTO",
            "STATUS PRODUTO",
            "SITUACAO DO PRODUTO",
            "SITUAÇÃO DO PRODUTO",
            "STATUS_ITEM",
        ],
        "TOTAL_TAREFAS": ["TOTAL DE TAREFAS"],
        "TIPO_OS": ["TIPO O.S 1"],
        "HABILIDADE": ["HABILIDADE DE TRABALHO"],
        "PRODUTO": ["PRODUTO"],
        "INTERVALO": ["INTERVALO DE TEMPO", "INTERVALO"],
        "CIDADE": ["CIDADE"],
        "COORD_X": ["COORDENADA X", "LONGITUDE", "LON"],
        "COORD_Y": ["COORDENADA Y", "LATITUDE", "LAT"],
    }
    for padrao, variacoes in mapa.items():
        col = next((c for c in df.columns if c in variacoes), None)
        if col:
            df = df.rename(columns={col: padrao})
        else:
            df[padrao] = np.nan

    contrato = (
        df["CONTRATO"]
        .astype("string")
        .str.replace("\u00a0", " ", regex=False)
        .str.strip()
    )
    mask_vazio = (
        contrato.isna()
        | contrato.eq("")
        | contrato.str.upper().isin(_VAZIOS_CONTRATO_ROTA)
    )
    removidos = int(mask_vazio.sum())
    df = df.loc[~mask_vazio].copy()
    df["CONTRATO"] = contrato.loc[df.index].str.upper()

    if df.empty:
        return pd.DataFrame()

    df["LOGIN_TECNICO"] = (
        df["LOGIN_TECNICO"]
        .astype(str)
        .str.replace(r"\.0$", "", regex=True)
        .str.strip()
        .str.upper()
    )
    df["TOTAL_TAREFAS"] = (
        pd.to_numeric(
            df["TOTAL_TAREFAS"].astype(str).str.replace(",", "."), errors="coerce"
        )
        .fillna(1)
        .astype(int)
    )
    df["STATUS_ATIVIDADE"] = df["STATUS_ATIVIDADE"].astype(str).str.strip().str.upper()
    if "STATUS_PRODUTO" in df.columns:
        df["STATUS_PRODUTO"] = df["STATUS_PRODUTO"].astype(str).str.strip().str.upper()

    if isinstance(df_ativos, pd.DataFrame) and not df_ativos.empty:
        df = df.drop(
            columns=[
                c for c in ["Técnico", "Monitor", "Base"] if c.upper() in df.columns
            ],
            errors="ignore",
        )
        df = df.merge(df_ativos, left_on="LOGIN_TECNICO", right_on="Login", how="left")
        df = df.rename(columns={"Técnico": "NOME_OFICIAL"})

    df["NOME_OFICIAL"] = df.get("NOME_OFICIAL", df["LOGIN_TECNICO"]).fillna(
        df["LOGIN_TECNICO"]
    )
    # Sem a lista de ativos a coluna não existe: um `df.get` com Series vazia
    # alinharia por índice e deixaria tudo NaN em vez de "SEM MONITOR".
    if "Monitor" in df.columns:
        df["Monitor"] = df["Monitor"].fillna("SEM MONITOR")
    else:
        df["Monitor"] = "SEM MONITOR"

    hab = df["HABILIDADE"].astype(str).str.upper()
    tipo = df["TIPO_OS"].astype(str).str.upper()

    prod = df["PRODUTO"].astype(str).str.upper()
    prod = prod.str.replace(_RE_REMOVER_FID, "", regex=True)
    prod = prod.str.replace(r"\s{2,}", " ", regex=True).str.strip()
    df["PRODUTO"] = prod

    # Todas as buscas abaixo são literais (``regex=False``): as habilidades
    # trazem parênteses — "TV VAS(1/100)", "PON(1/100)" — e, como regex, o
    # parêntese viraria grupo, exigindo a grafia "TV VAS1/100" (que não existe
    # na exportação) e zerando os filtros de Streaming/GPON da Rota Inicial.
    df["Check_GPON"] = hab.str.contains("PON(1/100)", regex=False, na=False)
    df["Check_ND"] = tipo.str.contains("ADESAO", regex=False, na=False)
    df["Check_Migracao"] = (tipo.str.strip() == "24 - MUDANCA DE PACOTE") & df[
        "Check_GPON"
    ]
    df["Check_PME"] = df["Check_ND"] & hab.str.contains(
        "PME", regex=False, na=False
    )
    df["Check_Streaming"] = hab.str.contains("TV VAS(1/100)", regex=False, na=False)
    df["Check_Ponto_Ultra"] = hab.str.contains("NETLAR", regex=False, na=False)
    df["Check_4K"] = prod.str.contains("4K", regex=False, na=False)
    df["Check_Soundbox"] = prod.str.contains("SOUND", regex=False, na=False)

    df["PERIODO_TRATADO"] = (
        df["INTERVALO"]
        .astype(str)
        .str.strip()
        .map(MAPEAMENTO_PERIODOS)
        .fillna("Outros/Sem Período")
    )

    cidade = (
        df["CIDADE"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.upper()
        .apply(
            lambda v: (
                unicodedata.normalize("NFKD", v).encode("ASCII", "ignore").decode()
            )
        )
    )
    df["REGIÃO"] = np.select(
        [
            cidade.isin(["SAO PAULO"]),
            cidade.isin(
                [
                    "GUARULHOS",
                    "ARUJA",
                    "MOGI DAS CRUZES",
                    "SUZANO",
                    "ITAQUAQUECETUBA",
                    "FERRAZ DE VASCONCELOS",
                    "POA",
                ]
            ),
            cidade.isin(
                [
                    "SANTO ANDRE",
                    "SAO BERNARDO DO CAMPO",
                    "SAO CAETANO DO SUL",
                    "DIADEMA",
                    "MAUA",
                    "RIBEIRAO PIRES",
                    "RIO GRANDE DA SERRA",
                ]
            ),
        ],
        ["LESTE", "GRU", "ABCDM"],
        default="OUTRAS",
    )

    df.attrs["diagnostico"] = {"contrato_vazio": removidos}
    # Diagnóstico do vínculo com a lista de ativos (usado pelo upload).
    if isinstance(df_ativos, pd.DataFrame) and not df_ativos.empty:
        com_monitor = df["Monitor"].astype(str).str.strip().str.upper() != "SEM MONITOR"
        df.attrs["diag_vinculados"] = int(com_monitor.sum())
        df.attrs["diag_ativos"] = len(df_ativos)
    else:
        df.attrs["diag_vinculados"] = 0
        df.attrs["diag_ativos"] = 0
    fonte = str(getattr(df_ativos, "attrs", {}).get("fonte_ativos", "") or "")
    erro = str(getattr(df_ativos, "attrs", {}).get("erro_ativos", "") or "")
    df.attrs["fonte_ativos"] = fonte
    df.attrs["erro_ativos"] = erro
    return df


# ═══════════════════════════════════════════════════════════════════════
# UPLOAD MANUAL — BASE DA ROTA INICIAL
# ═══════════════════════════════════════════════════════════════════════
def gerar_bases_upload(
    conteudo: bytes, nome_arquivo: str, lista_ativos: pd.DataFrame
) -> dict[str, Any]:
    """
    Gera a base da Rota Inicial a partir de um upload.

    Retorna ``{"rota_inicial", "erros", "linhas_brutas"}`` — base ausente
    (``None``) sempre acompanhada da mensagem em ``erros``.
    """
    resultado: dict[str, Any] = {
        "rota_inicial": None,
        "erros": {},
        "linhas_brutas": 0,
    }
    erros: dict[str, str] = resultado["erros"]

    ativos = (
        lista_ativos
        if isinstance(lista_ativos, pd.DataFrame)
        else pd.DataFrame()
    )
    ativos_norm = normalizar_lista_ativos(ativos) if not ativos.empty else ativos

    try:
        bruta = ler_arquivo_bytes(conteudo, nome_arquivo)
    except Exception as exc:
        erros["leitura"] = str(exc)
        return resultado
    resultado["linhas_brutas"] = len(bruta)
    if bruta.empty:
        erros["leitura"] = "O arquivo enviado não possui registros."
        return resultado

    # A Rota trata a base como texto (mesmo comportamento do upload antigo).
    try:
        bruta_txt = ler_arquivo_bytes(conteudo, nome_arquivo, dtype=str)
    except Exception as exc:
        logger.warning("Falha na leitura como texto do upload: %s", exc)
        bruta_txt = bruta

    try:
        rota_df = preparar_base_rota_inicial(bruta_txt, ativos_norm)
        if rota_df is None or rota_df.empty:
            erros["rota_inicial"] = (
                "Nenhum registro válido para a Rota Inicial "
                "(verifique a coluna de contrato)."
            )
        else:
            resultado["rota_inicial"] = rota_df
    except Exception as exc:
        logger.exception("Falha ao preparar a base de Rota Inicial do upload.")
        erros["rota_inicial"] = str(exc)

    return resultado


__all__ = [
    "COL_CONTRATO",
    "COL_LOGIN",
    "COL_MONITOR",
    "COL_REGIAO",
    "COL_STATUS",
    "COL_TECNICO",
    "COL_TOTAL",
    "EXTENSOES_ACEITAS",
    "MAPEAMENTO_PERIODOS",
    "Utils",
    "carregar_hierarquia",
    "carregar_lista_ativos",
    "gerar_bases_upload",
    "hierarquia_de",
    "ler_arquivo_bytes",
    "normalizar_erro_worksheet",
    "normalizar_lista_ativos",
    "preparar_base_rota_inicial",
    "resolver_sheet_id",
]
