"""MOTOR: transcripcion con faster-whisper (CTranslate2) + deteccion de audio con PyAV.

Puro, tal como exige ADR-0001 D11 / ARCHITECTURE.md Sec.2: sin estado global, sin leer
configuracion, sin `print`, sin `sys.exit`, sin una sola palabra en castellano. No
importa `webview`, `http.server` ni `settings`. Quien lo llama pasa todo por argumento.

Lote 7 (ADR-0002): rellena la rama CUDA que el lote 1 dejo apagada a proposito.
Tres reglas que gobiernan este archivo y no son negociables:

1. **`faster_whisper` y `ctranslate2` se importan de forma PEREZOSA**, dentro de las
   funciones que los usan, nunca al nivel de modulo (ADR-0002 E7, mismo patron que el
   import perezoso de `yt_dlp`, ADR-0001 D7). `add_cuda_dlls_to_path()` tiene que
   correr ANTES de cualquiera de los dos imports: pip deja las DLL de CUDA en
   `site-packages/nvidia/*/bin` sin publicarlas en el PATH, y el sintoma de no
   hacerlo es IDENTICO al de no tener las librerias instaladas.
2. **Ninguna construccion de `WhisperModel(device="cuda")` prueba por si sola que la
   GPU funciona** (ADR-0002 E8, medido: carga sin error con las DLL ausentes; el
   `RuntimeError` solo llega en la primera `transcribe()`). La unica comprobacion
   fiable es `smoke_test_cuda()`, fusionada con la primera carga real en
   `load_model()`.
3. **La holgura de VRAM es 512 MiB ABSOLUTOS, nunca un porcentaje** (ADR-0002 Sec.7):
   quedarse justo por debajo del limite es peor que pasarse -- pasarse da un
   `CUDA out of memory` capturable, quedarse al borde no da nada que capturar.

Lote 8 (ARCHITECTURE.md Sec.3, "Donde vive esto"): `ModelSpec` y `CATALOG` se
extraen a `catalog.py`, una HOJA sin comportamiento. Este archivo importa
`catalog.py` -- NUNCA `models.py` -- porque la direccion de esa dependencia es la
que evita el ciclo (`models.py` conoce el layout de cache que `load_model()`
consume; si `transcribe.py` importara `models.py`, la dependencia se invertiria).
`resolve_device()` recibe un `ModelSpec` en vez de un `model_id`: asi no busca en
ningun catalogo y sigue siendo una funcion PURA de sus argumentos.
`recommend_profile()` y `ModelRecommendation` viven aqui, junto a `resolve_device()`:
son la misma politica de ADR-0001 Sec.17.2 a dos granularidades (que modelo / que
dispositivo) -- **sugerir nunca es descargar** (ADR-0002): un trabajo de
transcripcion jamas dispara una descarga por su cuenta (`allow_download=False`
siempre, blindado desde el lote 2).
"""
from __future__ import annotations

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import av

from catalog import ModelSpec
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
    """Lo que HAY en la maquina. Barato, sin cargar modelo.

    `cuda_status` es tri-estado (ADR-0002 E9), NUNCA un bool: "se construyo el
    modelo" no prueba que la GPU funcione (medido, ver `smoke_test_cuda`).
    `probe_devices()` solo puede devolver "unavailable" o "probable" -- "confirmed"
    exige la prueba de humo real, que ocurre en la primera carga (`load_model`).
    """
    cuda_status: str                                  # "unavailable" | "probable" | "confirmed"
    cuda_device_count: int
    gpu_name: Optional[str]                          # "NVIDIA GeForce GTX 1050 Ti"
    compute_capability: Optional[tuple[int, int]]     # (6, 1) en Pascal
    vram_total_mb: Optional[int]
    vram_free_mb: Optional[int]
    supported_compute_types: list[str]                # p.ej. ["int8", "float32"]
    unavailable_reason: Optional[str]                 # codigo estable, nunca texto:
    # "no_nvidia_gpu" | "cuda_libs_missing" | "cuda_libs_not_on_path"
    # | "cuda_libs_mismatch" | "compute_capability_too_low" | "insufficient_vram"
    # | "smoke_test_failed"


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

# Orden de preferencia de compute_type (ARCHITECTURE.md Sec.3, politica 2): calidad
# primero, se cuantiza solo lo que el hardware obligue. Se filtra siempre contra
# `DeviceCapabilities.supported_compute_types`, que sale de CTranslate2, nunca de
# una tabla escrita por nosotros (E11: en Pascal no incluye float16 y es un
# ValueError limpio si se fuerza; en Ampere se espera que si lo incluya).
_GPU_COMPUTE_ORDER = ("float16", "int8_float16", "int8", "float32")
_CPU_COMPUTE_ORDER = (_CPU_COMPUTE_TYPE, "float32")

_VRAM_SLACK_MB = 512  # holgura ABSOLUTA (ADR-0002 Sec.7), nunca un porcentaje

# Suelo de viabilidad de `recommend_profile()` (ADR-0002 E2): un candidato con
# `speed_ratio` estimado por debajo de esto no se recomienda -- correria mas lento
# que el propio audio.
_MIN_VIABLE_SPEED_RATIO = 1.0

# Subcarpetas de site-packages/nvidia/ que pip crea al instalar requirements-gpu.txt.
# Deben coincidir con los paquetes fijados ahi (ADR-0002 E6): cublas, cudnn y la
# transitiva cuda_nvrtc que pip trae sin que nadie la pida.
_CUDA_DLL_SUBDIRS = ("cublas", "cudnn", "cuda_nvrtc")


def add_cuda_dlls_to_path() -> list[Path]:
    """Antepone al PATH del proceso las carpetas `bin/` de las DLL de CUDA que pip
    deja sueltas en `site-packages/nvidia/*/bin` (ADR-0002 E7).

    OBLIGATORIO llamarla antes de importar `ctranslate2` o `faster_whisper`: sin
    este paso el sintoma es IDENTICO a no tener las librerias instaladas, con pip
    diciendo que la instalacion fue exitosa [M-dev, SPIKE-GPU-RESULTS.md Sec.5].

    Devuelve las carpetas `bin/` que existian en disco y se antepusieron. Lista
    vacia si el complemento de GPU no esta instalado -- caso mayoritario, no un
    error.
    """
    added: list[Path] = []
    try:
        import nvidia  # paquete namespace que agrupa cublas/cudnn/cuda_nvrtc
    except ImportError:
        return added

    search_locations = getattr(nvidia, "__path__", None)
    if not search_locations:
        return added
    nvidia_root = Path(list(search_locations)[0])

    for sub in _CUDA_DLL_SUBDIRS:
        bin_dir = nvidia_root / sub / "bin"
        if bin_dir.is_dir():
            added.append(bin_dir)

    if not added:
        return added

    current = os.environ.get("PATH", "")
    prefix = os.pathsep.join(str(p) for p in added)
    os.environ["PATH"] = prefix + os.pathsep + current
    return added


def _query_gpu_info() -> tuple[
    Optional[str], Optional[tuple[int, int]], Optional[int], Optional[int]
]:
    """Nombre, compute capability y VRAM AHORA MISMO via `nvidia-smi`.

    `vram_free_mb` se lee en el momento, nunca se calcula restando de la capacidad
    nominal: el escritorio de Windows ya ocupa ~460 MiB en reposo [M-dev,
    SPIKE-GPU-RESULTS.md Sec.4]. Comprobacion barata: un solo proceso corto, sin
    tocar CUDA. Si `nvidia-smi` no esta (no hay driver NVIDIA), se degrada a
    "no se sabe", nunca a una excepcion que tumbe `probe_devices()`.
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,compute_cap,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None, None, None

    first_line = result.stdout.strip().splitlines()[0] if result.stdout.strip() else ""
    parts = [p.strip() for p in first_line.split(",")]
    if len(parts) != 4:
        return None, None, None, None

    name, cap_text, total_text, free_text = parts
    compute_capability: Optional[tuple[int, int]] = None
    if "." in cap_text:
        major_text, _, minor_text = cap_text.partition(".")
        if major_text.isdigit() and minor_text.isdigit():
            compute_capability = (int(major_text), int(minor_text))

    try:
        vram_total_mb: Optional[int] = int(float(total_text))
        vram_free_mb: Optional[int] = int(float(free_text))
    except ValueError:
        vram_total_mb = vram_free_mb = None

    return (name or None), compute_capability, vram_total_mb, vram_free_mb


def _unavailable(reason: str) -> DeviceCapabilities:
    return DeviceCapabilities(
        cuda_status="unavailable",
        cuda_device_count=0,
        gpu_name=None,
        compute_capability=None,
        vram_total_mb=None,
        vram_free_mb=None,
        supported_compute_types=[_CPU_COMPUTE_TYPE, "float32"],
        unavailable_reason=reason,
    )


def probe_devices() -> DeviceCapabilities:
    """Lo que hay en la maquina, SIN cargar ningun modelo. Comprobaciones baratas:

      1. Que las carpetas `bin/` de CUDA existan en disco y tengan DLL de verdad
         (tapa el caso "instalado pero no en el PATH", que da el mismo error que
         "no instalado" -- ADR-0002 Sec.6, no estaba en la recomendacion del spike
         y se anade a proposito porque es gratis).
      2. `ctranslate2.get_cuda_device_count() > 0`.
      3. `ctranslate2.get_supported_compute_types('cuda', 0)` -- se PREGUNTA a la
         libreria, jamas una tabla de compute capability escrita por nosotros (E11).

    Devuelve como mucho "probable", NUNCA "confirmed": la unica confirmacion real
    es la prueba de humo de `smoke_test_cuda()`, fusionada con la primera carga.
    """
    dll_dirs = add_cuda_dlls_to_path()
    if not dll_dirs:
        return _unavailable("cuda_libs_missing")

    if any(not any(bin_dir.glob("*.dll")) for bin_dir in dll_dirs):
        # Las carpetas existen (el paquete de pip esta) pero estan vacias: instalacion
        # a medias, no "no instalado". Se distingue porque la accion es distinta.
        return _unavailable("cuda_libs_not_on_path")

    try:
        import ctranslate2
    except (ImportError, OSError) as exc:
        logger.warning("ctranslate2 no cargo con el PATH de CUDA puesto: %s", one_line(str(exc)))
        return _unavailable("cuda_libs_mismatch")

    try:
        device_count = ctranslate2.get_cuda_device_count()
    except Exception as exc:  # ctranslate2 no documenta una jerarquia propia aqui
        logger.warning("get_cuda_device_count() fallo: %s", one_line(str(exc)))
        return _unavailable("cuda_libs_mismatch")

    if device_count <= 0:
        return _unavailable("no_nvidia_gpu")

    try:
        supported = list(ctranslate2.get_supported_compute_types("cuda", 0))
    except Exception as exc:
        logger.warning("get_supported_compute_types() fallo: %s", one_line(str(exc)))
        return _unavailable("cuda_libs_mismatch")

    if not supported:
        return _unavailable("compute_capability_too_low")

    gpu_name, compute_capability, vram_total_mb, vram_free_mb = _query_gpu_info()

    return DeviceCapabilities(
        cuda_status="probable",
        cuda_device_count=device_count,
        gpu_name=gpu_name,
        compute_capability=compute_capability,
        vram_total_mb=vram_total_mb,
        vram_free_mb=vram_free_mb,
        supported_compute_types=supported,
        unavailable_reason=None,
    )


def _pick_gpu_compute_type(
    spec: ModelSpec, caps: DeviceCapabilities, override: Optional[str]
) -> Optional[str]:
    """Primer compute_type que (a) soporta esta GPU y (b) deja >= 512 MiB libres.

    Lee el pico de VRAM directamente de `spec.vram_peak_mb` (catalog.py, lote 8):
    sin medicion para ese compute_type, se DESCARTA el candidato -- nunca se asume
    que cabe (ADR-0002 Sec.7: quedarse al borde es peor que un OOM limpio).
    """
    candidates = [override] if override else list(_GPU_COMPUTE_ORDER)

    for compute_type in candidates:
        if compute_type not in caps.supported_compute_types:
            continue
        if caps.vram_free_mb is None:
            continue
        peak = spec.vram_peak_mb.get(compute_type)
        if peak is None:
            continue
        if caps.vram_free_mb - peak >= _VRAM_SLACK_MB:
            return compute_type

    return None


def resolve_device(
    spec: ModelSpec,
    caps: DeviceCapabilities,
    preference: str = "auto",
    compute_type_override: Optional[str] = None,
) -> DeviceChoice:
    """Unica politica de eleccion de dispositivo (ARCHITECTURE.md Sec.3, ADR-0002).

    Vive aqui y en ningun otro sitio: la cascara solo puede pasar una preferencia
    (`"auto" | "cuda" | "cpu"`), nunca un dispositivo concreto. FUNCION PURA: no
    toca hardware, solo decide a partir de `caps` -- por eso se puede probar la
    politica de una RTX 3080 desde una GTX 1050 Ti con capacidades sinteticas
    (ARCHITECTURE.md Sec.14).

    Recibe el `ModelSpec` (de `catalog.py`, lote 8), no un `model_id`: asi no tiene
    que buscar en ningun catalogo y sigue siendo pura en sus argumentos.
    """
    if preference == "cpu":
        return DeviceChoice(
            device="cpu",
            device_index=0,
            compute_type=compute_type_override or _CPU_COMPUTE_TYPE,
            cpu_threads=0,
            fell_back_from=None,
            fallback_reason=None,
        )

    wants_gpu = preference in ("auto", "cuda")

    if wants_gpu and caps.cuda_status != "unavailable":
        chosen = _pick_gpu_compute_type(spec, caps, compute_type_override)
        if chosen is not None:
            return DeviceChoice(
                device="cuda",
                device_index=0,
                compute_type=chosen,
                cpu_threads=0,
                fell_back_from=None,
                fallback_reason=None,
            )
        # Ningun compute_type soportado deja la holgura de VRAM exigida: CPU, y se
        # dice por que (nunca una caida muda -- ARCHITECTURE.md Sec.3).
        return DeviceChoice(
            device="cpu",
            device_index=0,
            compute_type=compute_type_override or _CPU_COMPUTE_TYPE,
            cpu_threads=0,
            fell_back_from="cuda",
            fallback_reason="insufficient_vram",
        )

    fell_back_from = "cuda" if (wants_gpu and caps.cuda_status == "unavailable") else None
    fallback_reason = caps.unavailable_reason if fell_back_from else None

    return DeviceChoice(
        device="cpu",
        device_index=0,
        compute_type=compute_type_override or _CPU_COMPUTE_TYPE,
        cpu_threads=0,
        fell_back_from=fell_back_from,
        fallback_reason=fallback_reason,
    )


@dataclass(frozen=True)
class ModelRecommendation:
    model_id: str
    compute_type: str
    reason: str                            # codigo estable: "best_quality_fits_vram" |
                                            # "budget_limited" | "cpu_only"
    estimated_speed_ratio: Optional[float]  # None si no hay medicion para ese perfil


def _recommendation_reason(choice: DeviceChoice) -> str:
    """Por que ESTE candidato quedo con este `DeviceChoice` (ver `recommend_profile`).

    `"budget_limited"` es literalmente el presupuesto de VRAM: el candidato cayo a
    CPU porque, con GPU presente, ningun `compute_type` dejaba la holgura de 512
    MiB exigida (ADR-0002 Sec.7) -- no porque la GPU no exista. `"cpu_only"` cubre
    todo lo demas: sin GPU en absoluto, o el usuario pidio CPU.
    """
    if choice.device == "cuda":
        return "best_quality_fits_vram"
    if choice.fallback_reason == "insufficient_vram":
        return "budget_limited"
    return "cpu_only"


def recommend_profile(
    caps: DeviceCapabilities, catalog: dict[str, ModelSpec]
) -> list[ModelRecommendation]:
    """Que modelo(s) recomendar para ESTA maquina (ARCHITECTURE.md Sec.3, ADR-0002
    E1/E2). SUGIERE, nunca actua: no descarga nada, no carga ningun modelo. Es la
    misma politica que `resolve_device()` a otra granularidad (que modelo, en vez
    de que dispositivo) -- por eso viven juntas en este archivo.

    1) FILTRO DE VIABILIDAD (E2): un candidato entra solo si su `speed_ratio`
       estimado (para el `DeviceChoice` que le tocaria via `resolve_device()`, que
       ya aplica la holgura de VRAM de Sec.7) es >= `_MIN_VIABLE_SPEED_RATIO`.
       Sin medicion para ese `(device, compute_type)`, el candidato NO pasa --
       mismo criterio conservador que la VRAM: nunca se afirma lo que no se midio.
       Si NINGUNO pasa, se devuelve el mas rapido disponible -- nunca lista vacia.
    2) ORDEN por calidad (`quality_rank` ascendente, 1 = mejor); a igualdad, por
       velocidad (mayor primero); a igualdad de ambas, por peso (`expected_bytes`
       ascendente).

    Recomendar NO es resolver un dispositivo: esta funcion nunca dispara una
    descarga (esa es una decision de usuario, ADR-0001 D4/Sec.8); `resolve_device()`
    sigue siendo la unica que corre por trabajo, sobre un modelo ya elegido y ya
    descargado.
    """
    scored: list[tuple[ModelSpec, DeviceChoice, Optional[float]]] = []
    for spec in catalog.values():
        choice = resolve_device(spec, caps, preference="auto")
        estimated_speed_ratio = spec.speed_ratio.get(f"{choice.device}_{choice.compute_type}")
        scored.append((spec, choice, estimated_speed_ratio))

    viable = [
        item for item in scored
        if item[2] is not None and item[2] >= _MIN_VIABLE_SPEED_RATIO
    ]

    if not viable:
        # Nunca una lista vacia (ADR-0002 E2): se ofrece el mas rapido, aunque
        # ninguno supere el suelo de viabilidad.
        spec, choice, ratio = max(scored, key=lambda item: item[2] if item[2] is not None else -1.0)
        return [
            ModelRecommendation(
                model_id=spec.model_id,
                compute_type=choice.compute_type,
                reason=_recommendation_reason(choice),
                estimated_speed_ratio=ratio,
            )
        ]

    viable.sort(key=lambda item: (item[0].quality_rank, -item[2], item[0].expected_bytes))
    return [
        ModelRecommendation(
            model_id=spec.model_id,
            compute_type=choice.compute_type,
            reason=_recommendation_reason(choice),
            estimated_speed_ratio=ratio,
        )
        for spec, choice, ratio in viable
    ]


def smoke_test_cuda(model: object) -> tuple[bool, Optional[str]]:
    """LA UNICA comprobacion fiable de que la GPU funciona de verdad (ADR-0002 E8).

    `model` debe haberse construido con `device="cuda"`. Ejercita la ruta de
    verdad: una inferencia real sobre medio segundo de audio sintetico generado EN
    MEMORIA (silencio; nunca toca disco). En el camino feliz cuesta ~0,1 s porque
    el modelo ya estaba cargado (ADR-0002 Sec.6) -- por eso vive fusionada con la
    primera carga real en `load_model()`, no como un paso de arranque aparte.

    Devuelve `(ok, reason)`. Si `ok=False`, `reason` es uno de:
    "gpu_libraries_missing" | "gpu_out_of_memory" | "gpu_unavailable", clasificado
    por SUBCADENA del `RuntimeError` (fragil por diseno -- mismo aviso de
    fragilidad que la clasificacion de errores de yt-dlp, ARCHITECTURE.md Sec.5).
    """
    import numpy as np

    sample_rate = 16000
    duration_seconds = 0.5
    silence = np.zeros(int(sample_rate * duration_seconds), dtype=np.float32)

    try:
        segments, _info = model.transcribe(silence, language="en", vad_filter=False)
        list(segments)  # faster-whisper devuelve un generador: el trabajo ocurre al iterar
    except RuntimeError as exc:
        message = str(exc)
        if "not found or cannot be loaded" in message:
            return False, "gpu_libraries_missing"
        if "out of memory" in message:
            return False, "gpu_out_of_memory"
        logger.warning("smoke_test_cuda: RuntimeError sin clasificar: %s", one_line(message))
        return False, "gpu_unavailable"
    except Exception as exc:  # cubo por defecto: tambien es "no funciona", nunca se propaga
        logger.warning("smoke_test_cuda: fallo no RuntimeError: %s", one_line(str(exc)))
        return False, "gpu_unavailable"

    return True, None


def _build_whisper_model(
    model_id: str, models_dir: Path, choice: DeviceChoice, allow_download: bool
):
    """Construye el `WhisperModel` con el `DeviceChoice` dado, o CoreError.

    Interno. No confirma que la GPU funcione (ver `load_model` para eso): esto
    solo construye -- que, medido, tampoco falla aunque falten las DLL de CUDA
    (ADR-0002 E8).
    """
    # OBLIGATORIO antes de importar faster_whisper/ctranslate2 (ADR-0002 E7): si el
    # complemento de GPU no esta instalado, esta llamada no hace nada (lista vacia).
    add_cuda_dlls_to_path()
    from faster_whisper import WhisperModel  # import perezoso, ver cabecera del modulo

    try:
        return WhisperModel(
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

    **Lote 7 (ADR-0002 E8/Sec.6):** si `choice.device == "cuda"`, la prueba de humo
    corre aqui mismo, fusionada con esta primera carga -- en el camino feliz cuesta
    ~0,1 s porque el modelo ya estaba cargado. Si la prueba falla, se recarga en
    CPU UNA VEZ (nunca se propaga el fallo como si fuera un error del trabajo) y el
    `DeviceChoice` devuelto lleva `fell_back_from`/`fallback_reason` para que la
    caida nunca sea muda (ARCHITECTURE.md Sec.3).
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    model = _build_whisper_model(model_id, models_dir, choice, allow_download)
    final_choice = choice

    if choice.device == "cuda":
        ok, reason = smoke_test_cuda(model)
        if not ok:
            logger.warning(
                "GPU no confirmada tras la prueba de humo (motivo=%s); se recarga en CPU",
                reason,
            )
            fallback_choice = DeviceChoice(
                device="cpu",
                device_index=0,
                compute_type=_CPU_COMPUTE_TYPE,
                cpu_threads=choice.cpu_threads,
                fell_back_from="cuda",
                fallback_reason=reason,
            )
            model = _build_whisper_model(model_id, models_dir, fallback_choice, allow_download)
            final_choice = fallback_choice

    # transcribe() necesita saber con que DeviceChoice se construyo este manejador
    # para rellenar TranscriptionResult.device_used, sin ampliar la firma publica
    # de transcribe() (que no recibe el device_choice como argumento aparte).
    setattr(model, _ATTR_DEVICE_CHOICE, final_choice)
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
