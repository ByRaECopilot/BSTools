@echo off
setlocal
title Voice2Text - Modo servidor - BSTools

rem Lanzador del modo servidor (ARCHITECTURE.md Sec.6.2, ADR-0001 D18/D24).
rem Arranque MANUAL y explicito, en primer plano: nada de servicio, tarea
rem programada ni arranque con la sesion de Windows. Cerrar esta ventana o
rem pulsar Ctrl+C apaga el servidor y cancela el trabajo en curso.
rem
rem Uso:  Voice2Text-Servidor.cmd [--port 8317]

set "SCRIPT=%~dp0serve.py"

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
    echo   El servidor de Voice2Text termino con codigo %RC%.
    pause
)

exit /b %RC%
