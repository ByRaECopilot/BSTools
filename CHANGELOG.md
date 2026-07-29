# Changelog

Todos los cambios relevantes de BSTools.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y el versionado es [semántico](https://semver.org/lang/es/), aplicado **por
herramienta** (cada carpeta lleva su propia versión).

---

## [Mermaid 1.3.0] - 2026-07-29

Guardar y cargar diagramas en la subcarpeta `graphs/`. Para poder escribir en
disco, la herramienta pasa de **cliente puro** a **interfaz web local** (servidor
Python, patrón de BrandAssets).

### Añadido

- `server.py`: servidor local (biblioteca estándar, `127.0.0.1`, puerto libre,
  token) que sirve el editor y expone `/save`, `/load`, `/list`, `/delete`,
  `/preload` y `/quit`. Los nombres se sanean (sin travesía de rutas).
- Guardado en dos archivos por diagrama: `<nombre>.mmd` (código) y
  `<nombre>.layout.json` (estado completo con posiciones, formas, colores y
  dirección). Carpeta `graphs/` con su propio `.gitignore`.
- Sección **Diagramas** en la barra izquierda: campo de nombre, *Guardar* y lista
  de guardados (clic para cargar, ✕ para borrar).
- El menú contextual de un `.mmd` ahora **abre el archivo cargado** (y sus
  posiciones si hay un `.layout.json` al lado): resuelve la idea pendiente.

### Cambiado

- `Mermaid.cmd` arranca el servidor (con detección de Python) en vez de abrir el
  HTML directamente. El acceso directo apunta al `.cmd`, minimizado.
- `install.ps1`: comprueba Python, crea el acceso directo al lanzador y pasa `%1`
  en el menú contextual para precargar el archivo.

### Notas

- Si el `index.html` se abre suelto por `file://`, la sección de guardado se
  oculta con un aviso (no hay servidor); el resto del editor sigue funcionando.
- Cuarto patrón de arranque del repo (**cliente puro**) queda sin herramienta que
  lo use; se mantiene documentado en SPEC como opción válida.

---

## [Mermaid 1.2.0] - 2026-07-29

El parser código→lienzo pasa de entender solo lo que genera el editor a digerir
el `flowchart` habitual que produce una IA.

### Añadido

- **Subgráficos** (`subgraph ... end`): se aplanan (se conservan nodos y
  flechas; la caja no se dibuja en el lienzo, pero sí en la Vista previa).
- **Multidestino con `&`**: `A --> B & C` y `A & B --> C` se expanden a varias
  flechas (producto cartesiano de los extremos).
- **Etiqueta de flecha en línea**: `-- texto -->`, `-. texto .->` y
  `== texto ==>` se normalizan a la forma con tubería antes de parsear.
- Decodificación de entidades HTML en las etiquetas (`&lt;`, `&gt;`, `&amp;`,
  `&quot;`).

### Notas

- Motivación: al pegar un diagrama generado por Claude, la *Vista previa* (motor
  real de Mermaid) ya lo renderizaba, pero el lienzo editable fallaba con estas
  construcciones. Ahora las reconstruye. Lo que quede fuera del subconjunto sigue
  avisando en el lienzo sin afectar a la Vista previa.

---

## [Mermaid 1.1.0] - 2026-07-29

Edición del código en los dos sentidos.

### Añadido

- El panel de código pasa de solo lectura a **editable**: lo que escribe el
  usuario se parsea y reconstruye el lienzo en tiempo real. Se conserva la
  posición de los nodos existentes (por id) y los nuevos se autoubican (cerca de
  sus vecinos, o por capas si el código es nuevo del todo).
- Parser del subconjunto de `flowchart` que genera el editor: cabecera, las 8
  formas, las 4 flechas con etiqueta `|"..."|`, cadenas `A --> B --> C` y líneas
  `style`. Ante un error de sintaxis, el lienzo no se toca y se muestra un aviso.

### Cambiado

- El panel de código es ahora un `<textarea>` transparente superpuesto a un
  `<pre>` resaltado, alineados y con scroll sincronizado, para mantener el
  resaltado de sintaxis mientras se edita.
- El teclado global (Supr, Ctrl+Z...) deja de interceptarse cuando el foco está
  en el editor de código, para no pisar su edición nativa.

---

## [Mermaid 1.0.0] - 2026-07-28

Primera versión. Editor gráfico de diagramas de flujo que genera el código
Mermaid en tiempo real.

### Añadido

- `index.html` + `editor.js`: lienzo SVG propio para arrastrar formas y unirlas
  con flechas (conexión arrastrando desde los puertos de cada nodo). 8 formas,
  4 tipos de flecha, 4 direcciones, color de nodo (vía `style`), edición de
  etiquetas de nodo y de flecha, mover/panear/zoom, deshacer-rehacer y
  autoguardado en `localStorage`. UI con tema claro/oscuro.
- Generación del código `flowchart` en vivo, con escapado de comillas
  (`#quot;`) y de `<`/`>`.
- Vista previa del diagrama renderizado y exportación a `.mmd`, `.svg` y `.png`,
  usando la propia librería Mermaid empaquetada en `vendor/mermaid.min.js`.
- `install.ps1` / `uninstall.ps1`: acceso directo con icono propio (`icon.ico`)
  apuntando directamente al HTML, y entrada de menú contextual en los `.mmd`.

### Notas

- **Cuarto patrón de arranque del repo: cliente puro.** Primera herramienta sin
  Python ni servidor; el acceso directo abre el HTML directamente, sin ninguna
  ventana de consola. Todo funciona sin conexión.
- No importa `.mmd` existentes (haría falta un parser) ni otros tipos de diagrama
  más allá de `flowchart`.

---

## [BSTools] - 2026-07-28

### Añadido

- `SPEC.md` gana el **cuarto patrón de arranque, "cliente puro"** (UI que se
  resuelve entera en el navegador, sin servidor), con su plantilla de lanzador y
  la nota de que `file://` no ejecuta JS en el panel de vista previa del entorno.

---

## [BSTools] - 2026-07-22

### Añadido

- `SPEC.md`: especificación de una herramienta, con plantillas copiables de
  `install.ps1`, `uninstall.ps1` y el lanzador `.cmd`, los tres patrones de
  arranque (menú contextual, tarea programada, interfaz web local), el contrato
  con el registro de Windows, cómo probar y la lista de comprobación previa a
  publicar. Objetivo: no tener que abrir otra herramienta para copiar su
  estructura al desarrollar una nueva.

### Cambiado

- `CLAUDE.md` adelgaza: la anatomía, las convenciones y el procedimiento de
  prueba viven ahora en `SPEC.md`; queda lo imprescindible y los enlaces.
- Nombre del lanzador unificado en `<NombreHerramienta>.cmd` para las
  herramientas nuevas. `PDF2MD/convert.cmd` conserva su nombre: renombrarlo
  rompería los registros ya instalados.

---

## [BrandAssets 1.0.0] - 2026-07-22

Primera versión. Genera el juego completo de iconos e imágenes de marca de una
PWA a partir de un PNG de 1024×1024 con transparencia.

### Añadido

- `server.py`: servidor local con la biblioteca estándar. Escucha solo en
  `127.0.0.1`, en un puerto libre elegido al arrancar, y exige un token
  aleatorio en cada petición para que ningún otro proceso local pueda pedirle
  que escriba archivos.
- `assets.py`: la generación, sin nada de HTTP. Devuelve los 17 archivos en
  memoria para poder previsualizarlos antes de tocar el disco.
- `ui.html`: interfaz web (arrastrar y soltar, opciones, previsualización con
  tamaños reales, carpeta destino + nombre de subcarpeta, exportar).
- 17 archivos de salida: `logo.png`, `favicon.ico` multi-resolución,
  `favicon-16/32/48`, `icon-96/128/192/256/384/512`, `maskable-192/512`,
  `apple-touch-icon.png`, `og-image.jpg`, `manifest.webmanifest` y
  `snippet.html` con las etiquetas del `<head>`.
- Optimización: PNG sin metadatos, paleta de 256 colores cuando es **sin
  pérdida**, JPEG progresivo de calidad 82 y casilla opcional de compresión
  agresiva (solo se acepta si ahorra más de un 15%).
- `install.ps1` / `uninstall.ps1`: instalan Pillow, crean un acceso directo con
  icono dentro de la propia carpeta de la herramienta y registran la opción
  *Generar assets de marca* en el menú contextual de los `.png`.

### Notas

- Tercer patrón de arranque del repositorio: doble clic que levanta una
  **interfaz web local**, junto al menú contextual (PDF2MD) y la tarea de
  arranque (Limpiar Temporales).
- No genera `favicon.svg` (no se puede reconstruir un vectorial desde un PNG) ni
  las capturas del manifest (son de la app real, no del logo).

---

## [Limpiar Temporales 2.0.0] - 2026-07-22

Cambio de enfoque: de lanzarse a mano a **ejecutarse solo al iniciar Windows**,
en silencio y sin preguntar.

### Cambiado

- `install.ps1` ahora registra una **tarea programada** (`BSTools - Limpiar
  Temporales`) con disparador al iniciar sesión, en vez de crear un acceso
  directo en el Menú Inicio. La tarea corre **oculta** (sin ventana).
- El `.bat` **borra directamente, sin confirmación** `S/N`. Nuevo modo `/silent`
  (sin texto ni pausa) que usa la tarea del arranque.

### Eliminado

- Confirmación previa al borrado.
- Autoelevación automática del `.bat`: en una tarea de arranque habría provocado
  un aviso UAC en cada inicio de sesión. El Temp del sistema pasa a cubrirse con
  el modo `-System` del instalador (tarea con privilegios altos).
- Acceso directo del Menú Inicio de la versión 1.1.0 (el instalador y el
  desinstalador lo eliminan si existe).

### Añadido

- `install.ps1 -System`: registra la tarea con privilegios altos para vaciar
  también el Temp del sistema (requiere administrador en la instalación).

### Notas

- Es la primera herramienta de BSTools que se instala como **tarea de arranque**.

---

## [Limpiar Temporales 1.1.0] - 2026-07-22

### Añadido

- `install.ps1` / `uninstall.ps1`: crean y eliminan un acceso directo en el Menú
  Inicio del usuario (`%APPDATA%`, sin permisos de administrador). Con `-Desktop`
  se crea también en el Escritorio. Icono de papelera.
- Autoelevación en el `.bat`: se relanza pidiendo administrador una sola vez para
  vaciar también el Temp del sistema; si el usuario cancela, limpia solo el suyo.
- Confirmación `¿Continuar? (S/N)` antes de borrar, para evitar vaciados
  accidentales al abrirlo desde el Menú Inicio.
- Resumen en pantalla que indica si se limpió el Temp del sistema o no.

### Cambiado

- `timeout` sustituido por `ping` en la ruta de cancelación para no fallar si la
  entrada está redirigida.

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
