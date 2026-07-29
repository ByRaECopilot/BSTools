# SPEC — Especificación de una herramienta de BSTools

Hoja de referencia para crear una herramienta nueva **sin tener que abrir
ninguna de las existentes**. Todo lo que hay aquí es copiable tal cual.

- Convenciones de trabajo y trampas del entorno: [CLAUDE.md](CLAUDE.md)
- Estado del proyecto: [STATUS.md](STATUS.md) · Histórico: [CHANGELOG.md](CHANGELOG.md)

---

## 1. La regla de oro

Una herramienta es una **carpeta autocontenida**. Alguien tiene que poder copiar
solo esa carpeta a otro equipo, ejecutar `install.ps1` y que funcione. Si tu
herramienta necesita algo que vive fuera de su carpeta, está mal diseñada.

---

## 2. Archivos de la carpeta

```
NombreHerramienta/
├── install.ps1            obligatorio si hay algo que registrar o instalar
├── uninstall.ps1          obligatorio si existe install.ps1 — revierte TODO
├── NombreHerramienta.cmd  lanzador: puente entre Windows y el script
├── script.py              la lógica (o .bat/.ps1 si no hace falta Python)
├── requirements.txt       solo si hay dependencias de Python
├── .gitignore             solo si el uso genera archivos locales
└── README.md              obligatorio siempre
```

**Nombres.** El lanzador se llama `<NombreHerramienta>.cmd` (así el acceso
directo y el icono del Explorador se leen solos). Las herramientas anteriores a
esta regla conservan su nombre: PDF2MD usa `convert.cmd`. No las renombres, se
romperían los registros ya instalados.

**Versión.** Cada carpeta lleva su propia versión semántica, declarada en
`STATUS.md` y en `CHANGELOG.md`. No hay versión global del repositorio.

---

## 3. Los cuatro patrones de arranque

Elige uno antes de escribir nada. Determina qué hace `install.ps1`.

| Patrón | Cuándo | Referencia |
|---|---|---|
| **Menú contextual** | La acción se aplica a un archivo o carpeta concretos | PDF2MD |
| **Tarea programada** | Se ejecuta sola, sin que el usuario la invoque | Limpiar Temporales |
| **Interfaz web local** | Hace falta un formulario o UI **y** el servidor toca el disco / procesa | BrandAssets, Mermaid |
| **Cliente puro** | UI visual que se resuelve entera en el navegador, sin tocar el disco desde el servidor | (sin ejemplo actual) |

Se pueden combinar: BrandAssets tiene interfaz web **y** entrada de menú
contextual en los `.png` que la abre con la imagen ya cargada; Mermaid tiene
acceso directo **y** entrada de menú contextual en los `.mmd` que abre el archivo
ya cargado.

**Web local vs. cliente puro.** Si el navegador necesita que un proceso escriba
archivos, ejecute algo o procese imágenes, hace falta el servidor local (patrón
*Interfaz web local*: `http.server` en `127.0.0.1` + token). Si todo —incluida
la exportación, vía descargas del navegador— se resuelve en el propio HTML,
puedes ahorrarte el servidor: el lanzador hace `start index.html` y el acceso
directo apunta directo al HTML (cero ventanas de consola). Empaqueta cualquier
librería en `vendor/` para no depender de la red.

**Aviso por experiencia (Mermaid):** el cliente puro es tentador por lo ligero,
pero en cuanto pidas *guardar en una carpeta del proyecto* topas con que
`file://` no puede escribir en disco (ni la File System Access API funciona ahí).
Si intuyes que la herramienta acabará guardando/cargando archivos, arranca ya con
servidor local: migrar de cliente puro a servidor a mitad de camino cuesta más
que empezar bien. Mermaid nació cliente puro y tuvo que migrar en la v1.3.0.

Lo que **no** hacemos: instaladores binarios, servicios en segundo plano,
entradas en el arranque que no sean una tarea programada visible, ni
dependencias de gigabytes.

---

## 4. Contrato con Windows

### Registro

Siempre en `HKCU:\Software\Classes`. Nunca `HKLM` ni `HKCR`: así no hace falta
administrador y el usuario puede desinstalar sin fricción.

| Objetivo del click derecho | Clave |
|---|---|
| Archivos de una extensión | `HKCU:\Software\Classes\SystemFileAssociations\.EXT\shell\<verbo>` |
| Carpeta (click sobre ella) | `HKCU:\Software\Classes\Directory\shell\<verbo>` |
| Fondo de una carpeta abierta | `HKCU:\Software\Classes\Directory\Background\shell\<verbo>` |

- **Verbo**: `BSTools.<NOMBRE>` — siempre. Hace que las entradas se puedan
  encontrar y borrar de un vistazo en `regedit`.
- Valor `(default)` de la clave = texto del menú. Valor `Icon` = icono.
- Valor `(default)` de la subclave `command` = `"<ruta absoluta al .cmd>" "%1"`.
- Argumento: `%1` para archivo, `%V` para carpeta.

### Iconos

`"$env:SystemRoot\System32\imageres.dll,-NNN"`. En uso ahora mismo: `-102`
(documento, PDF2MD) y `-71` (imágenes, BrandAssets). Alternativa: un `.ico`
propio en la carpeta (Mermaid genera el suyo con Pillow en tiempo de desarrollo
y lo referencia como `icon.ico,0`). Para elegir un índice de `imageres.dll`, abre
`imageres.dll` o `shell32.dll` con cualquier visor de recursos; **verifica** que
el índice se ve como esperas antes de dejarlo escrito.

### Rutas

`install.ps1` deduce su propia ubicación y escribe **rutas absolutas** en el
registro:

```powershell
$toolDir = Split-Path -Parent $MyInvocation.MyCommand.Path
```

Nunca escribas una ruta a mano: rompe el repositorio para quien se lo descargue.
Consecuencia que debe constar en el README: **si el usuario mueve la carpeta,
tiene que reejecutar `install.ps1`**.

---

## 5. Reglas de código

**Idioma.** Todo lo que ve el usuario (README, mensajes de consola, interfaz) en
español.

**Acentos.** Los `.cmd`, y la salida por consola de `.ps1` y `.py`, van **sin
acentos ni caracteres no ASCII**: la codepage de la consola de Windows los
destroza. Los `.md` y el HTML sí llevan acentos normales.

**Errores.** El lanzador `.cmd` solo hace `pause` **si algo falla**. Si todo va
bien, la ventana se cierra sola.

**Dependencias.** Doble red: `install.ps1` las instala, y el script comprueba en
el arranque que están y avisa con el comando exacto si faltan. Alguien usará el
script sin pasar por el instalador.

**Legibilidad antes que magia.** El usuario tiene que poder abrir el archivo,
entenderlo y borrarlo.

---

## 6. Plantillas

### `NombreHerramienta.cmd`

```bat
@echo off
setlocal
title NOMBRE - BSTools

rem Lanzador para el Explorador de Windows. Acepta ARGUMENTO como primer parametro.

set "SCRIPT=%~dp0script.py"

rem --- Localizar Python -----------------------------------------------------
set "PY="
where py >nul 2>&1 && set "PY=py -3"
if not defined PY (
    where python >nul 2>&1 && set "PY=python"
)
if not defined PY (
    echo.
    echo   No se ha encontrado Python en el sistema.
    echo   Instalalo desde https://www.python.org/downloads/
    echo   ^(marca "Add Python to PATH" durante la instalacion^)
    echo.
    pause
    exit /b 9009
)

%PY% "%SCRIPT%" %*
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
    echo.
    echo   NOMBRE ha terminado con error ^(codigo %RC%^).
    pause
)

exit /b %RC%
```

`%~dp0` incluye la barra final y sobrevive a las rutas con espacios: no le
añadas otra. Pasa `%*` si quieres que el lanzador acepte varios argumentos.

### `install.ps1`

```powershell
<#
.SYNOPSIS
    Instala la entrada "TEXTO DEL MENU" en el menu contextual del Explorador.

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
$launcher = Join-Path $toolDir 'NombreHerramienta.cmd'
$verbName = 'BSTools.NOMBRE'
$label    = 'TEXTO DEL MENU'
$icon     = "$env:SystemRoot\System32\imageres.dll,-102"

if (-not (Test-Path $launcher)) {
    throw "No se encuentra NombreHerramienta.cmd en $toolDir"
}

Write-Host 'NOMBRE - Instalacion' -ForegroundColor Cyan
Write-Host "  Carpeta: $toolDir"

# --- 1. Dependencias de Python ------------------------------------------------
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
        Write-Host '  Instalando dependencias (PAQUETE)...'
        $pipArgs = @('-m', 'pip', 'install', '--quiet', '--upgrade', 'PAQUETE')
        if ($python -eq 'py') { $pipArgs = @('-3') + $pipArgs }
        & $python @pipArgs
        if ($LASTEXITCODE -ne 0) {
            Write-Warning 'Fallo la instalacion. Ejecuta: pip install PAQUETE'
        }
        else {
            Write-Host '  Dependencias listas.' -ForegroundColor Green
        }
    }
}

# --- 2. Registro --------------------------------------------------------------
$key        = "HKCU:\Software\Classes\SystemFileAssociations\.EXT\shell\$verbName"
$commandKey = Join-Path $key 'command'
New-Item -Path $commandKey -Force | Out-Null
Set-ItemProperty -Path $key -Name '(default)' -Value $label
Set-ItemProperty -Path $key -Name 'Icon'      -Value $icon
Set-ItemProperty -Path $commandKey -Name '(default)' -Value "`"$launcher`" `"%1`""

Write-Host ''
Write-Host 'Instalado correctamente.' -ForegroundColor Green
Write-Host "  Click derecho sobre un .EXT -> '$label'"
Write-Host ''
Write-Host 'En Windows 11 la opcion aparece dentro de "Mostrar mas opciones" (Shift+F10).' -ForegroundColor DarkGray
Write-Host 'Para desinstalar: .\uninstall.ps1' -ForegroundColor DarkGray
```

### `uninstall.ps1`

```powershell
<#
.SYNOPSIS
    Elimina la entrada de NOMBRE del menu contextual del Explorador.

.DESCRIPTION
    Parte de BSTools - https://www.byraesoftware.com
    Licencia CC0 1.0 (dominio publico).
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$verbName = 'BSTools.NOMBRE'
$removed  = 0

$keys = @(
    "HKCU:\Software\Classes\SystemFileAssociations\.EXT\shell\$verbName"
)

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
    Write-Host 'NOMBRE desinstalado.' -ForegroundColor Green
}

Write-Host 'Nota: PAQUETE sigue instalado. Para quitarlo: pip uninstall PAQUETE' -ForegroundColor DarkGray
```

`uninstall.ps1` debe deshacer **todo** lo que crea `install.ps1`: claves del
registro, accesos directos, tareas programadas. Los datos del usuario (archivos
ya generados) no se tocan, y se dice.

### Fragmentos de los otros patrones

**Acceso directo con icono propio** (un `.cmd` muestra el icono genérico de
consola; el `.lnk` permite darle uno y arrancar minimizado):

```powershell
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $toolDir 'NOMBRE.lnk'))
$link.TargetPath       = $launcher
$link.WorkingDirectory = $toolDir
$link.IconLocation     = $icon
$link.WindowStyle      = 7   # 1 normal, 3 maximizado, 7 minimizado
$link.Description      = 'Descripcion que sale en el tooltip'
$link.Save()
```

El `.lnk` lleva rutas absolutas: va al `.gitignore`, no al repositorio.

**Cliente puro** (patrón sin Python ni servidor). El lanzador entero:

```bat
@echo off
setlocal
title NOMBRE - BSTools
rem Aplicacion de una sola pagina: no necesita Python ni servidor.
start "" "%~dp0index.html"
exit /b 0
```

Y el acceso directo apunta **directo al HTML** (así no hay ninguna ventana de
consola, ni siquiera un parpadeo):

```powershell
$link.TargetPath   = Join-Path $toolDir 'index.html'
$link.IconLocation = (Join-Path $toolDir 'icon.ico') + ',0'
```

El HTML debe ser autocontenido y funcionar bajo `file://`: scripts clásicos (no
módulos ES), librerías en `vendor/` cargadas con `<script src>` (una build UMD),
exportación por descargas de `Blob`, persistencia en `localStorage`. **Ojo al
probarlo:** el panel de vista previa del entorno trata `file://` como snapshot
estático y no ejecuta el JS; para verificarlo de verdad, sírvelo con
`python -m http.server` en `127.0.0.1` y navega por HTTP.

**Tarea programada al iniciar sesión:**

```powershell
# Doble ocultacion: powershell sin ventana lanza el script tambien oculto.
# Con una sola capa se ve un parpadeo de consola en cada arranque.
$inner    = "Start-Process -WindowStyle Hidden -FilePath '$script' -ArgumentList '/silent'"
$argument = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"$inner`""

$action  = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $argument
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -Hidden `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME `
    -LogonType Interactive -RunLevel 'Limited'

Register-ScheduledTask -TaskName 'BSTools - NOMBRE' -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null
```

Nombre de la tarea: `BSTools - <NOMBRE>`, y `uninstall.ps1` la borra con
`Unregister-ScheduledTask -TaskName 'BSTools - NOMBRE' -Confirm:$false`.

`RunLevel Limited` por defecto: `Highest` provocaría un UAC en cada inicio de
sesión. Si de verdad hace falta administrador, ponlo detrás de un `-System` o
similar y avisa de que la instalación pedirá elevación una vez.

**Servidor web local.** Solo biblioteca estándar (`http.server`), escucha en
`127.0.0.1` con puerto `0` (el sistema elige uno libre) y, **si el servidor
escribe en disco o ejecuta algo**, token aleatorio (`secrets.token_urlsafe`)
exigido en cada petición, incluido en la URL que se abre. Sin token, `403`.
Endpoint de apagado y enlace para cerrarlo desde la propia página.

### `README.md` de la herramienta

Orden fijo, para que se lean todos igual:

```markdown
# NOMBRE

Una o dos frases: qué hace y qué obtienes.

## Instalación
El comando, y qué hace exactamente el instalador (lista numerada).
Nota de que escribe en HKCU y no necesita administrador.
Nota de Windows 11 → "Mostrar más opciones" (Shift+F10).
Cómo desinstalar.

## Uso
Los pasos, incluido el resultado esperado.

## Qué genera / Qué hace  (si aplica)
Tabla de salidas o de opciones.

## Lo que no hace (y por qué)   (si aplica)
Las limitaciones conocidas, explicadas. Ahorra issues.

## Problemas comunes
Síntoma → causa → solución. Incluye siempre "moviste la carpeta →
reejecuta install.ps1".

---
Parte de [BSTools](../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · CC0 1.0
```

---

## 7. Cómo probar

No hace falta tener archivos reales: **genera la entrada sintéticamente** y que
incluya los casos difíciles. Para PDF2MD se creó un PDF con encabezados, pies
con número de página, palabras partidas con guion, listas y una tabla. Para
BrandAssets, un PNG 1024×1024 con transparencia dibujado con Pillow.

Los tres niveles, siempre:

**1. El script directamente**

```bash
python script.py entrada
```

**2. El lanzador, desde una ruta con espacios** (es el fallo clásico)

```powershell
Start-Process -FilePath "C:\ruta con espacios\NOMBRE.cmd" -ArgumentList '"C:\otra ruta\entrada.ext"'
```

**3. El registro quedó bien escrito**

```powershell
$k = 'HKCU:\Software\Classes\SystemFileAssociations\.EXT\shell\BSTools.NOMBRE'
(Get-ItemProperty $k).'(default)'
(Get-ItemProperty "$k\command").'(default)'
```

Y además: que `uninstall.ps1` deja el registro limpio, y que reejecutar
`install.ps1` dos veces seguidas no duplica nada.

Si la herramienta **escribe archivos**, prueba también rutas con espacios,
nombres con caracteres inválidos y un intento de travesía de directorios
(`../../`) para confirmar que no se escapa de la carpeta destino.

---

## 8. Antes de dar por terminada la herramienta

- [ ] `README.md` de la herramienta, con el orden de secciones de arriba
- [ ] Fila nueva en la tabla de [README.md](README.md) raíz
- [ ] Bloque nuevo en el árbol de estructura del README raíz
- [ ] Fila nueva en la tabla de [STATUS.md](STATUS.md) + sección con decisiones
      de diseño, limitaciones y qué se probó exactamente
- [ ] Entrada nueva **arriba** en [CHANGELOG.md](CHANGELOG.md), con versión y
      fecha (`## [NOMBRE 1.0.0] - AAAA-MM-DD`)
- [ ] `.gitignore` si el uso genera archivos locales (`.lnk`, carpetas de salida)
- [ ] `install.ps1` ejecutado de verdad y registro verificado
- [ ] Commit y **push**. No dejes trabajo sin empujar: se desarrolla desde varias
      máquinas y la siguiente sesión empieza con `git pull`.

---

## 9. Trampas del entorno

- **PowerShell 5.1**: no existen `&&`, `||`, ni el operador ternario. Encadena
  con `;` o `if ($?) { ... }`.
- **`git push` desde PowerShell** escupe su salida por stderr y PowerShell la
  presenta como `NativeCommandError` aunque haya funcionado. Verifica de verdad
  con `git ls-remote origin` o `git status -sb`.
- **Identidad de git**: puede no estar configurada en una máquina nueva. Se
  configura **local al repositorio** (`git config user.name` sin `--global`).
- **Windows 11**: las entradas clásicas del menú contextual viven dentro de
  *Mostrar más opciones* (`Shift+F10`). Menciónalo siempre en los README.
- **`gh` (GitHub CLI) no está instalado** en la máquina principal; usa `git`.
- **Salida de Python a un archivo** está bufferizada por bloques: usa `-u` o
  `flush=True` si necesitas ver el arranque al instante.

---

Parte de [BSTools](README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · CC0 1.0
