<div align="center">

![Totale Tecnologia](https://img.shields.io/badge/TOTALE-TECNOLOGIA-F37C04?style=for-the-badge&labelColor=012869)

# 📊 Totale KPI

### Plataforma Corporativa de Indicadores Operacionais

[![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Google Sheets](https://img.shields.io/badge/Google_Sheets-34A853?style=flat&logo=google-sheets&logoColor=white)](https://sheets.google.com/)
[![Plotly](https://img.shields.io/badge/Plotly-3F4F75?style=flat&logo=plotly&logoColor=white)](https://plotly.com/)
[![License](https://img.shields.io/badge/License-Proprietary-red?style=flat)](LICENSE)

[🌐 Demo ao Vivo](https://totale-kpi.streamlit.app) · 
[🐛 Reportar Bug](https://github.com/denisvick-dev/totale-kpi/issues) · 
[✨ Solicitar Feature](https://github.com/denisvick-dev/totale-kpi/issues)

</div>

---

## 📖 Sobre o Projeto

O **Totale KPI** é uma plataforma corporativa desenvolvida em **Streamlit** para indicadores de produtividade e de técnicos de campo da Totale Tecnologia. As bases de produção e consultivos integram-se ao Google Sheets, com dashboards interativos de performance, produtividade e conversão.

### 🎯 Objetivos

- ✅ Centralizar informações operacionais em uma única plataforma
- ✅ Fornecer visão em tempo real de KPIs estratégicos
- ✅ Automatizar processos manuais e reduzir erros
- ✅ Padronizar o tratamento das bases operacionais

---

## ✨ Funcionalidades

### 🎨 Aparência TOTALE
Na barra lateral, abra **Aparência TOTALE → Cor da barra lateral** e escolha:
- **Prata TOTALE** (padrão): acabamento prata com detalhes institucionais.
- **Azul institucional**: fundo azul com textos claros.
- **Laranja TOTALE**: tons suaves de laranja com textos escuros.
- **Claro corporativo**: fundo claro com destaques em azul.

A escolha vale para todas as páginas durante a sessão atual, sem alterar as
cores semânticas dos indicadores ou os dados e filtros dos painéis.

Os temas, o seletor e o CSS da barra lateral ficam em `components/sidebar.py`.
As cores compartilhadas ficam em `components/paleta.py`, evitando dependências
circulares com `componentes.py`. O seletor é renderizado uma única vez em
`streamlit_app.py`, antes de `aplicar_estilo()`. As páginas continuam chamando
apenas `aplicar_estilo()`: o entrypoint abre a execução com `nova_execucao()` e
a função ignora chamadas repetidas no mesmo rerun, então o CSS (com as fontes
em base64) entra uma única vez no DOM.
Heros, cards de KPI, cabeçalhos, links de painéis e tabelas são reutilizados de
`components/componentes.py` (`render_hero`, `render_kpi`,
`render_section_header`, `render_painel_link`, `render_dataframe`). Evite CSS
próprio para esses elementos: mantenha estilos específicos apenas quando a
página precisar de uma visualização especial.
Para scripts independentes, importe `render_seletor_tema_sidebar` de
`components.sidebar` e chame essa função após
`st.set_page_config()` e antes de `aplicar_estilo()`.

Para executar os testes e a verificação estática, instale as dependências de
desenvolvimento e rode:
```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
ruff check .
```

### 🗓️ Projeções em dias úteis (Seg–Sáb)
- A semana útil é de **segunda a sábado** — **domingos não contam**
- **Feriados** também são descontados: nacionais (fixos e móveis: Carnaval, Paixão de Cristo, Corpus Christi) e **estaduais de SP** (09/07)
- Regra única em `components/calendario.py`, usada por **Qtde. de O.S.**, **Ranking de Pontos** e **Consultivos**
- Feriados extras (municipais, pontos facultativos da operação) podem ser adicionados em `config/feriados_extra.json` ou na variável `TOTALE_FERIADOS_EXTRA`

### 📊 Dashboard Operacional
- Panorama em tempo real com KPIs essenciais
- Filtros dinâmicos por Base, Monitor e Situação
- Gráficos interativos (pizza, barras, heatmap)
- Exportação em Excel e CSV

### 🎯 Aderência à projeção (Ranking de Pontos)
- Aba dedicada no painel de Produtividade: projeção de fechamento × meta por **monitor**, **projeto** ou **monitor × projeto**
- Meta de referência selecionável (300/350/375/400 pts/equipe/mês), com gráfico de aderência, % de equipes aderentes, gap e ritmo necessário por dia útil
- Detalhe das equipes de cada grupo e exportação em Excel; cálculo em `components/aderencia.py`

Os dashboards seguem um padrão único de leitura — hero, insight de
status, KPIs e conteúdo em abas (Ranking/Aderência em Pontos;
Supervisor/Projeto/Técnicos em Qtde. de O.S.; Consolidada/Zeradas em
Consultivos). A página inicial mostra o status da base de produção
carregada na sessão.

## 🛠️ Tecnologias

| Categoria | Tecnologias |
|-----------|-------------|
| **Framework** | Streamlit 1.55+ |
| **Linguagem** | Python 3.11+ |
| **Backend** | Google Sheets API |
| **Visualização** | Plotly, Pandas |
| **Autenticação** | Service Account OAuth 2.0 |
| **Exportação** | OpenPyXL |

---

## 📋 Pré-requisitos

- Python **3.11** ou superior
- Conta Google Cloud com **Service Account**
- Planilha Google Sheets compartilhada
- Git

---

## ⚙️ Instalação Local

### 1. Clone o Repositório
```bash
git clone https://github.com/denisvick-dev/totale-kpi.git
cd totale-kpi
```

### 2. Crie o Ambiente Virtual
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
```

### 3. Instale as Dependências
```bash
pip install -r requirements.txt
```

### 4. Configure as Credenciais

Copie o arquivo de exemplo:
```bash
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
```

O `secrets.toml` é opcional: sem ele o app usa apenas os valores padrão.

### 5. Configure o Google Sheets

As bases de **Produção** e **Consultivos** são lidas das planilhas por
**exportação pública em CSV/XLSX** (`URL_PROD` e `URL_CONS` em
`pages/envio_excel.py`). Basta que as planilhas estejam acessíveis por
link para leitura; não há conta de serviço nem chave JSON para
configurar. Para trocar de planilha, atualize as constantes de URL.

### 6. Execute o Aplicativo
```bash
streamlit run streamlit_app.py
```

Acesse: **http://localhost:8501**

---

## 🌐 Deploy no Streamlit Cloud

### Deploy Automático

1. Fork este repositório
2. Acesse [share.streamlit.io](https://share.streamlit.io)
3. Conecte sua conta GitHub
4. Clique em **"New app"**
5. Selecione o repositório e branch
6. Configure:
   - **Main file:** `streamlit_app.py`
   - **Python version:** `3.11`
7. Em **Advanced settings**, cole os secrets
8. Clique em **Deploy**

📚 [Guia completo do Streamlit Cloud](https://docs.streamlit.io/streamlit-community-cloud)

---

## 📁 Estrutura do Projeto

```text
totale-kpi/
├── streamlit_app.py                 # Entrada e navegação
├── components/                      # Design system, calendário e regras compartilhadas
├── pages/                           # Painéis da aplicação e Central de Atualização
├── docs/                             # Guias operacionais e mapa do projeto
├── assets/
│   ├── fonts/                       # Fontes corporativas (SIL OFL) + licenças
│   ├── icons/totale.ico             # Ícone do app
│   └── images/novo-logo-totale.png  # Logo da navegação
├── tests/                           # Testes de interface e de dados
├── .github/workflows/ci.yml         # Testes, compilação e lint
├── .devcontainer/                   # Ambiente Python 3.11
├── .streamlit/                      # Configuração e exemplo de credenciais
├── requirements.txt                 # Dependências de execução
├── requirements-dev.txt             # Ferramentas de teste e lint
├── pyproject.toml                   # Configuração do pytest e Ruff
└── README.md
```

---

## 🎨 Identidade Visual

Cores oficiais Totale Tecnologia:

| Cor | Hex | Uso |
|-----|-----|-----|
| 🔵 Azul Corporativo | `#012869` | Títulos, textos principais |
| 🟠 Laranja Marca | `#F37C04` | Destaques, botões, acentos |
| ⚪ Branco | `#FFFFFF` | Backgrounds |
| ⬜ Cinza Claro | `#F1F5F9` | Backgrounds secundários |

**Tipografia**

Toda a interface usa somente fontes **SIL Open Font License**, versionadas
no próprio repositório — sem CDN, sem kit web e sem fonte proprietária.

| Uso | Fonte | Pesos |
|-----|-------|-------|
| 🅰️ **Títulos** (heros, `h1`–`h6`, seções) | **Manrope** | 800 / 700 |
| 🔢 Valores de KPI e métricas | **Manrope** | 700 |
| 📊 **Tabelas e DataFrames** | **Manrope** (Inter no fallback) | 400–700 |
| Textos, rótulos e controles | **Inter** | 400–700 |
| Códigos | JetBrains Mono | 400 / 500 |

As três famílias ficam em `assets/fonts/*.woff2` (subconjunto `latin`, que
cobre os acentos do português) com as licenças ao lado. O app embute os
arquivos em base64 no `@font-face` injetado no `<head>`, então a tipografia
não depende de acesso do navegador ao Google Fonts.

Duas definições precisam coincidir: `FONTE_TABELA` em
`components/componentes.py` e `font` em `.streamlit/config.toml` — o canvas
dos `st.dataframe` (glide-data-grid) ignora o `font-family` do `Styler` e
usa a fonte do tema. Os testes cobrem essa coerência.

Para trocar ou acrescentar um peso (inclusive `latin-ext`), siga
`assets/fonts/LEIA-ME.md`.

---

## 📊 Roadmap

- [x] ✅ Dashboard Operacional
- [x] ✅ Integração Google Sheets
- [ ] 🚧 Notificações via e-mail
- [ ] 🚧 API REST para integrações
- [ ] 🚧 Aplicativo mobile
- [ ] 🚧 Autenticação 2FA
- [ ] 🚧 Backup automático diário
- [ ] 🚧 Integração com WhatsApp Business

---

## 🤝 Contribuindo

Contribuições são bem-vindas! Siga estes passos:

1. Fork o projeto
2. Crie uma branch: `git checkout -b feature/MinhaFeature`
3. Commit suas mudanças: `git commit -m 'feat: adiciona MinhaFeature'`
4. Push para a branch: `git push origin feature/MinhaFeature`
5. Abra um Pull Request

### 📋 Padrão de Commits

Utilizamos [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` Nova funcionalidade
- `fix:` Correção de bug
- `docs:` Documentação
- `style:` Formatação
- `refactor:` Refatoração
- `test:` Testes
- `chore:` Manutenção

---

## 🐛 Reportar Bugs

Encontrou um bug? Abra uma [issue](https://github.com/denisvick-dev/totale-kpi/issues) com:

- Descrição clara do problema
- Passos para reproduzir
- Comportamento esperado vs atual
- Screenshots (se aplicável)
- Ambiente (SO, versão Python, etc.)

---

## 👨‍💻 Sobre o Autor

<div align="center">

<table>
<tr>
<td align="center" width="150">
<img src="https://github.com/denisvick-dev.png" width="120" style="border-radius:50%"/>
</td>
<td align="left">

### **Denis Vick**
**Analista de COP** · *Totale Tecnologia*

Apaixonado por transformar dados em decisões estratégicas e por criar soluções que facilitam o dia a dia das operações.

</td>
</tr>
</table>

<br>

### 📬 Vamos Conectar!

<a href="https://www.linkedin.com/in/dvick13/">
  <img src="https://img.shields.io/badge/LinkedIn-Denis_Vick-0077B5?style=for-the-badge&logo=linkedin&logoColor=white" />
</a>
<a href="https://github.com/denisvick-dev">
  <img src="https://img.shields.io/badge/GitHub-denisvick--dev-181717?style=for-the-badge&logo=github&logoColor=white" />
</a>
<a href="https://instagram.com/denisvick">
  <img src="https://img.shields.io/badge/Instagram-@denisvick-E4405F?style=for-the-badge&logo=instagram&logoColor=white" />
</a>
<br>
<a href="https://wa.me/5511993045101">
  <img src="https://img.shields.io/badge/WhatsApp-(11)_99304--5101-25D366?style=for-the-badge&logo=whatsapp&logoColor=white" />
</a>
<a href="mailto:denis.vick@totaletecnologia.com.br">
  <img src="https://img.shields.io/badge/Email-denis.vick@totaletecnologia.com.br-D14836?style=for-the-badge&logo=gmail&logoColor=white" />
</a>

</div>

<br>

📱 **WhatsApp Corporativo:** [(11) 99304-5101](https://wa.me/5511993045101)  
📧 **E-mail:** denis.vick@totaletecnologia.com.br  
💼 **LinkedIn:** [/in/dvick13](https://www.linkedin.com/in/dvick13/)  
📸 **Instagram:** [@denisvick](https://instagram.com/denisvick)  
💻 **GitHub:** [@denisvick-dev](https://github.com/denisvick-dev)

</div>

---

## 🙏 Agradecimentos

- [Streamlit](https://streamlit.io/) pela framework incrível
- [Plotly](https://plotly.com/) pelas visualizações interativas
- [Google Cloud](https://cloud.google.com/) pela infraestrutura
- Em especial a **Vania S. Souza** pelo incentivo e confiança em meu trabalho

---

<div align="center">

**Feito com ❤️ por Denis Vick | Analista de COP | Totale Tecnologia**

⭐ Se este projeto foi útil, deixe uma estrela!

![Totale Tecnologia](https://img.shields.io/badge/TOTALE-TECNOLOGIA-F37C04?style=for-the-badge&labelColor=012869)

*Conexão em Movimento*

</div>