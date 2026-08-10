@echo off
setlocal
title Voice2Text - BSTools

rem Lanzador del modo ventana (ARCHITECTURE.md Sec.6.1). Acepta como primer
rem parametro la ruta de un archivo de audio/video: si llega, la ventana
rem arranca con el origen ya rellenado (nunca transcribe solo, UI-SPEC.md Sec.6).
rem
rem La consola se deja visible a proposito (ARCHITECTURE.md Sec.7.1.3): es la
rem red de seguridad si WebView2 se queda pillado durante una descarga larga.

set "SCRIPT=%~dp0app.py"

rem --- Localizar Python -----------------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo.
    echo   No se ha encontrado Python en el sistema.
    echo   Instalalo desde https://www.python.org/downloads/
    echo   ^(marca "Add Python to PATH" durante la instalacion^)
    echo.
    pause
    exit /b 9009
)

%PY% "%SCRIPT%" %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo   Voice2Text ha terminado con error ^(codigo %RC%^).
    pause
)

exit /b %RC%
