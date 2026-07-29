<#
.SYNOPSIS
    Instala el editor grafico de Mermaid: crea un acceso directo con icono en la
    propia carpeta y anade una entrada al menu contextual de los archivos .mmd.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).

    Escribe en HKCU:\Software\Classes, por lo que NO requiere permisos de
    administrador y solo afecta al usuario actual. El editor es una aplicacion
    web de una sola pagina: no necesita Python ni servidor.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$toolDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$page     = Join-Path $toolDir 'index.html'
$icon     = Join-Path $toolDir 'icon.ico'
$verbName = 'BSTools.Mermaid'
$label    = 'Abrir con el editor Mermaid'

if (-not (Test-Path $page)) {
    throw "No se encuentra index.html en $toolDir"
}

Write-Host 'Mermaid - Instalacion' -ForegroundColor Cyan
Write-Host "  Carpeta: $toolDir"

# --- 1. Acceso directo con icono en la propia carpeta -------------------------
# Apunta directamente al index.html: al abrirlo no aparece ninguna ventana de
# consola, solo el navegador. El icono propio lo hace reconocible.
$shortcut = Join-Path $toolDir 'Mermaid.lnk'
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath       = $page
$link.WorkingDirectory = $toolDir
$link.IconLocation     = "$icon,0"
$link.Description       = 'Editor grafico de diagramas Mermaid'
$link.Save()
Write-Host "  Acceso directo creado: $shortcut" -ForegroundColor Green

# --- 2. Menu contextual para archivos .mmd ------------------------------------
# Abre el editor (con el navegador). El editor no importa el .mmd todavia, pero
# deja a mano la herramienta desde cualquier diagrama guardado.
$launcher = Join-Path $toolDir 'Mermaid.cmd'
$key = "HKCU:\Software\Classes\SystemFileAssociations\.mmd\shell\$verbName"
$commandKey = Join-Path $key 'command'
New-Item -Path $commandKey -Force | Out-Null
Set-ItemProperty -Path $key -Name '(default)' -Value $label
Set-ItemProperty -Path $key -Name 'Icon'      -Value "$icon,0"
Set-ItemProperty -Path $commandKey -Name '(default)' -Value "`"$launcher`""

Write-Host ''
Write-Host 'Instalado correctamente.' -ForegroundColor Green
Write-Host "  Doble clic en 'Mermaid' (dentro de $toolDir) -> abre el editor"
Write-Host "  Click derecho sobre un .mmd -> '$label'"
Write-Host ''
Write-Host 'En Windows 11 la opcion aparece dentro de "Mostrar mas opciones" (Shift+F10).' -ForegroundColor DarkGray
Write-Host 'Para desinstalar: .\uninstall.ps1' -ForegroundColor DarkGray
