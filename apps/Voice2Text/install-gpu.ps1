<#
.SYNOPSIS
    Instala el complemento OPCIONAL de aceleracion GPU de Voice2Text (ADR-0002).

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).

    NO toca el registro de Windows -- eso lo hace install.ps1 (lote 5). Este
    script solo instala requirements-gpu.txt en el mismo Python que ya usa
    Voice2Text y termina EJECUTANDO la prueba de humo real (`cli.py --self-check`,
    ADR-0002 E8/Sec.6): construir el modelo en GPU sin error NO prueba que
    funcione (medido), asi que este script nunca se declara satisfecho solo
    porque pip no devolvio un error.

    Anade unos 2 GB [M-dev] sobre la instalacion base. Es opcional a proposito
    (ADR-0002 E5): la instalacion base de Voice2Text funciona entera sin esto,
    solo que en CPU. Requiere una GPU NVIDIA con su driver ya instalado -- este
    script no lo instala ni lo comprueba mas alla de lo que la prueba de humo
    descubre por si sola.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\install-gpu.ps1
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$toolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $toolDir

Write-Host 'Voice2Text - complemento de GPU (opcional)' -ForegroundColor Cyan
Write-Host '============================================'
Write-Host ''
Write-Host 'Esto instala unos 2 GB de librerias CUDA (cublas, cudnn, cuda-nvrtc) [M-dev].'
Write-Host 'Acelera la transcripcion entre 5 y 20 veces segun el modelo, con margen sobre'
Write-Host 'el umbral que se exigio para aprobarlo -- la cifra exacta esta pendiente de'
Write-Host 'remedirse en condiciones aisladas (ADR-0002 V8) y no se publica suelta hasta'
Write-Host 'entonces.'
Write-Host ''
Write-Host 'Es opcional: sin esto, Voice2Text funciona entero, solo que en CPU.'
Write-Host 'Necesitas una GPU NVIDIA con su driver ya instalado.'
Write-Host ''

# --- 1. localizar Python (mismo patron que install.ps1, guia-nueva-herramienta.md) ---
$python = $null
foreach ($candidate in @('py', 'python')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) { $python = $candidate; break }
}
if (-not $python) {
    Write-Warning 'Python no encontrado. Instalalo desde https://www.python.org/downloads/'
    exit 1
}

# NOTA para quien toque esto despues: NO envuelvas "& $python ...; return
# $LASTEXITCODE" en una funcion que se asigna con "$x = Mi-Funcion". En
# PowerShell, la salida por consola del proceso hijo (todo lo que imprime pip)
# se cuela en el valor de retorno de la funcion junto al codigo de salida, y
# "$exitCode" deja de ser un numero. Por eso aqui se llama a python DIRECTO,
# sin funcion intermedia, y se lee $LASTEXITCODE justo despues (medido en este
# mismo script: el primer intento tenia justo este bug).

function Get-NvidiaFolderBytes {
    # Mide site-packages/nvidia/ con Python, nunca adivinando la ruta: distintas
    # instalaciones de Python (py launcher, venv, Store) la ponen en sitios
    # distintos. Devuelve 0 si el paquete no esta instalado.
    $code = @'
import importlib.util, pathlib, sys
spec = importlib.util.find_spec("nvidia")
if spec is None or not spec.submodule_search_locations:
    print(0)
    sys.exit(0)
root = pathlib.Path(list(spec.submodule_search_locations)[0])
total = sum(f.stat().st_size for f in root.rglob("*") if f.is_file())
print(total)
'@
    $tmpFile = [System.IO.Path]::GetTempFileName() + '.py'
    Set-Content -Path $tmpFile -Value $code -Encoding UTF8
    if ($python -eq 'py') {
        $result = & py -3 $tmpFile
    }
    else {
        $result = & python $tmpFile
    }
    Remove-Item $tmpFile -ErrorAction SilentlyContinue
    if (-not $result) { return 0 }
    return [int64]($result | Select-Object -Last 1)
}

# --- 2. instalar, midiendo antes y despues para reportar el peso real ---
$bytesBefore = Get-NvidiaFolderBytes

Write-Host 'Instalando requirements-gpu.txt (varios minutos; son unos 2 GB de descarga)...'
Write-Host ''
$reqFile = Join-Path $toolDir 'requirements-gpu.txt'
if ($python -eq 'py') {
    & py -3 -m pip install -r $reqFile
}
else {
    & python -m pip install -r $reqFile
}
$exitCode = $LASTEXITCODE
if ($exitCode -ne 0) {
    Write-Host ''
    Write-Warning "pip devolvio el codigo $exitCode. Revisa el mensaje de arriba."
    Write-Warning 'Voice2Text sigue funcionando en CPU: esta instalacion no toco nada mas.'
    exit 1
}

$bytesAfter = Get-NvidiaFolderBytes
$mbTotal = [math]::Round($bytesAfter / 1MB, 0)
$mbNew = [math]::Round(($bytesAfter - $bytesBefore) / 1MB, 0)

Write-Host ''
Write-Host "Instalado. site-packages\nvidia ocupa ahora $mbTotal MB en disco ($mbNew MB nuevos)." -ForegroundColor Green
Write-Host ''

# --- 3. la parte que de verdad importa: la prueba de humo real ---
Write-Host 'Ejecutando la prueba de humo (una inferencia real en GPU, no solo construir' -ForegroundColor Cyan
Write-Host 'el modelo -- construir sin error NO prueba que la GPU funcione, medido en el' -ForegroundColor Cyan
Write-Host 'spike de este proyecto)...' -ForegroundColor Cyan
Write-Host ''

$cliFile = Join-Path $toolDir 'cli.py'
if ($python -eq 'py') {
    & py -3 $cliFile --self-check
}
else {
    & python $cliFile --self-check
}
$smokeExit = $LASTEXITCODE

Write-Host ''
if ($smokeExit -eq 0) {
    Write-Host 'RESULTADO: GPU confirmada y funcionando.' -ForegroundColor Green
    Write-Host 'Voice2Text la usara sola en el modo por defecto (auto). Nada mas que hacer.'
}
else {
    Write-Host 'RESULTADO: las librerias se instalaron pero la prueba de humo NO confirmo' -ForegroundColor Yellow
    Write-Host 'la GPU. Voice2Text seguira funcionando -- en CPU. El motivo exacto esta en' -ForegroundColor Yellow
    Write-Host 'la linea "RESULTADO" de arriba; segun cual sea:' -ForegroundColor Yellow
    Write-Host ''
    Write-Host '  gpu_libraries_missing  -> falta una DLL o la instalacion quedo a medias.'
    Write-Host '                            Vuelve a ejecutar este script.'
    Write-Host '  gpu_out_of_memory      -> no hay VRAM suficiente para el modelo de prueba'
    Write-Host '                            en esta GPU. Prueba con un modelo mas pequeno.'
    Write-Host '  gpu_unavailable        -> otro fallo de CUDA. Revisa que el driver NVIDIA'
    Write-Host '                            este instalado y actualizado.'
    Write-Host ''
    Write-Host 'Para quitar el complemento de GPU: .\uninstall-gpu.ps1'
}
Write-Host ''

exit $smokeExit
