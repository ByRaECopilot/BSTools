"""CASCARA ventana: app.py (ARCHITECTURE.md Sec.2/6.1, lote 3).

Unica capa que sabe de `webview`, de Windows y de castellano (junto con
`messages.py`, que es donde vive el castellano de verdad). Este archivo:

  - crea la ventana con pywebview y le da un `storage_path` PROPIO (Sec.6.1):
    sin esto la ventana puede no abrir en una maquina donde ya vive MDViewer
    (medido, E_ABORT / 0x80004004) -- es requisito de arranque, no un detalle.
  - expone a `ui.html` las operaciones de Sec.6.3 (mas un puñado de utilidades
    propias de la cascara -- ver el bloque "operaciones extra" mas abajo, todas
    de solo lectura o de UI, ninguna reimplementa politica del nucleo).
  - traduce SIEMPRE via `messages.py`: ninguna cadena de pantalla se compone
    aqui a mano.
  - NUNCA reescribe `jobs.py`, `transcribe.py`, `models.py`, `fetch.py` ni
    `export.py`: los importa y llama a sus funciones publicas, exactamente
    igual que hace `serve.py` (lote 6) -- incluidas las lecturas sincronas
    (`fetch.probe`, `models.installed`, `transcribe.probe_devices`) que ese
    archivo YA hace directamente sin pasar por `jobs.py`: encolar/orquestar es
    lo unico que le corresponde en exclusiva a `jobs.py` (ARCHITECTURE.md Sec.2).

`start_transcription()` acepta un origen `file` o `url` por igual: `jobs.py` es
quien encola y orquesta la descarga (fase `fetching`) antes de transcribir, esta
cascara no reimplementa nada de eso. `ui.html` es quien compone `options` para
un origen de enlace -- incluidos `player_clients` y `max_input_bytes`, leidos de
`App.ctx.settings` (que ya trae TODAS las claves de `settings.py`, ADR-0001
D26) -- exactamente igual que ya hace hoy con `device_preference`/`vad_filter`
para un archivo local: esta cascara Python no necesita inyectar nada aparte.
"""
from __future__ import annotations

import ctypes
import json
import logging
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import Any, Callable, Optional

import av

import fetch
import jobs
import messages
import models
import settings as config
import transcribe
from errors import CoreError, ErrorCode, one_line

TOOL_DIR = Path(__file__).resolve().parent
MODELS_DIR = TOOL_DIR / "models"
WEBVIEW_STORAGE_DIR = TOOL_DIR / "webview"  # Sec.6.1: perfil PROPIO, obligatorio
UI_PATH = TOOL_DIR / "ui.html"

WINDOW_TITLE = "Voice2Text"
MIN_SIZE = (760, 560)      # UI-SPEC.md Sec.16
INITIAL_SIZE = (960, 680)  # UI-SPEC.md Sec.16

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _show_native_dialog(title: str, body: str) -> None:
    """Dialogo nativo de Windows ANTES de `webview.start()` (Sec.5/6.4): la
    ventana no llega a abrirse, asi que no hay `ui.html` que pueda pintar esto.
    Un solo boton ("Entendido"): es informacion, no una eleccion.
    """
    MB_OK = 0x00000000
    MB_ICONINFORMATION = 0x00000040
    MB_TOPMOST = 0x00040000
    ctypes.windll.user32.MessageBoxW(0, body, title, MB_OK | MB_ICONINFORMATION | MB_TOPMOST)


def _disk_free_bytes(path: Path) -> int:
    probe_dir = path if path.exists() else path.parent
    try:
        return shutil.disk_usage(probe_dir).free
    except OSError:
        return 0


def _safe(fn: Callable[..., Any]) -> Callable[..., dict[str, Any]]:
    """Envuelve cada operacion expuesta a `ui.html`: pywebview solo entrega a la
    promesa de JS un `str(exception)` plano si algo revienta (perdiendo `code` y
    `details`), asi que aqui se atrapa TODO y se devuelve siempre la misma forma:
    `{"data": ...}` o `{"error": {"code", "details", "technical"}}`. `ui.html`
    nunca ve una excepcion cruda de Python.
    """

    def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            return {"data": fn(*args, **kwargs)}
        except CoreError as err:
            return {"error": {"code": err.code.value, "details": err.details, "technical": err.technical}}
        except (KeyError, ValueError) as exc:
            return {"error": {"code": "internal", "details": {}, "technical": one_line(str(exc))}}
        except Exception as exc:  # nunca una excepcion cruda hasta la ventana
            logger.exception("fallo inesperado en una operacion expuesta a la ventana")
            return {"error": {"code": "internal", "details": {}, "technical": one_line(str(exc))}}

    wrapper.__name__ = getattr(fn, "__name__", "wrapped")
    return wrapper


class Api:
    """Todo lo que `ui.html` puede llamar (`window.pywebview.api.<metodo>`).

    Las NUEVE operaciones de ARCHITECTURE.md Sec.6.3 estan todas aqui, mas un
    grupo pequeño de utilidades de cascara (carpeta de destino, ajustes, abrir
    el explorador...) que no tocan la politica del nucleo -- se marcan como
    tales en su propio docstring.
    """

    def __init__(self, job_manager: jobs.JobManager, resolved_settings: dict[str, Any], initial_source_path: Optional[str]):
        self._jobs = job_manager
        self._settings = resolved_settings
        self._initial_source_path = initial_source_path
        self._window = None  # se asigna tras crear la ventana (bind_window)

    def bind_window(self, window: Any) -> None:
        self._window = window

    # ------------------------------------------------------------ contexto

    @_safe
    def get_context(self) -> dict[str, Any]:
        """Todo lo que la pantalla necesita ANTES de pintar nada (UI-SPEC.md
        Sec.6): en menos de 2 s, sin cargar ningun modelo (ARCHITECTURE.md
        Sec.8.1). `probe_devices()` es barato (Sec.3: "sin cargar modelo").
        """
        caps = transcribe.probe_devices()
        installed = models.installed(MODELS_DIR)
        recommendations = transcribe.recommend_profile(caps, models.CATALOG)
        recommended_id = recommendations[0].model_id if recommendations else None

        yt_available = fetch.is_available()
        if yt_available:
            try:
                version, age_days = fetch.ytdlp_version()
            except CoreError:
                version, age_days = None, None
        else:
            version, age_days = None, None

        return {
            "tool_dir": str(TOOL_DIR),
            "models_installed": installed,
            "models_total_bytes": models.total_size(MODELS_DIR),
            "models_dir": str(MODELS_DIR),
            "disk_free_bytes": _disk_free_bytes(MODELS_DIR),
            "catalog": self._catalog_cards(caps),
            "recommended_model_id": recommended_id,
            "cuda_status": caps.cuda_status,
            "gpu_name": caps.gpu_name,
            "device_chip": messages.device_chip(caps.cuda_status, caps.gpu_name),
            "settings": dict(self._settings),
            "initial_source_path": self._initial_source_path,
            "yt_dlp": {"available": yt_available, "version": version, "age_days": age_days},
            "ytdlp_stale_warning": (
                messages.ytdlp_stale_warning(age_days)
                if yt_available and age_days is not None and age_days >= self._settings.get("ytdlp_stale_days", 60)
                else None
            ),
            "yt_dlp_unavailable_warning": None if yt_available else messages.YTDLP_UNAVAILABLE_WARNING,
            "copy": self._static_copy(),
        }

    def _static_copy(self) -> dict[str, Any]:
        """Paquete de texto ESTATICO (no depende de un trabajo en curso), para
        que `ui.html` no tenga que inventar ni un caracter en castellano por su
        cuenta (Sec.2: `messages.py` es el unico sitio con copy).
        """
        return {
            "phase_titles": dict(messages.PHASE_TITLES),
            "writing_cancel_warning": messages.WRITING_CANCEL_WARNING,
            "language_confidence_warning": messages.LANGUAGE_CONFIDENCE_WARNING,
            "inline_unsupported_scheme": messages.INLINE_UNSUPPORTED_SCHEME,
            "drag_drop_multiple_files": messages.DRAG_DROP_MULTIPLE_FILES,
        }

    def _catalog_cards(self, caps: "transcribe.DeviceCapabilities") -> list[dict[str, Any]]:
        installed = models.installed(MODELS_DIR)
        min_viable = self._settings.get("min_viable_speed_ratio", 1.0)
        cards: list[dict[str, Any]] = []
        for model_id, spec in models.CATALOG.items():
            choice = transcribe.resolve_device(spec, caps, preference="auto")
            speed_ratio = spec.speed_ratio.get(f"{choice.device}_{choice.compute_type}")
            texts = messages.model_card_texts(
                quality_rank=spec.quality_rank,
                expected_bytes=spec.expected_bytes,
                memory_peak_mb=spec.vram_peak_mb.get(choice.compute_type),
                speed_ratio=speed_ratio,
            )
            cards.append({
                "model_id": model_id,
                "quality_rank": spec.quality_rank,
                "expected_bytes": spec.expected_bytes,
                "installed": model_id in installed,
                "installed_bytes": installed.get(model_id, 0),
                "device": choice.device,
                "compute_type": choice.compute_type,
                "viable": bool(speed_ratio is not None and speed_ratio >= min_viable),
                **texts,
            })
        cards.sort(key=lambda c: c["quality_rank"])
        return cards

    # ------------------------------------------------------------ origen

    @_safe
    def pick_file(self) -> Optional[str]:
        """`create_file_dialog()` devuelve la ruta ABSOLUTA: cero copias
        (ARCHITECTURE.md Sec.6.1)."""
        if self._window is None:
            return None
        import webview
        result = self._window.create_file_dialog(webview.FileDialog.OPEN, allow_multiple=False)
        return str(result[0]) if result else None

    @_safe
    def pick_folder(self) -> Optional[str]:
        """Decima operacion, aprobada por Kronos (hueco de ARCHITECTURE.md
        Sec.11: "la carpeta de destino la elige quien llama", pero ninguna
        operacion la exponia). NO toca el nucleo: `output_dir` ya viajaba en
        `options` desde el lote 2 (`jobs._normalize_options`).

        Alcance a proposito, tal como se aprobo: lo elegido vale SOLO para la
        sesion (lo retiene `ui.html` en memoria y lo manda en `options` al
        encolar). No se escribe en `settings.json` desde aqui -- quien quiera un
        destino fijo usa Ajustes avanzados (`save_settings`), que si persiste
        `output_dir`. Dos sitios de escritura para el mismo dato habria sido el
        bug que Kronos pidio evitar explicitamente.
        """
        if self._window is None:
            return None
        import webview
        result = self._window.create_file_dialog(webview.FileDialog.FOLDER)
        return str(result[0]) if result else None

    @_safe
    def probe_media(self, path: str) -> dict[str, Any]:
        """Validacion barata y SINCRONA de un archivo local, adoptada por
        Kronos (aprobo el hueco que UI-SPEC.md Sec.1.2 dejaba abierto).

        Lee la CABECERA del contenedor con PyAV -- `container.duration` y la
        lista de streams -- SIN decodificar ni un fotograma: es la misma
        llamada que ya hace `jobs._probe_duration_seconds()` puertas adentro,
        mas la comprobacion de que existe al menos un stream de audio (el mismo
        chequeo que reserva `NO_AUDIO_STREAM`, ARCHITECTURE.md Sec.3: "PyAV
        confirma que el medio no tiene pista de audio" -- aqui se hace ANTES de
        encolar, no despues de cargar un modelo de hasta 3 GB).

        Reglas que esta funcion NUNCA rompe (impuestas por el encargo):
          - `duration_seconds = None` no es un error: hay contenedores que no
            publican duracion en la cabecera. La pantalla debe seguir
            funcionando sin ese dato (mensajes escalonados por tiempo).
          - La duracion AUTORITATIVA sigue siendo la del resultado final
            (`TranscriptionResult.media_duration_seconds`, que faster-whisper
            calcula al decodificar): si discrepan, manda esa, nunca esta.
          - Jamas decodifica. Si algun dia hace falta "afinar" la duracion,
            eso es una operacion de minutos, no de milisegundos, y le sale del
            presupuesto a esta funcion.
        """
        media_path = Path(path).resolve()
        if not media_path.is_file():
            raise CoreError(ErrorCode.FILE_NOT_FOUND, details={"path": str(media_path)}, technical="")

        try:
            with av.open(str(media_path)) as container:
                duration = container.duration  # microsegundos, o None (cabecera puede no traerlo)
                duration_seconds = (duration / 1_000_000) if duration else None
                has_audio = len(container.streams.audio) > 0
                container_format = (container.format.name or "").split(",")[0]
        except CoreError:
            raise
        except Exception as exc:
            raise CoreError(
                ErrorCode.DECODE_FAILED,
                details={"path": str(media_path), "container": media_path.suffix.lstrip(".")},
                technical=one_line(str(exc)),
            ) from exc

        if not has_audio:
            raise CoreError(ErrorCode.NO_AUDIO_STREAM, details={"path": str(media_path)}, technical="")

        return {
            "path": str(media_path),
            "display_name": media_path.name,
            "size_bytes": media_path.stat().st_size,
            "duration_seconds": duration_seconds,
            "container": container_format,
        }

    @_safe
    def probe_url(self, url: str) -> dict[str, Any]:
        """Examinar un enlace SIN descargar (ARCHITECTURE.md Sec.6.3). Llamada
        de solo lectura, directa a `fetch.py` -- mismo patron que `serve.py`
        usa para `/health` (Sec.2: orquestar es lo unico exclusivo de `jobs.py`;
        una consulta sincrona no orquesta nada).
        """
        info = fetch.probe(url, list(self._settings.get("youtube_player_clients") or []))
        return {
            "title": info.title,
            "duration_seconds": info.duration_seconds,
            "extractor": info.extractor,
            "estimated_bytes": info.estimated_bytes,
        }

    # ------------------------------------------------------------ trabajos

    @_safe
    def start_transcription(self, source: dict[str, Any], options: dict[str, Any]) -> dict[str, Any]:
        job_id, position = self._jobs.submit_transcription(source, options)
        return {"job_id": job_id, "queue_position": position}

    @_safe
    def get_job(self, job_id: str, since: Optional[int] = None, elapsed_in_phase: float = 0.0) -> dict[str, Any]:
        """Consulta de estado (ARCHITECTURE.md Sec.4, punto 3: "cada segundo").
        Enriquecida con `state["ui"]`, TODO calculado por `messages.py`: nunca
        un texto de pantalla compuesto en `ui.html`.
        """
        state = self._jobs.get_job(job_id, since=since)
        state["ui"] = self._describe_job(state, elapsed_in_phase)
        return state

    def _describe_job(self, state: dict[str, Any], elapsed_in_phase: float) -> dict[str, Any]:
        phase = state.get("phase")
        device_used = state.get("device_used") or {}
        ui: dict[str, Any] = {"phase_title": messages.phase_title(phase)}

        if phase == "detecting_language":
            ui["phase_hint"] = messages.detecting_language_hint(elapsed_in_phase, state.get("media_duration_seconds"))

        if device_used:
            ui["device_chip"] = messages.device_chip(
                "confirmed" if device_used.get("device") == "cuda" else "unavailable",
                fell_back_from=device_used.get("fell_back_from"),
                fallback_reason=device_used.get("fallback_reason"),
            )

        if state.get("error"):
            err = state["error"]
            ui["error"] = messages.error_message(err.get("code", "internal"), err.get("details"))

        if state.get("state") == "done" and state.get("result"):
            result = state["result"]
            fallback = messages.fallback_warning(device_used.get("fallback_reason"))
            if fallback:
                ui["fallback_warning"] = fallback
            probability = result.get("language_probability")
            threshold = self._settings.get("language_confidence_warn_threshold", 0.75)
            if probability is not None and probability < threshold:
                ui["language_confidence_warning"] = messages.LANGUAGE_CONFIDENCE_WARNING

        return ui

    @_safe
    def cancel_job(self, job_id: str) -> dict[str, Any]:
        return {"cancelled": self._jobs.cancel_job(job_id)}

    @_safe
    def cancel_button_text(self, phase: Optional[str], cancelling: bool) -> dict[str, Any]:
        return messages.cancel_button(phase, cancelling)

    @_safe
    def error_message(self, code: str, details: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Traduccion bajo demanda para errores que NO llegan dentro de un
        `job.error` (p.ej. `probe_media`/`probe_url` fallando antes de encolar
        nada): `ui.html` la llama con el `code`/`details` que trae la excepcion.
        """
        return messages.error_message(code, details)

    # ------------------------------------------------------------ modelos

    @_safe
    def download_model(self, model_id: str) -> dict[str, Any]:
        job_id, position = self._jobs.submit_model_download(model_id)
        return {"job_id": job_id, "queue_position": position}

    @_safe
    def delete_model(self, model_id: str) -> dict[str, Any]:
        if model_id not in models.CATALOG:
            raise ValueError(f"modelo desconocido: {model_id!r}")
        freed = models.delete_model(model_id, MODELS_DIR)
        return {"bytes_freed": freed}

    # ------------------------------------------------------------ ajustes

    @_safe
    def get_settings(self) -> dict[str, Any]:
        return dict(self._settings)

    # Solo lo que Ajustes avanzados expone (UI-SPEC.md Sec.14): el resto de
    # settings.json (puerto del servidor, tamano de cola...) es de operacion,
    # no de uso diario, y no tiene control en esta pantalla.
    _SETTINGS_SCREEN_KEYS = frozenset({
        "language", "output_formats", "output_dir", "device_preference", "vad_filter",
    })

    @_safe
    def save_settings(self, overrides: dict[str, Any]) -> dict[str, Any]:
        filtered = {k: v for k, v in overrides.items() if k in self._SETTINGS_SCREEN_KEYS}
        self._settings = config.save(filtered)
        return dict(self._settings)

    # ------------------------------------------------------------ utilidades de cascara

    @_safe
    def open_folder(self, path: str) -> bool:
        """"Abrir carpeta" (UI-SPEC.md Sec.10): explorador de Windows, con el
        archivo seleccionado si `path` es un archivo. No toca el nucleo.
        """
        target = Path(path)
        if target.is_file():
            subprocess.run(["explorer", "/select,", str(target)], check=False)
        elif target.is_dir():
            subprocess.run(["explorer", str(target)], check=False)
        else:
            subprocess.run(["explorer", str(target.parent)], check=False)
        return True

    @_safe
    def open_external(self, url: str) -> bool:
        """Botones "Descargar el archivo yo mismo" / "Comprobar el enlace en el
        navegador" (Sec.11): abre el enlace fuera de la ventana, nunca dentro.
        """
        webbrowser.open(url)
        return True

    @_safe
    def format_bytes(self, n: Optional[int]) -> str:
        return messages.format_bytes(n)

    @_safe
    def format_minutes_per_10(self, speed_ratio: Optional[float]) -> Optional[str]:
        return messages.format_minutes_per_10(speed_ratio)

    @_safe
    def format_mmss(self, seconds: Optional[float]) -> str:
        return messages.format_mmss(seconds)

    @_safe
    def format_percent(self, fraction: Optional[float]) -> Optional[str]:
        return messages.format_percent(fraction)

    def quit(self) -> None:
        if self._window is not None:
            self._window.destroy()


# --------------------------------------------------------------- arrastrar y soltar

def _bind_drop_handler(window: Any) -> None:
    """Arrastrar y soltar con RUTA ABSOLUTA real (UI-SPEC.md Sec.7.2). pywebview
    inyecta `pywebviewFullPath` en los `File` soltados a traves de `webview.dom`
    (verificado en el codigo instalado, pywebview 6.2.1, `webview/util.py`).

    Degradacion silenciosa si la API no esta: "Elegir archivo..." y el campo de
    enlace siguen funcionando enteros -- arrastrar y soltar es una comodidad,
    nunca el unico camino.
    """
    try:
        from webview.dom import DOMEventHandler

        def _on_drop(e: dict) -> None:
            try:
                files = ((e.get("dataTransfer") or {}).get("files")) or []
                paths = [f["pywebviewFullPath"] for f in files if f.get("pywebviewFullPath")]
            except Exception:
                logger.exception("fallo leyendo archivos soltados")
                paths = []
            if not paths:
                return
            had_extra = len(paths) > 1
            payload = json.dumps(paths[0])
            window.evaluate_js(f"window.__v2tOnFileDropped({payload}, {str(had_extra).lower()})")

        window.events.loaded.wait(timeout=5)
        window.dom.document.on("dragover", DOMEventHandler(lambda e: None, prevent_default=True))
        window.dom.document.on("drop", DOMEventHandler(_on_drop, prevent_default=True, stop_propagation=True))
    except Exception:
        logger.warning("arrastrar y soltar no disponible en esta version de pywebview; se usa Elegir archivo")


# --------------------------------------------------------------- arranque

def main() -> int:
    _configure_logging()
    resolved_settings = config.load()
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    job_manager = jobs.JobManager(
        models_dir=MODELS_DIR,
        tool_dir=TOOL_DIR,
        max_queued_jobs=resolved_settings["max_queued_jobs"],
        model_idle_timeout_seconds=resolved_settings["model_idle_timeout_seconds"],
        work_retention_hours=resolved_settings["work_retention_hours"],
    )

    # Cerrojo ANTES de tocar la ventana (ARCHITECTURE.md Sec.6.4/D21): nunca dos
    # procesos con el modelo en RAM, y nunca un fallo mudo -- la ventana no
    # llega a abrirse, se explica por que con un dialogo nativo (Sec.5).
    try:
        job_manager.acquire_runtime_lock(mode="window")
    except jobs.RuntimeLockError as exc:
        dialog = messages.exclusivity_dialog(exc.info)
        _show_native_dialog(dialog["title"], dialog["body"])
        return 1

    initial_source_path: Optional[str] = None
    if len(sys.argv) > 1 and sys.argv[1]:
        candidate = Path(sys.argv[1])
        if candidate.is_file():
            initial_source_path = str(candidate.resolve())

    api = Api(job_manager, resolved_settings, initial_source_path)

    import webview  # perezoso: no se importa si el cerrojo ya nos hizo salir arriba

    window = webview.create_window(
        WINDOW_TITLE,
        str(UI_PATH),
        js_api=api,
        width=INITIAL_SIZE[0],
        height=INITIAL_SIZE[1],
        min_size=MIN_SIZE,
        text_select=True,
        confirm_close=False,
    )
    api.bind_window(window)

    def _on_closed() -> None:
        # Cerrar la ventana termina el trabajo entero, en un gesto
        # (ARCHITECTURE.md Sec.6.1). `wait=False`: el proceso va a morir de
        # todas formas, no hace falta bloquear el cierre esperando al hilo.
        try:
            job_manager.shutdown(wait=False)
        except Exception:
            logger.exception("fallo al apagar el gestor de trabajos en el cierre")

    window.events.closed += _on_closed

    def _on_start() -> None:
        job_manager.start()
        _bind_drop_handler(window)

    webview.start(
        _on_start,
        storage_path=str(WEBVIEW_STORAGE_DIR),  # OBLIGATORIO -- ARCHITECTURE.md Sec.6.1
        private_mode=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
