<#
.SYNOPSIS
    Desinstala el complemento OPCIONAL de aceleracion GPU de Voice2Text (ADR-0002).

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).

    Revierte EXACTAMENTE lo que instala install-gpu.ps1: los tres paquetes de
    CUDA (nvidia-cublas-cu12, nvidia-cudnn-cu12, nvidia-cuda-nvrtc-cu12).

    NUNCA desinstala `ctranslate2`: ese paquete lo necesita la instalacion BASE
    de Voice2Text para funcionar en CPU (lo trae faster-whisper, obligatorio).
    Quitarlo dejaria la herramienta entera rota, no solo sin GPU -- el pin de la
    version en requirements-gpu.txt (ADR-0002 E6) es para emparejarlo con cuDNN,
    no para hacerlo exclusivo del camino GPU.

    No toca el registro de Windows: install-gpu.ps1 tampoco lo toca.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\uninstall-gpu.ps1
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$toolDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host 'Voice2Text - quitar el complemento de GPU' -ForegroundColor Cyan
Write-Host '============================================'
Write-Host ''

$python = $null
foreach ($candidate in @('py', 'python')) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) { $python = $candidate; break }
}
if (-not $python) {
    Write-Warning 'Python no encontrado. No hay nada que este script pueda hacer.'
    exit 1
}

# NOTA (mismo hallazgo que install-gpu.ps1): NO se envuelve "& $python ...;
# return $LASTEXITCODE" en una funcion asignada con "$x = ...". La salida de
# pip se cuela en el valor de retorno junto al codigo de salida. Se llama a
# python directo y se lee $LASTEXITCODE justo despues.

function Get-NvidiaFolderBytes {
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

$bytesBefore = Get-NvidiaFolderBytes
if ($bytesBefore -eq 0) {
    Write-Host 'El complemento de GPU no parece estar instalado (no hay carpeta'
    Write-Host 'site-packages\nvidia). Nada que desinstalar.'
    exit 0
}

$mbBefore = [math]::Round($bytesBefore / 1MB, 0)
Write-Host "Quitando nvidia-cublas-cu12, nvidia-cudnn-cu12 y nvidia-cuda-nvrtc-cu12"
Write-Host "(unos $mbBefore MB en disco ahora mismo)..."
Write-Host ''

if ($python -eq 'py') {
    & py -3 -m pip uninstall -y nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-nvrtc-cu12
}
else {
    & python -m pip uninstall -y nvidia-cublas-cu12 nvidia-cudnn-cu12 nvidia-cuda-nvrtc-cu12
}
$exitCode = $LASTEXITCODE

$bytesAfter = Get-NvidiaFolderBytes
$mbFreed = [math]::Round(($bytesBefore - $bytesAfter) / 1MB, 0)

Write-Host ''
if ($exitCode -ne 0) {
    Write-Warning "pip devolvio el codigo $exitCode al desinstalar. Revisa el mensaje de arriba."
}
if ($bytesAfter -gt 0) {
    $mbLeft = [math]::Round($bytesAfter / 1MB, 0)
    Write-Warning "Quedan $mbLeft MB en site-packages\nvidia. Puede que algun paquete no se"
    Write-Warning 'haya podido quitar (revisa el mensaje de pip de arriba).'
}
else {
    Write-Host "Liberados aproximadamente $mbFreed MB." -ForegroundColor Green
}
Write-Host ''
Write-Host 'ctranslate2 NO se toca: lo sigue necesitando la instalacion base, en CPU.'
Write-Host 'Voice2Text sigue funcionando -- se ha quedado en modo CPU.'
Write-Host ''

exit 0
