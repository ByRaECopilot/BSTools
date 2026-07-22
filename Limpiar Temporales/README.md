# Limpiar Temporales

Vacía las carpetas temporales de Windows con un clic. Útil cuando una
herramienta —o un asistente como Claude— deja miles de archivos temporales
acumulados.

Parte de [BSTools](../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · Licencia [CC0](../LICENSE)

---

## Instalación

Crea un acceso directo en el Menú Inicio (no requiere administrador):

```powershell
cd "Limpiar Temporales"
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

Añade `-Desktop` si además lo quieres en el Escritorio:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1 -Desktop
```

Para revertirlo:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

También puedes usarlo sin instalar nada: doble clic directamente en
`LimpiarTemporales.bat`.

## Uso

Abre **Limpiar Temporales** desde el Menú Inicio (o doble clic en el `.bat`).

1. Al abrirlo pide **permisos de administrador**. Es opcional pero recomendable:
   solo con ellos puede vaciar el Temp del sistema (`%SystemRoot%\Temp`) además
   del tuyo (`%TEMP%`). Si rechazas el aviso, limpia solo el Temp del usuario.
2. Pide confirmación (`¿Continuar? S/N`) antes de borrar nada, para evitar
   vaciados por accidente.
3. Muestra un resumen y espera a que pulses una tecla.

## Qué esperar

- **Los archivos en uso no se borran.** Windows los tiene bloqueados mientras un
  programa los usa; el script los omite y continúa. Es normal, no es un fallo.
- No pide confirmación por archivo: vacía las carpetas de temporales completas.
  Están pensadas para contenido desechable, así que es seguro, pero no guardes
  nada que quieras conservar dentro de `%TEMP%`.

## Cómo funciona la elevación

El `.bat` se **autoeleva**: si no se está ejecutando como administrador, se
relanza a sí mismo pidiéndolo una sola vez (aviso UAC de Windows). Así basta con
un único acceso directo para el caso completo, sin tener que acordarse de hacer
click derecho → *Ejecutar como administrador*. Si cancelas el UAC, no falla:
continúa limpiando solo tu Temp de usuario.
