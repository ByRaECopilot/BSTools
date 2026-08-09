@echo off
setlocal
title PDF2MD - BSTools

rem Lanzador para el menu contextual del Explorador de Windows.
rem Acepta un archivo .pdf o una carpeta como primer argumento.

set "SCRIPT=%~dp0pdf2md.py"

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

if "%~1"=="" (
    echo   Uso: convert.cmd "archivo.pdf" ^| "carpeta"
    pause
    exit /b 1
)

echo   Convirtiendo: %~nx1
echo.
%PY% "%SCRIPT%" "%~1"
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo   La conversion ha fallado ^(codigo %RC%^).
    pause
)

exit /b %RC%
