# BrandAssets

Un PNG de 1024×1024 con transparencia entra; salen todos los iconos e imágenes
que necesita una PWA, optimizados, previsualizados y guardados en la subcarpeta
que tú indiques.

Doble clic en el icono **BrandAssets** de esta carpeta → se abre una página web
local en tu navegador. **Nada sale de tu equipo**: el servidor escucha solo en
`127.0.0.1`, con un token aleatorio, y la imagen se procesa en tu máquina.

---

## Instalación

```powershell
cd BrandAssets
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

El instalador:

1. Instala **Pillow** (la única dependencia).
2. Crea el acceso directo **BrandAssets** dentro de esta misma carpeta, con
   icono propio, para abrir la herramienta con un doble clic.
3. Añade al menú contextual de los archivos `.png` la opción
   *Generar assets de marca (BrandAssets)*, que abre la herramienta con esa
   imagen ya cargada y la carpeta de destino apuntando a donde está el PNG.

Escribe en `HKCU:\Software\Classes`: **no necesita administrador**.

> En Windows 11, la opción del menú contextual está dentro de
> *Mostrar más opciones* (`Shift+F10`).

Para desinstalar: `powershell -ExecutionPolicy Bypass -File .\uninstall.ps1`

---

## Uso

1. **Imagen de origen.** Arrastra tu PNG (ideal: 1024×1024, cuadrado, con fondo
   transparente). Si no es cuadrado se rellena con transparencia; si es pequeño,
   la herramienta avisa.
2. **Datos de la aplicación.** Nombre, nombre corto, `start_url`, ruta pública
   de los iconos, color de fondo y color de tema. El color de fondo es el que
   llevan el icono *maskable*, el de iOS y la imagen social — esos tres no
   pueden ser transparentes.
3. **Generar y previsualizar.** Se muestran los 17 archivos con su tamaño real.
4. **Exportar.** Escribe la carpeta destino y el **nombre de la subcarpeta**;
   se crea y se escriben ahí todos los archivos.

---

## Qué genera

17 archivos, unos 150 KB en total para un logo plano típico.

| Archivo | Tamaño | Para qué |
|---|---|---|
| `logo.png` | 1024×1024 | Original optimizado, fuente de verdad del proyecto |
| `favicon.ico` | 16/32/48 | Navegadores antiguos, accesos directos, `/favicon.ico` |
| `favicon-16.png` `favicon-32.png` `favicon-48.png` | — | Favicons modernos |
| `icon-96` … `icon-512` .png | 96, 128, 192, 256, 384, 512 | Iconos `purpose: any` del manifest |
| `maskable-192.png` `maskable-512.png` | 192, 512 | Android: el sistema recorta los bordes |
| `apple-touch-icon.png` | 180×180 | Pantalla de inicio de iOS |
| `og-image.jpg` | 1200×630 | Vista previa al compartir (Open Graph y Twitter/X) |
| `manifest.webmanifest` | — | Manifest completo, listo para usar |
| `snippet.html` | — | Etiquetas `<link>` y `<meta>` para pegar en el `<head>` |

### Los tres casos especiales

**Maskable.** Android aplica una máscara (círculo, cuadrado redondeado,
gota…) que puede comerse hasta el 20% del borde. Por eso el logo se dibuja al
**80% central** sobre fondo opaco. Si usaras el icono normal como maskable, se
te recortarían las esquinas del dibujo.

**apple-touch-icon.** iOS **no respeta la transparencia**: la pinta de negro.
Se genera con fondo opaco y sin esquinas redondeadas, que ya las pone el
sistema.

**og-image.** Es JPG porque los agregadores (WhatsApp, Slack, Twitter/X,
LinkedIn) lo tratan mejor y pesa menos. 1200×630 es la proporción 1.91:1 que
esperan todos. Sirve igual para `twitter:image` con `summary_large_image`.

---

## Optimización

- PNG con `optimize=True` y sin metadatos.
- Si la imagen cabe sin pérdida en 256 colores, se guarda en paleta (típico de
  logos planos: bastante más ligero, **idéntico** píxel a píxel).
- Casilla **compresión agresiva**: fuerza la paleta de 256 colores aunque haya
  pérdida, y solo se queda con el resultado si ahorra más de un 15%. Útil en
  logos planos, desaconsejado si tu logo tiene degradados.
- JPEG progresivo, calidad 82.

---

## Lo que no genera (y por qué)

- **`favicon.svg`**: un SVG no se puede reconstruir desde un PNG. Si tienes el
  vectorial original, súbelo tal cual a tu web; es lo mejor para el favicon.
- **Capturas de pantalla del manifest** (`screenshots`): Chrome las usa para
  enseñar un diálogo de instalación más rico. Son capturas reales de tu app,
  no se pueden derivar del logo. Recomendado: una *wide* de 1280×720 y una
  *narrow* de 720×1280.

---

## Problemas comunes

**No se abre el navegador.** La consola imprime la URL con el token
(`http://127.0.0.1:PUERTO/?t=...`); ábrela a mano. Sin ese token el servidor
responde `403`, es a propósito.

**"Falta Pillow".** `pip install Pillow`, o vuelve a ejecutar `install.ps1`.

**El servidor no se cierra.** Enlace *cerrar servidor* al pie de la página, o
`Ctrl+C` / cerrar la ventana de consola.

**Moviste la carpeta.** El acceso directo y el menú contextual guardan rutas
absolutas: vuelve a ejecutar `install.ps1`.

---

Parte de [BSTools](../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · CC0 1.0
