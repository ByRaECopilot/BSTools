@echo off
setlocal
title Mermaid - BSTools

rem Abre el editor grafico de Mermaid en el navegador por defecto.
rem Es una aplicacion de una sola pagina: no necesita Python ni servidor,
rem se abre directamente el archivo local.

start "" "%~dp0index.html"
exit /b 0
