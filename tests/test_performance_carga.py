"""Suíte do robô TOTALE (``components/robo_local.py``).

Cobre o motor puro — padronização de texto/colunas, descoberta de candidatos,
leitura resiliente de CSV/Excel, detecção de base, fachada ``TotaleRoboEngine``
e o ciclo headless/CLI —, o ciclo de sincronismo Streamlit (com um dublê leve do
``streamlit``, sem runtime) e o benchmark de desempenho da carga citado no
docstring de :func:`components.robo_local._padronizar_coluna_texto`.

O dublê de Streamlit é intencional: as funções de UI são exercitadas sem subir
um ``ScriptRunContext``, o que mantém os testes determinísticos e rápidos.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import types
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from components import robo_local as robo

# ── Utilidades de arquivo ───────────────────────────────────────────


def _tocar(caminho: Path, mtime_ns: int) -> Path:
    os.utime(caminho, ns=(mtime_ns, mtime_ns))
    return caminho


def _gravar_csv(
    pasta: Path,
    nome: str,
    texto: str,
    encoding: str = "utf-8",
    mtime_ns: int = 1_700_000_000_000_000_000,
) -> Path:
    caminho = pasta / nome
    caminho.write_bytes(texto.encode(encoding))
    return _tocar(caminho, mtime_ns)


def _gravar_xlsx(
    pasta: Path,
    nome: str,
    linhas: list[list[object]],
    mtime_ns: int = 1_700_000_000_000_000_000,
) -> Path:
    caminho = pasta / nome
    pd.DataFrame(linhas[1:], columns=linhas[0]).to_excel(caminho, index=False)
    return _tocar(caminho, mtime_ns)


BASE_CSV = "LOGIN;BASE;QTDE\njoao;;3\nmaria;NET-LESTE;5\n"


# ── _celula_para_texto ──────────────────────────────────────────────


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (None, ""),
        (pd.NA, ""),
        (float("nan"), ""),
        (True, "True"),
        (False, "False"),
        (7, "7"),
        (-3, "-3"),
        (7.0, "7"),
        (-0.0, "0"),
        (2.5, "2.5"),
        (1e17, "100000000000000000"),
        (1e-7, "1e-07"),
        ("  joao  ", "joao"),
        ("123.0", "123"),
        ("-45.0", "-45"),
        ("1.5", "1.5"),
        ("versão 1.0", "versão 1.0"),
        ("NaT", ""),
        ("<NA>", ""),
        ("nan", ""),
        ("None", ""),
        (pd.Timestamp("2024-03-05 10:00:00"), "2024-03-05 10:00:00"),
    ],
)
def test_celula_para_texto(valor: object, esperado: str) -> None:
    assert robo._celula_para_texto(valor) == esperado


# ── _nomes_colunas_unicos ───────────────────────────────────────────


def test_nomes_colunas_unicos_limpa_e_desambigua() -> None:
    assert robo._nomes_colunas_unicos(["\ufeffLOGIN", "BASE\xa0", " QTDE "]) == [
        "LOGIN",
        "BASE",
        "QTDE",
    ]
    assert robo._nomes_colunas_unicos(["", None, "Unnamed: 2"]) == [
        "col_0",
        "col_1",
        "col_2",
    ]


def test_nomes_colunas_unicos_nao_colide_com_sufixo_existente() -> None:
    # A duplicata de "A" não pode virar "A.1" quando "A.1" já existe no arquivo.
    assert robo._nomes_colunas_unicos(["A", "A", "A.1"]) == ["A", "A.2", "A.1"]
    assert robo._nomes_colunas_unicos(["X", "X", "X", "X.1"]) == [
        "X",
        "X.2",
        "X.3",
        "X.1",
    ]


# ── _padronizar_coluna_texto (rota vetorial) ────────────────────────


def test_padronizar_coluna_bool_datetime() -> None:
    booleans = robo._padronizar_coluna_texto(pd.Series([True, False, None]))
    assert list(booleans[:2]) == ["True", "False"]
    assert pd.isna(booleans.iloc[2])

    datas = pd.Series(
        pd.to_datetime(["2024-01-01 00:00:00", None, "2024-03-05 10:20:30"])
    )
    padrao = robo._padronizar_coluna_texto(datas)
    assert padrao.iloc[0] == "2024-01-01 00:00:00"
    assert padrao.iloc[2] == "2024-03-05 10:20:30"
    assert pd.isna(padrao.iloc[1])


def test_padronizar_coluna_numerica_remove_decimal_zero() -> None:
    serie = pd.Series([1.0, 2.5, None, -0.0, 3.0, 1e17])
    assert list(robo._padronizar_coluna_texto(serie)) == [
        "1",
        "2.5",
        pd.NA,
        "0",
        "3",
        "100000000000000000",
    ]


def test_padronizar_coluna_texto_remove_sufixo_decimal() -> None:
    serie = pd.Series([" 123.0 ", "-45.0", "1.5", "abc", "  ", "N/A"])
    assert list(robo._padronizar_coluna_texto(serie)) == [
        "123",
        "-45",
        "1.5",
        "abc",
        "",
        "N/A",
    ]


def test_padronizar_dataframe_equivalencia_com_rota_celula_a_celula() -> None:
    """A rota vetorial e a célula a célula terminam no mesmo DataFrame.

    A comparação passa pela padronização completa (``_celula_para_texto`` +
    máscara de ausentes), porque é esse o resultado publicado no pipeline.
    """
    df = pd.DataFrame(
        {
            "NUM": [1.0, 2.5, None, -0.0, 1e17, 1e-7, 12345678901234567890.0],
            "BOOL": [True, False, None, True, False, True, False],
            "DATA": pd.to_datetime(
                [
                    "2024-01-01 00:00:00",
                    None,
                    "2024-03-05 10:20:30",
                    "2024-12-31 23:59:59",
                    "2024-06-15 12:00:00",
                    "2024-02-29 00:00:00",
                    "2024-07-04 08:30:00",
                ]
            ),
            "TEXTO": ["  x ", "123.0", "n/a", "-", "não informado", "abc", "NaT"],
        }
    )
    vetorial = robo._padronizar_dataframe(df)

    celula = df.copy()
    for col in celula.columns:
        texto = celula[col].map(robo._celula_para_texto).str.strip()
        celula[col] = texto.mask(texto.str.lower().isin(robo._VALORES_AUSENTES), pd.NA)
    celula = celula.dropna(how="all")

    assert list(vetorial.columns) == list(celula.columns)
    for col in vetorial.columns:
        assert list(vetorial[col].fillna("<NA>")) == list(celula[col].fillna("<NA>")), (
            col
        )


def test_padronizar_dataframe_mascara_ausentes_e_descarta_linhas_vazias() -> None:
    df = pd.DataFrame(
        {
            "A": ["joao", "", "n/a", "NÃO INFORMADO", "-"],
            "B": ["1", "nan", "NULL", "  ", "2"],
        }
    )
    saida = robo._padronizar_dataframe(df)
    # Linhas cujas células viraram ausentes em todas as colunas são descartadas.
    assert list(saida["A"]) == ["joao", pd.NA]
    assert list(saida["B"]) == ["1", "2"]
    assert len(saida) == 2

    vazias = robo._padronizar_dataframe(pd.DataFrame({"A": ["nan", "  ", None]}))
    assert vazias.empty


def test_padronizar_dataframe_vazio_sem_colunas() -> None:
    vazio = robo._padronizar_dataframe(pd.DataFrame())
    assert vazio.empty and list(vazio.columns) == []


def test_padronizar_dataframe_renameia_colunas() -> None:
    df = pd.DataFrame([["a", "b"]], columns=["\ufeffLOGIN", "LOGIN"])
    assert list(robo._padronizar_dataframe(df).columns) == ["LOGIN", "LOGIN.1"]


# ── Cabeçalho e colunas esperadas ───────────────────────────────────


def test_cabecalho_fraco() -> None:
    assert robo._cabecalho_fraco([]) is True
    assert robo._cabecalho_fraco(["col_0", "col_1"]) is True
    assert robo._cabecalho_fraco(["LOGIN", "col_1"]) is True
    assert robo._cabecalho_fraco(["LOGIN", "BASE", "col_2"]) is False
    assert robo._cabecalho_fraco(["Unnamed: 0", "Unnamed: 1"]) is True


def test_alinhar_e_verificar_colunas_esperadas() -> None:
    df = pd.DataFrame({"Login": ["a"], "qtde": ["1"]})
    alinhado = robo._alinhar_colunas_esperadas(df, ["LOGIN", "QTDE"])
    assert list(alinhado.columns) == ["LOGIN", "QTDE"]
    assert robo._contem_colunas(alinhado, ["login", "qtde"]) is True
    assert robo._faltam_colunas(alinhado, ["LOGIN", "BASE"]) == ["BASE"]
    assert robo._contem_colunas(df, None) is True
    assert robo._faltam_colunas(df, None) == []
    assert robo._alinhar_colunas_esperadas(df, None) is df


# ── Detecção de base ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("nome", "marcador", "base"),
    [
        ("Atividades-SPO.csv", "SPO", "NET-LESTE"),
        ("atividades-spo.csv", "SPO", "NET-LESTE"),
        ("Atividades-GRS.xlsx", "GRS", "NET-GUARULHOS"),
        ("Atividades-ABCDM.xlsm", "ABCDM", "NET-ABCDM"),
        ("C:/Users/x/Downloads/Atividades-ABCDM.csv", "ABCDM", "NET-ABCDM"),
        ("Atividades-OUTRA.csv", None, None),
        ("", None, None),
        (None, None, None),
    ],
)
def test_detectar_base_arquivo(
    nome: str | None, marcador: str | None, base: str | None
) -> None:
    assert robo.detectar_marcador_arquivo(nome) == marcador
    assert robo.detectar_base_arquivo(nome) == base


def test_detectar_marcador_prefere_o_mais_longo() -> None:
    assert robo.detectar_marcador_arquivo("Atividades-ABCDM-SPO.csv") == "ABCDM"


# ── Aplicação de BASE no DataFrame ──────────────────────────────────


def test_aplicar_base_cria_coluna_quando_nao_existe() -> None:
    saida = robo._aplicar_base_no_dataframe(
        pd.DataFrame({"A": ["1", "2"]}), "NET-LESTE"
    )
    assert list(saida["BASE"]) == ["NET-LESTE", "NET-LESTE"]


def test_aplicar_base_preenche_apenas_vazios() -> None:
    df = pd.DataFrame({"BASE": ["NET-GUARULHOS", "", "  ", None]})
    saida = robo._aplicar_base_no_dataframe(df, "NET-LESTE")
    assert list(saida["BASE"]) == [
        "NET-GUARULHOS",
        "NET-LESTE",
        "NET-LESTE",
        "NET-LESTE",
    ]


def test_canonizar_coluna_base_funde_variantes() -> None:
    df = pd.DataFrame({"Base": ["", "NET-ABCDM"], "base": ["NET-LESTE", "NET-LESTE"]})
    saida = robo._aplicar_base_no_dataframe(df, "NET-GUARULHOS")
    assert list(saida.columns) == ["BASE"]
    assert list(saida["BASE"]) == ["NET-LESTE", "NET-ABCDM"]


def test_unificar_nomes_colunas_usa_grafia_do_primeiro() -> None:
    frames = [
        pd.DataFrame({"Login": ["a"]}),
        pd.DataFrame({"login": ["b"], "QTDE": ["1"]}),
    ]
    unificados = robo._unificar_nomes_colunas(frames)
    assert list(unificados[1].columns) == ["Login", "QTDE"]
    assert list(unificados[0].columns) == ["Login"]


# ── Metadados e formatação ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("bytes_", "esperado"),
    [(0, "0 B"), (1023, "1023 B"), (2048, "2.0 KB"), (5 * 1024 * 1024, "5.00 MB")],
)
def test_formatar_tamanho(bytes_: int, esperado: str) -> None:
    assert robo.formatar_tamanho(bytes_) == esperado


def test_obter_metadados_arquivo(tmp_path: Path) -> None:
    arquivo = tmp_path / "Atividades-SPO.csv"
    arquivo.write_bytes(BASE_CSV.encode("utf-8"))
    meta = robo.obter_metadados_arquivo(str(arquivo))
    assert meta["nome"] == "Atividades-SPO.csv"
    assert meta["ext"] == ".csv"
    assert meta["tamanho"] == f"{arquivo.stat().st_size} B"
    assert meta["caminho_completo"] == str(arquivo.resolve())
    datetime.strptime(meta["modificado"], "%d/%m/%Y %H:%M:%S")


def test_obter_metadados_arquivo_inexistente() -> None:
    meta = robo.obter_metadados_arquivo("/tmp/nao-existe-abc123.csv")
    assert meta["tamanho"] == "—" and meta["modificado"] == "—"
    assert robo.obter_metadados_arquivo(None)["nome"] == "Desconhecido"


def test_arquivo_ignorado() -> None:
    for nome in (
        "~$Atividades-SPO.xlsx",
        ".oculto.csv",
        "Atividades-SPO.csv.crdownload",
    ):
        assert robo._arquivo_ignorado(nome), nome
    for nome in ("Atividades-SPO.csv", "atividades-grs.XLSX"):
        assert not robo._arquivo_ignorado(nome), nome


def test_pasta_robo_padrao_usa_home_e_cria_a_pasta(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(robo, "_obter_pasta_downloads_windows", lambda: None)
    monkeypatch.setattr(robo.Path, "home", classmethod(lambda cls: tmp_path))
    assert robo.obter_pasta_robo_padrao() == str((tmp_path / "downloads").resolve())
    assert (tmp_path / "downloads").is_dir()


def test_pasta_downloads_windows_fora_do_windows(monkeypatch) -> None:
    monkeypatch.setattr(robo.sys, "platform", "linux")
    assert robo._obter_pasta_downloads_windows() is None


def test_pasta_downloads_windows_hresult_invalido_libera_caminho(
    monkeypatch,
) -> None:
    class _CUByte:
        def __mul__(self, outro: int) -> type:
            class _Vetor:
                @staticmethod
                def from_buffer_copy(*_args: object) -> bytes:
                    return b"\x00" * outro

            return _Vetor

    caminho_alocado = types.SimpleNamespace(value="C:\\Users\\teste\\Downloads")
    caminhos_liberados = []
    ctypes_falso = types.SimpleNamespace(
        c_ubyte=_CUByte(),
        c_wchar_p=lambda: caminho_alocado,
        byref=lambda x: x,
        cast=lambda x, _t: x,
        windll=types.SimpleNamespace(
            shell32=types.SimpleNamespace(SHGetKnownFolderPath=lambda *_: 1),
            ole32=types.SimpleNamespace(
                CoTaskMemFree=lambda caminho: caminhos_liberados.append(caminho)
            ),
        ),
    )
    monkeypatch.setitem(sys.modules, "ctypes", ctypes_falso)
    monkeypatch.setattr(robo.sys, "platform", "win32")
    assert robo._obter_pasta_downloads_windows() is None
    assert caminhos_liberados == [caminho_alocado]


# ── Descoberta de candidatos ────────────────────────────────────────


def test_listar_candidatos_ordena_por_mtime_e_filtra(tmp_path: Path) -> None:
    antiga = _gravar_csv(
        tmp_path, "Atividades-GRS.csv", BASE_CSV, mtime_ns=1_600_000_000_000_000_000
    )
    recente = _gravar_csv(
        tmp_path, "Atividades-SPO.csv", BASE_CSV, mtime_ns=1_800_000_000_000_000_000
    )
    temporario = tmp_path / "Atividades-ABCDM.csv.crdownload"
    temporario.write_bytes(b"x")
    _tocar(temporario, 1_900_000_000_000_000_000)
    (tmp_path / "~$Atividades-SPO.xlsx").write_bytes(b"lock")
    (tmp_path / "notas.txt").write_text("ignorado", encoding="utf-8")
    (tmp_path / "Atividades-Vazia.csv").write_bytes(b"")

    candidatos = robo._listar_candidatos_com_stat(str(tmp_path))
    assert [Path(c[0]).name for c in candidatos] == [
        "Atividades-SPO.csv",
        "Atividades-GRS.csv",
    ]
    assert candidatos[0][0] == str(recente) and candidatos[1][0] == str(antiga)
    assert candidatos[0][1] == recente.stat().st_mtime_ns
    assert candidatos[0][2] == recente.stat().st_size


def test_listar_candidatos_aceita_nomes_alternativos(tmp_path: Path) -> None:
    (tmp_path / "GRS.csv").write_bytes(BASE_CSV.encode("utf-8"))
    (tmp_path / "Atividades-Geral.csv").write_bytes(BASE_CSV.encode("utf-8"))
    (tmp_path / "folha-pagamento.csv").write_bytes(BASE_CSV.encode("utf-8"))
    nomes = {Path(c[0]).name for c in robo._listar_candidatos_com_stat(str(tmp_path))}
    assert nomes == {"GRS.csv", "Atividades-Geral.csv"}


def test_listar_candidatos_pasta_inexistente() -> None:
    assert robo._listar_candidatos_com_stat("/tmp/pasta-inexistente-xyz") == []


def test_listar_candidatos_recursivo(tmp_path: Path) -> None:
    sub = tmp_path / "sub" / "fundo"
    sub.mkdir(parents=True)
    (sub / "Atividades-SPO.csv").write_bytes(BASE_CSV.encode("utf-8"))

    assert robo._listar_candidatos_com_stat(str(tmp_path)) == []
    assert len(robo._listar_candidatos_com_stat(str(tmp_path), recursivo=True)) == 1


def test_buscar_arquivo_mais_recente_devolve_mtime_em_segundos(tmp_path: Path) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    caminho, mtime, tamanho = robo.buscar_arquivo_mais_recente(str(tmp_path))
    assert caminho == str(arquivo)
    assert mtime == pytest.approx(arquivo.stat().st_mtime_ns / 1_000_000_000)
    assert tamanho == arquivo.stat().st_size
    assert robo.buscar_arquivo_mais_recente(str(tmp_path / "nada")) == (
        None,
        None,
        None,
    )


def test_mapear_arquivos_por_base_pega_o_mais_recente_de_cada(tmp_path: Path) -> None:
    _gravar_csv(
        tmp_path, "Atividades-SPO.csv", BASE_CSV, mtime_ns=1_600_000_000_000_000_000
    )
    _gravar_csv(
        tmp_path,
        "Atividades-SPO-novo.csv",
        BASE_CSV,
        mtime_ns=1_800_000_000_000_000_000,
    )
    _gravar_csv(
        tmp_path, "Atividades-GRS.csv", BASE_CSV, mtime_ns=1_700_000_000_000_000_000
    )
    _gravar_csv(
        tmp_path, "Atividades-Extra.csv", BASE_CSV, mtime_ns=1_900_000_000_000_000_000
    )

    por_base = robo.mapear_arquivos_por_base(str(tmp_path))
    assert set(por_base) == {"NET-LESTE", "NET-GUARULHOS"}
    assert Path(por_base["NET-LESTE"][0]).name == "Atividades-SPO-novo.csv"


def test_selecionar_arquivos_sempre_o_mais_recente() -> None:
    candidatos = [
        ("a.csv", 1_600_000_000_000_000_000, 10),
        ("b.csv", 1_900_000_000_000_000_000, 10),
        ("c.csv", 1_700_000_000_000_000_000, 10),
    ]
    assert robo.selecionar_arquivos([]) == []
    for modo in ("ultimo", "ultimo_por_base", "todos"):
        assert robo.selecionar_arquivos(candidatos, modo) == [candidatos[1]]


def test_contar_arquivos_por_base() -> None:
    candidatos = [
        ("Atividades-SPO.csv", 1, 1),
        ("Atividades-SPO-2.csv", 1, 1),
        ("Atividades-GRS.csv", 1, 1),
        ("Atividades-SemMarcador.csv", 1, 1),
    ]
    assert robo.contar_arquivos_por_base(candidatos) == {
        "NET-LESTE": 2,
        "NET-GUARULHOS": 1,
        "SEM MARCADOR": 1,
    }


# ── Leitura de CSV ──────────────────────────────────────────────────


def test_quantidade_campos_csv_ignora_delimitador_entre_aspas() -> None:
    assert robo._quantidade_campos_csv("A;B;C", ";") == 3
    assert robo._quantidade_campos_csv('"OS;SERVICO";B;C', ";") == 3
    assert robo._quantidade_campos_csv("", ";") == 0
    assert robo._quantidade_campos_csv("A,B;C", ",") == 2


def test_ordem_tentativas_csv_prioriza_charset_e_separador() -> None:
    ordem = robo._ordem_tentativas_csv("LOGIN;BASE;QTDE\n".encode("utf-8"))
    assert ordem[0] == ("utf-8-sig", ";")
    assert len(ordem) == len(robo._ENCODINGS_CSV) * len(robo._SEPARADORES_CSV)

    # O charset é decidido pela linha de cabeçalho: um cabeçalho ASCII puro é
    # utf-8 válido ainda que o corpo seja cp1252.
    ascii_puro = "LOGIN;BASE;QTDE\njoão;NET-LESTE;3\n".encode("cp1252")
    assert robo._ordem_tentativas_csv(ascii_puro)[0] == ("utf-8-sig", ";")

    com_acento = "LOGIN;BASE;OBSERVAÇÃO\na;NET-LESTE;ç\n".encode("cp1252")
    assert robo._ordem_tentativas_csv(com_acento)[0] == ("cp1252", ";")

    com_virgula = "LOGIN,BASE,QTDE\n".encode("utf-8")
    assert robo._ordem_tentativas_csv(com_virgula)[0] == ("utf-8-sig", ",")


def test_ler_csv_de_bytes_separadores_e_charsets() -> None:
    df, motor = robo._ler_csv_de_bytes("A\tB\n1\t2\n".encode("utf-8"), "x.csv")
    assert motor == "csv utf-8-sig sep='\\t'" and list(df.columns) == ["A", "B"]

    df, motor = robo._ler_csv_de_bytes("A|B\n1|2\n".encode("utf-8"), "x.csv")
    assert motor == "csv utf-8-sig sep='|'" and list(df["B"]) == ["2"]

    df, _ = robo._ler_csv_de_bytes(
        "LOGIN;BASE\njoão;NET-LESTE\n".encode("cp1252"), "x.csv"
    )
    assert df["LOGIN"].iloc[0] == "joão"


def test_ler_csv_de_bytes_uma_coluna_valida() -> None:
    df, motor = robo._ler_csv_de_bytes("SOLO\n1\n2\n".encode("utf-8"), "x.csv")
    assert df is not None and list(df.columns) == ["SOLO"] and motor is not None


def test_ler_csv_de_bytes_coluna_excedente_vira_erro() -> None:
    # on_bad_lines="error" + ParserWarning promovido a erro: nenhuma coluna pode
    # ser descartada em silêncio nem virar índice.
    bruto = "A;B;C\n1;2;3;4\n".encode("utf-8")
    df, erro = robo._ler_csv_de_bytes(bruto, "quebrado.csv")
    assert df is None
    assert erro.startswith("quebrado.csv: falha ao interpretar CSV")


def test_ler_arquivo_csv_basico(tmp_path: Path) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    leitura = robo.ler_arquivo_detalhado(str(arquivo))
    assert leitura.erro is None
    assert leitura.motor == "csv utf-8-sig sep=';'"
    assert list(leitura.df.columns) == ["LOGIN", "BASE", "QTDE"]
    assert list(leitura.df["QTDE"]) == ["3", "5"]
    assert pd.isna(leitura.df["BASE"].iloc[0])


def test_ler_arquivo_csv_com_bom(tmp_path: Path) -> None:
    arquivo = _gravar_csv(
        tmp_path, "Atividades-SPO.csv", BASE_CSV, encoding="utf-8-sig"
    )
    leitura = robo.ler_arquivo_detalhado(str(arquivo))
    assert list(leitura.df.columns)[0] == "LOGIN"


def test_ler_arquivo_csv_separado_por_virgula(tmp_path: Path) -> None:
    arquivo = _gravar_csv(
        tmp_path, "Atividades-GRS.csv", "LOGIN,BASE\na,NET-GUARULHOS\n"
    )
    leitura = robo.ler_arquivo_detalhado(str(arquivo))
    assert leitura.motor == "csv utf-8-sig sep=','"
    assert list(leitura.df["BASE"]) == ["NET-GUARULHOS"]


def test_ler_arquivo_vazio_e_acima_do_limite(tmp_path: Path) -> None:
    vazio = tmp_path / "Atividades-SPO.csv"
    vazio.write_bytes(b"")
    leitura_vazia = robo.ler_arquivo_detalhado(str(vazio))
    assert leitura_vazia.df is None and "está vazio" in leitura_vazia.erro

    grande = tmp_path / "Atividades-GRS.csv"
    grande.write_bytes(b"LOGIN\n" + b"1\n" * 200)
    leitura = robo.ler_arquivo_detalhado(str(grande), tamanho_maximo=128)
    assert leitura.df is None and "acima do limite" in leitura.erro


def test_ler_arquivo_inexistente_e_extensao_invalida(tmp_path: Path) -> None:
    assert "não encontrado" in robo.ler_arquivo_detalhado(str(tmp_path / "x.csv")).erro
    assert "não encontrado" in robo.ler_arquivo_detalhado("").erro

    texto = tmp_path / "Atividades-SPO.txt"
    texto.write_text("LOGIN;BASE\na;b\n", encoding="utf-8")
    leitura = robo.ler_arquivo_detalhado(str(texto))
    assert leitura.df is None and "não é CSV/Excel" in leitura.erro


def test_ler_arquivo_colunas_esperadas_faltando(tmp_path: Path) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    leitura = robo.ler_arquivo_detalhado(
        str(arquivo), colunas_esperadas=["LOGIN", "MONITOR"]
    )
    assert leitura.df is None
    assert "colunas ausentes → MONITOR" in leitura.erro


def test_ler_arquivo_colunas_esperadas_case_insensitive(tmp_path: Path) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", "login;qtde\na;1\n")
    leitura = robo.ler_arquivo_detalhado(
        str(arquivo), colunas_esperadas=["LOGIN", "QTDE"]
    )
    assert leitura.erro is None
    assert list(leitura.df.columns) == ["LOGIN", "QTDE"]


def test_ler_arquivo_arquivo_bloqueado_propaga(tmp_path, monkeypatch) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)

    def _bloqueado(caminho: str, tamanho_maximo: int) -> bytes:
        raise robo.ArquivoBloqueadoError(f"'{Path(caminho).name}' está bloqueado.")

    monkeypatch.setattr(robo, "_ler_bytes_estavel", _bloqueado)
    with pytest.raises(robo.ArquivoBloqueadoError):
        robo.ler_arquivo_detalhado(str(arquivo))


# ── Leitura de Excel ────────────────────────────────────────────────


def test_ler_arquivo_xlsx(tmp_path: Path) -> None:
    arquivo = _gravar_xlsx(
        tmp_path,
        "Atividades-SPO.xlsx",
        [["LOGIN", "QTDE"], ["joao", 1.0], ["maria", 2.0]],
    )
    leitura = robo.ler_arquivo_detalhado(str(arquivo))
    assert leitura.erro is None
    assert leitura.motor == "openpyxl/temp.xlsx"
    assert list(leitura.df["QTDE"]) == ["1", "2"]


def test_ler_arquivo_xlsx_por_nome_de_aba(tmp_path: Path) -> None:
    arquivo = tmp_path / "Atividades-GRS.xlsx"
    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        pd.DataFrame({"A": ["1"]}).to_excel(writer, sheet_name="Resumo", index=False)
        pd.DataFrame({"LOGIN": ["joao"]}).to_excel(
            writer, sheet_name="Atividades", index=False
        )
    leitura = robo.ler_arquivo_detalhado(str(arquivo), sheet_name="Atividades")
    assert leitura.erro is None and list(leitura.df.columns) == ["LOGIN"]


def test_ler_arquivo_xlsx_aba_inexistente(tmp_path: Path) -> None:
    arquivo = _gravar_xlsx(tmp_path, "Atividades-SPO.xlsx", [["A"], ["1"]])
    leitura = robo.ler_arquivo_detalhado(str(arquivo), sheet_name="NaoExiste")
    assert leitura.df is None and "Aba 'NaoExiste' não encontrada" in leitura.erro


def test_ler_arquivo_xlsx_com_titulo_antes_do_cabecalho(tmp_path: Path) -> None:
    arquivo = tmp_path / "Atividades-SPO.xlsx"
    dados = [["Relatório TOTALE — exportado em 05/03/2024", None, None]]
    dados.append(["LOGIN", "BASE", "QTDE"])
    dados.append(["joao", None, 3])
    with pd.ExcelWriter(arquivo, engine="openpyxl") as writer:
        pd.DataFrame(dados).to_excel(
            writer, sheet_name="Sheet1", index=False, header=False
        )

    leitura = robo.ler_arquivo_detalhado(
        str(arquivo), colunas_esperadas=["LOGIN", "QTDE"]
    )
    assert leitura.erro is None
    assert leitura.motor.endswith("header=1")
    assert list(leitura.df.columns) == ["LOGIN", "BASE", "QTDE"]
    assert list(leitura.df["LOGIN"]) == ["joao"]


def test_ler_arquivo_xlsx_sem_linhas_de_dados(tmp_path: Path) -> None:
    arquivo = _gravar_xlsx(tmp_path, "Atividades-SPO.xlsx", [["LOGIN", "QTDE"]])
    leitura = robo.ler_arquivo_detalhado(str(arquivo))
    assert leitura.df is None
    assert leitura.motor is None
    assert "planilha vazia" in leitura.erro


def test_ler_arquivo_xlsx_download_incompleto(tmp_path: Path) -> None:
    arquivo = tmp_path / "Atividades-SPO.xlsx"
    arquivo.write_bytes(b"PK\x03\x04" + b"\x00" * 100)
    leitura = robo.ler_arquivo_detalhado(str(arquivo))
    assert leitura.df is None
    assert "download incompleto" in leitura.erro


def test_ler_arquivo_xlsx_zip_corrompido(tmp_path: Path) -> None:
    arquivo = tmp_path / "Atividades-SPO.xlsx"
    arquivo.write_bytes(b"X" * (robo._TAMANHO_MINIMO_XLSX + 10))
    leitura = robo.ler_arquivo_detalhado(str(arquivo))
    assert leitura.df is None and "não é um Excel ZIP válido" in leitura.erro


def test_validar_xlsx_membro_corrompido(tmp_path: Path) -> None:
    import zipfile

    arquivo = tmp_path / "corrompido.xlsx"
    conteudo = "<workbook>" + "dados-operacionais-totale;" * 400 + "</workbook>"
    with zipfile.ZipFile(arquivo, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("xl/workbook.xml", conteudo)
    assert arquivo.stat().st_size > robo._TAMANHO_MINIMO_XLSX

    # Um byte trocado no corpo do membro quebra o CRC sem invalidar o ZIP.
    bruto = bytearray(arquivo.read_bytes())
    bruto[2_000] ^= 0xFF
    with pytest.raises(ValueError, match="corrompido no membro interno"):
        robo._validar_xlsx(bytes(bruto), "corrompido.xlsx")


def test_ler_arquivo_xls_invalido_tenta_calamine_e_xlrd(tmp_path: Path) -> None:
    # A validação de tamanho mínimo é exclusiva de .xlsx/.xlsm; um .xls truncado
    # chega aos motores e o erro agregado cita as duas tentativas.
    arquivo = tmp_path / "Atividades-SPO.xls"
    arquivo.write_bytes(b"\xd0\xcf\x11\xe0" + b"\x00" * 500)
    leitura = robo.ler_arquivo_detalhado(str(arquivo))
    assert leitura.df is None and leitura.motor is None
    assert "calamine/.xls" in leitura.erro and "xlrd/.xls" in leitura.erro


def test_ler_excel_robusto_motor_nativo_como_ultimo_recurso(
    tmp_path: Path, monkeypatch
) -> None:
    arquivo = _gravar_xlsx(
        tmp_path, "Atividades-SPO.xlsx", [["LOGIN", "QTDE"], ["joao", 1]]
    )

    def _sem_engine(*_args, **_kwargs):
        raise ImportError("Missing optional dependency 'openpyxl'")

    monkeypatch.setattr(robo.pd, "read_excel", _sem_engine)
    df, motor = robo._ler_excel_robusto(str(arquivo))
    assert motor == "openpyxl nativo"
    assert list(df.columns) == ["LOGIN", "QTDE"]


def test_ler_excel_robusto_todos_os_motores_falham(tmp_path, monkeypatch) -> None:
    arquivo = _gravar_xlsx(tmp_path, "Atividades-SPO.xlsx", [["A"], ["1"]])
    monkeypatch.setattr(robo.pd, "read_excel", lambda *a, **k: pd.DataFrame())
    monkeypatch.setattr(
        robo, "_ler_excel_via_openpyxl_nativo", lambda *a, **k: pd.DataFrame()
    )
    with pytest.raises(RuntimeError, match="planilha vazia"):
        robo._ler_excel_robusto(str(arquivo))


def test_ler_excel_robusto_dica_de_instalacao(tmp_path, monkeypatch) -> None:
    arquivo = _gravar_xlsx(tmp_path, "Atividades-SPO.xlsx", [["A"], ["1"]])

    def _ausente(*_args, **_kwargs):
        raise ImportError("Missing optional dependency 'openpyxl'")

    monkeypatch.setattr(robo.pd, "read_excel", _ausente)
    monkeypatch.setattr(robo, "_ler_excel_via_openpyxl_nativo", _ausente)
    with pytest.raises(RuntimeError, match="pip install openpyxl"):
        robo._ler_excel_robusto(str(arquivo))


# ── Estabilidade de leitura ─────────────────────────────────────────


def test_ler_bytes_estavel_detecta_mudanca_durante_leitura(tmp_path: Path) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    original = os.stat
    chamadas = {"n": 0}

    def _stat_segundo_muda(caminho, *args, **kwargs):
        resultado = original(caminho, *args, **kwargs)
        if str(caminho) != str(arquivo):
            return resultado
        chamadas["n"] += 1
        if chamadas["n"] == 1:
            return resultado
        campos = list(resultado)
        campos[9] = resultado.st_mtime_ns + 10**9  # índice de st_mtime_ns
        return os.stat_result(campos)

    # O patch é restrito ao alvo e desfeito aqui mesmo: trocar ``os.stat`` em
    # definitivo quebraria o coletor do pytest durante o teardown.
    robo.os.stat = _stat_segundo_muda
    try:
        with pytest.raises(robo.ArquivoBloqueadoError, match="mudou durante a leitura"):
            robo._ler_bytes_estavel(str(arquivo), robo._TAMANHO_MAXIMO_PADRAO)
    finally:
        robo.os.stat = original
    assert chamadas["n"] == 2


def test_ler_bytes_estavel_permission_error_vira_bloqueio(
    tmp_path: Path, monkeypatch
) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    original = robo.open if hasattr(robo, "open") else open

    def _abrir_negado(*args, **kwargs):
        if str(args[0]) == str(arquivo):
            raise PermissionError("acesso negado pelo OneDrive")
        return original(*args, **kwargs)

    monkeypatch.setattr("builtins.open", _abrir_negado)
    with pytest.raises(robo.ArquivoBloqueadoError, match="bloqueado"):
        robo._ler_bytes_estavel(str(arquivo), robo._TAMANHO_MAXIMO_PADRAO)


def test_ler_bytes_estavel_arquivo_sumiu(tmp_path: Path) -> None:
    with pytest.raises(robo.ArquivoBloqueadoError, match="não pôde ser medido"):
        robo._ler_bytes_estavel(str(tmp_path / "nada.csv"), robo._TAMANHO_MAXIMO_PADRAO)


# ── processar_candidatos ────────────────────────────────────────────


def test_processar_candidatos_sem_candidatos() -> None:
    resultado = robo.processar_candidatos([])
    assert resultado.df is None
    assert resultado.arquivos == () and resultado.erros == ()
    assert resultado.bloqueio is None and resultado.duplicatas_removidas == 0


def test_processar_candidatos_aplica_base_e_publica_motor(tmp_path: Path) -> None:
    recente = _gravar_csv(
        tmp_path, "Atividades-SPO.csv", BASE_CSV, mtime_ns=1_800_000_000_000_000_000
    )
    _gravar_csv(
        tmp_path, "Atividades-GRS.csv", BASE_CSV, mtime_ns=1_600_000_000_000_000_000
    )

    resultado = robo.processar_candidatos(
        robo._listar_candidatos_com_stat(str(tmp_path))
    )
    assert resultado.bases == ("NET-LESTE",)
    assert resultado.arquivos == (str(recente),)
    assert resultado.erros == () and resultado.bloqueio is None
    assert resultado.motores == ("Atividades-SPO.csv: csv utf-8-sig sep=';'",)
    assert list(resultado.df["BASE"]) == ["NET-LESTE", "NET-LESTE"]


def test_processar_candidatos_registra_erro_de_leitura(tmp_path: Path) -> None:
    arquivo = tmp_path / "Atividades-SPO.txt"
    arquivo.write_text("LOGIN;BASE\na;b\n", encoding="utf-8")
    resultado = robo.processar_candidatos([(str(arquivo), 1, 10)])
    assert resultado.df is None
    assert resultado.arquivos == ()
    assert len(resultado.erros) == 1


def test_processar_candidatos_reporta_bloqueio(tmp_path: Path, monkeypatch) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)

    def _bloqueado(*_args, **_kwargs):
        raise robo.ArquivoBloqueadoError("aguardando o próximo ciclo")

    monkeypatch.setattr(robo, "ler_arquivo_detalhado", _bloqueado)
    resultado = robo.processar_candidatos([(str(arquivo), 1, 10)])
    assert resultado.df is None
    assert resultado.bloqueio == "aguardando o próximo ciclo"
    assert resultado.erros == ()


# ── Fachada TotaleRoboEngine ────────────────────────────────────────


def test_engine_constantes_expõem_mapas_do_modulo() -> None:
    assert robo.TotaleRoboEngine.PADROES == robo.PADROES_TOTALE
    assert robo.TotaleRoboEngine.MAPA_BASES == robo.MAPA_BASES_ARQUIVO
    assert robo.TotaleRoboEngine.detectar_base("Atividades-SPO.csv") == "NET-LESTE"


def test_engine_listar_validos_e_buscar_mais_recente(tmp_path: Path) -> None:
    recente = _gravar_csv(
        tmp_path, "Atividades-SPO.csv", BASE_CSV, mtime_ns=1_800_000_000_000_000_000
    )
    _gravar_csv(
        tmp_path, "Atividades-GRS.csv", BASE_CSV, mtime_ns=1_600_000_000_000_000_000
    )

    validos = robo.TotaleRoboEngine.listar_validos(tmp_path)
    assert validos == [recente, tmp_path / "Atividades-GRS.csv"]
    assert robo.TotaleRoboEngine.buscar_mais_recente(tmp_path) == recente
    assert robo.TotaleRoboEngine.arquivos_por_base(tmp_path) == {"NET-LESTE": recente}
    assert robo.TotaleRoboEngine.buscar_mais_recente(tmp_path / "nada") is None
    assert robo.TotaleRoboEngine.arquivos_por_base(tmp_path / "nada") == {}


def test_engine_ler_dados_com_e_sem_base(tmp_path: Path) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", "LOGIN;QTDE\njoao;3\n")
    sem_base = robo.TotaleRoboEngine.ler_dados(arquivo)
    assert "BASE" not in sem_base.columns
    assert robo.TotaleRoboEngine.ultimo_erro() is None
    assert robo.TotaleRoboEngine.ultimo_motor() == "csv utf-8-sig sep=';'"

    com_base = robo.TotaleRoboEngine.ler_dados(arquivo, aplicar_base=True)
    assert list(com_base["BASE"]) == ["NET-LESTE"]


def test_engine_ler_mais_recente_e_registro_de_erro(tmp_path: Path) -> None:
    _gravar_csv(tmp_path, "Atividades-GRS.csv", "LOGIN;BASE;QTDE\njoao;;3\nmaria;;5\n")
    df = robo.TotaleRoboEngine.ler_mais_recente(tmp_path, aplicar_base=True)
    assert df is not None and list(df["BASE"]) == ["NET-GUARULHOS"] * 2

    assert robo.TotaleRoboEngine.ler_mais_recente(tmp_path / "vazia") is None
    assert "Nenhum arquivo TOTALE válido" in robo.TotaleRoboEngine.ultimo_erro()


def test_engine_ler_dados_arquivo_bloqueado_nao_propaga(tmp_path, monkeypatch) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)

    def _bloqueado(*_args, **_kwargs):
        raise robo.ArquivoBloqueadoError("arquivo em sincronização")

    monkeypatch.setattr(robo, "ler_arquivo_detalhado", _bloqueado)
    assert robo.TotaleRoboEngine.ler_dados(arquivo) is None
    assert robo.TotaleRoboEngine.ultimo_erro() == "arquivo em sincronização"


def test_engine_assinatura_e_estabilidade(tmp_path: Path, monkeypatch) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    stat = arquivo.stat()
    assert robo.TotaleRoboEngine.assinatura(arquivo) == (
        stat.st_size,
        stat.st_mtime_ns,
    )
    assert robo.TotaleRoboEngine.assinatura(tmp_path / "nada.csv") is None

    dormidos: list[float] = []
    monkeypatch.setattr(robo.time, "sleep", dormidos.append)
    assert robo.TotaleRoboEngine.verificar_estabilidade(arquivo, ciclos=2, intervalo=0)
    assert dormidos == [0, 0]
    assert not robo.TotaleRoboEngine.verificar_estabilidade(tmp_path / "nada.csv")

    vazia = tmp_path / "Atividades-Vazia.csv"
    vazia.write_bytes(b"")
    assert not robo.TotaleRoboEngine.verificar_estabilidade(vazia)


def test_engine_estabilidade_detecta_arquivo_em_gravacao(
    tmp_path: Path, monkeypatch
) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    dormidos: list[float] = []

    def _sleep(intervalo: float) -> None:
        dormidos.append(intervalo)
        if len(dormidos) == 1:
            # Simula o OneDrive/Excel escrevendo entre dois ciclos.
            arquivo.write_bytes((BASE_CSV + "pedro;;7\n").encode("utf-8"))

    monkeypatch.setattr(robo.time, "sleep", _sleep)
    assert not robo.TotaleRoboEngine.verificar_estabilidade(
        arquivo, ciclos=2, intervalo=0.01
    )


# ── ler_arquivo_totale (fachada com notificação) ────────────────────


def test_ler_arquivo_totale_sem_notificacao(tmp_path: Path) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    df = robo.ler_arquivo_totale(str(arquivo), notificar=False)
    assert df is not None and len(df) == 2
    assert robo.ler_arquivo_totale(str(tmp_path / "nada.csv"), notificar=False) is None


# ── executar_ciclo_headless ─────────────────────────────────────────


def test_ciclo_headless_publica_csv(tmp_path: Path) -> None:
    sem_base = "LOGIN;QTDE\njoao;3\nmaria;5\n"
    _gravar_csv(
        tmp_path, "Atividades-ABCDM.csv", sem_base, mtime_ns=1_800_000_000_000_000_000
    )
    _gravar_csv(
        tmp_path, "Atividades-SPO.csv", sem_base, mtime_ns=1_600_000_000_000_000_000
    )
    destino = tmp_path / "saida" / "robo.csv"

    resultado = robo.executar_ciclo_headless(str(tmp_path), destino_csv=str(destino))
    assert resultado.bases == ("NET-ABCDM",)
    assert destino.is_file()
    gravado = pd.read_csv(destino, sep=";", encoding="utf-8-sig", dtype=str)
    assert list(gravado["BASE"]) == ["NET-ABCDM", "NET-ABCDM"]


def test_ciclo_headless_recusa_sobrescrever_a_origem(tmp_path: Path) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    with pytest.raises(ValueError, match="não pode sobrescrever"):
        robo.executar_ciclo_headless(str(tmp_path), destino_csv=str(arquivo))


def test_ciclo_headless_pasta_vazia(tmp_path: Path) -> None:
    resultado = robo.executar_ciclo_headless(
        str(tmp_path), destino_csv=str(tmp_path / "o.csv")
    )
    assert resultado.df is None and not (tmp_path / "o.csv").exists()


def test_ciclo_headless_com_colunas_esperadas(tmp_path: Path) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    resultado = robo.executar_ciclo_headless(
        str(tmp_path), colunas_esperadas=["LOGIN", "BASE", "QTDE"]
    )
    assert resultado.df is not None and resultado.erros == ()

    resultado = robo.executar_ciclo_headless(
        str(tmp_path), colunas_esperadas=["LOGIN", "MONITOR"]
    )
    assert resultado.df is None and "MONITOR" in resultado.erros[0]


def test_cli_do_modulo(tmp_path: Path) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    destino = tmp_path / "cache" / "robo.csv"
    processo = subprocess.run(
        [sys.executable, "components/robo_local.py", str(tmp_path), str(destino)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert processo.returncode == 0, processo.stderr
    assert "2 linhas" in processo.stdout and "NET-LESTE" in processo.stdout
    assert destino.is_file()


def test_cli_do_modulo_sem_arquivos(tmp_path: Path) -> None:
    processo = subprocess.run(
        [sys.executable, "components/robo_local.py", str(tmp_path)],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert processo.returncode == 1
    assert "Nenhum arquivo processado" in processo.stdout


def test_cli_do_modulo_pasta_inexistente(tmp_path: Path) -> None:
    processo = subprocess.run(
        [sys.executable, "components/robo_local.py", str(tmp_path / "nao-existe")],
        capture_output=True,
        text=True,
        cwd=Path(__file__).resolve().parents[1],
    )
    assert processo.returncode == 1


# ── Dublê de Streamlit para o ciclo de sincronismo ──────────────────


class _ColunaStub:
    def __enter__(self) -> _ColunaStub:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


class StreamlitStub:
    """Superfície mínima do ``streamlit`` usada por ``robo_local``.

    Por padrão **não** expõe ``fragment``: assim o módulo deixa o ciclo sem o
    invólucro do ``st.fragment``, e os testes alcançam a lógica real trocando
    apenas ``robo.st``. O comportamento com o fragment é coberto por
    :func:`test_ciclo_e_registrado_como_fragment_de_5s`.
    """

    def __init__(self, com_fragment: bool = False) -> None:
        self.session_state: dict[str, object] = {}
        self.toasts: list[tuple[str, str]] = []
        self.mensagens: list[tuple[str, str]] = []
        self.botoes_clicados: set[str] = set()
        self.reruns = 0
        self.reruns_com_scope = 0
        self.com_fragment = com_fragment
        self.uploads: list[tuple[str, dict[str, object]]] = []

    # ── exibição
    def markdown(self, corpo: str, **_kwargs: object) -> None:
        self.mensagens.append(("markdown", corpo))

    def caption(self, corpo: str, **_kwargs: object) -> None:
        self.mensagens.append(("caption", corpo))

    def info(self, corpo: str, **_kwargs: object) -> None:
        self.mensagens.append(("info", corpo))

    def success(self, corpo: str, **_kwargs: object) -> None:
        self.mensagens.append(("success", corpo))

    def warning(self, corpo: str, **_kwargs: object) -> None:
        self.mensagens.append(("warning", corpo))

    def error(self, corpo: str, **_kwargs: object) -> None:
        self.mensagens.append(("error", corpo))

    # ── widgets
    def file_uploader(self, rotulo: str, **kwargs: object):
        self.uploads.append((rotulo, kwargs))
        return None

    def toggle(self, rotulo: str, value: bool = False, key: str = "", **_kw) -> bool:
        self.mensagens.append(("toggle", rotulo))
        return bool(self.session_state.get(key, value))

    def checkbox(self, rotulo: str, value: bool = False, key: str = "", **_kw) -> bool:
        self.mensagens.append(("checkbox", rotulo))
        return bool(self.session_state.get(key, value))

    def text_input(self, rotulo: str, value: str = "", key: str = "", **_kw) -> str:
        self.mensagens.append(("text_input", rotulo))
        return str(self.session_state.get(key, value))

    def button(self, rotulo: str, key: str = "", **_kw) -> bool:
        return key in self.botoes_clicados

    def expander(self, rotulo: str, **_kw) -> _ColunaStub:
        self.mensagens.append(("expander", rotulo))
        return _ColunaStub()

    def columns(self, n: int) -> list[_ColunaStub]:
        return [_ColunaStub() for _ in range(n)]

    # ── runtime
    def toast(self, mensagem: str, icon: str = "✅") -> None:
        self.toasts.append((mensagem, icon))

    def rerun(self, *args: object, **kwargs: object) -> None:
        self.reruns += 1
        if kwargs:
            self.reruns_com_scope += 1

    def fragment(self, *_args: object, **_kwargs: object):
        def decorador(fn):
            return fn

        return decorador


@pytest.fixture
def st_stub(monkeypatch):
    stub = StreamlitStub()
    monkeypatch.setattr(robo, "st", stub)
    return stub


def _ciclo(pasta: Path, stub: StreamlitStub, **kwargs) -> None:
    """Executa o ciclo de sincronismo sobre a pasta usando o dublê de Streamlit.

    O ``streamlit`` real decora o ciclo com ``st.fragment`` quando importado
    dentro do app; o invólucro devolve ``None`` sem ``ScriptRunContext`` (modo
    bare) e mantém um ``__globals__`` próprio, inacessível ao monkeypatch. Por
    isso os testes chamam ``__wrapped__`` quando existe — a função original, que
    lê o ``st`` do módulo.
    """
    assert robo.st is stub, "o dublê precisa estar instalado no módulo"
    alvo = getattr(robo._executar_verificacao_robo, "__wrapped__", None)
    if alvo is None:
        alvo = robo._executar_verificacao_robo
    alvo(pasta_monitorada=str(pasta), **kwargs)


def test_ciclo_e_registrado_como_fragment_de_5s() -> None:
    """Com o Streamlit real do app, o ciclo vira fragment executado a cada 5s."""
    import streamlit as st_real

    assert hasattr(st_real, "fragment")
    assert getattr(robo._executar_verificacao_robo, "__wrapped__", None) is not None
    assert robo._executar_verificacao_robo.__module__ == "components.robo_local"


def test_renderizar_no_runtime_streamlit_publica_a_base(tmp_path: Path) -> None:
    """Integração de ponta: ``AppTest`` executa a página com o runtime real.

    Cobre o caminho que o dublê não alcança — o ``st.fragment`` decorado, que só
    roda com ``ScriptRunContext`` — e confirma que a Central publica ``df_memoria``
    após o ciclo de estabilidade.
    """
    from streamlit.testing.v1 import AppTest

    raiz = Path(__file__).resolve().parents[1]
    pasta = tmp_path / "downloads"
    pasta.mkdir()
    _gravar_csv(pasta, "Atividades-SPO.csv", "LOGIN;QTDE\njoao;3\nmaria;5\n")

    script = tmp_path / "app_robo.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {str(raiz)!r})\n"
        "import streamlit as st\n"
        "from components.robo_local import renderizar_robo_local\n"
        'st.set_page_config(page_title="Robô")\n'
        f"renderizar_robo_local(pasta_padrao={str(pasta)!r}, ciclos_estabilidade=1)\n",
        encoding="utf-8",
    )

    app = AppTest.from_file(str(script), default_timeout=60)
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]

    estado = app.session_state
    publicado = estado["df_memoria"]
    assert len(publicado) == 2
    assert list(publicado["BASE"]) == ["NET-LESTE", "NET-LESTE"]
    assert estado["origem_dados"] == "Robô Local (1 arquivo(s) · NET-LESTE)"
    assert estado["robo_base_detectada"] == "NET-LESTE"
    assert estado["robo_pasta_alvo"] == str(pasta)
    assert any("✅ NET-LESTE — Atividades-SPO.csv" in c.value for c in app.caption)

    # Segundo ciclo com o mesmo arquivo: nada é reprocessado e o painel confirma.
    antes = estado["robo_processado_sig"]
    app.run()
    assert not app.exception, [str(e.value) for e in app.exception]
    assert app.session_state["robo_processado_sig"] == antes
    assert any("Sincronizado às" in s.value for s in app.success)


# ── Ciclo de sincronismo (Streamlit) ────────────────────────────────


def test_ciclo_exige_estabilidade_antes_de_processar(tmp_path, st_stub) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)

    _ciclo(tmp_path, st_stub, ciclos_estabilidade=2)
    assert "df_memoria" not in st_stub.session_state
    assert st_stub.session_state["robo_candidato_stable"] == 1
    assert st_stub.toasts == []

    _ciclo(tmp_path, st_stub, ciclos_estabilidade=2)
    estado = st_stub.session_state
    assert len(estado["df_memoria"]) == 2
    assert estado["robo_candidato_stable"] == 2
    assert estado["robo_bases_carregadas"] == ["NET-LESTE"]
    assert estado["robo_base_detectada"] == "NET-LESTE"
    assert estado["robo_ultimo_processado_path"] == str(tmp_path / "Atividades-SPO.csv")
    assert estado["origem_dados"] == "Robô Local (1 arquivo(s) · NET-LESTE)"
    assert estado["robo_arquivos_processados"] == {
        str(tmp_path / "Atividades-SPO.csv"): estado["robo_ultimo_processado_mtime"]
    }
    assert isinstance(estado["robo_hora_sucesso"], datetime)
    assert estado["robo_processando"] is False
    assert "robo_erro" not in estado
    assert st_stub.toasts == [("Bases: NET-LESTE — pipeline concluído!", "🚀")]
    assert st_stub.reruns == 1


def test_ciclo_nao_reprocessa_a_mesma_assinatura(tmp_path, st_stub) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)
    assert len(st_stub.toasts) == 1

    df_anterior = st_stub.session_state["df_memoria"]
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)
    assert len(st_stub.toasts) == 1
    assert st_stub.session_state["df_memoria"] is df_anterior
    assert st_stub.reruns == 1


def test_ciclo_reprocessa_quando_o_arquivo_muda(tmp_path, st_stub) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)

    arquivo.write_bytes((BASE_CSV + "pedro;;7\n").encode("utf-8"))
    _tocar(arquivo, 1_900_000_000_000_000_000)
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)

    assert len(st_stub.session_state["df_memoria"]) == 3
    assert st_stub.reruns == 2


def test_ciclo_pausado_quando_robo_desativado(tmp_path, st_stub) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    st_stub.session_state["robo_ativo"] = False
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)
    assert "df_memoria" not in st_stub.session_state
    assert st_stub.session_state.get("robo_candidato_sig") is None


def test_ciclo_sem_candidatos_nao_publica_nada(tmp_path, st_stub) -> None:
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)
    assert st_stub.session_state == {}
    assert st_stub.toasts == []


def test_ciclo_publica_raw_e_processado_com_etl(tmp_path, st_stub) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)

    def etl(df: pd.DataFrame, planilha: pd.DataFrame) -> pd.DataFrame:
        df.attrs["etl"] = True
        df["MONITOR"] = "ana"
        return df

    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1, etl_fn=etl, gsheets_fn=None)
    estado = st_stub.session_state
    assert "MONITOR" in estado["df_memoria"].columns
    assert "MONITOR" not in estado["df_memoria_raw"].columns
    assert estado["df_memoria"].attrs.get("etl") is True
    assert not estado["df_memoria_raw"].attrs.get("etl")


def test_ciclo_etl_retornando_none_mantem_base_bruta(tmp_path, st_stub) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1, etl_fn=lambda df, pl: None)
    estado = st_stub.session_state
    assert estado["df_memoria"] is estado["df_memoria_raw"]


def test_ciclo_etl_invalido_gera_erro_e_nao_publica(tmp_path, st_stub) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    _ciclo(
        tmp_path,
        st_stub,
        ciclos_estabilidade=1,
        etl_fn=lambda df, pl: "não é DataFrame",
    )

    estado = st_stub.session_state
    assert "df_memoria" not in estado
    assert "robo_processado_sig" not in estado
    assert estado["robo_erro"].startswith("TypeError")
    assert estado["robo_processando"] is False
    assert st_stub.reruns == 0
    assert any(icon == "❌" for _, icon in st_stub.toasts)


def test_ciclo_falha_do_etl_nao_substitui_base_anterior(tmp_path, st_stub) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)
    df_bom = st_stub.session_state["df_memoria"]

    arquivo = tmp_path / "Atividades-GRS.csv"
    arquivo.write_bytes(BASE_CSV.encode("utf-8"))
    _tocar(arquivo, 1_900_000_000_000_000_000)

    def etl_quebra(_df, _pl):
        raise RuntimeError("planilha indisponível")

    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1, etl_fn=etl_quebra)
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1, etl_fn=etl_quebra)

    assert st_stub.session_state["df_memoria"] is df_bom
    assert "RuntimeError: planilha indisponível" in st_stub.session_state["robo_erro"]
    assert (
        "robo_processado_sig" in st_stub.session_state
    )  # assinatura antiga preservada


def test_ciclo_gsheets_por_dataframe_e_por_callable(tmp_path, st_stub) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    planilha = pd.DataFrame({"LOGIN": ["joao"], "MONITOR": ["ana"]})
    vistas: list[pd.DataFrame] = []

    def etl(df: pd.DataFrame, ativos: pd.DataFrame) -> pd.DataFrame:
        vistas.append(ativos)
        return df

    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1, etl_fn=etl, gsheets_fn=planilha)
    assert vistas[-1] is planilha

    st_stub.session_state.pop("robo_processado_sig")
    _ciclo(
        tmp_path,
        st_stub,
        ciclos_estabilidade=1,
        etl_fn=etl,
        gsheets_fn=lambda: planilha,
    )
    assert vistas[-1] is planilha

    assert robo._obter_gsheets(None).empty


def test_ciclo_erro_de_leitura_vira_robo_erro(tmp_path, st_stub) -> None:
    # Coluna excedente é rejeitada (on_bad_lines="error"): nada é publicado.
    _gravar_csv(tmp_path, "Atividades-SPO.csv", "LOGIN;BASE;QTDE\n1;2;3;4\n")
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)
    assert "df_memoria" not in st_stub.session_state
    assert "falha ao interpretar CSV" in st_stub.session_state["robo_erro"]


def test_ciclo_bloqueio_aguarda_proximo_ciclo(tmp_path, st_stub, monkeypatch) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)

    def _bloqueado(*_args, **_kwargs):
        raise robo.ArquivoBloqueadoError(
            "'Atividades-SPO.csv' está bloqueado (OneDrive)."
        )

    monkeypatch.setattr(robo, "ler_arquivo_detalhado", _bloqueado)
    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)

    estado = st_stub.session_state
    assert estado["_robo_aguardando_lock"].startswith("'Atividades-SPO.csv'")
    assert estado["robo_candidato_stable"] == 0
    assert "robo_erro" not in estado
    assert "df_memoria" not in estado


def test_ciclo_lock_ativo_evita_reentrada(tmp_path, st_stub) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    st_stub.session_state["robo_processando"] = True
    st_stub.session_state["robo_processando_desde"] = datetime.now()

    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)
    assert "df_memoria" not in st_stub.session_state
    assert st_stub.session_state["robo_processando"] is True


def test_ciclo_lock_expirado_e_destravado(tmp_path, st_stub) -> None:
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    st_stub.session_state["robo_processando"] = True
    st_stub.session_state["robo_processando_desde"] = datetime.now() - timedelta(
        seconds=robo._LOCK_STALE_SEGUNDOS + 10
    )

    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)
    assert "df_memoria" in st_stub.session_state
    assert st_stub.session_state["robo_processando"] is False


def test_lock_ativo_sem_horario_de_inicio(tmp_path, st_stub) -> None:
    st_stub.session_state["robo_processando"] = True
    st_stub.session_state["robo_processando_desde"] = "ontem"
    assert robo._lock_ativo() is False
    assert st_stub.session_state["robo_processando"] is False


def test_ciclo_arquivo_mudou_durante_o_etl_nao_publica(tmp_path, st_stub) -> None:
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)

    def etl_troca_arquivo(df: pd.DataFrame, _pl) -> pd.DataFrame:
        _tocar(arquivo, 1_950_000_000_000_000_000)
        return df

    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1, etl_fn=etl_troca_arquivo)
    assert "df_memoria" not in st_stub.session_state
    assert st_stub.session_state["robo_candidato_stable"] == 0
    assert ("Arquivos mudaram durante o ETL. Aguardando...", "⚠️") in st_stub.toasts


def test_ciclo_recursivo(tmp_path, st_stub) -> None:
    sub = tmp_path / "sub"
    sub.mkdir()
    _gravar_csv(sub, "Atividades-GRS.csv", BASE_CSV)
    st_stub.session_state["robo_recursivo"] = True

    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1)
    assert "df_memoria" not in st_stub.session_state

    _ciclo(tmp_path, st_stub, ciclos_estabilidade=1, recursivo=True)
    assert st_stub.session_state["robo_base_detectada"] == "NET-GUARULHOS"


# ── Helpers de estado e toast ───────────────────────────────────────


def test_helpers_de_estado_sem_streamlit(monkeypatch) -> None:
    monkeypatch.setattr(robo, "st", None)
    assert robo._estado_bool("robo_ativo", True) is True
    assert robo._estado_str("x", "padrao") == "padrao"
    assert robo._lock_ativo() is False
    robo._toast_dedup("nada")
    robo._rerun_aplicacao()
    with pytest.raises(RuntimeError, match="Streamlit não está instalado"):
        robo._exigir_streamlit()


def test_helpers_de_estado_com_streamlit(st_stub) -> None:
    st_stub.session_state["robo_ativo"] = False
    st_stub.session_state["vazio"] = ""
    st_stub.session_state["texto"] = "  valor  "
    assert robo._estado_bool("robo_ativo", True) is False
    assert robo._estado_bool("ausente", True) is True
    assert robo._estado_str("vazio", "padrao") == "padrao"
    assert robo._estado_str("ausente", "padrao") == "padrao"
    assert robo._estado_str("texto", "padrao") == "  valor  "
    assert robo._modo_atual() == "ultimo"


def test_toast_dedup(st_stub) -> None:
    robo._toast_dedup("mensagem", icon="✅")
    robo._toast_dedup("mensagem", icon="✅")
    robo._toast_dedup("mensagem", icon="⚠️")
    assert st_stub.toasts == [("mensagem", "✅"), ("mensagem", "⚠️")]


def test_rerun_usa_scope_quando_suportado(st_stub) -> None:
    robo._rerun_aplicacao()
    assert (st_stub.reruns, st_stub.reruns_com_scope) == (1, 1)


def test_rerun_sem_scope_faz_fallback(st_stub) -> None:
    def rerun_antigo() -> None:
        st_stub.reruns += 1

    st_stub.rerun = rerun_antigo
    robo._rerun_aplicacao()
    assert st_stub.reruns == 1


# ── renderizar_robo_local ───────────────────────────────────────────


def test_interface_nuvem_exibe_titulo_e_upload(st_stub) -> None:
    robo._renderizar_interface_nuvem(None, None, None, 0)

    texto = " ".join(mensagem for _, mensagem in st_stub.mensagens)
    assert "Selecione a exportação CSV ou Excel, para rodar a Quebra e a Volumetria" in texto
    assert "Envio de Arquivo (Modo Nuvem)" not in texto
    assert st_stub.uploads == [
        (
            "Selecione a exportação CSV ou Excel",
            {
                "type": ["csv", "xlsx", "xlsm", "xls"],
                "key": "upload_nuvem",
                "label_visibility": "collapsed",
            },
        )
    ]


def test_renderizar_exige_streamlit(monkeypatch) -> None:
    monkeypatch.setattr(robo, "st", None)
    with pytest.raises(RuntimeError, match="Streamlit não está instalado"):
        robo.renderizar_robo_local()


def _ciclo_noop(monkeypatch) -> None:
    """Anula o ciclo: estes testes verificam apenas a renderização."""
    monkeypatch.setattr(robo, "_executar_verificacao_robo", lambda **_kw: None)


def test_renderizar_inicializa_estado_e_lista_bases(
    tmp_path, st_stub, monkeypatch
) -> None:
    _ciclo_noop(monkeypatch)
    _gravar_csv(
        tmp_path, "Atividades-SPO.csv", BASE_CSV, mtime_ns=1_800_000_000_000_000_000
    )

    robo.renderizar_robo_local(pasta_padrao=str(tmp_path))

    estado = st_stub.session_state
    assert estado["robo_ativo"] is True
    assert estado["robo_modo_leitura"] == "ultimo"
    assert estado["robo_recursivo"] is False
    assert estado["robo_pasta_alvo"] == str(tmp_path)

    corpo = " | ".join(texto for _, texto in st_stub.mensagens)
    assert "Robô de Sincronismo" in corpo
    assert "Bases Monitoradas" in corpo
    assert "📥 NET-LESTE — Atividades-SPO.csv" in corpo
    assert "⬜ NET-GUARULHOS" in corpo
    assert "⬜ NET-ABCDM" in corpo
    assert "1 na pasta, 1 na fila" in corpo
    assert "Estável 0/2" in corpo  # o ciclo está anulado; nada foi contabilizado
    assert ("toggle", "⚡ Auto-Sincronizar") in st_stub.mensagens


def test_renderizar_pasta_vazia_mostra_monitorando(
    tmp_path, st_stub, monkeypatch
) -> None:
    _ciclo_noop(monkeypatch)
    robo.renderizar_robo_local(pasta_padrao=str(tmp_path))
    assert any(
        f"🟢 Monitorando: `{tmp_path.name}`" == texto
        for tipo, texto in st_stub.mensagens
        if tipo == "info"
    )


def test_renderizar_pasta_inexistente_mostra_erro(
    tmp_path, st_stub, monkeypatch
) -> None:
    _ciclo_noop(monkeypatch)
    robo.renderizar_robo_local(pasta_padrao=str(tmp_path / "nao-existe"))
    assert any("❌ Pasta não existe" in texto for _, texto in st_stub.mensagens)


def test_renderizar_sincronizado_mostra_horario(tmp_path, st_stub, monkeypatch) -> None:
    _ciclo_noop(monkeypatch)
    arquivo = _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    candidato = (str(arquivo), arquivo.stat().st_mtime_ns, arquivo.stat().st_size)
    st_stub.session_state.update(
        {
            "robo_pasta_alvo": str(tmp_path),
            "robo_processado_sig": (candidato,),
            "robo_hora_sucesso": datetime(2026, 3, 5, 10, 20, 30),
            "robo_arquivos_processados": {candidato[0]: candidato[1]},
            "robo_duplicatas_removidas": 3,
        }
    )

    robo.renderizar_robo_local()
    corpo = " | ".join(texto for _, texto in st_stub.mensagens)
    assert "✅ Sincronizado às 10:20:30" in corpo
    assert "✅ NET-LESTE — Atividades-SPO.csv" in corpo
    assert "3 linha(s) idêntica(s) removida(s)" in corpo


def test_renderizar_aguardando_lock(tmp_path, st_stub, monkeypatch) -> None:
    _ciclo_noop(monkeypatch)
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    st_stub.session_state["_robo_aguardando_lock"] = (
        "'Atividades-SPO.csv' está bloqueado."
    )

    robo.renderizar_robo_local(pasta_padrao=str(tmp_path))
    assert any(
        "⏳ 'Atividades-SPO.csv' está bloqueado." in texto
        for _, texto in st_stub.mensagens
    )


def test_renderizar_mostra_erro_com_botoes(tmp_path, st_stub, monkeypatch) -> None:
    executados: list[dict] = []
    monkeypatch.setattr(
        robo,
        "_executar_verificacao_robo",
        lambda **kwargs: executados.append(kwargs),
    )
    _gravar_csv(tmp_path, "Atividades-SPO.csv", BASE_CSV)
    st_stub.session_state["robo_erro"] = "Arquivo corrompido"
    st_stub.botoes_clicados = {"retry_erro_robo"}

    robo.renderizar_robo_local(pasta_padrao=str(tmp_path))

    assert any("❌ Arquivo corrompido" in texto for _, texto in st_stub.mensagens)
    assert "robo_erro" not in st_stub.session_state
    assert st_stub.session_state["robo_candidato_stable"] == 0
    assert st_stub.reruns == 1
    # O ciclo continua sendo chamado com a pasta e o modo fixos.
    assert executados and executados[0]["pasta_monitorada"] == str(tmp_path)
    assert executados[0]["modo"] == "ultimo"


def test_renderizar_sem_toggle_e_sem_config(tmp_path, st_stub, monkeypatch) -> None:
    _ciclo_noop(monkeypatch)
    st_stub.session_state["robo_ativo"] = False

    robo.renderizar_robo_local(
        pasta_padrao=str(tmp_path), mostrar_toggle=False, mostrar_config=False
    )
    tipos = {tipo for tipo, _ in st_stub.mensagens}
    assert "toggle" not in tipos
    assert "text_input" not in tipos
    assert st_stub.session_state["robo_ativo"] is False
    assert any("⏸ Pausado" in texto for _, texto in st_stub.mensagens)


def test_renderizar_editar_pasta_marca_escolha_do_usuario(
    tmp_path, st_stub, monkeypatch
) -> None:
    monkeypatch.setattr(robo, "_executar_verificacao_robo", lambda **_kw: None)
    outra = tmp_path / "outra"
    outra.mkdir()
    st_stub.session_state.update(
        {"robo_pasta_alvo": str(tmp_path), "input_pasta_robo": str(outra)}
    )

    robo.renderizar_robo_local(pasta_padrao=str(tmp_path))
    assert st_stub.session_state["_robo_pasta_user_set"] is True
    assert st_stub.session_state["robo_pasta_alvo"] == str(outra)


def test_renderizar_avisa_arquivos_fora_do_pipeline(
    tmp_path, st_stub, monkeypatch
) -> None:
    monkeypatch.setattr(robo, "_executar_verificacao_robo", lambda **_kw: None)
    _gravar_csv(
        tmp_path, "Atividades-SPO.csv", BASE_CSV, mtime_ns=1_800_000_000_000_000_000
    )
    _gravar_csv(
        tmp_path, "Atividades-GRS.csv", BASE_CSV, mtime_ns=1_600_000_000_000_000_000
    )
    _gravar_csv(
        tmp_path, "Atividades-SemBase.csv", BASE_CSV, mtime_ns=1_500_000_000_000_000_000
    )

    robo.renderizar_robo_local(pasta_padrao=str(tmp_path))
    corpo = " | ".join(texto for _, texto in st_stub.mensagens)
    assert "2 arquivo(s) mais antigo(s) fora do pipeline." in corpo
    assert "1 arquivo(s) sem SPO, GRS ou ABCDM" in corpo


def test_aliases_publicos() -> None:
    assert robo.renderizar_sidebar_robo is robo.renderizar_robo_local
    assert robo._obter_pasta_robo_padrao is robo.obter_pasta_robo_padrao
    assert robo._obter_metadados_arquivo is robo.obter_metadados_arquivo
    for nome in robo.__all__:
        assert hasattr(robo, nome), nome


def test_modulo_funciona_sem_streamlit(monkeypatch) -> None:
    monkeypatch.setattr(robo, "st", None)
    assert robo.ler_arquivo_totale.__name__ == "ler_arquivo_totale"
    assert robo._obter_gsheets(pd.DataFrame({"A": ["1"]})).equals(
        pd.DataFrame({"A": ["1"]})
    )


# ── Desempenho da padronização (120 mil linhas × 18 colunas) ────────


def _base_grande(linhas: int, colunas: int) -> pd.DataFrame:
    rng = np.random.default_rng(20260305)
    dados: dict[str, pd.Series] = {}
    for indice in range(colunas):
        rotulo = f"COL_{indice:02d}"
        if indice % 3 == 0:
            dados[rotulo] = pd.Series(
                rng.integers(0, 1_000_000, size=linhas).astype(float),
                index=range(linhas),
            )
        elif indice % 3 == 1:
            dados[rotulo] = pd.Series(
                rng.choice(
                    ["joao", "maria", "  pedro ", "n/a", "123.0", "NET-LESTE", ""],
                    size=linhas,
                ),
                index=range(linhas),
            )
        else:
            dados[rotulo] = pd.Series(
                pd.to_datetime(
                    rng.integers(1_700_000_000, 1_800_000_000, size=linhas),
                    unit="s",
                ),
                index=range(linhas),
            )
    return pd.DataFrame(dados)


def test_padronizacao_grande_e_equivalente_e_mais_rapida() -> None:
    """A rota vetorial entrega a mesma saída da célula a célula, com folga.

    Medido neste repositório (pandas 3.0, 120 mil linhas × 18 colunas):
    ~2,2 s na rota célula a célula contra ~0,97 s na vetorial (~2,2×). O limiar
    padrão é 1,5× para não depender da máquina do CI; ajuste com
    ``TOTALE_TESTE_GANHO_MIN`` e reduza a base com ``TOTALE_TESTE_LINHAS``.
    """
    linhas = int(os.environ.get("TOTALE_TESTE_LINHAS", "120000"))
    ganho_minimo = float(os.environ.get("TOTALE_TESTE_GANHO_MIN", "1.5"))
    df = _base_grande(linhas, 18)

    inicio = time.perf_counter()
    vetorial = robo._padronizar_dataframe(df)
    tempo_vetorial = time.perf_counter() - inicio

    inicio = time.perf_counter()
    celula = df.copy()
    for col in celula.columns:
        texto = celula[col].map(robo._celula_para_texto).str.strip()
        celula[col] = texto.mask(texto.str.lower().isin(robo._VALORES_AUSENTES), pd.NA)
    celula = celula.dropna(how="all")
    tempo_celula = time.perf_counter() - inicio

    assert list(vetorial.columns) == list(celula.columns)
    for col in vetorial.columns:
        assert list(vetorial[col].fillna("<NA>")) == list(celula[col].fillna("<NA>")), (
            f"divergência na coluna {col}"
        )

    ganho = tempo_celula / tempo_vetorial if tempo_vetorial else float("inf")
    if linhas < 20_000:
        pytest.skip(
            f"base de {linhas} linhas é pequena demais para medir o ganho "
            f"(obtido {ganho:.2f}×); use TOTALE_TESTE_LINHAS ≥ 20000"
        )
    assert ganho >= ganho_minimo, (
        f"esperava ≥{ganho_minimo}× de ganho; obtido {ganho:.2f}× "
        f"(vetorial {tempo_vetorial:.3f}s × célula {tempo_celula:.3f}s "
        f"em {linhas} linhas × 18 colunas)"
    )
