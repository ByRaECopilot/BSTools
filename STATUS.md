# STATUS

Estado actual del proyecto. Se actualiza al final de cada sesión de trabajo.
Para el histórico de cambios, ver [CHANGELOG.md](CHANGELOG.md).
Para las convenciones de desarrollo, ver [CLAUDE.md](CLAUDE.md).
Para construir una herramienta nueva, ver [SPEC.md](SPEC.md).

**Última actualización:** 2026-07-22

---

## Herramientas

| Herramienta | Versión | Estado | Notas |
|---|---|---|---|
| [PDF2MD](PDF2MD/) | 1.0.0 | Estable | Probado de punta a punta. En uso. |
| [Limpiar Temporales](Limpiar%20Temporales/) | 2.0.0 | Estable | Tarea de arranque silenciosa, sin confirmación. Probado. |
| [BrandAssets](BrandAssets/) | 1.0.0 | Estable | Iconos de PWA desde un PNG 1024. Probado de punta a punta. |

---

## PDF2MD

Convierte PDF a Markdown optimizado para LLMs. Motor: `pymupdf4llm`.

**Funciona:** conversión de archivo suelto, conversión por lotes desde carpeta,
nombres con espacios, cabecera YAML, índice desde marcadores del PDF, marcadores
`<!-- page: N -->`, tablas en formato pipe, eliminación de encabezados/pies
repetidos, unión de palabras partidas, normalización de ligaduras.

**Limitación conocida:** los PDF escaneados (solo imágenes, sin capa de texto)
no se pueden convertir. El script lo detecta y avisa en vez de generar un `.md`
vacío. Añadir OCR obligaría a depender de Tesseract, que hoy no compensa —
pendiente de que aparezca la necesidad real.

**Decisión de diseño:** se descartó [Marker](https://github.com/VikParuchuri/marker)
como motor pese a dar mejor resultado en PDFs complejos, porque descarga unos
2 GB de modelos y es lento sin GPU. `pymupdf4llm` convierte en segundos y no
descarga nada.

---

## Limpiar Temporales

Utilidad de doble clic (`.bat`) que vacía `%TEMP%` y `%SystemRoot%\Temp`.

**Nota de diseño:** se ejecuta **automáticamente al iniciar sesión**, en silencio
y sin confirmación. `install.ps1` registra una **tarea programada**
(`BSTools - Limpiar Temporales`, disparador *AtLogOn*, oculta). Tercer patrón de
instalación del repo, junto al menú contextual (PDF2MD) y —descartado en esta
herramienta— el acceso directo de Menú Inicio.

**Silencioso sin ventana:** la tarea lanza `powershell -WindowStyle Hidden` que a
su vez ejecuta el `.bat /silent` también oculto. Sin flash de consola en el
arranque.

**Admin:** por defecto la tarea es *Limited* (sin admin) y limpia solo el Temp del
usuario — que es donde se acumulan los temporales de Claude, el caso real. Para
incluir el Temp del sistema, `install.ps1 -System` la registra con *Highest*
(requiere admin una vez en la instalación). Se quitó la autoelevación del `.bat`:
en una tarea de arranque provocaría un UAC en cada inicio de sesión.

**Probado:** modo `/silent` contra un `%TEMP%` de prueba (borra sin salida) y
registro de la tarea (disparador, RunLevel Limited, Hidden, acción correcta). No
se ejecutó la tarea en real para no borrar el scratchpad de la sesión.

---

## BrandAssets

De un PNG 1024×1024 con transparencia a los 17 archivos que necesita una PWA.
Motor: Pillow. Interfaz: página web servida en `127.0.0.1` desde la biblioteca
estándar de Python.

**Funciona:** carga por arrastre o desde el menú contextual de un `.png`
(con la carpeta de esa imagen como destino por defecto), previsualización con
tamaños reales, exportación a la subcarpeta indicada, `manifest.webmanifest` y
`snippet.html` generados con los datos del formulario.

**Seguridad:** el servidor escribe archivos, así que exige un token aleatorio
generado al arrancar (va en la URL que se abre) y escucha solo en loopback. Sin
token responde `403`. El nombre de la subcarpeta se sanea: no puede contener
rutas ni escaparse de la carpeta destino.

**Decisiones de diseño:**

- Los assets se generan **en memoria** y solo se escriben al pulsar *Exportar*.
  Así la previsualización muestra los bytes reales, no una estimación.
- El *maskable* dibuja el logo al 80% central sobre fondo opaco (zona segura de
  Android); `apple-touch-icon` lleva fondo opaco porque iOS pinta de negro la
  transparencia; `og-image` es JPG 1200×630 porque es lo que esperan los
  agregadores.
- La reducción a paleta de 256 colores se aplica sola **solo cuando es sin
  pérdida** (el caso habitual de un logo plano). La versión con pérdida está
  detrás de una casilla y solo se acepta si ahorra más de un 15%.

**No genera:** `favicon.svg` (no se reconstruye un vectorial desde un PNG) ni
las capturas del manifest (son capturas de la app real).

**Probado:** generación contra un PNG sintético de 1024 (17 archivos, ~150 KB),
servidor de punta a punta (token válido e inválido, `/generate`, `/export`,
`/quit`), exportación a rutas con espacios, intento de travesía de directorios
(`../../`) contenido dentro del destino, flujo completo en el navegador y
lanzador `.cmd` desde una carpeta con espacios.

---

## Pendiente / ideas

Nada bloqueante. Ideas para más adelante, sin compromiso:

- OCR en PDF2MD para escaneados (solo si surge la necesidad).
- Descripción y *topics* del repositorio en GitHub, para que se encuentre.
- Herramientas nuevas: aún sin decidir.
- BrandAssets: generar `favicon.svg` cuando la entrada ya sea un SVG, y
  plantillas de captura para el `screenshots` del manifest.

---

## Entorno de la máquina principal

- Windows 10 Pro · Python 3.11.9 · Git 2.55
- `gh` (GitHub CLI) **no** instalado
- Ruta local del repositorio: `D:\_IAG\_Tools`
- PDF2MD instalado en el menú contextual de este equipo
