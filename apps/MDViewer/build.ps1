<#
.SYNOPSIS
    Compila MDViewer.exe a partir de src\MDViewer.cs.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).

    No hay .NET SDK instalado: se usa el compilador de .NET Framework
    (csc.exe) que trae Windows. Embebe assets\viewer.html como recurso del
    ejecutable y enlaza las DLL de WebView2 que viven junto al exe (tienen que
    estar ahi de todos modos para que el runtime las encuentre al arrancar).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\build.ps1
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$toolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$csc = Join-Path $env:SystemRoot 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'

Write-Host 'MDViewer - Compilacion' -ForegroundColor Cyan
Write-Host "  Carpeta: $toolDir"

if (-not (Test-Path $csc)) {
    throw "No se encuentra csc.exe en $csc. Hace falta .NET Framework 4.x (viene con Windows)."
}
Write-Host "  csc.exe: $csc"

$source = Join-Path $toolDir 'src\MDViewer.cs'
if (-not (Test-Path $source)) {
    throw "No se encuentra $source"
}

foreach ($dll in 'Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll', 'WebView2Loader.dll') {
    if (-not (Test-Path (Join-Path $toolDir $dll))) {
        throw "Falta $dll en $toolDir"
    }
}

$viewerHtml = Join-Path $toolDir 'assets\viewer.html'
if (-not (Test-Path $viewerHtml)) {
    throw "No se encuentra $viewerHtml. Es el contrato con el HTML del visor (window.MDV.render); sin el, MDViewer no puede arrancar."
}

$iconFile = Join-Path $toolDir 'MDViewer.ico'
if (-not (Test-Path $iconFile)) {
    throw "No se encuentra $iconFile. Es el icono de marca (exe, ventana y asociacion .md)."
}

$outExe = Join-Path $toolDir 'MDViewer.exe'

$refs = @(
    'System.dll'
    'System.Core.dll'
    'System.Drawing.dll'
    'System.Windows.Forms.dll'
    (Join-Path $toolDir 'Microsoft.Web.WebView2.Core.dll')
    (Join-Path $toolDir 'Microsoft.Web.WebView2.WinForms.dll')
) -join ','

$cscArgs = @(
    '/nologo'
    '/target:winexe'
    '/platform:x64'
    '/optimize+'
    '/codepage:65001'
    "/out:$outExe"
    "/win32icon:$iconFile"
    "/reference:$refs"
    "/resource:$viewerHtml,MDViewer.Viewer.html"
    "/resource:$iconFile,MDViewer.Icon.ico"
    $source
)

Write-Host '  Compilando...'
& $csc @cscArgs
$rc = $LASTEXITCODE

if ($rc -ne 0) {
    throw "La compilacion fallo (codigo $rc)."
}

Write-Host ''
Write-Host "Compilado: $outExe" -ForegroundColor Green
Write-Host '  DLL de WebView2 ya estaban junto al exe (misma carpeta usada para compilar y ejecutar): no hace falta copiarlas.' -ForegroundColor DarkGray
