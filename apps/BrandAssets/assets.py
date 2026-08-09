"""
Generacion del juego completo de recursos de marca de una PWA a partir de un
PNG cuadrado con transparencia (idealmente 1024x1024).

Parte de BSTools - https://www.byraesoftware.com
Licencia CC0 1.0 (dominio publico).

Todo se genera en memoria: build() devuelve una lista de Asset con los bytes
finales, para poder previsualizar antes de escribir nada en disco.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field

from PIL import Image

# Zona segura de un icono maskable: el contenido debe caber en el 80% central,
# porque Android recorta el resto con formas distintas segun el fabricante.
MASKABLE_SAFE = 0.80

# El icono de iOS se ve mejor con un margen pequeno; no lleva transparencia.
APPLE_PADDING = 0.90

# Iconos "any" del manifest (fondo transparente).
ICON_SIZES = [96, 128, 192, 256, 384, 512]

# Favicons sueltos, ademas del .ico multi-resolucion.
FAVICON_SIZES = [16, 32, 48]

# Tamanos que se empaquetan dentro de favicon.ico.
ICO_SIZES = [16, 32, 48]

MASKABLE_SIZES = [192, 512]

APPLE_SIZE = 180

OG_SIZE = (1200, 630)

JPEG_QUALITY = 82


@dataclass
class Asset:
    """Un archivo generado, todavia en memoria."""

    name: str
    data: bytes
    width: int = 0
    height: int = 0
    kind: str = 'icono'
    note: str = ''

    @property
    def size(self) -> int:
        return len(self.data)

    @property
    def mime(self) -> str:
        if self.name.endswith('.png'):
            return 'image/png'
        if self.name.endswith('.jpg'):
            return 'image/jpeg'
        if self.name.endswith('.ico'):
            return 'image/x-icon'
        return 'text/plain'


@dataclass
class Options:
    app_name: str = 'Mi aplicacion'
    short_name: str = 'MiApp'
    background: str = '#ffffff'   # fondo de maskable, apple y og-image
    theme: str = '#111111'        # theme_color del manifest
    start_url: str = '/'
    icon_path: str = '/icons'     # prefijo de las rutas dentro del manifest
    aggressive: bool = False      # paleta de 256 colores aunque haya perdida
    extras: list = field(default_factory=list)


# --- utilidades ---------------------------------------------------------------

def _hex_to_rgb(value: str) -> tuple:
    value = (value or '').strip().lstrip('#')
    if len(value) == 3:
        value = ''.join(c * 2 for c in value)
    if len(value) != 6:
        return (255, 255, 255)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (255, 255, 255)


def _png_bytes(img: Image.Image, aggressive: bool) -> bytes:
    """PNG optimizado. Reduce a paleta solo si no pierde calidad, o si el
    usuario ha pedido compresion agresiva y el ahorro es significativo."""
    buf = io.BytesIO()
    img.save(buf, 'PNG', optimize=True)
    best = buf.getvalue()

    # Caso sin perdida: la imagen ya cabe en 256 colores.
    lossless = img.getcolors(256) is not None
    if lossless or aggressive:
        try:
            pal = img.quantize(colors=256, method=Image.Quantize.FASTOCTREE)
            buf = io.BytesIO()
            pal.save(buf, 'PNG', optimize=True)
            candidate = buf.getvalue()
            if lossless and len(candidate) < len(best):
                best = candidate
            elif aggressive and len(candidate) < len(best) * 0.85:
                best = candidate
        except Exception:
            pass
    return best


def _jpg_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.convert('RGB').save(
        buf, 'JPEG', quality=JPEG_QUALITY, optimize=True, progressive=True,
    )
    return buf.getvalue()


def _resize(src: Image.Image, size: int) -> Image.Image:
    return src.resize((size, size), Image.LANCZOS)


def _on_background(src: Image.Image, size: int, rgb: tuple, ratio: float) -> Image.Image:
    """Coloca el logo centrado sobre un fondo opaco, ocupando `ratio` del lienzo."""
    canvas = Image.new('RGB', (size, size), rgb)
    inner = max(1, int(round(size * ratio)))
    logo = _resize(src, inner)
    offset = (size - inner) // 2
    canvas.paste(logo, (offset, offset), logo)
    return canvas


def _load_square(data: bytes) -> Image.Image:
    """Abre la imagen, la pasa a RGBA y la hace cuadrada anadiendo transparencia."""
    img = Image.open(io.BytesIO(data))
    img = img.convert('RGBA')
    if img.width != img.height:
        side = max(img.width, img.height)
        square = Image.new('RGBA', (side, side), (0, 0, 0, 0))
        square.paste(img, ((side - img.width) // 2, (side - img.height) // 2), img)
        img = square
    return img


# --- generacion ---------------------------------------------------------------

def build(source_png: bytes, opts: Options) -> list:
    src = _load_square(source_png)
    bg = _hex_to_rgb(opts.background)
    out = []

    # Logo original normalizado a 1024 (fuente de verdad para el proyecto).
    master = _resize(src, 1024) if src.width != 1024 else src
    out.append(Asset(
        'logo.png', _png_bytes(master, opts.aggressive), 1024, 1024,
        'origen', 'Logo original optimizado. Guardalo como fuente de verdad.',
    ))

    # Favicons sueltos.
    for size in FAVICON_SIZES:
        img = _resize(src, size)
        out.append(Asset(
            f'favicon-{size}.png', _png_bytes(img, opts.aggressive), size, size,
            'favicon', 'Favicon clasico con transparencia.',
        ))

    # favicon.ico multi-resolucion (para navegadores viejos y accesos directos).
    ico = io.BytesIO()
    _resize(src, 256).save(ico, 'ICO', sizes=[(s, s) for s in ICO_SIZES])
    out.append(Asset(
        'favicon.ico', ico.getvalue(), 48, 48, 'favicon',
        'Multi-resolucion (' + ', '.join(str(s) for s in ICO_SIZES) + '). Va en la raiz del sitio.',
    ))

    # Iconos "any" del manifest.
    for size in ICON_SIZES:
        img = _resize(src, size)
        out.append(Asset(
            f'icon-{size}.png', _png_bytes(img, opts.aggressive), size, size,
            'icono', 'Icono "any" del manifest (fondo transparente).',
        ))

    # Iconos maskable: fondo opaco y logo dentro de la zona segura del 80%.
    for size in MASKABLE_SIZES:
        img = _on_background(src, size, bg, MASKABLE_SAFE)
        out.append(Asset(
            f'maskable-{size}.png', _png_bytes(img, opts.aggressive), size, size,
            'maskable', 'Android recorta los bordes: el logo ocupa el 80% central.',
        ))

    # iOS: sin transparencia, sin esquinas redondeadas (las pone el sistema).
    apple = _on_background(src, APPLE_SIZE, bg, APPLE_PADDING)
    out.append(Asset(
        'apple-touch-icon.png', _png_bytes(apple, opts.aggressive),
        APPLE_SIZE, APPLE_SIZE, 'apple',
        'Pantalla de inicio de iOS. Fondo opaco obligatorio.',
    ))

    # Imagen social 1200x630 (Open Graph y Twitter summary_large_image).
    w, h = OG_SIZE
    canvas = Image.new('RGB', (w, h), bg)
    inner = int(round(h * 0.55))
    logo = _resize(src, inner)
    canvas.paste(logo, ((w - inner) // 2, (h - inner) // 2), logo)
    out.append(Asset(
        'og-image.jpg', _jpg_bytes(canvas), w, h, 'social',
        'Vista previa al compartir el enlace. Sirve tambien para Twitter/X.',
    ))

    # Textos de apoyo.
    manifest = build_manifest(opts)
    out.append(Asset(
        'manifest.webmanifest', manifest.encode('utf-8'), 0, 0, 'texto',
        'Manifest listo para usar. Ajusta start_url y las rutas si hace falta.',
    ))
    out.append(Asset(
        'snippet.html', build_snippet(opts).encode('utf-8'), 0, 0, 'texto',
        'Etiquetas para pegar dentro del <head>.',
    ))

    return out


def build_manifest(opts: Options) -> str:
    base = opts.icon_path.rstrip('/')
    icons = []
    for size in ICON_SIZES:
        icons.append({
            'src': f'{base}/icon-{size}.png',
            'sizes': f'{size}x{size}',
            'type': 'image/png',
            'purpose': 'any',
        })
    for size in MASKABLE_SIZES:
        icons.append({
            'src': f'{base}/maskable-{size}.png',
            'sizes': f'{size}x{size}',
            'type': 'image/png',
            'purpose': 'maskable',
        })

    manifest = {
        'name': opts.app_name,
        'short_name': opts.short_name,
        'start_url': opts.start_url,
        'scope': '/',
        'display': 'standalone',
        'background_color': opts.background,
        'theme_color': opts.theme,
        'icons': icons,
    }
    return json.dumps(manifest, indent=2, ensure_ascii=False) + '\n'


def build_snippet(opts: Options) -> str:
    base = opts.icon_path.rstrip('/')
    return f'''<!-- Iconos y metadatos - generado por BSTools BrandAssets -->
<link rel="icon" href="/favicon.ico" sizes="32x32">
<link rel="icon" type="image/png" sizes="16x16" href="{base}/favicon-16.png">
<link rel="icon" type="image/png" sizes="32x32" href="{base}/favicon-32.png">
<link rel="apple-touch-icon" href="{base}/apple-touch-icon.png">
<link rel="manifest" href="/manifest.webmanifest">
<meta name="theme-color" content="{opts.theme}">

<meta property="og:title" content="{opts.app_name}">
<meta property="og:description" content="">
<meta property="og:type" content="website">
<meta property="og:image" content="{base}/og-image.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{base}/og-image.jpg">
'''
