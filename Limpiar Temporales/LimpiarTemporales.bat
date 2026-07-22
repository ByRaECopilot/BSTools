@echo off
setlocal
title Limpiar Temporales - BSTools

echo Limpiando archivos temporales...
echo.

rem --- Temp del usuario -----------------------------------------------------
if defined TEMP (
    echo   Usuario:  %TEMP%
    del /q /f /s "%TEMP%\*.*" >nul 2>&1
    for /d %%i in ("%TEMP%\*") do rmdir /q /s "%%i" >nul 2>&1
)

rem --- Temp del sistema (requiere permisos de administrador) -----------------
if defined SystemRoot (
    echo   Sistema:  %SystemRoot%\Temp
    del /q /f /s "%SystemRoot%\Temp\*.*" >nul 2>&1
    for /d %%i in ("%SystemRoot%\Temp\*") do rmdir /q /s "%%i" >nul 2>&1
)

echo.
echo Listo.
echo Los archivos en uso no se pueden borrar y se omiten: es normal.
echo Para limpiar tambien el Temp del sistema, ejecuta este .bat como
echo administrador (click derecho ^> Ejecutar como administrador).
echo.
pause
endlocal
exit /b
