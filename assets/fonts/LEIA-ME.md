# Fontes dos títulos dos heros

Os **títulos dos heros** usam a família **Oscine** (Dalton Maag / Adobe Fonts).
Como a licença não permite redistribuir os arquivos, a fonte é aplicada nesta ordem:

1. **Kit web** configurado em `.streamlit/secrets.toml`:

   ```toml
   [tipografia]
   fonte_hero_url = "https://use.typekit.net/XXXXXXX.css"
   ```

   ou na variável de ambiente `TOTALE_FONTE_HERO_URL`.

2. **Arquivos auto-hospedados** nesta pasta (embutidos em base64 no CSS):

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
