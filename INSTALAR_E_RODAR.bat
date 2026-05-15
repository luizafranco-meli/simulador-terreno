@echo off
title Simulador de Terreno - Instalacao
echo ============================================================
echo  Simulador de Compra de Terreno
echo ============================================================
echo.

:: Verificar se uv esta instalado (instalador mais moderno)
where uv >nul 2>&1
if %errorlevel% equ 0 goto usar_uv

:: Verificar se Python esta instalado
where python >nul 2>&1
if %errorlevel% equ 0 goto usar_python

:: Instalar uv automaticamente (nao precisa de Python pre-instalado)
echo [1/3] Python nao encontrado. Instalando uv (gerenciador Python moderno)...
powershell -Command "irm https://astral.sh/uv/install.ps1 | iex"
if %errorlevel% neq 0 (
    echo ERRO: Nao foi possivel instalar uv automaticamente.
    echo Por favor instale Python manualmente em: https://www.python.org/downloads/
    echo Depois execute este arquivo novamente.
    pause
    exit /b 1
)
:: Atualizar PATH para encontrar uv
set "PATH=%USERPROFILE%\.local\bin;%PATH%"

:usar_uv
echo [2/3] Instalando dependencias...
uv pip install --system streamlit numpy numpy-financial pandas plotly openpyxl supabase 2>nul
if %errorlevel% neq 0 (
    uv run --with streamlit --with numpy-financial --with pandas --with plotly --with openpyxl --with supabase streamlit run "%~dp0app.py"
    goto fim
)
echo [3/3] Iniciando o simulador...
uv run streamlit run "%~dp0app.py"
goto fim

:usar_python
echo [2/3] Instalando dependencias Python...
python -m pip install -q streamlit numpy numpy-financial pandas plotly openpyxl supabase
if %errorlevel% neq 0 (
    echo ERRO ao instalar dependencias. Tente: pip install -r requirements.txt
    pause
    exit /b 1
)
echo [3/3] Iniciando o simulador...
python -m streamlit run "%~dp0app.py"

:fim
pause
