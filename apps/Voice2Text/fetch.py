"""MOTOR: descarga de enlaces publicos con yt-dlp -- aislado y opcional (ADR-0001 D7).

Puro, tal como exige ADR-0001 D11 / ARCHITECTURE.md Sec.2: sin estado global, sin leer
`settings.json`, sin `print` (usa excepciones de `errors.py`), sin una sola palabra en
castellano. No importa `webview` ni `http.server`. Quien lo llama (la cascara, lote 3/6)
pasa `player_clients` por argumento (ADR-0001 D26): este archivo NUNCA lee configuracion.

`import yt_dlp` es SIEMPRE perezoso -- dentro de las funciones, nunca a nivel de modulo
(mismo cortafuegos que exige D7 para que un yt-dlp roto o ausente no rompa la
transcripcion de archivos locales; `transcribe.py`/`export.py` no importan este archivo).

Regla obligatoria, medida en el spike (SPIKE-RESULTS.md S6) y escrita en ADR-0001 Sec.3.2
y ARCHITECTURE.md Sec.3: **que caiga un archivo MUXEADO (video+audio) es FLUJO NORMAL,
nunca un error.** Sin cookies, YouTube redujo su catalogo de formatos accesibles a un
unico `itag` ya muxeado en el 100% de los videos probados. `FetchedMedia.has_video` es
un DATO para que la cascara lo comente, no una senal de fallo:

  - JAMAS se levanta `DOWNLOAD_FAILED` ni `NO_AUDIO_STREAM` porque haya caido un muxeado.
  - `NO_AUDIO_STREAM` se reserva a que PyAV, sobre el archivo YA DESCARGADO, confirme que
    de verdad no hay ninguna pista de audio -- nunca se infiere del contenedor o del
    `player_client` usado.

Cookies del navegador (encargo del 2026-08-10), OPCIONAL y desactivada por defecto,
mismo patron D26 que `player_clients`: `cookies_from_browser` llega SIEMPRE por
argumento -- este archivo NUNCA lee `settings.json`, ni sabe que existe. Contrato de
privacidad, innegociable: las cookies son credenciales de sesion de quien las presta.
Este archivo NUNCA fija `cookiefile` (no se escribe un cookiejar propio a disco), NUNCA
registra ni un byte de su contenido (ni en `technical`, ni en `details` de `CoreError`:
solo viaja el NOMBRE del navegador, nunca el valor de una cookie), y le entrega el
nombre del navegador a `cookiesfrombrowser` de yt-dlp tal cual -- es yt-dlp quien lee el
perfil del navegador y lo descarta despues de cada llamada, no una copia nuestra.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable, NoReturn, Optional
from urllib.parse import urlsplit

from errors import CoreError, ErrorCode, one_line

# Selector cerrado por ADR-0001 D3: pide audio suelto y cae en `best` cuando la
# plataforma no lo ofrece -- es el `/best` de reserva el que salva el caso muxeado.
_FORMAT_SELECTOR = "bestaudio[abr<=128]/bestaudio/best"

# Opciones de yt-dlp cerradas por ADR-0001 D3 / D6 y ARCHITECTURE.md Sec.3. Los campos
# de credenciales van explicitos a `None` por politica, no por descuido (D6): esta
# herramienta NUNCA se autentica.
_YDL_BASE_OPTS: dict = {
    "noplaylist": True,           # un enlace de playlist NO puede lanzar 200 descargas
    "hls_prefer_native": True,    # descargador HLS propio, sin ffmpeg
    "retries": 3,
    "socket_timeout": 30,
    "quiet": True,
    "no_warnings": False,
    "cookiesfrombrowser": None,
    "cookiefile": None,
    "username": None,
    "password": None,
}

_ALLOWED_SCHEMES = ("http", "https")

_VERSION_DATE_RE = re.compile(r"^(\d{4})\.(\d{2})\.(\d{2})")


@dataclass(frozen=True)
class MediaInfo:
    """De `probe()`, SIN descargar."""
    title: str
    duration_seconds: Optional[float]
    extractor: str           # "youtube", "tiktok"...
    estimated_bytes: Optional[int]


@dataclass(frozen=True)
class FetchedMedia:
    path: Path                # work/<job_id>.<ext>
    title: str
    duration_seconds: Optional[float]
    bytes_downloaded: int
    container: str            # "mp4", "webm", "m4a"...
    has_video: bool           # True = cayo un stream MUXEADO. NO es un error (ver arriba)


def is_available() -> bool:
    """`yt_dlp` importable? Import perezoso: no falla si falta o esta roto."""
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        return False
    return True


def _import_yt_dlp():
    try:
        import yt_dlp
    except ImportError as exc:
        # No hay codigo dedicado para "yt_dlp no instalado": la cascara debe comprobar
        # `is_available()` ANTES de llegar aqui (Sec.5, avisos que no son error). Si de
        # todas formas se llega, es el cubo por defecto global.
        raise CoreError(
            ErrorCode.INTERNAL,
            details={"reason": "yt_dlp_not_importable"},
            technical=one_line(str(exc)),
        ) from exc
    return yt_dlp


def ytdlp_version() -> tuple[str, int]:
    """Version instalada y su antiguedad en dias, SIN tocar la red.

    La version de yt-dlp es una fecha (`AAAA.MM.DD[...]`, con posible sufijo de build):
    basta con parsear la cadena que ya trae el paquete instalado (medido en el spike:
    "2026.7.4" con 37 dias de antiguedad el 2026-08-10).
    """
    yt_dlp = _import_yt_dlp()
    version = getattr(yt_dlp.version, "__version__", "") or ""
    match = _VERSION_DATE_RE.match(version)
    if not match:
        return version, 0
    year, month, day = (int(part) for part in match.groups())
    try:
        released = date(year, month, day)
    except ValueError:
        return version, 0
    age_days = max((date.today() - released).days, 0)
    return version, age_days


def validate_url(url: str) -> None:
    """Solo `http`/`https` llegan a yt-dlp (ARCHITECTURE.md Sec.3).

    Publica (sin guion bajo) porque `jobs.py` la llama tambien -- es la
    validacion barata y SINCRONA que exige encolar (ARCHITECTURE.md Sec.3:
    "validacion barata SINCRONA, trabajo ASINCRONO"): un esquema invalido
    falla al encolar, no tras arrancar un trabajo.
    """
    scheme = urlsplit(url).scheme.lower()
    if scheme not in _ALLOWED_SCHEMES:
        raise CoreError(
            ErrorCode.UNSUPPORTED_URL,
            details={"url": url},
            technical=f"scheme not allowed: {scheme or '(none)'}",
        )


def normalize_cookies_from_browser(value: Optional[str]) -> Optional[str]:
    """`None` (el valor por defecto de `settings.py`, ADR-0003 C2) o cadena vacia se
    normalizan a `None` -- "desactivado". El sentinela de texto `"none"` tambien se
    acepta por si acaso (p.ej. `cli.py`, donde un flag de linea de comandos no puede
    llevar `null` de verdad). Cualquier otro valor se devuelve tal cual, en
    minusculas: esta funcion NO decide la lista de navegadores soportados (eso vive
    en settings.py/ui.html/cli.py, capa de cascara); un nombre que yt-dlp no
    reconozca termina en `CoreError(COOKIES_BROWSER_NOT_FOUND)` al primer intento de
    descarga, no aqui. Pura y sin estado, para que las tres cascaras (mas `jobs.py`)
    no dupliquen el mismo chequeo cada una a su manera.
    """
    if not value:
        return None
    value = value.strip().lower()
    return value if value and value != "none" else None


def _base_ydl_opts(player_clients: list[str], cookies_from_browser: Optional[str] = None) -> dict:
    opts = dict(_YDL_BASE_OPTS)
    # `player_clients` llega SIEMPRE por argumento (D26): este archivo no lo lee de
    # `settings.json`. Es el parametro que mas rapido caduca [O] -- se arregla editando
    # un dato, sin tocar esta linea.
    opts["extractor_args"] = {"youtube": {"player_client": list(player_clients)}}
    if cookies_from_browser:
        # Tupla que exige la API de yt-dlp: (browser_name, profile, keyring, container).
        # Solo el navegador nos hace falta hoy -- el resto se deja en su default
        # (perfil mas reciente, sin contenedor). NUNCA se fija `cookiefile`: las
        # cookies se leen del navegador y se le pasan a yt-dlp en memoria, jamas se
        # escribe un cookiejar propio (contrato de privacidad de este modulo).
        opts["cookiesfrombrowser"] = (cookies_from_browser,)
    return opts


# Fragilidad declarada (ADR-0001 Sec.10 / ARCHITECTURE.md Sec.5): estos tres codigos se
# distinguen buscando subcadenas en el mensaje de yt-dlp, que cambia con las versiones.
_LOGIN_REQUIRED_MARKERS = (
    "sign in", "log in", "cookies", "age-restricted", "age restricted",
    "confirm you're not a bot", "private video", "requires purchase",
    "this is a private", "join this channel",
)
_GEO_BLOCKED_MARKERS = (
    "not available in your country", "not available from your location",
    "blocked it in your country", "geo restricted", "geo-restricted",
    "not made this video available in your country",
    # Medido en este lote (2026-08-10, TikTok, IP residencial): "Your IP address is
    # blocked from accessing this post". No es literalmente "geografico", pero es la
    # misma familia -- acceso restringido por origen de red, no por sesion -- y es el
    # cubo con el que la cascara ya sabe redactar ("no disponible en tu pais/red").
    "ip address is blocked", "ip is blocked", "blocked from accessing",
)
_MEDIA_UNAVAILABLE_MARKERS = (
    "video unavailable", "has been removed", "no longer available",
    "content isn't available", "does not exist", "account associated",
    "drm protected", "this content is not available", "404",
)
_DOWNLOAD_FAILED_MARKERS = (
    "timed out", "timeout", "connection reset", "connection refused",
    "network is unreachable", "unable to download webpage",
    "http error 5", "urlopen error", "temporary failure",
)

# Cookies del navegador (encargo del 2026-08-10): tres subcadenas de yt-dlp/cookies.py,
# medidas en vivo (ver INFORME de la tarea) contra Chrome y Edge reales en Windows.
# Gateadas por `cookies_active` -- SOLO se consultan cuando la llamada de verdad pidio
# cookies, para no reclasificar por accidente un error de red que comparta alguna
# palabra suelta con estos mensajes.
_COOKIES_NOT_FOUND_MARKERS = (
    "could not find", "could not read local state", "unsupported browser",
)
_COOKIES_LOCKED_MARKERS = (
    "could not copy", "permission denied", "database is locked",
)
# Mensaje literal de yt-dlp cuando el propio antibot de YouTube sigue rechazando la
# sesion PESE a haber cookies activas -- es yt-dlp quien recomienda cookies con este
# texto exacto ("Sign in to confirm..."), asi que si ya las dimos y sigue apareciendo,
# la lectura mas honesta es que esa sesion ya no sirve (caducada), no que falte iniciar
# sesion. Con `cookies_active=False` este mismo texto cae en el cubo LOGIN_REQUIRED de
# siempre, sin cambios.
_COOKIES_STILL_BLOCKED_MARKERS = ("sign in to confirm",)


def _classify_download_error(message: str, cookies_active: bool = False) -> ErrorCode:
    low = message.lower()
    if cookies_active:
        if any(marker in low for marker in _COOKIES_STILL_BLOCKED_MARKERS):
            return ErrorCode.COOKIES_EXPIRED
        if any(marker in low for marker in _COOKIES_LOCKED_MARKERS):
            return ErrorCode.COOKIES_BROWSER_LOCKED
        if any(marker in low for marker in _COOKIES_NOT_FOUND_MARKERS):
            return ErrorCode.COOKIES_BROWSER_NOT_FOUND
    if "unsupported url" in low or "no extractor" in low:
        return ErrorCode.UNSUPPORTED_URL
    if any(marker in low for marker in _LOGIN_REQUIRED_MARKERS):
        return ErrorCode.LOGIN_REQUIRED
    if any(marker in low for marker in _GEO_BLOCKED_MARKERS):
        return ErrorCode.GEO_BLOCKED
    if any(marker in low for marker in _MEDIA_UNAVAILABLE_MARKERS):
        return ErrorCode.MEDIA_UNAVAILABLE
    if any(marker in low for marker in _DOWNLOAD_FAILED_MARKERS):
        return ErrorCode.DOWNLOAD_FAILED
    # Cubo por defecto de yt-dlp (ARCHITECTURE.md Sec.5): nunca se queda sin texto
    # comprensible -- lleva version y antiguedad para que la cascara sugiera actualizar.
    return ErrorCode.EXTRACTOR_OUTDATED


def _raise_for_download_error(exc: Exception, url: str, cookies_from_browser: Optional[str] = None) -> NoReturn:
    message = one_line(str(exc))
    code = _classify_download_error(message, cookies_active=bool(cookies_from_browser))
    details: dict = {"url": url}
    if cookies_from_browser:
        # Solo el NOMBRE del navegador (p.ej. "chrome") -- nunca una cookie, nunca una
        # ruta con contenido de sesion: es el mismo dato que ya circula como argumento
        # de esta llamada, no algo nuevo que este archivo empiece a exponer.
        details["cookies_from_browser"] = cookies_from_browser
    if code == ErrorCode.EXTRACTOR_OUTDATED:
        version, age_days = ytdlp_version()
        details["ytdlp_version"] = version
        details["ytdlp_age_days"] = age_days
    raise CoreError(code, details=details, technical=message)


def _safe_float(value: object) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _resolve_single_entry(info: Optional[dict]) -> dict:
    """`noplaylist=True` deberia bastar, pero algunos extractores devuelven un
    `_type: "playlist"` con una unica entrada de todas formas. Nunca se procesan varias
    entradas aqui: eso es exactamente lo que `noplaylist` existe para impedir.
    """
    if not info:
        return {}
    if info.get("_type") == "playlist":
        entries = [entry for entry in (info.get("entries") or []) if entry]
        return entries[0] if entries else info
    return info


def probe(url: str, player_clients: list[str], *, cookies_from_browser: Optional[str] = None) -> MediaInfo:
    """Titulo/duracion/extractor SIN descargar (fase `probing`, ARCHITECTURE.md Sec.4.3).

    `cookies_from_browser` (D26, mismo patron que `player_clients`): `None` =
    desactivado, igual que hoy. La cascara ya lo normaliza con
    `normalize_cookies_from_browser()` antes de llamar aqui.
    """
    validate_url(url)
    yt_dlp = _import_yt_dlp()

    opts = _base_ydl_opts(player_clients, cookies_from_browser)
    opts["format"] = _FORMAT_SELECTOR
    opts["postprocessors"] = []

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            raw_info = ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        _raise_for_download_error(exc, url, cookies_from_browser)
    except Exception as exc:  # yt-dlp no garantiza una jerarquia propia para todo
        raise CoreError(
            ErrorCode.INTERNAL, details={"url": url}, technical=one_line(str(exc))
        ) from exc

    info = _resolve_single_entry(raw_info)
    if not info:
        raise CoreError(
            ErrorCode.MEDIA_UNAVAILABLE,
            details={"url": url},
            technical="extract_info devolvio vacio",
        )

    return MediaInfo(
        title=info.get("title") or url,
        duration_seconds=_safe_float(info.get("duration")),
        extractor=(info.get("extractor") or "").lower(),
        estimated_bytes=info.get("filesize") or info.get("filesize_approx"),
    )


def fetch_audio(
    url: str,
    dest_dir: Path,
    job_id: str,
    *,
    player_clients: list[str],       # inyectado por la cascara (ADR-0001 D26)
    max_bytes: int,
    on_progress: Callable[[int, Optional[int]], None],   # (bytes hechos, total o None)
    should_cancel: Callable[[], bool],
    cookies_from_browser: Optional[str] = None,   # inyectado por la cascara, igual que player_clients
) -> FetchedMedia:
    """Descarga (fase `fetching`). Nunca exige ni invoca postprocesadores (D2/D3): jamas
    fusiona streams, jamas requiere el binario `ffmpeg`.

    `cookies_from_browser`: `None` = desactivado (comportamiento identico al de antes
    de este encargo). La cascara ya lo normaliza con `normalize_cookies_from_browser()`.
    """
    validate_url(url)
    yt_dlp = _import_yt_dlp()
    from yt_dlp.utils import DownloadCancelled, DownloadError

    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    # Nombrado por `job_id`, nunca con nombre fijo (ADR-0001 D15).
    outtmpl = str(dest_dir / f"{job_id}.%(ext)s")

    def _hook(status: dict) -> None:
        # Cancelacion cooperativa: se consulta en cada aviso de progreso, igual que
        # `transcribe.py` la consulta en cada vuelta del generador de segmentos.
        # `DownloadCancelled` es la excepcion que YoutubeDL.__download_wrapper()
        # reconoce y deja propagar tal cual (nunca la envuelve en DownloadError).
        if should_cancel():
            raise DownloadCancelled("cancelado por quien llama")

        state = status.get("status")
        if state == "downloading":
            downloaded = status.get("downloaded_bytes") or 0
            total = status.get("total_bytes") or status.get("total_bytes_estimate")
            on_progress(downloaded, total)
        elif state == "finished":
            done = status.get("downloaded_bytes") or status.get("total_bytes") or 0
            on_progress(done, status.get("total_bytes") or done)

    opts = _base_ydl_opts(player_clients, cookies_from_browser)
    opts["format"] = _FORMAT_SELECTOR
    opts["postprocessors"] = []              # PROHIBIDO (D2/D3): exigiria ffmpeg
    opts["outtmpl"] = outtmpl
    opts["max_filesize"] = max_bytes
    opts["progress_hooks"] = [_hook]

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            raw_info = ydl.extract_info(url, download=True)
    except DownloadCancelled as exc:
        raise CoreError(
            ErrorCode.CANCELLED, details={"url": url}, technical=one_line(str(exc))
        ) from exc
    except DownloadError as exc:
        _raise_for_download_error(exc, url, cookies_from_browser)
    except Exception as exc:
        raise CoreError(
            ErrorCode.INTERNAL, details={"url": url}, technical=one_line(str(exc))
        ) from exc

    info = _resolve_single_entry(raw_info)

    # "Tras la descarga, comprobar que hay exactamente un archivo" (ARCHITECTURE.md
    # Sec.3). Nombrado por job_id: no puede haber colision con otro trabajo.
    downloaded_files = sorted(dest_dir.glob(f"{job_id}.*"))
    if len(downloaded_files) == 0:
        raise CoreError(
            ErrorCode.DOWNLOAD_FAILED,
            details={"url": url, "bytes_downloaded": 0},
            technical="yt-dlp no produjo ningun archivo",
        )
    if len(downloaded_files) > 1:
        # Salvaguarda, no se ha observado en el spike: mas de un archivo con el mismo
        # job_id es un estado inconsistente (p.ej. restos de un intento previo), nunca
        # un dato a promediar o a ignorar en silencio.
        raise CoreError(
            ErrorCode.DOWNLOAD_FAILED,
            details={"url": url, "files": [str(f) for f in downloaded_files]},
            technical="mas de un archivo de salida para el mismo job_id",
        )

    media_path = downloaded_files[0]
    bytes_downloaded = media_path.stat().st_size

    # Salvaguarda de tamano: `max_filesize` de yt-dlp aborta la descarga mostrando un
    # aviso en pantalla, no lanzando una excepcion (medido en el codigo instalado,
    # yt_dlp/downloader/http.py). Si aun asi quedara un archivo mayor que el tope --
    # por ejemplo un HLS ya concatenado, que no pasa por ese chequeo -- se corta aqui.
    if bytes_downloaded > max_bytes:
        raise CoreError(
            ErrorCode.FILE_TOO_LARGE,
            details={"size_bytes": bytes_downloaded, "limit_bytes": max_bytes, "path": str(media_path)},
            technical="archivo descargado supera max_bytes",
        )

    container, has_video = _inspect_with_pyav(media_path)

    return FetchedMedia(
        path=media_path,
        title=info.get("title") or job_id,
        duration_seconds=_safe_float(info.get("duration")),
        bytes_downloaded=bytes_downloaded,
        container=container,
        has_video=has_video,
    )


def _inspect_with_pyav(media_path: Path) -> tuple[str, bool]:
    """Determina `container` y `has_video`, y confirma con PyAV si hay audio de verdad.

    Este es el UNICO sitio de todo el motor donde `no_audio_stream` puede levantarse
    para un enlace: se comprueba sobre el archivo YA DESCARGADO, nunca se infiere del
    `player_client` usado ni de que el resultado viniera muxeado.
    """
    import av

    try:
        with av.open(str(media_path)) as container:
            has_audio = any(stream.type == "audio" for stream in container.streams)
            has_video = any(stream.type == "video" for stream in container.streams)
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
            technical="el contenedor descargado no tiene pista de audio",
        )

    container_name = media_path.suffix.lstrip(".").lower() or "bin"
    return container_name, has_video
