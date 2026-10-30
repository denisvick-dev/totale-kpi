"""
components/criterios.py
=======================
Módulo centralizado de critérios de classificação para o portal TOTALE.

CRITÉRIOS OFICIAIS (ordem de prioridade da classificação):
    🏠 NOVOS DOMICÍLIOS (AND — TIPO O.S 1 contém um dos termos de ND)
        ADESAO · ADESÃO · ADESA · NOVO · NOVA · NOVO DOMICILIO ·
        INSTALACAO · INSTALAÇÃO · INST · PRIMEIRA · 1 VIA · PRIMEIRO ACESSO

    🔄 MIGRAÇÃO (AND — os 2 critérios juntos):
        1️⃣  TIPO O.S 1  contém  "MUDANCA DE PACOTE"
        2️⃣  HABILIDADE  contém  "PON"

    🏢 PME (AND — os 2 critérios juntos, sobrepõe Novos Domicílios):
        1️⃣  É Novos Domicílios
        2️⃣  HABILIDADE DE TRABALHO contém "PME"

    🔦 FLAG_GPON (auto-gerado quando a coluna não existe):
        HABILIDADE DE TRABALHO contém "PON" → "Sim"

    ⚪ OUTROS: não atende a nenhum dos critérios acima.

ARQUITETURA:
    ✅ Regras de classificação
    ✅ Detecção de colunas
    ✅ Métricas consolidadas (baseadas em TOTAL DE TAREFAS)
    ✅ Painéis internos de UI
"""

from __future__ import annotations

import unicodedata
from typing import Any

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════
# CONSTANTES
# ═══════════════════════════════════════════════════════════════════════
VAZIOS_GERAIS: set[str] = {
    "",
    "NAN",
    "NONE",
    "NULL",
    "N/A",
    "NA",
    "NAO INFORMADO",
    "NÃO INFORMADO",
    "-",
    "SEM INFORMACAO",
    "SEM INFORMAÇÃO",
    ".",
    "..",
    "...",
}
VAZIOS_CONTRATO: set[str] = {"", "NULL", "NAN", "NONE"}


def _norm_str(texto: Any) -> str:
    """Normaliza qualquer valor para ASCII maiúsculo sem acentos."""
    return (
        unicodedata.normalize("NFKD", str(texto))
        .encode("ascii", errors="ignore")
        .decode("ascii")
        .upper()
        .strip()
    )


TERMO_MIGRACAO_OS: str = "MUDANCA DE PACOTE"
VALOR_FLAG_GPON_SIM: str = "SIM"
TERMO_GPON_HABILIDADE: str = "PON"
TERMO_PME_HABILIDADE: str = "PME"

#: Termos que caracterizam Novos Domicílios em TIPO O.S 1.
TERMOS_ND: tuple[str, ...] = (
    "ADESAO",
    "ADESÃO",
    "ADESA",
    "NOVO",
    "INSTALACAO",
    "INSTALAÇÃO",
    "INST",
    "NOVA",
    "NOVO DOMICILIO",
    "NOVO DOMICÍLIO",
    "PRIMEIRA",
    "1 VIA",
    "PRIMEIRO ACESSO",
)
TERMOS_PME: tuple[str, ...] = (TERMO_PME_HABILIDADE,)

CANDS_TIPO_OS_1: list[str] = [
    "TIPO O.S 1",
    "TIPO OS 1",
    "TIPO O.S. 1",
    "TIPO_OS_1",
    "TIPO_O_S_1",
    "TIPOOS1",
    "TIPO OS 1",
    "TIPO O.S",
    "TIPO_DE_OS",
    "TIPO DE OS",
]
CANDS_FLAG_GPON: list[str] = [
    "FLAG_GPON",
    "FLAG GPON",
    "FLAGGPON",
    "IS_GPON",
]
CANDS_CAPACIDADE: list[str] = [
    "CATEGORIAS DA CAPACIDADE",
    "CATEGORIA DA CAPACIDADE",
    "CATEGORIAS CAPACIDADE",
    "CATEGORIA CAPACIDADE",
    "CAPACIDADE",
]
CANDS_HABILIDADE: list[str] = [
    "HABILIDADE DE TRABALHO",
    "HABILIDADES DE TRABALHO",
    "HABILIDADE",
    "HABILIDADES",
    "SKILL",
    "SKILLS",
    "HABILIDADE_TECNICA",
    "HABILIDADE TÉCNICA",
]

#: Termos que não podem ser confundidos com "TIPO O.S 1" no fallback genérico.
_RUIDO_TIPO_OS: tuple[str, ...] = (
    "ATIVIDADE",
    "DATA",
    "STATUS",
    "SITUACAO",
    "CONTRATO",
    "CLIENTE",
    "EQUIPE",
    "HABILIDAD",
    "ENDERECO",
    "BAIRRO",
    "CIDADE",
    "PACOTE",
    "PLANO",
)


# ═══════════════════════════════════════════════════════════════════════
# NORMALIZAÇÃO
# ═══════════════════════════════════════════════════════════════════════
def normalizar_str(texto: str) -> str:
    return _norm_str(texto)


def norm_col_nome(nome: str) -> str:
    return (
        unicodedata.normalize("NFKD", nome)
        .encode("ascii", errors="ignore")
        .decode("ascii")
        .upper()
        .strip()
        .replace(".", "")
        .replace("_", " ")
    )


# ═══════════════════════════════════════════════════════════════════════
# DETECÇÃO DE COLUNAS
# ═══════════════════════════════════════════════════════════════════════
def detectar_cols_tipo(df: pd.DataFrame) -> list[str]:
    return [
        c
        for c in df.columns
        if "TIPO" in norm_col_nome(str(c))
        and ("OS" in norm_col_nome(str(c)) or "O S" in norm_col_nome(str(c)))
    ]


def detectar_col_tipo_os_1(df: pd.DataFrame) -> str | None:
    if df is None or df.empty:
        return None

    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}

    # 1. Busca exata pelos apelidos conhecidos
    for cand in CANDS_TIPO_OS_1:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]

    # 2. Busca parcial: TIPO + O.S + 1
    for col_norm, col_real in cols_norm.items():
        if (
            "TIPO" in col_norm
            and ("OS" in col_norm or "O S" in col_norm)
            and (col_norm.endswith(("1", " 1")) or " 1 " in col_norm)
        ):
            return col_real

    # 3. Qualquer coluna com TIPO e O.S
    for col_norm, col_real in cols_norm.items():
        if "TIPO" in col_norm and ("OS" in col_norm or "O S" in col_norm):
            return col_real

    # 4. Fallback: coluna genérica de TIPO (sem ruído de outras naturezas)
    for col_norm, col_real in cols_norm.items():
        if "TIPO" in col_norm and not any(r in col_norm for r in _RUIDO_TIPO_OS):
            return col_real

    return None


def detectar_col_flag_gpon(df: pd.DataFrame) -> str | None:
    if df is None or df.empty:
        return None
    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}
    for cand in CANDS_FLAG_GPON:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for col_norm, col_real in cols_norm.items():
        if "GPON" in col_norm and "FLAG" in col_norm:
            return col_real
    return None


def detectar_col_capacidade(df: pd.DataFrame) -> str | None:
    if df is None or df.empty:
        return None
    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}
    for cand in CANDS_CAPACIDADE:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for col_norm, col_real in cols_norm.items():
        if "CAPACIDADE" in col_norm:
            return col_real
    return None


def detectar_col_habilidade(df: pd.DataFrame) -> str | None:
    if df is None or df.empty:
        return None
    for nome in [
        "HABILIDADE DE TRABALHO",
        "Habilidade de Trabalho",
        "habilidade de trabalho",
        "HABILIDADES DE TRABALHO",
        "HABILIDADE_DE_TRABALHO",
        "HABILIDADE",
    ]:
        if nome in df.columns:
            return nome
    for c in df.columns:
        if str(c).strip().upper() == "HABILIDADE DE TRABALHO":
            return c
    cols_norm = {norm_col_nome(str(c)): c for c in df.columns}
    for cand in CANDS_HABILIDADE:
        cn = norm_col_nome(cand)
        if cn in cols_norm:
            return cols_norm[cn]
    for c in df.columns:
        if "HABIL" in str(c).upper():
            return c
    for c in df.columns:
        try:
            amostra = df[c].dropna().astype(str).head(100)
            if amostra.str.contains(r"PON\(|PME\(", na=False, regex=True).any():
                return c
        except Exception:
            continue
    return None


def detectar_col_status_atividade(df: pd.DataFrame) -> str | None:
    for nome in [
        "STATUS DA ATIVIDADE",
        "Status da Atividade",
        "status da atividade",
        "STATUS_DA_ATIVIDADE",
    ]:
        if nome in df.columns:
            return nome
    for c in df.columns:
        if str(c).strip().upper() == "STATUS DA ATIVIDADE":
            return c
    alvo_norm = norm_col_nome("STATUS DA ATIVIDADE")
    for c in df.columns:
        if norm_col_nome(str(c)) == alvo_norm:
            return c
    for c in df.columns:
        cu = str(c).upper()
        if "STATUS" in cu and "ATIVIDADE" in cu:
            return c
    return None


def detectar_col_contrato(df: pd.DataFrame) -> str | None:
    for nome in ["CONTRATO", "Contrato", "contrato"]:
        if nome in df.columns:
            return nome
    for c in df.columns:
        if str(c).strip().upper() == "CONTRATO":
            return c
    alvo_norm = norm_col_nome("CONTRATO")
    for c in df.columns:
        if norm_col_nome(str(c)) == alvo_norm:
            return c
    _EVITAR = {"STATUS", "DATA", "TIPO", "VALOR", "PLANO", "SITUACAO"}
    candidatas = [
        c
        for c in df.columns
        if "CONTRATO" in str(c).upper()
        and not any(e in str(c).upper() for e in _EVITAR)
    ]
    if candidatas:
        return min(candidatas, key=lambda x: len(str(x)))
    return None


# ═══════════════════════════════════════════════════════════════════════
# COLUNAS AUXILIARES
# ═══════════════════════════════════════════════════════════════════════
def criar_coluna_tipos_agrupados(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    cols_tipo = detectar_cols_tipo(df)

    if not cols_tipo:
        df["_TIPOS_OS_AGRUPADOS"] = ""
        df["_TIPOS_OS_SET"] = pd.Series(
            [frozenset() for _ in range(len(df))],
            index=df.index,
            dtype=object,
        )
        return df

    def _agrupar(row: pd.Series) -> tuple[str, frozenset[str]]:
        raw, norm = set(), set()
        for col in cols_tipo:
            val = str(row.get(col, "")).strip()
            if not val or val.upper() in VAZIOS_GERAIS:
                continue
            vn = normalizar_str(val)
            if vn and vn not in VAZIOS_GERAIS:
                raw.add(val)
                norm.add(vn)
        return (" + ".join(sorted(raw)) if raw else ""), frozenset(norm)

    res = df[cols_tipo].apply(_agrupar, axis=1, result_type="expand")
    df["_TIPOS_OS_AGRUPADOS"] = res[0]
    df["_TIPOS_OS_SET"] = res[1]
    return df


def criar_flag_gpon(df: pd.DataFrame) -> tuple[pd.DataFrame, str | None, int]:
    df = df.copy()

    col_ex = detectar_col_flag_gpon(df)
    if col_ex and col_ex != "FLAG_GPON":
        df = df.rename(columns={col_ex: "FLAG_GPON"})

    if "FLAG_GPON" in df.columns:
        n_sim = int(
            df["FLAG_GPON"]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.upper()
            .eq(VALOR_FLAG_GPON_SIM)
            .sum()
        )
        return df, None, n_sim

    col_hab = detectar_col_habilidade(df)
    if not col_hab:
        df["FLAG_GPON"] = "Não"
        return df, None, 0

    serie = df[col_hab].fillna("").astype(str).str.strip()
    mask = serie.str.upper().str.contains(TERMO_GPON_HABILIDADE, na=False, regex=False)
    df["FLAG_GPON"] = np.where(mask, "Sim", "Não")
    return df, col_hab, int(mask.sum())


# ═══════════════════════════════════════════════════════════════════════
# CLASSIFICAÇÃO PRINCIPAL
# ═══════════════════════════════════════════════════════════════════════
def classificar_tipo_servico(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """
    Classifica cada linha em: Migração, PME, Novos Domicílios ou Outros.

    Regras oficiais (ordem de escrita = ordem de prioridade):
      1. NOVOS DOMICÍLIOS = TIPO O.S 1 contém um dos ``TERMOS_ND``
      2. MIGRAÇÃO  = TIPO O.S 1 contém "MUDANCA DE PACOTE"  AND
                     HABILIDADE DE TRABALHO contém "PON"
      3. PME       = é Novos Domicílios  AND  HABILIDADE contém "PME"
                     (sobrepõe Novos Domicílios quando a habilidade é PME)
      4. OUTROS    = restante
    """
    df = df.copy()

    # Garante colunas auxiliares
    df = criar_coluna_tipos_agrupados(df)
    df, _, _ = criar_flag_gpon(df)

    col_tipo_os_1 = detectar_col_tipo_os_1(df)
    col_hab = detectar_col_habilidade(df)

    # ── Séries normalizadas ──────────────────────────────────────────
    serie_tipo_os_1 = (
        df[col_tipo_os_1].fillna("").astype(str).map(normalizar_str)
        if col_tipo_os_1
        else pd.Series("", index=df.index, dtype=object)
    )
    serie_habilidade = (
        df[col_hab].fillna("").astype(str).map(normalizar_str)
        if col_hab
        else pd.Series("", index=df.index, dtype=object)
    )

    # ── Máscaras ─────────────────────────────────────────────────────
    # 1) Novos Domicílios: TIPO O.S 1 contém um dos termos de ND
    flag_nd = _mask_novos_domicilios(df)

    # 2) Migração: MUDANCA DE PACOTE + HABILIDADE contendo PON
    flag_migracao_tipo = serie_tipo_os_1.str.contains(
        _norm_str(TERMO_MIGRACAO_OS), na=False, regex=False
    )
    flag_hab_pon = serie_habilidade.str.contains(
        _norm_str(TERMO_GPON_HABILIDADE), na=False, regex=False
    )
    flag_migracao = flag_migracao_tipo & flag_hab_pon

    # 3) PME: Novos Domicílios + HABILIDADE contendo PME
    flag_hab_pme = serie_habilidade.str.contains(
        _norm_str(TERMO_PME_HABILIDADE), na=False, regex=False
    )
    flag_pme = flag_nd & flag_hab_pme

    # ── Aplicação da lógica de prioridade ────────────────────────────
    tipo = pd.Series("Outros", index=df.index, dtype=object)
    tipo.loc[flag_nd.fillna(False)] = "Novos Domicílios"
    tipo.loc[flag_migracao.fillna(False)] = "Migração"
    tipo.loc[flag_pme.fillna(False)] = "PME"  # PME sobrepõe ND

    df["TIPO_SERVICO"] = tipo
    return df, tipo


# ═══════════════════════════════════════════════════════════════════════
# MÉTRICAS DOS CRITÉRIOS — BASEADAS EM TOTAL DE TAREFAS
# ═══════════════════════════════════════════════════════════════════════
def _serie_total_tarefas(df: pd.DataFrame) -> pd.Series:
    """Retorna série numérica de TOTAL DE TAREFAS (default = 1)."""
    if "TOTAL DE TAREFAS" not in df.columns:
        return pd.Series(1, index=df.index, dtype="float64")

    return (
        pd.to_numeric(df["TOTAL DE TAREFAS"], errors="coerce")
        .fillna(1)
        .round()
        .clip(lower=0)
    )


def _serie_tipo_os_1_normalizada(df: pd.DataFrame) -> pd.Series:
    """Série normalizada (ASCII maiúsculo) da coluna TIPO O.S 1."""
    col_tipo_os_1 = detectar_col_tipo_os_1(df)
    if not col_tipo_os_1:
        return pd.Series("", index=df.index, dtype=object)
    return df[col_tipo_os_1].fillna("").astype(str).map(_norm_str)


def _mask_novos_domicilios(df: pd.DataFrame) -> pd.Series:
    """
    Máscara bruta de Novos Domicílios.

    Critério oficial: **TIPO O.S 1** contém um dos ``TERMOS_ND``.
    A busca é iterativa e com ``regex=False`` (segurança contra caracteres
    especiais vindos da base).
    """
    serie_tipo_os_1 = _serie_tipo_os_1_normalizada(df)
    flag_nd = pd.Series(False, index=df.index)
    for termo in TERMOS_ND:
        termo_norm = _norm_str(termo)
        if termo_norm:
            flag_nd |= serie_tipo_os_1.str.contains(termo_norm, na=False, regex=False)
    return flag_nd.fillna(False).astype(bool)
