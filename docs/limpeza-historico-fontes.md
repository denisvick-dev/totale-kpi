# Remover as fontes licenciadas do histórico do Git

> **Operação destrutiva.** Reescreve o SHA de todos os commits. Leia a seção
> [Efeitos colaterais](#efeitos-colaterais) antes de executar.

## Por que

`fonts/Oscine-Bold.ttf` e `fonts/Oscine-Regular.ttf` são fontes da
Dalton Maag distribuídas pela Adobe Fonts. A licença não permite
redistribuir os arquivos — o próprio `assets/fonts/LEIA-ME.md` já dizia
isso. Os arquivos saíram da árvore atual (PR #23), mas continuam no
histórico: qualquer pessoa com acesso ao repositório ainda consegue
recuperá-los por SHA.

O `scripts/instalar_fonte_hero.py` continua sendo o caminho suportado
para uso local: os arquivos ficam em `fonts/` ou `assets/fonts/`, ambas
já ignoradas pelo `.gitignore`.

## O que foi validado

Teste executado em um `git clone --mirror` real do repositório:

| | Antes | Depois |
|---|---|---|
| Commits | 242 | 241 (um commit que só adicionava as fontes virou vazio e foi podado) |
| Tamanho do repositório | 3.9 MB | 3.8 MB |
| Objetos com "Oscine" no caminho | 2 blobs | **0** |
| `ruff check .` / `pytest` | limpos | limpos (8 testes) |

Seis commits da história citam os arquivos (o mais antigo é
`6051121`). Só existem dois caminhos: `fonts/Oscine-Bold.ttf` e
`fonts/Oscine-Regular.ttf`.

## Procedimento

```bash
# 0) Requisito
pip install git-filter-repo

# 1) Clone espelho COMPLETO, fora do diretório de trabalho.
#    --mirror traz todas as branches; um clone raso (--depth) NÃO serve.
git clone --mirror https://github.com/denisvick-dev/totale-kpi.git /tmp/totale-mirror
cd /tmp/totale-mirror

# 2) Conferir o que será removido (deve listar 2 blobs, ambos em fonts/)
git rev-list --objects --all | grep -i oscine

# 3) Reescrever. O glob cobre também caminhos aninhados, como
#    totale-kpi/fonts/..., que já existiram em versões antigas do repo.
git filter-repo --invert-paths --path-glob '*Oscine*' --force

# 4) Verificar: os dois comandos devem voltar vazios
git rev-list --objects --all | grep -i oscine
git log --all --oneline -- '*Oscine*'

# 5) Publicar (destrutivo). --mirror reescreve todas as branches de uma vez.
git push --force --mirror origin
```

### Se o push for recusado

A `main` pode estar protegida. Nesse caso:

- libere temporariamente a proteção (Settings → Branches), ou
- push apenas das branches que você controla:
  `git push --force origin main arena/03074bc1-totale-kpi`

## Efeitos colaterais

- **Todos os SHAs mudam.** PRs abertos precisam ser recriados ou
  rebaseados; o GitHub fecha automaticamente PRs cuja base deixou de
  existir.
- **Clones antigos ficam inconsistentes.** Todo mundo precisa clonar de
  novo:
  ```bash
  git fetch --all && git reset --hard origin/main && git clean -fdx
  ```
  (ou simplesmente apagar a pasta e clonar outra vez).
- **Forks mantêm a cópia.** Reescrita não alcança forks nem caches de
  terceiros que já clonaram.
- **Objetos inalcançáveis no GitHub.** Depois de um force-push, o GitHub
  mantém os objetos antigos acessíveis por SHA por um tempo. Para
  remover de vez é preciso abrir um chamado no suporte do GitHub pedindo
  a limpeza de objetos inalcançáveis.
- **Um commit vazio é podado** por padrão. Para preservá-lo, acrescente
  `--prune-empty never`.

## Opcional: remover também o cache de dados

O commit `24c1599` subiu `dados/cache/volumetria.pkl` (524 KB, dados de
produção pickled) e o manifesto correspondente. O PR #23 remove os dois
da árvore atual; para tirá-los também do histórico, inclua o caminho na
mesma reescrita:

```bash
git filter-repo \
  --invert-paths \
  --path-glob '*Oscine*' \
  --path-glob 'dados/cache/*' \
  --force
```
