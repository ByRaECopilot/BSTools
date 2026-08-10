---
title: "Spike tecnico — validacion de supuestos S1/S5/S6/S8 de ADR-0001"
status: completado
fecha: 2026-08-10
---

# Spike tecnico — Voice2Text

Verifica con medidas reales, no con supuestos, los cuatro riesgos mas altos de
[`ADR-0001`](../../spec/decisions/ADR-0001-voice2text-stack.md) (seccion 13: S1, S5, S6, S8), mas la
medicion de peso de la seccion 6. No se ha escrito codigo de produccion: todo corrio en un venv desechable
fuera del repo, borrado al terminar.

**Maquina:** Windows 10 Pro, Python 3.11.9. **ffmpeg confirmado fuera del PATH** antes de empezar
(`where ffmpeg` -> `INFO: Could not find files for the given pattern(s).`, exit code 1) y vuelto a
confirmar despues de instalar cada paquete y despues de cada transcripcion, para que ningun resultado
verde sea un falso verde por contaminacion del entorno.

**Entorno:** `python -m venv C:\Users\<usuario>\AppData\Local\Temp\v2t-spike`, fuera del repo y fuera del
Python global. Al terminar se borro entero y se midio su peso antes de borrarlo (seccion "Peso real").

---

## Veredicto en una tabla

| # | Supuesto | Veredicto |
|---|---|---|
| S1 | Transcribir un `.mp4` sin ffmpeg en el PATH | **VERDE** |
| S6 | yt-dlp descarga solo audio sin postprocesado | **AMARILLO / matizado** — el mecanismo (sin ffmpeg, sin postprocesadores) funciona, pero hoy, en esta red, sin cookies, YouTube no entrego una pista de audio-only para los videos probados: solo un stream ya muxeado (video+audio) en resolucion baja |
| S8 | pywebview instala limpio y abre una ventana real | **VERDE**, con una advertencia operativa (ver detalle) |
| S5 | La transcripcion libera el GIL | **VERDE** |
| Peso | Wheels + modelo `small` frente a la estimacion del ADR (~220-330 MB + 484 MB) | **Wheels: ligeramente por encima del techo estimado (331 MB con B incluido). Modelo: acierta (464 MB medidos vs 484 MB estimados, -4%)** |

---

## S1 (bloqueante) — transcribir sin ffmpeg en el sistema

**Comando exacto:**

```
py -3 -m venv v2t-spike
v2t-spike\Scripts\python.exe -m pip install faster-whisper
```

**Generacion del audio de prueba sintetico** (regla de la constitucion: entrada de prueba sintetica; sin
anadir ninguna dependencia nueva de Python). Se resolvio con dos piezas que ya estan en la maquina o en el
venv, ninguna nueva:

1. **Voz real**, no un tono: `System.Speech.Synthesis` de .NET, invocado desde PowerShell (viene con
   Windows, no es una dependencia del proyecto), genero un `.wav` de ~42.6 s leyendo un parrafo en ingles
   con la voz "Microsoft David Desktop" (unica voz instalada en esta maquina — **no hay voz en espanol
   instalada aqui**, ver limitacion abajo).
2. **Contenedor `.mp4` con pista de video trivial**, construido con **PyAV puro** (ya es dependencia de
   faster-whisper): se decodifico el `.wav` con `av.open(...)`, se genero video sintetico cuadro a cuadro
   con `numpy` (color que cambia, para que no sea un frame estatico) codificado con `libx264` — confirmado
   que el wheel de PyAV trae `libx264` y `aac` embebidos (`av.codec.Codec("libx264","w")` no lanza
   excepcion) — y se muxo todo con `container.mux(...)`. Resultado: `synthetic_test.mp4`, 42.63 s, stream
   de video `h264` + audio `aac`, contenedor `mov,mp4,m4a,3gp,3g2,mj2`. Todo el proceso de creacion del
   archivo de prueba paso por PyAV, nunca por un binario `ffmpeg`.

**Limitacion honesta:** no hay voz SAPI en espanol instalada en esta maquina, asi que el audio hablado es
ingles, no espanol. Esto **no afecta la conclusion mecanica de S1** (¿decodifica PyAV el contenedor sin
ffmpeg? ¿transcribe faster-whisper?), que es lo que S1 pide verificar. Si afecta la calidad linguistica
cuando se fuerza `language="es"` sobre audio en ingles (ver abajo). Para separar ambas cosas se corrio la
transcripcion dos veces: una tal como pide la spec (`language="es"`) y otra de control con
`language="en"` para confirmar que el pipeline decodifica y transcribe correctamente cuando el idioma
declarado coincide con el audio.

**Transcripcion, comando exacto:**

```python
model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe("synthetic_test.mp4", language="es")  # y luego language="en"
```

**Resultado — funciono sin ffmpeg en el PATH.** `av.open("synthetic_test.mp4")` abrio el contenedor
directamente (`Container format: mov,mp4,m4a,3gp,3g2,mj2`, streams `[('video','h264'), ('audio','aac')]`)
sin ningun binario `ffmpeg`/`ffprobe` disponible en el sistema (verificado antes y despues con
`where ffmpeg`).

Con `language="es"` forzado sobre audio en ingles (mismatch deliberado del test, no del pipeline):

```
Detected language: es (p=1.00)
Audio duration reported by faster-whisper: 42.69 s
Transcribe wall time: 19.79 s
Realtime factor: 0.46x
[0.0-5.8]  Esta es una fila que genero un test de sintetismo sintetico para un spike tecnico.
[5.8-14.6]  Es usada para verificar que el mas rapido whisper puede transcribir audio sin la binaria
            Fnbeg instalada en el patron del sistema.
[14.6-18.8]  La linea de pipelin se realiza entero en la libreria Pi AV,
[18.8-24.8]  que embeda su propia copia de la codex Fnbeg dentro de la caida de Python.
...
```

(texto con acentos suprimidos aqui a proposito por la regla del repo; alucina una traduccion libre al
espanol porque se le pidio decodificar ingles como si fuera espanol — comportamiento esperado de Whisper,
no un fallo del pipeline).

Con `language="en"` (control, audio e idioma coinciden):

```
lang=en p=1.00 dur=42.69 wall=15.32
[0.0-5.8]  This is a synthetic spoken test file generated for a technical spike.
[5.8-14.6]  It is used to verify that faster whisper can transcribe audio without the fmbeg binary
            installed on the system path.
[14.6-24.8]  The pipeline relies entirely on the pyav library, which embeds its own copy of the fmbeg
             codecs inside the python wheel.
[24.8-34.5]  If this sentence appears correctly in the resulting transcript, the core assumption of the
             architecture decision record holds true.
[34.5-42.6]  Repository tools for windows are small utilities that live in the context menu of the file
             explorer.
```

Transcripcion practicamente perfecta (unico fallo: "ffmpeg" se oye como "fmbeg" porque la voz SAPI no
pronuncia bien la sigla — limitacion del audio de prueba, no del motor). Tiempo real de proceso 15.32 s
para 42.69 s de audio: **0.36x tiempo real**, es decir, mas rapido que tiempo real en CPU con `small`/int8.

**Veredicto S1: VERDE.** PyAV abrio el `.mp4` directamente, sin invocar ni requerir un binario `ffmpeg`
del sistema, y faster-whisper transcribio correctamente. La premisa central del ADR se sostiene.

---

## S6 — yt-dlp descarga solo audio sin postprocesado

**Comando exacto (instalacion):** `pip install yt-dlp` (version resuelta: `2026.7.4`).

**Lo que se intento primero**, tal como pide la spec: extraer formatos con la extraccion por defecto de
yt-dlp sobre un video publico corto y corriente ("Me at the zoo", `jNQXAC9IVRw`, 19 s, YouTube). Fallo
inmediato, **sin tocar nada nuestro**:

```
ERROR: [youtube] jNQXAC9IVRw: Sign in to confirm you're not a bot. Use --cookies-from-browser or
--cookies for the authentication.
```

Este es el bloqueo anti-bot que YouTube aplica hoy (2026-08-10) a peticiones no autenticadas del cliente
`web` por defecto de yt-dlp — coincide con el "riesgo real" que el propio ADR-0001 §8 ya anticipa
("yt-dlp es una dependencia viva"). D6 prohibe usar cookies, asi que esa salida esta cerrada por diseno,
no por limitacion tecnica del spike.

Se probaron **doce** `player_client` internos de yt-dlp (`android`, `ios`, `web_safari`, `tv`, `mweb`,
`web`, `tv_embedded`, `web_embedded`, `web_music`, `web_creator`, `android_vr`, `tv_downgraded`,
`tv_simply`) sobre tres videos publicos distintos, sin cookies en ningun caso. Resultado uniforme:

- Todos los clientes salvo `android` fallaron con el mismo bloqueo anti-bot o "DRM protected" o
  "video unavailable" (fallos de plataforma, no del selector de formato).
- `android` fue el **unico** que autentico sin cookies, pero **solo expuso un formato**: `itag 18`,
  `mp4`, `acodec=mp4a.40.2`, `vcodec=avc1.42001E` — es decir, **video+audio ya muxeados en 360p**, no una
  pista de audio aislada. Se repitio en los tres videos probados: nunca aparecio un `itag` audio-only
  (140/251/etc.) a traves de `android`.

**Descarga real, comando exacto, sin postprocesadores:**

```python
ydl_opts = {
    "extractor_args": {"youtube": {"player_client": ["android"]}},
    "format": "bestaudio[abr<=128]/bestaudio/best",
    "postprocessors": [],
    "noplaylist": True,
}
```

El selector `bestaudio[abr<=128]/bestaudio/best` cayo en `best` porque no habia ningun `bestaudio`
disponible sin cookies; descargo `itag 18`: `yt_download.mp4`, **629 172 bytes (~614 KiB)**, sin invocar
ningun postprocesador (`postprocessors: []` se respeto — no hubo merge ni extraccion).

**PyAV + faster-whisper sobre el archivo descargado**, con `ffmpeg` reconfirmado fuera del PATH:

```
Container: mov,mp4,m4a,3gp,3g2,mj2 [('video', 'h264'), ('audio', 'aac')]
lang=en p=1.00 dur=18.95s wall=7.30s
[0.0-5.0]  Alright, so here we are, one of the elephants.
[5.0-13.0]  The cool thing about these guys is that they have really, really, really long trunks.
[13.0-16.0]  And that's cool.
[16.0-19.0]  And that's pretty much all there is to say.
```

Transcripcion exacta del audio real del video (verificable: es el video mas citado de YouTube, su
transcripcion es publica y coincide). El decode y la transcripcion funcionaron sin ffmpeg del sistema.

**Formato y extension reales que cayeron:** `.mp4` (contenedor `mov,mp4,m4a,3gp,3g2,mj2`), `itag 18`,
audio AAC + video H.264 — **no** el `.m4a`/`.webm` audio-only que D3 y S6 dan por hecho.

**Tamano frente al video completo: NO CONCLUYENTE.** No se pudo medir porque, sin cookies, la extraccion
solo devolvio **un** formato descargable (`itag 18`, ~614 KiB) en los tres videos probados; no hubo una
alternativa de "video completo en mayor resolucion" visible para comparar. La comparacion que pide la
spec (audio-only vs. video completo) exige que existan al menos dos formatos accesibles sin cookies, y hoy
no fue el caso en esta red.

**Veredicto S6: AMARILLO, no verde limpio.** Lo que sostiene D2/D3 se cumple a medias:

- **Se sostiene:** nunca se invoco un postprocesador ni un merge; `postprocessors=[]` fue real y el
  archivo resultante lo abrio PyAV sin ffmpeg del sistema. La invariante "cero binario ffmpeg" **no se
  rompio en ningun momento**.
- **No se sostiene tal como estaba escrito el supuesto:** el ADR asume que "descargar un solo stream de
  audio nativo (m4a/webm/mp4)" es lo normal para YouTube (§3, punto 3). Hoy, sin cookies, YouTube no ofrece
  ese stream de audio aislado al unico cliente (`android`) que yt-dlp puede usar sin autenticarse: entrega
  un video+audio muxeado de baja resolucion. El texto se sigue pudiendo transcribir igual de bien (la pista
  de audio dentro del mp4 es la misma), pero se descarga **mas bytes de los necesarios** (incluye video) y
  el supuesto de "solo audio" de S6 no se cumplio para ninguno de los tres videos probados hoy.

Esto **no es un fallo del enfoque arquitectonico** (D2/D3 siguen siendo correctos: nunca se necesito
ffmpeg), es un dato nuevo sobre **el estado actual de las restricciones anti-bot de YouTube sin cookies**,
que ya era el riesgo declarado en ADR-0001 §8 pero con una forma concreta no anticipada: no es que yt-dlp
se rompa por un cambio de API, es que **el catalogo de formatos disponibles sin cookies se ha reducido a
uno solo**, y ese uno ya viene muxeado.

---

## S8 — pywebview instala limpio en Python 3.11.9

**Comando exacto:** `pip install pywebview` (version resuelta: `6.2.1`).

**Que arrastro:** exactamente lo que predecia el ADR (§4.3): `pythonnet` (`3.1.0`), `clr_loader`
(`0.3.1`), `cffi` (`2.1.1`) + `pycparser`, mas `bottle` (servidor HTTP interno de pywebview para su puente
JS) y `proxy_tools`. Ninguna sorpresa en la lista de dependencias.

**Peso real del conjunto anadido** (medido con `du -sh` sobre `site-packages`, sumando solo los paquetes
de la pila pywebview): `pythonnet` 3.6 MB + `clr_loader` 0.4 MB + `webview` 2.4 MB + `cffi` 0.9 MB +
`bottle` ~0.2 MB + `proxy_tools` ~0.03 MB + `pycparser` 0.5 MB = **~8 MB instalados**. Por debajo del rango
estimado en el ADR (~10-20 MB).

**Abrir una ventana real, no solo el import.** Primer intento fallido:

```
[pywebview] WebView2 initialization failed with exception:
  (0x80004004): Operation aborted (Exception from HRESULT: 0x80004004 (E_ABORT))
```

WebView2 Runtime **si esta instalado** en esta maquina (version `151.0.4129.72`, confirmado via el
registro), y el proceso corria en la sesion de escritorio interactiva correcta (sesion 4, la misma que
`explorer.exe`, `UserInteractive=True`) — no era un problema de sesion no interactiva. El fallo desaparecio
al indicar explicitamente un `storage_path` limpio para el perfil de WebView2
(`webview.start(storage_path=...)`); con eso la ventana abrio y cerro sin ningun error:

```python
webview.start(storage_path=r"...\webview_storage", debug=False)
# RESULT: {'opened_before_close': True, 'start_returned': True, 'error': None}
```

**Advertencia operativa para la implementacion real:** el primer intento con la carpeta de datos de
usuario por defecto de WebView2 fallo con `E_ABORT` al borrar un "user data folder" (probablemente un
perfil previo de otra herramienta que ya usa WebView2 en esta maquina, como MDViewer). La app de produccion
deberia fijar su propio `storage_path` dedicado (p. ej. dentro de `apps/Voice2Text/work/` o
`%LOCALAPPDATA%\BSTools\Voice2Text\webview`) en vez de confiar en el default de pywebview, para no heredar
el estado de otra app que tambien use WebView2 en la misma maquina.

**Veredicto S8: VERDE**, con esa advertencia operativa incorporada al diseno de `app.py` (fijar
`storage_path` propio), no como bloqueo.

---

## S5 — la transcripcion no debe congelar la UI (liberacion del GIL)

**Experimento:** un hilo `daemon` incrementa un contador cada 0.05 s (esperado ~20 ticks/s si el hilo
principal, ocupado transcribiendo, no bloquea al interprete) mientras el hilo principal llama a
`model.transcribe(...)` sobre `synthetic_test.mp4` con `language="en"`.

```
Transcribe wall time: 15.22s
Ticker counter after transcribe: 302
Ticks/sec observed during transcribe: 19.84 (expected ~20/s if GIL is released)
```

**Veredicto S5: VERDE.** 19.84 ticks/s frente a un maximo teorico de 20/s: el hilo contador avanzo
practicamente sin frenar mientras CTranslate2 calculaba. El computo pesado de faster-whisper **libera el
GIL**, asi que un hilo de UI puede seguir respondiendo mientras transcribe, tal como asume D9 (modelo de
trabajo asincrono) y S5.

---

## Peso real de la instalacion

**Venv completo, todo instalado** (`faster-whisper` + `yt-dlp` + `pywebview`, patron B completo):

```
du -sh v2t-spike
331M    v2t-spike
```

Desglose de los paquetes mas pesados (`du -sh Lib/site-packages/*`, orden descendente):

| Paquete | Tamano medido | Estimacion ADR |
|---|---:|---:|
| `av` + `av.libs` (PyAV) | 67.5 MB | 35-45 MB |
| `ctranslate2` | 60 MB | 60-150 MB |
| `onnxruntime` | 45 MB | ~25 MB |
| `numpy` + `numpy.libs` | 58 MB | ~50 MB (a menudo ya instalado) |
| `yt_dlp` | 26 MB | ~15 MB |
| `pip` + `setuptools` + `pkg_resources` (overhead del venv, no del proyecto) | ~22 MB | (no contado en el ADR) |
| `hf_xet` + `tokenizers` + `huggingface_hub` | 24 MB | ~15-27 MB (hf_xet no estaba en la cuenta del ADR) |
| pila pywebview completa (`pythonnet`+`clr_loader`+`webview`+`cffi`+...) | ~8 MB | 10-20 MB |

**Comparacion con §6 del ADR:** el ADR estima el subtotal de wheels en **220-330 MB**. El venv completo
(sin descontar overhead de `pip`/`setuptools`, que no es parte del proyecto sino del propio venv) pesa
**331 MB**; descontando ese overhead (~22 MB) queda en **~309 MB de dependencias del proyecto**, dentro
del rango estimado pero cerca del techo alto. La sobreestimacion de PyAV/onnxruntime/yt-dlp se compensa
con una pywebview mas ligera de lo estimado. **El ADR acierta de orden de magnitud, con un margen real de
error de +30/-40 MB por paquete individual** — normal para estimaciones de memoria previa sin medir.

**Modelo `small` descargado** (cache de Hugging Face, fuera del venv, ubicacion real que usara la app en
produccion — D4 — sera `apps/Voice2Text/models/`, aqui se midio en la ubicacion por defecto de
`huggingface_hub` para no tocar el repo):

```
du -sh ~/.cache/huggingface/hub/models--Systran--faster-whisper-small
464M
```

**Comparacion con §5 del ADR:** estimaba ~484 MB. Medido: **464 MB, un -4 %**. El ADR acierta dentro de su
propio margen declarado (±5 %, ver S10). Este dato tambien cierra S10 de paso.

**TOTAL medido en regimen (patron B completo + modelo `small`):** 331 MB (venv, incluye ~22 MB de overhead
de pip/setuptools) + 464 MB (modelo) = **~795 MB**, frente a la horquilla del ADR de 0,70-0,81 GB. **Cae
dentro del rango declarado.**

**Limpieza tras medir:** el venv completo (331 MB) y la carpeta del modelo `small` en la cache de
Hugging Face (464 MB) se borraron al terminar este spike; no queda ningun rastro en disco ni en el repo.

---

## Que cambia esto en el ADR

1. **S1 queda cerrado en verde con evidencia real**, no solo con razonamiento (ADR §3 punto 1-2). El ADR
   puede dejar de marcarlo como "confianza alta, sin ejecutar" y citarlo como validado, con fecha
   2026-08-10.

2. **S6 necesita una correccion de matiz en ADR §3 y §8, no un cambio de arquitectura.** El texto actual de
   §3 (punto 3) dice "en YouTube esos formatos [audio-only] existen y son directamente descargables". Hoy,
   sin cookies, **no siempre es asi**: el unico cliente que yt-dlp puede usar sin autenticarse
   (`android`) puede quedar limitado a un unico formato ya muxeado. Se recomienda:
   - Anadir esta situacion a la tabla de fragilidad de §8 como un tercer sintoma ademas del cambio de
     extractor: "el catalogo de formatos disponibles sin cookies puede reducirse a uno solo, ya muxeado,
     sin que eso sea un error de extraccion" — el codigo debe tratarlo como caso normal, no como
     `download_failed`.
   - El selector de formato de D3/S6 (`bestaudio[abr<=128]/bestaudio/best`) **ya contempla esto
     correctamente** gracias al `/best` de reserva: no hace falta tocar D3, la cadena de fallback ya
     resuelve el caso sin ffmpeg y sin postprocesado. Lo que hay que documentar es que "solo audio" es un
     **mejor esfuerzo**, no una garantia — coherente con el espiritu de D7/§8 (yt-dlp es una dependencia
     viva), simplemente con un ejemplo concreto y fechado que antes no estaba.
   - No cambia el tope de tamano de archivo de D13/§7: si el "mejor esfuerzo" cae en video completo, ese
     tope sigue siendo la salvaguarda correcta.

3. **S8 confirma la recomendacion B del ADR (§4.5)**, con un anadido concreto para `ARCHITECTURE.md` §12
   (la parte que depende del patron elegido): `app.py` debe fijar un `storage_path` propio y dedicado para
   WebView2 en vez de usar el default de pywebview, para blindarse frente a perfiles de WebView2 dejados
   por otras herramientas de la maquina (aqui, probablemente MDViewer). Es una linea de codigo, no cambia
   ninguna decision de arquitectura.

4. **S5 confirma D9** (modelo de trabajo asincrono) sin reservas: el hilo trabajador puede transcribir
   mientras el hilo de la ventana sigue respondiendo, sin necesidad de mover el motor a un subproceso.

5. **El peso real (§6) queda medido, no estimado**, y esta dentro de la horquilla que el ADR ya declaraba
   (~0,70-0,81 GB). No hace falta reabrir §6 con el dueno (el propio criterio de "si supera 1 GB" de S2 no
   se dispara). Los numeros de la tabla de §6 se pueden sustituir por los medidos aqui cuando se escriba el
   README de la herramienta (S2 y S10 quedan cerrados con este mismo spike, de paso).

**Ningun hallazgo de este spike bloquea el GO del ADR.** El unico ajuste de fondo es documental: §3 y §8
del ADR deben reconocer, con este ejemplo fechado, que "audio-only sin ffmpeg" es un resultado probable
pero no garantizado en YouTube sin cookies, y que el codigo (`fetch.py`) debe tratar el caso "solo cayo un
formato muxeado" como flujo normal, no como error.
