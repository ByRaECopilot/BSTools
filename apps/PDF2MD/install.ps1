<#
.SYNOPSIS
    Instala la entrada "Convertir a Markdown (Claude)" en el menu contextual
    del Explorador de Windows para archivos .pdf y para carpetas.

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
$launcher = Join-Path $toolDir 'convert.cmd'
$verbName = 'BSTools.PDF2MD'
$label    = 'Convertir a Markdown (Claude)'
$icon     = "$env:SystemRoot\System32\imageres.dll,-102"

if (-not (Test-Path $launcher)) {
    throw "No se encuentra convert.cmd en $toolDir"
}

Write-Host "PDF2MD - Instalacion" -ForegroundColor Cyan
Write-Host "  Carpeta: $toolDir"

# --- 1. Dependencias de Python ------------------------------------------------
if (-not $SkipDependencies) {
    $python = $null
    foreach ($candidate in @('py', 'python')) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) { $python = $candidate; break }
    }

    if (-not $python) {
        Write-Warning 'Python no encontrado. Instalalo desde https://www.python.org/downloads/'
        Write-Warning 'Continuo con el registro; la conversion fallara hasta que instales Python.'
    }
    else {
        Write-Host '  Instalando dependencias (pymupdf4llm)...'
        $pipArgs = @('-m', 'pip', 'install', '--quiet', '--upgrade', 'pymupdf4llm')
        if ($python -eq 'py') { $pipArgs = @('-3') + $pipArgs }
        & $python @pipArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'Fallo la instalacion de pymupdf4llm. Ejecuta: pip install pymupdf4llm'
        }
        else {
            Write-Host '  Dependencias listas.' -ForegroundColor Green
        }
    }
}

# --- 2. Registro --------------------------------------------------------------
function Set-ContextMenuEntry {
    param(
        [Parameter(Mandatory)][string]$KeyPath,
        [Parameter(Mandatory)][string]$Command
    )

    $commandPath = Join-Path $KeyPath 'command'
    New-Item -Path $commandPath -Force | Out-Null

    Set-ItemProperty -Path $KeyPath -Name '(default)' -Value $label
    Set-ItemProperty -Path $KeyPath -Name 'Icon'      -Value $icon
    Set-ItemProperty -Path $commandPath -Name '(default)' -Value $Command
}

$fileKey   = "HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\$verbName"
$folderKey = "HKCU:\Software\Classes\Directory\shell\$verbName"

Set-ContextMenuEntry -KeyPath $fileKey   -Command "`"$launcher`" `"%1`""
Set-ContextMenuEntry -KeyPath $folderKey -Command "`"$launcher`" `"%V`""

# --- 3. Limpieza de la entrada antigua "ConvertMD" (versiones previas) --------
$legacy = 'HKLM:\SOFTWARE\Classes\SystemFileAssociations\.pdf\shell\ConvertMD'
if (Test-Path $legacy) {
    try {
        Remove-Item -Path $legacy -Recurse -Force
        Write-Host '  Eliminada la entrada antigua "ConvertMD".'
    }
    catch {
        Write-Warning "Existe una entrada antigua en $legacy"
        Write-Warning 'Para quitarla, ejecuta este script como administrador.'
    }
}

Write-Host ''
Write-Host 'Instalado correctamente.' -ForegroundColor Green
Write-Host "  Click derecho sobre un PDF  -> '$label'"
Write-Host "  Click derecho sobre carpeta -> convierte todos sus PDF"
Write-Host ''
Write-Host 'En Windows 11 la opcion aparece dentro de "Mostrar mas opciones" (Shift+F10).' -ForegroundColor DarkGray
Write-Host 'Para desinstalar: .\uninstall.ps1' -ForegroundColor DarkGray
