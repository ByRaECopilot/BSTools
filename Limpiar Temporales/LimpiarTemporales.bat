@echo off
setlocal
title Limpiar Temporales - BSTools

rem --------------------------------------------------------------------------
rem  Borra directamente las carpetas temporales de Windows. Sin confirmacion.
rem
rem  /silent : sin texto ni pausa. Lo usa la tarea programada del arranque.
rem
rem  Vacia siempre el Temp del usuario (%TEMP%). El Temp del sistema
rem  (%SystemRoot%\Temp) solo se toca si el proceso corre como administrador
rem  (p. ej. la tarea instalada con -System, o al ejecutar el .bat como admin).
rem --------------------------------------------------------------------------

set "SILENT=0"
if /i "%~1"=="/silent" set "SILENT=1"

set "ES_ADMIN=0"
net session >nul 2>&1
if not errorlevel 1 set "ES_ADMIN=1"

if "%SILENT%"=="0" (
    echo Limpiando archivos temporales...
    echo   Usuario:  %TEMP%
    if "%ES_ADMIN%"=="1" echo   Sistema:  %SystemRoot%\Temp
)

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

if "%SILENT%"=="0" (
    echo.
    echo Listo. Los archivos en uso se omiten: es normal.
    pause
)

endlocal
exit /b
