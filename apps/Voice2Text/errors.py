"""MOTOR: codigos de error estables y la excepcion que los transporta.

Ninguna cadena en castellano vive aqui (ADR-0001 D10). La traduccion a texto de
pantalla es responsabilidad exclusiva de la cascara (`messages.py`, lote 3): este
archivo no sabe que existe una interfaz, ni que hay un idioma.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional


class ErrorCode(str, Enum):
    UNSUPPORTED_URL = "unsupported_url"
    LOGIN_REQUIRED = "login_required"
    GEO_BLOCKED = "geo_blocked"
    MEDIA_UNAVAILABLE = "media_unavailable"
    DOWNLOAD_FAILED = "download_failed"
    EXTRACTOR_OUTDATED = "extractor_outdated"
    NO_AUDIO_STREAM = "no_audio_stream"
    DECODE_FAILED = "decode_failed"
    FILE_TOO_LARGE = "file_too_large"
    FILE_NOT_FOUND = "file_not_found"
    MODEL_MISSING = "model_missing"
    MODEL_DOWNLOAD_FAILED = "model_download_failed"
    DISK_FULL = "disk_full"
    QUEUE_FULL = "queue_full"
    CANCELLED = "cancelled"
    INTERNAL = "internal"
    # Lote 7 (ADR-0002 E10): los tres modos de fallo de CUDA son RuntimeError, pero
    # piden acciones distintas -- reparar instalacion, elegir modelo menor, o nada.
    # Se distinguen por subcadena del mensaje en transcribe.smoke_test_cuda().
    GPU_LIBRARIES_MISSING = "gpu_libraries_missing"
    GPU_OUT_OF_MEMORY = "gpu_out_of_memory"
    GPU_UNAVAILABLE = "gpu_unavailable"


class CoreError(Exception):
    """Unica forma en la que el motor sale de sus limites (ADR-0001 D10, D11).

    `details` solo lleva datos que la cascara necesita para redactar (numeros,
    rutas, limites): NUNCA texto pensado para pantalla. `technical` es una sola
    linea del error original -- nunca un traceback completo.
    """

    def __init__(
        self,
        code: ErrorCode,
        details: Optional[dict[str, Any]] = None,
        technical: str = "",
    ) -> None:
        self.code = code
        self.details: dict[str, Any] = details or {}
        self.technical = technical
        super().__init__(f"{code.value}: {technical}" if technical else code.value)


def one_line(message: str) -> str:
    """Recorta un mensaje de excepcion a una sola linea (regla de `technical`)."""
    return " ".join(message.strip().splitlines()[:1]) if message else ""
