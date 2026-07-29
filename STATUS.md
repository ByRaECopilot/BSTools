# STATUS

Estado actual del proyecto. Se actualiza al final de cada sesión de trabajo.
Para el histórico de cambios, ver [CHANGELOG.md](CHANGELOG.md).
Para las convenciones de desarrollo, ver [CLAUDE.md](CLAUDE.md).
Para construir una herramienta nueva, ver [SPEC.md](SPEC.md).

**Última actualización:** 2026-07-29

---

## Herramientas

| Herramienta | Versión | Estado | Notas |
|---|---|---|---|
| [PDF2MD](PDF2MD/) | 1.0.0 | Estable | Probado de punta a punta. En uso. |
| [Limpiar Temporales](Limpiar%20Temporales/) | 2.0.0 | Estable | Tarea de arranque silenciosa, sin confirmación. Probado. |
| [BrandAssets](BrandAssets/) | 1.0.0 | Estable | Iconos de PWA desde un PNG 1024. Probado de punta a punta. |
| [Mermaid](Mermaid/) | 1.2.0 | Estable | Editor grafico de diagramas de flujo, cliente puro. Edicion bidireccional; el parser digiere el flowchart tipico de una IA. Probado de punta a punta. |

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

## Mermaid

Editor grafico de diagramas de flujo. Arrastras formas, las unes con flechas y el
codigo `flowchart` de Mermaid se genera en tiempo real. Motor de render (para la
vista previa y la exportacion SVG/PNG): la propia libreria Mermaid, empaquetada
en `vendor/`.

**Patron nuevo: cliente puro.** Es la primera herramienta sin Python ni servidor.
El lanzador solo hace `start index.html`; el acceso directo apunta directamente
al HTML, asi que al abrirlo no hay ninguna ventana de consola, solo el navegador.
Todo (logica, estilos, libreria) vive en la carpeta y funciona sin internet.

**Funciona:** 8 formas, 4 tipos de flecha, 4 direcciones, color de nodo (via
`style`), editar etiquetas de nodo y de flecha, conexion arrastrando desde los
puertos, mover/panear/zoom, deshacer-rehacer, autoguardado en `localStorage`,
generacion de codigo con escapado de comillas (`#quot;`) y `<`/`>`, vista previa
con Mermaid y exportacion a `.mmd`, `.svg` y `.png`.

**Edicion bidireccional (v1.1.0).** El panel de codigo es editable: lo que
escribe el usuario se parsea (con retardo) y reconstruye el lienzo. Se conserva
la posicion de los nodos existentes (por id) y los nuevos se autoubican cerca de
sus vecinos (o por capas si el codigo es nuevo del todo). Si el texto no encaja
en el subconjunto soportado, el lienzo no se toca y sale un aviso rojo. El editor
es un `<textarea>` transparente superpuesto a un `<pre>` resaltado, alineados
pixel a pixel (mismo font/padding/line-height, scroll sincronizado).

**Decisiones de diseno:**

- **Lienzo SVG propio** para la edicion (arrastrar/conectar), y Mermaid solo para
  la vista previa y el export. Separar ambos evita depender del render de Mermaid
  para la interaccion, que debe ser instantanea.
- **El parser digiere el `flowchart` habitual** (v1.2.0): ademas de lo que genera
  el editor, entiende subgraphs (aplanados), multidestino `&`, etiqueta de flecha
  en linea (`-. txt .->`) y entidades HTML. Motivo: la Vista previa (Mermaid real)
  ya renderizaba el codigo pegado de una IA, pero el lienzo fallaba; ahora lo
  reconstruye. Sigue sin ser un parser general de Mermaid: otros tipos de diagrama
  avisan en el lienzo (pero la Vista previa los pinta igual).
- **Libreria empaquetada** (`vendor/mermaid.min.js`, ~3,5 MB) en vez de CDN: fiel
  a la filosofia del repo (sin dependencias de red en runtime, funciona offline).

**No hace:** otros tipos de diagrama (secuencia, Gantt, clases...). Solo
`flowchart`. El menu contextual en `.mmd` abre el editor (no carga el archivo
automaticamente; para editarlo, pega su contenido en el panel de codigo).

**Probado:** servido por HTTP local y verificado por JS de punta a punta -- carga
del ejemplo (5 nodos/5 aristas), paleta de 8 formas, generacion de codigo con
escapado, render con Mermaid del ejemplo y de un nodo con comillas y `<test>`,
conexion por arrastre simulando pointer events (puerto -> nodo destino),
deshacer, y exportacion SVG (~100 KB) y PNG. Registro del menu contextual y
acceso directo (destino = index.html, icono propio) verificados. Nivel 2 (file://
en navegador real) queda al usuario: el panel de preview del entorno trata
file:// como snapshot estatico y no ejecuta el JS, por eso la prueba se hizo por
HTTP -- el unico camino distinto en file:// es la carga de scripts locales, que
para scripts clasicos y una libreria UMD funciona igual. Comprobado ademas que el
bundle de Mermaid no usa `import()` dinamico (0 ocurrencias): trae todos los
diagramas estaticos, asi que la vista previa no depende de fetch de modulos y no
rompe bajo file:// por CORS.

---

## Pendiente / ideas

Nada bloqueante. Ideas para más adelante, sin compromiso:

- OCR en PDF2MD para escaneados (solo si surge la necesidad).
- Descripción y *topics* del repositorio en GitHub, para que se encuentre.
- Herramientas nuevas: aún sin decidir.
- BrandAssets: generar `favicon.svg` cuando la entrada ya sea un SVG, y
  plantillas de captura para el `screenshots` del manifest.
- Mermaid: mas tipos de diagrama (secuencia, clases). Cargar el `.mmd` del menu
  contextual directamente en el editor (hoy hay que pegar el contenido).
  Autoruteo ortogonal de las flechas.

---

## Entorno de la máquina principal

- Windows 10 Pro · Python 3.11.9 · Git 2.55
- `gh` (GitHub CLI) **no** instalado
- Ruta local del repositorio: `D:\_IAG\_Tools`
- PDF2MD instalado en el menú contextual de este equipo
