# Tipografia corporativa

O app usa três famílias, todas **SIL Open Font License (OFL)** — ou seja,
podem ser versionadas e redistribuídas sem restrição de licença:

| Papel | Família | Pesos versionados |
|---|---|---|
| Títulos, heros, valores de KPI e **DataFrames** | **Manrope** | 400, 500, 600, 700, 800 |
| Corpo, rótulos, controles e gráficos | **Inter** | 400, 500, 600, 700 |
| Código e blocos mono | **JetBrains Mono** | 400, 500 |

## Arquivos

Os `.woff2` ficam nesta pasta no subconjunto `latin`, que cobre o
português (acentos, cedilha e ordinais). `latin-ext` só é necessário para
outros idiomas:

```text
assets/fonts/manrope-latin-{400,500,600,700,800}-normal.woff2
assets/fonts/inter-latin-{400,500,600,700}-normal.woff2
assets/fonts/jetbrains-mono-latin-{400,500}-normal.woff2
assets/fonts/LICENSE-Manrope.txt
assets/fonts/LICENSE-Inter.txt
assets/fonts/LICENSE-JetBrainsMono.txt
```

As licenças acompanham os binários — é isso que a OFL exige ao
redistribuir. Se algum arquivo for substituído, mantenha o `LICENSE`
correspondente.

## Como o app carrega

`components/componentes.py` lê esta pasta e embute os arquivos em base64 no
`@font-face` injetado no `<head>` (o Streamlit Cloud não serve arquivos
estáticos por padrão). Não há instalação, kit web nem CDN de fontes
envolvidos.

Duas definições precisam concordar sempre:

1. `FONTE_TABELA` em `components/componentes.py`;
2. `font` em `.streamlit/config.toml`.

O motivo é o canvas dos `st.dataframe` (glide-data-grid): ele ignora o
`font-family` vindo do `Styler` e usa a fonte do tema. Se as duas
divergirem, a tabela renderiza em uma família e o resto do app em outra.

## Como atualizar ou adicionar um peso

Os arquivos vêm do projeto [Fontsource](https://fontsource.org) (empacota
o Google Fonts):

```bash
npm pack @fontsource/manrope @fontsource/inter @fontsource/jetbrains-mono
tar xzf fontsource-manrope-*.tgz --strip-components=1 -C /tmp/manrope
cp /tmp/manrope/files/manrope-latin-900-normal.woff2 assets/fonts/
```

Depois, inclua o peso em `_FAMILIAS_CORPORATIVAS` (`components/componentes.py`).
O `@font-face` é regerado sozinho: a assinatura de cache considera o
`mtime` de cada arquivo.

## Testes

`tests/test_tipografia.py` garante que os arquivos dos pesos declarados
existem, que o `font` do `config.toml` coincide com `FONTE_TABELA` e que
nenhuma referência à fonte licenciada anterior sobrou no código.
