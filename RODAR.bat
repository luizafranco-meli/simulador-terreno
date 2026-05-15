@echo off
title Simulador de Terreno
cd /d "%~dp0"

where uv >nul 2>&1
if %errorlevel% equ 0 (
    uv run streamlit run app.py
    goto fim
)

where python >nul 2>&1
if %errorlevel% equ 0 (
    python -m streamlit run app.py
    goto fim
)

echo Python nao encontrado. Execute primeiro INSTALAR_E_RODAR.bat
pause

:fim
