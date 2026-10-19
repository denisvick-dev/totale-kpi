@echo off
set "ROOT=%~dp0.."
set "PYTHON=%ROOT%\.venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Ambiente .venv nao encontrado. Crie-o e instale as dependencias do projeto.
    exit /b 1
)

"%PYTHON%" -m scripts.agente_downloads %*
