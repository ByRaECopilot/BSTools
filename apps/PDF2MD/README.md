# PDF2MD

Convierte cualquier PDF a Markdown desde el menú contextual del Explorador de
Windows. El Markdown resultante está pensado para dárselo a un LLM (Claude,
ChatGPT, etc.): estructura limpia, tablas reales y sin la basura que suelen
arrastrar los extractores de PDF.

Parte de [BSTools](../../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · Licencia [CC0](../../LICENSE)

---

## Instalación

```powershell
cd PDF2MD
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

El instalador se encarga de todo:

1. Instala la dependencia de Python (`pymupdf4llm`).
2. Registra la entrada del menú contextual para archivos `.pdf` y para carpetas.

No requiere permisos de administrador. Para revertirlo:

```powershell
powershell -ExecutionPolicy Bypass -File .\uninstall.ps1
```

## Uso

**Desde el Explorador**

- Click derecho sobre un `.pdf` → **Convertir a Markdown (Claude)**
  → genera `documento.md` junto al PDF.
- Click derecho sobre una **carpeta** → convierte todos los PDF que contenga.

En Windows 11, la opción está dentro de *Mostrar más opciones* (`Shift + F10`).

**Desde la línea de comandos**

```bash
python pdf2md.py documento.pdf                # -> documento.md
python pdf2md.py documento.pdf salida.md      # nombre de salida concreto
python pdf2md.py C:\ruta\carpeta              # convierte todos los PDF
python pdf2md.py documento.pdf --images       # extrae también las imágenes
python pdf2md.py documento.pdf --no-page-markers
```

---

## Qué hace especial al Markdown que genera

El objetivo no es "un PDF pasado a texto", sino un documento que un modelo de
lenguaje pueda navegar y citar sin confundirse.

**Cabecera YAML con el contexto del documento.** El modelo sabe de qué está
leyendo antes de la primera línea:

```yaml
---
title: "Informe de Arquitectura"
source_file: "informe.pdf"
pages: 42
author: "ByRae Software"
converted: 2026-07-20
converter: pdf2md (BSTools)
---
```

**Índice del documento** extraído de los marcadores reales del PDF, con número
de página. Da al modelo un mapa del contenido de un vistazo.

**Marcadores de página** como comentarios HTML invisibles al renderizar:

```markdown
<!-- page: 17 -->
```

Así el modelo puede responder *"según la página 17..."* con precisión, algo
imposible cuando el PDF se aplana en un único bloque de texto.

**Jerarquía de encabezados** deducida del tamaño y peso de las fuentes, no de
adivinanzas sobre el texto. Los `#`/`##`/`###` reflejan la estructura real.

**Tablas en formato pipe** de Markdown, no columnas de texto desalineadas —
que es donde fallan la mayoría de los conversores y donde el modelo empieza a
inventar datos.

**Limpieza específica de PDF**, lo que marca la diferencia en documentos largos:

| Problema del PDF | Qué hace PDF2MD |
|---|---|
| Encabezado/pie repetido en cada página | Lo detecta por frecuencia y lo elimina |
| Palabras partidas: `exten-\nsión` | Las une: `extensión` |
| Ligaduras tipográficas: `ﬁ`, `ﬂ`, `ﬀ` | Las normaliza a `fi`, `fl`, `ff` |
| Comillas curvas, espacios de ancho cero | Normalizados a ASCII |
| Encabezados vacíos y ruido del extractor | Eliminados |
| Listas con huecos, líneas en blanco de sobra | Compactadas |

Todo eso son *tokens* que dejas de pagar y ruido que el modelo deja de
interpretar como significativo.

---

## Motor

Usa [PyMuPDF4LLM](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/), la
extracción de PyMuPDF diseñada específicamente para alimentar LLMs y pipelines
RAG. Es rápida (segundos, no minutos), local, y no descarga modelos de varios
gigabytes.

**Decisión de diseño:** se descartó [Marker](https://github.com/VikParuchuri/marker)
como motor pese a dar mejor resultado en PDFs complejos, porque descarga unos
2 GB de modelos y es lento sin GPU. `pymupdf4llm` convierte en segundos y no
descarga nada.

**Limitación conocida:** un PDF escaneado (solo imágenes, sin capa de texto) no
tiene texto que extraer. PDF2MD lo detecta y avisa en lugar de generar un `.md`
vacío. Para esos casos necesitas OCR previo — por ejemplo
[OCRmyPDF](https://ocrmypdf.readthedocs.io/).

## Requisitos

- Windows 10 u 11
- Python 3.9 o superior en el `PATH`
- `pymupdf4llm` (lo instala `install.ps1`; si falta, el script intenta
  instalarlo solo en la primera ejecución)

## Resolución de problemas

**No aparece la opción en el menú.** En Windows 11 mira dentro de *Mostrar más
opciones*. Si sigue sin salir, reinicia el Explorador:
`Ctrl+Shift+Esc` → *Explorador de Windows* → *Reiniciar*.

**"No se ha encontrado Python".** Instálalo desde
[python.org](https://www.python.org/downloads/) marcando *Add Python to PATH*, y
vuelve a ejecutar `install.ps1`.

**La ventana se cierra muy rápido.** Es lo normal cuando todo va bien: la
ventana solo se queda abierta si hay un error.

**Moviste la carpeta de sitio.** El registro guarda la ruta absoluta del
lanzador. Vuelve a ejecutar `install.ps1` desde la ubicación nueva.
