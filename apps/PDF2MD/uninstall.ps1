<#
.SYNOPSIS
    Elimina la entrada de PDF2MD del menu contextual del Explorador.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$verbName = 'BSTools.PDF2MD'

$keys = @(
    "HKCU:\Software\Classes\SystemFileAssociations\.pdf\shell\$verbName",
    "HKCU:\Software\Classes\Directory\shell\$verbName"
)

$removed = 0
foreach ($key in $keys) {
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
    Write-Host 'PDF2MD desinstalado del menu contextual.' -ForegroundColor Green
}

Write-Host 'Nota: pymupdf4llm sigue instalado. Para quitarlo: pip uninstall pymupdf4llm' -ForegroundColor DarkGray
