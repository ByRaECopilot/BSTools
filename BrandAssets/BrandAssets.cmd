@echo off
setlocal
title BrandAssets - BSTools

rem Doble clic aqui (o en el acceso directo "BrandAssets" que crea install.ps1)
rem para abrir la interfaz web en el navegador. Tambien acepta un PNG como
rem primer argumento, que se carga solo.

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
    echo   BrandAssets ha terminado con error ^(codigo %RC%^).
    pause
)

exit /b %RC%
