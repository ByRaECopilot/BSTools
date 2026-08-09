<#
.SYNOPSIS
    Elimina el acceso directo de Mermaid y su entrada del menu contextual.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$toolDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$verbName = 'BSTools.Mermaid'
$removed  = 0

$key = "HKCU:\Software\Classes\SystemFileAssociations\.mmd\shell\$verbName"
if (Test-Path $key) {
    Remove-Item -Path $key -Recurse -Force
    Write-Host "  Eliminado: $key"
    $removed++
}

$shortcut = Join-Path $toolDir 'Mermaid.lnk'
if (Test-Path $shortcut) {
    Remove-Item -Path $shortcut -Force
    Write-Host "  Eliminado: $shortcut"
    $removed++
}

if ($removed -eq 0) {
    Write-Host 'No habia nada que desinstalar.' -ForegroundColor Yellow
}
else {
    Write-Host 'Mermaid desinstalado.' -ForegroundColor Green
}

Write-Host 'Tus diagramas en la carpeta graphs\ no se tocan.' -ForegroundColor DarkGray
