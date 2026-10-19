from __future__ import annotations

from components.base_operacional import normalizar_erro_worksheet, resolver_sheet_id


def test_resolver_sheet_id_usa_variavel_de_ambiente(monkeypatch):
    monkeypatch.setenv("TOTALE_SHEET_ID", "abc123")
    assert resolver_sheet_id(default="fallback") == "abc123"

    monkeypatch.delenv("TOTALE_SHEET_ID", raising=False)
    assert (
        resolver_sheet_id(
            "https://docs.google.com/spreadsheets/d/xyz456/edit",
            default="fallback",
        )
        == "xyz456"
    )


def test_normalizar_erro_worksheet_sanitiza_html_404():
    msg = normalizar_erro_worksheet(
        Exception('<!DOCTYPE html><title>Error 404 (Not Found)</title>'),
        "lista_ativos",
    )
    assert "lista_ativos" in msg
    assert "404" in msg
    assert "<!DOCTYPE html>" not in msg
