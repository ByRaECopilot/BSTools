# MDViewer

Visor de archivos Markdown (`.md`) para Windows. Solo lectura, fondo blanco,
formato idéntico al de GitHub y **exportación a PDF**.

Está pensado para abrirse al instante: es lo que haces cuando haces doble clic en
un `.md`, no una aplicación que "arrancas".

---

## Instalación

**No tiene instalador.** Ejecuta `MDViewer.exe` y él mismo te preguntará, la
primera vez, si quieres asociar los archivos `.md` a la aplicación. Responde que
sí y a partir de ahí abrirán con doble clic.

Si respondes que no, puedes cambiar de idea cuando quieras: haz clic derecho
dentro de la ventana del visor y usa **Asociar archivos .md** / **Quitar
asociación**.

La asociación se escribe solo en `HKCU:\Software\Classes` (tu usuario, sin
permisos de administrador) y se revierte por completo desde el mismo menú.

> **Si Windows sigue abriendo otro programa:** significa que ya habías elegido
> una aplicación por defecto para los `.md`. Windows protege esa elección y
> ningún programa puede cambiarla en silencio. Hazlo tú una vez: clic derecho en
> un `.md` → *Abrir con* → *Elegir otra aplicación* → MDViewer → *Usar siempre*.

---

## Uso

- **Doble clic** en cualquier `.md` (si aceptaste la asociación).
- O arrastra el archivo sobre `MDViewer.exe`.
- O abre `MDViewer.exe` sin más: te pedirá que elijas un archivo.

**Exportar a PDF:** el botón está arriba a la derecha. Eliges dónde guardar y
listo, sin diálogos de impresión. Esta función no se carga hasta que la pulsas,
así que no ralentiza el arranque.

**Recarga en vivo:** si editas el `.md` en otro programa y guardas, la vista se
actualiza sola sin perder tu posición de lectura.

**Varios archivos a la vez:** cada uno abre su propia ventana, pero todas
comparten el mismo proceso. Por eso el segundo archivo abre mucho más rápido que
el primero.

---

## Rendimiento

Medido en la máquina de desarrollo:

| | |
|---|---|
| Primer archivo (en frío) | ~165 ms |
| Siguientes archivos | ~235 ms |
| RAM | ~260 MB mientras hay una ventana abierta |

Esos 260 MB son el precio de usar el motor de Chromium, que es lo que permite que
las tablas, el código y el PDF se vean bien. Es memoria que se libera entera al
cerrar la ventana.

---

## Qué hay dentro

```
MDViewer/
├── MDViewer.exe                          la aplicación (~90 KB)
├── Microsoft.Web.WebView2.Core.dll       \
├── Microsoft.Web.WebView2.WinForms.dll    |  motor de render (WebView2)
├── WebView2Loader.dll                    /
├── build.ps1                             recompila el .exe (solo desarrollo)
├── src/MDViewer.cs                       código fuente, un solo archivo
└── assets/
    ├── viewer.html                       la vista: HTML+CSS+JS, autocontenido
    └── vendor/                           marked.js y github-markdown-css
```

Todo funciona **sin internet**. No hay servicios en segundo plano ni nada que
quede corriendo cuando cierras la ventana.

### Recompilar

Solo si tocas `src/MDViewer.cs` o `assets/viewer.html`:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

No necesitas instalar nada: usa el compilador de C# que ya viene con Windows
(`csc.exe` de .NET Framework 4.8). El `viewer.html` se incrusta dentro del `.exe`
durante la compilación.

---

## Requisitos

- Windows 10 u 11
- **WebView2 Runtime** — ya viene preinstalado en Windows 11 y en Windows 10
  actualizado. Si faltara, se descarga gratis de Microsoft.
- No necesita Python, ni .NET SDK, ni permisos de administrador.

---

## Limitaciones conocidas

- **Solo lectura**: no edita ni guarda archivos. Es deliberado.
- **Sin colores en el código**: los bloques de código se ven en monoespaciada sin
  resaltado de sintaxis. Se descartó para que el arranque siguiera siendo
  instantáneo.
- **Tablas muy anchas en el PDF**: en pantalla se desplazan hacia los lados, pero
  el papel no se desplaza, así que una tabla más ancha que la página puede
  recortarse por la derecha.
- **Compilado para x64**: en un Windows ARM funcionará por emulación, algo más
  lento.

---

## Terceros

`marked` (MIT) y `github-markdown-css` (MIT) van incrustados en `viewer.html`,
conservando sus avisos de licencia. Las DLL de WebView2 son de Microsoft
(licencia BSD de 3 cláusulas). El resto es CC0, como todo BSTools.
