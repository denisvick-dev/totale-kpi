# Agente local de Downloads

O app publicado no Streamlit Cloud não consegue acessar pastas do computador do
usuário. Para automatizar a leitura de `Downloads`, execute o agente neste
Windows: ele monitora a pasta local e envia o arquivo estável para a página
**Atualização de Dados** no app.

## Requisitos

- Windows com Python 3.11 instalado;
- cópia local deste repositório;
- acesso ao app TOTALE KPI e autenticação, se solicitada.

## Instalação inicial

No PowerShell, na pasta do repositório:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-agent.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

## Uso diário

Execute `scripts\iniciar_agente_downloads.bat`. O agente abre o app em um
navegador persistente. Se necessário, entre normalmente e mantenha o navegador
e o processo do agente abertos. Novos arquivos estáveis serão enviados
automaticamente.

O agente considera apenas o arquivo mais recente que:

- começa com `Atividades-`;
- termina em `.csv`, `.xlsx`, `.xlsm` ou `.xls`;
- não está vazio, temporário ou ainda sendo gravado;
- tem no máximo 80 MB.

Para enviar o mais recente uma única vez:

```powershell
.\.venv\Scripts\python.exe -m scripts.agente_downloads --uma-vez
```

Para escolher outro diretório ou endereço do app:

```powershell
.\.venv\Scripts\python.exe -m scripts.agente_downloads `
  --pasta "C:\bases" `
  --url "https://totale-kpi.streamlit.app/envio_excel"
```

Encerre o monitoramento com `Ctrl+C`. O login persistente do navegador fica no
perfil local `%LOCALAPPDATA%\TotaleKpi\agente-downloads\perfil`.

## Execução local sem o app publicado

Se o próprio Streamlit estiver sendo executado no computador, o processo local
pode ler `Downloads` diretamente. Essa configuração é diferente do agente de
envio para o app publicado; o caminho padrão ou alternativo é configurado na
interface do robô ou com `TOTALE_BASE_ENTRADA`.

## Estrutura do código

- `scripts/agente_downloads.py`: monitoramento local e envio pelo navegador;
- `scripts/iniciar_agente_downloads.bat`: inicialização no Windows;
- `components/robo_local.py`: validação, processamento e interface do robô;
- `pages/envio_excel.py`: Central de Atualização de Dados.
