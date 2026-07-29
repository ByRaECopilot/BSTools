# BSTools

Colección de pequeñas herramientas para Windows que se integran en el menú
contextual del Explorador. Sin instaladores, sin servicios en segundo plano:
scripts que puedes leer, modificar y borrar cuando quieras.

Creado por **[www.byraesoftware.com](https://www.byraesoftware.com)** y liberado
al dominio público bajo **[CC0 1.0](LICENSE)**: úsalo, modifícalo y véndelo sin
pedir permiso ni dar atribución.

---

## Herramientas

| Herramienta | Qué hace |
|---|---|
| [PDF2MD](PDF2MD/) | Convierte un PDF a Markdown limpio y optimizado para que lo entienda un LLM (Claude, ChatGPT...). Click derecho → *Convertir a Markdown*. |
| [Limpiar Temporales](Limpiar%20Temporales/) | Vacía las carpetas temporales de Windows automáticamente al iniciar sesión, en silencio. Útil cuando se acumulan miles de archivos temporales. |
| [BrandAssets](BrandAssets/) | De un PNG de 1024×1024 saca todos los iconos e imágenes de una PWA (favicons, *maskable*, `apple-touch-icon`, `og-image.jpg` y el `manifest.webmanifest`). Interfaz web local, previsualización antes de exportar. |
| [Mermaid](Mermaid/) | Editor gráfico de diagramas de flujo: arrastras formas, las unes con flechas y el código Mermaid se genera en tiempo real. Vista previa y exportación a `.mmd` / `.svg` / `.png`. Funciona sin internet. |

*(Se irán añadiendo más.)*

---

## Instalación

Descarga el repositorio y ejecuta el instalador de la herramienta que quieras.

```powershell
git clone https://github.com/ByRaECopilot/BSTools.git
cd BSTools\PDF2MD
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

O bien: **Code → Download ZIP**, descomprime donde prefieras y ejecuta el
`install.ps1` de la carpeta correspondiente.

> Los instaladores escriben en `HKCU:\Software\Classes`, así que **no necesitan
> permisos de administrador** y solo afectan a tu usuario. Cada herramienta trae
> su `uninstall.ps1` para revertirlo por completo.

> **Windows 11:** las entradas clásicas del menú contextual aparecen dentro de
> *Mostrar más opciones* (o pulsando `Shift + F10`).

---

## Requisitos

- Windows 10 u 11
- [Python 3.9+](https://www.python.org/downloads/) con *Add Python to PATH*
  marcado durante la instalación (solo para las herramientas que lo usen)

---

## Estructura del repositorio

```
BSTools/
├── LICENSE            CC0 1.0
├── README.md          este archivo
├── CLAUDE.md          convenciones de desarrollo
├── SPEC.md            cómo se construye una herramienta (plantillas incluidas)
├── STATUS.md          estado actual del proyecto
├── CHANGELOG.md       histórico de cambios
├── PDF2MD/            una carpeta autocontenida por herramienta
│   ├── install.ps1
│   ├── uninstall.ps1
│   ├── convert.cmd
│   ├── pdf2md.py
│   ├── requirements.txt
│   └── README.md
├── Limpiar Temporales/
│   ├── install.ps1
│   ├── uninstall.ps1
│   ├── LimpiarTemporales.bat
│   └── README.md
├── BrandAssets/
│   ├── install.ps1
│   ├── uninstall.ps1
│   ├── BrandAssets.cmd
│   ├── server.py
│   ├── assets.py
│   ├── ui.html
│   ├── requirements.txt
│   └── README.md
└── Mermaid/
    ├── install.ps1
    ├── uninstall.ps1
    ├── Mermaid.cmd
    ├── server.py
    ├── index.html
    ├── editor.js
    ├── icon.ico
    ├── vendor/mermaid.min.js
    ├── graphs/            diagramas guardados (locales, en .gitignore)
    └── README.md
```

Cada herramienta es independiente: puedes copiar solo su carpeta y funcionará.

## Contribuir

Las *pull requests* son bienvenidas. Al enviar código aceptas liberarlo también
bajo CC0.

Si vas a añadir una herramienta, [SPEC.md](SPEC.md) tiene la especificación
completa y las plantillas de `install.ps1`, `uninstall.ps1` y el lanzador listas
para copiar.
