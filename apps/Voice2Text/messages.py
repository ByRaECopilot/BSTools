"""CASCARA: unico archivo con texto de pantalla en castellano (ARCHITECTURE.md Sec.2).

El nucleo (errors.py, transcribe.py, jobs.py, models.py, fetch.py) emite codigos y
datos, nunca texto para humanos (ADR-0001 D10, D12). Este archivo -- y SOLO este
archivo -- convierte esos codigos en las frases que ve el usuario. `app.py` importa
estas funciones para enriquecer lo que expone a `ui.html`; `ui.html` nunca decide
un texto de error por su cuenta, solo pinta lo que aqui se compuso.

Todo el copy viene de `UI-SPEC.md` (Pixel, lote 3) trasladado literalmente.

Convencion de la casa (igual que `export.py`): los COMENTARIOS y docstrings de
este archivo van sin acentos; los VALORES de las cadenas -- lo que de verdad
aparece en pantalla -- llevan acentos correctos, porque eso es la interfaz, no
la consola.
"""
from __future__ import annotations

from typing import Any, Optional

# --------------------------------------------------------------------- formato

def format_bytes(n: Optional[int]) -> str:
    """Sigue la convencion de UI-SPEC.md (MB por debajo de 1 GB, GB con una
    cifra decimal por encima), con coma decimal (castellano).
    """
    if not n:
        return "0 MB"
    mb = n / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB".replace(".", ",")
    return f"{mb:.0f} MB"


def format_minutes_per_10(speed_ratio: Optional[float]) -> Optional[str]:
    """Regla de unidad OBLIGATORIA (ADR-0002 Sec.8.4 / ARCHITECTURE.md Sec.8):
    SIEMPRE "X min de proceso por cada 10 min de audio", JAMAS un multiplicador
    `x`. Ya hubo un incidente real de lectura invertida sobre esta cifra.
    """
    if not speed_ratio or speed_ratio <= 0:
        return None
    minutes = 10.0 / speed_ratio
    return f"{minutes:.1f}".replace(".", ",") + " min de proceso por cada 10 min de audio"


def format_mmss(seconds: Optional[float]) -> str:
    if not seconds or seconds < 0:
        seconds = 0
    total = int(round(seconds))
    hh, remainder = divmod(total, 3600)
    mm, ss = divmod(remainder, 60)
    if hh:
        return f"{hh}:{mm:02d}:{ss:02d}"
    return f"{mm}:{ss:02d}"


def format_percent(fraction: Optional[float]) -> Optional[str]:
    if fraction is None:
        return None
    return f"{round(fraction * 100)} %"


# ---------------------------------------------------------- exclusividad (Sec.5)

def exclusivity_dialog(info: dict[str, Any]) -> dict[str, str]:
    """La ventana no llega a abrirse (ARCHITECTURE.md Sec.6.4). Un solo boton:
    es informacion, no una eleccion (UI-SPEC.md Sec.5).
    """
    port = info.get("port") or 8317
    return {
        "title": "Voice2Text ya está en marcha en modo servidor",
        "body": (
            f"Voice2Text ya está en marcha en modo servidor (puerto {port}).\n\n"
            "Ciérralo desde su ventana de consola, o con Ctrl+C, y vuelve a intentarlo."
        ),
        "button": "Entendido",
    }


# ------------------------------------------------------- fases (UI-SPEC Sec.8.1)

PHASE_TITLES: dict[str, str] = {
    "queued": "En cola",
    "probing": "Consultando el enlace…",
    "detecting_language": "Preparando el audio…",
    "fetching": "Descargando…",
    "downloading_model": "Descargando el modelo…",
    "loading_model": "Cargando el modelo…",
    "transcribing": "Transcribiendo…",
    "writing": "Guardando el resultado…",
    "finished": "Listo",
}


def phase_title(phase: Optional[str]) -> str:
    return PHASE_TITLES.get(phase or "", "Trabajando…")


# ------------------------------------------- detecting_language (UI-SPEC Sec.8.3)

def _detecting_language_upper_bound_seconds(media_duration_seconds: float) -> float:
    """Cota superior interpolada linealmente entre los tres puntos medidos en
    ARCHITECTURE.md Sec.4.3 (7 s/2 min - 22 s/37 min), UI-SPEC.md Sec.8.3.3.
    NUNCA un porcentaje: es una cota, se rotula como tal.
    """
    minutes = media_duration_seconds / 60.0
    if minutes <= 2.0:
        return 7.0
    return 7.0 + 0.4286 * (minutes - 2.0)


def detecting_language_hint(elapsed_seconds: float, media_duration_seconds: Optional[float]) -> str:
    """UI-SPEC.md Sec.8.3.2 (sin duracion conocida) y Sec.8.3.3 (con duracion
    conocida -- mejora recomendada por Pixel en Sec.1.2 del mismo documento).

    `jobs.py` YA publica `media_duration_seconds` desde el instante de encolar
    (`_probe_duration_seconds`, lectura de cabecera sin decodificar), asi que la
    mejora del Sec.1.2 esta disponible desde hoy: se usa siempre que el dato
    exista, y se cae a los mensajes escalonados solo si de verdad falta (medio
    corrupto, cabecera sin duracion).
    """
    if media_duration_seconds:
        cap = _detecting_language_upper_bound_seconds(media_duration_seconds)
        return f"Puede tardar hasta ~{round(cap)} s en un archivo de esta duración."
    if elapsed_seconds <= 8:
        return "Leyendo el archivo y detectando el idioma…"
    if elapsed_seconds <= 20:
        return "Sigue en marcha: los archivos largos tardan más en este paso."
    return (
        "Todavía preparando el audio. En archivos de más de media hora esto puede "
        "llevar medio minuto; no hace falta reiniciar nada."
    )


# ------------------------------------------------------- cancelar (UI-SPEC Sec.9)

def cancel_button(phase: Optional[str], cancelling: bool) -> dict[str, Optional[str]]:
    """UI-SPEC.md Sec.9: dos situaciones distintas, y el boton no puede
    prometer lo que no cumple.
    """
    if not cancelling:
        return {"label": "Cancelar", "note": None}
    if phase in ("detecting_language",):
        return {"label": "Cancelando…", "note": "Puede tardar unos segundos en archivos largos."}
    return {"label": "Cancelando…", "note": None}


WRITING_CANCEL_WARNING = "Está a punto de terminar; cancelar ahora perderá el resultado."


# ------------------------------------------------- chip de dispositivo (Sec.4.3)

UNAVAILABLE_REASON_SHORT: dict[str, str] = {
    "no_nvidia_gpu": "no se detecta una GPU NVIDIA",
    "cuda_libs_missing": "falta el complemento de aceleración",
    "cuda_libs_not_on_path": "el complemento de aceleración está incompleto",
    "cuda_libs_mismatch": "el complemento de aceleración no coincide con esta GPU",
    "compute_capability_too_low": "la GPU es demasiado antigua para acelerar",
    "insufficient_vram": "no queda memoria de vídeo suficiente",
    "smoke_test_failed": "la prueba de la GPU no pasó",
}


def device_chip(
    cuda_status: str,
    gpu_name: Optional[str] = None,
    fell_back_from: Optional[str] = None,
    fallback_reason: Optional[str] = None,
) -> dict[str, str]:
    """UI-SPEC.md Sec.4.3. NUNCA "GPU activa" antes de la prueba de humo real."""
    if fell_back_from == "cuda":
        motivo = UNAVAILABLE_REASON_SHORT.get(fallback_reason or "", fallback_reason or "motivo desconocido")
        return {"label": f"CPU (la GPU falló: {motivo})", "icon": "cpu", "severity": "warn"}
    if cuda_status == "confirmed":
        label = "GPU activa" + (f" · {gpu_name}" if gpu_name else "")
        return {"label": label, "icon": "zap", "severity": "ok"}
    if cuda_status == "probable":
        return {"label": "GPU disponible · se confirma al transcribir", "icon": "zap", "severity": "muted"}
    return {"label": "CPU", "icon": "cpu", "severity": "neutral"}


# -------------------------------------------------- vocabulario de calidad (7.1.2)

QUALITY_ADJECTIVES: dict[int, str] = {
    1: "El más preciso",
    2: "Muy preciso",
    3: "Preciso",
    4: "Preciso, para uso normal",
    5: "Básico — más rápido, se equivoca más con nombres y cifras",
}


def quality_adjective(quality_rank: int) -> str:
    return QUALITY_ADJECTIVES.get(quality_rank, "Preciso")


def model_card_texts(
    *,
    quality_rank: int,
    expected_bytes: int,
    memory_peak_mb: Optional[int],
    speed_ratio: Optional[float],
) -> dict[str, str]:
    """Los DOS numeros obligatorios (ADR-0002 E3): descarga y memoria al usarse,
    mas el adjetivo de calidad y la velocidad -- nunca un multiplicador (Sec.7.1.2).
    """
    speed_text = format_minutes_per_10(speed_ratio)
    return {
        "quality_adjective": quality_adjective(quality_rank),
        "download_text": format_bytes(expected_bytes),
        "memory_text": (f"Ocupa ~{format_bytes(memory_peak_mb * 1024 * 1024)} en memoria al usarse" if memory_peak_mb else "Ocupación en memoria: sin medir en este perfil"),
        "speed_text": (speed_text if speed_text else "Velocidad: sin medir en este perfil"),
    }


# ------------------------------------------------------------ avisos (Sec.12)

def has_video_warning(bytes_downloaded: int) -> str:
    mb = format_bytes(bytes_downloaded)
    return (
        f"Esa plataforma no ofrece hoy una pista de audio suelta: se han descargado {mb} de "
        "vídeo además del audio. El texto sale igual — solo se bajó más de lo estrictamente necesario."
    )


def ytdlp_stale_warning(age_days: int) -> str:
    return (
        f"Tu yt-dlp tiene {age_days} días. Si algún enlace falla, prueba actualizándolo: "
        "py -3 -m pip install --upgrade yt-dlp"
    )


YTDLP_UNAVAILABLE_WARNING = (
    "La descarga desde enlaces no está disponible ahora mismo (falta un componente). "
    "Puedes seguir usando archivos locales sin ningún problema."
)

LANGUAGE_CONFIDENCE_WARNING = (
    "No estoy muy seguro del idioma detectado. Si el texto no encaja, vuelve a "
    "transcribir fijando el idioma a mano en Opciones."
)


def fallback_warning(fallback_reason: Optional[str]) -> Optional[dict[str, str]]:
    """Trabajo YA terminado que cayo a CPU (Sec.10): aviso --warn, nunca error.
    ARCHITECTURE.md Sec.3: "la caida a CPU nunca es silenciosa".
    """
    if not fallback_reason:
        return None
    if fallback_reason == "gpu_libraries_missing":
        return {
            "title": (
                "Se ha transcrito con la CPU: no se pudo usar la GPU (falta el "
                "complemento de aceleración). El texto sigue siendo el mismo."
            ),
            "action_label": "Cómo instalar el complemento de GPU",
        }
    motivo = UNAVAILABLE_REASON_SHORT.get(fallback_reason, fallback_reason)
    return {
        "title": f"Se ha transcrito con la CPU: no se pudo usar la GPU ({motivo}). El texto sigue siendo el mismo.",
        "action_label": None,
    }


# ------------------------------------------------------- errores (Sec.5 + Sec.11)

def _fmt_details_bytes(details: dict[str, Any], key: str) -> str:
    return format_bytes(details.get(key))


# Cookies del navegador (encargo del 2026-08-10): nombre tecnico -> nombre que ve el
# usuario. `details["cookies_from_browser"]` (fetch.py, `_raise_for_download_error`)
# solo lleva el NOMBRE del navegador -- nunca una cookie -- por eso es seguro
# formatearlo directo en pantalla.
_BROWSER_DISPLAY_NAMES: dict[str, str] = {
    "chrome": "Chrome",
    "edge": "Edge",
    "firefox": "Firefox",
}


def _browser_display_name(details: dict[str, Any]) -> str:
    code = details.get("cookies_from_browser")
    return _BROWSER_DISPLAY_NAMES.get(code or "", "el navegador")


_ERROR_TEMPLATES: dict[str, dict[str, Any]] = {
    "unsupported_url": {
        "title": "No sé descargar de ese sitio.",
        "hint": "Descarga el archivo y arrástralo aquí.",
        "primary": ("Elegir un archivo en su lugar", "choose_file"),
        "secondary": None,
        "surface": "card",
    },
    "login_required": {
        "title": "Ese contenido exige iniciar sesión.",
        "hint": "Descárgalo tú y arrástralo aquí, o activa tus cookies del navegador en Ajustes avanzados: solo se usan para esta descarga, nunca se guardan.",
        "primary": ("Activar cookies del navegador", "go_to_settings"),
        "secondary": ("Descargar el archivo yo mismo", "open_source_url"),
        "surface": "card",
    },
    "cookies_browser_not_found": {
        "title": "No encuentro las cookies de {browser} en este equipo.",
        "hint": "Revisa que {browser} esté instalado y que hayas iniciado sesión en YouTube con él, o elige otro navegador en Ajustes avanzados.",
        "primary": ("Ir a Ajustes avanzados", "go_to_settings"),
        "secondary": ("Reintentar", "retry"),
        "surface": "card",
    },
    "cookies_browser_locked": {
        "title": "{browser} está abierto y bloquea el acceso a sus cookies.",
        "hint": "Cierra {browser} por completo (revisa que no quede en segundo plano) y vuelve a intentarlo.",
        "primary": ("Reintentar", "retry"),
        "secondary": None,
        "surface": "card",
    },
    "cookies_expired": {
        "title": "Tus cookies de {browser} ya no bastan para iniciar sesión (puede que hayan caducado).",
        "hint": "Vuelve a iniciar sesión en YouTube desde {browser} y reintenta.",
        "primary": ("Reintentar", "retry"),
        "secondary": ("Elegir otro origen", "restart"),
        "surface": "card",
    },
    "geo_blocked": {
        "title": "Ese contenido no está disponible en tu país.",
        "hint": None,
        "primary": ("Elegir otro origen", "restart"),
        "secondary": None,
        "surface": "card",
    },
    "media_unavailable": {
        "title": "Ese contenido ya no existe, es privado o está protegido.",
        "hint": "Comprueba el enlace en el navegador.",
        "primary": ("Comprobar el enlace en el navegador", "open_source_url"),
        "secondary": ("Elegir otro origen", "restart"),
        "surface": "card",
    },
    "download_failed": {
        "title": "Falló la descarga.",
        "hint": "Revisa tu conexión y vuelve a intentarlo.",
        "primary": ("Reintentar", "retry"),
        "secondary": ("Elegir otro origen", "restart"),
        "surface": "card",
    },
    "extractor_outdated": {
        "title": "Puede que yt-dlp se haya quedado atrás: las plataformas cambian a menudo.",
        "hint": "Actualízalo: py -3 -m pip install --upgrade yt-dlp",
        "primary": ("Copiar el comando", "copy:py -3 -m pip install --upgrade yt-dlp"),
        "secondary": ("Reintentar de todos modos", "retry"),
        "surface": "card",
    },
    "no_audio_stream": {
        "title": "Ese medio no tiene audio.",
        "hint": None,
        "primary": ("Elegir otro archivo", "choose_file"),
        "secondary": None,
        "surface": "card",
    },
    "decode_failed": {
        "title": "No he podido leer el audio de ese archivo.",
        "hint": "Puede estar incompleto o protegido.",
        "primary": ("Elegir otro archivo", "choose_file"),
        "secondary": None,
        "surface": "card",
    },
    "file_too_large": {
        "title": "El archivo pesa {size} y el tope es {limit}.",
        "hint": "Sube el tope en settings.json si de verdad lo necesitas.",
        "primary": ("Elegir otro archivo", "choose_file"),
        "secondary": None,
        "surface": "card",
    },
    "file_not_found": {
        "title": "No encuentro ese archivo.",
        "hint": "¿Lo has movido o renombrado?",
        "primary": ("Elegir otro archivo", "choose_file"),
        "secondary": None,
        "surface": "card",
    },
    "model_missing": {
        "title": "Falta el modelo de reconocimiento.",
        "hint": "Descárgalo desde el aviso de arriba ({expected}).",
        "primary": ("Ir a descargar el modelo", "go_to_models"),
        "secondary": None,
        "surface": "card",
    },
    "model_download_failed": {
        "title": "No he podido descargar el modelo ({downloaded} descargados).",
        "hint": "Comprueba la conexión; se reanuda donde se quedó.",
        "primary": ("Reintentar descarga", "retry"),
        "secondary": None,
        "surface": "card",
    },
    "disk_full": {
        "title": "No queda espacio en disco.",
        "hint": "Hacen falta {required} libres en {path}.",
        "primary": ("Reintentar", "retry"),
        "secondary": None,
        "surface": "card",
    },
    "queue_full": {
        "title": "Hay demasiados trabajos esperando.",
        "hint": "Espera a que terminen o cancela alguno.",
        "primary": None,
        "secondary": None,
        "surface": "toast",
    },
    "gpu_out_of_memory": {
        "title": "La GPU se ha quedado sin memoria.",
        "hint": None,
        "primary": ("Reintentar en CPU", "retry_cpu"),
        "secondary": ("Elegir un modelo más ligero", "go_to_options"),
        "surface": "card",
    },
    "gpu_libraries_missing": {
        "title": "Falta el complemento de GPU, o sus librerías no se encuentran.",
        "hint": "Ejecuta install-gpu.ps1. Se ha transcrito con la CPU.",
        "primary": None,
        "secondary": None,
        "surface": "card",
    },
    "gpu_unavailable": {
        "title": "No se ha podido usar la GPU.",
        "hint": "Se ha transcrito con la CPU; el detalle está abajo.",
        "primary": None,
        "secondary": None,
        "surface": "card",
    },
    "cancelled": {
        "title": "Cancelado.",
        "hint": None,
        "primary": None,
        "secondary": None,
        "surface": "neutral",
    },
    "internal": {
        "title": "Algo ha fallado por dentro.",
        "hint": "Detalle técnico abajo.",
        "primary": ("Reintentar", "retry"),
        "secondary": ("Copiar el detalle técnico", "copy_technical"),
        "surface": "card",
    },
}

# unsupported_url detectado por esquema, ANTES de tocar el nucleo (UI-SPEC Sec.7.2):
# validacion en linea bajo el campo de enlace, nunca una tarjeta completa.
INLINE_UNSUPPORTED_SCHEME = (
    "No reconozco ese tipo de enlace. Prueba con http:// o https://, o arrastra el archivo directamente."
)

DRAG_DROP_MULTIPLE_FILES = "Solo puedo procesar un archivo a la vez; se ha tomado el primero."


def error_message(code: str, details: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Traduce un `job.error` (o cualquier `CoreError`) a lo que pinta la
    pantalla: titulo, pista, botones y donde se presenta (Sec.11).
    """
    details = details or {}

    template = _ERROR_TEMPLATES.get(code, _ERROR_TEMPLATES["internal"])
    title = template["title"]
    hint = template["hint"]

    if code == "file_too_large":
        title = title.format(size=_fmt_details_bytes(details, "size_bytes"), limit=_fmt_details_bytes(details, "limit_bytes"))
    elif code == "model_missing":
        hint = hint.format(expected=_fmt_details_bytes(details, "expected_bytes"))
    elif code == "model_download_failed":
        title = title.format(downloaded=_fmt_details_bytes(details, "downloaded_bytes"))
    elif code == "disk_full":
        hint = hint.format(required=_fmt_details_bytes(details, "required_bytes"), path=details.get("path", ""))
    elif code in ("cookies_browser_not_found", "cookies_browser_locked", "cookies_expired"):
        browser = _browser_display_name(details)
        title = title.format(browser=browser)
        hint = hint.format(browser=browser)

    return {
        "code": code,
        "title": title,
        "hint": hint,
        "primary": template["primary"],
        "secondary": template["secondary"],
        "surface": template["surface"],
    }
