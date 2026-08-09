<#
.SYNOPSIS
    Compila MDViewer.exe a partir de src\MDViewer.cs.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).

    No hay .NET SDK instalado: se usa el compilador de .NET Framework
    (csc.exe) que trae Windows. Embebe assets\viewer.html como recurso del
    ejecutable y enlaza las DLL de WebView2 que viven en lib\.

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

$libDir = Join-Path $toolDir 'lib'
foreach ($dll in 'Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll', 'WebView2Loader.dll') {
    if (-not (Test-Path (Join-Path $libDir $dll))) {
        throw "Falta $dll en $libDir"
    }
}

$viewerHtml = Join-Path $toolDir 'assets\viewer.html'
if (-not (Test-Path $viewerHtml)) {
    throw "No se encuentra $viewerHtml. Es el contrato con el HTML del visor (window.MDV.render); sin el, MDViewer no puede arrancar."
}

$outExe = Join-Path $toolDir 'MDViewer.exe'

$refs = @(
    'System.dll'
    'System.Core.dll'
    'System.Drawing.dll'
    'System.Windows.Forms.dll'
    (Join-Path $libDir 'Microsoft.Web.WebView2.Core.dll')
    (Join-Path $libDir 'Microsoft.Web.WebView2.WinForms.dll')
) -join ','

$cscArgs = @(
    '/nologo'
    '/target:winexe'
    '/platform:x64'
    '/optimize+'
    '/codepage:65001'
    "/out:$outExe"
    "/reference:$refs"
    "/resource:$viewerHtml,MDViewer.Viewer.html"
    $source
)

Write-Host '  Compilando...'
& $csc @cscArgs
$rc = $LASTEXITCODE

if ($rc -ne 0) {
    throw "La compilacion fallo (codigo $rc)."
}

# Las DLL de lib\ solo se usaron como referencia de compilacion: en tiempo
# de ejecucion el CLR busca los ensamblados en la carpeta del exe, no en
# lib\. Hay que copiar las tres junto al exe (las dos administradas y el
# cargador nativo WebView2Loader.dll) o el arranque falla con
# FileNotFoundException al construir la primera ventana.
foreach ($dll in 'Microsoft.Web.WebView2.Core.dll', 'Microsoft.Web.WebView2.WinForms.dll', 'WebView2Loader.dll') {
    Copy-Item -Path (Join-Path $libDir $dll) -Destination $toolDir -Force
}

Write-Host ''
Write-Host "Compilado: $outExe" -ForegroundColor Green
Write-Host '  Copiadas junto al exe: Microsoft.Web.WebView2.Core.dll, Microsoft.Web.WebView2.WinForms.dll, WebView2Loader.dll' -ForegroundColor DarkGray
