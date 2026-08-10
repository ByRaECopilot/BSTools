<#
.SYNOPSIS
    Elimina la entrada "Transcribir con Voice2Text" del menu contextual del
    Explorador (todas las extensiones registradas por install.ps1).

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).

    Solo revierte el registro. NO borra tus modelos descargados (models/), tus
    transcripciones, ni desinstala los paquetes de Python -- son datos y
    dependencias que puede que sigas usando desde la linea de comandos
    (cli.py) o el modo servidor.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$verbName = 'BSTools.VOICE2TEXT'
$removed  = 0

# Misma lista de extensiones que registra install.ps1.
$audioExtensions = @('.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg', '.opus', '.wma', '.aiff', '.amr')
$videoExtensions = @('.mp4', '.mkv', '.mov', '.avi', '.webm', '.wmv', '.flv', '.m4v', '.mpg', '.mpeg', '.3gp', '.ts')
$extensions = $audioExtensions + $videoExtensions

foreach ($ext in $extensions) {
    $key = "HKCU:\Software\Classes\SystemFileAssociations\$ext\shell\$verbName"
    if (Test-Path $key) {
        Remove-Item -Path $key -Recurse -Force
        Write-Host "  Eliminado: $key"
        $removed++
    }
}

if ($removed -eq 0) {
    Write-Host 'No habia nada que desinstalar.' -ForegroundColor Yellow
}
else {
    Write-Host "Voice2Text desinstalado ($removed entradas de menu eliminadas)." -ForegroundColor Green
}

Write-Host ''
Write-Host 'Lo que NO se ha tocado:' -ForegroundColor DarkGray
Write-Host '  - Tus modelos descargados en models\ (borra esa carpeta a mano si quieres liberar el espacio)' -ForegroundColor DarkGray
Write-Host '  - Tus transcripciones .txt/.md ya generadas' -ForegroundColor DarkGray
Write-Host '  - Los paquetes de Python (faster-whisper, yt-dlp, pywebview, y el complemento de GPU si lo instalaste)' -ForegroundColor DarkGray
Write-Host '    Para quitarlos: pip uninstall faster-whisper yt-dlp pywebview' -ForegroundColor DarkGray
