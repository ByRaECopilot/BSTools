"""
Servidor local de BrandAssets: sirve la interfaz web y hace de puente entre el
navegador y el disco.

Parte de BSTools - https://www.byraesoftware.com
Licencia CC0 1.0 (dominio publico).

- Escucha solo en 127.0.0.1, en un puerto libre elegido al arrancar.
- Exige un token aleatorio en cada peticion, para que ningun otro proceso local
  pueda pedirle que escriba archivos.
- No sale nada a Internet: la imagen se procesa aqui mismo.

Uso:  python server.py [imagen.png]
"""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TOOL_DIR = Path(__file__).resolve().parent

try:
    from PIL import Image  # noqa: F401  (solo para comprobar que esta)
except ImportError:
    print()
    print('  Falta Pillow. Instalalo con:')
    print('    pip install Pillow')
    print()
    sys.exit(2)

import assets as ga

TOKEN = secrets.token_urlsafe(16)
MAX_UPLOAD = 30 * 1024 * 1024   # 30 MB de margen sobrado para un PNG 1024

# Ultimo juego de assets generado, para no reenviar los bytes al exportar.
_last = {'items': []}
_lock = threading.Lock()


def _safe_folder_name(name: str) -> str:
    """Nombre de subcarpeta sin sorpresas: nada de rutas ni caracteres raros."""
    name = (name or '').strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    name = name.strip(' .')
    return name


class Handler(BaseHTTPRequestHandler):
    server_version = 'BrandAssets'

    # --- infraestructura ------------------------------------------------------

    def log_message(self, fmt, *args):
        pass  # la consola solo muestra lo que interesa al usuario

    def _authorised(self) -> bool:
        if self.headers.get('X-Token') == TOKEN:
            return True
        query = parse_qs(urlparse(self.path).query)
        return query.get('t', [''])[0] == TOKEN

    def _send(self, code, body: bytes, mime='application/json; charset=utf-8'):
        self.send_response(code)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def _json(self, code, payload):
        self._send(code, json.dumps(payload, ensure_ascii=False).encode('utf-8'))

    def _read_json(self):
        length = int(self.headers.get('Content-Length') or 0)
        if length <= 0 or length > MAX_UPLOAD:
            return None
        return json.loads(self.rfile.read(length).decode('utf-8'))

    # --- rutas ----------------------------------------------------------------

    def do_GET(self):
        path = self.path.split('?')[0]

        if path == '/':
            if not self._authorised():
                self._send(403, b'Token invalido', 'text/plain; charset=utf-8')
                return
            html = (TOOL_DIR / 'ui.html').read_bytes()
            self._send(200, html, 'text/html; charset=utf-8')
            return

        if path == '/preload':
            if not self._authorised():
                self._json(403, {'error': 'token'})
                return
            self._json(200, self.server.preload)
            return

        self._send(404, b'No encontrado', 'text/plain; charset=utf-8')

    def do_POST(self):
        path = self.path.split('?')[0]

        if not self._authorised():
            self._json(403, {'error': 'token'})
            return

        if path == '/generate':
            self._generate()
        elif path == '/export':
            self._export()
        elif path == '/quit':
            self._json(200, {'ok': True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self._json(404, {'error': 'ruta desconocida'})

    # --- acciones -------------------------------------------------------------

    def _generate(self):
        try:
            data = self._read_json()
            image = base64.b64decode(data['image'])
            opts = ga.Options(
                app_name=data.get('app_name') or 'Mi aplicacion',
                short_name=data.get('short_name') or 'MiApp',
                background=data.get('background') or '#ffffff',
                theme=data.get('theme') or '#111111',
                start_url=data.get('start_url') or '/',
                icon_path=data.get('icon_path') or '/icons',
                aggressive=bool(data.get('aggressive')),
            )
            items = ga.build(image, opts)
        except Exception as exc:
            self._json(400, {'error': f'{type(exc).__name__}: {exc}'})
            return

        with _lock:
            _last['items'] = items

        payload = [{
            'name': a.name,
            'kind': a.kind,
            'note': a.note,
            'width': a.width,
            'height': a.height,
            'bytes': a.size,
            'mime': a.mime,
            'data': base64.b64encode(a.data).decode('ascii'),
        } for a in items]
        self._json(200, {'assets': payload})

    def _export(self):
        try:
            data = self._read_json()
            base = Path(os.path.expandvars(str(data.get('folder') or ''))).expanduser()
            name = _safe_folder_name(data.get('name'))
        except Exception as exc:
            self._json(400, {'error': str(exc)})
            return

        if not name:
            self._json(400, {'error': 'Indica un nombre de subcarpeta valido.'})
            return

        with _lock:
            items = list(_last['items'])
        if not items:
            self._json(400, {'error': 'No hay nada generado todavia.'})
            return

        target = (base / name).resolve()
        try:
            target.mkdir(parents=True, exist_ok=True)
            for asset in items:
                (target / asset.name).write_bytes(asset.data)
        except Exception as exc:
            self._json(400, {'error': f'No se pudo escribir en {target}: {exc}'})
            return

        total = sum(a.size for a in items)
        print(f'  Exportados {len(items)} archivos en {target}')
        self._json(200, {
            'folder': str(target),
            'count': len(items),
            'bytes': total,
        })


def main():
    preload = {}
    if len(sys.argv) > 1:
        source = Path(sys.argv[1]).resolve()
        if source.is_file():
            try:
                preload = {
                    'name': source.name,
                    'folder': str(source.parent),
                    'data': base64.b64encode(source.read_bytes()).decode('ascii'),
                }
            except Exception:
                preload = {}

    if not preload:
        preload = {'folder': str(TOOL_DIR / 'salida')}

    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    httpd.preload = preload
    port = httpd.server_address[1]
    url = f'http://127.0.0.1:{port}/?t={TOKEN}'

    print()
    print('  BrandAssets - BSTools')
    print(f'  Servidor local en {url}')
    print('  Cierra esta ventana o pulsa Ctrl+C para terminar.')
    print(flush=True)

    threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    print('  Servidor detenido.')


if __name__ == '__main__':
    main()
