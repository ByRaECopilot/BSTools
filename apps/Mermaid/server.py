"""
Servidor local del editor Mermaid: sirve la interfaz y guarda/carga los
diagramas en la subcarpeta graphs/.

Parte de BSTools - https://www.byraesoftware.com
Licencia CC0 1.0 (dominio publico).

- Escucha solo en 127.0.0.1, en un puerto libre elegido al arrancar.
- Las rutas que tocan el disco (guardar, cargar, borrar, listar) exigen un token
  aleatorio, para que ningun otro proceso local pueda usarlas. Los archivos
  estaticos (editor.js, la libreria) se sirven sin token: no son sensibles.
- Cada diagrama se guarda en dos archivos dentro de graphs/:
    <nombre>.mmd          el codigo Mermaid (reutilizable en cualquier sitio)
    <nombre>.layout.json  posiciones, formas, colores y direccion del lienzo

Uso:  python server.py [diagrama.mmd]
"""

from __future__ import annotations

import json
import re
import secrets
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

TOOL_DIR = Path(__file__).resolve().parent
GRAPHS_DIR = TOOL_DIR / 'graphs'

TOKEN = secrets.token_urlsafe(16)
MAX_UPLOAD = 20 * 1024 * 1024   # margen sobrado para un diagrama grande

# Archivos estaticos que el servidor puede entregar sin token.
STATIC_FILES = {
    '/editor.js': 'application/javascript; charset=utf-8',
    '/vendor/mermaid.min.js': 'application/javascript; charset=utf-8',
    '/icon.ico': 'image/x-icon',
}


def safe_name(name: str) -> str:
    """Nombre de archivo sin sorpresas: nada de rutas ni caracteres raros."""
    name = (name or '').strip()
    name = re.sub(r'\.(mmd|layout\.json)$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', name)
    name = name.strip(' .')
    return name


class Handler(BaseHTTPRequestHandler):
    server_version = 'MermaidEditor'

    def log_message(self, fmt, *args):
        pass

    # --- infraestructura ------------------------------------------------------

    def _authorised(self) -> bool:
        if self.headers.get('X-Token') == TOKEN:
            return True
        return parse_qs(urlparse(self.path).query).get('t', [''])[0] == TOKEN

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

    # --- GET ------------------------------------------------------------------

    def do_GET(self):
        path = urlparse(self.path).path

        if path == '/':
            if not self._authorised():
                self._send(403, b'Token invalido', 'text/plain; charset=utf-8')
                return
            self._send(200, (TOOL_DIR / 'index.html').read_bytes(), 'text/html; charset=utf-8')
            return

        if path in STATIC_FILES:
            target = (TOOL_DIR / path.lstrip('/')).resolve()
            if TOOL_DIR in target.parents and target.is_file():
                self._send(200, target.read_bytes(), STATIC_FILES[path])
            else:
                self._send(404, b'No encontrado', 'text/plain; charset=utf-8')
            return

        if path == '/preload':
            if not self._authorised():
                self._json(403, {'error': 'token'}); return
            self._json(200, self.server.preload)
            return

        if path == '/list':
            if not self._authorised():
                self._json(403, {'error': 'token'}); return
            self._json(200, {'graphs': self._list_graphs()})
            return

        if path == '/load':
            if not self._authorised():
                self._json(403, {'error': 'token'}); return
            self._load(parse_qs(urlparse(self.path).query).get('name', [''])[0])
            return

        self._send(404, b'No encontrado', 'text/plain; charset=utf-8')

    # --- POST -----------------------------------------------------------------

    def do_POST(self):
        path = urlparse(self.path).path
        if not self._authorised():
            self._json(403, {'error': 'token'}); return

        if path == '/save':
            self._save()
        elif path == '/delete':
            self._delete()
        elif path == '/quit':
            self._json(200, {'ok': True})
            threading.Thread(target=self.server.shutdown, daemon=True).start()
        else:
            self._json(404, {'error': 'ruta desconocida'})

    # --- acciones -------------------------------------------------------------

    def _list_graphs(self):
        if not GRAPHS_DIR.is_dir():
            return []
        out = []
        for f in GRAPHS_DIR.glob('*.layout.json'):
            name = f.name[:-len('.layout.json')]
            out.append({'name': name, 'savedAt': int(f.stat().st_mtime)})
        out.sort(key=lambda g: g['savedAt'], reverse=True)
        return out

    def _save(self):
        try:
            data = self._read_json()
            name = safe_name(data.get('name'))
            mmd = str(data.get('mmd') or '')
            state = data.get('state')
        except Exception as exc:
            self._json(400, {'error': str(exc)}); return

        if not name:
            self._json(400, {'error': 'Indica un nombre valido para el diagrama.'}); return
        if not isinstance(state, dict):
            self._json(400, {'error': 'Falta el estado del diagrama.'}); return

        GRAPHS_DIR.mkdir(parents=True, exist_ok=True)
        layout = {
            'tool': 'BSTools Mermaid',
            'version': 2,
            'name': name,
            'savedAt': time.strftime('%Y-%m-%dT%H:%M:%S'),
            'state': state,
        }
        try:
            (GRAPHS_DIR / f'{name}.mmd').write_text(mmd, encoding='utf-8')
            (GRAPHS_DIR / f'{name}.layout.json').write_text(
                json.dumps(layout, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as exc:
            self._json(400, {'error': f'No se pudo guardar: {exc}'}); return

        print(f'  Guardado: graphs/{name}.mmd  (+ .layout.json)', flush=True)
        self._json(200, {'ok': True, 'name': name, 'graphs': self._list_graphs()})

    def _load(self, raw_name):
        name = safe_name(raw_name)
        if not name:
            self._json(400, {'error': 'Nombre no valido.'}); return
        layout_file = GRAPHS_DIR / f'{name}.layout.json'
        mmd_file = GRAPHS_DIR / f'{name}.mmd'
        if not layout_file.is_file():
            self._json(404, {'error': f'No existe el diagrama "{name}".'}); return
        try:
            layout = json.loads(layout_file.read_text(encoding='utf-8'))
            mmd = mmd_file.read_text(encoding='utf-8') if mmd_file.is_file() else ''
        except Exception as exc:
            self._json(400, {'error': f'No se pudo leer: {exc}'}); return
        self._json(200, {'name': name, 'mmd': mmd, 'state': layout.get('state')})

    def _delete(self):
        try:
            name = safe_name((self._read_json() or {}).get('name'))
        except Exception as exc:
            self._json(400, {'error': str(exc)}); return
        if not name:
            self._json(400, {'error': 'Nombre no valido.'}); return
        removed = 0
        for suffix in ('.mmd', '.layout.json'):
            f = GRAPHS_DIR / f'{name}{suffix}'
            if f.is_file():
                try:
                    f.unlink(); removed += 1
                except Exception:
                    pass
        self._json(200, {'ok': True, 'removed': removed, 'graphs': self._list_graphs()})


def build_preload(argv):
    """Si se abre con un .mmd como argumento, se precarga en el editor. Si al lado
    hay un .layout.json con el mismo nombre, se restauran tambien las posiciones."""
    if len(argv) <= 1:
        return {}
    source = Path(argv[1]).resolve()
    if not source.is_file():
        return {}
    try:
        pre = {'name': source.stem, 'mmd': source.read_text(encoding='utf-8')}
    except Exception:
        return {}
    layout = source.with_name(source.stem + '.layout.json')
    if layout.is_file():
        try:
            pre['state'] = json.loads(layout.read_text(encoding='utf-8')).get('state')
        except Exception:
            pass
    return pre


def main():
    httpd = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    httpd.preload = build_preload(sys.argv)
    port = httpd.server_address[1]
    url = f'http://127.0.0.1:{port}/?t={TOKEN}'

    print()
    print('  Mermaid - editor grafico - BSTools')
    print(f'  Servidor local en {url}')
    print(f'  Los diagramas se guardan en: {GRAPHS_DIR}')
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
