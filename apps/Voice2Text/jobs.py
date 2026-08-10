"""ORQUESTACION: cola FIFO, estado, cancelacion, cerrojo de proceso, modelo en RAM.

Vive entre la cascara (`app.py`, lote 3, todavia no existe; `serve.py`, lote 6,
ya lo consume) y el motor (`transcribe.py`, `models.py`, `export.py`). A
diferencia del motor, este archivo SI tiene estado (la cola, el modelo cargado,
los trabajos) y SI puede usar hilos -- eso es exactamente lo que
ARCHITECTURE.md Sec.2 le asigna. Lo que sigue prohibido aqui, igual que en el
motor: nada de `webview`, nada de `http.server`, nada de texto en castellano
(D10/D12) -- eso es trabajo exclusivo de `messages.py` en la cascara, que este
archivo ni conoce.

Lote 6: tres metodos de solo lectura/limpieza (`running_job_id`, `loaded_model`,
`forget_job`) se anadieron para que `serve.py` pudiera exponer `/health` y
`DELETE /api/v1/jobs/{job_id}` sin leer los atributos privados de
`JobManager` desde fuera. Son lectura de estado y limpieza de la cola, no
logica nueva: no reimplementan nada que ya estuviera aqui.

Decision de diseno que no esta escrita literalmente en ARCHITECTURE.md y que hay
que dejar explicita para que nadie la lea como un descuido: **un trabajo de
transcripcion NUNCA descarga un modelo por su cuenta** (`transcribe.load_model(...,
allow_download=False)` siempre). El unico camino que dispara una descarga es
`submit_model_download()`, que exige que quien llama ya haya pedido esa descarga
explicitamente (la pantalla de consentimiento vive en la cascara, lote 3). Encolar
una transcripcion con un modelo que falta termina en `CoreError(MODEL_MISSING)`,
nunca en una descarga sorpresa de hasta 3,1 GB -- es la regla mas importante del
encargo del lote 2 y se aplica aqui, no en el motor.
"""
from __future__ import annotations

import gc
import json
import logging
import msvcrt
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import av

import export
import models
import transcribe
from errors import CoreError, ErrorCode, one_line

logger = logging.getLogger(__name__)

# Fases dentro de state="running" (ARCHITECTURE.md Sec.4.3, mas "detecting_language"
# -- anadida el 2026-08-10, ver docstring de _run_transcription). "probing" y
# "fetching" son de origen enlace (lote 4, fetch.py): se dejan en la lista para que
# el estado tenga un vocabulario cerrado desde ya, aunque este lote no las produzca.
PHASE_QUEUED = "queued"
PHASE_PROBING = "probing"
PHASE_FETCHING = "fetching"
PHASE_DOWNLOADING_MODEL = "downloading_model"
PHASE_LOADING_MODEL = "loading_model"
PHASE_DETECTING_LANGUAGE = "detecting_language"
PHASE_TRANSCRIBING = "transcribing"
PHASE_WRITING = "writing"
PHASE_FINISHED = "finished"

_DEFAULT_FORMATS = ("txt", "md")
_MIN_ETA_ELAPSED_SECONDS = 20.0  # ARCHITECTURE.md Sec.4.4: eta_seconds=null antes de esto


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_job_id() -> str:
    return "j_" + uuid.uuid4().hex[:12]


def _probe_duration_seconds(media_path: Path) -> Optional[float]:
    """Duracion del medio, leida de metadatos -- NO decodifica audio. Sirve para
    poblar `media_duration_seconds` desde el momento de encolar (util para la
    cascara y para estimar espera) y para que la fase `detecting_language` pueda
    explicarse ("esto va a tardar unos segundos porque el archivo dura X"): la
    escala de esa fase es justamente esta cifra, ya disponible en el estado.
    """
    try:
        with av.open(str(media_path)) as container:
            duration = container.duration  # microsegundos, o None
            return (duration / 1_000_000) if duration else None
    except Exception:
        return None


def _segment_to_dict(segment: "transcribe.Segment") -> dict[str, Any]:
    return {
        "index": segment.index,
        "start": segment.start,
        "end": segment.end,
        "speech_end": segment.speech_end,
        "text": segment.text,
    }


def _device_choice_to_dict(choice: "transcribe.DeviceChoice") -> dict[str, Any]:
    return {
        "device": choice.device,
        "device_index": choice.device_index,
        "compute_type": choice.compute_type,
        "fell_back_from": choice.fell_back_from,
        "fallback_reason": choice.fallback_reason,
    }


def _purge_work_dir(work_dir: Path, retention_hours: float) -> None:
    """D15: al arrancar, se purga lo de `work/` mas viejo que `retention_hours`.
    No falla si `work/` no existe todavia (nada lo ha creado: `fetch.py` es lote 4).
    """
    if retention_hours <= 0 or not work_dir.exists():
        return
    cutoff = time.time() - retention_hours * 3600
    for entry in work_dir.iterdir():
        try:
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                entry.unlink()
        except OSError:
            continue


def _purge_job_work_files(work_dir: Path, job_id: str) -> None:
    """D15: tras cada trabajo, lo suyo. Los temporales se llaman `<job_id>.<ext>`."""
    if not work_dir.exists():
        return
    for entry in work_dir.glob(f"{job_id}.*"):
        try:
            entry.unlink()
        except OSError:
            continue


def _normalize_options(raw: dict[str, Any]) -> dict[str, Any]:
    if not raw.get("model_id"):
        raise ValueError("options.model_id es obligatorio")
    return {
        "model_id": raw["model_id"],
        "device_preference": raw.get("device_preference", "auto"),
        "language": raw.get("language"),
        "vad_filter": raw.get("vad_filter", True),
        "output_dir": raw.get("output_dir"),
        "formats": list(raw.get("formats") or _DEFAULT_FORMATS),
    }


@dataclass
class Job:
    """Objeto de estado (ARCHITECTURE.md Sec.4.2). Solo numeros y codigos -- ni una
    cadena pensada para pantalla (D10): lo que ve el usuario lo redacta la cascara.
    """

    job_id: str
    kind: str  # "transcription" | "model_download"
    source: dict[str, Any]
    options: dict[str, Any]
    created_at: str = field(default_factory=_now_iso)

    state: str = "queued"  # queued | running | done | error | cancelled
    phase: Optional[str] = None
    progress: Optional[float] = None

    processed_media_seconds: Optional[float] = None
    media_duration_seconds: Optional[float] = None
    downloaded_bytes: Optional[int] = None
    total_bytes: Optional[int] = None
    eta_seconds: Optional[int] = None

    updated_at: str = field(default_factory=_now_iso)
    finished_at: Optional[str] = None

    device_used: Optional[dict[str, Any]] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[dict[str, Any]] = None

    segments: list[dict[str, Any]] = field(default_factory=list)  # solo kind=transcription
    _cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    _transcribe_start_wall: Optional[float] = field(default=None, repr=False)

    def to_state_dict(self) -> dict[str, Any]:
        """Copia JSON-segura, SIN `new_segments` (eso lo anade `JobManager.get_job`,
        que sabe el `since` que pidio quien llama) y sin los campos internos (`_*`).
        """
        return {
            "job_id": self.job_id,
            "kind": self.kind,
            "state": self.state,
            "phase": self.phase,
            "progress": self.progress,
            "processed_media_seconds": self.processed_media_seconds,
            "media_duration_seconds": self.media_duration_seconds,
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "eta_seconds": self.eta_seconds,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "finished_at": self.finished_at,
            "source": dict(self.source),
            "options": dict(self.options),
            "device_used": dict(self.device_used) if self.device_used else None,
            "result": dict(self.result) if self.result else None,
            "error": dict(self.error) if self.error else None,
        }


class RuntimeLockError(Exception):
    """Ya hay otro proceso vivo (ventana o servidor). `info` es el contenido de
    `runtime.json` de quien tiene el cerrojo (S12, ARCHITECTURE.md Sec.6.4).
    """

    def __init__(self, info: dict[str, Any]):
        self.info = info
        super().__init__(f"runtime lock held by: {info}")


class JobManager:
    """Cola FIFO de un solo trabajo en ejecucion (ADR-0001 D14), con:
      - un unico hilo trabajador (ARCHITECTURE.md Sec.4, punto 2),
      - un modelo en RAM compartido entre trabajos (Sec.4.5 / D22), que se libera
        solo tras `model_idle_timeout_seconds` de cola vacia,
      - el cerrojo exclusivo de proceso de Sec.6.4 (S12),
      - la purga de `work/` de D15.

    Todas las lecturas y escrituras de estado pasan por `self._lock`: es lo que
    permite que `get_job()`/`submit_*()`/`cancel_job()` se llamen desde cualquier
    hilo (la futura cascara, o un bot) mientras el trabajador transcribe en el
    suyo. El lock SOLO se sostiene para mutaciones puntuales -- nunca durante una
    llamada larga (`transcribe.transcribe()`, `models.ensure_model()`), o cualquier
    consulta de estado se quedaria colgada minutos.
    """

    def __init__(
        self,
        *,
        models_dir: Path,
        tool_dir: Path,
        max_queued_jobs: int = 8,
        model_idle_timeout_seconds: float = 300.0,
        work_retention_hours: float = 24.0,
        idle_check_interval_seconds: float = 5.0,
    ) -> None:
        self._models_dir = Path(models_dir)
        self._tool_dir = Path(tool_dir)
        self._work_dir = self._tool_dir / "work"
        self._max_queued_jobs = max_queued_jobs
        self._model_idle_timeout_seconds = model_idle_timeout_seconds
        self._work_retention_hours = work_retention_hours
        self._idle_check_interval_seconds = idle_check_interval_seconds

        self._lock = threading.RLock()
        self._jobs: dict[str, Job] = {}
        self._queue: list[str] = []
        self._running_job_id: Optional[str] = None

        self._loaded_model: Optional[object] = None
        self._loaded_model_key: Optional[tuple[str, str, str]] = None
        self._model_last_used: float = 0.0

        self._speed_ratio_cache: dict[tuple[str, str], float] = {}

        self._wake = threading.Event()
        self._shutdown = threading.Event()

        self._runtime_lock_handle: Optional[Any] = None

        self._worker_thread = threading.Thread(target=self._worker_loop, name="v2t-worker", daemon=True)
        self._idle_thread = threading.Thread(target=self._idle_loop, name="v2t-idle-watchdog", daemon=True)
        self._started = False

    # ------------------------------------------------------------------ ciclo de vida

    def start(self) -> None:
        if self._started:
            return
        _purge_work_dir(self._work_dir, self._work_retention_hours)
        self._started = True
        self._worker_thread.start()
        self._idle_thread.start()

    def shutdown(self, wait: bool = True) -> None:
        self._shutdown.set()
        self._wake.set()
        if wait:
            self._worker_thread.join(timeout=10)
            self._idle_thread.join(timeout=self._idle_check_interval_seconds + 2)
        with self._lock:
            self._loaded_model = None
            self._loaded_model_key = None
        gc.collect()
        self.release_runtime_lock()

    # ------------------------------------------------------------------ cerrojo de proceso (S12, Sec.6.4)

    def acquire_runtime_lock(self, mode: str, port: Optional[int] = None) -> None:
        """Un unico proceso vivo por instalacion (ventana XOR servidor). El cerrojo
        es un `msvcrt.locking()` NO bloqueante sobre `runtime.lock`: Windows lo
        libera solo cuando el proceso muere -- incluso a lo bruto (Ctrl+C duro,
        Terminar tarea) -- porque el lock esta atado al *handle* del archivo, no a
        que nadie lo suelte a mano. `runtime.json` es solo informativo: lo que de
        verdad excluye es el lock, `runtime.json` es lo que se lee para EXPLICAR
        que hay corriendo cuando el segundo intento falla (Sec.6.4: "nunca un fallo
        mudo").
        """
        lock_path = self._tool_dir / "runtime.lock"
        info_path = self._tool_dir / "runtime.json"

        handle = open(lock_path, "a+b")
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            stale_info: dict[str, Any] = {}
            try:
                stale_info = json.loads(info_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            raise RuntimeLockError(stale_info) from exc

        self._runtime_lock_handle = handle
        info = {"mode": mode, "pid": os.getpid(), "port": port, "started_at": _now_iso()}
        info_path.write_text(json.dumps(info, ensure_ascii=True), encoding="utf-8")

    def release_runtime_lock(self) -> None:
        if self._runtime_lock_handle is None:
            return
        try:
            self._runtime_lock_handle.seek(0)
            msvcrt.locking(self._runtime_lock_handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        try:
            self._runtime_lock_handle.close()
        except OSError:
            pass
        self._runtime_lock_handle = None

    # ------------------------------------------------------------------ encolar

    def submit_transcription(self, source: dict[str, Any], options: dict[str, Any]) -> tuple[str, int]:
        """`source = {"kind": "file", "path": "..."}`. `"kind": "url"` no esta
        disponible hasta el lote 4 (`fetch.py`): se rechaza aqui mismo, no a medias.
        Devuelve `(job_id, queue_position)`.
        """
        if source.get("kind") != "file":
            raise CoreError(
                ErrorCode.UNSUPPORTED_URL,
                details={"kind": source.get("kind")},
                technical="url source not available before lote 4 (fetch.py)",
            )

        media_path = Path(source["path"]).resolve()
        if not media_path.is_file():
            raise CoreError(ErrorCode.FILE_NOT_FOUND, details={"path": str(media_path)}, technical="")

        normalized_options = _normalize_options(options)
        if normalized_options["output_dir"] is None:
            normalized_options["output_dir"] = str(media_path.parent)

        job = Job(
            job_id=_new_job_id(),
            kind="transcription",
            source={
                "kind": "file",
                "display_name": media_path.name,
                "path": str(media_path),
                "url": None,
                "has_video": None,
            },
            options=normalized_options,
            media_duration_seconds=_probe_duration_seconds(media_path),
        )
        return self._enqueue(job)

    def submit_model_download(self, model_id: str) -> tuple[str, int]:
        if model_id not in models.CATALOG:
            raise ValueError(f"unknown model_id: {model_id!r}")
        job = Job(
            job_id=_new_job_id(),
            kind="model_download",
            source={"kind": "model", "display_name": model_id, "path": None, "url": None, "has_video": None},
            options={"model_id": model_id},
            total_bytes=models.CATALOG[model_id].expected_bytes,
        )
        return self._enqueue(job)

    def _enqueue(self, job: Job) -> tuple[str, int]:
        with self._lock:
            pending = len(self._queue) + (1 if self._running_job_id else 0)
            if pending >= self._max_queued_jobs:
                raise CoreError(
                    ErrorCode.QUEUE_FULL,
                    details={"queued": pending, "limit": self._max_queued_jobs},
                    technical="",
                )
            self._jobs[job.job_id] = job
            self._queue.append(job.job_id)
            position = self._queue_position_locked(job.job_id)
        self._wake.set()
        return job.job_id, position

    # ------------------------------------------------------------------ consultar

    def get_job(self, job_id: str, since: Optional[int] = None) -> dict[str, Any]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            state = job.to_state_dict()
            state["queue_position"] = self._queue_position_locked(job_id)
            state["estimated_wait_seconds"] = self._estimate_wait_locked(job_id)
            if since is not None and job.kind == "transcription":
                state["new_segments"] = [seg for seg in job.segments if seg["index"] >= since]
        return state

    def list_jobs(self) -> list[str]:
        with self._lock:
            return list(self._jobs.keys())

    def running_job_id(self) -> Optional[str]:
        """El `job_id` en ejecucion ahora mismo, o `None` (lote 6: lo usa `serve.py`
        para cancelar el trabajo en curso al apagar, ARCHITECTURE.md Sec.6.2/D15).
        """
        with self._lock:
            return self._running_job_id

    def loaded_model(self) -> Optional[dict[str, Any]]:
        """Que modelo (si alguno) esta cargado en RAM ahora mismo (D22). Lote 6:
        lo consume `GET /api/v1/health` (ARCHITECTURE.md Sec.6.3).
        """
        with self._lock:
            if self._loaded_model_key is None:
                return None
            model_id, device, compute_type = self._loaded_model_key
            return {"model_id": model_id, "device": device, "compute_type": compute_type}

    def _queue_position_locked(self, job_id: str) -> int:
        if job_id == self._running_job_id:
            return 0
        try:
            return self._queue.index(job_id) + 1
        except ValueError:
            return 0  # ya termino (done/error/cancelled): no tiene sentido una posicion

    def _estimate_wait_locked(self, job_id: str) -> Optional[float]:
        """Mejor esfuerzo, honesto (ARCHITECTURE.md Sec.4.4): si falta cualquier
        dato para estimar un trabajo por delante, se devuelve `None` entero antes
        que inventar un numero. Solo tiene sentido para trabajos en cola
        (queue_position > 0); el trabajo en ejecucion usa `eta_seconds`, no esto.
        """
        position = self._queue_position_locked(job_id)
        if position <= 0:
            return None

        total = 0.0
        ahead_ids = ([self._running_job_id] if self._running_job_id else []) + self._queue[: position - 1]
        for ahead_id in ahead_ids:
            ahead = self._jobs.get(ahead_id) if ahead_id else None
            if ahead is None or ahead.kind != "transcription":
                return None
            if ahead_id == self._running_job_id and ahead.processed_media_seconds is not None and ahead.eta_seconds is not None:
                total += ahead.eta_seconds
                continue
            if ahead.media_duration_seconds is None:
                return None
            device = self._likely_device(ahead.options.get("model_id"), ahead.options.get("device_preference", "auto"))
            speed_ratio = self._speed_ratio_cache.get((ahead.options.get("model_id"), device))
            if not speed_ratio:
                return None
            total += ahead.media_duration_seconds / speed_ratio
        return total

    def _likely_device(self, model_id: Optional[str], preference: str) -> str:
        spec = models.CATALOG.get(model_id) if model_id else None
        if spec is None:
            # Lote 8: resolve_device() ahora recibe un ModelSpec (ARCHITECTURE.md
            # Sec.3), no un model_id. Sin uno valido no hay nada que resolver --
            # mismo resultado conservador que antes (VRAM desconocida -> CPU).
            return "cpu"
        try:
            caps = transcribe.probe_devices()
            return transcribe.resolve_device(spec, caps, preference=preference).device
        except Exception:
            return "cpu"

    # ------------------------------------------------------------------ cancelar

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job.state in ("done", "error", "cancelled"):
                return False
            if job.state == "queued":
                # Instantaneo (ARCHITECTURE.md Sec.4.1 / Sec.14): sale de la cola
                # sin que el trabajador llegue a mirarlo.
                if job_id in self._queue:
                    self._queue.remove(job_id)
                job.state = "cancelled"
                job.error = {"code": ErrorCode.CANCELLED.value, "details": {}, "technical": ""}
                job.finished_at = _now_iso()
                job.updated_at = job.finished_at
                return True
            # En ejecucion: cooperativo. El trabajador lo ve en su siguiente punto
            # de control (cada segmento, cada trozo de 256 KiB de una descarga de
            # modelo). Tarda hasta ~30s en transcripcion (ARCHITECTURE.md Sec.4.1);
            # es sub-segundo en descarga de modelo (models.py, medido en el lote 2).
            job._cancel_event.set()
            return True

    def forget_job(self, job_id: str) -> None:
        """Quita el trabajo del mapa de estado y purga sus temporales de `work/`
        (lote 6: `DELETE /api/v1/jobs/{job_id}`, ARCHITECTURE.md Sec.5.4/6.3).

        No cancela por su cuenta: un trabajo `queued` o `running` se rechaza con
        `ValueError` -- primero se cancela (`cancel_job`), luego se olvida. Mismo
        patron que `cancel_job()`: valida bajo `self._lock`, hace la E/S fuera.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise KeyError(job_id)
            if job.state in ("queued", "running"):
                raise ValueError(f"job {job_id!r} sigue {job.state}; cancelalo antes de olvidarlo")
            del self._jobs[job_id]
        _purge_job_work_files(self._work_dir, job_id)

    # ------------------------------------------------------------------ trabajador

    def _worker_loop(self) -> None:
        while not self._shutdown.is_set():
            job_id = self._pop_next_locked()
            if job_id is None:
                self._wake.wait(timeout=1.0)
                self._wake.clear()
                continue
            self._run_job(job_id)

    def _pop_next_locked(self) -> Optional[str]:
        with self._lock:
            if not self._queue:
                return None
            job_id = self._queue.pop(0)
            self._running_job_id = job_id
            job = self._jobs[job_id]
            job.state = "running"
            job.phase = PHASE_QUEUED
            job.updated_at = _now_iso()
            return job_id

    def _run_job(self, job_id: str) -> None:
        job = self._jobs[job_id]
        try:
            if job.kind == "model_download":
                self._run_model_download(job)
            else:
                self._run_transcription(job)
            with self._lock:
                job.state = "done"
                job.phase = PHASE_FINISHED
                job.progress = 1.0
        except CoreError as err:
            with self._lock:
                job.state = "cancelled" if err.code == ErrorCode.CANCELLED else "error"
                job.error = {"code": err.code.value, "details": err.details, "technical": err.technical}
        except Exception as exc:  # el trabajador no puede morir por un fallo de un trabajo
            logger.exception("fallo inesperado en el trabajo %s", job_id)
            with self._lock:
                job.state = "error"
                job.error = {"code": ErrorCode.INTERNAL.value, "details": {}, "technical": one_line(str(exc))}
        finally:
            with self._lock:
                job.finished_at = _now_iso()
                job.updated_at = job.finished_at
                self._running_job_id = None
            _purge_job_work_files(self._work_dir, job_id)
            self._wake.set()  # por si alguien esperaba a que se vaciara la cola

    def _set_phase(self, job: Job, phase: str, *, progress: Optional[float]) -> None:
        with self._lock:
            job.phase = phase
            job.progress = progress
            job.updated_at = _now_iso()

    # -- transcripcion -------------------------------------------------------

    def _run_transcription(self, job: Job) -> None:
        media_path = Path(job.source["path"])
        options = job.options
        model_id = options["model_id"]

        def should_cancel() -> bool:
            return job._cancel_event.is_set()

        already_present = model_id in models.installed(self._models_dir)
        self._set_phase(job, PHASE_LOADING_MODEL if already_present else PHASE_DOWNLOADING_MODEL, progress=None)
        if not already_present:
            # No se descarga aqui NUNCA (ver docstring del modulo): si falta, es
            # `MODEL_MISSING` -- lo mismo que hace `transcribe.load_model()` con
            # `allow_download=False`, mas abajo. La fase queda anotada igual para
            # que el estado explique POR QUE va a fallar antes de que falle.
            pass

        device_choice, model = self._acquire_model(model_id, options["device_preference"])
        with self._lock:
            job.device_used = _device_choice_to_dict(device_choice)

        if should_cancel():
            raise CoreError(ErrorCode.CANCELLED, details={}, technical="")

        # Fase nueva (anadida el 2026-08-10 al contrato de estado): faster-whisper
        # decodifica el archivo ENTERO y corre el VAD sobre el completo ANTES de
        # devolver el primer segmento -- medido: 7s/2min, 10.5s/10min, 22s/37min de
        # audio. Progreso INDETERMINADO a proposito: no hay forma de saber cuanto
        # falta hasta que termina. `job.media_duration_seconds` (ya poblado desde
        # que se encolo, ver `_probe_duration_seconds`) es la cifra con la que la
        # cascara puede decir algo proporcional en archivos largos -- esta fase
        # ESCALA con esa duracion, no es un tiempo fijo.
        self._set_phase(job, PHASE_DETECTING_LANGUAGE, progress=None)

        transcribe_start = time.monotonic()

        def on_segment(segment: "transcribe.Segment", progress: float) -> None:
            with self._lock:
                job.phase = PHASE_TRANSCRIBING
                job.progress = progress
                job.processed_media_seconds = segment.end
                job.segments.append(_segment_to_dict(segment))
                job.updated_at = _now_iso()

                elapsed = time.monotonic() - transcribe_start
                if elapsed >= _MIN_ETA_ELAPSED_SECONDS and job.media_duration_seconds:
                    speed_ratio = segment.end / elapsed if elapsed > 0 else 0.0
                    remaining = max(0.0, job.media_duration_seconds - segment.end)
                    job.eta_seconds = int(remaining / speed_ratio) if speed_ratio > 0 else None
                else:
                    job.eta_seconds = None

        result = transcribe.transcribe(
            media_path,
            model,
            language=options["language"],
            vad_filter=options["vad_filter"],
            word_timestamps=True,  # ARCHITECTURE.md Sec.7/Sec.9: es lo unico que
                                    # permite cortar parrafo por pausas reales
            on_segment=on_segment,
            should_cancel=should_cancel,
        )

        self._update_speed_ratio_cache(model_id, device_choice.device, result)

        self._set_phase(job, PHASE_WRITING, progress=None)
        meta = {
            "title": media_path.stem,
            "source": str(media_path),
            "media_duration_seconds": result.media_duration_seconds,
            "language": result.language,
            "language_probability": result.language_probability,
            "model_id": model_id,
            "compute_type": result.device_used.compute_type,
            "device": result.device_used.device,
            "transcribed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        written = export.write_outputs(
            result.segments,
            meta,
            Path(options["output_dir"]),
            media_path.stem,
            options["formats"],
        )

        with self._lock:
            job.media_duration_seconds = result.media_duration_seconds
            job.processed_media_seconds = result.media_duration_seconds
            job.eta_seconds = None
            job.result = {
                "language": result.language,
                "language_probability": result.language_probability,
                "segment_count": len(result.segments),
                "character_count": sum(len(s.text) for s in result.segments),
                "elapsed_seconds": result.elapsed_seconds,
                "speed_ratio": result.speed_ratio,
                "outputs": [
                    {"format": w.format, "path": str(w.path), "bytes": w.bytes} for w in written
                ],
            }

    def _update_speed_ratio_cache(self, model_id: str, device: str, result: "transcribe.TranscriptionResult") -> None:
        # ARCHITECTURE.md Sec.4.4: se cachea por (model_id, device), NUNCA global --
        # mezclar GPU y CPU produce estimaciones que se equivocan por un factor.
        if result.speed_ratio > 0:
            with self._lock:
                self._speed_ratio_cache[(model_id, device)] = result.speed_ratio

    # -- descarga de modelo ---------------------------------------------------

    def _run_model_download(self, job: Job) -> None:
        model_id = job.options["model_id"]

        def should_cancel() -> bool:
            return job._cancel_event.is_set()

        def on_progress(downloaded: int, total: Optional[int]) -> None:
            with self._lock:
                job.phase = PHASE_DOWNLOADING_MODEL
                job.downloaded_bytes = downloaded
                job.total_bytes = total
                job.progress = (downloaded / total) if total else None
                job.updated_at = _now_iso()

        models.ensure_model(model_id, self._models_dir, on_progress=on_progress, should_cancel=should_cancel)

    # -- modelo en RAM (D22, S13) ---------------------------------------------

    def _acquire_model(self, model_id: str, device_preference: str) -> tuple["transcribe.DeviceChoice", object]:
        """Carga (o reutiliza) el modelo YA descargado. Nunca descarga (ver
        docstring del modulo). `allow_download=False`: si falta, `MODEL_MISSING`,
        igual que documenta ARCHITECTURE.md Sec.3.

        Cambiar de `model_id` -- o de dispositivo resuelto, que hoy siempre es
        `cpu` porque `probe_devices()` no activa CUDA hasta el lote 7 -- suelta el
        modelo anterior antes de cargar el nuevo: nunca dos modelos vivos (D22).
        """
        caps = transcribe.probe_devices()
        # Lote 8: resolve_device() recibe el ModelSpec del catalogo, no el model_id
        # (ARCHITECTURE.md Sec.3). Un model_id que no existe en CATALOG termina
        # igualmente en CoreError(MODEL_MISSING) mas abajo, en transcribe.load_model().
        spec = models.CATALOG.get(model_id, models.ModelSpec(
            model_id=model_id, repo_id="", expected_bytes=0, params_millions=0,
            quality_rank=0, vram_peak_mb={}, speed_ratio={},
        ))
        choice = transcribe.resolve_device(spec, caps, preference=device_preference)
        key = (model_id, choice.device, choice.compute_type)

        with self._lock:
            if self._loaded_model is not None and self._loaded_model_key == key:
                self._model_last_used = time.monotonic()
                return choice, self._loaded_model
            stale = self._loaded_model
            self._loaded_model = None
            self._loaded_model_key = None

        if stale is not None:
            del stale
            gc.collect()  # S13: confirma que se libera la memoria nativa, no solo la referencia Python

        model = transcribe.load_model(model_id, self._models_dir, choice, allow_download=False)

        with self._lock:
            self._loaded_model = model
            self._loaded_model_key = key
            self._model_last_used = time.monotonic()
        return choice, model

    def _idle_loop(self) -> None:
        # D22: se suelta el modelo tras `model_idle_timeout_seconds` sin trabajos
        # (cola vacia Y nada en ejecucion). `0` = nunca soltar -- pensado para la
        # ruta CPU si algun dia `settings.json` lo expone (ADR-0001 D22 enmendado:
        # en CPU, con RAM sin limite declarado, el beneficio de soltar es menor).
        while not self._shutdown.wait(timeout=self._idle_check_interval_seconds):
            if self._model_idle_timeout_seconds <= 0:
                continue
            should_unload = False
            with self._lock:
                has_work = bool(self._queue) or self._running_job_id is not None
                if self._loaded_model is not None and not has_work:
                    idle_for = time.monotonic() - self._model_last_used
                    if idle_for >= self._model_idle_timeout_seconds:
                        should_unload = True
                        self._loaded_model = None
                        self._loaded_model_key = None
            if should_unload:
                gc.collect()
                logger.info("modelo liberado tras %.0fs de inactividad", self._model_idle_timeout_seconds)
