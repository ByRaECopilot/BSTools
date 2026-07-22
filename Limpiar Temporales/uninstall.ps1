<#
.SYNOPSIS
    Elimina los accesos directos de "Limpiar Temporales".

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$linkName = 'Limpiar Temporales.lnk'

$startFolder = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\BSTools'
$targets = @(
    (Join-Path $startFolder $linkName),
    (Join-Path ([Environment]::GetFolderPath('Desktop')) $linkName)
)

$removed = 0
foreach ($path in $targets) {
    if (Test-Path $path) {
        Remove-Item -Path $path -Force
        Write-Host "  Eliminado: $path"
        $removed++
    }
}

# Borrar la carpeta BSTools del Menu Inicio si quedo vacia
if ((Test-Path $startFolder) -and -not (Get-ChildItem $startFolder -Force)) {
    Remove-Item -Path $startFolder -Force
    Write-Host "  Eliminada carpeta vacia: $startFolder"
}

if ($removed -eq 0) {
    Write-Host 'No habia accesos directos que eliminar.' -ForegroundColor Yellow
}
else {
    Write-Host 'Limpiar Temporales desinstalado del Menu Inicio.' -ForegroundColor Green
}
