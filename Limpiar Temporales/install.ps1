<#
.SYNOPSIS
    Crea un acceso directo a "Limpiar Temporales" en el Menu Inicio.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).

    Coloca el acceso directo en el Menu Inicio del usuario actual
    (%APPDATA%\Microsoft\Windows\Start Menu\Programs\BSTools). NO requiere
    permisos de administrador. Con -Desktop crea tambien uno en el Escritorio.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -Desktop
#>

[CmdletBinding()]
param(
    [switch]$Desktop
)

$ErrorActionPreference = 'Stop'

$toolDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$target   = Join-Path $toolDir 'LimpiarTemporales.bat'
$linkName = 'Limpiar Temporales.lnk'
$icon     = "$env:SystemRoot\System32\imageres.dll,-54"  # papelera

if (-not (Test-Path $target)) {
    throw "No se encuentra LimpiarTemporales.bat en $toolDir"
}

Write-Host 'Limpiar Temporales - Instalacion' -ForegroundColor Cyan
Write-Host "  Carpeta: $toolDir"

function New-Shortcut {
    param([Parameter(Mandatory)][string]$Path)

    $parent = Split-Path -Parent $Path
    if (-not (Test-Path $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }

    $shell = New-Object -ComObject WScript.Shell
    $lnk = $shell.CreateShortcut($Path)
    $lnk.TargetPath       = $target
    $lnk.WorkingDirectory = $toolDir
    $lnk.IconLocation     = $icon
    $lnk.Description       = 'Vacia las carpetas temporales de Windows (BSTools)'
    $lnk.Save()
    [Runtime.InteropServices.Marshal]::ReleaseComObject($shell) | Out-Null
    Write-Host "  Creado: $Path" -ForegroundColor Green
}

# --- Menu Inicio (siempre) ----------------------------------------------------
$startMenu = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\BSTools\$linkName"
New-Shortcut -Path $startMenu

# --- Escritorio (opcional) ----------------------------------------------------
if ($Desktop) {
    $desktopLnk = Join-Path ([Environment]::GetFolderPath('Desktop')) $linkName
    New-Shortcut -Path $desktopLnk
}

Write-Host ''
Write-Host 'Instalado correctamente.' -ForegroundColor Green
Write-Host "  Busca 'Limpiar Temporales' en el Menu Inicio."
Write-Host ''
Write-Host 'Al abrirlo pedira permisos de administrador para limpiar tambien el' -ForegroundColor DarkGray
Write-Host 'Temp del sistema; si los rechazas, limpiara solo el Temp del usuario.' -ForegroundColor DarkGray
Write-Host 'Para desinstalar: .\uninstall.ps1' -ForegroundColor DarkGray
