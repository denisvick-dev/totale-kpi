"""
components/base_operacional.py
==============================
Fonte única do tratamento da base operacional (exportação "Atividades")
compartilhada por **quebra.py**, **volumetria.py** e **rota_inicial.py**.

Fluxo (upload manual):
    1. o usuário envia o arquivo (.xlsx/.xls/.csv) na Central de
       Atualização (``envio_excel.py``) ou direto em um dos painéis;
    2. :func:`gerar_bases_upload` lê o arquivo uma única vez e gera as
       três bases tratadas, vinculadas à aba ``lista_ativos``;
    3. ``components/upload_base.py`` publica cada base na sessão, na
       chave que o respectivo painel já consome.

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

from components.criterios import (
    VAZIOS_CONTRATO,
    classificar_tipo_servico,
    detectar_col_contrato,
    detectar_col_status_atividade,
)

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

STATUS_ORDEM: list[str] = ["Executada", "Não Executada", "Pendente"]

EXTENSOES_ACEITAS: tuple[str, ...] = (".xlsx", ".xls", ".csv")

CIDADES_POR_REGIAO: dict[str, tuple[str, ...]] = {
    "LESTE": ("SAO PAULO",),
    "GRU": (
        "GUARULHOS",
        "ARUJA",
        "MOGI DAS CRUZES",
        "MOGI",
        "SUZANO",
        "ITAQUAQUECETUBA",
        "FERRAZ DE VASCONCELOS",
        "POA",
    ),
    "ABCDM": (
        "SANTO ANDRE",
        "SAO BERNARDO DO CAMPO",
        "SAO CAETANO DO SUL",
        "DIADEMA",
        "MAUA",
        "RIBEIRAO PIRES",
        "RIO GRANDE DA SERRA",
    ),
}


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

    @staticmethod
    def buscar_coluna_quebra(df: pd.DataFrame, palavras: Sequence[str]) -> str | None:
        """Busca por parte do nome (compatível com o padrão antigo de quebra.py)."""
        if df is None or df.empty:
            return None
        cols = {
            str(c)
            .strip()
            .upper()
            .replace(".", "")
            .replace("_", "")
            .replace("  ", " "): c
            for c in df.columns
        }
        for palavra in palavras:
            alvo = (
                str(palavra)
                .strip()
                .upper()
                .replace(".", "")
                .replace("_", "")
                .replace("  ", " ")
            )
            for nome_norm, nome_real in cols.items():
                if alvo in nome_norm:
                    return nome_real
        return None

    @staticmethod
    def classificar_status(status_os: pd.Series) -> pd.Series:
        """EXECUTADA / NÃO EXECUTADA / Pendente — aceita variações do status da O.S."""
        s = Utils.normalizar_chave(status_os)
        nao_exec = s.str.contains(r"NAO\s*EXECUT", regex=True, na=False)
        executada = s.str.contains("EXECUT", regex=False, na=False) & ~nao_exec
        return pd.Series(
            np.select(
                [executada, nao_exec],
                ["Executada", "Não Executada"],
                default="Pendente",
            ),
            index=status_os.index,
            dtype="object",
        )

    @staticmethod
    def regiao_por_cidade(cidade: pd.Series) -> pd.Series:
        normalizada = Utils.normalizar_chave(cidade).str.strip()
        condicoes = []
        rotulos = []
        for regiao, cidades in CIDADES_POR_REGIAO.items():
            condicoes.append(normalizada.isin(cidades))
            rotulos.append(regiao)
        return pd.Series(
            np.select(condicoes, rotulos, default="OUTRAS"),
            index=cidade.index,
            dtype="object",
        )


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
    Lista de ativos no formato usado pela Volumetria
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
    Volumetria (``__LOGIN_KEY``, ``__TEC_GS``, ``__MON_GS``).

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
# PREPARAÇÃO — VOLUMETRIA
# ═══════════════════════════════════════════════════════════════════════
def preparar_base_volumetria(
    raw: pd.DataFrame, hierarquia: pd.DataFrame
) -> pd.DataFrame:
    """
    Trata a base bruta para o painel de Volumetria.

    Retorna o DataFrame com ``attrs["diagnostico"]`` (avisos e erros) para a
    página decidir como exibir — nada de ``st.stop`` aqui.
    """
    df = raw.copy()
    df.columns = df.columns.astype(str).str.strip()
    avisos: list[str] = []
    erros: list[str] = []
    diag: dict[str, Any] = {"Inicial": len(df)}

    hierarquia = hierarquia if hierarquia is not None else pd.DataFrame()

    # 1. Contratos vazios
    col_con = Utils.buscar_coluna(
        df, ["CONTRATO", "Nº CONTRATO", "NUMERO CONTRATO", "NUM CONTRATO"]
    )
    if col_con:
        normalizada = (
            df[col_con].astype(str).str.strip().str.upper().map(Utils.remover_acentos)
        )
        valida = ~normalizada.isin({v for v in VAZIOS_CONTRATO})
        removidos = int((~valida).sum())
        df = df[valida].copy()
        diag["Removidos por contrato vazio"] = removidos
    else:
        avisos.append(
            "Coluna de contrato não encontrada — nada foi filtrado por contrato."
        )

    # 2. Remove suspensos
    col_atv = detectar_col_status_atividade(df)
    if col_atv:
        susp = Utils.normalizar_chave(df[col_atv]).str.contains("SUSP", na=False)
        diag["Removidos por suspensão"] = int(susp.sum())
        df = df[~susp].copy()

    # 3. Status
    col_os1 = _coluna_status_volumetria(df)
    if col_os1:
        df[COL_STATUS] = Utils.classificar_status(df[col_os1])
    else:
        erros.append("Coluna 'Status da O.S 1' não encontrada na base.")

    # 4. Total de tarefas
    col_qtd = Utils.buscar_coluna(df, ["TOTAL DE TAREFAS", "QUANTIDADE", "QTD TAREFAS"])
    if col_qtd:
        df[COL_TOTAL] = pd.to_numeric(df[col_qtd], errors="coerce").fillna(1)
    else:
        df[COL_TOTAL] = 1.0
        avisos.append(
            "Coluna 'TOTAL DE TAREFAS' não encontrada — considerando 1 por registro."
        )
    df[COL_TOTAL] = df[COL_TOTAL].clip(lower=0)

    # 5. Vínculo com a lista de ativos
    col_log = Utils.buscar_coluna(
        df, ["LOGIN DO TÉCNICO", "LOGIN", "USUÁRIO", "MATRÍCULA"]
    )
    if col_log and not hierarquia.empty:
        df["__LOGIN_KEY"] = Utils.normalizar_login(df[col_log])
        df = df.merge(hierarquia, on="__LOGIN_KEY", how="left")
    for col in ("__TEC_GS", "__MON_GS"):
        if col not in df.columns:
            df[col] = np.nan

    # 6. Técnico / Monitor (Sheets → arquivo → fallback)
    col_tec_b = Utils.buscar_coluna(df, ["TÉCNICO", "NOME"]) or col_log
    col_mon_b = Utils.buscar_coluna(df, ["MONITOR", "GESTOR"])

    base_tec = df[col_tec_b] if col_tec_b else pd.Series(np.nan, index=df.index)
    base_mon = df[col_mon_b] if col_mon_b else pd.Series(np.nan, index=df.index)

    tec_gs = df["__TEC_GS"].where(df["__TEC_GS"].notna(), "")
    mon_gs = df["__MON_GS"].where(df["__MON_GS"].notna(), "")

    df[COL_TECNICO] = tec_gs.mask(tec_gs.astype(str).str.strip().eq(""), base_tec)
    df[COL_MONITOR] = mon_gs.mask(mon_gs.astype(str).str.strip().eq(""), base_mon)

    df[COL_TECNICO] = df[COL_TECNICO].where(
        df[COL_TECNICO].notna() & df[COL_TECNICO].astype(str).str.strip().ne(""),
        "NÃO MAPEADO",
    )
    df[COL_MONITOR] = df[COL_MONITOR].where(
        df[COL_MONITOR].notna() & df[COL_MONITOR].astype(str).str.strip().ne(""),
        "SEM MONITOR",
    )

    # 7. Região
    col_cid = Utils.buscar_coluna(df, ["CIDADE", "LOCALIDADE"])
    cidade = (
        Utils.normalizar_chave(df[col_cid])
        if col_cid
        else pd.Series("", index=df.index)
    )
    df[COL_REGIAO] = Utils.regiao_por_cidade(cidade)

    diag["Final"] = len(df)
    diag["avisos"] = avisos
    diag["erros"] = erros
    diag["Fonte"] = "Upload manual"

    df.attrs["diagnostico"] = diag
    return df


def _coluna_status_volumetria(df: pd.DataFrame) -> str | None:
    return Utils.buscar_coluna(
        df,
        ["STATUS DA O.S 1", "STATUS OS 1", "STATUS DA OS 1", COL_STATUS],
    )


# ═══════════════════════════════════════════════════════════════════════
# PREPARAÇÃO — QUEBRA DE AGENDA
# ═══════════════════════════════════════════════════════════════════════
def preparar_base_quebra(
    raw: pd.DataFrame,
    lista_ativos: pd.DataFrame,
    fonte_ativos: str = "",
    erro_ativos: str = "",
) -> pd.DataFrame:
    """
    Trata a base bruta para a Quebra de Agenda (mesma regra da página).

    Mantém ``attrs`` de diagnóstico (``diag_*``) usados por ``quebra.py``.
    """
    if raw is None or raw.empty:
        return pd.DataFrame()

    df = raw.copy()
    df.columns = df.columns.astype(str).str.strip().str.upper()
    total_importado = len(df)

    col_mon_orig = Utils.buscar_coluna_quebra(
        df, ["MONITOR", "SUPERVISOR", "GESTOR", "COORDENADOR", "NOME MONITOR"]
    )
    col_tec_orig = Utils.buscar_coluna_quebra(
        df, ["TECNICO", "NOME TECNICO", "NOME DO TECNICO", "TÉCNICO"]
    )

    # 1. Remove suspensos
    col_atv = detectar_col_status_atividade(df)
    n_susp = 0
    if col_atv:
        serie_atv = df[col_atv].fillna("").astype(str).str.strip().str.upper()
        mask_susp = serie_atv.str.contains("SUSP", na=False) | serie_atv.eq("SUSPENSO")
        n_susp = int(mask_susp.sum())
        df = df[~mask_susp].copy()

    # 2. Remove contratos vazios
    col_con = detectar_col_contrato(df)
    n_inv = 0
    if col_con:
        serie_con = (
            df[col_con]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .str.replace(r"\.0$", "", regex=True)
        )
        mask_inv = serie_con.isin(VAZIOS_CONTRATO)
        n_inv = int(mask_inv.sum())
        df = df[~mask_inv].copy()

    # 3. Total de tarefas
    col_tot = Utils.buscar_coluna_quebra(
        df, ["TOTAL DE TAREFAS", "QTD TAREFAS", "TOTAL TAREFAS"]
    )
    if col_tot:
        df[COL_TOTAL] = (
            pd.to_numeric(
                df[col_tot].astype(str).str.replace(",", "."), errors="coerce"
            )
            .fillna(1)
            .astype(int)
        )
    else:
        df[COL_TOTAL] = 1

    # 4. Login + merge com a lista de ativos
    col_login = Utils.buscar_coluna_quebra(
        df,
        ["LOGIN DO TÉCNICO", "LOGIN DO TECNICO", "LOGIN", "USUÁRIO", "MATRÍCULA"],
    )
    if col_login:
        df[COL_LOGIN] = (
            df[col_login]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
            .str.upper()
        )
    else:
        df[COL_LOGIN] = "SEM LOGIN"

    lista_ativos = lista_ativos if lista_ativos is not None else pd.DataFrame()
    if not lista_ativos.empty:
        # A lista pode chegar bruta (download da nuvem, sessão, cache antigo):
        # login em caixa baixa, espaços, ".0", duplicados e desligados faziam o
        # merge não encontrar ninguém (ou explodir no validate="many_to_one").
        # Normalizar aqui torna o vínculo determinístico para qualquer fonte;
        # os attrs (fonte/erro) precisam sobreviver à normalização.
        attrs_ativos = dict(lista_ativos.attrs)
        lista_ativos = normalizar_lista_ativos(lista_ativos)
        lista_ativos.attrs.update(attrs_ativos)
    if col_login and not lista_ativos.empty and "Login" in lista_ativos.columns:
        df = df.merge(
            lista_ativos,
            left_on=COL_LOGIN,
            right_on="Login",
            how="left",
            suffixes=("", "_GS"),
            validate="many_to_one",
        )
    n_vinculados = int(df["Login"].notna().sum()) if "Login" in df.columns else 0

    # 5. Monitor (Sheets → arquivo → SEM MONITOR)
    mon_gs = (
        df["Monitor_GS"]
        if "Monitor_GS" in df.columns
        else (
            df["Monitor"]
            if "Monitor" in df.columns
            else pd.Series(np.nan, index=df.index)
        )
    )
    mon_file = (
        df[col_mon_orig]
        if col_mon_orig and col_mon_orig in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    mon_gs_c = (
        mon_gs.fillna(pd.NA)
        .astype("string")
        .str.strip()
        .replace(["", "nan", "None", "NAN", "NULL"], None)
    )
    mon_file_c = (
        mon_file.fillna(pd.NA)
        .astype("string")
        .str.strip()
        .replace(["", "nan", "None", "NAN", "NULL"], None)
    )

    df["ORIGEM_MAPEAMENTO"] = np.where(
        mon_gs_c.notna(),
        "Merge (Sheets)",
        np.where(mon_file_c.notna(), "Arquivo Origem", "Não Mapeado"),
    )
    df[COL_MONITOR] = (
        mon_gs_c.combine_first(mon_file_c)
        .fillna("SEM MONITOR")
        .astype(str)
        .str.strip()
        .str.upper()
    )
    df.loc[
        df[COL_MONITOR].isin(["", "NAN", "NONE", "NULL", "0", "N/A"]), COL_MONITOR
    ] = "SEM MONITOR"

    # 6. Técnico (Sheets → arquivo → NÃO MAPEADO)
    tec_gs = (
        df["Técnico_GS"]
        if "Técnico_GS" in df.columns
        else (
            df["Técnico"]
            if "Técnico" in df.columns
            else pd.Series(np.nan, index=df.index)
        )
    )
    tec_file = (
        df[col_tec_orig]
        if col_tec_orig and col_tec_orig in df.columns
        else pd.Series(np.nan, index=df.index)
    )
    tec_gs_c = (
        tec_gs.fillna(pd.NA)
        .astype("string")
        .str.strip()
        .replace(["", "nan", "None", "NAN", "NULL"], None)
    )
    tec_file_c = (
        tec_file.fillna(pd.NA)
        .astype("string")
        .str.strip()
        .replace(["", "nan", "None", "NAN", "NULL"], None)
    )

    df[COL_TECNICO] = (
        tec_gs_c.combine_first(tec_file_c)
        .fillna("NÃO MAPEADO")
        .astype(str)
        .str.strip()
        .str.upper()
    )
    df.loc[
        df[COL_TECNICO].isin(["", "NAN", "NONE", "NULL", "0", "N/A"]), COL_TECNICO
    ] = "NÃO MAPEADO"

    # 7. Contrato normalizado
    if col_con and col_con in df.columns:
        df[COL_CONTRATO] = df[col_con].astype(str).str.strip()

    # 8. Região
    col_cid = Utils.buscar_coluna_quebra(df, ["CIDADE", "LOCALIDADE"])
    cidade = (
        df[col_cid].fillna("").astype(str).str.strip().str.upper()
        if col_cid
        else pd.Series("", index=df.index)
    )
    df[COL_REGIAO] = Utils.regiao_por_cidade(cidade)

    # 9. Status do contrato
    col_status_os = Utils.buscar_coluna_quebra(
        df, ["STATUS DA O.S 1", "STATUS OS 1", "STATUS CONTRATO"]
    )
    df["Status Contrato"] = (
        Utils.classificar_status(df[col_status_os]) if col_status_os else "Pendente"
    )

    # 10. Classificação oficial de segmentos (criterios.py)
    df, _ = classificar_tipo_servico(df)
    df = df.drop(columns=["_TIPOS_OS_SET"], errors="ignore")

    # 11. Motivo de baixa
    col_baixa = Utils.buscar_coluna_quebra(
        df,
        ["CÓD DE BAIXA 1", "MOTIVO DE BAIXA", "COD DE BAIXA 1", "MOTIVO BAIXA"],
    )
    df["_COL_BAIXA"] = df[col_baixa].astype(str) if col_baixa else ""

    df.attrs["diag_importado"] = total_importado
    df.attrs["diag_susp"] = n_susp
    df.attrs["diag_inv"] = n_inv
    df.attrs["diag_final"] = len(df)
    df.attrs["diag_vinculados"] = n_vinculados
    df.attrs["diag_ativos"] = len(lista_ativos)
    df.attrs["fonte_ativos"] = fonte_ativos or lista_ativos.attrs.get(
        "fonte_ativos", ""
    )
    df.attrs["erro_ativos"] = erro_ativos or lista_ativos.attrs.get("erro_ativos", "")
    df.attrs["diag_login"] = col_login or ""
    return df



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
    df["Monitor"] = df.get("Monitor", pd.Series(dtype=str)).fillna("SEM MONITOR")

    hab = df["HABILIDADE"].astype(str).str.upper()
    tipo = df["TIPO_OS"].astype(str).str.upper()

    prod = df["PRODUTO"].astype(str).str.upper()
    prod = prod.str.replace(_RE_REMOVER_FID, "", regex=True)
    prod = prod.str.replace(r"\s{2,}", " ", regex=True).str.strip()
    df["PRODUTO"] = prod

    df["Check_GPON"] = hab.str.contains(r"PON\(1/100\)", regex=True, na=False)
    df["Check_ND"] = tipo.str.contains("ADESAO", na=False)
    df["Check_Migracao"] = (tipo.str.strip() == "24 - MUDANCA DE PACOTE") & df[
        "Check_GPON"
    ]
    df["Check_PME"] = df["Check_ND"] & hab.str.contains("PME", na=False)
    df["Check_Streaming"] = hab.str.contains("TV VAS(1/100)", na=False)
    df["Check_Ponto_Ultra"] = hab.str.contains("NETLAR", na=False)
    df["Check_4K"] = prod.str.contains("4K", na=False)
    df["Check_Soundbox"] = prod.str.contains("SOUND", na=False)

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
    return df



# ═══════════════════════════════════════════════════════════════════════
# UPLOAD MANUAL — UM ARQUIVO, TRÊS BASES
# ═══════════════════════════════════════════════════════════════════════
def gerar_bases_upload(
    conteudo: bytes, nome_arquivo: str, lista_ativos: pd.DataFrame
) -> dict[str, Any]:
    """
    Gera as bases de Quebra, Volumetria e Rota Inicial de um único upload.

    Cada painel é processado de forma independente: a falha de um deles
    (ex.: coluna de status ausente para a Volumetria) não bloqueia os
    demais. Retorna ``{"quebra", "volumetria", "rota_inicial", "erros",
    "linhas_brutas"}`` — base ausente (``None``) sempre acompanhada da
    mensagem em ``erros``.
    """
    resultado: dict[str, Any] = {
        "quebra": None,
        "volumetria": None,
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
    fonte_ativos = str(ativos.attrs.get("fonte_ativos", "") or "")
    erro_ativos = str(ativos.attrs.get("erro_ativos", "") or "")
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

    # Quebra e Rota tratam a base como texto (mesmo comportamento dos
    # uploads que existiam nas páginas).
    try:
        bruta_txt = ler_arquivo_bytes(conteudo, nome_arquivo, dtype=str)
    except Exception as exc:
        logger.warning("Falha na leitura como texto do upload: %s", exc)
        bruta_txt = bruta

    try:
        volumetria_df = preparar_base_volumetria(bruta, hierarquia_de(ativos))
        erros_vol = volumetria_df.attrs.get("diagnostico", {}).get("erros", [])
        if erros_vol:
            erros["volumetria"] = "; ".join(str(e) for e in erros_vol)
        else:
            resultado["volumetria"] = volumetria_df
    except Exception as exc:
        logger.exception("Falha ao preparar a base de Volumetria do upload.")
        erros["volumetria"] = str(exc)

    try:
        quebra_df = preparar_base_quebra(
            bruta_txt, ativos, fonte_ativos, erro_ativos
        )
        if quebra_df is None or quebra_df.empty:
            erros["quebra"] = "Nenhum registro válido para a Quebra de Agenda."
        else:
            resultado["quebra"] = quebra_df
    except Exception as exc:
        logger.exception("Falha ao preparar a base de Quebra do upload.")
        erros["quebra"] = str(exc)

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
    "CIDADES_POR_REGIAO",
    "COL_CONTRATO",
    "COL_LOGIN",
    "COL_MONITOR",
    "COL_REGIAO",
    "COL_STATUS",
    "COL_TECNICO",
    "COL_TOTAL",
    "EXTENSOES_ACEITAS",
    "MAPEAMENTO_PERIODOS",
    "STATUS_ORDEM",
    "Utils",
    "carregar_hierarquia",
    "carregar_lista_ativos",
    "gerar_bases_upload",
    "hierarquia_de",
    "ler_arquivo_bytes",
    "normalizar_erro_worksheet",
    "normalizar_lista_ativos",
    "preparar_base_quebra",
    "preparar_base_rota_inicial",
    "preparar_base_volumetria",
    "resolver_sheet_id",
]
