# Verificación final independiente — Voice2Text v1.0

**Auditor:** Véritas (QA), papel de auditor externo — no construí nada de lo verificado aquí.
**HEAD auditado:** `b48e9e9` ("pegar un enlace produce texto (lote 11)").
**Fecha:** 2026-08-10. **Máquina:** en reposo antes de empezar (`tasklist`/`wmic cpu` en 4% de carga,
cero `python.exe` compitiendo). No se midió rendimiento (fuera de encargo).
**Material de prueba:** generado por mí con `System.Speech.Synthesis` (voz `Sabina Desktop`, es-MX) y
un `.mp4` sin audio construido con PyAV, todo en `scratchpad` fuera del repo. **No toqué
`test/uvlVg3c2fCxBzKVk.*`** (el material de otro agente que ya estaba en `test/`).

---

## BLUF

**Los seis recorridos pedidos funcionan de punta a punta.** No encontré ningún fallo que
rompa un flujo completo, ni ninguna promesa del README que sea falsa. Encontré **una brecha
real y no documentada como tal**: la ruta API (la que usará el bot) **no valida "archivo sin
pista de audio" antes de encolar** — sí lo hace la ventana, no el servidor — y **un dato del
catálogo desactualizado que infla las estimaciones de espera en cola en CPU** en más de un 30%.
Ninguna de las dos rompe el uso; ambas están honestamente marcadas como pendientes en el propio
plan de `ARCHITECTURE.md` (lote 9, "siguiente"), así que no es una mentira — es trabajo
declarado y no cerrado. **Mi veredicto: v1.0 es usable hoy, con dos matices que el dueño debe
conocer antes de conectar el bot de Telegram** (ver §7).

---

## 1. Archivo local → texto (CLI)

**VERDE.** `py -3 cli.py prueba.wav --language es` sobre un WAV sintético de 13s (voz real
SAPI, cifras y nombre propio incluidos): modelo cargado, transcripción correcta ("2.400 euros",
"12 de agosto" bien reconocidos), `.txt` y `.md` escritos con metadatos completos.
Repetido con un segundo WAV con una pausa de 3.5s deliberada: el corte de párrafo se activó
correctamente y **los saltos de línea del `.txt` son CRLF de verdad** (`\r\n\r\n` entre
párrafos, verificado byte a byte) — el README no exagera en eso.

## 2. Enlace público → texto

**VERDE.** `py -3 cli.py "https://www.youtube.com/watch?v=jNQXAC9IVRw"` (el primer vídeo de
YouTube, 19s, público): descargó, transcribió en inglés, y **los archivos de salida se
llamaron `Me at the zoo.txt` / `Me at the zoo.md`** — título real, no un ID temporal. Cumple
exactamente lo que pediste comprobar.

Bonus no pedido: un enlace de **Facebook público** (un vídeo antiguo sin restricción) también
funcionó de punta a punta, con nota correcta de "esa plataforma no ofrece audio suelto, se
descargó video+audio" — comportamiento documentado en el README, no un error disfrazado.

## 3. API HTTP (la vía del bot)

**VERDE, con un matiz de contrato (ver más abajo).** Arranqué `serve.py --port 8317`, y:

- **Sin token → 403.** Token equivocado → 403. **Token como `?token=` en la URL → 403** (el
  servidor de verdad solo acepta la cabecera `X-Token`, tal como promete el README:
  *"nunca en la URL"*).
- Token correcto por cabecera → `GET /health` responde con `api_version`, `core_version`,
  estado de `yt_dlp`, modelos instalados.
- `POST /jobs` con `{"source": {"kind": "file", "path": ...}, "options": {"model_id": "small",
  "language": "es"}}` → `202` con `job_id` y `queue_position`.
- Sondeo por `GET /jobs/{id}` hasta `state: done` (dos sondeos, ~3s).
- `GET /jobs/{id}/result?format=txt` y `?format=md` devuelven el texto correcto, con el mismo
  contenido que produjo la CLI sobre el mismo archivo.
- El nombre de salida respetó la regla de no-sobrescritura: como ya existía `prueba.txt` de la
  prueba §1, el job de la API escribió `prueba (2).txt` / `prueba (2).md` — confirmado en dos
  vías distintas (CLI y API) sin que nadie lo pisara.

**Matiz de contrato que el bot debe conocer y el README no menciona:** `POST /jobs` **exige
`options.model_id`** — si se omite (como sugiere el ejemplo del README, que solo muestra
`"options": {...}` sin decir qué es obligatorio), la API responde `400 bad_request` con
`"options.model_id es obligatorio"`. No es un bug — es una validación real y razonable — pero
**quien conecte un bot leyendo solo el README se va a topar con este 400 a la primera**, porque
el ejemplo no lo advierte. Sugerencia: una línea en el README listando los campos obligatorios
de `options`.

## 4. Exclusividad

**VERDE, en las dos direcciones.** Con el servidor corriendo en el puerto 8317:

- Un segundo `serve.py` en otro puerto se niega con mensaje claro (código de salida 1):
  *"Ya hay un servidor escuchando en el puerto 8317 (PID ..., desde ...). Cierra esa ventana o
  pulsa Ctrl+C ahí para apagarlo."* Nunca carga un segundo modelo.
- Probé también la dirección cruzada: con la **ventana** (`app.py`) abierta, un intento de
  `serve.py` se niega igual, distinguiendo el mensaje ("Hay una ventana abierta... Ciérrala
  para poder usar el modo servidor").
- **Recuperación de cerrojo fantasma, probada de verdad:** maté el proceso del servidor a la
  fuerza (`taskkill /F`, simulando un cierre anómalo) dejando `runtime.lock`/`runtime.json`
  con un PID muerto. El siguiente arranque **detectó que el PID ya no existe y arrancó limpio**
  — no se quedó bloqueado por un cerrojo fantasma. Esto no estaba explícitamente en tu lista,
  pero es exactamente el escenario que un bot en producción puede disparar (un corte de luz, un
  `kill -9`), y responde bien.

**NO VERIFICADO — apagado con Ctrl+C real.** No conseguí, desde este entorno de automatización,
enviar una señal `CTRL_C_EVENT` real a la consola del servidor (el proceso no está adjunto a un
terminal interactivo controlable desde aquí; `taskkill` sin `/F` lo rechaza explícitamente:
*"This process can only be terminated forcefully"*). Leí el código de `_graceful_shutdown()` y
la estructura `try/finally` alrededor de `serve_forever()` — parece correcta (cancela el
trabajo en curso, espera hasta 35s, purga `work/` entero) — **pero no vi esa ruta ejecutarse en
vivo**. Es una declaración de límite del entorno, no un hallazgo negativo: lo marco NO
VERIFICADO en vez de darlo por bueno.

## 5. Errores honestos

Probé los cinco casos pedidos y uno extra:

| Caso | Resultado | Mensaje |
|---|---|---|
| Archivo inexistente (CLI) | `ERROR [file_not_found] ...` | Código + detalles, sin traceback |
| Archivo inexistente (API) | Rechazado **al encolar** (`400`, síncrono) | Confirma la promesa de `jobs.py`: nunca espera a cargar el modelo para este caso |
| Archivo sin pista de audio (CLI y `.mp4` sin audio construido por mí) | `ERROR [no_audio_stream] ...` tras cargar el modelo (~3s en GPU) | Ver hallazgo abajo |
| Archivo sin pista de audio (**API**) | `202` (encolado), y solo falla **después**, ya en `running` | **Hallazgo, ver §7.1** |
| Enlace no soportado (`https://www.google.com`) | `ERROR [unsupported_url] ...` | Correcto |
| Enlace roto (`https://example.com/no-existe`) | `ERROR [media_unavailable] ...` | Correcto |
| Enlace de X sin vídeo | `ERROR [extractor_outdated] ...` | Correcto (yt-dlp no encontró vídeo en ese tuit, mapeo razonable) |
| Enlace de X/Facebook que exige sesión | **NO VERIFICADO en vivo** | Ver nota |

Ninguno de los casos reales produjo un stack trace de Python — siempre `codigo + detalles`
estructurados. **Para la ventana**, revisé `messages.py::_ERROR_TEMPLATES` y confirmé que
**todos** los códigos que disparé en mis pruebas (`file_not_found`, `no_audio_stream`,
`unsupported_url`, `media_unavailable`, `extractor_outdated`) tienen texto en español,
comprensible y con una acción concreta (botón "Elegir otro archivo", "Reintentar", etc.) — la
ventana no expone el código crudo al usuario final, solo la API lo hace (por diseño explícito
del contrato: *"el texto es trabajo de quien consuma la API"*, `serve.py` línea 33).

**NO VERIFICADO — un enlace real de X/Facebook que exija sesión.** No encontré, dentro de un
esfuerzo razonable de búsqueda a ciegas (sin navegador), una URL pública que reprodujera
`login_required` en vivo — los intentos que hice contra X devolvieron otros códigos (sin vídeo,
o `extractor_outdated`) según el contenido, no por exigir sesión. Sí verifiqué directamente la
función que clasifica el mensaje de error de `yt-dlp` (`fetch._classify_download_error`) con
frases reales del estilo que yt-dlp emite para vídeos privados/con restricción de edad
(`"Sign in to confirm your age"`, `"Private video. Sign in if..."`) y ambas se clasifican
correctamente como `login_required`. Es una verificación de unidad, no del recorrido completo
en vivo — lo declaro así en vez de darlo por bueno.

## 6. El README, contrastado con lo real

Revisé cada afirmación concreta del README contra el código y la ejecución real:

| Afirmación del README | Contrastada con | Resultado |
|---|---|---|
| Token nunca viaja en la URL, solo cabecera `X-Token` | Prueba HTTP directa | **Cierto** |
| `.txt` en CRLF | Lectura de bytes del archivo | **Cierto** |
| No sobrescribe en silencio, usa `(2)` | Dos escrituras sobre el mismo nombre (CLI + API) | **Cierto** |
| Aviso de `yt-dlp` con más de 60 días sin actualizar | `settings.py: "ytdlp_stale_days": 60` + `app.py` lo aplica | **Cierto** (el umbral es real, no decorativo) |
| Pesos del catálogo (145 MB / 464 MB / 1,5 GB / 1,6 GB / 3,1 GB) | `catalog.py::expected_bytes` | **Cierto**, calculado byte a byte |
| El instalador de GPU "termina ejecutando la prueba de humo real" | `install-gpu.ps1` llama a `cli.py --self-check` al final | **Cierto** |
| "Pedir GPU no la garantiza… cae a CPU y avisa" | Ya verificado en sesiones anteriores (memoria del proyecto), no repetido hoy | Confío en la verificación previa, no la repetí (no era el encargo de hoy) |
| Peso de instalación base "~795 MB" (330 MB deps + 464 MB modelo) | — | **NO VERIFICADO.** No reinstalé desde cero (hubiera arriesgado desestabilizar el entorno de la máquina compartida). El componente del modelo (464 MB) sí lo confirmé; el de las dependencias (330 MB), no |
| Complemento GPU "~2 GB más" | — | **NO VERIFICADO**, mismo motivo (no soy quien debe desinstalar/reinstalar CUDA en la máquina del dueño sin permiso explícito) |
| Apertura visual de la ventana, WebView2 renderizando `ui.html` | Lancé `app.py` dos veces: el proceso arrancó sin excepción ni traceback en consola, tomó el cerrojo (`runtime.json` con `mode: "window"`), y un segundo intento de servidor lo detectó correctamente | **PARCIAL.** Confirmo que el proceso no revienta al arrancar y que el cerrojo funciona; **NO VERIFICADO** que la ventana realmente se vea y sea usable (no tengo acceso visual en este entorno) |
| "Cerrar la ventana termina el trabajo en curso, en un solo gesto" | — | **NO VERIFICADO** (requiere interacción gráfica) |

**No encontré ninguna promesa del README que resultara falsa.** Las dos zonas marcadas "no
verificado" lo están porque de verdad no pude probarlas desde este entorno — no porque
sospeche de ellas.

## 7. Hallazgos que sí importan

### 7.1 La ruta API no valida "sin audio" antes de encolar (la ventana sí)

`app.py::probe_media()` existe y la ventana lo llama **antes** de dejar pulsar "Transcribir"
(confirmado en `ui.html::adoptFile`): un archivo sin pista de audio nunca llega a cargar un
modelo en la ventana. **`jobs.py::submit_transcription()` no hace ese mismo chequeo** — solo
comprueba que el archivo exista. Repetí el archivo sin audio contra la API real: `POST /jobs`
devolvió `202` (aceptado), y el trabajo pasó a `running` y cargó el modelo **antes** de fallar
con `no_audio_stream`. Para el caso que probé (modelo `small` ya en caché de GPU) costó ~3
segundos desperdiciados; en un servidor recién arrancado, con un modelo mayor o en CPU, el
costo real sería mayor. **Esto es justo lo que el propio `ARCHITECTURE.md` (§13, lote 9,
estado "siguiente") dice que falta**: *"un fichero sin audio falla al encolar, no tras cargar
el modelo"*. No es una sorpresa oculta — está en el propio plan como pendiente — pero como el
encargo de hoy destacó la API como **la vía que usará el bot**, quiero que quede explícito:
**hoy esa promesa solo se cumple en la ventana, no en la API.**

### 7.2 El catálogo de velocidades sigue con el número viejo (ya lo sabe `ARCHITECTURE.md`)

`catalog.py`: `"small": speed_ratio={"cpu_int8": 1.15, ...}`. Las mediciones limpias de hoy
(español 1,725×, inglés 1,534×, ambas sin contención de CPU, documentadas en
`VERIF-ESPANOL.md` y en mi memoria de sesión) están **muy por encima** de ese 1,15 — el
catálogo sigue reflejando la cifra vieja del spike, no la remedición. Esto no es cosmético:
`jobs.py::_estimate_wait_locked()` usa exactamente ese número para calcular
`estimated_wait_seconds` de los trabajos en cola detrás de otro. Un bot que muestre "tiempo de
espera estimado" a un usuario en CPU va a ver una cifra **~35-50% más pesimista** que la
realidad. Igual que el punto anterior: `ARCHITECTURE.md` ya marca esta corrección como
pendiente (lote 9, "siguiente"), así que no es una mentira — es trabajo declarado y no cerrado
que vale la pena priorizar antes de anunciar tiempos de espera a usuarios reales del bot.

### 7.3 El plan de `ARCHITECTURE.md` §13 está desalineado con lo que el repo ya tiene

La tabla de lotes marca el **lote 10** ("`/health` con estado real del dispositivo") como
**"pendiente"**, pero el commit `f9b2a44` ("el estado vivo refleja el dispositivo real, no la
intención") ya está en `HEAD` y mi propia memoria de sesiones anteriores confirma que se probó
con dos repros reales de `JobManager`. La tabla no refleja el estado real del repo. No afecta
al funcionamiento —es un documento interno de planificación, no una promesa al usuario— pero sí
puede confundir a quien la use para decidir qué falta.

### 7.4 Diferencia menor de formato entre el `.md` de la CLI y el de la API

El campo "Transcrito" del `.md` sale como `2026-08-10 11:36` (CLI) vs `2026-08-10T16:37:38Z`
(API, formato ISO con hora UTC) para el mismo tipo de trabajo. No es un error — ambos son
fechas válidas y legibles— pero es una inconsistencia cosmética entre las dos cáscaras que
generan el "mismo" documento. Menor, no bloqueante.

---

## 8. Veredicto

**Sí, esto se puede considerar una v1.0 usable**, con dos condiciones que le pondría al dueño
antes de conectar el bot de Telegram a producción sin supervisión:

1. **Que el bot maneje bien un `error.code: "no_audio_stream"` que llega tarde** (después de
   `202`), en vez de asumir que un `202` significa "archivo válido". Hoy es así; arreglarlo es
   exactamente lo que el lote 9 del propio plan ya tiene anotado.
2. **Que no se muestre `estimated_wait_seconds` como una cifra confiable al usuario final del
   bot todavía** — está sistemáticamente sesgada al alza en CPU hasta que se corrija el
   catálogo.

Ninguno de los dos rompe un recorrido completo (los seis que pediste verificar, funcionan). Los
dos están honestamente declarados como pendientes en la documentación interna del propio
proyecto — mi trabajo hoy fue confirmar que **son reales, medibles y con impacto concreto en el
caso de uso que más te importa (el bot)**, no solo notas en un ADR.

**Lo que dejo sin verificar, por límites del entorno, no por sospecha:** el apagado con
Ctrl+C real del servidor, el peso exacto de la instalación base y del complemento GPU, la
apertura visual de la ventana y su interacción, y un caso real en vivo de enlace de X/Facebook
que exija sesión (sí verificado a nivel de función).
