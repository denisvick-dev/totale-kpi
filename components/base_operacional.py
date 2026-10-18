"""
components/base_operacional.py
==============================
Fonte única dos dados operacionais compartilhados por **volumetria.py**,
**quebra.py** e pelo **robô** (``scripts/robot_base.py``).

Fluxo do robô:
    1. localiza o arquivo mais recente na pasta monitorada
       (por padrão a pasta **Downloads** do usuário);
    2. lê e trata a base bruta (Excel/CSV);
    3. gera as bases prontas de Volumetria e de Quebra de Agenda;
    4. grava o cache em ``dados/cache/`` + ``manifesto.json``;
    5. as páginas leem esse cache automaticamente (sem upload manual).

O módulo roda **com ou sem Streamlit** — nenhuma função de UI é obrigatória.
Quando o Streamlit está disponível, a leitura da lista de ativos tenta a conta
de serviço, depois a conexão nativa e, por fim, o CSV público da planilha.

Configuração (ordem de precedência):
    secrets ``[base_operacional]``  →  variáveis de ambiente  →  padrões

    pasta_entrada   TOTALE_BASE_ENTRADA    Downloads do usuário
    pasta_cache     TOTALE_BASE_CACHE      dados/cache
    arquivo_glob    TOTALE_BASE_ARQUIVO    "" (qualquer .xlsx/.xls/.csv)
    ttl_minutos     TOTALE_BASE_TTL         0 (sem expiração)
    recursivo       TOTALE_BASE_RECURSIVO  1
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
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

#: Opções aceitas para a leitura da lista de ativos (repasse às páginas).
_OPCOES_ATIVOS: tuple[str, ...] = (
    "sheet_id",
    "worksheet",
    "url",
    "segredos",
    "credenciais",
    "autorizar",
    "conexao",
    "read_csv",
)

_ARQUIVO_VOLUMETRIA = "volumetria.pkl"
_ARQUIVO_QUEBRA = "quebra.pkl"
_ARQUIVO_MANIFESTO = "manifesto.json"


# ═══════════════════════════════════════════════════════════════════════
# CONFIGURAÇÃO
# ═══════════════════════════════════════════════════════════════════════
def _caminho_downloads(sistema: str | None = None, home: Path | None = None) -> str:
    """
    Caminho (string) da pasta Downloads — isolado para facilitar os testes.

    ``sistema`` e ``home`` existem só para injeção em testes; em produção usa
    ``os.name`` e ``Path.home()``.
    """
    sistema = sistema or os.name
    home = Path(home) if home else Path.home()

    if sistema == "nt":
        perfil = os.getenv("USERPROFILE") or str(home)
        return os.path.join(perfil, "Downloads")

    xdg = home / ".config" / "user-dirs.dirs"
    if xdg.is_file():
        try:
            for linha in xdg.read_text(encoding="utf-8", errors="ignore").splitlines():
                if not linha.strip().startswith("XDG_DOWNLOAD_DIR"):
                    continue
                valor = linha.split("=", 1)[-1].strip().strip('"').strip("'")
                valor = os.path.expandvars(
                    valor.replace("$HOME", str(home)).replace("${HOME}", str(home))
                )
                if valor:
                    return os.path.expanduser(valor)
        except OSError:
            pass

    return str(home / "Downloads")


def pasta_downloads() -> Path:
    """
    Pasta de **Downloads** do usuário — origem padrão das bases do robô.

    - Windows: ``%USERPROFILE%\\Downloads``
    - Linux: respeita ``XDG_DOWNLOAD_DIR`` (``~/.config/user-dirs.dirs``)
    - macOS: ``~/Downloads``
    """
    return Path(_caminho_downloads())


@dataclass(frozen=True)
class ConfigBase:
    pasta_entrada: Path
    pasta_cache: Path
    arquivo_glob: str = ""
    ttl_minutos: int = 0
    #: Varre também as subpastas. Desligado por padrão porque a pasta
    #: Downloads costuma ser grande e cheia de arquivos temporários.
    recursivo: bool = False


def _secrets_base() -> dict[str, Any]:
    try:
        import streamlit as st  # import local: o robô roda sem Streamlit

        secao = st.secrets.get("base_operacional", {})
        return {str(k): v for k, v in dict(secao).items()}
    except Exception:
        return {}


def _como_bool(valor: Any, padrao: bool) -> bool:
    if valor is None:
        return padrao
    if isinstance(valor, bool):
        return valor
    return str(valor).strip().lower() in {"1", "true", "sim", "yes", "on"}


def config(**sobreescrever: Any) -> ConfigBase:
    """Configuração do robô (secrets → ambiente → padrões)."""
    segredos = _secrets_base()
    ambiente = os.environ

    def valor(chave: str, env: str, padrao: Any) -> Any:
        if chave in segredos and segredos[chave] not in (None, ""):
            return segredos[chave]
        if ambiente.get(env):
            return ambiente[env]
        return padrao

    cfg = ConfigBase(
        pasta_entrada=Path(
            str(valor("pasta_entrada", "TOTALE_BASE_ENTRADA", pasta_downloads()))
        ),
        pasta_cache=Path(str(valor("pasta_cache", "TOTALE_BASE_CACHE", "dados/cache"))),
        arquivo_glob=str(valor("arquivo_glob", "TOTALE_BASE_ARQUIVO", "")).strip(),
        ttl_minutos=int(valor("ttl_minutos", "TOTALE_BASE_TTL", 0) or 0),
        recursivo=_como_bool(valor("recursivo", "TOTALE_BASE_RECURSIVO", False), False),
    )

    dados = {k: v for k, v in sobreescrever.items() if v is not None}
    if not dados:
        return cfg

    for chave in ("pasta_entrada", "pasta_cache"):
        if chave in dados:
            dados[chave] = Path(str(dados[chave]))
    return ConfigBase(**{**cfg.__dict__, **dados})


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
    """Lê Excel/CSV a partir de bytes (usado pelo upload e pelo robô)."""
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


def ler_arquivo_caminho(
    caminho: os.PathLike | str, dtype: Any | None = None
) -> pd.DataFrame:
    """Lê a base direto do disco (robô)."""
    caminho = Path(caminho)
    if not caminho.exists():
        raise FileNotFoundError(f"Base não encontrada: {caminho}")
    return ler_arquivo_bytes(caminho.read_bytes(), caminho.name, dtype=dtype)


# ═══════════════════════════════════════════════════════════════════════
# LOCALIZAÇÃO DA BASE NA PASTA MONITORADA
# ═══════════════════════════════════════════════════════════════════════
def localizar_base(
    pasta: os.PathLike | str | None = None,
    arquivo_glob: str = "",
    recursivo: bool | None = None,
    extensoes: Sequence[str] = EXTENSOES_ACEITAS,
) -> Path | None:
    """
    Retorna o arquivo de base **mais recente** da pasta monitorada.

    Considera apenas os arquivos diretamente na pasta (a não ser que
    ``recursivo`` esteja ligado), ignorando temporários do Excel (``~$``) e
    arquivos ocultos. Critério: maior ``mtime``; em caso de empate, o nome.
    """
    cfg = config(recursivo=recursivo)
    pasta_path = Path(pasta) if pasta else cfg.pasta_entrada
    if not pasta_path.exists():
        return None

    padrao = (arquivo_glob or cfg.arquivo_glob or "").strip()
    extensoes = tuple(e.lower() for e in extensoes)

    if padrao:
        candidatos = []
        for padrao_individual in padrao.split(";"):
            padrao_individual = padrao_individual.strip()
            if not padrao_individual:
                continue
            candidatos.extend(
                pasta_path.rglob(padrao_individual)
                if cfg.recursivo
                else pasta_path.glob(padrao_individual)
            )
    else:
        candidatos = [
            p
            for p in (pasta_path.rglob("*") if cfg.recursivo else pasta_path.glob("*"))
            if p.is_file() and p.suffix.lower() in extensoes
        ]

    candidatos = [
        p
        for p in candidatos
        if p.is_file()
        and p.suffix.lower() in extensoes
        and not p.name.startswith(("~$", "."))
    ]
    if not candidatos:
        return None

    return max(candidatos, key=lambda p: (p.stat().st_mtime, p.name.lower()))


def calcular_hash(caminho: os.PathLike | str) -> str:
    """Hash SHA-256 (por blocos) do arquivo — usado para saber se a base mudou."""
    h = hashlib.sha256()
    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


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
    Carrega a ``lista_ativos`` (mesma aba da Gestão de Ativos).

    Ordem: conta de serviço (gspread) → conexão nativa configurada → CSV público.
    As dependências podem ser injetadas (páginas passam ``st`` e ``gspread``).
    """
    sheet_id = sheet_id or "1LQKDcLshC6XSXLBVWaEYSpxrro6uydyU9pwDLc38pEg"
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
        logger.warning("Falha na leitura autenticada da lista_ativos: %s", exc)

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
            logger.warning("Falha na conexão da lista_ativos: %s", exc)

    # 3) CSV público
    try:
        leitor = read_csv or pd.read_csv
        csv_url = (
            f"https://docs.google.com/spreadsheets/d/{sheet_id}"
            f"/gviz/tq?tqx=out:csv&sheet={worksheet}"
        )
        return validar(leitor(csv_url), "Google Sheets (CSV público)")
    except Exception as exc:
        logger.warning("Falha na leitura pública da lista_ativos: %s", exc)

    vazia = pd.DataFrame()
    vazia.attrs["erro_ativos"] = (
        "Não foi possível ler a aba lista_ativos. Verifique a conta de serviço, "
        "o compartilhamento da planilha e a coluna Login."
    )
    return vazia


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


# ═══════════════════════════════════════════════════════════════════════
# PREPARAÇÃO — VOLUMETRIA
# ═══════════════════════════════════════════════════════════════════════
def preparar_base_volumetria(
    raw: pd.DataFrame, hierarquia: pd.DataFrame
) -> pd.DataFrame:
    """
    Trata a base bruta para o painel de Volumetria.

    Retorna o DataFrame com ``attrs["diagnostico"]`` (avisos e erros) para a
    página decidir como exibir — nada de ``st.stop`` aqui, o robô depende disto.
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
    diag["Fonte"] = "Robô (pasta monitorada)"

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
        .replace(["", "nan", "None", "NAN", "NULL"], pd.NA)
    )
    mon_file_c = (
        mon_file.fillna(pd.NA)
        .astype("string")
        .str.strip()
        .replace(["", "nan", "None", "NAN", "NULL"], pd.NA)
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
        .replace(["", "nan", "None", "NAN", "NULL"], pd.NA)
    )
    tec_file_c = (
        tec_file.fillna(pd.NA)
        .astype("string")
        .str.strip()
        .replace(["", "nan", "None", "NAN", "NULL"], pd.NA)
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
# CACHE EM DISCO + MANIFESTO
# ═══════════════════════════════════════════════════════════════════════
@dataclass
class ResultadoBase:
    """Resultado de uma execução do robô."""

    caminho: Path | None
    hash_arquivo: str = ""
    volumetria: pd.DataFrame | None = None
    quebra: pd.DataFrame | None = None
    manifesto: dict[str, Any] = field(default_factory=dict)
    do_cache: bool = False

    @property
    def ok(self) -> bool:
        return bool(self.manifesto.get("status") == "ok")


def caminho_cache(pasta: os.PathLike | str | None = None) -> Path:
    return Path(pasta) if pasta else config().pasta_cache


def _caminho_manifesto(pasta: os.PathLike | str | None = None) -> Path:
    return caminho_cache(pasta) / _ARQUIVO_MANIFESTO


def salvar_cache(
    df: pd.DataFrame, nome: str, pasta: os.PathLike | str | None = None
) -> Path:
    destino = caminho_cache(pasta)
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / nome
    df.to_pickle(arquivo)
    return arquivo


def ler_cache(nome: str, pasta: os.PathLike | str | None = None) -> pd.DataFrame | None:
    arquivo = caminho_cache(pasta) / nome
    if not arquivo.exists():
        return None
    try:
        df = pd.read_pickle(arquivo)
    except Exception as exc:
        logger.warning("Cache %s ilegível (%s). Será recalculado.", arquivo, exc)
        return None

    meta = manifesto(pasta).get("arquivos", {}).get(nome, {})
    for chave, valor in (meta.get("attrs") or {}).items():
        df.attrs[chave] = valor
    return df


def manifesto(pasta: os.PathLike | str | None = None) -> dict[str, Any]:
    caminho = _caminho_manifesto(pasta)
    if not caminho.exists():
        return {}
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _gravar_manifesto(
    dados: dict[str, Any], pasta: os.PathLike | str | None = None
) -> Path:
    destino = caminho_cache(pasta)
    destino.mkdir(parents=True, exist_ok=True)
    caminho = destino / _ARQUIVO_MANIFESTO
    caminho.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return caminho


def _cache_expirado(dados: dict[str, Any], ttl_minutos: int | None = None) -> bool:
    ttl = config().ttl_minutos if ttl_minutos is None else int(ttl_minutos or 0)
    if ttl <= 0:
        return False
    atualizado = dados.get("atualizado_em")
    if not atualizado:
        return True
    try:
        momento = datetime.fromisoformat(atualizado)
    except ValueError:
        return True
    return (datetime.now() - momento).total_seconds() > ttl * 60


def status_base(pasta: os.PathLike | str | None = None) -> dict[str, Any]:
    """Resumo do estado atual da base (para UI e para o robô)."""
    dados = manifesto(pasta)
    if not dados:
        return {
            "status": "sem_cache",
            "mensagem": "Nenhuma base processada ainda. Rode o robô ou envie o arquivo.",
        }
    resultado = dict(dados)
    resultado["expirado"] = _cache_expirado(dados)
    return resultado


# ═══════════════════════════════════════════════════════════════════════
# PIPELINA DO ROBÔ
# ═══════════════════════════════════════════════════════════════════════
def gerar_bases(
    caminho: os.PathLike | str | None = None,
    forcar: bool = False,
    usar_cache: bool = True,
    somente: Sequence[str] = ("volumetria", "quebra"),
    pasta_entrada: os.PathLike | str | None = None,
    pasta_cache: os.PathLike | str | None = None,
    registrar_log: Callable[[str], None] | None = None,
    arquivo_glob: str | None = None,
    **ativos_opcoes: Any,
) -> ResultadoBase:
    """
    Executa o pipeline completo e atualiza o cache:

        localizar → ler → vincular ativos → preparar (volumetria/quebra) → gravar

    ``somente`` permite processar apenas um dos painéis.
    """
    log = registrar_log or (lambda msg: logger.info("%s", msg))
    cfg = config(
        pasta_entrada=pasta_entrada,
        pasta_cache=pasta_cache,
        arquivo_glob=arquivo_glob,
    )

    arquivo = (
        Path(caminho)
        if caminho
        else localizar_base(cfg.pasta_entrada, arquivo_glob=cfg.arquivo_glob)
    )
    if arquivo is None or not arquivo.exists():
        return ResultadoBase(
            caminho=None,
            manifesto={
                "status": "sem_arquivo",
                "mensagem": f"Nenhuma base encontrada em {cfg.pasta_entrada}.",
                "pasta_entrada": str(cfg.pasta_entrada),
            },
        )

    hash_arquivo = calcular_hash(arquivo)
    anteriores = manifesto(cfg.pasta_cache)
    if (
        usar_cache
        and not forcar
        and anteriores.get("hash") == hash_arquivo
        and anteriores.get("status") == "ok"
        and not _cache_expirado(anteriores)
    ):
        log(f"Base inalterada ({arquivo.name}) — reaproveitando o cache.")
        return ResultadoBase(
            caminho=arquivo,
            hash_arquivo=hash_arquivo,
            volumetria=ler_cache(_ARQUIVO_VOLUMETRIA, cfg.pasta_cache),
            quebra=ler_cache(_ARQUIVO_QUEBRA, cfg.pasta_cache),
            manifesto=anteriores,
            do_cache=True,
        )

    log(f"Lendo base {arquivo.name} ...")
    bruta_volumetria = ler_arquivo_caminho(arquivo)
    if bruta_volumetria.empty:
        return ResultadoBase(
            caminho=arquivo,
            hash_arquivo=hash_arquivo,
            manifesto={
                "status": "vazia",
                "mensagem": f"A base {arquivo.name} não possui registros.",
            },
        )

    if "volumetria" in somente and _coluna_status_volumetria(bruta_volumetria) is None:
        mensagem = (
            f"O arquivo '{arquivo.name}' não é uma base de volumetria: "
            "coluna de status ausente. Esperado: 'STATUS DA O.S 1', "
            "'STATUS OS 1', 'STATUS DA OS 1' ou 'STATUS CONTRATO'."
        )
        dados = {
            "status": "base_invalida",
            "atualizado_em": datetime.now().isoformat(timespec="seconds"),
            "origem": str(arquivo),
            "arquivo": arquivo.name,
            "hash": hash_arquivo,
            "mensagem": mensagem,
        }
        _gravar_manifesto(dados, cfg.pasta_cache)
        return ResultadoBase(
            caminho=arquivo,
            hash_arquivo=hash_arquivo,
            manifesto=dados,
        )

    # A Quebra lê tudo como texto (como no upload da página).
    bruta_quebra = ler_arquivo_caminho(arquivo, dtype=str)

    log("Vinculando lista de ativos ...")
    try:
        ativos = carregar_lista_ativos(
            **{k: v for k, v in ativos_opcoes.items() if k in _OPCOES_ATIVOS}
        )
    except Exception as exc:  # rede indisponível não pode derrubar o robô
        logger.warning("Falha ao carregar a lista de ativos: %s", exc)
        ativos = pd.DataFrame()
    hierarquia = _hierarquia_de(ativos)

    fonte_ativos = ativos.attrs.get("fonte_ativos", "")
    erro_ativos = ativos.attrs.get("erro_ativos", "")

    volumetria_df: pd.DataFrame | None = None
    quebra_df: pd.DataFrame | None = None

    if "volumetria" in somente:
        log("Gerando base de Volumetria ...")
        volumetria_df = preparar_base_volumetria(bruta_volumetria, hierarquia)
        salvar_cache(volumetria_df, _ARQUIVO_VOLUMETRIA, cfg.pasta_cache)

    if "quebra" in somente:
        log("Gerando base de Quebra de Agenda ...")
        quebra_df = preparar_base_quebra(
            bruta_quebra, ativos, fonte_ativos, erro_ativos
        )
        salvar_cache(quebra_df, _ARQUIVO_QUEBRA, cfg.pasta_cache)

    dados = {
        "status": "ok",
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        "origem": str(arquivo),
        "arquivo": arquivo.name,
        "hash": hash_arquivo,
        "modificado_em": datetime.fromtimestamp(arquivo.stat().st_mtime).isoformat(
            timespec="seconds"
        ),
        "fonte_ativos": fonte_ativos,
        "erro_ativos": erro_ativos,
        "registros_ativos": len(ativos),
        "arquivos": {
            _ARQUIVO_VOLUMETRIA: _meta_cache(volumetria_df, bruta_volumetria),
            _ARQUIVO_QUEBRA: _meta_cache(quebra_df, bruta_quebra),
        },
    }
    _gravar_manifesto(dados, cfg.pasta_cache)
    log(f"Cache atualizado: {cfg.pasta_cache}")

    return ResultadoBase(
        caminho=arquivo,
        hash_arquivo=hash_arquivo,
        volumetria=volumetria_df,
        quebra=quebra_df,
        manifesto=dados,
    )


def _hierarquia_de(ativos: pd.DataFrame) -> pd.DataFrame:
    """Converte a lista de ativos no formato usado pela Volumetria."""
    if ativos is None or ativos.empty or "Login" not in ativos.columns:
        return pd.DataFrame()
    return pd.DataFrame(
        {
            "__LOGIN_KEY": Utils.normalizar_login(ativos["Login"]),
            "__TEC_GS": ativos["Técnico"] if "Técnico" in ativos.columns else "",
            "__MON_GS": ativos["Monitor"] if "Monitor" in ativos.columns else "",
        }
    ).drop_duplicates("__LOGIN_KEY")


def _meta_cache(df: pd.DataFrame | None, bruta: pd.DataFrame) -> dict[str, Any]:
    if df is None:
        return {}
    return {
        "registros": len(df),
        "colunas": len(df.columns),
        "registros_brutos": len(bruta),
        "attrs": {
            k: v for k, v in df.attrs.items() if isinstance(v, (str, int, float, bool))
        },
    }


def carregar_base_volumetria(
    forcar: bool = False,
    usar_cache: bool = True,
    **kwargs: Any,
) -> pd.DataFrame | None:
    """Base de Volumetria pronta (cache do robô, recalculando quando necessário)."""
    cache_invalido = False
    if usar_cache and not forcar:
        dados = manifesto(kwargs.get("pasta_cache"))
        if dados.get("status") == "ok" and not _cache_expirado(dados):
            cache = ler_cache(_ARQUIVO_VOLUMETRIA, kwargs.get("pasta_cache"))
            if cache is not None and not _colunas_volumetria_ausentes(cache):
                return cache
            cache_invalido = True

    resultado = gerar_bases(
        forcar=forcar or cache_invalido,
        usar_cache=usar_cache,
        somente=("volumetria",),
        **kwargs,
    )
    if resultado.manifesto.get("status") == "base_invalida":
        raise ValueError(resultado.manifesto["mensagem"])

    base = resultado.volumetria
    if base is None:
        return None

    ausentes = _colunas_volumetria_ausentes(base)
    if ausentes:
        raise ValueError(
            "Base de volumetria inválida. Colunas obrigatórias ausentes: "
            + ", ".join(ausentes)
        )
    erros = base.attrs.get("diagnostico", {}).get("erros", [])
    if erros:
        raise ValueError("Base de volumetria inválida: " + "; ".join(erros))
    return base


def _colunas_volumetria_ausentes(df: pd.DataFrame) -> list[str]:
    """Colunas consumidas pela página de Volumetria."""
    obrigatorias = (COL_STATUS, COL_TOTAL, COL_TECNICO, COL_MONITOR, COL_REGIAO)
    return [coluna for coluna in obrigatorias if coluna not in df.columns]


def carregar_base_quebra(
    forcar: bool = False,
    usar_cache: bool = True,
    **kwargs: Any,
) -> pd.DataFrame | None:
    """Base de Quebra de Agenda pronta (cache do robô, recalculando quando necessário)."""
    if usar_cache and not forcar:
        dados = manifesto(kwargs.get("pasta_cache"))
        if dados.get("status") == "ok" and not _cache_expirado(dados):
            cache = ler_cache(_ARQUIVO_QUEBRA, kwargs.get("pasta_cache"))
            if cache is not None:
                return cache
    return gerar_bases(
        forcar=forcar, usar_cache=usar_cache, somente=("quebra",), **kwargs
    ).quebra


# ═══════════════════════════════════════════════════════════════════════
# APOIO À INTERFACE (opcional — só é chamado pelas páginas)
# ═══════════════════════════════════════════════════════════════════════
def render_status_base(
    dados: dict[str, Any] | None = None,
    *,
    titulo: str = "🤖 Base automática (robô)",
) -> None:
    """Mostra a situação da base gerada pelo robô na barra lateral."""
    import streamlit as st

    dados = dados if dados is not None else status_base()
    status = dados.get("status")

    if status != "ok":
        st.caption(f"🤖 {dados.get('mensagem', 'Base automática indisponível.')}")
        return

    with st.container():
        st.markdown(f"**{titulo}**")
        st.caption(
            f"📄 `{dados.get('arquivo', '—')}`  \n"
            f"🕒 {_formatar_data(dados.get('atualizado_em'))}  \n"
            f"📦 Volumetria: {dados.get('arquivos', {}).get(_ARQUIVO_VOLUMETRIA, {}).get('registros', 0):,} registros".replace(
                ",", "."
            )
        )


def _formatar_data(valor: str | None) -> str:
    if not valor:
        return "—"
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m/%Y %H:%M:%S")
    except ValueError:
        return str(valor)


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
    "STATUS_ORDEM",
    "ConfigBase",
    "ResultadoBase",
    "Utils",
    "calcular_hash",
    "carregar_base_quebra",
    "carregar_base_volumetria",
    "carregar_hierarquia",
    "carregar_lista_ativos",
    "config",
    "gerar_bases",
    "ler_arquivo_bytes",
    "ler_arquivo_caminho",
    "ler_cache",
    "localizar_base",
    "manifesto",
    "normalizar_lista_ativos",
    "preparar_base_quebra",
    "preparar_base_volumetria",
    "render_status_base",
    "salvar_cache",
    "status_base",
]
