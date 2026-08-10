"""CASCARA servidor: modo `--serve`, HTTP local en `/api/v1` (lote 6).

Segunda cascara hermana de `app.py` (lote 3, todavia no existe) -- las dos
"exponen" el mismo motor y la misma orquestacion (`jobs.py`), nunca lo
reimplementan (ADR-0001 D11/D18, ARCHITECTURE.md Sec.2/6/13). Este archivo es
la prueba de falsacion de las tres capas: si escribirlo hubiera exigido tocar
`transcribe.py`, `fetch.py`, `export.py` o `models.py`, el desacople habria
sido decorativo. No los toca -- solo los importa y llama a sus funciones
publicas, igual que hace `jobs.py`.

Reglas de este archivo, todas de ARCHITECTURE.md Sec.6.2/9 y ADR-0001:

- Solo biblioteca estandar (`http.server`). Nada de Flask/FastAPI: mismo
  patron que `apps/BrandAssets/server.py` y `apps/Mermaid/server.py`.
- Escucha SOLO en 127.0.0.1. Puerto FIJO (por defecto 8317, `settings.json` o
  `--port`); si esta ocupado, mensaje y salida -- nunca se busca otro puerto
  (D23).
- Arranque MANUAL y en primer plano. Sin servicio, sin tarea programada, sin
  arranque con la sesion de Windows (D24). Se apaga cerrando la consola o con
  Ctrl+C.
- Token aleatorio por arranque en `serve-token.txt`, exigido en TODAS las
  peticiones (incluida `/health`) por CABECERA `X-Token` -- nunca en la URL:
  quedaria en el historial del navegador y en logs de proxy/servidor, a
  diferencia de BrandAssets/Mermaid, que si aceptan `?t=` porque abren un
  navegador. Aqui no hay navegador: solo header.
- Cerrojo exclusivo de proceso (`jobs.acquire_runtime_lock`): nunca dos
  procesos con el modelo en RAM (D21). Un segundo intento -- en cualquier
  direccion, ventana u otro servidor -- termina con un mensaje claro y un
  codigo de salida distinto de cero, nunca un fallo mudo (Sec.6.4).
- Los errores del nucleo son codigos + datos (D10): este archivo los traduce a
  status HTTP (`_ERROR_HTTP_STATUS`), pero el cuerpo JSON sigue siendo
  `{"error": {"code": ..., "details": {...}}}` -- nunca un texto en castellano
  pensado para pantalla. Ese texto es trabajo de quien consuma la API (el bot).
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import export
import fetch
import jobs
import models
import settings as config
import transcribe
from errors import CoreError, ErrorCode, one_line

TOOL_DIR = Path(__file__).resolve().parent
MODELS_DIR = TOOL_DIR / "models"
WORK_DIR = TOOL_DIR / "work"
TOKEN_PATH = TOOL_DIR / "serve-token.txt"

API_VERSION = "v1"
# Provisional: todavia no hay un archivo de version en el repo (llega en el
# lote 5, con install.ps1/README.md). No se inventa un esquema de versiones
# nuevo aqui -- es solo el numero que anuncia /health mientras tanto.
CORE_VERSION = "1.0.0-dev"

_API_PREFIX = "/api/v1"

_RE_JOB = re.compile(r"^/api/v1/jobs/(?P<job_id>[^/]+)$")
_RE_JOB_CANCEL = re.compile(r"^/api/v1/jobs/(?P<job_id>[^/]+)/cancel$")
_RE_JOB_RESULT = re.compile(r"^/api/v1/jobs/(?P<job_id>[^/]+)/result$")
_RE_MODEL_DOWNLOAD = re.compile(r"^/api/v1/models/(?P<model_id>[^/]+)/download$")
_RE_MODEL = re.compile(r"^/api/v1/models/(?P<model_id>[^/]+)$")

# Traduccion codigo->HTTP (ARCHITECTURE.md Sec.5.4/6.3): 202 encolado, 400
# invalida, 403 token, 404 desconocido, 413 grande, 429 queue_full, 507
# disk_full, 500 interno. NUNCA 409: con cola FIFO estar ocupado no es error.
# La mayoria de estos codigos en realidad viajan dentro de `job.error` (Sec.4.2,
# HTTP 200: el recurso "trabajo" SI se encontro, el fallo es dato) -- esta
# tabla solo se usa para los pocos que `jobs.py` puede levantar de forma
# SINCRONA al encolar (ver docstrings de `submit_transcription`/`_enqueue`).
_ERROR_HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.UNSUPPORTED_URL: 400,
    ErrorCode.LOGIN_REQUIRED: 400,
    ErrorCode.GEO_BLOCKED: 400,
    ErrorCode.MEDIA_UNAVAILABLE: 400,
    ErrorCode.DOWNLOAD_FAILED: 400,
    ErrorCode.EXTRACTOR_OUTDATED: 400,
    ErrorCode.NO_AUDIO_STREAM: 400,
    ErrorCode.DECODE_FAILED: 400,
    ErrorCode.FILE_TOO_LARGE: 413,
    ErrorCode.FILE_NOT_FOUND: 400,
    ErrorCode.MODEL_MISSING: 400,
    ErrorCode.MODEL_DOWNLOAD_FAILED: 400,
    ErrorCode.DISK_FULL: 507,
    ErrorCode.QUEUE_FULL: 429,
    ErrorCode.CANCELLED: 400,
    ErrorCode.INTERNAL: 500,
    ErrorCode.GPU_LIBRARIES_MISSING: 400,
    ErrorCode.GPU_OUT_OF_MEMORY: 400,
    ErrorCode.GPU_UNAVAILABLE: 400,
    ErrorCode.COOKIES_BROWSER_NOT_FOUND: 400,
    ErrorCode.COOKIES_BROWSER_LOCKED: 400,
    ErrorCode.COOKIES_EXPIRED: 400,
}

_MAX_BODY_BYTES = 1 * 1024 * 1024  # 1 MiB: solo JSON de metadatos, nunca el medio


# --------------------------------------------------------------------- consola

def _print(message: str = "") -> None:
    print(message, flush=True)


def _timestamp() -> str:
    return time.strftime("%H:%M:%S")


def _format_mmss(seconds: float | None) -> str:
    if not seconds:
        return "0:00"
    total = int(round(seconds))
    minutes, secs = divmod(total, 60)
    return f"{minutes}:{secs:02d}"


def _log_job_received(state: dict) -> None:
    job_id = state["job_id"]
    if state["kind"] == "model_download":
        name = state["source"].get("display_name") or "?"
        _print(f"  [{_timestamp()}] trabajo {job_id} recibido - descarga de modelo {name}")
        return
    name = state["source"].get("display_name") or "?"
    duration = _format_mmss(state.get("media_duration_seconds"))
    _print(f"  [{_timestamp()}] trabajo {job_id} recibido - {name} ({duration})")


def _log_job_finished(state: dict) -> None:
    job_id = state["job_id"]
    if state["state"] == "error":
        code = (state.get("error") or {}).get("code", "internal")
        _print(f"  [{_timestamp()}] trabajo {job_id} termino con error [{code}]")
        return
    if state["state"] == "cancelled":
        _print(f"  [{_timestamp()}] trabajo {job_id} cancelado")
        return
    if state["kind"] == "model_download":
        _print(f"  [{_timestamp()}] trabajo {job_id} terminado - modelo descargado")
        return
    result = state.get("result") or {}
    chars = result.get("character_count", 0)
    elapsed = result.get("elapsed_seconds", 0.0)
    _print(f"  [{_timestamp()}] trabajo {job_id} terminado - {chars} caracteres, {elapsed:.0f} s")


def _watch_job(job_manager: jobs.JobManager, job_id: str) -> None:
    """Hilo corto y desechable, uno por trabajo encolado: espera a que termine
    para imprimir el resultado en la consola (Sec.6.2, "se ve que avanza" para
    quien esta sentado delante). No sustituye el sondeo HTTP del cliente real
    (el bot): es solo la vista de quien mira la ventana del servidor.
    """
    while True:
        try:
            state = job_manager.get_job(job_id)
        except KeyError:
            return
        if state["state"] in ("done", "error", "cancelled"):
            _log_job_finished(state)
            return
        time.sleep(1.0)


# --------------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = "Voice2Text/1"

    def log_message(self, fmt, *args) -> None:  # noqa: A002 - firma exigida por BaseHTTPRequestHandler
        pass  # la consola solo muestra las lineas de trabajo (_log_job_received/_log_job_finished)

    # -- infraestructura ----------------------------------------------------

    @property
    def _job_manager(self) -> jobs.JobManager:
        return self.server.job_manager  # type: ignore[attr-defined]

    @property
    def _settings(self) -> dict:
        return self.server.settings  # type: ignore[attr-defined]

    def _authorized(self) -> bool:
        header = self.headers.get("X-Token", "")
        if not header:
            return False
        return secrets.compare_digest(header, self.server.token)  # type: ignore[attr-defined]

    def _send(self, code: int, body: bytes, mime: str = "application/json; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError):
            pass

    def _json(self, code: int, payload) -> None:
        self._send(code, json.dumps(payload, ensure_ascii=False).encode("utf-8"))

    def _error(self, code: int, error_code: str, details: dict | None = None, technical: str | None = None) -> None:
        body: dict = {"code": error_code, "details": details or {}}
        if technical:
            body["technical"] = technical
        self._json(code, {"error": body})

    def _forbidden(self) -> None:
        self._error(403, "invalid_token")

    def _not_found(self, details: dict) -> None:
        self._error(404, "not_found", details)

    def _bad_request(self, exc) -> None:
        self._error(400, "bad_request", technical=str(exc))

    def _core_error(self, err: CoreError) -> None:
        status = _ERROR_HTTP_STATUS.get(err.code, 500)
        # Formato del contrato (ARCHITECTURE.md Sec.5.4): code + details, SIN
        # texto de pantalla. `technical` no viaja aqui a proposito -- es para
        # depurar desde consola/logs, no parte del contrato publico de error.
        self._json(status, {"error": {"code": err.code.value, "details": err.details}})

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        if length > _MAX_BODY_BYTES:
            return None
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    # -- rutas ----------------------------------------------------------------

    def do_GET(self) -> None:
        if not self._authorized():
            self._forbidden()
            return
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == f"{_API_PREFIX}/health":
            self._health()
            return
        if path == f"{_API_PREFIX}/models":
            self._list_models()
            return

        match = _RE_JOB_RESULT.match(path)
        if match:
            fmt = (query.get("format") or ["txt"])[0]
            self._get_result(match.group("job_id"), fmt)
            return

        match = _RE_JOB.match(path)
        if match:
            since_raw = (query.get("since") or [None])[0]
            since = int(since_raw) if since_raw is not None and since_raw.lstrip("-").isdigit() else None
            self._get_job(match.group("job_id"), since)
            return

        self._not_found({"path": path})

    def do_POST(self) -> None:
        if not self._authorized():
            self._forbidden()
            return
        path = urlparse(self.path).path

        if path == f"{_API_PREFIX}/jobs":
            self._submit_job()
            return

        match = _RE_JOB_CANCEL.match(path)
        if match:
            self._cancel_job(match.group("job_id"))
            return

        match = _RE_MODEL_DOWNLOAD.match(path)
        if match:
            self._download_model(match.group("model_id"))
            return

        self._not_found({"path": path})

    def do_DELETE(self) -> None:
        if not self._authorized():
            self._forbidden()
            return
        path = urlparse(self.path).path

        match = _RE_MODEL.match(path)
        if match:
            self._delete_model(match.group("model_id"))
            return

        match = _RE_JOB.match(path)
        if match:
            self._forget_job(match.group("job_id"))
            return

        self._not_found({"path": path})

    # -- health / catalogo ------------------------------------------------------

    def _health(self) -> None:
        if fetch.is_available():
            try:
                version, age_days = fetch.ytdlp_version()
                yt_dlp_info = {"available": True, "version": version, "age_days": age_days}
            except CoreError as err:
                yt_dlp_info = {"available": True, "version": None, "age_days": None, "technical": err.technical}
        else:
            yt_dlp_info = {"available": False, "version": None, "age_days": None}

        self._json(200, {
            "api_version": API_VERSION,
            "core_version": CORE_VERSION,
            "yt_dlp": yt_dlp_info,
            "models_installed": models.installed(MODELS_DIR),
            "model_loaded": self._job_manager.loaded_model(),
        })

    def _list_models(self) -> None:
        installed_map = models.installed(MODELS_DIR)
        entries = []
        for model_id, spec in models.CATALOG.items():
            entries.append({
                "model_id": model_id,
                "repo_id": spec.repo_id,
                "expected_bytes": spec.expected_bytes,
                "params_millions": spec.params_millions,
                "quality_rank": spec.quality_rank,
                "vram_peak_mb": dict(spec.vram_peak_mb),
                "speed_ratio": dict(spec.speed_ratio),
                "installed": model_id in installed_map,
                "installed_bytes": installed_map.get(model_id, 0),
            })
        self._json(200, {"models": entries, "total_bytes": models.total_size(MODELS_DIR)})

    def _download_model(self, model_id: str) -> None:
        try:
            job_id, position = self._job_manager.submit_model_download(model_id)
        except ValueError as exc:
            self._bad_request(exc)
            return
        except CoreError as err:
            self._core_error(err)
            return
        self._json(202, {"job_id": job_id, "queue_position": position})
        _log_job_received(self._job_manager.get_job(job_id))
        threading.Thread(target=_watch_job, args=(self._job_manager, job_id), daemon=True).start()

    def _delete_model(self, model_id: str) -> None:
        if model_id not in models.CATALOG:
            self._not_found({"model_id": model_id})
            return
        try:
            freed = models.delete_model(model_id, MODELS_DIR)
        except OSError as exc:
            # models.py documenta que no traduce E/S a CoreError (sin codigo
            # cerrado para "no se pudo borrar"): se deja como 500 generico.
            self._error(500, "internal", technical=one_line(str(exc)))
            return
        self._json(200, {"bytes_freed": freed})

    # -- trabajos -----------------------------------------------------------

    def _submit_job(self) -> None:
        try:
            body = self._read_json()
        except (ValueError, UnicodeDecodeError) as exc:
            self._bad_request(exc)
            return
        if body is None:
            self._bad_request("cuerpo vacio o mayor que 1 MiB")
            return

        source = body.get("source")
        options = body.get("options") or {}
        if not isinstance(source, dict):
            self._bad_request(
                "falta 'source' (objeto: {'kind': 'file', 'path': ...} o {'kind': 'url', 'url': ...})"
            )
            return

        if source.get("kind") == "url":
            # D26: player_clients (y, desde el encargo del 2026-08-10,
            # cookies_from_browser) SIEMPRE salen de settings.json, nunca los
            # escribe quien llama -- un bot no tiene por que conocer este detalle
            # de yt-dlp. Si el cliente ya los trae explicitos en `options`, se
            # respetan.
            options = dict(options)
            options.setdefault("player_clients", self._settings.get("youtube_player_clients"))
            options.setdefault("max_input_bytes", self._settings.get("max_input_bytes"))
            options.setdefault("cookies_from_browser", self._settings.get("youtube_cookies_from_browser"))

        try:
            job_id, position = self._job_manager.submit_transcription(source, options)
        except ValueError as exc:
            self._bad_request(exc)
            return
        except CoreError as err:
            self._core_error(err)
            return

        self._json(202, {"job_id": job_id, "queue_position": position})
        _log_job_received(self._job_manager.get_job(job_id))
        threading.Thread(target=_watch_job, args=(self._job_manager, job_id), daemon=True).start()

    def _get_job(self, job_id: str, since: int | None) -> None:
        try:
            state = self._job_manager.get_job(job_id, since=since)
        except KeyError:
            self._not_found({"job_id": job_id})
            return
        self._json(200, state)

    def _cancel_job(self, job_id: str) -> None:
        try:
            cancelled = self._job_manager.cancel_job(job_id)
        except KeyError:
            self._not_found({"job_id": job_id})
            return
        self._json(200, {"cancelled": cancelled})

    def _forget_job(self, job_id: str) -> None:
        try:
            self._job_manager.forget_job(job_id)
        except KeyError:
            self._not_found({"job_id": job_id})
            return
        except ValueError as exc:
            self._bad_request(exc)
            return
        self._json(200, {"ok": True})

    def _get_result(self, job_id: str, fmt: str) -> None:
        if fmt not in ("txt", "md"):
            self._bad_request(f"format debe ser 'txt' o 'md', no {fmt!r}")
            return
        try:
            # since=0: `JobManager.get_job` solo adjunta `new_segments` cuando
            # se pide `since` -- con 0 devuelve TODOS los segmentos (indices
            # >= 0), sin que haga falta un metodo nuevo en jobs.py para leerlos
            # completos.
            state = self._job_manager.get_job(job_id, since=0)
        except KeyError:
            self._not_found({"job_id": job_id})
            return

        if state["kind"] != "transcription" or state["state"] != "done":
            self._error(400, "result_not_ready", {"kind": state["kind"], "state": state["state"]})
            return

        segments = [
            transcribe.Segment(
                index=seg["index"], start=seg["start"], end=seg["end"],
                speech_end=seg["speech_end"], text=seg["text"],
            )
            for seg in (state.get("new_segments") or [])
        ]
        device_used = state.get("device_used") or {}
        result = state.get("result") or {}
        source_info = state.get("source") or {}
        meta = {
            "title": Path(source_info["display_name"]).stem if source_info.get("display_name") else None,
            "source": source_info.get("path"),
            "media_duration_seconds": state.get("media_duration_seconds"),
            "language": result.get("language"),
            "language_probability": result.get("language_probability"),
            "model_id": (state.get("options") or {}).get("model_id"),
            "compute_type": device_used.get("compute_type"),
            "device": device_used.get("device"),
            "transcribed_at": state.get("finished_at"),
        }

        if fmt == "txt":
            text = export.to_plain_text(segments)
            mime = "text/plain; charset=utf-8"
        else:
            text = export.to_markdown(segments, meta)
            mime = "text/markdown; charset=utf-8"

        self._send(200, text.encode("utf-8"), mime)


# --------------------------------------------------------------------- arranque

def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Voice2Text - modo servidor (ARCHITECTURE.md Sec.6.2/9). Arranque manual, primer plano.",
    )
    parser.add_argument("--port", type=int, default=None, help="por defecto, settings.json/serve_port (8317)")
    return parser.parse_args(argv)


def _print_banner(port: int, token_path: Path, idle_timeout_seconds: float) -> None:
    _print()
    _print("  Voice2Text - Modo servidor")
    _print(f"  Escuchando en http://127.0.0.1:{port}")
    _print(f"  Token en: {token_path}")
    _print(f"  El modelo de cada trabajo se carga al primer uso y se libera tras {int(idle_timeout_seconds)}s sin trabajos.")
    _print("  Cierra esta ventana o pulsa Ctrl+C para apagar.")
    _print()


def _print_lock_conflict(info: dict) -> None:
    _print()
    _print("  Voice2Text ya esta corriendo.")
    mode = info.get("mode") or "desconocido"
    pid = info.get("pid", "?")
    started = info.get("started_at", "?")
    if mode == "window":
        _print(f"  Hay una ventana abierta (PID {pid}, desde {started}).")
        _print("  Cierrala para poder usar el modo servidor.")
    else:
        port = info.get("port", "?")
        _print(f"  Ya hay un servidor escuchando en el puerto {port} (PID {pid}, desde {started}).")
        _print("  Cierra esa ventana o pulsa Ctrl+C ahi para apagarlo.")
    _print()


def _purge_work_dir_fully(work_dir: Path) -> None:
    """D15: al apagar el servidor se purga TODO `work/` -- a diferencia del
    arranque, que solo purga lo mas viejo que `work_retention_hours`.
    """
    if not work_dir.exists():
        return
    for entry in work_dir.iterdir():
        try:
            if entry.is_file():
                entry.unlink()
        except OSError:
            continue


def _graceful_shutdown(job_manager: jobs.JobManager) -> None:
    running_id = job_manager.running_job_id()
    if running_id:
        _print(f"  Cancelando el trabajo en curso ({running_id})...")
        job_manager.cancel_job(running_id)
        # Cancelar lo que corre tarda "hasta ~30s" (ARCHITECTURE.md Sec.4.1):
        # se espera un poco mas antes de soltar el modelo y purgar work/.
        deadline = time.monotonic() + 35.0
        while time.monotonic() < deadline:
            try:
                state = job_manager.get_job(running_id)
            except KeyError:
                break
            if state["state"] in ("done", "error", "cancelled"):
                break
            time.sleep(0.5)

    job_manager.shutdown(wait=True)
    _purge_work_dir_fully(WORK_DIR)
    _print("  work/ purgado.")


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    args = _parse_args(sys.argv[1:] if argv is None else argv)
    resolved_settings = config.load()
    port = args.port if args.port is not None else resolved_settings["serve_port"]

    job_manager = jobs.JobManager(
        models_dir=MODELS_DIR,
        tool_dir=TOOL_DIR,
        max_queued_jobs=resolved_settings["max_queued_jobs"],
        model_idle_timeout_seconds=resolved_settings["model_idle_timeout_seconds"],
        work_retention_hours=resolved_settings["work_retention_hours"],
    )

    # Cerrojo ANTES de tocar el puerto o arrancar el trabajador (Sec.6.4/D21):
    # nunca dos procesos con el modelo en RAM, y nunca un fallo mudo.
    try:
        job_manager.acquire_runtime_lock(mode="server", port=port)
    except jobs.RuntimeLockError as exc:
        _print_lock_conflict(exc.info)
        return 1

    token = secrets.token_urlsafe(32)
    TOKEN_PATH.write_text(token, encoding="ascii")

    try:
        httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except OSError as exc:
        _print(f"  No se pudo abrir el puerto {port}: {exc}")
        _print(f"  Elige otro con --port, o libera el puerto {port} y reintenta. (D23: nunca se busca otro puerto solo)")
        job_manager.release_runtime_lock()
        return 1

    httpd.job_manager = job_manager  # type: ignore[attr-defined]
    httpd.token = token  # type: ignore[attr-defined]
    httpd.settings = resolved_settings  # type: ignore[attr-defined]

    job_manager.start()
    _print_banner(port, TOKEN_PATH, resolved_settings["model_idle_timeout_seconds"])

    try:
        httpd.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        _print()
        _print("  Apagando...")
        httpd.server_close()
        _graceful_shutdown(job_manager)
        _print("  Servidor detenido.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
