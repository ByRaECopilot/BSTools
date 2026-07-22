<#
.SYNOPSIS
    Desregistra la tarea de arranque de "Limpiar Temporales".

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$taskName = 'BSTools - Limpiar Temporales'

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
    Write-Host "  Eliminada la tarea: '$taskName'"
    $removed = $true
}

# Limpieza de accesos directos de versiones anteriores, por si quedaron
$legacyLinks = @(
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\BSTools\Limpiar Temporales.lnk'),
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Limpiar Temporales.lnk')
)
foreach ($link in $legacyLinks) {
    if (Test-Path $link) {
        Remove-Item $link -Force
        Write-Host "  Eliminado acceso directo antiguo: $link"
        $removed = $true
    }
}
$legacyFolder = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\BSTools'
if ((Test-Path $legacyFolder) -and -not (Get-ChildItem $legacyFolder -Force)) {
    Remove-Item $legacyFolder -Force
}

if ($removed) {
    Write-Host 'Limpiar Temporales desinstalado del arranque.' -ForegroundColor Green
}
else {
    Write-Host 'No habia nada que desinstalar.' -ForegroundColor Yellow
}
