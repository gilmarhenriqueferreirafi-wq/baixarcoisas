@echo off
title Downloader Universal
cd /d "%~dp0"

python verificar_dependencias.py

if errorlevel 1 (
    pause
    exit
)

:menu
cls
echo =====================================
echo        DOWNLOADER UNIVERSAL
echo =====================================
echo.
echo 1 - YouTube
echo 2 - Instagram
echo 3 - Configuracoes
echo 4 - Corrigir audios pendentes (.webm etc)
echo 0 - Sair
echo.

set /p opcao=Escolha: 

if "%opcao%"=="1" (
    python youtube.py
    goto menu
)

if "%opcao%"=="2" (
    python instagram.py
    goto menu
)

if "%opcao%"=="3" (
    python configurar.py
    goto menu
)

if "%opcao%"=="4" (
    python corrigir_audios_pendentes.py
    pause
    goto menu
)

if "%opcao%"=="0" exit

goto menu
