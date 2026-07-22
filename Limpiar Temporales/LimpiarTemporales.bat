@echo off
setlocal
title Limpiar Temporales - BSTools

rem --------------------------------------------------------------------------
rem Autoelevacion (una sola vez): intenta obtener permisos de administrador
rem para poder vaciar tambien el Temp del sistema. Si el usuario cancela el
rem UAC, la ejecucion continua y limpia solo el Temp del usuario.
rem --------------------------------------------------------------------------
net session >nul 2>&1
if errorlevel 1 (
    if not "%~1"=="/elevated" (
        powershell -NoProfile -Command "try { Start-Process -FilePath '%~f0' -ArgumentList '/elevated' -Verb RunAs; exit 0 } catch { exit 1 }"
        if not errorlevel 1 exit /b
    )
)

rem --- Saber si finalmente somos administrador (para el mensaje) -------------
set "ES_ADMIN=0"
net session >nul 2>&1
if not errorlevel 1 set "ES_ADMIN=1"

echo ==========================================================
echo   Limpiar Temporales - BSTools
echo ==========================================================
echo.
echo   Se vaciaran las carpetas temporales de Windows:
echo     - Usuario:  %TEMP%
if "%ES_ADMIN%"=="1" (
    echo     - Sistema:  %SystemRoot%\Temp
) else (
    echo     - Sistema:  (omitido, sin permisos de administrador^)
)
echo.

choice /c SN /n /m "  Continuar? (S/N): "
if errorlevel 2 (
    echo.
    echo   Cancelado.
    ping -n 2 127.0.0.1 >nul
    exit /b
)

echo.
echo   Limpiando...

rem --- Temp del usuario -----------------------------------------------------
if defined TEMP (
    del /q /f /s "%TEMP%\*.*" >nul 2>&1
    for /d %%i in ("%TEMP%\*") do rmdir /q /s "%%i" >nul 2>&1
)

rem --- Temp del sistema (solo si somos administrador) ------------------------
if "%ES_ADMIN%"=="1" if defined SystemRoot (
    del /q /f /s "%SystemRoot%\Temp\*.*" >nul 2>&1
    for /d %%i in ("%SystemRoot%\Temp\*") do rmdir /q /s "%%i" >nul 2>&1
)

echo.
echo   Listo.
echo   Los archivos en uso no se pueden borrar y se omiten: es normal.
if "%ES_ADMIN%"=="0" (
    echo   El Temp del sistema no se toco: relanza aceptando el aviso de
    echo   administrador para incluirlo.
)
echo.
pause
endlocal
exit /b
