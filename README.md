<div align="center">

![Totale Tecnologia](https://img.shields.io/badge/TOTALE-TECNOLOGIA-F37C04?style=for-the-badge&labelColor=012869)

# 📊 Totale KPI

### Plataforma Corporativa de Gestão de Ativos e Indicadores

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

O **Totale KPI** é uma plataforma corporativa completa desenvolvida em **Streamlit** para gestão de ativos, técnicos de campo e indicadores operacionais da Totale Tecnologia. Integra-se diretamente ao Google Sheets como backend, oferecendo dashboards interativos, controle de acesso por perfis e ferramentas de produtividade.

### 🎯 Objetivos

- ✅ Centralizar informações operacionais em uma única plataforma
- ✅ Fornecer visão em tempo real de KPIs estratégicos
- ✅ Automatizar processos manuais e reduzir erros
- ✅ Garantir rastreabilidade com auditoria completa
- ✅ Padronizar comunicações corporativas

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
apenas `aplicar_estilo()`.
Heros, cards de KPI, cabeçalhos, links de painéis e tabelas são reutilizados de
`components/componentes.py` (`render_hero`, `render_kpi`,
`render_section_header`, `render_painel_link`, `render_dataframe`). Evite CSS
próprio para esses elementos: mantenha estilos específicos apenas quando a
página precisar de uma visualização especial. A Gestão de Ativos preserva o
modo escuro, mas reutiliza os mesmos componentes.
Para scripts independentes, importe `render_seletor_tema_sidebar` de
`components.sidebar` e chame essa função após
`st.set_page_config()` e antes de `aplicar_estilo()`.

Teste de regressão (com as dependências do projeto e `pytest` instalados):
```bash
python -m pytest -q
```

### 🤖 Robô de Bases (Volumetria + Quebra de Agenda)
- **Puxa a base automaticamente**: vigia a pasta **Downloads** do usuário (padrão) e processa sempre o arquivo **mais recente** (`.xlsx`, `.xls` ou `.csv`)
- **Atualiza os dois painéis de uma vez**: gera as bases prontas de `volumetria.py` e `quebra.py` com o mesmo pipeline (sem upload manual)
- **Só reprocessa quando muda**: compara o hash SHA-256 do arquivo; base inalterada reaproveita o cache
- **Modo contínuo ou agendado**: `--modo loop --intervalo 15`, cron (Linux/macOS) ou Agendador de Tarefas (Windows)
- **Funciona offline da planilha**: se a `lista_ativos` não estiver acessível, o robô segue e avisa no painel
- Botão **🤖 Atualizar base** na barra lateral das duas páginas roda o robô sob demanda

```bash
# execução única
python scripts/robot_base.py

# forçar reprocessamento
python scripts/robot_base.py --forcar

# vigiar a pasta a cada 15 minutos
python scripts/robot_base.py --modo loop --intervalo 15

# ver a situação do cache
python scripts/robot_base.py --status
```

Configuração (`.streamlit/secrets.toml` ou variáveis de ambiente):

| Chave | Variável | Padrão |
|-------|----------|--------|
| `pasta_entrada` | `TOTALE_BASE_ENTRADA` | `Downloads` do usuário |
| `pasta_cache` | `TOTALE_BASE_CACHE` | `dados/cache` |
| `arquivo_glob` | `TOTALE_BASE_ARQUIVO` | qualquer `.xlsx/.xls/.csv` |
| `ttl_minutos` | `TOTALE_BASE_TTL` | `0` (sem expiração) |

```toml
[base_operacional]
# Opcional: por padrão o robô já usa a pasta Downloads do usuário.
# pasta_entrada = "C:/Users/denis/Downloads"
pasta_cache   = "dados/cache"
```

Para apontar outra pasta na execução:
```bash
python scripts/robot_base.py --pasta-entrada "C:/caminho/das/bases"
```

### 🤖 Robô de Sincronismo local (Central de Atualização)

A página **Atualização de Dados** também hospeda o painel do robô local:

- monitora a pasta **Downloads** (ou o caminho configurado) a cada 5 s;
- aceita somente arquivos iniciados com `Atividades-` (`*.csv`, `.xlsx`, `.xlsm`, `.xls`);
- ignora temporários (`~$`, `.tmp`, `.crdownload`) e arquivos em gravação;
- valida o ZIP do Excel, o encoding/separador do CSV e a estabilidade do arquivo;
- publica a base tratada em `df_memoria` para os painéis e mantém a versão bruta
  em `df_memoria_raw`;
- mostra o status de cada base (SPO→Leste, GRS→Guarulhos, ABCDM→ABCDM), a fila
  da pasta e o diagnóstico do último ciclo.

Uso via terminal (sem Streamlit):

```bash
python components/robo_local.py "C:/Users/<usuario>/Downloads"
python components/robo_local.py "C:/bases" "dados/cache/robo.csv"
```

Para usar uma pasta diferente na interface, abra **⚙️ Pasta monitorada** no painel.

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

### 👥 Gestão de Técnicos
- **Cadastro** de novos técnicos com validação
- **Edição rápida** de campos individuais
- **Importação em lote** via Excel/CSV
- **Desligamento** com registro de motivo
- **Histórico completo** de desligamentos

### 🗂️ Hierarquia Organizacional
- Visualização em treemap
- Análise Base → Monitor → Técnico
- Filtros multi-nível

### 📑 Relatórios Avançados
- Distribuição por Monitor
- Comparativo Ativos × Desligados
- Análise por Base
- Timeline de desligamentos

### 🔐 Segurança e Controle
- **Autenticação** por usuário e senha
- **Perfis de acesso**: Admin, Supervisor, Operador, Leitura
- **Filtros por base** conforme permissão
- **Auditoria completa** de todas as ações

### ✉️ Gerador de Assinatura de E-mail
- Template padronizado Totale
- Personalização Nome, Cargo e Telefones
- Exportação em PNG otimizado para e-mail
- Ajustes finos de posicionamento

---

## 🎯 Critérios de Classificação (Quebra de Agenda)

Regras oficiais implementadas em `components/criterios.py`:

| Segmento | Critério |
|----------|----------|
| 🏠 **Novos Domicílios** | `TIPO O.S 1` contém `ADESAO`, `ADESÃO`, `NOVO`, `NOVA`, `INSTALACAO`, `INSTALAÇÃO`, `INST`, `NOVO DOMICÍLIO`, `PRIMEIRA`, `1 VIA` ou `PRIMEIRO ACESSO` |
| 🔄 **Migração** | `TIPO O.S 1` contém `MUDANCA DE PACOTE` **E** `HABILIDADE DE TRABALHO` contém `PON` |
| 🏢 **PME** | É **Novos Domicílios** **E** `HABILIDADE DE TRABALHO` contém `PME` (sobrepõe ND) |
| ⚪ **Outros** | Não atende a nenhum dos critérios acima |

- 🔦 `FLAG_GPON` é derivada automaticamente: `HABILIDADE` contém `PON` → `Sim`
- A detecção das colunas aceita variações de nome (`TIPO OS 1`, `tipo_os_1`, `HABILIDADES`, `SKILL`...)

## 🚀 Demonstração

### Screenshots

<details>
<summary>📊 Dashboard Principal</summary>

![Dashboard](docs/screenshots/dashboard.png)

</details>

<details>
<summary>🗂️ Hierarquia</summary>

![Hierarquia](docs/screenshots/hierarquia.png)

</details>

<details>
<summary>✉️ Gerador de Assinatura</summary>

![Assinatura](docs/screenshots/assinatura.png)

</details>

---

## 🛠️ Tecnologias

| Categoria | Tecnologias |
|-----------|-------------|
| **Framework** | Streamlit 1.31+ |
| **Linguagem** | Python 3.11+ |
| **Backend** | Google Sheets API |
| **Visualização** | Plotly, Pandas |
| **Autenticação** | Service Account OAuth 2.0 |
| **Processamento de Imagem** | Pillow |
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
\```bash
git clone https://github.com/denisvick-dev/totale-kpi.git
cd totale-kpi
\```

### 2. Crie o Ambiente Virtual
\```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/Mac
source .venv/bin/activate
\```

### 3. Instale as Dependências
\```bash
pip install -r requirements.txt
\```

### 4. Configure as Credenciais

Copie o arquivo de exemplo:
\```bash
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
\```

Edite o `.streamlit/secrets.toml` com suas credenciais reais do Google Cloud e usuários.

### 5. Configure o Google Sheets

1. Acesse o [Google Cloud Console](https://console.cloud.google.com/)
2. Crie um projeto ou selecione um existente
3. Ative as APIs:
   - Google Sheets API
   - Google Drive API
4. Crie uma **Service Account**
5. Baixe a chave JSON
6. Compartilhe sua planilha com o e-mail da service account
7. Preencha os dados no `secrets.toml`

Na página **Quebra de Agenda**, o vínculo de monitores usa a aba `lista_ativos` da mesma planilha da Gestão de Ativos. A aba deve conter `Login` e `Monitor` (e, opcionalmente, `Técnico`, `Base` e `Situação`). O login do arquivo operacional deve corresponder ao da lista. A leitura autenticada usa `[gcp_service_account]`; confira se a planilha foi compartilhada com o `client_email` dessa conta. Quando a base já estiver carregada, clique em **Atualizar Lista de Ativos** na barra lateral para refazer o vínculo sem enviar o arquivo novamente. Para base automática, o botão relê a lista e reprocessa o arquivo original do robô; para upload manual, refaz o vínculo com o arquivo enviado. A página mostra a quantidade de registros vinculados e alerta quando a aba não puder ser lida ou os logins não coincidirem.

As páginas **Volumetria de O.S.** e **Quebra de Agenda** carregam sozinhas a base
gerada pelo robô (`dados/cache`). O upload manual continua disponível como
alternativa — veja a seção [🤖 Robô de Bases](#-robô-de-bases-volumetria--quebra-de-agenda).

### 6. Execute o Aplicativo
\```bash
streamlit run streamlit_app.py
\```

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
├── streamlit_app.py                # Entrada e navegação
├── components/
│   ├── componentes.py             # Design system (heros, cards, tabelas)
│   ├── paleta.py                  # Cores compartilhadas
│   ├── sidebar.py                 # Tema da barra lateral
│   ├── calendario.py              # Dias úteis (Seg–Sáb) e feriados
│   ├── base_operacional.py        # Pipeline único do robô (volumetria + quebra)
│   ├── robo_local.py              # Robô de sincronismo da pasta local + painel
│   └── criterios.py               # Regras de classificação operacional
├── pages/                         # Painéis e Gestão de Ativos independente
├── scripts/
│   └── robot_base.py              # 🤖 Robô de atualização das bases
├── dados/                         # (não versionado)
│   ├── entrada/                   # Opcional: pasta alternativa às bases
│   ├── cache/                     # Bases tratadas + manifesto.json
│   └── logs/                      # Log das execuções do robô
├── assets/
│   ├── icons/totale.ico           # Ícone do app
│   ├── images/novo-logo-totale.png # Logo da navegação
│   └── fonts/                     # Oscine auto-hospedada (não versionada)
├── tests/                         # Testes de interface e de dados
├── .streamlit/                    # Configuração e exemplo de credenciais
├── requirements.txt
└── README.md
```

Foram removidas imagens antigas sem referências no código; as páginas e
arquivos de configuração utilizados continuam preservados.

---

## 🔐 Perfis de Acesso

| Perfil | Permissões |
|--------|-----------|
| 👑 **Admin** | Todas as funções + Auditoria |
| 🎯 **Supervisor** | Cadastro, Edição, Desligamento, Importação |
| ⚙️ **Operador** | Cadastro e Edição básica |
| 👁️ **Leitura** | Apenas visualização de dados |

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
| Uso | Fonte |
|-----|-------|
| 🅰️ **Títulos** (heros, `h1`–`h6`, seções) | **Oscine** (com fallback para Manrope → Segoe UI) |
| 🔢 Valores de KPI e métricas | Manrope |
| Textos e tabelas | Inter |
| Códigos | JetBrains Mono |

A **Oscine** é uma fonte licenciada (Dalton Maag / Adobe Fonts) e vale para
**heros, `h1`–`h6` e títulos de seção**; valores de KPI seguem em Manrope.

Para instalá-la:
```bash
python scripts/instalar_fonte_hero.py ~/Downloads/Oscine   # normaliza os nomes
python scripts/instalar_fonte_hero.py --listar              # confere sem copiar
```

Os arquivos podem ficar em `assets/fonts/` ou em `fonts/` na raiz do
repositório (ambas as pastas são lidas). Sem os arquivos, o app usa a Oscine
se ela estiver ativa no computador (Adobe Creative Cloud) e cai no
**Manrope** caso contrário — nada quebra.
Para servir a todos os usuários (Streamlit Cloud), configure o kit web:
`[tipografia] fonte_hero_url` nos secrets ou `TOTALE_FONTE_HERO_URL`.
Detalhes em `assets/fonts/LEIA-ME.md`.

---

## 📊 Roadmap

- [x] ✅ Dashboard Operacional
- [x] ✅ Gestão de Técnicos completa
- [x] ✅ Sistema de Auditoria
- [x] ✅ Gerador de Assinatura
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