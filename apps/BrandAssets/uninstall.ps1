<#
.SYNOPSIS
    Elimina la entrada de BrandAssets del menu contextual y el acceso directo.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$toolDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$verbName = 'BSTools.BrandAssets'
$removed  = 0

$key = "HKCU:\Software\Classes\SystemFileAssociations\.png\shell\$verbName"
if (Test-Path $key) {
    Remove-Item -Path $key -Recurse -Force
    Write-Host "  Eliminado: $key"
    $removed++
}

$shortcut = Join-Path $toolDir 'BrandAssets.lnk'
if (Test-Path $shortcut) {
    Remove-Item -Path $shortcut -Force
    Write-Host "  Eliminado: $shortcut"
    $removed++
}

if ($removed -eq 0) {
    Write-Host 'No habia nada que desinstalar.' -ForegroundColor Yellow
}
else {
    Write-Host 'BrandAssets desinstalado.' -ForegroundColor Green
}

Write-Host 'Nota: Pillow sigue instalado. Para quitarlo: pip uninstall Pillow' -ForegroundColor DarkGray
Write-Host 'Los assets ya exportados no se tocan.' -ForegroundColor DarkGray
