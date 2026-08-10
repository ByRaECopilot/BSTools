"""MOTOR: transcripcion con faster-whisper (CTranslate2) + deteccion de audio con PyAV.

Puro, tal como exige ADR-0001 D11 / ARCHITECTURE.md Sec.2: sin estado global, sin leer
configuracion, sin `print`, sin `sys.exit`, sin una sola palabra en castellano. No
importa `webview`, `http.server` ni `settings`. Quien lo llama pasa todo por argumento.

Incluye la enmienda de resolucion de dispositivo del 2026-08-10 (ARCHITECTURE.md Sec.3,
obligatoria en el lote 1): el contrato completo se escribe aqui -- `DeviceCapabilities`,
`DeviceChoice`, `probe_devices()`, `resolve_device()` -- pero SOLO se implementa la rama
CPU. La rama CUDA la rellena ADR-0002 sin tener que reabrir estas firmas.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import av
from faster_whisper import WhisperModel

from errors import CoreError, ErrorCode, one_line

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Segment:
    index: int          # 0,1,2... correlativo
    start: float         # segundos desde el inicio del medio
    end: float            # fin del CONTENEDOR del segmento. OJO: faster-whisper lo ESTIRA
                          # hasta el inicio del siguiente, absorbiendo el silencio (medido,
                          # ver ARCHITECTURE.md Sec.7 y la verificacion V2 del lote 1.b:
                          # el hueco sigue siendo 0 incluso con vad_filter=True)
    speech_end: Optional[float]   # fin real del habla = end de la ULTIMA PALABRA.
                          # None si word_timestamps=False. Es el UNICO campo que ve los
                          # silencios (verificado V4: start SI marca el inicio real del
                          # habla, con o sin word_timestamps -- pero end no lo hace nunca)
    text: str            # ya recortado


@dataclass(frozen=True)
class DeviceCapabilities:
    """Lo que HAY en la maquina. Barato, sin cargar modelo."""
    cuda_available: bool
    cuda_device_count: int
    gpu_name: Optional[str]                          # "NVIDIA GeForce GTX 1050 Ti"
    compute_capability: Optional[tuple[int, int]]     # (6, 1) en Pascal
    vram_total_mb: Optional[int]
    vram_free_mb: Optional[int]
    supported_compute_types: list[str]                # p.ej. ["int8", "float32"]
    unavailable_reason: Optional[str]                 # codigo estable, nunca texto:
    # "no_nvidia_gpu" | "cuda_libs_missing" | "cuda_libs_mismatch" | "compute_capability_too_low"


@dataclass(frozen=True)
class DeviceChoice:
    device: str                   # "cuda" | "cpu"
    device_index: int
    compute_type: str             # "int8" | "int8_float16" | "float16" | "float32"
    cpu_threads: int              # 0 = decide CTranslate2. Ignorado si device="cuda"
    fell_back_from: Optional[str]     # "cuda" si se pidio GPU y se acabo en CPU
    fallback_reason: Optional[str]    # mismo vocabulario que unavailable_reason


@dataclass(frozen=True)
class TranscriptionResult:
    segments: list[Segment]
    language: str
    language_probability: float
    media_duration_seconds: float
    elapsed_seconds: float
    speed_ratio: float            # media_duration / elapsed. Medido en el spike: 2.8 [M]
    device_used: DeviceChoice     # con que se transcribio. Va al estado y a la cabecera del .md


_CPU_COMPUTE_TYPE = "int8"
_ATTR_DEVICE_CHOICE = "_v2t_device_choice"


def probe_devices() -> DeviceCapabilities:
    """Lo que hay en la maquina, sin cargar ningun modelo.

    Lote 1: SOLO CPU. No importa nada de CUDA de forma ansiosa -- mismo cortafuegos
    de import perezoso que exige ADR-0001 D7 para yt-dlp, aplicado a la segunda
    dependencia opcional. La deteccion real (bibliotecas CUDA, VRAM libre, compute
    capability) es la rama que ADR-0002 debe decidir antes de activarse.
    """
    return DeviceCapabilities(
        cuda_available=False,
        cuda_device_count=0,
        gpu_name=None,
        compute_capability=None,
        vram_total_mb=None,
        vram_free_mb=None,
        supported_compute_types=[_CPU_COMPUTE_TYPE, "float32"],
        unavailable_reason="cuda_libs_missing",
    )


def resolve_device(model_id: str, caps: DeviceCapabilities, preference: str = "auto") -> DeviceChoice:
    """Unica politica de eleccion de dispositivo (ARCHITECTURE.md Sec.3).

    Vive aqui y en ningun otro sitio: la cascara solo puede pasar una preferencia
    (`"auto" | "cuda" | "cpu"`), nunca un dispositivo concreto. Lote 1: solo existe
    la rama CPU. Cuando ADR-0002 apruebe la GPU, esta funcion -y solo esta funcion-
    gana la rama CUDA (comprobando `caps` y `ModelSpec.min_vram_mb`); nada mas cambia.
    """
    del model_id  # la rama CUDA lo usara para consultar ModelSpec.min_vram_mb (ADR-0002)

    wanted_gpu = preference in ("auto", "cuda")
    fell_back_from = "cuda" if (wanted_gpu and not caps.cuda_available) else None
    fallback_reason = caps.unavailable_reason if fell_back_from else None

    return DeviceChoice(
        device="cpu",
        device_index=0,
        compute_type=_CPU_COMPUTE_TYPE,
        cpu_threads=0,
        fell_back_from=fell_back_from,
        fallback_reason=fallback_reason,
    )


def load_model(
    model_id: str,
    models_dir: Path,
    choice: DeviceChoice,
    allow_download: bool = False,
) -> object:
    """Carga (y si hace falta y se permite, descarga) un modelo faster-whisper.

    Devuelve un MANEJADOR. No lo cachea en ninguna variable global: quien lo guarda
    y quien lo suelta es `jobs.py` (ADR-0001 D22, lote 2). Con `allow_download=False`
    y el modelo ausente, produce `CoreError(MODEL_MISSING)`.
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    try:
        model = WhisperModel(
            model_id,
            device=choice.device,
            device_index=choice.device_index,
            compute_type=choice.compute_type,
            cpu_threads=choice.cpu_threads,
            download_root=str(models_dir),
            local_files_only=not allow_download,
        )
    except Exception as exc:  # huggingface_hub/ctranslate2 no exponen jerarquia propia
        message = one_line(str(exc))
        if not allow_download:
            raise CoreError(
                ErrorCode.MODEL_MISSING,
                details={"model_id": model_id, "models_dir": str(models_dir)},
                technical=message,
            ) from exc
        raise CoreError(
            ErrorCode.MODEL_DOWNLOAD_FAILED,
            details={"model_id": model_id, "models_dir": str(models_dir)},
            technical=message,
        ) from exc

    # transcribe() necesita saber con que DeviceChoice se construyo este manejador
    # para rellenar TranscriptionResult.device_used, sin ampliar la firma publica
    # de transcribe() (que no recibe el device_choice como argumento aparte).
    setattr(model, _ATTR_DEVICE_CHOICE, choice)
    return model


def _probe_has_audio(media_path: Path) -> None:
    """Confirma con PyAV que el medio tiene al menos un stream de audio.

    `NO_AUDIO_STREAM` se reserva a este caso -- comprobado, no supuesto
    (ARCHITECTURE.md Sec.3/Sec.5). Cualquier otro fallo al abrir el contenedor es
    `DECODE_FAILED`.
    """
    try:
        with av.open(str(media_path)) as container:
            has_audio = any(stream.type == "audio" for stream in container.streams)
    except Exception as exc:
        raise CoreError(
            ErrorCode.DECODE_FAILED,
            details={"path": str(media_path)},
            technical=one_line(str(exc)),
        ) from exc

    if not has_audio:
        raise CoreError(
            ErrorCode.NO_AUDIO_STREAM,
            details={"path": str(media_path)},
            technical="container has no audio stream",
        )


def transcribe(
    media_path: Path,
    model: object,
    *,
    language: Optional[str] = None,        # None = deteccion automatica
    vad_filter: bool = True,
    word_timestamps: bool = True,          # rellena Segment.speech_end (ver Segment,
                                            # ARCHITECTURE.md Sec.7, verificaciones V2/V3/V4)
    on_segment: Callable[[Segment, float], None],   # (segmento, progreso 0..1)
    should_cancel: Callable[[], bool],
) -> TranscriptionResult:
    media_path = Path(media_path)

    if not media_path.is_file():
        raise CoreError(
            ErrorCode.FILE_NOT_FOUND,
            details={"path": str(media_path)},
            technical="",
        )

    _probe_has_audio(media_path)

    device_used = getattr(model, _ATTR_DEVICE_CHOICE, None)
    if device_used is None:
        # Manejador que no paso por load_model(): mejor esfuerzo, sin datos de fallback.
        device_used = DeviceChoice(
            device="cpu", device_index=0, compute_type=_CPU_COMPUTE_TYPE,
            cpu_threads=0, fell_back_from=None, fallback_reason=None,
        )

    start_wall = time.monotonic()
    try:
        segment_iter, info = model.transcribe(
            str(media_path),
            language=language,
            vad_filter=vad_filter,
            word_timestamps=word_timestamps,
        )
    except Exception as exc:
        raise CoreError(
            ErrorCode.DECODE_FAILED,
            details={"path": str(media_path)},
            technical=one_line(str(exc)),
        ) from exc

    media_duration = info.duration or 0.0

    segments: list[Segment] = []
    try:
        for index, raw in enumerate(segment_iter):
            if should_cancel():
                raise CoreError(ErrorCode.CANCELLED, details={}, technical="")

            # raw.words es None si word_timestamps=False; si esta activo, es una lista
            # (posiblemente vacia en un segmento sin palabras reconocidas -- p.ej. ruido).
            speech_end = raw.words[-1].end if raw.words else None

            segment = Segment(
                index=index,
                start=raw.start,
                end=raw.end,
                speech_end=speech_end,
                text=raw.text.strip(),
            )
            segments.append(segment)

            progress = min(segment.end / media_duration, 1.0) if media_duration else 0.0
            on_segment(segment, progress)
    except CoreError:
        raise
    except Exception as exc:
        raise CoreError(
            ErrorCode.DECODE_FAILED,
            details={"path": str(media_path)},
            technical=one_line(str(exc)),
        ) from exc

    elapsed = time.monotonic() - start_wall
    speed_ratio = (media_duration / elapsed) if elapsed > 0 else 0.0

    return TranscriptionResult(
        segments=segments,
        language=info.language,
        language_probability=info.language_probability,
        media_duration_seconds=media_duration,
        elapsed_seconds=elapsed,
        speed_ratio=speed_ratio,
        device_used=device_used,
    )
