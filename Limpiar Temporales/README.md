# Limpiar Temporales

Borra el contenido de las carpetas temporales de Windows con un doble clic.
Útil cuando una herramienta —o un asistente como Claude— deja miles de archivos
temporales acumulados.

Parte de [BSTools](../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · Licencia [CC0](../LICENSE)

---

## Uso

Doble clic en **`LimpiarTemporales.bat`**.

Limpia dos ubicaciones:

- **Temp del usuario** (`%TEMP%`) — no necesita permisos especiales.
- **Temp del sistema** (`%SystemRoot%\Temp`) — necesita **administrador**. Si lo
  ejecutas con doble clic normal, esta parte se omite sin error. Para incluirla:
  click derecho → *Ejecutar como administrador*.

Al terminar muestra un resumen y espera a que pulses una tecla.

## Qué esperar

- **Los archivos en uso no se borran.** Windows los tiene bloqueados mientras un
  programa los usa; el script los omite y sigue. Es normal y no es un fallo.
- No pide confirmación por archivo: vacía las carpetas de temporales directamente.
  Esas carpetas están pensadas para contenido desechable, así que es seguro, pero
  no guardes nada que quieras conservar dentro de `%TEMP%`.

## Sin instalador

A diferencia de otras herramientas de BSTools, esta no se integra en el menú
contextual: es una utilidad que ejecutas a mano cuando lo necesitas. No hay nada
que instalar ni desinstalar; el `.bat` no toca el registro.
