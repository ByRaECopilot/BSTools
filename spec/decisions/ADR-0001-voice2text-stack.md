---
title: "ADR-0001 — Voice2Text: núcleo de transcripción local reutilizable, con faster-whisper y sin ffmpeg del sistema"
status: parcialmente-derogado
superseded_by: "ADR-0002-voice2text-modelo-y-gpu.md — supersede D5, D20 y la regla de peso de §7"
updated: 2026-08-10
---

# ADR-0001 — Voice2Text: núcleo de transcripción local reutilizable, con faster-whisper y sin ffmpeg del sistema

> ## AVISO — premisa corregida el 2026-08-10. Lee esto antes de construir nada
>
> Este ADR se escribió con **un límite mal transmitido**: se entendió "1 GB" como techo de la
> **instalación completa**. El dueño lo ha corregido: **1 GB es el presupuesto del MODELO, "incluso un
> poco más", y la prioridad declarada es la CALIDAD del texto**. Sobre la memoria: *"cómete el 100 % si
> deseas"*. La única frontera dura es física: **4096 MiB de VRAM** (GTX 1050 Ti, Pascal, driver 560.94)
> menos lo que gaste el escritorio.
>
> **EN CUARENTENA — no se construye contra esto:**
>
> | Qué | Dónde | Por qué muere |
> |---|---|---|
> | **D20** (techo de instalación de 1 GB) | §2 | El techo nunca fue de la instalación. Se sustituye por un **presupuesto de modelo** + **obligación de transparencia** sobre el total |
> | **D5** (modelo por defecto `small`) | §2, §6 | Con calidad como prioridad y ~1 GB de presupuesto de modelo, `small` (464 MB) ya no es la elección obvia: entran `medium` y `large-v3-turbo`. **Reabierto, pendiente de las cifras del spike de GPU** |
> | **La cláusula condicional V1** (bajar a `base` si < 3× tiempo real) | D5, §14, §16 | **SUSPENDIDA.** Está exactamente del revés: degradaba el modelo para ganar velocidad cuando la prioridad declarada es la calidad. Ya no puede dispararse |
> | **La regla pre-comprometida de peso** (≤ 0,9 / 0,9-1,0 / > 1,0 GB) | §7 | Ya no refleja la intención del dueño. El peso total **se reporta, no se limita** |
> | Marcas de "supera el techo" en el catálogo | §6, `ARCHITECTURE.md` §3 y §8 | El criterio de marcado cambia |
> | La justificación por peso de rechazar `openai-whisper` | §12 | El argumento del techo se evapora. **El rechazo sigue en pie por otras razones**, pero hay que reescribirlas |
>
> **SIGUE FIRME todo lo demás**, y en particular: D1-D4, D6-D19, D21-D26; §3 (sin ffmpeg, medido); §5
> (tres capas, contrato del núcleo, modo servidor); §8 (licencias); §9 (yt-dlp); §10 (errores); §11 (ToS).
> Los lotes 1-6 de `ARCHITECTURE.md` §13 **siguen siendo el plan**, con la enmienda de contrato de §3 que
> ya está incorporada (resolución de dispositivo).
>
> **Instrumento de corrección:** un **ADR-0002** que supersede D5, D20 y la regla de §7, y que decidirá a
> la vez el modelo y la política de GPU — **son una sola decisión, no dos** (§17). Se escribe cuando
> entreguen las cifras del spike de GPU. Hasta entonces este documento queda `parcialmente-derogado`.

**Conclusión primero.** Se adopta faster-whisper (CTranslate2) sobre Python 3.11, con PyAV como único
decodificador y yt-dlp para enlaces. **La premisa central —transcribir sin `ffmpeg` en el sistema— está
medida, no supuesta** (§3). Decisiones del dueño: modelo **`small`** por defecto, **techo de 1 GB**,
idiomas **español e inglés**, **ventana propia con pywebview**, y un **modo servidor de arranque manual**
para que un bot de Telegram **en la misma máquina** consuma el núcleo.

**Peso real medido: ~795 MB** (331 MB de venv + 464 MB de modelo) [M] — dentro de la horquilla declarada y
bajo el techo. **Lo único que el spike refutó es un matiz, no una decisión:** hoy YouTube sin cookies no
entrega pista de audio suelta; cae un `.mp4` ya muxeado. La invariante "cero ffmpeg" **no se rompió en
ningún momento**, pero D3 se reescribe para no prometer lo que la plataforma no garantiza (§3.2).

**Aviso que gobierna todas las cifras de este documento:**

| Marca | Significado |
|---|---|
| **[M-dev]** | **Medido** el **2026-08-10** en la máquina de **desarrollo** (Windows 10 Pro, Python 3.11.9, GTX 1050 Ti). **Es el peor caso, no el rendimiento esperado** (§17.1) |
| **[M-prod]** | Medido en la máquina de **producción** (RTX 3080). **Todavía no existe ninguna cifra así** |
| **[E]** | **Estimado**, sin medir. Trátese como orden de magnitud, no como dato |
| **[O]** | **Observación fechada sobre un tercero** (YouTube, TikTok…). **No es una propiedad del diseño**: la plataforma puede cambiarla unilateralmente y sin aviso |

Un número sin marca es un error de redacción. Ya costó una afirmación optimista al dueño sobre el ahorro
de descarga de yt-dlp (§3.2).

---

## 0. Historias de usuario

1. Como usuario **quiero hacer clic derecho sobre un `.mp4`/`.mp3` y sacar su texto** sin subir nada a
   internet, para transcribir reuniones y vídeos propios sin pagar ni exponer material privado.
2. Como usuario **quiero pegar el enlace de un vídeo público** (YouTube, TikTok) y obtener su texto.
3. Como usuario **quiero ver que la cosa avanza** durante los minutos que tarda y poder cancelar.
4. Como usuario **quiero el texto en `.txt` (corrido) y en `.md` (párrafos con `[mm:ss]`)**.
5. Como usuario **quiero que cuando falle se me diga qué pasó en castellano** y no un volcado de error.
6. Como dueño **quiero levantar un modo servidor a mano cuando lo necesite**, para que un bot de Telegram
   **en mi propio equipo** use el mismo motor, y **apagarlo cuando termine**.

**Lo que NO se hace:** `.srt`, diarización, traducción, cookies o cuentas para contenido privado, GPU
obligatoria, **el bot en sí**, y **cualquier forma de arranque automático** del servidor.

---

## 1. Contexto

- La herramienta vive en `apps/Voice2Text/` y debe cumplir la regla de oro: **carpeta autocontenida, se
  copia y funciona** ([`principles.md`](../constitution/principles.md)).
- La constitución prohíbe **"dependencias de gigabytes"**, **instaladores binarios**, **servicios en
  segundo plano** y **entradas en el arranque que no sean una tarea programada visible**
  ([`tech-stack.md`](../constitution/tech-stack.md)). Las cuatro se respetan; la primera lleva cifra del
  dueño: **1 GB** (§7).
- La dirección fijó: motor local `faster-whisper`, Python 3.11 + `requirements.txt`, modelos fuera del
  repo, **prohibido exigir `ffmpeg`**, `yt-dlp` sin cookies y solo contenido público, salida `.txt` +
  `.md`, CC0.
- **Idiomas objetivo: español e inglés.** Descarta los modelos `.en` y los destilados rápidos.
- Máquina principal: **Windows 10 Pro, Python 3.11.9**
  ([`entorno-local.md`](../operations/entorno-local.md)); sin .NET SDK ni `gh`.
- **Requisitos llegados después del encargo**, en tres aclaraciones del dueño: *"quisiera dejarlo preparado
  para que brinde apis y otras apps (bot telegram) lo puedan consumir"*; el bot correrá **en la propia
  máquina del usuario**; y el modo servidor *"solo se activa manualmente… osea arranco el server, uso el
  bot, apago el server"*.
- **El spike del lote 0 se ejecutó el 2026-08-10** en un venv desechable fuera del repo, con `ffmpeg`
  confirmado fuera del `PATH` antes y después de cada paso. Informe:
  `apps/Voice2Text/SPIKE-RESULTS.md`.

### Nota de numeración de ADRs (leer una vez)

Este repositorio **no tenía `spec/decisions/`**: este es su primer ADR y por eso lleva el **0001**. Los
números altos citados en la constitución (ADR-0042, ADR-0045, ADR-0047, ADR-0049) son ADRs **del canon de
la casa**, viven en el repositorio padre y **no están aquí**. Anotado en
[`spec/decisions/README.md`](README.md).

### Nota sobre las correcciones de este documento

Todas las correcciones se hicieron **antes** de la aceptación, mientras el ADR estaba en `propuesto`; por
eso son ediciones y no ADRs nuevos. **A partir de hoy el documento es *append-only***: un cambio será un
ADR nuevo que lo supersede — con **una única excepción ya escrita**, la cláusula condicional de D5, que
esta decisión pre-autoriza y por tanto no necesita otro ADR para dispararse.

Las formulaciones refutadas (por los requisitos posteriores y por el spike) se han eliminado del documento
**entero**, no solo de donde se discuten.

---

## 2. Decisión

Las marcadas ✎ corrigen una versión anterior de este mismo documento; **D3 y D5 fueron corregidas por
mediciones del spike.**

| # | Decisión |
|---|---|
| **D1** | Motor: **`faster-whisper`** (CTranslate2), en CPU, `compute_type="int8"`. Sin PyTorch, sin CUDA obligatoria. **Validado [M]**: `.mp4` transcrito sin ffmpeg en el sistema. |
| **D2** | **Toda** la decodificación la hace **PyAV**, que embebe FFmpeg dentro de su wheel. **Ninguna ruta de código invoca un binario `ffmpeg`/`ffprobe` del sistema.** Invariante: un PR que la introduzca se rechaza. **Validado [M]**. |
| **D3** ✎ | A `yt-dlp` **no se le pide ningún postprocesado**: `postprocessors=[]`, y prohibidos `--extract-audio`, `merge_output_format` y cualquier selector que obligue a fusionar dos streams. El selector es `bestaudio[abr<=128]/bestaudio/best`: pide audio suelto y **cae en `best` cuando la plataforma no lo ofrece**. **Descargar solo audio es un mejor esfuerzo, no una garantía** (§3.2). Que caiga un archivo muxeado (vídeo+audio) es **flujo normal, nunca un error**. |
| **D4** | **Modelos fuera de git**, en `models/`, descargados al primer uso, en `.gitignore`. Razón dura: `small` es un `model.bin` de **464 MB [M]** y **GitHub rechaza archivos de más de 100 MB** sin LFS. |
| **D5** 🚫 | **EN CUARENTENA — reabierto, no construir contra esto.** Decía: modelo por defecto `small`, `medium` y `large-v3-turbo` marcados por superar el techo, y una **cláusula condicional** que bajaba a `base` si V1 daba < 3× tiempo real. Con la premisa corregida (presupuesto de ~1 GB **de modelo**, calidad como prioridad, memoria sin límite), `small` deja de ser la elección obvia y **la cláusula condicional queda SUSPENDIDA por estar del revés**: degradaba calidad para ganar velocidad. Lo único que sobrevive de D5 y **sigue firme**: `tiny` retirado, **prohibidos los modelos `.en`** y las variantes *distil* (solo inglés; los idiomas objetivo son español **e** inglés). Se decide en **ADR-0002**, junto con la GPU. |
| **D6** | Enlaces con **`yt-dlp`**, solo **HTTP/HTTPS**, solo contenido público, **sin cookies ni credenciales jamás**. No es alcance: es la postura legal (§11). |
| **D7** | El camino de enlaces es **módulo opcional y aislado**: `import yt_dlp` perezoso. Si yt-dlp falta o está roto, **los archivos locales siguen funcionando**. |
| **D8** | Salida: **`.txt`** (texto corrido) y **`.md`** (párrafos con `[mm:ss]` y cabecera). `.srt` fuera. Contrato en [`ARCHITECTURE.md`](../../apps/Voice2Text/ARCHITECTURE.md). |
| **D9** | **Trabajo asíncrono**: encolar → consultar → recoger. **La misma forma en proceso y por HTTP** (§5.2). No existe ninguna llamada síncrona que espere. **Validado [M]**: CTranslate2 libera el GIL (19,84 de 20 tics/s durante la transcripción), así que un hilo de interfaz sigue respondiendo. |
| **D10** ✎ | **Los errores del núcleo son códigos estables + datos estructurados**: `code` (inglés, `snake_case`) + `details`. **Ni un solo texto de pantalla vive en el núcleo**; la traducción está en la cáscara, en un único archivo. |
| **D11** ✎ | **Tres capas: motor → orquestación → cáscara.** El **motor** (`transcribe.py`, `fetch.py`, `export.py`, `models.py`) es puro: sin estado global, sin leer configuración, sin `print`, sin `sys.exit`, sin idioma. La **orquestación** (`jobs.py`) posee cola, estado y cancelación. La **cáscara** (`app.py`, `serve.py`) es lo único que sabe de ventanas, HTTP o castellano. Se audita leyendo los `import`. |
| **D12** | **Nombres de datos en inglés** `snake_case`; **lo que ve el usuario, en castellano**. Sin acentos en consola, con acentos en `.md` y HTML. |
| **D13** ✎ | La configuración se **resuelve en la cáscara y se pasa por argumentos**. El motor **nunca lee `settings.json`** ni variables de entorno. |
| **D14** ✎ | **Cola FIFO con un único trabajo en ejecución.** Encolar **siempre se acepta** hasta `max_queued_jobs` (8); el cliente recibe `queue_position` y espera estimada. **Sin prioridades**, porque D21 impide que ventana y bot coexistan. |
| **D15** | `work/` se **purga sola** (24 h al arrancar; lo suyo tras cada trabajo). Archivos nombrados por `job_id`, **nunca con nombre fijo**. `models/` y `webview/` **no se purgan solas**: la UI muestra el tamaño de `models/` y ofrece borrar cada modelo. |
| **D16** | La arquitectura se documenta en **`apps/Voice2Text/ARCHITECTURE.md`**. El ADR va en `spec/decisions/` porque la decisión es del repositorio. |
| **D17** | **El núcleo es la API.** Su contrato se escribe **ahora** y se trata como contrato público. Romperlo es un cambio incompatible, no un refactor. |
| **D18** | **Modo servidor `--serve`: construido en el lote 6, dentro de la v1.0.** No por tener consumidor, sino porque **escribir una segunda cáscara es la prueba de falsación de D11** (§5.4). |
| **D19** | **`--serve` escucha solo en `127.0.0.1`. No hay, ni habrá, opción para escuchar en `0.0.0.0`.** |
| **D20** 🚫 | **EN CUARENTENA — premisa mal transmitida.** Decía "techo de instalación por defecto: 1 GB". **El techo nunca fue de la instalación: es el presupuesto del modelo, con margen hacia arriba.** Sobre el peso total, lo que el dueño exige es **transparencia, no un límite**: se sigue midiendo, se sigue publicando en el README y se sigue avisando en la pantalla de primer arranque (`ARCHITECTURE.md` §8), pero **deja de ser una restricción de diseño**. La medición de ~795 MB [M] sigue siendo válida como dato. Se reescribe en ADR-0002. |
| **D21** ✎ | **Ventana y servidor son excluyentes**, garantizado por un cerrojo de archivo. El segundo intento **no arranca** y explica qué hay corriendo. **Razones, reordenadas tras la corrección de premisa:** (1) **la VRAM es la única frontera dura** — 4096 MiB menos el escritorio, y dos procesos peleándose por ella en una GPU de 4 GB no es un desperdicio, es un fallo de asignación; (2) dos transcripciones sobre la misma CPU **no van más rápido, van más lento**. **El argumento de la RAM se retira**: el dueño ha dicho *"cómete el 100 % si deseas"*. La decisión **no cambia; su justificación sí**, y ahora es más fuerte, no menos. |
| **D22** ✎ | **El modelo se descarga de memoria** tras `model_idle_timeout_seconds` (300 s) sin trabajos. Coste: la siguiente transcripción paga la recarga (~3-10 s [E], S13). **Justificación reordenada:** en **GPU** libera VRAM que el escritorio y cualquier otra aplicación necesitan de verdad — ahí sigue siendo claramente rentable. En **CPU**, con la RAM sin límite declarado, **el beneficio casi desaparece**: ADR-0002 debe evaluar si el valor por defecto en CPU pasa a `0` (no soltar nunca) y el temporizador queda solo para la ruta GPU. |
| **D23** | Modo servidor con **puerto fijo y configurable** (`8317`), no efímero. Si está ocupado, **mensaje claro y salida**; nunca se busca otro puerto en silencio. |
| **D24** | **Sin arranque automático de ninguna clase**: ni servicio, ni tarea programada, ni entrada en el inicio de sesión. **Consecuencia que va al README con estas palabras: el bot de Telegram solo responde mientras el servidor esté levantado; si está apagado, el bot no contesta. No es un fallo, es el trato.** |
| **D25** | **La ventana fija su propio `storage_path` para WebView2**, en `apps/Voice2Text/webview/`. **No es una nota al pie: es un requisito de arranque.** Medido [M]: con el perfil por defecto de pywebview la ventana **falló con `E_ABORT`** en una máquina que ya tenía otro perfil de WebView2 (probablemente de MDViewer); con `storage_path` propio abrió y cerró limpio. |
| **D26** | La lista de `player_client` que yt-dlp prueba para YouTube vive en **`settings.json`, no en el código** (`["android","ios","tv","web"]` por defecto, en orden). Razón: es el parámetro que **más rápido caduca** [O] y debe poder ajustarse sin tocar un `.py` ni esperar a una versión. |

---

## 3. La restricción "sin ffmpeg instalado": medida, no supuesta

### 3.1 Lo que se verificó [M] — 2026-08-10

Con `where ffmpeg` devolviendo *"Could not find files for the given pattern(s)"* antes y después de cada
paso, en un venv desechable:

1. **PyAV abrió un `.mp4` directamente** (`mov,mp4,m4a,3gp,3g2,mj2`, streams `h264` + `aac`) sin ningún
   binario `ffmpeg`/`ffprobe` en el sistema.
2. **faster-whisper lo transcribió correctamente.** Con el idioma coincidiendo con el audio, la
   transcripción del clip de prueba fue prácticamente perfecta.
3. **PyAV también codifica:** el propio `.mp4` de prueba se construyó con PyAV (`libx264` + `aac`
   embebidos en el wheel), sin tocar un binario externo. Esto no era necesario para D2, pero cierra la
   pregunta de si el wheel trae un FFmpeg completo o recortado.
4. **Rendimiento del pipeline:** 42,69 s de audio transcritos en 15,32 s de reloj = **2,8× tiempo real**
   con `small`/int8 en CPU [M]. *(Convención de este documento: "×  tiempo real" = duración del audio ÷
   tiempo de proceso. Más alto es mejor.)*
5. **La misma cadena funcionó sobre un archivo bajado de YouTube** con yt-dlp: contenedor abierto por PyAV,
   audio transcrito, `ffmpeg` reconfirmado ausente.

**La premisa central del ADR se sostiene con evidencia.** Ya no es "confianza alta": es un hecho fechado.

### 3.2 Lo que el spike refutó, y la corrección

La versión anterior de este ADR afirmaba: *"en YouTube esos formatos [audio-only] existen y son
directamente descargables"*. **Eso no se sostuvo en la prueba** [O, 2026-08-10, sin cookies, en la red del
dueño]:

- La extracción por defecto falló con *"Sign in to confirm you're not a bot"* — el bloqueo anti-bot que
  YouTube aplica hoy a peticiones no autenticadas.
- Se probaron **doce `player_client`** distintos sobre **tres vídeos públicos**. Todos fallaron salvo
  **`android`**, y `android` expuso **un único formato**: `itag 18`, `.mp4`, AAC + H.264, **360p ya
  muxeado**. En ninguno de los tres apareció un formato audio-only.
- El selector `bestaudio[abr<=128]/bestaudio/best` **cayó correctamente en `best`** y descargó ese `.mp4`
  de **629 172 bytes para 19 s de vídeo [M]** (~266 kbps de contenedor completo).

**Qué se sostiene y qué no:**

| | |
|---|---|
| **Se sostiene, y es lo importante** | **Nunca se invocó un postprocesador ni una fusión.** `postprocessors=[]` fue real, el archivo lo abrió PyAV sin ffmpeg y se transcribió bien. **La invariante de D2 no se rompió en ningún momento.** El `/best` de reserva de D3 ya cubría este caso: no hace falta cambiar el selector |
| **No se sostiene** | Que "descargar solo audio" sea lo normal en YouTube. Hoy, sin cookies, **no lo es** |

**La afirmación optimista que hay que retirar, y su corrección.** Este ADR decía que `abr<=128` "ahorra
descarga sin coste de calidad". Es cierto **solo cuando existe una pista de audio suelta**. Cuando cae un
muxeado, se descargan también los bytes del vídeo: en el ejemplo medido, ~266 kbps frente a los ~50-130
kbps [E] que habría pesado el audio solo — del orden de **2 a 5 veces más bytes**. Extrapolado, una hora de
vídeo rondaría los **120 MB** [E, derivado del punto medido], muy por debajo del tope de 2 GiB, que sigue
siendo la salvaguarda correcta. **El filtro se mantiene** —cuando la plataforma sí ofrece audio suelto,
funciona— pero **no se vende como ahorro garantizado**.

**Consecuencia de diseño, y es la parte que el código debe respetar:** "solo cayó un formato muxeado" es
**flujo normal**. `fetch.py` devuelve un indicador `has_video` y la cáscara lo comenta como dato, no como
problema. **Jamás se emite `download_failed` ni `no_audio_stream` por ese motivo**; `no_audio_stream` se
reserva a que el medio **de verdad** no tenga pista de audio.

**Y una lectura que conviene guardar:** el riesgo de §9 ("yt-dlp es una dependencia viva") se manifestó de
una forma que este ADR no había anticipado. No fue que yt-dlp se rompiera por un cambio de API, sino que
**el catálogo de formatos accesibles sin cookies se redujo a uno solo, y ese uno viene muxeado**. Es una
observación con fecha [O], no una propiedad del diseño: mañana puede haber tres formatos o ninguno.

### 3.3 La grieta que sigue abierta

Hay fuentes que **solo** sirven HLS (`.m3u8`) — X/Twitter y parte de Facebook. Ahí yt-dlp usa su
descargador HLS nativo, que concatena fragmentos sin ffmpeg (`hls_prefer_native`), y el resultado es un
MPEG-TS o un fMP4 concatenado que **PyAV normalmente decodifica, pero "normalmente" no es "siempre"**.
**No se probó en el spike (S7 sigue abierto).** Si falla, el código es `decode_failed` y el usuario ve que
ese enlace no se puede leer. **No se resuelve metiendo ffmpeg.**

---

## 4. Patrón de arranque: A vs B vs C

**Resuelto: B (ventana propia con pywebview). Confirmado por medición [M]:** pywebview `6.2.1` instaló
limpio en Python 3.11.9, arrastró exactamente lo previsto y **abrió una ventana real**, con la advertencia
que se convirtió en D25.

### 4.1 Las tres candidatas

| | A — Web local | B — Ventana propia (pywebview) | C — Ejecutable C# (tipo MDViewer) |
|---|---|---|---|
| Piezas | `http.server` + puerto + token + navegador + consola | pywebview + WebView2 + consola | `.exe` C# + WebView2 + **subproceso Python** + IPC + `build.ps1` |
| Precedente en el repo | BrandAssets, Mermaid | ninguno (sería el **sexto patrón**) | MDViewer |
| Dependencias nuevas | **0** (biblioteca estándar) | **~8 MB [M]** (`pythonnet`, `clr_loader`, `cffi`, `pycparser`, `bottle`, `proxy_tools`) | 0 en pip, pero DLL versionadas + cadena de compilación |
| Diálogo de archivo | **No da la ruta**: el navegador no expone la ruta absoluta | **Nativo, devuelve la ruta absoluta** | Nativo (`OpenFileDialog`, `src/MDViewer.cs:627`) |
| Archivo de 800 MB | hay que **subirlo por HTTP** (copia en disco) o pegar la ruta | se pasa **la ruta**, cero copias | se pasa la ruta, cero copias |
| Cerrar = terminar | no: cerrar la pestaña deja el servidor vivo; cerrar la consola mata la transcripción en silencio | **sí, un gesto** | sí |
| Runtimes en la carpeta | 1 (Python) | 1 (Python) | **2 (Python + .NET)** |

Nota medida: la pila de pywebview pesó **~8 MB [M]**, por debajo de los 10-20 MB que este ADR estimaba —
**el 1 % del total de la herramienta**. El argumento de "no añadir dependencias" tenía todavía menos peso
del que se le dio.

### 4.2 Por qué se descartó C

MDViewer se compila en C# porque así **no necesita Python en absoluto**
(`apps/MDViewer/README.md:108`). Voice2Text **necesita Python de todas formas**: el motor es
faster-whisper y yt-dlp. C no elimina un runtime, **añade uno**, más una segunda cadena de build y un
protocolo de líneas JSON en `stdout` para llevar el progreso de Python a C#. Con la regla de la casa —*el
usuario tiene que poder abrir el archivo y entenderlo*— eso significa entender dos lenguajes. Descartado.

### 4.3 El punto que decidió entre A y B

La tarea nuclear es *"cargar un vídeo o audio local"*, y ahí A tiene un defecto estructural: **el navegador
no da la ruta del archivo** (`File.path` no existe en la plataforma web; la File System Access API tampoco
la expone). Con A solo hay dos salidas: **subir los bytes por HTTP** —duplicando en disco un archivo de
cientos de MB— o **pedir que se pegue la ruta**. En B es `create_file_dialog()`, ruta absoluta, cero
copias.

Contra los cuatro criterios: (1) **copiable**: B añade ~8 MB [M] y exige WebView2, supuesto que el repo ya
hizo con MDViewer (`apps/MDViewer/README.md:106`); (2) **proceso de minutos**: gana B, cerrar la ventana
termina el trabajo en un gesto; (3) **piezas móviles**: gana B en conceptos aunque pierda en paquetes;
(4) **legibilidad**: gana B, ~40 líneas de cáscara frente a ~250 de fontanería HTTP.

**A sigue siendo el plan B literal** si algún día la pila de pywebview da problemas en otra máquina; volver
cuesta un archivo (D11).

### 4.4 El precio de compartir WebView2 con MDViewer (D25)

El spike encontró un fallo que no estaba en ninguna lista de riesgos: **con el perfil por defecto de
WebView2, la ventana no abrió** (`E_ABORT`, 0x80004004) en una máquina donde el runtime **sí** estaba
instalado (`151.0.4129.72`) y la sesión era interactiva. Se resolvió fijando un `storage_path` propio.

La causa probable es que **BSTools ya tiene otra herramienta usando WebView2 en la misma máquina**
(MDViewer), y heredar su carpeta de datos de usuario rompe el arranque. De ahí D25, y de ahí una regla que
va más allá de esta herramienta: **toda herramienta de BSTools que use WebView2 debe poseer su propio
perfil.** Se anota aquí porque es exactamente el tipo de interacción entre carpetas "autocontenidas" que la
regla de oro no cubre: las carpetas están aisladas, el estado de WebView2 en `%LOCALAPPDATA%` no.

### 4.5 El modo servidor no reabre esto

El servidor **se levanta y se apaga a mano** (D24). Si la ventana dependiera de él, abrir la ventana
obligaría a mantener un servidor vivo, que es el ciclo de vida que el dueño descartó. Por tanto: **la
ventana ejecuta el núcleo en su propio proceso**, `--serve` es un **segundo modo de arranque explícito**, y
las dos son **cáscaras hermanas** (D11) y **excluyentes** (D21).

Además, y conviene dejarlo escrito para que nadie lo "optimice": el transporte de una interfaz de usuario y
una API para máquinas **no deben ser el mismo código**. Fusionarlos ata el contrato público a los caprichos
de la pantalla.

**Consecuencia documental:** `spec/constitution/tech-stack.md` gana un **sexto patrón de arranque**
("ventana propia en Python") y `spec/guides/guia-nueva-herramienta.md` su plantilla, en el cierre de la
herramienta.

---

## 5. El núcleo como producto

### 5.1 Qué corrigió el requisito de consumo externo

Cinco cosas que este ADR daba por buenas dejaron de valer:

| Lo que estaba escrito | Por qué ya no vale | Corrección |
|---|---|---|
| El error llevaba `message` y `hint` **en castellano** dentro del objeto | Un bot redacta sus propios mensajes y puede hablar otro idioma | **D10**: `code` + `details`; la traducción, en la cáscara |
| El estado llevaba `phase_detail: "12:03 de 28:45"`, ya formateado | Formatear es presentación; un bot querrá "45 %" | **D10**: el estado lleva números; quien lo enseña, lo formatea |
| Dos capas: motor y cáscara | Falso desacople: mezclaba el motor con la cola de trabajos | **D11**: tres capas |
| El motor podía apoyarse en ajustes globales | Un fichero leído al importar impide dos configuraciones en un proceso | **D13**: configuración inyectada |
| "Un trabajo a la vez; el segundo se rechaza" | Un bot recibe tres notas de voz seguidas | **D14**: cola FIFO |

Dos reglas derivadas, verificables leyendo el código: el motor **no imprime** (usa `logging`) y **no lee
configuración**.

### 5.2 El contrato: la misma forma en proceso y por HTTP

| Operación | En proceso (bot en Python) | Por HTTP (`--serve`) |
|---|---|---|
| encolar | `job_id = jobs.submit(request)` | `POST /api/v1/jobs` → `202 {job_id}` |
| consultar | `jobs.get(job_id, since=n)` | `GET /api/v1/jobs/{job_id}?since=n` |
| cancelar | `jobs.cancel(job_id)` | `POST /api/v1/jobs/{job_id}/cancel` |
| recoger | `jobs.get(...).result` | `GET /api/v1/jobs/{job_id}` |

Es deliberado que **no** exista `transcribe_and_wait()`: invita a bloquear un hilo doce minutos y es lo que
rompe a los consumidores. Quien quiera esperar, sondea.

**Solo cruzan la frontera datos serializables.** Las llamadas de vuelta de progreso (`on_segment`,
`should_cancel`) son **internas** entre motor y orquestación y **no** forman parte del contrato público.
Firmas exactas en [`ARCHITECTURE.md`](../../apps/Voice2Text/ARCHITECTURE.md) §3 y §4.

### 5.3 Alcance de red: un solo futuro, y por qué basta

**El bot corre en la máquina del usuario**, y eso es lo que hace viable todo lo demás: **un bot de Telegram
que use `getUpdates` (*long polling*) solo necesita salida HTTPS hacia `api.telegram.org`. No necesita que
nadie lo alcance desde fuera.** Vive en el PC del usuario, habla con Telegram hacia fuera y llama a
`http://127.0.0.1:8317/api/v1/…` hacia dentro. **Cero puertos abiertos, cero TLS, cero autenticación de
internet.** Con *webhooks* en lugar de *long polling* ya no estaríamos en este escenario.

**Fuera de alcance por decisión del dueño: el bot alojado en la nube.** No se invierte más. Si algún día se
quisiera, la garantía es concreta: el **motor viaja intacto** y se reescribirían la orquestación (cola
persistente, concurrencia, cuotas) y la cáscara.

### 5.4 Modo servidor: arranque manual, en primer plano (D18, D24)

**No hay servicio, no hay tarea programada, no hay entrada en el arranque de Windows. No hay ninguna
desviación de la constitución que justificar.**

```
apps/Voice2Text/Voice2Text-Servidor.cmd     ->  py -3 serve.py [--port 8317]
```

Cinco propiedades deliberadas: **(1)** encendido o apagado sin tercer estado — si la consola existe, está
vivo; **(2)** se apaga cerrando la ventana o con `Ctrl+C`, cancelando el trabajo en curso y purgando
`work/`; **(3)** **puerto fijo `8317`, configurable** — si está ocupado, mensaje y salida, nunca otro
puerto en silencio; **(4)** **token** por arranque en `serve-token.txt`, exigido en **todas** las
peticiones, incluida `/health`; **(5)** prefijo **`/api/v1/`** desde el primer día.

| Endpoint | Qué hace |
|---|---|
| `GET /api/v1/health` | versión del núcleo y de la API, versión y antigüedad de yt-dlp, modelos instalados, si el modelo está cargado |
| `GET /api/v1/models` | catálogo: `model_id`, `expected_bytes`, instalado o no, si supera el techo |
| `POST /api/v1/models/{model_id}/download` | `202 {job_id}` |
| `DELETE /api/v1/models/{model_id}` | libera disco, devuelve bytes liberados |
| `POST /api/v1/jobs` | encola → `202 {job_id, queue_position}` |
| `GET /api/v1/jobs/{job_id}?since=N` | estado + segmentos nuevos desde `N` |
| `POST /api/v1/jobs/{job_id}/cancel` | cancelación cooperativa |
| `GET /api/v1/jobs/{job_id}/result?format=txt\|md` | el texto compuesto, sin escribir en disco |
| `DELETE /api/v1/jobs/{job_id}` | olvida el trabajo y borra sus temporales |

Errores: `{"error": {"code": "…", "details": {…}}}`, **sin texto de pantalla**. HTTP: `202` encolado ·
`400` inválida · `403` token · `404` desconocido · `413` grande · `429` `queue_full` · `507` `disk_full` ·
`500` interno. **No existe `409` de "ocupado"**: con cola FIFO, estar ocupado no es un error.

**Por qué se construye ahora aunque el bot no exista:** es **la prueba de falsación de D11**. Si escribir
la segunda cáscara obliga a tocar `transcribe.py`, `fetch.py`, `export.py` o `models.py`, el desacople era
decorativo. Cuesta ~150 líneas sobre `http.server` y compra una certeza que ninguna revisión de código da.

**Expresamente fuera:** autenticación por usuario, TLS, escucha fuera de loopback (**prohibida por D19**),
persistencia entre reinicios, cuotas por cliente, subida por HTTP (en la misma máquina se pasa la **ruta**),
*webhooks* y multiusuario.

### 5.5 Exclusividad: nunca dos modelos en RAM (D21)

Dos procesos con `small` cargado son ~2 GB de RSS [E] y **dos transcripciones sobre la misma CPU no van más
rápido, van más lento**. Un **cerrojo exclusivo de archivo** (`runtime.lock`) —que el sistema operativo
libera al morir el proceso, aunque muera a lo bruto— garantiza un único proceso vivo; junto a él,
`runtime.json` con `mode`, `pid`, `port` y `started_at` para poder decir **qué** está corriendo.

**Nunca un fallo mudo:** abrir la ventana con el servidor arriba muestra un diálogo que dice qué hay
corriendo y cómo apagarlo, y la ventana no llega a abrirse; lanzar `--serve` con la ventana abierta imprime
lo equivalente y sale con código de error.

**Alternativa descartada: que la ventana se conectara al servidor como cliente.** Elegante sobre el papel,
muere contra D24: obligaría a que abrir la ventana levantase o exigiese un servidor. La variante de dos
caminos en el cliente duplica código para un caso raro.

### 5.6 Cola, espera y RAM (D14, D22)

**Un trabajo en ejecución, los demás en cola FIFO**, hasta `max_queued_jobs` (8); pasado ese punto,
`queue_full`. **Sin prioridades**, y esa es la simplificación que regala D21: como ventana y servidor no
coexisten, no hay dos clases de cliente que ordenar.

Quien espera ve `{"state":"queued","queue_position":2,"estimated_wait_seconds":340}` — el mismo campo del
mismo estado para la ventana y para el bot. `estimated_wait_seconds` suma lo que va por delante usando el
`speed_ratio` del último trabajo completado, y es `null` mientras no haya ninguno. Cancelar algo **en cola**
es instantáneo; cancelar lo que está **en ejecución** tarda lo que tarde la ventana en curso del modelo
(hasta ~30 s [E]).

**El modelo en RAM (D22).** Se carga al primer trabajo, se mantiene mientras haya cola y se suelta tras
`model_idle_timeout_seconds` (300 s) sin trabajos, liberando ~1 GB [E]. El siguiente trabajo paga la
recarga (~3-10 s [E], S13). En un trabajo de minutos es ruido; en un servidor levantado toda la tarde, es
1 GB que el usuario recupera sin apagarlo.

---

## 6. Modelo por defecto: los datos

Decidido: **`small`**, con la cláusula condicional de D5. **`compute_type="int8"` cuantiza al cargar, en
memoria — lo que se descarga sigue siendo el modelo en float16.** Elegir int8 ahorra RAM y tiempo, no
descarga.

| `model_id` | Parámetros | Descarga | RSS del proceso | Velocidad en CPU | Español / inglés | Catálogo |
|---|---:|---:|---:|---|---|---|
| `base` | 74 M | ~145 MB [E] | ~0,5 GB [E] | ~8-12× [E] | justo; falla en nombres y cifras | sí, opción ligera |
| **`small`** | 244 M | **464 MB [M]** | ~1 GB [E] | **2,8× [M]** (clip de 42,7 s) | **primera utilizable de verdad** | **sí — por defecto** |
| `medium` | 769 M | ~1,53 GB [E] | ~1,8 GB [E] | ~1-1,5× [E] | notablemente mejor, lenta | 🚫 **candidato a por defecto en ADR-0002** |
| `large-v3-turbo` | 809 M | ~1,6 GB fp16 · ~0,9 GB int8 pre-cuantizado [E] | ~1,9 GB [E] | ~0,7-1,5× [E] en CPU | la mejor relación calidad/tamaño | 🚫 **candidato a por defecto en ADR-0002** |
| `tiny` | 39 M | ~75 MB [E] | ~0,4 GB [E] | ~12-20× [E] | texto que hay que reescribir | **no** — solo pruebas |
| `*.en` | — | — | — | — | **solo inglés** | **no** — D5 |

**Aviso honesto sobre esta columna de velocidad.** Este ADR estimaba `small` en **4-7×** y el único punto
medido dio **2,8×** [M]: la estimación nació **entre 1,5 y 2× optimista**. Las demás filas siguen siendo
estimaciones y **se han reescalado a la baja con ese factor**, pero siguen sin medir: **trátense como cota
superior**. Dos matices que juegan a favor: el clip medido eran 42,7 s, y en audios largos los costes fijos
se amortizan [E]; y la medición se hizo con el proceso compitiendo con el resto de la máquina.

Traducido a lo que verá el usuario, con `small`: **10 minutos de audio ≈ 3,5-4 minutos** [E, derivado del
punto medido]. La versión anterior de este documento decía "1,5-2,5 min" y **eso era falso**.

**Por qué se descartan los `.en`.** Son mejores en inglés, pero obligarían a elegir modelo **antes** de
saber el idioma del audio, o a tener dos descargados (+629 MB [E]). Con dos idiomas objetivo, el
multilingüe con **detección automática** es lo único que no le pide al usuario que adivine. Consecuencia:
`language` va a `null` por defecto, la interfaz **muestra el idioma detectado con su probabilidad**, y hay
selector manual `es`/`en`. **La detección automática no se probó en el spike** (se forzó el idioma en todas
las corridas): S11 sigue abierto.

**Aviso sobre `large-v3-turbo`:** su fama de "8× más rápido" viene de GPU y de recortar el decodificador a
4 capas. **Su codificador sigue siendo el de `large-v3`**, y en CPU el codificador es quien manda.

---

## 7. Peso de la instalación: medido (D20)

**Medición del 2026-08-10 [M]**, venv desechable con `faster-whisper` + `yt-dlp` + `pywebview` (patrón B
completo), borrado tras medir.

| Pieza | Medido [M] | Lo que estimaba este ADR | Desvío |
|---|---:|---:|---|
| `av` + `av.libs` (PyAV) | **67,5 MB** | 35-45 MB | subestimado −50 % |
| `ctranslate2` | **60 MB** | 60-150 MB | acertado |
| `numpy` + `numpy.libs` | **58 MB** | ~50 MB | acertado |
| `onnxruntime` | **45 MB** | ~25 MB | subestimado −45 % |
| `yt_dlp` | **26 MB** | ~15 MB | subestimado |
| `hf_xet` + `tokenizers` + `huggingface_hub` | **24 MB** | ~15 MB | `hf_xet` no estaba en la cuenta |
| `pip` + `setuptools` + `pkg_resources` | **~22 MB** | no contado | overhead del venv, **no del proyecto** |
| Pila `pywebview` completa | **~8 MB** | 10-20 MB | sobrestimado |
| **Venv completo** | **331 MB** | 220-330 MB (subtotal de wheels) | **~309 MB descontando el overhead del venv: dentro del rango, cerca del techo** |
| **Modelo `small`** | **464 MB** | ~484 MB | **−4 %, dentro del ±5 % declarado** |
| **TOTAL en régimen** | **~795 MB** | 0,70-0,81 GB | **dentro del rango. Techo: 1 GB. Margen: ~205 MB** |

> 🚫 **EN CUARENTENA (2026-08-10).** Aquí había una **regla pre-comprometida por tramos** (≤ 0,9 GB /
> 0,9-1,0 GB / > 1,0 GB) que decidía el modelo por defecto según el peso **total** de la instalación.
> **Muere entera**: el presupuesto de 1 GB era del **modelo**, no de la instalación, y sobre el total el
> dueño pide **transparencia, no límite**.
>
> **Lo que la sustituye, y sigue siendo obligatorio:** medir el peso total, publicarlo con cifras en el
> README (primera pantalla) y en la pantalla de primer arranque, y marcar cada cifra con su origen. **Lo
> que desaparece:** que ese número decida nada. El presupuesto que sí manda —el del modelo— se fija en
> ADR-0002.

Nota metodológica: el venv aísla, pero **en producción se instala con `pip` global** (patrón de la casa),
así que parte de esos 331 MB puede estar ya en la máquina del usuario — `numpy` es el candidato típico. El
número real que verá cada usuario está **entre ~250 y ~330 MB de wheels** [E], según lo que ya tuviera.

**La postura, sin maquillaje.** ~795 MB: bajo el techo, pero con diferencia la herramienta más pesada de
BSTools (las DLL de MDViewer son unos pocos MB). Se acepta porque (1) la alternativa obvia —
`openai-whisper` con PyTorch — pesa 2,5-3,5 GB [E], **~4× más**; (2) **el 58 % del peso es el modelo**:
fuera del repositorio, borrable, y el usuario elige su tamaño; (3) la regla que la constitución de verdad
protege —"nada de instaladores binarios ni servicios en segundo plano"— se cumple entera, D24 incluido.
**No se puede afirmar que esta herramienta sea ligera**, y el README lo dice en la primera pantalla con
esta cifra medida.

---

## 8. Licencias (y su encaje con CC0)

| Componente | Licencia | ¿Fricción con CC0? |
|---|---|---|
| `faster-whisper` | MIT | No |
| `CTranslate2` | MIT | No |
| `PyAV` | BSD-3-Clause | No |
| **FFmpeg embebido en el wheel de PyAV** | **LGPL 2.1+** | No para nosotros — ver abajo |
| `yt-dlp` | **Unlicense** (dominio público) | No |
| `onnxruntime` | MIT | No |
| `pywebview` | BSD-3-Clause | No |
| `pythonnet`, `clr_loader`, `cffi`, `pycparser`, `bottle`, `proxy_tools` | MIT / BSD / MIT | No |
| Runtime de Intel dentro de los wheels de CTranslate2 | oneDNN Apache-2.0 · MKL licencia propia de Intel | No para nosotros — ver abajo |
| **Pesos del modelo Whisper** (OpenAI) | MIT | No |
| Código propio de Voice2Text | **CC0 1.0** | — |

**Ninguna fricción**, y la razón importa: todas son permisivas y, sobre todo, **no redistribuimos ninguna**.
El repositorio contiene solo `requirements.txt`; los binarios los baja pip de PyPI. Las obligaciones de la
LGPL (FFmpeg) y de la licencia de Intel (MKL) recaen en quien redistribuye, y ese es PyPI.

**Regla dura: prohibido vendorizar wheels o binarios de estas dependencias dentro del repositorio.**
Meterlos convertiría a BSTools en redistribuidor de binarios LGPL y de MKL dentro de un repositorio que se
anuncia como CC0 íntegro. Mismo motivo, reforzado, para D4.

Contraste con MDViewer, que **sí** versiona las DLL de WebView2 (BSD-3 de Microsoft,
`apps/MDViewer/README.md:130`): allí es permisiva y son unos pocos MB. Aquí serían cientos de MB y una
LGPL. No es el mismo caso.

El README lleva sección **"Terceros"** con esta tabla, como ya hace MDViewer.

---

## 9. Riesgo: yt-dlp es una dependencia viva

**El choque es real y ya se manifestó en el spike.** La regla de oro dice "copia la carpeta y funcionará".
**Para los enlaces, esa promesa es falsa**, y el README debe decirlo con estas palabras:

> **La transcripción de archivos locales funciona para siempre.** La descarga desde enlaces depende de
> `yt-dlp`, que persigue cambios continuos de YouTube, TikTok, X y Facebook: **es normal que un enlace deje
> de funcionar y se arregle actualizando `yt-dlp`**. No es un fallo de esta herramienta.

**Tres síntomas, no uno.** El spike aportó el tercero, que este ADR no había anticipado:

1. **El extractor deja de entender la página** → `extractor_outdated`. Se arregla actualizando.
2. **La plataforma exige sesión** → `login_required`. **No se arregla**: D6 lo prohíbe por diseño.
3. **El catálogo de formatos accesibles sin cookies se reduce, o se queda en un único formato ya
   muxeado** [O, medido el 2026-08-10 en YouTube]. **Esto NO es un error y el código no debe tratarlo como
   tal**: se descarga el muxeado, se transcribe igual de bien y se informa de que se bajaron más bytes de
   los necesarios. Convertir esto en `download_failed` sería el bug.

Cinco medidas:

1. **Cortafuegos arquitectónico (D7).** El fallo de yt-dlp **no puede** tocar la ruta de archivos locales.
2. **Nunca fijar la versión.** `yt-dlp>=<fecha>` **sin techo**, e `install.ps1` con `--upgrade`.
3. **Detector de caducidad gratis.** La versión de yt-dlp **es una fecha**: la antigüedad se calcula **sin
   tocar la red**. Pasados **60 días**, aviso no bloqueante con el comando exacto. *(La versión resuelta en
   el spike, `2026.7.4`, tenía 37 días [M]: dentro del umbral.)*
4. **Los `player_client` en datos, no en código (D26).** El spike tuvo que probar **doce** para encontrar
   uno que funcionara [M]; el que hoy funciona (`android`) puede dejar de hacerlo mañana [O]. Que viva en
   `settings.json` permite arreglarlo editando un valor, sin esperar a una versión de la herramienta.
5. **Expectativas honestas por plataforma en el README:** YouTube funciona hoy **con formato muxeado**;
   TikTok suele funcionar; **X y Facebook fallan a menudo**. Eso **no** se arreglará: es consecuencia
   directa de D6.

---

## 10. Errores: el contrato de honestidad

Tabla completa (código, datos, detección, y el texto castellano **de la cáscara**) en
[`ARCHITECTURE.md`](../../apps/Voice2Text/ARCHITECTURE.md) §5. La regla: toda excepción se traduce a un
**código de una tabla cerrada** antes de salir del núcleo (D10); ninguna se propaga en crudo.

Códigos: `unsupported_url`, `login_required`, `geo_blocked`, `media_unavailable`, `download_failed`,
`extractor_outdated`, `no_audio_stream`, `decode_failed`, `file_too_large`, `file_not_found`,
`model_missing`, `model_download_failed`, `disk_full`, `queue_full`, `cancelled`, `internal`.

**Fragilidad declarada:** `login_required`, `geo_blocked` y `media_unavailable` se distinguen **buscando
subcadenas en el mensaje de yt-dlp**. Es frágil y cambia con las versiones — el spike lo vio de primera
mano con *"Sign in to confirm you're not a bot"*, que hay que clasificar como `login_required` y no como
`download_failed`. Los cubos por defecto (`extractor_outdated`, `internal`) nunca pueden quedar sin un texto
comprensible.

---

## 11. Términos de servicio de las plataformas

Los términos de YouTube prohíben descargar contenido salvo por los medios que la propia plataforma ofrece.
**Esta herramienta no puede prometer que su uso sea conforme, y no lo va a hacer.**

Lo defendible, y sale directo de D6: **la herramienta nunca se autentica.** Sin cookies, sin cuentas, sin
sesiones. Solo pide lo que un visitante anónimo puede pedir. Si el contenido exige iniciar sesión, **se
detiene y lo dice** en lugar de rodear el control de acceso — que es exactamente lo que ocurrió en el spike
al toparse con el bloqueo anti-bot: se paró. Eso la mantiene lejos de la "elusión de una medida técnica de
protección". **Es una invariante de diseño: añadir cookies exigiría un ADR nuevo.**

El README lleva sección **"Uso responsable"**: pensada para **material propio o con permiso**; **solo
contenido público, sin iniciar sesión**; el uso de descargas puede **contravenir los términos** y la
responsabilidad es de quien la usa; esto **no es asesoramiento legal**; y CC0 libera **el código**, no el
contenido que cada uno transcriba.

---

## 12. Alternativas descartadas

| Alternativa | Por qué no |
|---|---|
| **whisper.cpp** | Sería **más ligera** (un binario de pocos MB + modelo GGUF) y hay que reconocerlo. Se descarta porque el coste se traslada a nosotros: habría que **compilar y versionar un `.exe` por variante de CPU**, y este repo no tiene cadena de C++ — MDViewer funciona porque `csc.exe` viene con Windows, cosa que no pasa con MSVC. Además yt-dlp obliga a tener Python igualmente. |
| **API en la nube** (OpenAI, Deepgram, AssemblyAI) | Rompe la promesa de "**nada sale de tu equipo**" que BrandAssets ya hace por escrito. Exige una API key, y las claves viven fuera del repo por política. ~0,006 USD/min ≈ **0,36 USD por hora** [P, tarifa publicada por el proveedor]. Deja de funcionar sin internet. |
| **Exigir `ffmpeg` instalado** | Obliga a una instalación manual fuera de la carpeta: **rompe la regla de oro**. Meterlo en el repo son ~80-150 MB [E] de binario con GPL/LGPL a cuestas. **Y el spike demuestra que no hace ninguna falta** (§3.1). |
| **`openai-whisper` + PyTorch** | 🚫 **Justificación reescrita: el argumento del techo se evaporó** con la premisa corregida, y con GPU sobre la mesa PyTorch deja de ser absurdo. **Se rechaza igual, por mérito y no por peso:** CTranslate2 es sensiblemente más rápido en CPU con el mismo modelo, es lo que ya está medido y funcionando en el spike [M], y su ruta de GPU no exige arrastrar el runtime entero de PyTorch. Confirmar en ADR-0002 con las cifras de GPU delante. |
| **Vosk** | Modelos de ~50 MB [E], tentador por peso. Calidad en español muy inferior y **sin puntuación ni mayúsculas**: el texto hay que reescribirlo. |
| **`distil-whisper`** y **modelos `.en`** | Solo inglés, o mejores solo en inglés a cambio de elegir modelo antes de conocer el idioma del audio. |
| **Cliente puro** (todo en el navegador) | Imposible: hay que ejecutar un modelo de 464 MB y escribir en disco. Es el escenario contra el que avisa `tech-stack.md` desde la migración de Mermaid. |
| **La ventana como cliente HTTP del modo servidor** | Muere contra D24 (arranque manual): obligaría a que abrir la ventana levantase o exigiese un servidor. |
| **Servicio en segundo plano o tarea programada** | Prohibido por la constitución, **y ni siquiera hace falta**: el dueño quiere levantarlo y bajarlo a mano (D24). |
| **Prioridades entre ventana y bot en la cola** | Problema inexistente: D21 impide que coexistan. FIFO es la única política que un humano predice. |
| **Fijar `player_client: ["android"]` en el código** | Es lo que funciona hoy [O, 2026-08-10] y por eso mismo **no puede vivir en un `.py`**: caduca. Va a `settings.json` como lista ordenada (D26). |

---

## 13. Consecuencias

**Lo que se gana**

- Transcripción **local, gratuita e ilimitada**, sin cuentas ni claves, sin que el audio salga del equipo —
  **demostrado punta a punta en el spike**, incluido un vídeo bajado de YouTube.
- Cero requisitos manuales fuera de `pip`.
- Un **motor reutilizable** y una segunda cáscara (lote 6) que lo demuestra en vez de prometerlo.
- Un `.md` con marcas de tiempo que encaja con la vocación del repo de preparar material para LLMs.

**Costes aceptados**

| Coste | Mitigación |
|---|---|
| **~795 MB instalados [M]** con `small` en CPU, y **subirá** con el modelo y la GPU que decida ADR-0002 | 🚫 Ya no es un límite: es una **obligación de transparencia**. Cifra medida en el README (primera pantalla) y en el primer arranque |
| **~3,5-4 min de CPU por cada 10 min de audio** con `small` [E, derivado de 2,8× medido] — y **más** con un modelo mayor | 🚫 La cláusula que bajaba a `base` queda **suspendida**: la prioridad es la calidad. La palanca correcta pasa a ser la **GPU**, no un modelo peor. Se decide en ADR-0002 |
| **El bot solo responde con el servidor levantado** (D24) | Es el trato, aceptado por el dueño; va al README con esas palabras |
| No se pueden usar ventana y servidor a la vez (D21) | Mensaje claro en ambos sentidos; nunca dos modelos en RAM |
| **En YouTube sin cookies se descarga vídeo+audio, no solo audio** [O] | Se transcribe igual; son ~2-5× más bytes [E], muy por debajo del tope de 2 GiB. Se informa, no se falla (§3.2) |
| Primer arranque: 464 MB de descarga | Pantalla explícita con tamaño, destino, disco libre y progreso real |
| Los enlaces **no** funcionan para siempre (§9) | Cortafuegos D7, `player_client` en datos (D26), detector de caducidad, error que enseña la cura |
| X y Facebook fallarán a menudo | Consecuencia de D6; límite permanente documentado |
| **BSTools pasa a tener dos herramientas usando WebView2 en la misma máquina** | D25: cada una posee su propio `storage_path`. Es una interacción entre carpetas "autocontenidas" que la regla de oro no cubre y conviene recordar en la próxima herramienta que use WebView2 |
| Recarga del modelo tras 5 min de inactividad (D22) | ~3-10 s [E] frente a ~1 GB de RAM recuperado; configurable y desactivable |
| Whisper alucina texto repetido en silencios y música | `vad_filter=True` por defecto; límite conocido en el README |
| Detección automática de idioma **sin probar** | S11 en ejecución desde el 2026-08-10; hay selector manual `es`/`en` |
| Tres capas en vez de dos | Se paga una vez; el lote 6 comprueba que sirvieron |
| `pip` global ensucia el Python del usuario | Patrón de la casa; `uninstall.ps1` documenta el `pip uninstall` exacto |

---

## 14. Estado de verificación de los supuestos

**Spike ejecutado el 2026-08-10.** Informe: `apps/Voice2Text/SPIKE-RESULTS.md`.

| # | Supuesto | Estado | Qué salió |
|---|---|---|---|
| **S1** | Transcribir un `.mp4` sin ffmpeg en el `PATH` | **VERDE [M]** | PyAV abrió el contenedor y faster-whisper transcribió, con `ffmpeg` confirmado ausente antes y después. **La premisa central deja de ser un supuesto** |
| **S2** | Peso real de los wheels | **CERRADO [M]** | 331 MB de venv (~309 MB de proyecto). Dentro del rango; no dispara ninguna escalada |
| **S5** | CTranslate2 libera el GIL | **VERDE [M]** | 19,84 de 20 tics/s durante la transcripción. D9 confirmado, sin necesidad de subprocesos |
| **S6** | yt-dlp descarga solo audio sin postprocesado | **ÁMBAR [M/O]** | El mecanismo funciona (cero postprocesado, cero ffmpeg); **la promesa de "solo audio" no se cumple hoy en YouTube sin cookies**. Corregido en §3.2 y D3 |
| **S8** | pywebview instala limpio y abre ventana | **VERDE [M]** | `6.2.1`, ~8 MB, ventana real. Advertencia convertida en **D25** (`storage_path` propio) |
| **S9** | Sin *redistributable* de Visual C++ ausente | **PARCIAL [M]** | Instaló y ejecutó en la máquina del dueño. **Sin probar en máquina limpia**; si aparece, se documenta en Problemas comunes |
| **S10** | Tamaño del modelo ±5 % | **CERRADO [M]** | 464 MB frente a 484 estimados: −4 % |
| **S3** | Velocidad con **10 min de audio en español**, en el modelo y el dispositivo que decida ADR-0002 | **ABIERTO, reencuadrado** | El spike midió **2,8× sobre 42,7 s en inglés** con `small` en CPU [M]. 🚫 **Ya no dispara nada**: la cláusula condicional está suspendida. Sigue siendo la verificación **V1** del lote 1, pero ahora su función es **informar la estimación que ve el usuario**, no elegir el modelo |
| **S4** | Progreso de descarga del modelo | **ABIERTO** | El modelo se descargó, pero no se probó cómo reportar su progreso. Plan B ya escrito: sondear el tamaño de `models/` |
| **S7** | Un enlace de X con HLS produce algo que PyAV lee | **ABIERTO** | No se probó. Si falla → `decode_failed` y se documenta. **No se resuelve con ffmpeg** |
| **S11** | Detección **automática** de idioma en español e inglés | **DESBLOQUEADO (2026-08-10), en ejecución** | Las corridas del spike forzaron el idioma. El dueño instaló `Microsoft Sabina Desktop` (`es-MX`), **verificada visible para SAPI** con `GetInstalledVoices()`. Entrega en `VERIF-ESPANOL.md`. **La voz sintética vale para idioma y velocidad, NO para calidad de texto** (ADR-0002 §10) |
| **S12** | El cerrojo exclusivo de archivo no deja fantasmas | **ABIERTO** | Se verifica en el lote 2 |
| **S13** | Soltar el modelo libera la memoria nativa; coste de recarga | **ABIERTO** | Se verifica en el lote 2. Si no libera, **D22 se retira** y el modelo se queda cargado mientras viva el proceso |
| **V2** | Los huecos entre segmentos con **`vad_filter=True`** (nuestra configuración real) | **CERRADO [M], 2026-08-10** | **No se reconstruyen solos.** Con 4 silencios construidos por muestra exacta (3,5/6,0/1,0/4,3 s), el hueco medido entre `end` y el `start` siguiente fue **0,000 s en los cuatro casos**, igual que con `vad_filter=False`. El VAD remapea los tiempos al medio original, pero **no libera el `end` de su estiramiento** hasta el `start` siguiente. `word_timestamps` **sigue haciendo falta** |
| **V3** | Sobrecoste de `word_timestamps=True`, mismo clip con y sin | **CERRADO [M], 2026-08-10** | **Muy por debajo de lo esperado: dentro del ruido de medición, ~0 %.** Ronda 1 (clip real 300 s, 2 corridas por config): −5,5 %. Ronda 2 (clip real 120 s, 4 corridas por config, intercaladas): False 81,22 s vs True 81,21 s de media → **−0,0 %**. La horquilla de +10-30 % [E] **no se cumplió, en sentido favorable** — contradice la propia advertencia de calibración de Kronos (que apuntaba a que sus estimaciones salen optimistas, no pesimistas). No se activa la cláusula de ajuste por perfil |
| **V4** | ¿El **`start`** del segmento posterior a un silencio marca el inicio real del habla? | **CERRADO [M], 2026-08-10** | **Sí, dentro de ~30 ms**, en las cuatro posiciones de silencio probadas (después de 3,5/6,0/1,0/4,3 s): `start` observado 7,650/19,140/25,880/36,860 s vs. ground truth por construcción 7,679/19,162/25,911/36,869 s. Las marcas de tiempo del `.md` **son fiables**: el riesgo grave que abría esta verificación no se materializó |

**Ningún hallazgo bloquea la construcción.** Lo único con consecuencia sobre una decisión es S3, y su
consecuencia ya está escrita y pre-autorizada en D5.

---

## 15. Decisiones del dueño

- **Modelo:** `small` por defecto, con la cláusula condicional de D5. **Techo: 1 GB**, cumplido con ~795 MB
  medidos. `medium` y `large-v3-turbo` disponibles marcados. Idiomas **español e inglés**, sin `.en`.
- **Patrón:** **B, ventana propia con pywebview** — condición S8 **cumplida y medida**.
- **Consumo externo:** el núcleo es la API (D17). El bot correrá **en la misma máquina**; el escenario en la
  nube queda **fuera de alcance**.
- **Ciclo de vida:** modo servidor **manual, explícito y en primer plano** (D18, D24). Sin servicios, sin
  tareas programadas, sin autoarranque. **Sin desviación de la constitución.**
- **Concurrencia:** ventana y servidor **excluyentes** (D21); dentro de un proceso, **cola FIFO** sin
  prioridades (D14); modelo descargado de RAM tras 5 min (D22).

---

## 16. Estado

**Parcialmente derogado** (2026-08-10, mismo día de su aceptación), por una **corrección de premisa del
dueño**, no por un cambio de opinión: el límite de 1 GB se transmitió como techo de la instalación y era
el **presupuesto del modelo**.

- **Vigente y construible:** D1-D4, D6-D19, D21-D26 y las secciones §3, §5, §8-§11. Los lotes de
  `ARCHITECTURE.md` §13 siguen siendo el plan.
- **En cuarentena:** D5, D20, la regla por tramos de §7 y la cláusula condicional V1 — inventario completo
  en el aviso de cabecera.
- **La cláusula condicional de D5 queda SUSPENDIDA y no puede dispararse.** Se pre-autorizó para degradar
  el modelo si la velocidad no llegaba; con la calidad como prioridad declarada, eso es exactamente lo
  contrario de lo que el dueño quiere.

**Instrumento de corrección: ADR-0002**, que decidirá **en una sola decisión** el modelo por defecto y la
política de GPU (§17), cuando entreguen las cifras del spike de GPU. Se sigue respetando *append-only*: no
se reescribe ninguna decisión aquí, se marca lo muerto y se decide en el documento nuevo.

---

## 17. Nota para ADR-0002: dos perfiles de hardware, no uno

Se deja escrito antes de ver las cifras, para que los números se juzguen contra un criterio y no al revés.

### 17.1 El dato que lo reencuadra todo: hay dos máquinas

La máquina actual **es la de desarrollo**. El destino declarado por el dueño es otra:

| | **Perfil DEV** (hoy) | **Perfil PROD** (destino) | **Perfil CPU** (terceros) |
|---|---|---|---|
| GPU | GTX 1050 Ti, 4 GB | **RTX 3080, 10 GB GDDR6X** | ninguna |
| Arquitectura | Pascal, cómputo **6.1** | Ampere, cómputo **8.6** | — |
| `float16` | **no viable** (CT2 exige ≥ 7.0) [E] | **viable, y es la ruta natural** | no aplica |
| VRAM útil | ~3-3,5 GB tras el escritorio [E] | ~9 GB [E] | — |
| Papel | **peor caso y prueba de degradación** | **el objetivo real** | el que se publica en un repo CC0 |

**Consecuencia inmediata, y hay que decirla así para que nadie la malinterprete: las cifras del spike son
del perfil DEV, que es el peor caso.** No son "el rendimiento de Voice2Text". Por eso las marcas de este
documento pasan a ser **[M-dev]** y **[M-prod]**: una cifra medida sin perfil se lee como *el* rendimiento,
y sería mentira en las dos máquinas. **Hoy no existe ninguna cifra [M-prod].**

Y una consecuencia que va más allá del proyecto: BSTools es un repositorio **público CC0**. El README **no
puede** decir "tarda 3 minutos", porque quien lo descargue no tiene ninguna de las dos máquinas. Tiene que
publicar una **tabla por perfil**. Los dos perfiles conviven en la documentación; no se sustituyen.

### 17.2 La decisión es de cuatro dimensiones, no de dos

Lo que este ADR llamaba "modelo y GPU son una sola decisión" se queda corto. Es
**modelo × dispositivo × `compute_type` × perfil de hardware**, y las cuatro se atan entre sí:
`large-v3-turbo` recorta el decodificador a 4 capas pero **conserva el codificador de `large-v3`** — lo
caro en CPU, lo barato en GPU.

**Matriz de recomendación de partida** (todo [E] hasta que el spike de GPU la contraste):

| Perfil detectado | Modelo sugerido | `compute_type` | VRAM estimada | Por qué |
|---|---|---|---|---|
| **CPU sola** | `medium` o `small` | `int8` | — | Depende de la rama del techo (§17.4) |
| **DEV** (cc 6.1, 4 GB) | `large-v3-turbo` | **`int8`** (no hay otra) | ~1,5 GB | fp16 no soportado; turbo mueve el decodificador barato |
| **PROD** (cc 8.6, 10 GB) | **`large-v3` completo** | **`float16`** | ~4 GB | Caben 3,1 GB de pesos con holgura en 10 GB, y fp16 **no pierde calidad por cuantización** |

**La regla que ata la matriz a la prioridad declarada del dueño ("calidad de texto"), y que conviene
escribir porque es la que zanja las discusiones futuras: no se cuantiza más de lo que el hardware
obligue.** En PROD eso significa `float16`, no `int8`, aunque int8 fuera más rápido: la prioridad es
calidad. En DEV, `int8` es el único camino y la pérdida se acepta porque es la máquina de pruebas.

### 17.3 Cerrado: el artefacto que se descarga

**fp16 canónico (`Systran/faster-whisper-*`) y cuantizar al cargar. Decidido, no vuelve a discutirse.**

Con una Ampere de destino ya no hay dilema: un repositorio **int8 pre-cuantizado de terceros cerraría la
puerta a `float16` justo en la máquina buena**, además de ser menos canónico. Un solo artefacto en
`models/` sirve para CPU, para DEV y para PROD, porque **la cuantización ocurre al cargar**. Coste
aceptado: la descarga es mayor (`turbo` 1,6 GB en vez de ~0,9 GB), y eso alimenta la pregunta de §17.4.

### 17.4 CERRADO por el dueño: rama B, y el techo muere del todo

**Respuesta recibida el 2026-08-10. No quedan preguntas de dirección abiertas.**

1. **Rama B — "lo mejor que quepa por máquina".** `large-v3` completo (~3,1 GB en fp16) en la RTX 3080; el
   mejor viable en la 1050 Ti; el mejor viable sin GPU. **El catálogo recomendado se calcula por perfil de
   hardware: no hay un ganador único.**
2. **El techo de ~1 GB era ORIENTATIVO, no un límite** — ni de descarga ni de memoria. Literal del dueño:
   *"Ninguno, era orientativo"*. **Muere como restricción de diseño en todas partes**, igual que murió
   D20, y con él mueren los campos que lo representaban en el código (`over_model_budget`,
   `model_budget_bytes`: ver `ARCHITECTURE.md` §3). **Dejar un parámetro que ya nadie hace cumplir es
   peor que quitarlo: invita a que alguien lo vuelva a aplicar.**
3. **Criterio de desempate definitivo y único: CALIDAD DE TEXTO.** Velocidad después. Peso, al final.

**Lo que ocupa el lugar del techo: la obligación de transparencia.** El usuario tiene que saber, **antes
de que ocurra y siempre**, **dos** números y no uno: **cuánto se va a descargar** y **cuánto va a ocupar
al ejecutarse** (RAM o VRAM). Antes bastaba con el primero porque el segundo era pequeño; con `large-v3`
son ~3,1 GB de descarga y ~4 GB de VRAM [E], y callar el segundo sería engañar por omisión.

#### El filtro de viabilidad, que "calidad primero" necesita para no ser una trampa

**Aplicar "calidad primero, velocidad después" como un orden puramente lexicográfico recomendaría
`large-v3` en un portátil sin GPU**, donde 10 minutos de audio tardarían del orden de **30-50 minutos**
[E, extrapolado del único punto medido]. Eso no es una recomendación: es una emboscada, y encima en un
repositorio público que descargará gente con hardware que no conocemos.

Por eso `recommend_profile()` hace **dos pasos, en este orden**:

1. **Filtro de viabilidad** — un candidato entra solo si (a) cabe en la VRAM libre con margen, en caso de
   GPU; y (b) su `speed_ratio` estimado supera un suelo configurable, `min_viable_speed_ratio`, **1,0 por
   defecto**: nunca se *recomienda* algo más lento que el tiempo real.
2. **Orden por calidad** entre los que pasaron, y solo a igualdad de calidad, por velocidad; y a igualdad
   de ambas, por peso.

**El filtro solo gobierna la recomendación, no la libertad del usuario:** quien quiera `large-v3` en su
CPU y esperar 45 minutos puede elegirlo a mano, viendo la estimación. Lo que no puede pasar es que se lo
encuentre preseleccionado sin haberlo pedido.

#### Por qué `recommend_profile()` y `resolve_device()` siguen siendo dos funciones — y no se toca

Esta decisión **refuerza** la separación, y se deja escrito aquí para que nadie la "simplifique" dentro de
seis meses:

> Con modelos de **3,1 GB** sobre la mesa, si `resolve_device()` pudiera resolver también el modelo,
> **encolar una transcripción podría disparar una descarga de 3 GB que el usuario nunca aceptó.** El
> modelo es una decisión de **descarga**, del usuario, una vez y con consentimiento explícito (D4). El
> dispositivo y el `compute_type` son una decisión de **ejecución**, automática, por trabajo y sin
> consecuencias en disco. **Fusionarlas es el desastre, no la simplificación.**

#### La consecuencia incómoda: la misma herramienta da textos distintos

Con un modelo por perfil, **el mismo audio produce texto distinto según la máquina donde corra** — y
también según el `compute_type`, porque `int8` y `float16` no calculan igual. Para el dueño es aceptable y
está aceptado. Para un repositorio **público CC0** hay que **declararlo en el README**, no descubrirlo:

- La herramienta **no garantiza salida reproducible entre máquinas**. Depende del modelo, del dispositivo
  y de la precisión, y las tres se eligen solas según el hardware.
- Por eso **cada `.md` lleva en su cabecera con qué se hizo** (`Modelo: large-v3 (float16, GPU)`): es el
  rastro que explica una diferencia sin tener que depurar nada.
- Y por eso **ninguna prueba compara salidas por igualdad exacta**, sino con tolerancia
  (`ARCHITECTURE.md` §14).
- **Ninguna cifra de velocidad, ni en el README ni en la pantalla**, puede aparecer sin decir en qué
  hardware se midió: `[M-dev]` / `[M-prod]`, o "sin medir".

#### Y el número que nadie ha dicho todavía: la instalación de PROD ronda los 5-6 GB

Es la consecuencia aritmética directa de la rama B, y la obligación de transparencia empieza por decirla
aquí: ~309 MB de wheels [M-dev] + **3,1 GB** de `large-v3` + **1,5-2,5 GB** de librerías CUDA [E] =
**~5-6 GB**. Frente a los ~795 MB [M-dev] de la configuración por defecto en CPU.

Eso choca de frente con *"nada de dependencias de gigabytes"* de la constitución, y hay que resolverlo
con una regla explícita, no mirando a otro lado:

> **La instalación por defecto —CPU, sin GPU, modelo modesto— se mantiene en el orden de los ~800 MB. La
> configuración de 5-6 GB es un camino OPCIONAL que el usuario construye a propósito**, instalando el
> paquete de GPU y eligiendo un modelo mayor, **con los dos números delante en cada paso**. La regla de la
> constitución protege a quien clona el repositorio, y a ese no se le impone nada.

ADR-0002 debe confirmar esta lectura al fijar el catálogo: **el modelo por defecto de una instalación
recién clonada sin GPU no puede ser `large-v3`**.

### 17.5 Lo que ADR-0002 tiene que resolver además

1. **Umbral de justificación de la GPU, fijado ANTES de mirar el resultado:** el camino GPU compensa su
   coste (~1,5-2,5 GB de librerías CUDA [E], instalador aparte, matriz de soporte) si entrega **≥ 3×
   sobre CPU con el mismo modelo**, o si hace viable un modelo que en CPU no lo sería. **Matiz que añade
   el perfil PROD:** aunque el spike en DEV devuelva 1,5× y no justifique publicar el instalador *para
   Pascal*, en PROD la respuesta será otra — la decisión de publicar puede quedar **condicionada a la
   capacidad de cómputo detectada**, no ser un sí/no global.
2. **Predicción a contrastar [E, no verificada]:** CTranslate2 exige **≥ 7.0 para `float16`** y **≥ 6.1
   para `int8`** (DP4A). Si acierto, en DEV la única ruta es `int8` y la pata "float16" del spike fallará.
   **En el código esto no se codifica como tabla**: se pregunta a
   `ctranslate2.get_supported_compute_types(...)` (`ARCHITECTURE.md` §3). Una tabla de capacidades escrita
   a mano caduca igual que la lista de `player_client` (D26).
3. **`min_vram_mb` es por (modelo, `compute_type`)**, no por modelo: `large-v3` son ~4 GB en fp16 y ~2,5 GB
   en int8 [E]. Sin ese desglose, `resolve_device()` no puede decidir en una tarjeta de 4 GB.
4. **Pascal está en cuenta atrás [O]**, pero **ya no es un argumento de peso**: la máquina de destino es
   Ampere. Lo que sí sigue en pie es que **la instalación base se queda en CPU**, porque el repositorio es
   público y la mayoría de quien lo descargue no tendrá ninguna GPU.

**Lo que NO hay que reabrir en ADR-0002:** la elección de faster-whisper (D1), la invariante sin ffmpeg
(D2-D3, medida), las tres capas (D11), el modo servidor (D18-D19, D23-D24), la exclusividad (D21) ni la
postura sin cookies (D6). Nada de eso dependía del techo ni del hardware.

### 17.6 El riesgo de migrar: fallos que solo aparecen en la máquina buena

Si se desarrolla en DEV y el destino es PROD, hay una clase de fallo que **por construcción no puede
aparecer durante el desarrollo**:

1. **La rama `float16` no se ejecuta ni una sola vez** en DEV: es código muerto hasta el día de la
   migración.
2. **La política de VRAM nunca se ejercita con 10 GB**: los umbrales y el margen de holgura solo se han
   visto decir "no cabe".
3. **`get_supported_compute_types()` devuelve otro conjunto** y se toma otra rama.
4. **`large-v3` no se descarga ni se ejecuta nunca** en DEV: su `min_vram_mb`, su tiempo de carga y su
   comportamiento en memoria están sin ver.
5. **El texto de salida cambia legítimamente** entre `int8` y `float16`: cualquier prueba de salida
   idéntica escrita en DEV fallará en PROD **por un motivo correcto**, que es la peor clase de falso
   positivo.

**Cómo se verifica sin exigir la 3080 para desarrollar** — y esto es lo que justifica que `probe_devices()`
y `resolve_device()` sean **dos funciones y no una**:

- **(a) La política es una función pura de `DeviceCapabilities`.** `resolve_device()` no toca hardware:
  recibe capacidades y devuelve una decisión. Eso permite **probar la política entera con capacidades
  sintéticas** — fabricar la `DeviceCapabilities` de una 3080 (cc 8.6, 10 240 MB,
  `["float16","int8_float16","int8","float32"]`) en la máquina de desarrollo y comprobar que resuelve
  `large-v3` + `float16`. Cubre los riesgos 1, 2 y 3 **al nivel de la decisión**, que es donde vive la
  lógica. Tabla de casos en `ARCHITECTURE.md` §14.
- **(b) Lo que NO se puede simular, y hay que decirlo:** la **ejecución** real en `float16` exige hardware
  ≥ 7.0. No hay truco. Lo que se verifica en DEV es que se **llega** a la rama y que el fallo, si lo
  hubiera, se maneja; que el cálculo dé el resultado correcto solo se sabe en PROD.
- **(c) Un `--self-check` escrito ANTES de migrar**, que es lo que convierte "esperemos que funcione" en
  diez segundos: imprime las `DeviceCapabilities` reales, la `DeviceChoice` resuelta, transcribe el clip
  sintético y compara con la referencia. **Un comando, no un procedimiento.**
- **(d) Cada salida dice con qué se hizo.** La cabecera del `.md` ya lleva `Modelo: small (int8, CPU)`. Si
  el rendimiento cambia, se sabe por qué sin depurar nada.
- **(e) Criterio de aceptación de la migración:** PROD no se da por bueno hasta que el `--self-check` pasa,
  `device_used.compute_type == "float16"`, y **V1 se remide en PROD**. Las cifras del README **se
  reetiquetan por perfil, no se sustituyen**.

Plan de construcción por lotes y criterios de aceptación:
[`ARCHITECTURE.md`](../../apps/Voice2Text/ARCHITECTURE.md) §13.
