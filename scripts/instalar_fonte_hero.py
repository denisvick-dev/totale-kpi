#!/usr/bin/env python
r"""
scripts/instalar_fonte_hero.py
==============================
Instala os arquivos da **Oscine** na pasta usada pelos títulos do app.

O script apenas normaliza os nomes dos arquivos para os pesos que o
``components/componentes.py`` procura em ``assets/fonts``:

    oscine-regular.woff2 / .otf / .ttf / .woff   → peso 400
    oscine-medium.*                              → peso 500
    oscine-bold.*                                → peso 700
    oscine-extrabold.*                           → peso 800

Uso
---
```bash
# arquivos avulsos ou pasta inteira
python scripts/instalar_fonte_hero.py ~/Downloads/Oscine/Oscine-Bold.otf
python scripts/instalar_fonte_hero.py ~/Downloads/Oscine

# só conferir o que seria instalado
python scripts/instalar_fonte_hero.py ~/Downloads/Oscine --listar

# remover as fontes instaladas
python scripts/instalar_fonte_hero.py --limpar
```

Depois de instalar, reinicie o app: os títulos (heros, h1–h6 e títulos de
seção) passam a usar a Oscine. Se os arquivos não estiverem lá, o app cai
automaticamente no Manrope — nada quebra.
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

PASTA_PADRAO = RAIZ / "assets" / "fonts"

EXTENSOES_ACEITAS: Tuple[str, ...] = (".woff2", ".woff", ".otf", ".ttf")

#: Pesos suportados pelo CSS, com as palavras que os identificam no nome.
MAPA_PESOS: Tuple[Tuple[int, Tuple[str, ...]], ...] = (
    (800, ("extrabold", "extra bold", "extrabold Demo", "black", "heavy", "ultra")),
    (700, ("semibold", "semi bold", "demi", "bold", "negrito")),
    (500, ("medium", "medio", "médio")),
    (400, ("extralight", "light", "thin", "book", "roman", "normal", "regular")),
)

NOMES_POR_PESO = {
    400: "oscine-regular",
    500: "oscine-medium",
    700: "oscine-bold",
    800: "oscine-extrabold",
}

logger = logging.getLogger("instalar_fonte_hero")


def detectar_peso(nome: str) -> int:
    """Infere o peso pelo nome do arquivo (Regular, Bold, ExtraBold...)."""
    base = Path(str(nome).lower()).stem.replace("_", " ").replace("-", " ")
    for peso, termos in MAPA_PESOS:
        if any(termo in base for termo in termos):
            return peso
    return 400


def coletar_arquivos(caminhos: Iterable[str | Path]) -> List[Path]:
    """Aceita arquivos soltos e pastas (varredura não recursiva)."""
    arquivos: List[Path] = []
    for caminho in caminhos:
        p = Path(caminho)
        if p.is_dir():
            arquivos.extend(
                sorted(
                    f
                    for f in p.iterdir()
                    if f.is_file() and f.suffix.lower() in EXTENSOES_ACEITAS
                )
            )
        elif p.is_file() and p.suffix.lower() in EXTENSOES_ACEITAS:
            arquivos.append(p)
        else:
            logger.warning("Ignorado (não é fonte suportada): %s", p)
    return arquivos


def instalar(
    caminhos: Iterable[str | Path],
    destino: Optional[Path] = None,
    simular: bool = False,
) -> List[Tuple[Path, Path]]:
    """
    Copia as fontes para ``destino`` com os nomes canônicos.

    Retorna a lista ``(origem, destino_final)``. Com ``simular=True`` nada é
    gravado — apenas calculado (usado pelo ``--listar``).
    """
    pasta = Path(destino) if destino else PASTA_PADRAO
    if not simular:
        pasta.mkdir(parents=True, exist_ok=True)

    instalados: List[Tuple[Path, Path]] = []
    for origem in coletar_arquivos(caminhos):
        peso = detectar_peso(origem.name)
        nome_final = f"{NOMES_POR_PESO[peso]}{origem.suffix.lower()}"
        alvo = pasta / nome_final
        instalados.append((origem, alvo))
        if not simular:
            shutil.copy2(origem, alvo)
            logger.info("✔ %s → %s (peso %d)", origem.name, alvo, peso)
    return instalados


def limpar(destino: Optional[Path] = None) -> int:
    pasta = Path(destino) if destino else PASTA_PADRAO
    removidos = 0
    if not pasta.is_dir():
        return 0
    for arquivo in pasta.iterdir():
        if arquivo.is_file() and arquivo.stem.startswith("oscine-"):
            arquivo.unlink()
            removidos += 1
            logger.info("🗑️  removido %s", arquivo.name)
    return removidos


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Instala a fonte Oscine usada nos títulos do app."
    )
    parser.add_argument("arquivos", nargs="*", help="Arquivos de fonte ou pastas.")
    parser.add_argument(
        "--destino", help=f"Pasta de destino (padrão: {PASTA_PADRAO})."
    )
    parser.add_argument(
        "--listar",
        action="store_true",
        help="Mostra o que seria instalado, sem copiar nada.",
    )
    parser.add_argument(
        "--limpar", action="store_true", help="Remove as fontes instaladas."
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.limpar:
        removidos = limpar(args.destino)
        print(f"✅ {removidos} arquivo(s) removido(s).")
        return 0

    if not args.arquivos:
        parser.error("informe ao menos um arquivo ou pasta de fontes.")

    instalados = instalar(args.arquivos, destino=args.destino, simular=args.listar)

    if not instalados:
        print("⚠️  Nenhuma fonte compatível encontrada (.woff2, .woff, .otf, .ttf).")
        return 1

    for origem, alvo in instalados:
        verbo = "seria instalado" if args.listar else "instalado"
        print(f"{'📄' if args.listar else '✔'} {origem.name} → {alvo.name} ({verbo})")

    if args.listar:
        return 0

    print(f"\n✅ {len(instalados)} fonte(s) instalada(s). Reinicie o app.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
