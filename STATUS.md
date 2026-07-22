# STATUS

Estado actual del proyecto. Se actualiza al final de cada sesión de trabajo.
Para el histórico de cambios, ver [CHANGELOG.md](CHANGELOG.md).
Para las convenciones de desarrollo, ver [CLAUDE.md](CLAUDE.md).

**Última actualización:** 2026-07-22

---

## Herramientas

| Herramienta | Versión | Estado | Notas |
|---|---|---|---|
| [PDF2MD](PDF2MD/) | 1.0.0 | Estable | Probado de punta a punta. En uso. |
| [Limpiar Temporales](Limpiar%20Temporales/) | 1.1.0 | Estable | Acceso directo en Menú Inicio + autoelevación. Probado. |

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

**Nota de diseño:** no se integra en el menú contextual — se instala como
**acceso directo en el Menú Inicio** (`install.ps1`, en `%APPDATA%`, sin admin;
sin tocar el registro). Es el segundo patrón de instalación del repo, junto al
verbo de menú contextual de PDF2MD.

**Autoelevación:** el `.bat` se relanza pidiendo administrador una sola vez, para
poder vaciar también el Temp del sistema. Si el usuario cancela el UAC, sigue y
limpia solo el Temp del usuario. Un único acceso directo cubre ambos casos.
Incluye confirmación `S/N` antes de borrar (evita vaciados por un clic accidental
desde el Menú Inicio). Los archivos en uso quedan bloqueados por Windows y se
saltan (comportamiento normal). Probado: ruta de cancelación y limpieza real
contra un `%TEMP%` de prueba.

---

## Pendiente / ideas

Nada bloqueante. Ideas para más adelante, sin compromiso:

- OCR en PDF2MD para escaneados (solo si surge la necesidad).
- Descripción y *topics* del repositorio en GitHub, para que se encuentre.
- Herramientas nuevas: aún sin decidir.

---

## Entorno de la máquina principal

- Windows 10 Pro · Python 3.11.9 · Git 2.55
- `gh` (GitHub CLI) **no** instalado
- Ruta local del repositorio: `D:\_IAG\_Tools`
- PDF2MD instalado en el menú contextual de este equipo
