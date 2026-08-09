# Tech Stack — BSTools

> Redistribuido desde `SPEC.md` §3 ("Los cuatro patrones de arranque"), §4 ("Contrato con Windows")
> y §9 ("Trampas del entorno"). Texto literal del dueño, sin reescribir.

## Los cuatro patrones de arranque

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

*(Origen: `SPEC.md` §3. Este mismo párrafo de "lo que no hacemos" se cita también en
[`spec/constitution/mission.md`](mission.md) §4, como respuesta a "qué NO es el producto".)*

## Contrato con Windows

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

*(Origen: `SPEC.md` §4)*

## Trampas del entorno

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

*(Origen: `SPEC.md` §9)*
