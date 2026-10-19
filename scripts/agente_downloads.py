"""Monitora o Downloads local e envia exportações TOTALE pelo app Streamlit."""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from components.robo_local import obter_pasta_robo_padrao

if TYPE_CHECKING:
    from playwright.sync_api import BrowserContext, Page

logger = logging.getLogger("agente_downloads")

EXTENSOES_VALIDAS = {".csv", ".xlsx", ".xlsm", ".xls"}
EXTENSOES_TEMPORARIAS = (".tmp", ".crdownload", ".partial", ".download", ".part")
TAMANHO_MAXIMO = 80 * 1024 * 1024
URL_PADRAO = "https://totale-kpi.streamlit.app/envio_excel"


def listar_exportacoes(pasta: Path) -> list[Path]:
    try:
        entradas = list(pasta.iterdir())
    except OSError:
        logger.exception("Não foi possível listar a pasta Downloads: %s", pasta)
        return []
    arquivos: list[tuple[Path, int]] = []
    for arquivo in entradas:
        if (
            arquivo.name.startswith(("~$", "."))
            or arquivo.name.lower().endswith(EXTENSOES_TEMPORARIAS)
            or not arquivo.name.lower().startswith("atividades-")
            or arquivo.suffix.lower() not in EXTENSOES_VALIDAS
        ):
            continue
        try:
            stat = arquivo.stat()
            if arquivo.is_file() and stat.st_size > 0:
                arquivos.append((arquivo, stat.st_mtime_ns))
        except OSError:
            logger.warning("Arquivo indisponível durante a varredura: %s", arquivo)
    arquivos.sort(key=lambda item: item[1], reverse=True)
    return [arquivo for arquivo, _ in arquivos]


def aguardar_arquivo_estavel(
    caminho: Path, intervalo: float, tentativas: int = 3
) -> tuple[int, int] | None:
    assinatura_anterior: tuple[int, int] | None = None
    estavel = 0
    for _ in range(tentativas):
        try:
            stat = caminho.stat()
        except OSError:
            return None
        assinatura = (stat.st_mtime_ns, stat.st_size)
        if stat.st_size <= 0:
            estavel = 0
        elif assinatura == assinatura_anterior:
            estavel += 1
            if estavel >= 2:
                return assinatura
        else:
            estavel = 0
        assinatura_anterior = assinatura
        time.sleep(intervalo)
    return None


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def _validar_url(url: str) -> str:
    analisada = urlparse(url)
    if (
        analisada.username
        or analisada.password
        or analisada.query
        or analisada.fragment
    ):
        raise ValueError("A URL do app não pode conter credenciais ou parâmetros.")
    if analisada.scheme != "https" and analisada.hostname not in {
        "localhost",
        "127.0.0.1",
    }:
        raise ValueError("O endereço do app deve usar HTTPS.")
    if not analisada.netloc:
        raise ValueError("Informe o endereço completo do app Streamlit.")
    return url.rstrip("/")


def _perfil_navegador() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if base:
        raiz = Path(base)
    else:
        raiz = Path.home() / "AppData" / "Local"
    perfil = raiz / "TotaleKpi" / "agente-downloads" / "perfil"
    perfil.mkdir(parents=True, exist_ok=True)
    return perfil


def _abrir_pagina(contexto: BrowserContext, url: str) -> Page:
    pagina = contexto.pages[0] if contexto.pages else contexto.new_page()
    pagina.goto(url, wait_until="domcontentloaded")
    logger.info(
        "Navegador aberto. Se solicitado, entre no app; aguardando campo de envio."
    )
    return pagina


def _campo_upload(pagina: Page):
    return (
        pagina.locator('[data-testid="stFileUploader"]')
        .filter(has_text="Enviar exportação do computador")
        .locator('input[type="file"]')
    )


def executar(
    pasta: Path,
    url: str,
    intervalo: float,
    uma_vez: bool = False,
) -> None:
    try:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Playwright não está instalado. Execute: "
            "python -m pip install -r requirements-agent.txt "
            "e python -m playwright install chromium"
        ) from exc

    url_validada = _validar_url(url)
    if not pasta.is_dir():
        raise NotADirectoryError(f"Pasta Downloads não encontrada: {pasta}")

    ultimo_enviado: tuple[str, int, int, str] | None = None
    with sync_playwright() as playwright:
        contexto = playwright.chromium.launch_persistent_context(
            user_data_dir=str(_perfil_navegador()),
            headless=False,
        )
        pagina = _abrir_pagina(contexto, url_validada)
        try:
            while True:
                exportacoes = listar_exportacoes(pasta)
                candidato = exportacoes[0] if exportacoes else None
                if candidato is None:
                    time.sleep(intervalo)
                    if uma_vez:
                        return
                    continue

                assinatura_arquivo = aguardar_arquivo_estavel(candidato, intervalo)
                if assinatura_arquivo is None:
                    logger.info("Aguardando o término do download: %s", candidato.name)
                    if uma_vez:
                        return
                    continue
                mtime_ns, tamanho = assinatura_arquivo
                if tamanho > TAMANHO_MAXIMO:
                    logger.error(
                        "Arquivo acima do limite de 80 MB; ignorado: %s",
                        candidato.name,
                    )
                    if uma_vez:
                        return
                    time.sleep(intervalo)
                    continue

                assinatura = (
                    str(candidato.resolve()),
                    mtime_ns,
                    tamanho,
                    _sha256(candidato),
                )
                try:
                    stat_atual = candidato.stat()
                except OSError:
                    continue
                if (stat_atual.st_mtime_ns, stat_atual.st_size) != assinatura_arquivo:
                    logger.info("O arquivo mudou durante a leitura: %s", candidato.name)
                    continue
                if assinatura == ultimo_enviado:
                    if uma_vez:
                        return
                    time.sleep(intervalo)
                    continue

                campo = _campo_upload(pagina)
                try:
                    campo.wait_for(state="attached", timeout=15_000)
                except PlaywrightTimeoutError:
                    logger.warning(
                        "Campo de envio indisponível; tentando abrir novamente o app."
                    )
                    pagina = _abrir_pagina(contexto, url_validada)
                    if uma_vez:
                        return
                    continue

                logger.info("Enviando exportação: %s", candidato.name)
                campo.set_input_files(str(candidato))
                try:
                    pagina.get_by_text("Exportação recebida:", exact=False).wait_for(
                        state="visible", timeout=90_000
                    )
                except PlaywrightTimeoutError:
                    logger.error(
                        "O app não confirmou o recebimento de %s; o agente tentará "
                        "novamente.",
                        candidato.name,
                    )
                    if uma_vez:
                        raise RuntimeError(
                            f"O app não confirmou o recebimento de {candidato.name}."
                        )
                    time.sleep(intervalo)
                    continue

                ultimo_enviado = assinatura
                logger.info(
                    "Exportação recebida pelo app: %s. O robô continuará o "
                    "processamento automaticamente.",
                    candidato.name,
                )
                if uma_vez:
                    return
                time.sleep(intervalo)
        finally:
            contexto.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Vigia o Downloads do Windows e envia exportações TOTALE novas "
            "ao app publicado."
        )
    )
    parser.add_argument("--url", default=URL_PADRAO, help="URL HTTPS do app Streamlit.")
    parser.add_argument(
        "--pasta",
        type=Path,
        default=None,
        help="Pasta a monitorar (padrão: Downloads configurado no Windows).",
    )
    parser.add_argument(
        "--intervalo",
        type=float,
        default=5,
        help="Intervalo em segundos entre verificações (padrão: 5).",
    )
    parser.add_argument(
        "--uma-vez",
        action="store_true",
        help="Envia o arquivo estável mais recente e encerra.",
    )
    argumentos = parser.parse_args()

    if argumentos.intervalo <= 0:
        parser.error("--intervalo precisa ser maior que zero.")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )
    try:
        executar(
            pasta=(
                argumentos.pasta.expanduser()
                if argumentos.pasta
                else Path(obter_pasta_robo_padrao())
            ),
            url=argumentos.url,
            intervalo=argumentos.intervalo,
            uma_vez=argumentos.uma_vez,
        )
    except KeyboardInterrupt:
        logger.info("Agente encerrado.")
    except (OSError, RuntimeError, ValueError) as exc:
        logger.error("%s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
