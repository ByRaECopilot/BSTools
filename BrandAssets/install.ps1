<#
.SYNOPSIS
    Instala BrandAssets: dependencias, acceso directo con icono en la propia
    carpeta de la herramienta y entrada en el menu contextual para archivos .png.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).

    Escribe en HKCU:\Software\Classes, por lo que NO requiere permisos de
    administrador y solo afecta al usuario actual.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
#>

[CmdletBinding()]
param(
    [switch]$SkipDependencies
)

$ErrorActionPreference = 'Stop'

$toolDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $toolDir 'BrandAssets.cmd'
$verbName = 'BSTools.BrandAssets'
$label    = 'Generar assets de marca (BrandAssets)'
$icon     = "$env:SystemRoot\System32\imageres.dll,-71"

if (-not (Test-Path $launcher)) {
    throw "No se encuentra BrandAssets.cmd en $toolDir"
}

Write-Host 'BrandAssets - Instalacion' -ForegroundColor Cyan
Write-Host "  Carpeta: $toolDir"

# --- 1. Dependencias de Python ------------------------------------------------
if (-not $SkipDependencies) {
    $python = $null
    foreach ($candidate in @('py', 'python')) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) { $python = $candidate; break }
    }

    if (-not $python) {
        Write-Warning 'Python no encontrado. Instalalo desde https://www.python.org/downloads/'
        Write-Warning 'Continuo con el resto; la herramienta no arrancara hasta que instales Python.'
    }
    else {
        Write-Host '  Instalando dependencias (Pillow)...'
        $pipArgs = @('-m', 'pip', 'install', '--quiet', '--upgrade', 'Pillow')
        if ($python -eq 'py') { $pipArgs = @('-3') + $pipArgs }
        & $python @pipArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'Fallo la instalacion de Pillow. Ejecuta: pip install Pillow'
        }
        else {
            Write-Host '  Dependencias listas.' -ForegroundColor Green
        }
    }
}

# --- 2. Acceso directo con icono en la propia carpeta -------------------------
# Un .cmd muestra el icono generico de consola; el .lnk permite darle uno propio
# y arrancar minimizado, para que solo se vea el navegador.
$shortcut = Join-Path $toolDir 'BrandAssets.lnk'
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut($shortcut)
$link.TargetPath       = $launcher
$link.WorkingDirectory = $toolDir
$link.IconLocation     = $icon
$link.WindowStyle      = 7   # minimizado
$link.Description      = 'Genera los iconos e imagenes de marca de una PWA'
$link.Save()
Write-Host "  Acceso directo creado: $shortcut" -ForegroundColor Green

# --- 3. Menu contextual para archivos .png ------------------------------------
$key = "HKCU:\Software\Classes\SystemFileAssociations\.png\shell\$verbName"
$commandKey = Join-Path $key 'command'
New-Item -Path $commandKey -Force | Out-Null
Set-ItemProperty -Path $key -Name '(default)' -Value $label
Set-ItemProperty -Path $key -Name 'Icon'      -Value $icon
Set-ItemProperty -Path $commandKey -Name '(default)' -Value "`"$launcher`" `"%1`""

Write-Host ''
Write-Host 'Instalado correctamente.' -ForegroundColor Green
Write-Host "  Doble clic en 'BrandAssets' (dentro de $toolDir) -> abre la interfaz"
Write-Host "  Click derecho sobre un .png -> '$label'"
Write-Host ''
Write-Host 'En Windows 11 la opcion aparece dentro de "Mostrar mas opciones" (Shift+F10).' -ForegroundColor DarkGray
Write-Host 'Para desinstalar: .\uninstall.ps1' -ForegroundColor DarkGray
