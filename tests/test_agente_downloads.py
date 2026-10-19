from __future__ import annotations

import os

import pytest

from scripts import agente_downloads as agente


def test_listar_exportacoes_filtra_e_ordena_por_modificacao(tmp_path):
    antigo = tmp_path / "Atividades-SPO-antigo.csv"
    recente = tmp_path / "Atividades-GRS-recente.xlsx"
    antigo.write_bytes(b"antigo")
    recente.write_bytes(b"recente")
    os.utime(antigo, ns=(1_700_000_000_000_000_000,) * 2)
    os.utime(recente, ns=(1_800_000_000_000_000_000,) * 2)
    (tmp_path / "Atividades-ABCDM.csv.crdownload").write_bytes(b"temporario")
    (tmp_path / "~$Atividades-SPO.xlsx").write_bytes(b"temporario")
    (tmp_path / "outra-base.csv").write_bytes(b"ignorado")
    (tmp_path / "Atividades-SPO.txt").write_bytes(b"extensao invalida")

    assert agente.listar_exportacoes(tmp_path) == [recente, antigo]


def test_aguardar_arquivo_estavel_retorna_assinatura(tmp_path, monkeypatch):
    arquivo = tmp_path / "Atividades-SPO.csv"
    arquivo.write_bytes(b"base")
    monkeypatch.setattr(agente.time, "sleep", lambda _intervalo: None)

    assinatura = agente.aguardar_arquivo_estavel(arquivo, intervalo=0)

    stat = arquivo.stat()
    assert assinatura == (stat.st_mtime_ns, stat.st_size)


def test_validar_url_exige_https_e_rejeita_segredos_na_url():
    assert (
        agente._validar_url("https://totale-kpi.streamlit.app/envio_excel")
        == "https://totale-kpi.streamlit.app/envio_excel"
    )
    assert agente._validar_url("http://localhost:8501") == "http://localhost:8501"
    with pytest.raises(ValueError, match="HTTPS"):
        agente._validar_url("http://exemplo.com")
    with pytest.raises(ValueError, match="credenciais"):
        agente._validar_url("https://usuario:senha@exemplo.com")
