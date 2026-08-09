# Limpiar Temporales

Vacía las carpetas temporales de Windows **automáticamente al iniciar sesión**,
en silencio y sin preguntar. Útil cuando una herramienta —o un asistente como
Claude— deja miles de archivos temporales acumulados.

Parte de [BSTools](../../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · Licencia [CC0](../../LICENSE)

---

## Instalación

Registra la tarea de arranque (no requiere administrador):

```powershell
cd "Limpiar Temporales"
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

A partir de ahí, cada vez que inicies sesión en Windows se vaciará tu Temp de
usuario sin que veas nada.

**Para vaciar también el Temp del sistema** (`%SystemRoot%\Temp`), instala en modo
`-System`. Esto registra la tarea con privilegios altos, así que hay que
ejecutarlo **como administrador una sola vez**:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -System
```

Para revertirlo:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

## Cómo funciona

- La instalación crea una tarea en el Programador de tareas de Windows
  (`BSTools - Limpiar Temporales`) con disparador **al iniciar sesión**.
- La tarea se ejecuta **oculta**: PowerShell lanza el `.bat` en modo `/silent`
  sin ninguna ventana. No verás nada en el arranque.
- **Borra directamente, sin confirmación.**

## Uso manual

Puedes ejecutarla cuando quieras, sin esperar al siguiente arranque:

```powershell
Start-ScheduledTask -TaskName 'BSTools - Limpiar Temporales'
```

O doble clic en `LimpiarTemporales.bat`, que además muestra un resumen. (El doble
clic solo vacía el Temp del sistema si lo ejecutas como administrador.)

## Qué esperar

- **Los archivos en uso no se borran.** Windows los tiene bloqueados mientras un
  programa los usa; se omiten y la limpieza continúa. Es normal, no es un fallo.
- No pide confirmación por archivo ni al empezar: vacía las carpetas de
  temporales completas. Están pensadas para contenido desechable, así que es
  seguro, pero no guardes nada que quieras conservar dentro de `%TEMP%`.

## Notas

- Es la primera herramienta de BSTools que se instala como **tarea de arranque**,
  no como entrada de menú ni acceso directo.
- El Temp del usuario (`%TEMP%`) es donde se acumulan la mayoría de temporales,
  incluidos los de asistentes como Claude. El del sistema es secundario y por eso
  requiere el modo `-System` con administrador.
