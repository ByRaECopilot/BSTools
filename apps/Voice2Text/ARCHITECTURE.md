# Voice2Text — Arquitectura

> **Estado: especificación cerrada, sin implementar.** Decisiones y su porqué en
> [`ADR-0001`](../../spec/decisions/ADR-0001-voice2text-stack.md) (`listo-para-construir`). Este documento
> es el **contrato** que debe respetar la implementación; si ADR y código se contradicen, gana el ADR y se
> para a escalar.
>
> El spike del lote 0 ya se ejecutó (`SPIKE-RESULTS.md`, 2026-08-10) y sus hallazgos están incorporados.
>
> ⚠️ **Premisa corregida el 2026-08-10:** el límite de 1 GB es el presupuesto del **modelo** (con margen
> hacia arriba), no de la instalación, y **la prioridad declarada es la calidad del texto**; la memoria no
> tiene límite. Por eso hay bloques marcados 🚫 en §3, §8 y §9: **el modelo por defecto y la política de
> GPU los decide ADR-0002**.
>
> ⚠️ **Y hay DOS perfiles de hardware, no uno** (ADR-0001 §17): se desarrolla en una **GTX 1050 Ti (4 GB,
> cómputo 6.1, sin `float16`)** y el destino es una **RTX 3080 (10 GB, cómputo 8.6, con `float16`)**. Las
> cifras medidas llevan perfil: **[M-dev]** es el **peor caso**, no el rendimiento esperado. El contrato
> de resolución de dispositivo de §3 —**obligatorio en el lote 1 y ya incorporado**— existe precisamente
> para que el mismo código sirva a los dos, y §14 explica cómo se prueba la máquina que todavía no se
> tiene.
>
> **Marcas de origen de cada cifra**, obligatorias en todo este documento:
> **[M]** medido el 2026-08-10 en la máquina del dueño (Windows 10 Pro, Python 3.11.9) ·
> **[E]** estimado, sin medir ·
> **[O]** observación fechada sobre un tercero (YouTube, TikTok): **no es una propiedad del diseño** y
> puede cambiar sin aviso.

---

## 1. Qué hace, en una frase

Entra un archivo de audio/vídeo local **o** un enlace público; sale su texto en `.txt` y `.md`, transcrito
**en la máquina del usuario**. Dos modos de arranque, excluyentes entre sí: **ventana** (uso normal) y
**servidor** (para que otra aplicación del mismo equipo consuma el motor).

---

## 2. Las tres capas y la estructura de la carpeta

**La regla de arquitectura que se vigila en revisión, y se audita leyendo los `import`:**

```
CASCARA        app.py (ventana)          serve.py (--serve)
                      \                    /
                       \                  /          <- unica capa que sabe de
                        \                /              ventanas, HTTP y castellano
ORQUESTACION            jobs.py  (cola FIFO, estado, cancelacion, cerrojo, modelo en RAM)
                       /    |     \
MOTOR      transcribe.py  fetch.py  export.py  models.py   (+ errors.py)
                                                        <- puro: sin estado global,
                                                           sin config, sin print, sin idioma
```

Ninguna capa importa de una superior. **El motor no importa `webview`, `http.server`, `webbrowser` ni
`settings`**, no llama a `print()` (usa `logging`) y no llama a `sys.exit()`.

```
apps/Voice2Text/
├── install.ps1                 registra menu contextual + dependencias + accesos directos
├── uninstall.ps1               revierte TODO lo que escribe install.ps1
├── Voice2Text.cmd              lanzador del modo ventana
├── Voice2Text-Servidor.cmd     lanzador del modo servidor (consola en primer plano)
│
├── app.py                      CASCARA ventana (pywebview)
├── serve.py                    CASCARA servidor (http.server, /api/v1)
├── messages.py                 CASCARA: codigo de error -> texto en castellano. UNICO sitio con copy
├── settings.py                 CASCARA: valores por defecto + settings.json opcional
│
├── jobs.py                     ORQUESTACION: cola FIFO, estado, cancelacion, cerrojo, modelo en RAM
│
├── transcribe.py               MOTOR: faster-whisper + PyAV
├── models.py                   MOTOR: catalogo, descarga, tamano en disco, borrado
├── fetch.py                    MOTOR: yt-dlp, aislado y opcional
├── export.py                   MOTOR: .txt y .md
├── errors.py                   MOTOR: codigos de error + excepcion CoreError
│
├── ui.html                     la interfaz (HTML+CSS+JS, en castellano, autocontenida)
├── requirements.txt
├── icon.ico
├── .gitignore
├── README.md
├── ARCHITECTURE.md             este archivo
├── SPIKE-RESULTS.md            informe del lote 0 (historico, fechado)
│
├── models/                     (IGNORADO) modelos descargados — 464 MB el `small` [M]
├── webview/                    (IGNORADO) perfil propio de WebView2 — OBLIGATORIO, ver 6.1
├── work/                       (IGNORADO) descargas y temporales, se purga sola
└── salida/                     (IGNORADO salvo su .gitignore) destino por defecto de los enlaces
```

`messages.py` existe por una razón concreta: **es el único archivo con texto para humanos**. El día que
alguien quiera el bot en inglés, toca ese archivo y nada más.

---

## 3. Contrato del motor (firmas)

Nombres de datos en inglés `snake_case`; texto de usuario, solo en la cáscara (ADR-0001 D10, D12).

### `errors.py`

```python
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

class CoreError(Exception):
    code: ErrorCode
    details: dict          # SOLO datos: numeros, rutas, limites. NUNCA texto de pantalla
    technical: str         # UNA linea del error original. Nunca un traceback
```

**Ninguna cadena en castellano vive aquí.** `details` lleva lo que la cáscara necesita para redactar:
`{"required_bytes": 507510784, "available_bytes": 312000000, "path": "D:\\..."}`.

### `transcribe.py`

```python
@dataclass(frozen=True)
class Segment:
    index: int          # 0,1,2... correlativo
    start: float        # segundos desde el inicio del medio
    end: float          # fin del CONTENEDOR del segmento. OJO: faster-whisper lo ESTIRA
                        # hasta el inicio del siguiente, absorbiendo el silencio (medido)
    speech_end: float | None   # fin real del habla = end de la ULTIMA PALABRA.
                        # None si word_timestamps=False. Es el unico campo que ve los silencios
    text: str           # ya recortado

@dataclass(frozen=True)
class TranscriptionResult:
    segments: list[Segment]
    language: str                 # "es" | "en" | ...
    language_probability: float   # 0..1
    media_duration_seconds: float
    elapsed_seconds: float
    speed_ratio: float            # media_duration / elapsed. Medido: 2.8 con small/int8/CPU [M]
    device_used: "DeviceChoice"   # con QUE se transcribio. Va al estado y a la cabecera del .md
```

#### Resolución de dispositivo — enmienda del 2026-08-10, **obligatoria en el lote 1**

La política de "GPU si la hay, CPU si no" **vive en el motor, no en las cáscaras**. Si `app.py` y
`serve.py` tuvieran que decidir el dispositivo, esa política estaría duplicada en dos sitios y el futuro
bot la duplicaría por tercera vez. La cáscara pasa como mucho una **preferencia**; nunca un dispositivo.

```python
@dataclass(frozen=True)
class DeviceCapabilities:            # lo que HAY en la maquina. Barato, sin cargar modelo
    cuda_status: str                 # "unavailable" | "probable" | "confirmed"  (ADR-0002 E9)
                                     # NUNCA un bool: "se construyo el modelo" NO prueba que
                                     # la GPU funcione (medido). Ver la prueba de humo, abajo.
    cuda_device_count: int
    gpu_name: str | None                          # "NVIDIA GeForce GTX 1050 Ti"
    compute_capability: tuple[int, int] | None    # (6, 1) en Pascal
    vram_total_mb: int | None
    vram_free_mb: int | None
    supported_compute_types: list[str]            # p.ej. ["int8", "float32"] en cc 6.1
    unavailable_reason: str | None                # CODIGO estable, nunca texto:
                                                  # "no_nvidia_gpu" | "cuda_libs_missing"
                                                  # | "cuda_libs_not_on_path" | "cuda_libs_mismatch"
                                                  # | "compute_capability_too_low" | "insufficient_vram"
                                                  # | "smoke_test_failed"

@dataclass(frozen=True)
class DeviceChoice:
    device: str                  # "cuda" | "cpu"
    device_index: int
    compute_type: str            # "float16" | "int8_float16" | "int8" | "float32"
    cpu_threads: int             # 0 = decide CTranslate2. Ignorado si device="cuda"
    fell_back_from: str | None   # "cuda" si se pidio GPU y se acabo en CPU
    fallback_reason: str | None  # mismo vocabulario que unavailable_reason

def add_cuda_dlls_to_path() -> list[Path]: ...
    # OBLIGATORIO ANTES de importar ctranslate2 (ADR-0002 E7). pip deja las DLL en
    # site-packages/nvidia/*/bin y NO las publica en el PATH: sin este paso el sintoma
    # es IDENTICO a no tenerlas instaladas, con pip diciendo que todo fue bien.
    # Consecuencia: faster_whisper y ctranslate2 se importan DE FORMA PEREZOSA,
    # dentro de las funciones. Mismo patron que el import perezoso de yt_dlp (D7).

def probe_devices() -> DeviceCapabilities: ...
    # Comprobaciones BARATAS. Devuelve como mucho "probable", NUNCA "confirmed".
    #   1. ctranslate2.get_cuda_device_count() > 0
    #   2. que los ficheros DLL EXISTAN en site-packages/nvidia/*/bin  <- tapa el caso
    #      "instalado pero no en el PATH", que da el mismo error que "no instalado"
    #   3. ctranslate2.get_supported_compute_types('cuda', 0)   <- se PREGUNTA a la
    #      libreria; jamas una tabla de compute capability escrita por nosotros
    # ImportError / OSError -> cuda_status="unavailable" con su codigo.

def smoke_test_cuda(model: object) -> tuple[bool, str | None]: ...
    # LA UNICA comprobacion fiable (ADR-0002 E8). Inferencia sobre medio segundo de
    # audio sintetico generado en memoria, envuelta en try/except RuntimeError.
    # Se clasifica por subcadena del mensaje:
    #   "not found or cannot be loaded" -> gpu_libraries_missing
    #   "out of memory"                 -> gpu_out_of_memory
    #   resto                           -> gpu_unavailable

def resolve_device(model_id: str, caps: DeviceCapabilities,
                   preference: str = "auto",
                   compute_type_override: str | None = None) -> DeviceChoice: ...
    # FUNCION PURA: no toca hardware, solo decide a partir de `caps`. Es lo que permite
    # probar la politica de una RTX 3080 desde una GTX 1050 Ti (ver 14).
    # preference: "auto" | "cuda" | "cpu"  <- lo UNICO que puede llegar de la cascara.
```

**Política de `resolve_device()`, escrita una sola vez y en el motor** (ADR-0001 §17.2):

1. `preference="cpu"` → CPU. `preference="cuda"` sin CUDA → CPU con `fell_back_from="cuda"` y su motivo.
2. Con CUDA disponible, se elige el **primer `compute_type` soportado** de esta lista, **consultando el
   conjunto que devuelve CTranslate2**, no una tabla nuestra: `float16` → `int8_float16` → `int8` →
   `float32`. En CPU: `int8` → `float32`.
3. Se exige que **tras cargar queden al menos 512 MiB libres**:
   `vram_free_mb - vram_peak_mb(model, compute_type) >= 512`. Si no, se prueba el siguiente
   `compute_type`; si ninguno cabe, **CPU** con motivo `insufficient_vram`.
4. **La VRAM se vuelve a comprobar al cargar el modelo, no solo al sondear**: entre el sondeo y la carga el
   usuario puede haber abierto un juego. Y `vram_free_mb` **se lee en el momento**, nunca se calcula
   restando de la capacidad nominal: el escritorio de Windows ya ocupa ~460 MiB [M-dev].

> **Por qué la holgura es absoluta y no un porcentaje (ADR-0002 §7).** Medido: `medium`/`float32` subió a
> **3881-3927 MiB de 4096** y, pasados 13 minutos, **ni terminó ni lanzó excepción** — degradación
> silenciosa, probablemente *spillover* a memoria compartida por PCIe [O]. **Quedarse justo por debajo del
> límite es PEOR que pasarse**: pasarse da un `CUDA out of memory` capturable; quedarse al borde no da nada
> que capturar ni nada que enseñar. Un porcentaje falla en los dos extremos (15 % de 4 GiB son 600 MiB,
> justos; 15 % de 10 GiB son 1,5 GiB, desperdicio); un mínimo absoluto encaja en las dos tarjetas.

**Por qué el orden de la regla 2 es ese y no "el más rápido primero":** la prioridad declarada por el dueño
es la **calidad del texto**, así que **no se cuantiza más de lo que el hardware obligue**. En una Ampere
eso significa `float16` aunque `int8` fuera más rápido; en una Pascal, `int8` es el único camino y la
pérdida se acepta porque es la máquina de desarrollo.

#### Recomendar un modelo NO es resolver un dispositivo — separación deliberada

```python
@dataclass(frozen=True)
class ModelRecommendation:
    model_id: str
    compute_type: str
    reason: str              # codigo estable: "best_quality_fits_vram" | "budget_limited" | "cpu_only"
    estimated_speed_ratio: float | None   # None si no hay medicion para ese perfil

def recommend_profile(caps: DeviceCapabilities,
                      catalog: dict[str, ModelSpec]) -> list[ModelRecommendation]: ...
    # Lista ORDENADA de candidatos. SUGIERE, nunca actua.
    # 1) FILTRO DE VIABILIDAD: speed_ratio estimado >= min_viable_speed_ratio (1.0), y
    #    en GPU, holgura de 512 MiB tras el pico. Si NINGUNO pasa -> se devuelve el mas
    #    rapido, nunca una lista vacia.
    # 2) ORDEN por calidad; a igualdad, por velocidad; a igualdad de ambas, por peso.
    # Ya NO recibe model_budget_bytes: el techo murio (ADR-0002 E3).
```

> **Aquí me aparto del encargo, a propósito.** Se pidió que `resolve_device()` resolviera *también el
> modelo*. **No debe.** Son dos decisiones con ciclos de vida distintos y juntarlas crea un fallo feo:
>
> - El **modelo** es una **decisión de descarga**, de cientos de MB a 3 GB, que toma **el usuario una vez
>   y con consentimiento explícito** (ADR-0001 D4 y §8). Si un trabajo pudiera "resolver" que prefiere
>   `large-v3`, **encolar una transcripción dispararía una descarga de 3 GB por sorpresa.**
> - El **dispositivo y el `compute_type`** son una **decisión de ejecución**, por trabajo, automática e
>   invisible, sin consecuencias en disco.
>
> Por eso: `recommend_profile()` alimenta la pantalla de primer arranque y la de cambiar modelo —
> **sugiere**; `resolve_device()` corre en cada trabajo sobre un modelo **ya elegido y ya descargado** —
> **actúa**. La política sigue viviendo entera en el motor, que es lo que el encargo perseguía.

**`settings.json` es un *override*, no la fuente de la decisión.** `device_preference` y
`compute_type_override` existen para depurar y para el usuario que quiera forzar; **si están a `null`
—que es el valor por defecto— manda `resolve_device()`**. Un `compute_type` fijo en el fichero sería
incorrecto en al menos una de las dos máquinas del dueño (ADR-0001 §17.1).

def load_model(model_id: str, models_dir: Path, choice: DeviceChoice,
               allow_download: bool = False) -> object: ...
    # Devuelve un MANEJADOR. No lo cachea en ninguna variable global:
    # quien lo guarda y quien lo suelta es jobs.py (ADR-0001 D22).
    # allow_download=False -> si falta, CoreError(MODEL_MISSING).

def transcribe(media_path: Path, model: object, *,
               language: str | None = None,      # None = deteccion automatica
               vad_filter: bool = True,
               word_timestamps: bool = True,     # rellena Segment.speech_end. Ver 7
               on_segment: Callable[[Segment, float], None],   # (segmento, progreso 0..1)
               should_cancel: Callable[[], bool]) -> TranscriptionResult: ...
```

**Detalles que no son opcionales:**

- `faster_whisper` devuelve un **generador** de segmentos: el trabajo ocurre al iterarlo. El progreso sale
  de ahí sin instrumentar nada: `progress = segment.end / media_duration_seconds`.
- La duración del medio y el idioma se conocen **antes** de transcribir: hay barra desde el primer segundo.
- **Cancelación cooperativa:** se consulta `should_cancel()` en cada vuelta. Latencia = la ventana en curso
  (hasta ~30 s [E]); la cáscara muestra "Cancelando…" en vez de fingir que ya paró.
- `vad_filter=True` por defecto: recorta silencios y **reduce la alucinación de texto repetido**. Las
  marcas de tiempo siguen refiriéndose al medio original.
- `on_segment` y `should_cancel` son **internos del proceso**: no forman parte del contrato público. Un
  consumidor externo ve progreso sondeando estado (§4).
- **El cómputo libera el GIL** [M: 19,84 de 20 tics/s durante la transcripción], así que basta con un hilo
  trabajador: no hace falta subproceso.

**Qué se implementa AHORA en el lote 1 y qué no** *(afinado con el dato de las dos máquinas)*:

- **`resolve_device()` se implementa ENTERA, incluida la rama CUDA.** Es una función **pura**: no toca
  hardware, así que su política se puede escribir y **probar hoy con capacidades sintéticas de una RTX
  3080** (§14). No hay ninguna razón para dejarla a medias, y dejarla a medias sería justo el código que
  nadie ejercita hasta el día de la migración.
- **`probe_devices()` se deja con la detección de CUDA en modo apagado**: devuelve `cuda_available=False`
  con motivo `cuda_libs_missing`. Es la única parte que necesita hardware y librerías que aún no se ha
  decidido publicar.
- **`recommend_profile()` se escribe** con la matriz de ADR-0001 §17.2 parametrizada; qué modelo gana en
  cada perfil lo fija ADR-0002 rellenando el catálogo, no cambiando el código.

Coste: unas decenas de líneas, y evita reabrir una firma pública (ADR-0001 D17) que `jobs.py` llamará en el
lote 2.

**La caída a CPU nunca es silenciosa.** `fell_back_from` y `fallback_reason` viajan al estado del trabajo
y `messages.py` los convierte en un aviso ("no se pudo usar la GPU: falta el paquete de aceleración; se ha
transcrito con la CPU"). Un usuario que instala el paquete de GPU y sigue viendo velocidades de CPU sin
que nadie se lo explique es el fallo clásico de este diseño, y es un aviso, no un error.

### `fetch.py` — aislado y opcional (ADR-0001 D7)

```python
@dataclass(frozen=True)
class MediaInfo:            # de probe(), SIN descargar
    title: str
    duration_seconds: float | None
    extractor: str          # "youtube", "tiktok"...
    estimated_bytes: int | None

@dataclass(frozen=True)
class FetchedMedia:
    path: Path              # work/<job_id>.<ext>
    title: str
    duration_seconds: float | None
    bytes_downloaded: int
    container: str          # "mp4", "webm", "m4a"...
    has_video: bool         # True = cayo un stream MUXEADO. NO es un error (ver abajo)

def is_available() -> bool: ...              # yt_dlp importable? (import perezoso)
def ytdlp_version() -> tuple[str, int]: ...  # ("2026.7.4", 37) -> version y dias de antiguedad
def probe(url: str, player_clients: list[str]) -> MediaInfo: ...
def fetch_audio(url: str, dest_dir: Path, job_id: str, *,
                player_clients: list[str],       # inyectado por la cascara (ADR-0001 D26)
                max_bytes: int,
                on_progress: Callable[[int, int | None], None],   # (bytes hechos, total o None)
                should_cancel: Callable[[], bool]) -> FetchedMedia: ...
```

#### El hallazgo del spike que el código DEBE respetar

**Medido el 2026-08-10 [M/O]:** en YouTube, sin cookies, la extracción por defecto falló con *"Sign in to
confirm you're not a bot"*. De **doce `player_client`** probados sobre **tres vídeos públicos**, solo
`android` autenticó, y expuso **un único formato**: `itag 18`, `.mp4`, AAC + H.264, **360p ya muxeado**.
El selector cayó en `best` y descargó 629 172 bytes para 19 s de vídeo. PyAV lo abrió y faster-whisper lo
transcribió perfectamente, con `ffmpeg` confirmado ausente.

**Reglas que salen de ahí, y son obligatorias:**

1. **`has_video=True` es flujo normal, no un error.** Jamás se emite `DOWNLOAD_FAILED` ni
   `NO_AUDIO_STREAM` porque haya caído un muxeado. La cáscara lo comenta como dato
   (*"se descargaron X MB porque esa plataforma no ofrece hoy una pista de audio suelta"*), nunca como
   fallo.
2. **`NO_AUDIO_STREAM` se reserva** a que el medio **de verdad** no tenga pista de audio, comprobado con
   PyAV sobre el archivo ya descargado.
3. **`player_clients` se inyecta**, nunca se escribe en el `.py` (ADR-0001 D26). Se prueban en orden hasta
   que uno devuelva formatos. Es el parámetro que más rápido caduca [O].
4. **`abr<=128` es un filtro oportunista, no un ahorro garantizado.** Solo actúa si existe audio suelto.
   Cuando cae un muxeado se descargan también los bytes del vídeo: ~2-5× más [E, derivado del punto
   medido]. El tope `max_input_bytes` sigue siendo la salvaguarda.

**Opciones de yt-dlp — cerradas** (ADR-0001 D3):

```python
{
  'extractor_args': {'youtube': {'player_client': player_clients}},   # de settings, no del codigo
  'format': 'bestaudio[abr<=128]/bestaudio/best',   # el /best de reserva es LO QUE SALVA el caso muxeado
  'postprocessors': [],            # PROHIBIDO. Cualquier postproceso exige el binario ffmpeg
  'noplaylist': True,              # un enlace de playlist NO puede lanzar 200 descargas
  'hls_prefer_native': True,       # descargador HLS propio, sin ffmpeg
  'outtmpl': str(dest_dir / f'{job_id}.%(ext)s'),
  'max_filesize': max_bytes,
  'retries': 3, 'socket_timeout': 30,
  'quiet': True, 'no_warnings': False,
  'progress_hooks': [...],
  # Explicitos por politica, no por descuido (ADR-0001 D6):
  'cookiesfrombrowser': None, 'cookiefile': None, 'username': None, 'password': None,
}
```

Validación previa: solo `http`/`https`; `file:`, `ftp:`, `data:` → `UNSUPPORTED_URL` sin llegar a yt-dlp.
Tras la descarga, comprobar que hay **exactamente un archivo** y abrirlo con PyAV para determinar
`container` y `has_video`.

### `export.py`

```python
@dataclass(frozen=True)
class WrittenFile:
    format: str      # "txt" | "md"
    path: Path
    bytes: int

def to_plain_text(segments: list[Segment]) -> str: ...
def to_markdown(segments: list[Segment], meta: dict) -> str: ...
def write_outputs(segments, meta, output_dir: Path, base_name: str,
                  formats: list[str], overwrite: bool = False) -> list[WrittenFile]: ...
```

### `models.py`

```python
@dataclass(frozen=True)
class ModelSpec:
    model_id: str            # "small"
    repo_id: str             # "Systran/faster-whisper-small"
    expected_bytes: int      # small: 486_539_264 aprox (464 MB medidos [M])
    params_millions: int
    quality_rank: int                  # 1 = mejor. ORDINAL y [E]: nunca se ha medido
                                       # calidad en espanol. Deuda declarada (ADR-0002 V6)
    vram_peak_mb: dict[str, int]       # por compute_type, MEDIDO: {"int8": 1575, ...}
    speed_ratio: dict[str, float]      # por (dispositivo, compute_type), MEDIDO donde exista

CATALOG: dict[str, ModelSpec]   # sin `tiny`, sin modelos `.en`, sin variantes distil (solo ingles)
                                # Repos y cifras medidas: ADR-0002 seccion 3.
                                # OJO: large-v3-turbo NO tiene repo de Systran; el de
                                # referencia es mobiuslabsgmbh/faster-whisper-large-v3-turbo,
                                # tambien fp16 (nunca un pre-cuantizado int8).

def installed(models_dir: Path) -> dict[str, int]: ...      # model_id -> bytes en disco
def ensure_model(model_id, models_dir, *, on_progress, should_cancel) -> Path: ...
def delete_model(model_id: str, models_dir: Path) -> int: ...   # bytes liberados
def total_size(models_dir: Path) -> int: ...
```

`ModelSpec` **no lleva etiquetas** como "recomendado" o "más ligero", ni una bandera `recommended`: **cuál
es el recomendado depende del hardware** y lo calcula `recommend_profile()`. El adjetivo lo pone
`messages.py`.

> **Historia de este `dataclass`, para que nadie reintroduzca lo muerto.** Tuvo un campo `exceeds_ceiling`,
> luego `over_model_budget`, que medían contra un techo de 1 GB. **Ese techo era orientativo y ya no existe
> como restricción** (ADR-0002 E3): quedó sustituido por la obligación de transparencia. **Dejar un campo
> que ya nadie hace cumplir es peor que quitarlo: invita a volver a aplicarlo.** También cayó
> `recommended: bool`, por la misma razón de fondo: era una propiedad estática para algo que depende de la
> máquina.

---

## 4. Orquestación: cola, estado y progreso

1. Quien llama encola y **recibe `job_id` de inmediato**, con su `queue_position`.
2. Un **único hilo trabajador** consume la cola FIFO y actualiza el estado bajo un `Lock`.
3. Quien espera **consulta el estado cada segundo**. Es lo único que puede cruzar una frontera de proceso.
4. Cancelar levanta una bandera; el motor la mira y se para.

### 4.1 Cola FIFO (ADR-0001 D14)

- **Encolar siempre se acepta** hasta `max_queued_jobs` (8). Pasado ese punto, `QUEUE_FULL`.
- **Un trabajo en ejecución**, el resto esperando. **Sin prioridades**: ventana y servidor son excluyentes
  (§6.4), así que no hay dos clases de cliente que ordenar.
- **Cancelar algo en cola es instantáneo**; cancelar lo que está en ejecución tarda hasta ~30 s [E].
- El estado vive tras una interfaz `JobStore` con **una sola implementación: en memoria**. Los trabajos
  **no sobreviven al cierre del proceso**; lo que sobrevive es lo escrito en disco.

### 4.2 El objeto de estado

**Solo números y códigos. Ni una cadena pensada para enseñarse** (ADR-0001 D10).

```jsonc
{
  "job_id": "j_7f3a1c2e",
  "kind": "transcription",              // "transcription" | "model_download"
  "state": "running",                   // queued | running | done | error | cancelled
  "phase": "transcribing",              // ver 4.3
  "queue_position": 0,                  // 0 = en ejecucion; 1 = el siguiente...
  "estimated_wait_seconds": null,       // solo si queue_position > 0; null = no calculable
  "progress": 0.42,                     // 0..1 dentro de la fase; null = indeterminado

  // Los numeros con los que la cascara compone lo que quiera enseñar:
  "processed_media_seconds": 723.0,
  "media_duration_seconds": 1725.0,
  "downloaded_bytes": null,
  "total_bytes": null,
  "eta_seconds": 214,                   // null hasta que sea fiable (4.4)

  "created_at": "2026-08-10T18:52:12Z",
  "updated_at": "2026-08-10T18:54:31Z",
  "finished_at": null,

  "source": {
    "kind": "file",                     // "file" | "url"
    "display_name": "reunion-comite.mp4",
    "path": "D:\\Videos\\reunion-comite.mp4",
    "url": null,
    "has_video": null                   // tras fetch: true = cayo un muxeado. Dato, no error
  },
  "options": {
    "model_id": "small",
    "device_preference": "auto",        // "auto" | "cuda" | "cpu". La cascara NO elige dispositivo
    "language": null,                   // null = automatico
    "vad_filter": true,
    "output_dir": "D:\\Videos",
    "formats": ["txt", "md"]
  },
  "device_used": {                      // resuelto por el motor, no por quien llama
    "device": "cpu", "device_index": 0, "compute_type": "int8",
    "fell_back_from": null,             // "cuda" si se pidio GPU y no se pudo
    "fallback_reason": null             // codigo estable; messages.py lo traduce a un AVISO
  },
  "result": {                           // null hasta state=done
    "language": "es", "language_probability": 0.99,
    "segment_count": 412, "character_count": 18422,
    "elapsed_seconds": 289.4, "speed_ratio": 5.96,
    "outputs": [ { "format": "md", "path": "D:\\Videos\\reunion-comite.md", "bytes": 19233 } ]
  },
  "error": null                         // ver §5
}
```

**Texto parcial en vivo.** La consulta acepta `since=<n>` y devuelve solo lo nuevo:

```jsonc
{ "...": "...", "new_segments": [ { "index": 118, "start": 712.4, "end": 717.9, "text": "..." } ] }
```

Así se **ve aparecer el texto mientras se transcribe** y cada sondeo son cientos de bytes. Los segmentos se
guardan en memoria (una hora de audio ≈ 130 KB de texto [E]).

### 4.3 Fases

| `phase` | Qué pasa | `progress` | Solo si |
|---|---|---|---|
| `queued` | en cola | null | |
| `probing` | yt-dlp pregunta título/duración sin descargar | null | origen enlace |
| `fetching` | descarga del medio | `downloaded_bytes / total_bytes` | origen enlace |
| `downloading_model` | descarga del modelo | bytes en disco / `expected_bytes` | falta el modelo |
| `loading_model` | carga en memoria y cuantización int8 | null | no estaba cargado |
| `transcribing` | el grueso del trabajo | `processed_media_seconds / media_duration_seconds` | |
| `writing` | se escriben `.txt` y `.md` | null | |
| `finished` | terminado | 1.0 | |

**Una barra por fase, no una barra global**: una barra única obliga a inventar pesos y a saltar hacia atrás
cuando la estimación falla.

### 4.4 Estimación de tiempo restante

Solo para `transcribing`, y **solo tras 20 s** de transcripción real:

```
speed_ratio  = processed_media_seconds / elapsed_seconds
eta_seconds  = (media_duration_seconds - processed_media_seconds) / speed_ratio
```

Hasta entonces `eta_seconds = null` y la cáscara dice "calculando…". **Nunca se enseña una estimación
inventada.** `estimated_wait_seconds` se calcula igual, sumando lo que va por delante con el `speed_ratio`
del último trabajo completado; sin ninguno, es `null`.

> **Detalle que hay que respetar desde el lote 2:** el `speed_ratio` de referencia se cachea **por
> `(model_id, device)`**, no globalmente. Un trabajo que corrió en GPU y otro que va a correr en CPU no
> tienen nada que ver, y mezclarlos produce estimaciones que se equivocan por un factor, no por un margen.

### 4.5 El modelo en RAM (ADR-0001 D22)

`jobs.py` —no el motor— guarda el manejador:

- Se carga al primer trabajo y **se mantiene mientras haya cola**.
- Tras `model_idle_timeout_seconds` (300 s) sin trabajos, **se suelta** (~1 GB [E]).
- El siguiente trabajo paga la recarga: **~3-10 s [E]**, pendiente de medir (S13).
- Cambiar de `model_id` entre trabajos **también** suelta el anterior: nunca dos modelos vivos.

### 4.6 Máquina de estados

```
queued ──► running ──► done
   │         │  └────► error
   └─────────┴───────► cancelled          (done, error y cancelled son terminales)
```

Sin reintento automático. Reintentar es crear un trabajo nuevo.

---

## 5. Errores: códigos en el núcleo, texto en la cáscara

**El núcleo emite** (ADR-0001 D10):

```jsonc
"error": {
  "code": "disk_full",
  "details": { "required_bytes": 507510784, "available_bytes": 312000000, "path": "D:\\...\\models" },
  "technical": "OSError: [Errno 28] No space left on device"   // UNA linea, nunca un traceback
}
```

**La cáscara traduce** (`messages.py`, único sitio con copy):

| `code` | Se detecta cuando | `details` | Texto (cáscara) | Pista | ¿Reintentar? |
|---|---|---|---|---|---|
| `unsupported_url` | esquema no http/https, o yt-dlp sin extractor | `url` | "No sé descargar de ese sitio." | "Descarga el archivo y arrástralo aquí." | no |
| `login_required` | el mensaje de yt-dlp menciona sesión, privado, edad, cookies o **"confirm you're not a bot"** [M] | `url`, `extractor` | "Ese contenido exige iniciar sesión, y Voice2Text nunca inicia sesión." | "Descárgalo tú y arrástralo aquí." | no |
| `geo_blocked` | el mensaje menciona bloqueo geográfico | `url` | "Ese contenido no está disponible en tu país." | — | no |
| `media_unavailable` | borrado, privado, 404, DRM | `url` | "Ese contenido ya no existe, es privado o está protegido." | "Comprueba el enlace en el navegador." | no |
| `download_failed` | red, tiempo agotado, corte. **Nunca por haber caído un muxeado** | `url`, `bytes_downloaded` | "Falló la descarga." | "Revisa tu conexión y vuelve a intentarlo." | **sí** |
| `extractor_outdated` | **cubo por defecto de yt-dlp** | `url`, `ytdlp_version`, `ytdlp_age_days` | "Puede que yt-dlp se haya quedado atrás: las plataformas cambian a menudo." | "Actualízalo: `py -3 -m pip install --upgrade yt-dlp`" (botón de copiar) | tras actualizar |
| `no_audio_stream` | **PyAV confirma que el medio no tiene pista de audio.** No se usa para muxeados | `path` | "Ese medio no tiene audio." | — | no |
| `decode_failed` | PyAV no puede abrir o decodificar | `path`, `container` | "No he podido leer el audio de ese archivo." | "Puede estar incompleto o protegido." | no |
| `file_too_large` | supera `max_input_bytes` | `size_bytes`, `limit_bytes` | "El archivo pesa X y el tope es Y." | "Sube el tope en `settings.json` si de verdad lo necesitas." | no |
| `file_not_found` | la ruta no existe o no es un archivo | `path` | "No encuentro ese archivo." | "¿Lo has movido o renombrado?" | no |
| `model_missing` | falta el modelo y no se permitió descargar | `model_id`, `expected_bytes` | "Falta el modelo de reconocimiento." | "Descárgalo desde el aviso de arriba (464 MB)." | sí |
| `model_download_failed` | falla la descarga del modelo | `model_id`, `downloaded_bytes` | "No he podido descargar el modelo." | "Comprueba la conexión; se reanuda donde se quedó." | **sí** |
| `disk_full` | `OSError` de espacio o comprobación previa | `required_bytes`, `available_bytes`, `path` | "No queda espacio en disco." | "Hacen falta X MB libres en \<ruta\>." | sí |
| `queue_full` | la cola llegó a `max_queued_jobs` | `queued`, `limit` | "Hay demasiados trabajos esperando." | "Espera a que terminen o cancela alguno." | sí |
| `gpu_out_of_memory` | el `RuntimeError` contiene **`"out of memory"`** | `vram_free_mb`, `required_mb`, `model_id` | "La GPU se ha quedado sin memoria." | "Reintentar en CPU" (botón) o elegir un modelo menor. **No se reintenta solo**: sería multiplicar el tiempo en silencio | sí, en CPU |
| `gpu_libraries_missing` | el `RuntimeError` contiene **`"not found or cannot be loaded"`** | `library`, `expected_path` | "Falta el complemento de GPU, o sus librerías no se encuentran." | "Ejecuta `install-gpu.ps1`. Se ha transcrito con la CPU." | sí |
| `gpu_unavailable` | **cubo por defecto de CUDA**: cualquier otro `RuntimeError` de la ruta GPU | `technical` | "No se ha podido usar la GPU." | "Se ha transcrito con la CPU; el detalle está abajo." | sí |
| `cancelled` | lo paró quien llamó | — | "Cancelado." | — | sí |
| `internal` | **cubo por defecto global** | — | "Algo ha fallado por dentro." | "Detalle técnico abajo." | sí |

**Avisos que NO son errores** (van por otro canal, informativo):

| Situación | Qué se dice |
|---|---|
| `has_video=True` tras la descarga | "Esa plataforma no ofrece hoy una pista de audio suelta: se han descargado X MB de vídeo+audio. El texto sale igual." |
| yt-dlp con más de `ytdlp_stale_days` | "Tu yt-dlp tiene N días. Si algún enlace falla, actualízalo: `…`" |
| `yt_dlp` no importable | El campo de enlace se deshabilita: "La descarga desde enlaces no está disponible (falta yt-dlp)." |

**Fragilidad declarada.** `login_required`, `geo_blocked` y `media_unavailable` se distinguen **buscando
subcadenas en el texto de yt-dlp**. El spike lo vio de primera mano. Por eso `extractor_outdated` tiene que
ser una frase comprensible: recogerá lo que la clasificación no acierte. **Nunca una pila de llamadas**.

**Comprobación previa de disco:** antes de descargar un modelo o un medio se exige
`necesario * 1.2` de espacio libre.

---

## 6. Los dos modos y su exclusividad (ADR-0001 D21, D24, D25)

### 6.1 Modo ventana — el uso normal

`Voice2Text.cmd [archivo]` → `app.py` crea la ventana con pywebview, ejecuta el núcleo **en su propio
proceso** y expone las operaciones de §6.3. El archivo del menú contextual llega por `sys.argv[1]`.
`pick_file()` es `create_file_dialog()` y **devuelve la ruta absoluta**: cero copias.

> ### Requisito de arranque, no nota al pie: `storage_path` propio
>
> **`app.py` DEBE arrancar con un perfil de WebView2 dedicado**, dentro de la carpeta de la herramienta:
>
> ```python
> webview.start(storage_path=str(TOOL_DIR / "webview"), ...)
> ```
>
> **Por qué [M, 2026-08-10]:** con el perfil por defecto de pywebview, la ventana **no abrió**
> (`E_ABORT`, `0x80004004`) en una máquina donde el WebView2 Runtime **sí** estaba instalado
> (`151.0.4129.72`) y la sesión era interactiva. Al fijar un `storage_path` limpio, abrió y cerró sin
> error. La causa probable es un perfil de WebView2 heredado de **otra herramienta de BSTools que también
> lo usa: MDViewer**.
>
> Es un fallo de arranque en máquina de usuario, no un detalle estético. Y la regla trasciende a esta
> herramienta: **toda herramienta de BSTools que use WebView2 debe poseer su propio perfil.** Las carpetas
> son autocontenidas; el estado de WebView2 en `%LOCALAPPDATA%` no lo es.

Cerrar la ventana termina el trabajo entero, en un gesto.

### 6.2 Modo servidor — arranque manual, primer plano

`Voice2Text-Servidor.cmd [--port 8317]` → `serve.py`. **No hay servicio, ni tarea programada, ni arranque
con la sesión de Windows.** La consola es la que dice que está vivo (sin acentos, regla de la casa):

```
  Voice2Text - Modo servidor
  Escuchando en http://127.0.0.1:8317
  Token en: D:\...\apps\Voice2Text\serve-token.txt
  Modelo small: se carga al primer trabajo y se descarga tras 5 min sin uso.
  Cierra esta ventana o pulsa Ctrl+C para apagar.

  [19:04:12] trabajo j_7f3a1c2e recibido - nota-voz.ogg (2:14)
  [19:04:39] trabajo j_7f3a1c2e terminado - 412 caracteres, 27 s
```

- **Encendido o apagado, sin tercer estado**: si la consola existe, está vivo.
- Al apagar: cancela el trabajo en curso, purga `work/` y lo dice.
- **Puerto fijo `8317`, configurable.** Si está ocupado: mensaje y salida con código de error; **no** se
  busca otro puerto, porque el consumidor tiene la dirección escrita.
- **Token** aleatorio por arranque en `serve-token.txt` (ignorado por git). **Todas** las peticiones lo
  exigen, incluida `/health`. Sin él, `403`.
- Solo `127.0.0.1`. **No existe bandera para escuchar en `0.0.0.0`** (ADR-0001 D19).

**El trato, que va al README con estas palabras:** *el bot de Telegram solo responde mientras el servidor
esté levantado; si está apagado, el bot no contesta. No es un fallo, es el trato.*

### 6.3 Las nueve operaciones, idénticas en los dos modos

| Operación | Ventana (`window.expose`) | Servidor (`/api/v1`) |
|---|---|---|
| contexto inicial | `get_context()` | `GET /health` + `GET /models` |
| elegir archivo | `pick_file()` | — (el cliente ya tiene la ruta) |
| examinar enlace | `probe_url(url)` | `POST /jobs` con `probe_only: true` |
| encolar | `start_transcription(source, options)` | `POST /jobs` → `202 {job_id, queue_position}` |
| consultar | `get_job(job_id, since)` | `GET /jobs/{job_id}?since=N` |
| cancelar | `cancel_job(job_id)` | `POST /jobs/{job_id}/cancel` |
| descargar modelo | `download_model(model_id)` | `POST /models/{model_id}/download` |
| borrar modelo | `delete_model(model_id)` | `DELETE /models/{model_id}` |
| apagar | `quit()` | cerrar la consola o `Ctrl+C` |

HTTP de los errores: `202` encolado · `400` inválida · `403` token · `404` desconocido · `413` grande ·
`429` `queue_full` · `507` `disk_full` · `500` interno. **No existe `409`**: con cola FIFO, estar ocupado
no es un error.

### 6.4 Exclusividad: nunca dos modelos en RAM

Dos procesos con `small` cargado son ~2 GB de RSS [E] y **dos transcripciones sobre la misma CPU no van más
rápido, van más lento**. Un **cerrojo exclusivo de archivo** sobre `runtime.lock` —que el sistema operativo
libera al morir el proceso, aunque muera a lo bruto— garantiza un único proceso vivo. Junto a él,
`runtime.json` con `mode`, `pid`, `port` y `started_at`, para poder decir **qué** está corriendo.

**Nunca un fallo mudo:**

- Ventana con el servidor arriba → diálogo *"El modo servidor está en marcha (puerto 8317). Ciérralo desde
  su ventana o con Ctrl+C para usar la ventana."*, y la ventana no llega a abrirse.
- `--serve` con la ventana abierta → la consola imprime el equivalente y sale con código de error.

---

## 7. Formato de salida (ADR-0001 D8)

### Agrupación en párrafos (igual para los dos formatos)

> **Corrección del 2026-08-10, a partir de un hallazgo del lote 1 verificado experimentalmente.** La regla
> 1 estaba escrita sobre una suposición falsa: **`segment.end` NO marca el fin del habla**. faster-whisper
> **lo estira hasta el inicio del segmento siguiente**, absorbiendo el silencio. Con 3,5 s de silencio real
> insertado, el hueco medido entre `end` y el `start` siguiente fue **0** — también con `vad_filter=False`.
> Con `word_timestamps=True`, el `end` de la **última palabra** sí lo refleja (11,82 s frente a 16,1 s:
> hueco real de ~4,3 s). Por eso existe `Segment.speech_end` (§3), separado de `end`: **sobrecargar `end`
> habría escondido el problema en vez de nombrarlo.**

Se abre párrafo nuevo cuando se cumple **cualquiera** de estas:

1. Hay un **hueco > `paragraph_gap_seconds`** (2,0 s por defecto, configurable) entre el
   **`speech_end`** de un segmento y el `start` del siguiente. **Se calcula con `speech_end`, nunca con
   `end`.** Si `speech_end` es `None` (word timestamps desactivados), **esta regla se desactiva entera**:
   no se finge un hueco que no se puede medir.
2. El párrafo lleva **≥ 400 caracteres** y el último segmento acaba en `.`, `?`, `!` o `…`.
3. El párrafo llega a **700 caracteres** (corte duro).

**Qué pasa exactamente sin la regla 1, para dimensionar bien el problema:** las reglas 2 y 3 siguen
funcionando, y la 3 **acota todo párrafo en 700 caracteres ≈ 9 líneas**. Así que el fallo **no** es un muro
de veinte líneas — eso ya lo impedía el corte duro. El fallo real es más sutil y también inaceptable:
**los cortes caen donde coincidan 400 caracteres con un punto, no donde el hablante hizo una pausa.** El
`.md` con marcas de tiempo es una de las dos salidas del MVP; que sus párrafos no sigan el ritmo del
hablante es una entrega pobre.

**Decisión: `word_timestamps=True` por defecto** (ADR-0001 §17.4: calidad primero, velocidad después),
**con la medición del coste como requisito, no como seguimiento** — igual que todo lo demás en este
proyecto. Coste esperado **+10-30 % de tiempo de proceso [E]**, con una advertencia sobre mí mismo: mis
estimaciones de rendimiento en este proyecto han salido **1,5-2× optimistas**. **Medido en el lote 1.b
(V3, tabla de abajo): el coste real salió en la dirección contraria a la advertencia — no un 15-60 %
más caro, sino ~0 %, dentro del ruido de medición.** Se implementa `word_timestamps=True` sin condición
ni ajuste por perfil, tal como marcaba el criterio de cierre.

**Tres verificaciones antes de dar la regla por buena** (§14) — **las tres CERRADAS el 2026-08-10, lote
1.b**. Metodología: 5 fragmentos de voz real (SAPI inglés) unidos con silencios de duración EXACTA por
recuento de muestras (3,5 / 6,0 / 1,0 / 4,3 s), sin pasar por ningún `ffmpeg`, con el ground truth de dónde
empieza cada fragmento registrado por construcción — no medido.

| # | Qué | Por qué importaba | Resultado medido |
|---|---|---|---|
| **V2** | Reconfirmar el hallazgo con **`vad_filter=True`**, que es nuestra configuración real | El experimento se hizo con `vad_filter=False`. Con VAD, el silencio se recorta antes de decodificar y los tiempos se remapean: **los huecos pueden reconstruirse de otra forma**. Si con VAD los huecos ya aparecen, `word_timestamps` podría no hacer falta | **No se reconstruyen.** Hueco `end`→`start` = **0,000 s en los 4 silencios**, igual que sin VAD. `word_timestamps` sigue haciendo falta |
| **V3** | Medir el sobrecoste real de `word_timestamps=True`, mismo clip, con y sin | Si supera ~30 % en CPU, se expone como ajuste con valor por defecto **por perfil** (GPU sí, CPU a elección). **No se construye esa maquinaria hasta que el número la justifique** | **~0 %, dentro del ruido de medición** (2 rondas, clip real de 120-300 s, 4-2 corridas intercaladas por config: −5,5 % y −0,0 % de media). Muy por debajo de la horquilla +10-30 % [E]. **No se construye el ajuste por perfil**. ⚠️ **Contaminación declarada:** las dos rondas corrieron con **otro agente transcribiendo en paralelo en la misma máquina** (confirmado independientemente en `VERIF-ESPANOL.md`, con PID y carga de CPU). Al ser una comparación **relativa** intercalada (False/True bajo el mismo ruido de fondo en cada punto), la contención sube la varianza pero no explica por sí sola que True saliera sistemáticamente igual o más barato que False en las dos rondas; **la magnitud exacta (−0,0 % frente a, digamos, +5 %) no debe leerse al decimal**, pero "muy por debajo de +10-30 %" es una lectura robusta a ese ruido |
| **V4** | Confirmar que el **`start`** del segmento posterior al silencio sí marca el inicio real del habla | Los `[mm:ss]` que se imprimen usan `start`. Si `start` también está corrido, **el problema no es el corte de párrafo: son las marcas de tiempo**, que es mucho más grave. Una línea de comprobación que decide si lo que publicamos es fiable | **Sí, dentro de ~30 ms** en las 4 posiciones probadas (start observado 7,650/19,140/25,880/36,860 s vs. ground truth 7,679/19,162/25,911/36,869 s). **Las marcas de tiempo del `.md` son fiables** |

**Lo que NO se elige, y por qué:** cortar por número de segmentos sería arbitrario (un segmento son 2-10 s
según lo que decida el decodificador) y **aceptar la limitación y documentarla** sería vender como
"párrafos con marcas de tiempo" algo que no sigue al hablante. Esa opción no hizo falta reabrirla: V3 salió
barato y V2 no ofreció una alternativa gratis, así que `word_timestamps=True` + `Segment.speech_end` es la
solución implementada, sin condiciones pendientes.

### `.txt` — texto corrido

Solo el texto, párrafos separados por una línea en blanco. **Sin marcas de tiempo, sin cabecera.**
**UTF-8 sin BOM, saltos CRLF** (para que el Bloc de notas lo abra bien).

### `.md` — párrafos con `[mm:ss]`

**UTF-8 sin BOM, saltos LF.**

```markdown
# reunion-comite

- **Origen:** D:\Videos\reunion-comite.mp4
- **Duración:** 28:45
- **Idioma detectado:** es (99 %)
- **Modelo:** small (int8, CPU)
- **Transcrito:** 2026-08-10 19:04

---

[00:00] Buenos días a todos, vamos a empezar con el punto primero del orden del día...

[01:37] Sobre el presupuesto, lo que se planteó en la reunión anterior era...
```

Marca de tiempo del **primer segmento del párrafo**. `[mm:ss]` si el medio dura menos de una hora,
`[hh:mm:ss]` si dura más — no se mezclan formatos dentro de un archivo.

### Nombres de archivo y colisiones

- Base = nombre del origen sin extensión; para enlaces, el título saneado.
- **Saneado**: fuera `<>:"/\|?*` y caracteres de control, recorte de puntos y espacios finales, tope de
  120 caracteres; si queda vacío, `transcripcion`.
- **Nunca se sobrescribe en silencio**: si `nombre.md` existe, se escribe `nombre (2).md`.
- Destino por defecto: **la carpeta del archivo de origen**; para enlaces, `salida/`.

---

## 8. Primer arranque: qué ve el usuario

1. Doble clic (o menú contextual sobre un `.mp4`) → arranca en **menos de 2 s** [E]: no se carga ningún
   modelo al abrir, solo se mira qué hay en `models/`.
2. Con `models/` vacío, lo primero que se ve **una pantalla con esta forma** — el catálogo concreto y cuál
   viene preseleccionado **lo fija ADR-0002**:

   > **Falta el modelo de reconocimiento de voz.** Se descarga una sola vez y se queda en tu equipo.
   >
   > - ⦿ **\<modelo por defecto\> — \<N\> MB** · recomendado · **~\<T\> min por cada 10 min de audio** ·
   >   español e inglés
   > - ○ **\<alternativa ligera\> — \<N\> MB** · más rápido, se equivoca más con nombres y cifras
   >
   > Se guardará en `D:\...\apps\Voice2Text\models` · **libre en disco: 214 GB**
   > Puedes borrar esa carpeta cuando quieras.
   >
   > **[ Descargar ]**

   **Lo que rellena esos huecos lo calcula `recommend_profile()` según el hardware** (ADR-0002 §3). En una
   máquina **sin GPU**, el preseleccionado es **`small` — 464 MB [M-dev]**, y el tiempo que hay que
   escribir es **~8,7 min por cada 10 min de audio** (de 1,15× medido sobre audio real), **no 3,5**. En la
   **1050 Ti** sería `large-v3-turbo` — 1,6 GB, ~1,4 min por cada 10.

   **Obligatorio en esta pantalla, sin excepción** (ADR-0002 E3, obligación de transparencia): **los dos
   números** —cuánto se descarga **y** cuánto ocupará en RAM o VRAM al ejecutarse—, la ruta de destino, el
   disco libre, la frase de que se puede borrar, y el tiempo estimado **con su perfil de hardware**.

   > **Regla de unidad, obligatoria en toda la interfaz y el README** (ADR-0002 §8.4): **el tiempo se
   > expresa en "minutos de proceso por cada 10 minutos de audio", NUNCA como un multiplicador `×`.** El
   > `speed_ratio` es un campo técnico del estado (§4.2) y **no aparece jamás en un texto para humanos**:
   > ya se leyó del revés una vez (un `2,8×` se transmitió como "28 minutos" en lugar de 3,6), con un
   > factor 8 de error. Una unidad que se puede leer al revés acabará leyéndose al revés.
   >
   > **Historial de cifras falsas en esta misma pantalla, para no repetirlo una tercera vez:** primero puso
   > "~2 min" (estimación de memoria), luego "~3-4 min" (derivada de un clip **sintético** de 42,7 s). La
   > buena es **~8,7 min** [M-dev, audio real, `vad_filter=True`]. **El audio sintético sirve para probar
   > el mecanismo, no para medir rendimiento, y su sesgo es optimista en una sola dirección.**

   Y una línea más, ahora que la GPU está aprobada: **qué dispositivo se va a usar**, con el estado
   tri-estado de §3 — *"Aceleración GPU: disponible (se confirma en el primer trabajo)"* / *"activa
   (GTX 1050 Ti, int8)"* / *"no instalada — [cómo activarla]"*. **Nunca se afirma que la GPU funciona antes
   de que la prueba de humo lo confirme.**

3. Al pulsar: fase `downloading_model` con progreso calculado **midiendo el tamaño de `models/` contra
   `expected_bytes`**, que funciona haya o no llamada de vuelta en la biblioteca de descarga (S4, abierto).
4. La **consola también imprime el progreso** (sin acentos): si el usuario cerró la interfaz, sigue viendo
   que avanza.
5. **Si se corta**, se reanuda donde se quedó.
6. **Sin internet y sin modelo**: `model_missing` con la ruta exacta donde dejar los archivos a mano.
7. A partir de la segunda vez, nada de esto aparece.

`medium` y `large-v3-turbo` aparecen **marcados por superar el techo de 1 GB**, no escondidos.

**Los modelos no se purgan solos** (ADR-0001 D15). La interfaz muestra `models/ — 464 MB` con un botón de
borrar por modelo, y el README dice que la carpeta se puede borrar entera.

---

## 9. `settings.json` — lo configurable, en datos

Valores por defecto en `settings.py` (un `dict` legible), **capa de cáscara**. Si existe `settings.json` al
lado, sus claves pisan a las de por defecto. **El motor nunca lee ninguno de los dos** (ADR-0001 D13).

| Clave | Por defecto | Qué es |
|---|---|---|
| `default_model_id` | 🚫 **lo fija ADR-0002** | modelo a usar |
| **`device_preference`** | `"auto"` | `"auto"` \| `"cuda"` \| `"cpu"`. **Es lo único que la cáscara puede decir sobre el dispositivo**; la política vive en `resolve_device()` (§3) |
| `compute_type_override` | `null` | **`null` = manda `resolve_device()`.** Fijarlo a mano solo para depurar: un valor fijo aquí **sería incorrecto en al menos una de las dos máquinas del dueño** (ADR-0001 §17.1) |
| `cpu_threads` | `0` | 0 = decide CTranslate2. Ignorado en GPU |
| `language` | `null` | `null` = detección automática; `"es"`/`"en"` la fuerzan |
| `vad_filter` | `true` | recorte de silencios |
| **`word_timestamps`** | `true` | rellena `Segment.speech_end`. **Es lo único que permite cortar párrafo por las pausas del hablante** (§7). Coste medido en V3: ~0 %, dentro del ruido |
| **`paragraph_gap_seconds`** | `2.0` | hueco a partir del cual se abre párrafo. Se ajusta contra material real **sin tocar código**, misma filosofía que D26 |
| **`min_viable_speed_ratio`** | `1.0` | suelo del filtro de viabilidad (ADR-0002 E2): nunca se **recomienda** algo más lento que el tiempo real. El usuario sí puede elegirlo a mano |
| `max_input_bytes` | `2147483648` | tope de archivo/descarga (2 GiB) |
| `output_formats` | `["txt","md"]` | qué se escribe |
| `output_dir` | `null` | `null` = junto al origen |
| `work_retention_hours` | `24` | antigüedad a partir de la cual se purga `work/` |
| `ytdlp_stale_days` | `60` | a partir de aquí, aviso de yt-dlp caducado |
| **`youtube_player_clients`** | `["android","ios","tv","web"]` | **orden de intento (ADR-0001 D26). Es el valor que más rápido caduca [O]: se arregla aquí, sin tocar código** |
| `serve_port` | `8317` | puerto fijo del modo servidor |
| `max_queued_jobs` | `8` | tope de cola; pasado, `queue_full` |
| `model_idle_timeout_seconds` | `300` | inactividad tras la que se suelta el modelo (`0` = nunca) |

---

## 10. Ciclo de vida de los archivos y purga (ADR-0001 D15)

| Carpeta / archivo | Quién escribe | Quién purga | Cómo se ve |
|---|---|---|---|
| `models/` | `models.py`, con consentimiento explícito | **nadie automáticamente** — solo el usuario | tamaño total siempre visible |
| `webview/` | WebView2, a través de pywebview | **nadie** — borrable a mano; se regenera solo | no se enseña |
| `work/` | `fetch.py` | **al arrancar**, lo de más de `work_retention_hours`; **tras cada trabajo**, lo suyo; **al apagar el servidor**, todo | detalle interno |
| `salida/` | `export.py`, solo para enlaces | nadie: **son datos del usuario** | es la carpeta que el usuario abre |
| `runtime.lock` / `runtime.json` | el proceso vivo | el sistema operativo suelta el cerrojo al morir el proceso | solo se lee para el mensaje de §6.4 |
| `serve-token.txt` | `serve.py` al arrancar | se reescribe en cada arranque | el bot lo lee |

Los temporales se llaman `<job_id>.<ext>`, **nunca con nombre fijo**.

---

## 11. Seguridad y validación

- **Canonicalizar antes de validar.** Toda ruta pasa por `Path(...).resolve()` **antes** de comprobar nada.
- **El destino se deriva, no se acepta.** El nombre de salida se **construye** desde el origen ya
  canonicalizado y el saneador de §7. Nunca se pega un nombre que venga del usuario o del título de un
  vídeo sobre una ruta.
- **URL:** solo `http`/`https`.
- **Tope de tamaño** en entrada y descarga, comprobado **antes** de empezar. Es la salvaguarda que cubre el
  caso de descarga muxeada (§3).
- **Nunca credenciales** (ADR-0001 D6): ni cookies, ni usuario/contraseña, ni lectura del navegador.
- **Nada escucha en red** salvo el modo servidor, y solo en `127.0.0.1`, con token en todas las peticiones.

---

## 12. Qué se versiona y qué se ignora

**Se versiona:** `install.ps1`, `uninstall.ps1`, los dos `.cmd`, todos los `.py`, `ui.html`,
`requirements.txt`, `icon.ico`, `README.md`, `ARCHITECTURE.md`, `SPIKE-RESULTS.md`, `.gitignore` y
`salida/.gitignore`.

**Se ignora** — `apps/Voice2Text/.gitignore`:

```gitignore
# Modelos descargados (464 MB el small). Se bajan al primer uso; borrables cuando quieras.
models/

# Perfil propio de WebView2 (ver ARCHITECTURE.md 6.1). Se regenera solo.
webview/

# Descargas y temporales de cada trabajo
work/

# Salida por defecto de las transcripciones desde enlace
salida/

# Ajustes locales de esta maquina (los valores por defecto estan en settings.py)
settings.json

# Estado de ejecucion y secreto del modo servidor
runtime.lock
runtime.json
serve-token.txt

# Accesos directos generados por install.ps1 (rutas absolutas de cada maquina)
*.lnk

# Material de prueba generado (audio sintetico, .mp4 construidos con PyAV, salidas de referencia)
test/

__pycache__/
```

**No se versiona nunca, y es una regla** (ADR-0001 §8): ningún wheel, ningún binario de
PyAV/CTranslate2/FFmpeg, ningún modelo. Además del peso, meterlos convertiría a BSTools en redistribuidor
de binarios LGPL y de MKL dentro de un repositorio CC0. Y un `model.bin` de 464 MB lo rechaza GitHub de
todas formas (tope de 100 MB por archivo).

---

## 13. Plan de construcción, en lotes aprobables

| Lote | Qué entra | Criterio de aceptación | Estado |
|---|---|---|---|
| **0** | *Spike* de supuestos en venv aislado | S1, S5, S6, S8 y peso resueltos | **HECHO** — `SPIKE-RESULTS.md` |
| **1** | `errors.py` + `transcribe.py` + `export.py` + `cli.py` + contrato de dispositivo (`resolve_device()` entera, `probe_devices()` con CUDA apagado, `recommend_profile()`) | 9 casos de ejecución real · motor sin `webview` ni `http.server` (verificado con `grep` sobre disco) | **HECHO y commiteado** |
| **1.b** | Cierre de los pendientes que dejó el lote 1 | **V2** (huecos con `vad_filter=True`) · **V3** (coste de `word_timestamps`) · **V4** (¿`start` marca el habla real?) · **V1** (10 min en español, bloqueada por falta de voz española) | **V2, V3, V4 HECHAS y `speech_end`/`word_timestamps` implementados (2026-08-10, ver §7)** · V1 y S11 verificados aparte (`VERIF-ESPANOL.md`, misma fecha): **S11 en verde**; **V1 medido pero NO cerrado** — `speed_ratio` 0,93x-1,31x según recorte, contaminado por contención de CPU con otro agente corriendo en la misma máquina durante la medición (evidencia de proceso en ese informe). Repetición limpia pendiente antes de tocar la cláusula de ADR-0001 D5 |
| **2** | `models.py` + `jobs.py`: catálogo, descarga con progreso, cola FIFO, cancelación, cerrojo, purga, suelta del modelo | encolar tres trabajos y ver `queue_position` · cerrar S4, S12 y S13 | pendiente |
| **3** | Cáscara ventana (`app.py`, `ui.html`, `messages.py`, `settings.py`) | doble clic abre · **`storage_path` propio (§6.1)** · cerrar S11 | pendiente |
| **4** | `fetch.py`: enlaces, clasificación de errores, aviso de caducidad, `player_clients` de settings | un muxeado de YouTube **no** produce error · cerrar S7 con un enlace de X | pendiente |
| **5** | `install.ps1`, `uninstall.ps1`, los dos `.cmd`, `icon.ico`, `README.md` + checklist de cierre | los tres niveles de prueba de la casa | pendiente |
| **6** | `serve.py`: modo servidor, `/api/v1`, token, exclusividad | `curl` contra los nueve endpoints **y `git diff --stat` sin cambios en el motor** | pendiente |
| **7** | **GPU (ADR-0002):** `install-gpu.ps1`, `uninstall-gpu.ps1`, `requirements-gpu.txt`, `add_cuda_dlls_to_path()`, imports perezosos, `smoke_test_cuda()`, catálogo con VRAM medida | el instalador **termina ejecutando la prueba de humo y dice el resultado** · desinstalar sin GPU no rompe nada · los tres códigos de fallo dan tres mensajes distintos | pendiente |

**V1 es la verificación que puede cambiar el valor por defecto** (ADR-0001 D5): si 10 minutos de audio en
español dan menos de 3× tiempo real, `base` pasa a ser el modelo por defecto, sin ADR nuevo.

**El lote 4 va tarde a propósito**: es el único frágil. Si hubiera que soltar antes, los lotes 1-3 y 5 ya
dan una herramienta completa para archivos locales.

**El lote 6 es la prueba de falsación de las tres capas** (ADR-0001 D18): si escribir la segunda cáscara
obliga a tocar `transcribe.py`, `fetch.py`, `export.py` o `models.py`, el desacople era decorativo y hay
que arreglarlo antes de cerrar la v1.0. Se comprueba con `git diff --stat`.

---

## 14. Cómo se prueba

Los tres niveles obligatorios de la casa, más lo propio de esta herramienta.

### La entrada sintética — receta validada en el spike [M]

**Funciona sin instalar nada y sin ffmpeg**, que es justo lo que hay que demostrar:

1. **Voz real** con `System.Speech.Synthesis` (viene con Windows, no es dependencia del proyecto):

   ```powershell
   Add-Type -AssemblyName System.Speech
   $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
   $s.SetOutputToWaveFile("C:\temp\prueba.wav")
   $s.Speak("Prueba de Voice2Text. Reunion del comite del doce de agosto. Presupuesto: dos mil cuatrocientos euros.")
   $s.Dispose()
   ```

2. **Contenedor `.mp4` con vídeo trivial, construido con PyAV** — nunca con un binario externo. El spike
   confirmó que el wheel de PyAV trae `libx264` y `aac` embebidos [M], así que se decodifica el `.wav` con
   `av.open(...)`, se generan fotogramas sintéticos y se muxa con `container.mux(...)`.

> **Voces SAPI disponibles (2026-08-10):** `Microsoft David Desktop` (inglés) y **`Microsoft Sabina
> Desktop` (`es-MX`)**, instalada por el dueño y **verificada visible para `System.Speech.Synthesis` con
> `GetInstalledVoices()`** — la comprobación importa: muchas voces de Windows se instalan solo para el
> Narrador y SAPI no las ve. **V1 y S11 quedan desbloqueadas.** El dialecto `es-MX` no afecta a ninguna de
> las dos: Whisper detecta `es` sin distinguir variante y el coste de proceso no depende del acento.
>
> **Lo que la voz sintética NO desbloquea: V6, la calidad de texto en español.** Una medición de calidad
> sobre TTS es **optimista**: no hay acento marcado, ni ruido, ni solapamiento, ni micrófono mediocre, ni
> muletillas — justo el material donde un modelo mayor se separa de uno menor. **V6 exige una grabación
> humana real** con transcripción de referencia (ADR-0002 §10).
>
> El lote 1 hizo lo correcto **no aproximando V1 con audio en inglés**: una medición de velocidad en el
> idioma equivocado no es conservadora, es un número que parece válido y no lo es.

Casos que la entrada debe incluir: cifras, nombres propios, un silencio largo (alucinación) y un archivo
deliberadamente truncado (para `decode_failed`).

### Los tres niveles

1. **El motor a pelo:** `py -3 cli.py "C:\temp\prueba.wav"`.
2. **El lanzador desde una ruta con espacios**, con el argumento entre comillas — el fallo clásico.
3. **El registro:** leer la clave y el `command`, comprobar que `uninstall.ps1` lo deja limpio y que
   ejecutar `install.ps1` dos veces no duplica nada.

### La migración a la RTX 3080: probar la máquina que no tienes

Se desarrolla en una **GTX 1050 Ti (Pascal, cc 6.1, 4 GB)** y el destino es una **RTX 3080 (Ampere, cc 8.6,
10 GB)**. Hay fallos que **por construcción no pueden aparecer en desarrollo**: la rama `float16` nunca se
ejecuta, la política de VRAM nunca se ve decir "sí cabe", y `large-v3` nunca se descarga ni se carga
(ADR-0001 §17.6).

**Lo que sí se puede probar hoy, y es la razón de que `probe_devices()` y `resolve_device()` sean dos
funciones:** `resolve_device()` es **pura** — recibe `DeviceCapabilities` y devuelve una decisión, sin
tocar hardware. Se le fabrican capacidades sintéticas y se comprueba la política entera desde la máquina de
desarrollo:

| Caso (capacidades sintéticas) | `DeviceChoice` esperada |
|---|---|
| cc 8.6 · 10240 MB libres · `["float16","int8_float16","int8","float32"]` | `cuda` + **`float16`** |
| cc 8.6 · **900 MB libres** (juego abierto) | `cpu`, `fell_back_from="cuda"`, motivo `insufficient_vram` |
| cc 6.1 · 3200 MB · `["int8","float32"]` (perfil DEV real) | `cuda` + **`int8`** |
| cc 6.1 · 3200 MB · modelo que pide 4 GB en fp16 | `cuda` + `int8` si cabe; si no, `cpu` |
| `cuda_status="unavailable"`, motivo `cuda_libs_missing` | `cpu`, con aviso, **nunca un error** |
| `cuda_status="unavailable"`, motivo `cuda_libs_mismatch` | `cpu`, con aviso **distinto**: la acción del usuario no es la misma |
| cc 8.6 · 9500 MiB libres · `large-v3` fp16 (pico ~6100 MiB [E]) | `cuda` + `float16` — quedan ~3,4 GiB, pasa la holgura de 512 MiB |
| cc 6.1 · 3546 MiB libres · `large-v3` int8 (pico **3951 MiB [M-dev]**) | `cpu` por `insufficient_vram` — **este caso se midió y reventó de verdad** |
| cc 6.1 · 3546 MiB libres · `medium` float32 (pico ~3900 MiB [M-dev]) | `cpu` — es el caso de **degradación silenciosa**: la holgura de 512 MiB existe para excluirlo |
| `preference="cpu"` con una 3080 presente | `cpu`, `fell_back_from=None` (lo pidió el usuario, no es caída) |

**Lo que NO se puede simular, y hay que decirlo sin adornos:** la **ejecución** real en `float16` exige
hardware ≥ 7.0. En desarrollo se verifica que se **llega** a la rama y que el error, si lo hubiera, se
maneja; que el cálculo sea correcto solo se sabe en producción.

**`--self-check`, escrito ANTES de migrar.** Un comando, no un procedimiento:

```
py -3 cli.py --self-check
```

Imprime las `DeviceCapabilities` reales, la `DeviceChoice` resuelta, transcribe el clip sintético y compara
con la referencia. **Criterio de aceptación de la migración:** pasa el `--self-check`,
`device_used.compute_type == "float16"`, y **V1 se remide en producción**. Las cifras del README **se
reetiquetan por perfil ([M-dev] / [M-prod]), no se sustituyen**: el repositorio es público y quien lo
descargue no tiene ninguna de las dos máquinas.

**Trampa de las pruebas de salida:** `int8` y `float16` producen texto **legítimamente distinto**. Una
prueba que exija salida idéntica byte a byte fallará en producción por un motivo correcto — el peor falso
positivo. Se compara con tolerancia (p. ej. tasa de error de palabra contra un texto de referencia), nunca
por igualdad exacta.

### Pruebas propias de esta herramienta

- **Sin ffmpeg, siempre.** Antes y después de cada corrida, `where ffmpeg` debe seguir sin encontrar nada.
  Es la invariante de D2 y así se verificó en el spike.
- **Cola:** encolar tres trabajos, comprobar `queue_position`, que se ejecutan en orden y que cancelar el
  segundo (en cola) es instantáneo.
- **Exclusividad:** abrir ventana + servidor en los dos órdenes y ver el mensaje, no un fallo mudo. Matar
  el primer proceso desde el administrador de tareas para confirmar que el cerrojo se libera (S12).
- **WebView2:** arrancar la ventana en una máquina que ya tenga MDViewer usado, para confirmar que el
  `storage_path` propio evita el `E_ABORT` medido en el spike (§6.1).
- **Enlace muxeado:** descargar un vídeo de YouTube y confirmar que `has_video=True` produce un **aviso**,
  no un error, y que la transcripción sale igual.
- **Escritura:** rutas con espacios, un título con caracteres inválidos (`¿Qué? / cómo: 1|2`) y un intento
  de travesía de directorios en el nombre de salida.

---

Parte de [BSTools](../../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · CC0 1.0
