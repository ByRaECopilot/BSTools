<#
.SYNOPSIS
    Instala Voice2Text: dependencias de Python y la entrada "Transcribir con
    Voice2Text" en el menu contextual de los archivos de audio y video.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).

    Escribe en HKCU:\Software\Classes, por lo que NO requiere permisos de
    administrador y solo afecta al usuario actual.

    Esto es la instalacion BASE (CPU). El complemento opcional de aceleracion
    GPU (unos 2 GB mas) se instala aparte con .\install-gpu.ps1 -- este script
    no lo toca.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
#>

[CmdletBinding()]
param(
    [switch]$SkipDependencies
)

$ErrorActionPreference = 'Stop'

$toolDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $toolDir 'Voice2Text.cmd'
$icon     = Join-Path $toolDir 'icon.ico'
$verbName = 'BSTools.VOICE2TEXT'
$label    = 'Transcribir con Voice2Text'

if (-not (Test-Path $launcher)) {
    throw "No se encuentra Voice2Text.cmd en $toolDir"
}
if (-not (Test-Path $icon)) {
    throw "No se encuentra icon.ico en $toolDir"
}

Write-Host 'Voice2Text - Instalacion' -ForegroundColor Cyan
Write-Host "  Carpeta: $toolDir"

# --- 1. Dependencias de Python -------------------------------------------------
# faster-whisper, yt-dlp y pywebview -- listadas y explicadas en requirements.txt.
# Son unos 330 MB de librerias [M-dev]; sumadas al modelo "small" (464 MB, se
# descarga aparte al primer arranque) dan los ~795 MB de base de la herramienta.
if (-not $SkipDependencies) {
    $python = $null
    foreach ($candidate in @('py', 'python')) {
        if (Get-Command $candidate -ErrorAction SilentlyContinue) { $python = $candidate; break }
    }

    if (-not $python) {
        Write-Warning 'Python no encontrado. Instalalo desde https://www.python.org/downloads/'
        Write-Warning 'Continuo con el resto; la herramienta no funcionara hasta que instales Python.'
    }
    else {
        Write-Host '  Instalando dependencias (faster-whisper, yt-dlp, pywebview)...'
        Write-Host '  Son unos 330 MB de descarga; puede tardar varios minutos.' -ForegroundColor DarkGray
        $reqFile = Join-Path $toolDir 'requirements.txt'
        $pipArgs = @('-m', 'pip', 'install', '--quiet', '--upgrade', '-r', $reqFile)
        if ($python -eq 'py') { $pipArgs = @('-3') + $pipArgs }
        & $python @pipArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "Fallo la instalacion. Ejecuta: pip install -r `"$reqFile`""
        }
        else {
            Write-Host '  Dependencias listas.' -ForegroundColor Green
        }
    }
}

# --- 2. Menu contextual sobre archivos de audio y video ------------------------
# PyAV (via faster-whisper) demuxa un abanico amplio de contenedores; esta lista
# cubre los formatos de audio/video mas comunes que un usuario arrastraria aqui.
# Si falta uno, se arregla anadiendolo a esta lista y volviendo a instalar --
# no hace falta tocar codigo.
$audioExtensions = @('.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.opus', '.wma', '.aiff', '.amr')
$videoExtensions = @('.mp4', '.mkv', '.mov', '.avi', '.webm', '.wmv', '.flv', '.m4v', '.mpg', '.mpeg', '.3gp', '.ts')
$extensions = $audioExtensions + $videoExtensions

foreach ($ext in $extensions) {
    $key        = "HKCU:\Software\Classes\SystemFileAssociations\$ext\shell\$verbName"
    $commandKey = Join-Path $key 'command'
    New-Item -Path $commandKey -Force | Out-Null
    Set-ItemProperty -Path $key -Name '(default)' -Value $label
    Set-ItemProperty -Path $key -Name 'Icon'      -Value "$icon,0"
    Set-ItemProperty -Path $commandKey -Name '(default)' -Value "`"$launcher`" `"%1`""
}

Write-Host ''
Write-Host 'Instalado correctamente.' -ForegroundColor Green
Write-Host "  Doble clic en Voice2Text.cmd (dentro de $toolDir) -> abre la ventana vacia"
Write-Host "  Click derecho sobre un archivo de audio o video -> '$label'"
Write-Host "  ($($extensions.Count) extensiones registradas: $($extensions -join ' '))" -ForegroundColor DarkGray
Write-Host ''
Write-Host 'En Windows 11 la opcion aparece dentro de "Mostrar mas opciones" (Shift+F10).' -ForegroundColor DarkGray
Write-Host 'Para desinstalar: .\uninstall.ps1' -ForegroundColor DarkGray
Write-Host 'Para el complemento de GPU (opcional, ~2 GB): .\install-gpu.ps1' -ForegroundColor DarkGray
