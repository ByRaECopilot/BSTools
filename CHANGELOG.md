# Changelog

Todos los cambios relevantes de BSTools.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado es [semántico](https://semver.org/lang/es/), aplicado **por
herramienta** (cada carpeta lleva su propia versión).

---

## [Limpiar Temporales 1.0.0] - 2026-07-22

Primera versión. Herramienta aportada por el usuario, adaptada a las
convenciones del repositorio.

### Añadido

- `LimpiarTemporales.bat`: vacía el Temp del usuario (`%TEMP%`) y el del sistema
  (`%SystemRoot%\Temp`) con un doble clic.
- `README.md` de la herramienta.

### Cambiado

- El script muestra ahora qué carpetas limpia y un resumen final con `pause`, en
  vez de cerrar la ventana sin feedback (`exit` → `exit /b`).
- Avisa de que el Temp del sistema requiere administrador y de que los archivos
  en uso se omiten, para no confundir la omisión con un fallo.

### Notas

- Es la primera herramienta que **no** usa menú contextual: es una utilidad de
  ejecución manual, sin instalador ni cambios en el registro.

---

## [PDF2MD 1.0.0] - 2026-07-20

Primera versión publicada. Reescritura completa de un prototipo previo que
usaba el CLI `pdf2md` de Node.

### Añadido

- Conversión de PDF a Markdown con `pymupdf4llm`, orientada a que el resultado
  lo consuma un LLM.
- Cabecera YAML con título, autor, archivo origen, número de páginas y fecha.
- Índice del documento extraído de los marcadores reales del PDF, con página.
- Marcadores `<!-- page: N -->` para que el modelo pueda citar página exacta.
- Detección de encabezados por tamaño y peso de fuente; tablas en formato pipe.
- Limpieza de artefactos del PDF: encabezados y pies repetidos (detectados por
  frecuencia), palabras partidas por guion, ligaduras tipográficas, comillas
  curvas, espacios de ancho cero, encabezados vacíos y listas con huecos.
- Conversión por lotes: click derecho sobre una carpeta convierte todos sus PDF.
- Extracción opcional de imágenes (`--images`).
- Aviso explícito cuando el PDF está escaneado y no tiene texto que extraer,
  en lugar de generar un `.md` vacío.
- `install.ps1` / `uninstall.ps1`: instalan dependencias y registran el menú
  contextual en `HKCU`, sin permisos de administrador.

### Cambiado

- Motor de conversión: de `pdf2md` (Node) a `pymupdf4llm` (Python), por la
  calidad del Markdown resultante.
- La ruta del lanzador se deduce en tiempo de instalación en vez de estar
  escrita a mano en un `.reg`, para que el repositorio funcione allá donde se
  descargue.

### Eliminado

- `convert_pdf2md.bat` y `Registro.reg` del prototipo. El `.bat` copiaba el PDF
  a un archivo temporal sin espacios para sortear una limitación del CLI
  antiguo; ya no hace falta.

---

## [BSTools] - 2026-07-20

### Añadido

- Estructura del repositorio: una carpeta autocontenida por herramienta.
- Licencia CC0 1.0 (dominio público).
- `README.md` con el índice de herramientas e instrucciones de instalación.
- `CLAUDE.md`, `STATUS.md` y este `CHANGELOG.md` para que el contexto del
  proyecto viaje con el repositorio entre máquinas.
- Publicación en https://github.com/ByRaECopilot/BSTools
