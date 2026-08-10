"""MOTOR: catalogo de modelos, descarga con progreso real y cancelable, borrado.

Puro (ADR-0001 D11): sin estado global, sin leer configuracion, sin `print`, sin
`sys.exit`. No importa `webview` ni `http.server`. `huggingface_hub` SI se importa
de forma normal (no perezosa): a diferencia de `ctranslate2`/`faster_whisper`
(ARCHITECTURE.md Sec.3, E7), no toca CUDA ni depende de que el PATH del proceso ya
tenga nada puesto -- el import perezoso ahi existe por una razon concreta que aqui
no aplica.

Por que este archivo NO delega la descarga en `huggingface_hub.snapshot_download()`
aunque esa es la funcion que usa `faster_whisper.utils.download_model()` (y por
tanto `transcribe.load_model(..., allow_download=True)`) -- decision registrada
para que nadie la deshaga sin volver a medir primero:

  Se probo `snapshot_download(..., tqdm_class=<hook>)` para obtener progreso Y
  cancelacion reales. El progreso funciono a medias: con el backend "Xet" que trae
  el `hf_xet` instalado hoy, las llamadas de progreso llegan en saltos grandes
  (un archivo de 145 MB llego en una sola llamada de ~67 MB seguida de otra de
  ~145 MB), no en trozos pequenos y regulares. La cancelacion desde ese mismo gancho
  demostro el mismo problema: al cancelar durante la descarga de un archivo de
  145 MB, el archivo siguio bajando ~7 s mas hasta el siguiente punto de control,
  porque no hay otro sitio donde el propio backend consulte "¿sigo?". Para un
  archivo de 3,1 GB (large-v3) esa latencia de cancelacion es inaceptable para el
  requisito de "descarga cancelable" (encargo del lote 2).

  En su lugar, este archivo baja cada archivo del repositorio con `urllib.request`
  a mano, en trozos de 256 KiB, comprobando `should_cancel()` en CADA trozo -- eso
  SI da cancelacion sub-segundo, medida. De regalo: reanudacion por `Range` cuando
  se corta a la mitad (ARCHITECTURE.md Sec.8, punto 5), que `snapshot_download()`
  tambien ofrece pero solo si se le deja terminar solo.

  El resultado en disco es el MISMO layout de cache de Hugging Face
  (`models--<org>--<nombre>/refs/main` + `snapshots/<commit>/<archivo>`) que arma
  `huggingface_hub`, verificado cargando el modelo asi bajado con
  `WhisperModel(..., local_files_only=True)` -- que es exactamente el camino que usa
  `transcribe.load_model()`. No hace falta el directorio `blobs/` con symlinks: sin
  cache de arbol (`trees/<commit>.json`), `snapshot_download(local_files_only=True)`
  no verifica integridad archivo a archivo, solo que `refs/main` resuelva a una
  carpeta en `snapshots/` que contenga lo necesario -- comprobado leyendo su propio
  codigo (`huggingface_hub._snapshot_download`) y confirmado en ejecucion real.
"""
from __future__ import annotations

import errno
import fnmatch
import logging
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from huggingface_hub import HfApi, hf_hub_url

from catalog import CATALOG, ModelSpec  # noqa: F401 -- re-exportado, API publica sin cambios
from errors import CoreError, ErrorCode, one_line

logger = logging.getLogger(__name__)

# Mismo filtro que `faster_whisper.utils.download_model()` (leido de su codigo
# fuente, faster-whisper 1.2.1): son los UNICOS archivos que faster-whisper necesita
# para cargar un modelo. El glob de `vocabulary.*` cubre tanto `vocabulary.txt`
# (Systran) como `vocabulary.json` (otros repos, p.ej. distil-whisper).
_ALLOW_PATTERNS = ("config.json", "preprocessor_config.json", "model.bin", "tokenizer.json", "vocabulary.*")

_CHUNK_BYTES = 256 * 1024
_DISK_HEADROOM_FACTOR = 1.2  # ARCHITECTURE.md Sec.5 / Sec.11: necesario * 1.2 libre
_USER_AGENT = "Voice2Text/1 (BSTools; +https://www.byraesoftware.com)"


# `ModelSpec` y `CATALOG` viven en `catalog.py` desde el lote 8 -- este modulo
# conserva solo el COMPORTAMIENTO (descargar, borrar, medir en disco), reexportados
# arriba para no romper la API publica de quien ya hacia `models.ModelSpec` /
# `models.CATALOG` (ARCHITECTURE.md Sec.3).


def _repo_cache_dir(models_dir: Path, repo_id: str) -> Path:
    """Nombre de carpeta que usa `huggingface_hub` para el cache de un repo:
    "models--<org>--<nombre>". Convencion publica y estable (la usa tambien
    `huggingface-cli scan-cache`), no un detalle interno fragil.
    """
    return Path(models_dir) / ("models--" + repo_id.replace("/", "--"))


def _dir_size(path: Path) -> int:
    """Bytes reales en disco bajo `path`. Ignora symlinks (su tamano ya cuenta en
    el archivo real al que apuntan) para no contar dos veces si algun dia se anade
    un layout con `blobs/` + symlinks; si el sistema no soporta symlinks y
    `huggingface_hub` copia en vez de enlazar, esos archivos SI son reales y cuentan
    -- en ese caso el numero es honesto porque el disco de verdad se usa dos veces.
    """
    if not path.exists():
        return 0
    total = 0
    for entry in path.rglob("*"):
        try:
            if entry.is_file() and not entry.is_symlink():
                total += entry.stat().st_size
        except OSError:
            continue
    return total


def _installed_commit(cache_dir: Path) -> Optional[str]:
    """Commit publicado (`refs/main`), o None si no hay ninguna descarga completa.

    Se escribe SOLO al final de `ensure_model()`, cuando todos los archivos ya
    estan enteros (ver docstring del modulo): mientras exista una descarga a medias
    -- cortada por cancelacion, por un corte de red o porque el proceso murio --
    `refs/main` no existe todavia y por tanto no se confunde con "instalado".
    """
    ref_main = cache_dir / "refs" / "main"
    if not ref_main.is_file():
        return None
    try:
        commit_hash = ref_main.read_text(encoding="ascii").strip()
    except OSError:
        return None
    if not commit_hash:
        return None
    snapshot_dir = cache_dir / "snapshots" / commit_hash
    if not (snapshot_dir / "model.bin").is_file():
        return None
    return commit_hash


def installed(models_dir: Path) -> dict[str, int]:
    """model_id -> bytes en disco, solo para los modelos del catalogo YA completos."""
    models_dir = Path(models_dir)
    result: dict[str, int] = {}
    for model_id, spec in CATALOG.items():
        cache_dir = _repo_cache_dir(models_dir, spec.repo_id)
        if _installed_commit(cache_dir) is not None:
            result[model_id] = _dir_size(cache_dir)
    return result


def total_size(models_dir: Path) -> int:
    """Peso total de `models/`, instalado o no por el catalogo (D15: siempre visible)."""
    return _dir_size(Path(models_dir))


def delete_model(model_id: str, models_dir: Path) -> int:
    """Borra el modelo entero (completo o a medias) y devuelve los bytes liberados.

    No traduce errores de E/S a `CoreError`: no hay codigo en la tabla cerrada de
    ARCHITECTURE.md Sec.5 para "no se pudo borrar" (ficheros en uso, permisos...).
    Se deja propagar `OSError` tal cual -- quien llame decide.
    """
    spec = CATALOG.get(model_id)
    if spec is None:
        raise ValueError(f"unknown model_id: {model_id!r}")

    cache_dir = _repo_cache_dir(Path(models_dir), spec.repo_id)
    if not cache_dir.exists():
        return 0
    freed = _dir_size(cache_dir)
    shutil.rmtree(cache_dir)
    return freed


def _resolve_download_plan(spec: ModelSpec) -> tuple[str, list[tuple[str, int]]]:
    """Pregunta al Hub que archivos hay que bajar y su tamano REAL, medido en el
    momento (ADR-0002 E3: los dos numeros -- cuanto se descarga y cuanto ocupara --
    antes de tocar la red de verdad). Si el Hub no responde, `MODEL_DOWNLOAD_FAILED`;
    quien llama decide si reintenta.
    """
    try:
        info = HfApi().model_info(spec.repo_id, files_metadata=True)
    except Exception as exc:  # huggingface_hub no expone una jerarquia propia estable
        raise CoreError(
            ErrorCode.MODEL_DOWNLOAD_FAILED,
            details={"model_id": spec.model_id, "downloaded_bytes": 0},
            technical=one_line(str(exc)),
        ) from exc

    commit_hash = info.sha
    files: list[tuple[str, int]] = []
    for sibling in info.siblings:
        if any(fnmatch.fnmatch(sibling.rfilename, pattern) for pattern in _ALLOW_PATTERNS):
            files.append((sibling.rfilename, sibling.size or 0))

    if commit_hash is None or not any(name == "model.bin" for name, _ in files):
        raise CoreError(
            ErrorCode.MODEL_DOWNLOAD_FAILED,
            details={"model_id": spec.model_id, "downloaded_bytes": 0},
            technical="repo metadata missing commit hash or model.bin",
        )
    return commit_hash, files


def _download_file(
    url: str,
    dest: Path,
    expected_size: int,
    *,
    on_chunk: Callable[[int], None],
    should_cancel: Callable[[], bool],
) -> None:
    """Baja UN archivo a `dest`, reanudando por `Range` si ya hay un `.part` a
    medias (ARCHITECTURE.md Sec.8 punto 5) y comprobando `should_cancel()` en CADA
    trozo de 256 KiB -- verificado en ejecucion real: es lo que da cancelacion
    sub-segundo en vez de dejar la descarga corriendo en segundo plano.
    """
    part = dest.with_name(dest.name + ".part")
    resume_from = part.stat().st_size if part.exists() else 0
    if resume_from and expected_size and resume_from > expected_size:
        # El repo cambio de tamano entre intentos: lo parcial ya no vale.
        part.unlink(missing_ok=True)
        resume_from = 0

    headers = {"User-Agent": _USER_AGENT}
    write_mode = "wb"
    if resume_from:
        headers["Range"] = f"bytes={resume_from}-"
        write_mode = "ab"

    request = urllib.request.Request(url, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=30)
    except urllib.error.URLError as exc:
        raise CoreError(
            ErrorCode.MODEL_DOWNLOAD_FAILED,
            details={"downloaded_bytes": resume_from},
            technical=one_line(str(exc)),
        ) from exc

    with response:
        if resume_from and getattr(response, "status", 200) != 206:
            # El servidor no soporto Range (o devolvio el archivo entero de nuevo):
            # se reanuda desde cero para no acabar con un archivo corrupto.
            resume_from = 0
            write_mode = "wb"
        else:
            on_chunk(resume_from)  # los bytes ya en disco tambien cuentan como progreso

        try:
            with open(part, write_mode) as handle:
                while True:
                    if should_cancel():
                        raise CoreError(
                            ErrorCode.CANCELLED,
                            details={"downloaded_bytes": resume_from},
                            technical="",
                        )
                    chunk = response.read(_CHUNK_BYTES)
                    if not chunk:
                        break
                    handle.write(chunk)
                    resume_from += len(chunk)
                    on_chunk(len(chunk))
        except OSError as exc:
            if exc.errno == errno.ENOSPC:
                free = shutil.disk_usage(dest.parent).free
                raise CoreError(
                    ErrorCode.DISK_FULL,
                    details={"required_bytes": expected_size - resume_from, "available_bytes": free, "path": str(dest)},
                    technical=one_line(str(exc)),
                ) from exc
            raise CoreError(
                ErrorCode.MODEL_DOWNLOAD_FAILED,
                details={"downloaded_bytes": resume_from},
                technical=one_line(str(exc)),
            ) from exc

    part.replace(dest)


def ensure_model(
    model_id: str,
    models_dir: Path,
    *,
    on_progress: Callable[[int, Optional[int]], None],
    should_cancel: Callable[[], bool],
) -> Path:
    """Confirma que `model_id` esta descargado por completo; si no, lo descarga.

    `on_progress(downloaded_bytes, total_bytes)` se llama primero con el PLAN
    (antes de tocar la red de datos: consentimiento informado, ADR-0002 E3) y
    despues en cada trozo recibido. `total_bytes` nunca es `None`: si el Hub no
    da tamanos por archivo se cae a `ModelSpec.expected_bytes`, pero SIEMPRE hay
    un numero que anunciar antes de empezar.

    Devuelve la carpeta de la instantanea (equivalente al valor de retorno de
    `huggingface_hub.snapshot_download()`).
    """
    spec = CATALOG.get(model_id)
    if spec is None:
        raise ValueError(f"unknown model_id: {model_id!r}")

    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = _repo_cache_dir(models_dir, spec.repo_id)

    already_commit = _installed_commit(cache_dir)
    if already_commit is not None:
        snapshot_dir = cache_dir / "snapshots" / already_commit
        size = _dir_size(cache_dir)
        on_progress(size, size)
        return snapshot_dir

    if should_cancel():
        raise CoreError(ErrorCode.CANCELLED, details={}, technical="")

    commit_hash, files = _resolve_download_plan(spec)

    if should_cancel():
        raise CoreError(ErrorCode.CANCELLED, details={}, technical="")

    snapshot_dir = cache_dir / "snapshots" / commit_hash
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    total_bytes = sum(size for _, size in files) or spec.expected_bytes

    already_bytes = 0
    pending: list[tuple[str, int]] = []
    for name, size in files:
        dest = snapshot_dir / name
        if dest.is_file() and (size == 0 or dest.stat().st_size == size):
            already_bytes += dest.stat().st_size
        else:
            pending.append((name, size))

    # Comprobacion previa de espacio (ARCHITECTURE.md Sec.5 / Sec.11): se exige
    # 1.2x de lo que falta por bajar, ANTES de escribir el primer byte.
    remaining = max(0, total_bytes - already_bytes)
    if remaining:
        free = shutil.disk_usage(models_dir).free
        required_with_margin = int(remaining * _DISK_HEADROOM_FACTOR)
        if free < required_with_margin:
            raise CoreError(
                ErrorCode.DISK_FULL,
                details={"required_bytes": required_with_margin, "available_bytes": free, "path": str(models_dir)},
                technical="",
            )

    downloaded = already_bytes
    on_progress(downloaded, total_bytes)  # el PLAN, antes de bajar nada

    def _on_chunk(count: int) -> None:
        nonlocal downloaded
        downloaded += count
        on_progress(min(downloaded, total_bytes), total_bytes)

    for name, size in pending:
        _download_file(
            hf_hub_url(spec.repo_id, name, revision=commit_hash),
            snapshot_dir / name,
            size,
            on_chunk=_on_chunk,
            should_cancel=should_cancel,
        )

    # `refs/main` se escribe AL FINAL, con todos los archivos ya completos: un
    # corte a mitad de camino nunca deja algo que `_installed_commit()` confunda
    # con una instalacion valida (ver docstring del modulo).
    refs_dir = cache_dir / "refs"
    refs_dir.mkdir(parents=True, exist_ok=True)
    (refs_dir / "main").write_text(commit_hash, encoding="ascii")

    on_progress(total_bytes, total_bytes)
    return snapshot_dir
