@echo off
setlocal
title Mermaid - BSTools

rem Arranca el servidor local del editor Mermaid y abre el navegador.
rem Acepta un archivo .mmd como primer argumento (se precarga en el editor).

set "SCRIPT=%~dp0server.py"

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
    echo   El servidor de Mermaid ha terminado con error ^(codigo %RC%^).
    pause
)

exit /b %RC%
