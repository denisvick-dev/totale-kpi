"""Regressões do robô de bases (pasta monitorada → cache → páginas)."""

import os
import time
from pathlib import Path

import pandas as pd
import pytest

from components import base_operacional as bo
from scripts import robot_base


#: Padrão de 6 linhas: 2 ND, 2 Migração, 1 PME e 1 Outros.
PADRAO_LINHAS = [
    ("EXECUTADA", "ADESAO", "HFC(1/100)", "SAO PAULO"),
    ("EXECUTADA", "ADESAO", "HFC(1/100)", "SAO PAULO"),
    ("EXECUTADA", "MUDANCA DE PACOTE", "PON(1/100)", "GUARULHOS"),
    ("NÃO EXECUTADA", "MUDANCA DE PACOTE", "PON(1/100)", "GUARULHOS"),
    ("NÃO EXECUTADA", "ADESAO", "PME(1/100)", "DIADEMA"),
    ("PENDENTE", "REPARO", "HFC(1/100)", "MAUA"),
]


def base_sintetica(caminho: Path, registros: int = 6) -> Path:
    """Cria uma base de teste (ciclo do padrão + 1 linha sem contrato)."""
    linhas = []
    for i in range(registros):
        status, tipo, habilidade, cidade = PADRAO_LINHAS[i % len(PADRAO_LINHAS)]
        linhas.append(
            {
                "CONTRATO": str(1000 + i),
                "LOGIN DO TÉCNICO": f"login{i}",
                "TÉCNICO": "TEC A",
                "MONITOR": "MON A",
                "STATUS DA ATIVIDADE": "ATIVA",
                "STATUS DA O.S 1": status,
                "TIPO O.S 1": tipo,
                "HABILIDADE DE TRABALHO": habilidade,
                "CIDADE": cidade,
                "TOTAL DE TAREFAS": 1,
            }
        )

    # Última linha sem contrato: precisa ser descartada no tratamento.
    status, tipo, habilidade, cidade = PADRAO_LINHAS[0]
    linhas.append(
        {
            "CONTRATO": "",
            "LOGIN DO TÉCNICO": "sem.contrato",
            "TÉCNICO": "TEC B",
            "MONITOR": "MON B",
            "STATUS DA ATIVIDADE": "ATIVA",
            "STATUS DA O.S 1": status,
            "TIPO O.S 1": tipo,
            "HABILIDADE DE TRABALHO": habilidade,
            "CIDADE": cidade,
            "TOTAL DE TAREFAS": 1,
        }
    )

    pd.DataFrame(linhas).to_excel(caminho, index=False)
    return caminho


@pytest.fixture()
def ambiente(tmp_path, monkeypatch):
    """Isola o robô em pastas temporárias e desliga a busca na nuvem."""
    entrada = tmp_path / "entrada"
    cache = tmp_path / "cache"
    entrada.mkdir()
    cache.mkdir()

    ativos = pd.DataFrame(
        {
            "Login": ["LOGIN0", "LOGIN1"],
            "Técnico": ["TEC SHEETS", "TEC SHEETS 2"],
            "Monitor": ["MON SHEETS", "MON SHEETS"],
        }
    )
    ativos.attrs["fonte_ativos"] = "Google Sheets (autenticado)"
    monkeypatch.setattr(bo, "carregar_lista_ativos", lambda *a, **k: ativos)

    return {"entrada": entrada, "cache": cache, "ativos": ativos}


def test_localiza_o_arquivo_mais_recente(ambiente):
    antigo = base_sintetica(ambiente["entrada"] / "antiga.xlsx")
    os.utime(antigo, (time.time() - 500, time.time() - 500))
    novo = base_sintetica(ambiente["entrada"] / "nova.xlsx")

    assert bo.localizar_base(ambiente["entrada"]) == novo


def test_sem_base_na_pasta_o_robo_avisa(ambiente):
    resultado = bo.gerar_bases(
        pasta_entrada=ambiente["entrada"], pasta_cache=ambiente["cache"]
    )

    assert resultado.ok is False
    assert resultado.manifesto["status"] == "sem_arquivo"
    assert resultado.volumetria is None


def test_robo_gera_as_duas_bases_e_grava_cache(ambiente):
    base_sintetica(ambiente["entrada"] / "base.xlsx")

    resultado = bo.gerar_bases(
        pasta_entrada=ambiente["entrada"], pasta_cache=ambiente["cache"]
    )

    assert resultado.ok is True
    assert (ambiente["cache"] / "volumetria.pkl").exists()
    assert (ambiente["cache"] / "quebra.pkl").exists()
    assert (ambiente["cache"] / "manifesto.json").exists()

    # 7 registros − 1 contrato vazio = 6
    assert len(resultado.volumetria) == 6
    assert len(resultado.quebra) == 6


def test_quebra_aplica_os_criterios_oficiais(ambiente):
    base_sintetica(ambiente["entrada"] / "base.xlsx")
    resultado = bo.gerar_bases(
        pasta_entrada=ambiente["entrada"], pasta_cache=ambiente["cache"]
    )

    quebra = resultado.quebra
    segmentos = quebra["TIPO_SERVICO"].value_counts().to_dict()

    assert segmentos["Novos Domicílios"] == 2   # ADESAO + HFC
    assert segmentos["Migração"] == 2           # MUDANCA DE PACOTE + PON
    assert segmentos["PME"] == 1                # ADESAO + PME
    assert segmentos["Outros"] == 1             # REPARO
    assert quebra.attrs["diag_susp"] == 0
    assert quebra.attrs["diag_inv"] == 1
    assert quebra.attrs["diag_vinculados"] == 2


def test_volumetria_devolve_status_e_regiao(ambiente):
    base_sintetica(ambiente["entrada"] / "base.xlsx")
    resultado = bo.gerar_bases(
        pasta_entrada=ambiente["entrada"], pasta_cache=ambiente["cache"]
    )

    volumetria = resultado.volumetria
    assert set(volumetria["STATUS CONTRATO"].unique()) == {
        "Executada",
        "Não Executada",
        "Pendente",
    }
    assert "LESTE" in set(volumetria["REGIÃO"])
    assert "GRU" in set(volumetria["REGIÃO"])
    assert "ABCDM" in set(volumetria["REGIÃO"])
    # Técnico/Monitor vindos da lista de ativos prevalecem sobre o arquivo
    assert "TEC SHEETS" in set(volumetria["TÉCNICO"])


def test_cache_e_reaproveitado_quando_o_arquivo_nao_muda(ambiente):
    base_sintetica(ambiente["entrada"] / "base.xlsx")

    primeiro = bo.gerar_bases(
        pasta_entrada=ambiente["entrada"], pasta_cache=ambiente["cache"]
    )
    segundo = bo.gerar_bases(
        pasta_entrada=ambiente["entrada"], pasta_cache=ambiente["cache"]
    )

    assert primeiro.do_cache is False
    assert segundo.do_cache is True
    assert segundo.manifesto["hash"] == primeiro.manifesto["hash"]
    assert len(segundo.volumetria) == len(primeiro.volumetria)


def test_arquivo_novo_reprocessa(ambiente):
    antigo = base_sintetica(ambiente["entrada"] / "base.xlsx", registros=6)
    os.utime(antigo, (time.time() - 300, time.time() - 300))
    bo.gerar_bases(pasta_entrada=ambiente["entrada"], pasta_cache=ambiente["cache"])

    base_sintetica(ambiente["entrada"] / "base_nova.xlsx", registros=12)
    resultado = bo.gerar_bases(
        pasta_entrada=ambiente["entrada"], pasta_cache=ambiente["cache"]
    )

    assert resultado.do_cache is False
    assert len(resultado.volumetria) == 12


def test_status_base_reflete_o_cache(ambiente):
    assert bo.status_base(ambiente["cache"])["status"] == "sem_cache"

    base_sintetica(ambiente["entrada"] / "base.xlsx")
    bo.gerar_bases(pasta_entrada=ambiente["entrada"], pasta_cache=ambiente["cache"])

    status = bo.status_base(ambiente["cache"])
    assert status["status"] == "ok"
    assert status["arquivo"] == "base.xlsx"
    assert status["arquivos"]["quebra.pkl"]["registros"] == 6


def test_cli_do_robo_gera_o_cache(ambiente, monkeypatch):
    base_sintetica(ambiente["entrada"] / "base.xlsx")
    monkeypatch.setattr(robot_base, "ARQUIVO_LOG", ambiente["cache"] / "logs" / "robo.log")

    codigo = robot_base.main(
        [
            "--pasta-entrada",
            str(ambiente["entrada"]),
            "--pasta-cache",
            str(ambiente["cache"]),
        ]
    )

    assert codigo == 0
    assert bo.status_base(ambiente["cache"])["status"] == "ok"


def test_cli_status_e_limpar_cache(ambiente, monkeypatch, capsys):
    base_sintetica(ambiente["entrada"] / "base.xlsx")
    monkeypatch.setattr(robot_base, "ARQUIVO_LOG", ambiente["cache"] / "logs" / "robo.log")
    robot_base.main(
        ["--pasta-entrada", str(ambiente["entrada"]), "--pasta-cache", str(ambiente["cache"])]
    )

    assert robot_base.main(["--pasta-cache", str(ambiente["cache"]), "--status"]) == 0
    assert "base.xlsx" in capsys.readouterr().out

    assert robot_base.main(["--pasta-cache", str(ambiente["cache"]), "--limpar-cache"]) == 0
    assert not (ambiente["cache"] / "manifesto.json").exists()
