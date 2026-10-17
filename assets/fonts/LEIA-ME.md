# Fonte dos títulos (Oscine)

Os **títulos** do app — heros, `h1`–`h6` e títulos de seção — usam a família
**Oscine** (Dalton Maag / Adobe Fonts). Os valores de KPI/métrica seguem com a
Manrope, que é melhor para números.

Como a licença não permite redistribuir os arquivos, a fonte é aplicada nesta ordem:

1. **Kit web** configurado em `.streamlit/secrets.toml`:

   ```toml
   [tipografia]
   fonte_hero_url = "https://use.typekit.net/XXXXXXX.css"
   ```

   ou na variável de ambiente `TOTALE_FONTE_HERO_URL`.

2. **Arquivos auto-hospedados** nesta pasta (embutidos em base64 no CSS).
   O jeito mais fácil é deixar que o instalador normalize os nomes:

   ```bash
   python scripts/instalar_fonte_hero.py ~/Downloads/Oscine
   python scripts/instalar_fonte_hero.py ~/Downloads/Oscine --listar  # só confere
   python scripts/instalar_fonte_hero.py --limpar                     # desfaz
   ```

   Ele aceita arquivos soltos ou a pasta inteira e grava:

   ```text
   assets/fonts/oscine-regular.woff2
   assets/fonts/oscine-bold.woff2
   assets/fonts/oscine-extrabold.woff2
   ```

   Extensões aceitas: `.woff2`, `.woff`, `.otf`, `.ttf`.

3. **Instalada no computador** — basta estar ativa (o Adobe Creative Cloud ativa
   a Oscine automaticamente para assinantes).

Se nada disso estiver disponível, o título cai automaticamente em **Manrope**
(fonte institucional dos demais títulos), sem quebrar o layout.
