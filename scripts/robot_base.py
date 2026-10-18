#!/usr/bin/env python
r"""
scripts/robot_base.py
=====================
🤖 Robô de atualização das bases operacionais (Volumetria + Quebra de Agenda).

O que ele faz
-------------
1. Procura o arquivo **mais recente** na pasta monitorada
   (por padrão, a pasta **Downloads** do usuário);
2. Lê a base (Excel/CSV);
3. Vincula a ``lista_ativos`` do Google Sheets (quando houver rede/credenciais);
4. Gera as bases tratadas de **volumetria.py** e **quebra.py**;
5. Grava o cache em ``dados/cache`` + ``manifesto.json``;
6. As páginas leem esse cache automaticamente — sem upload manual.

Se o arquivo não mudou (mesmo hash SHA-256), o robô **não** reprocessa.

Uso
---
```bash
# execução única
python scripts/robot_base.py

# ignorar o hash e reprocessar mesmo assim
python scripts/robot_base.py --forcar

# vigiar a pasta e atualizar a cada 15 minutos
python scripts/robot_base.py --modo loop --intervalo 15

# ver a situação atual do cache
python scripts/robot_base.py --status
```

Agendamento (exemplos)
----------------------
**Linux/macOS — cron** (a cada 15 min, das 7h às 22h, de seg a sáb):
```cron
*/15 7-22 * * 1-6 cd /caminho/totale-kpi && .venv/bin/python scripts/robot_base.py >> dados/logs/cron.log 2>&1
```

**Windows — Agendador de Tarefas**:
```
schtasks /create /sc minute /mo 15 /tn "Totale Robo Base" ^
  /tr "cmd /c cd /d C:\caminho\totale-kpi && .venv\Scripts\python.exe scripts\robot_base.py"
```

Configuração
------------
``.streamlit/secrets.toml`` (seção ``[base_operacional]``) ou variáveis de
ambiente — veja o docstring de ``components/base_operacional.py``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Garante que o robô enxergue o pacote ``components`` quando executado
# de qualquer pasta.
RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from components import base_operacional as bo

ARQUIVO_LOG = RAIZ / "dados" / "logs" / "robot_base.log"

logger = logging.getLogger("robot_base")

PADRAO_ARQUIVO_PADRAO = "Atividades-*.csv;Atividades-*.xlsx"


# ═══════════════════════════════════════════════════════════
# LOG
# ═══════════════════════════════════════════════════════════
def configurar_log(verboso: bool = False) -> None:
    ARQUIVO_LOG.parent.mkdir(parents=True, exist_ok=True)
    nivel = logging.DEBUG if verboso else logging.INFO

    logger.setLevel(nivel)
    logger.handlers.clear()

    formato = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(message)s", datefmt="%d/%m/%Y %H:%M:%S"
    )

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formato)
    logger.addHandler(console)

    arquivo = logging.FileHandler(ARQUIVO_LOG, encoding="utf-8")
    arquivo.setFormatter(formato)
    logger.addHandler(arquivo)

    logging.getLogger("components.base_operacional").setLevel(nivel)


def log(mensagem: str) -> None:
    logger.info("%s", mensagem)


# ═══════════════════════════════════════════════════════════
# EXECUÇÃO
# ═══════════════════════════════════════════════════════════
def executar(args: argparse.Namespace) -> bo.ResultadoBase:
    """Roda uma rodada do robô e devolve o resultado."""
    inicio = datetime.now()
    log("=" * 62)
    log("🤖 Robô de bases operacionais — início da execução")
    if args.arquivo:
        log(f"📄 Arquivo fixo: {args.arquivo}")

    padrao = args.padrao or bo.config().arquivo_glob or PADRAO_ARQUIVO_PADRAO
    resultado = bo.gerar_bases(
        caminho=args.arquivo,
        forcar=args.forcar,
        usar_cache=not args.forcar,
        pasta_entrada=args.pasta_entrada,
        pasta_cache=args.pasta_cache,
        registrar_log=log,
        arquivo_glob=padrao,
    )

    status = resultado.manifesto.get("status")
    if status == "ok":
        vol = resultado.manifesto.get("arquivos", {}).get("volumetria.pkl", {})
        que = resultado.manifesto.get("arquivos", {}).get("quebra.pkl", {})
        log(
            f"✅ Concluído em {(datetime.now() - inicio).total_seconds():.1f}s — "
            f"Volumetria: {vol.get('registros', 0):,} registros | "
            f"Quebra: {que.get('registros', 0):,} registros".replace(",", ".")
        )
        log(f"🗂️  Cache: {args.pasta_cache or bo.config().pasta_cache}")
    elif status == "sem_arquivo":
        log(f"⚠️  {resultado.manifesto.get('mensagem')}")
    else:
        log(f"❌ {resultado.manifesto.get('mensagem', 'Falha desconhecida.')}")

    return resultado


def modo_loop(args: argparse.Namespace) -> None:
    intervalo = max(1, args.intervalo)
    log(f"🔁 Modo loop ativo — nova verificação a cada {intervalo} minuto(s).")
    try:
        while True:
            executar(args)
            log(f"💤 Aguardando {intervalo} minuto(s) ...")
            time.sleep(intervalo * 60)
    except KeyboardInterrupt:
        log("🛑 Robô interrompido pelo usuário.")


def mostrar_status(args: argparse.Namespace) -> None:
    dados = bo.status_base(args.pasta_cache)
    print(json.dumps(dados, ensure_ascii=False, indent=2))
    if dados.get("status") == "ok":
        for nome, meta in dados.get("arquivos", {}).items():
            print(f"  • {nome}: {meta.get('registros', 0)} registros")


def limpar_cache(args: argparse.Namespace) -> None:
    pasta = Path(args.pasta_cache) if args.pasta_cache else bo.config().pasta_cache
    removidos = 0
    for nome in ("volumetria.pkl", "quebra.pkl", "manifesto.json"):
        caminho = pasta / nome
        if caminho.exists():
            caminho.unlink()
            removidos += 1
    log(f"🧹 Cache limpo ({removidos} arquivo(s) removidos em {pasta}).")


# ═══════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════
def parse_args(argv: list | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Robô de atualização das bases de Volumetria e Quebra de Agenda.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--arquivo",
        help="Processa um arquivo específico (ignora a busca na pasta monitorada).",
    )
    parser.add_argument(
        "--pasta-entrada",
        help="Pasta monitorada (padrão: Downloads do usuário).",
    )
    parser.add_argument(
        "--pasta-cache",
        help="Pasta do cache gerado (padrão: dados/cache).",
    )
    parser.add_argument(
        "--glob",
        dest="padrao",
        help=(
            "Filtro de nome dos arquivos monitorados (padrão: "
            "'Atividades-*.csv;Atividades-*.xlsx'; separe múltiplos padrões com ';')."
        ),
    )
    parser.add_argument(
        "--modo",
        choices=("uma-vez", "loop"),
        default="uma-vez",
        help="Execução única (padrão) ou vigilância contínua da pasta.",
    )
    parser.add_argument(
        "--intervalo",
        type=int,
        default=15,
        help="Minutos entre execuções no modo loop (padrão: 15).",
    )
    parser.add_argument(
        "--recursivo",
        action="store_true",
        help="Varrer também as subpastas da pasta monitorada (padrão: só a raiz).",
    )
    parser.add_argument(
        "--forcar",
        action="store_true",
        help="Reprocessa mesmo que o arquivo não tenha mudado.",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Mostra a situação atual do cache e sai.",
    )
    parser.add_argument(
        "--limpar-cache",
        action="store_true",
        help="Remove o cache gerado e sai.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Log detalhado (DEBUG).",
    )
    return parser.parse_args(argv)


def main(argv: list | None = None) -> int:
    args = parse_args(argv)
    configurar_log(args.verbose)

    if args.recursivo:
        os.environ["TOTALE_BASE_RECURSIVO"] = "1"

    if args.limpar_cache:
        limpar_cache(args)
        return 0

    if args.status:
        mostrar_status(args)
        return 0

    if args.modo == "loop":
        modo_loop(args)
    else:
        resultado = executar(args)
        return 0 if resultado.ok else 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
