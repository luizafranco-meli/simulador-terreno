@echo off
title Publicar Atualização — Simulador de Terreno 2.0
cd /d "%~dp0"

echo ============================================================
echo  Publicar Atualização no Site — v2.0
echo ============================================================
echo.

:: Verificar se git está instalado
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo ERRO: Git nao encontrado.
    echo Instale o Git em: https://git-scm.com/download/win
    pause
    exit /b 1
)

:: Verificar se já é um repositório git
if not exist ".git" (
    echo [1/4] Configurando repositório Git pela primeira vez...
    git init
    git remote add origin https://github.com/luizafranco-meli/simulador-terreno.git
    git branch -M main
)

echo [1/4] Preparando arquivos...
git add app.py requirements.txt

echo [2/4] Salvando alterações...
git commit -m "Atualização do simulador %date% %time%" 2>nul || echo (sem alterações novas — enviando versão atual)

echo [3/4] Cancelando sincronização conflituosa...
git rebase --abort 2>nul

echo [4/4] Enviando para o GitHub...
git push --force origin main

if %errorlevel% equ 0 (
    echo.
    echo ============================================================
    echo  [OK] Publicado com sucesso!
    echo  O site será atualizado em aproximadamente 1 minuto.
    echo  Acesse: https://simulador-terreno.streamlit.app
    echo ============================================================
) else (
    echo.
    echo ERRO ao enviar. Tente novamente ou verifique sua conexão.
)

echo.
pause
