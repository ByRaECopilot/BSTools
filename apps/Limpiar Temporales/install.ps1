<#
.SYNOPSIS
    Registra "Limpiar Temporales" para que se ejecute al iniciar Windows.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).

    Crea una tarea programada que, al iniciar sesion el usuario, vacia las
    carpetas temporales de forma silenciosa (sin ventana ni confirmacion).

    Por defecto limpia solo el Temp del usuario y NO requiere administrador.
    Con -System registra la tarea con privilegios altos para vaciar tambien
    el Temp del sistema; en ese caso hay que ejecutar este script como
    administrador (una sola vez, en la instalacion).

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install.ps1
    powershell -ExecutionPolicy Bypass -File .\install.ps1 -System
#>

[CmdletBinding()]
param(
    [switch]$System
)

$ErrorActionPreference = 'Stop'

$toolDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat      = Join-Path $toolDir 'LimpiarTemporales.bat'
$taskName = 'BSTools - Limpiar Temporales'

if (-not (Test-Path $bat)) {
    throw "No se encuentra LimpiarTemporales.bat en $toolDir"
}

Write-Host 'Limpiar Temporales - Instalacion' -ForegroundColor Cyan
Write-Host "  Carpeta: $toolDir"

# --- Limpieza de la version anterior (acceso directo en Menu Inicio) ----------
$legacyLinks = @(
    (Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\BSTools\Limpiar Temporales.lnk'),
    (Join-Path ([Environment]::GetFolderPath('Desktop')) 'Limpiar Temporales.lnk')
)
foreach ($link in $legacyLinks) {
    if (Test-Path $link) {
        Remove-Item $link -Force
        Write-Host "  Eliminado acceso directo antiguo: $link" -ForegroundColor DarkGray
    }
}
$legacyFolder = Join-Path $env:APPDATA 'Microsoft\Windows\Start Menu\Programs\BSTools'
if ((Test-Path $legacyFolder) -and -not (Get-ChildItem $legacyFolder -Force)) {
    Remove-Item $legacyFolder -Force
}

# --- Tarea programada al iniciar sesion ---------------------------------------
# Se ejecuta oculta: powershell (sin ventana) lanza el .bat en modo silencioso,
# tambien oculto. Asi no aparece ninguna ventana en el arranque.
$inner    = "Start-Process -WindowStyle Hidden -FilePath '$bat' -ArgumentList '/silent'"
$argument = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"$inner`""

$action  = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argument
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -Hidden `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

$runLevel = if ($System) { 'Highest' } else { 'Limited' }
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel $runLevel

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null

Write-Host ''
Write-Host 'Instalado correctamente.' -ForegroundColor Green
Write-Host "  Tarea: '$taskName'"
Write-Host '  Se ejecutara, en silencio, cada vez que inicies sesion en Windows.'
if ($System) {
    Write-Host '  Modo -System: vaciara tambien el Temp del sistema.' -ForegroundColor Green
}
else {
    Write-Host '  Limpia el Temp del usuario. Para incluir el del sistema, reinstala' -ForegroundColor DarkGray
    Write-Host '  como administrador con:  install.ps1 -System' -ForegroundColor DarkGray
}
Write-Host ''
Write-Host 'Para probarla ahora sin reiniciar:' -ForegroundColor DarkGray
Write-Host "  Start-ScheduledTask -TaskName '$taskName'" -ForegroundColor DarkGray
Write-Host 'Para desinstalar: .\uninstall.ps1' -ForegroundColor DarkGray
