<#
.SYNOPSIS
    Instala el editor grafico de Mermaid: crea un acceso directo con icono en la
    propia carpeta y anade una entrada al menu contextual de los archivos .mmd.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).

    Escribe en HKCU:\Software\Classes, por lo que NO requiere permisos de
    administrador y solo afecta al usuario actual. El editor corre sobre un
    servidor local en Python (para guardar/cargar diagramas en graphs/).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$toolDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $toolDir 'Mermaid.cmd'
$icon     = Join-Path $toolDir 'icon.ico'
$verbName = 'BSTools.Mermaid'
$label    = 'Abrir con el editor Mermaid'

if (-not (Test-Path $launcher)) {
    throw "No se encuentra Mermaid.cmd en $toolDir"
}

Write-Host 'Mermaid - Instalacion' -ForegroundColor Cyan
Write-Host "  Carpeta: $toolDir"

# --- 1. Aviso de Python -------------------------------------------------------
$python = $null
foreach ($candidate in @('py', 'python')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) { $python = $candidate; break }
}
if (-not $python) {
    Write-Warning 'Python no encontrado. El editor no arrancara hasta que lo instales.'
    Write-Warning 'Descarga: https://www.python.org/downloads/  (marca "Add Python to PATH")'
} else {
    Write-Host "  Python: $python" -ForegroundColor Green
}
Write-Host '  (El editor usa solo la biblioteca estandar; no instala nada.)' -ForegroundColor DarkGray

# --- 2. Acceso directo con icono en la propia carpeta -------------------------
# Apunta al lanzador (arranca el servidor local, minimizado, y abre el navegador).
$shortcut = Join-Path $toolDir 'Mermaid.lnk'
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath       = $launcher
$link.WorkingDirectory = $toolDir
$link.IconLocation     = "$icon,0"
$link.WindowStyle      = 7   # minimizado: la consola del servidor no molesta
$link.Description       = 'Editor grafico de diagramas Mermaid'
$link.Save()
Write-Host "  Acceso directo creado: $shortcut" -ForegroundColor Green

# --- 3. Menu contextual para archivos .mmd ------------------------------------
# Abre el editor con ese .mmd ya cargado (y sus posiciones si hay un .layout.json
# al lado).
$key = "HKCU:\Software\Classes\SystemFileAssociations\.mmd\shell\$verbName"
$commandKey = Join-Path $key 'command'
New-Item -Path $commandKey -Force | Out-Null
Set-ItemProperty -Path $key -Name '(default)' -Value $label
Set-ItemProperty -Path $key -Name 'Icon'      -Value "$icon,0"
Set-ItemProperty -Path $commandKey -Name '(default)' -Value "`"$launcher`" `"%1`""

Write-Host ''
Write-Host 'Instalado correctamente.' -ForegroundColor Green
Write-Host "  Doble clic en 'Mermaid' (dentro de $toolDir) -> abre el editor"
Write-Host "  Click derecho sobre un .mmd -> '$label' (lo abre ya cargado)"
Write-Host "  Los diagramas se guardan en: $toolDir\graphs"
Write-Host ''
Write-Host 'En Windows 11 la opcion aparece dentro de "Mostrar mas opciones" (Shift+F10).' -ForegroundColor DarkGray
Write-Host 'Para desinstalar: .\uninstall.ps1' -ForegroundColor DarkGray
