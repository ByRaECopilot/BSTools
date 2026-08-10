# Voice2Text

Transcribe audio y vídeo a texto **en tu propio equipo**, sin mandar nada a la nube.
Arrastra un archivo (o pega un enlace) y obtienes un `.txt` y un `.md` con marcas de
tiempo. Tiene dos modos, excluyentes entre sí: **ventana** (uso normal, doble clic) y
**servidor** (para que otra aplicación de tu equipo la consuma).

---

## Instalación

```powershell
cd Voice2Text
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

El instalador:

1. Instala las dependencias de Python: `faster-whisper`, `yt-dlp` y `pywebview`
   (unos 330 MB de descarga; puede tardar varios minutos). Si ya las tienes, `pip`
   no vuelve a bajar nada.
2. Añade al menú contextual de los archivos de audio y vídeo la opción
   **"Transcribir con Voice2Text"**: `.mp3 .wav .m4a .aac .flac .ogg .opus .wma
   .aiff .amr` y `.mp4 .mkv .mov .avi .webm .wmv .flv .m4v .mpg .mpeg .3gp .ts`.
   Abre la ventana con ese archivo ya cargado, listo para pulsar "Transcribir"
   (nunca arranca la transcripción sola: siempre hay un clic de por medio, porque
   es un trabajo de minutos con opciones que importan).

Escribe en `HKCU:\Software\Classes`: **no necesita permisos de administrador** y
solo afecta a tu usuario.

> En Windows 11, la opción del menú contextual está dentro de
> *Mostrar más opciones* (`Shift+F10`).

Para desinstalar: `powershell -ExecutionPolicy Bypass -File .\uninstall.ps1` — quita
la entrada del menú; no toca tus modelos descargados, tus transcripciones ni los
paquetes de Python (se indica cómo quitarlos si quieres).

Si mueves la carpeta, vuelve a ejecutar `install.ps1`: el registro guarda la ruta
absoluta de `Voice2Text.cmd` e `icon.ico` de este equipo.

### Complemento de GPU (opcional)

Si tienes una GPU NVIDIA con su driver instalado, puedes acelerar la transcripción:

```powershell
powershell -ExecutionPolicy Bypass -File .\install-gpu.ps1
```

Instala unas librerías CUDA adicionales (**unos 2 GB más** sobre la instalación
base) y termina ejecutando una prueba real sobre tu GPU, no solo comprobando que
la instalación no dio error — construir el modelo sin fallo **no** demuestra que la
GPU funcione (lo medimos: sí se puede construir sin usarla de verdad). El resultado
de esa prueba te dice si de verdad quedó activa. Es opcional del todo: sin esto,
Voice2Text funciona entero, solo que en CPU. Para quitarlo: `.\uninstall-gpu.ps1`.

---

## Uso (modo ventana)

1. Doble clic en `Voice2Text.cmd`, o clic derecho sobre un archivo de audio/vídeo →
   **"Transcribir con Voice2Text"**.
2. La primera vez, antes de nada, te pide **descargar el modelo de reconocimiento**
   (una sola vez, se queda en tu equipo, puedes borrarlo cuando quieras). Elige uno
   de la lista o deja el recomendado para tu hardware.
3. Con el origen ya elegido (o arrastra otro archivo, o pega un enlace), revisa el
   idioma y los formatos de salida, y pulsa **Transcribir**.
4. Verás el progreso por fases (preparando el audio, transcribiendo con el texto
   apareciendo en vivo, guardando) y al final, los archivos generados con un botón
   para abrir la carpeta.

Cerrar la ventana termina el trabajo en curso, en un solo gesto.

---

## Modo servidor

Para que **otra aplicación de tu mismo equipo** (por ejemplo, un bot) use el motor
de transcripción sin abrir la ventana:

```
Voice2Text-Servidor.cmd [--port 8317]
```

Arranque **manual y en primer plano**: no hay servicio de Windows, ni tarea
programada, ni arranque con la sesión. La consola de esa ventana es la que te dice
que está vivo; ciérrala o pulsa `Ctrl+C` para apagarlo.

**El trato, dicho sin rodeos: el servidor solo responde mientras esa ventana esté
encendida. Si está apagado, quien lo consuma (tu bot, tu script) no obtiene
respuesta — no es un fallo, es el trato.** Fue una decisión explícita: nada de
dejarlo corriendo en segundo plano sin que se note.

Escucha solo en `127.0.0.1`, puerto fijo `8317` por defecto (si está ocupado, el
servidor avisa y no arranca — no busca otro puerto solo). Cada petición necesita
un token, generado de nuevo en cada arranque y guardado en `serve-token.txt`
(ignorado por git), en la cabecera `X-Token`:

```bash
TOKEN=$(cat serve-token.txt)
curl -H "X-Token: $TOKEN" http://127.0.0.1:8317/api/v1/health
```

Endpoints principales (`/api/v1`): `GET /health`, `GET /models`,
`POST /jobs` (encolar, `{"source": {"kind": "file", "path": "..."}, "options": {...}}`),
`GET /jobs/{id}?since=N` (estado y texto nuevo desde el segmento N),
`POST /jobs/{id}/cancel`, `GET /jobs/{id}/result?format=txt|md`,
`POST /models/{id}/download`, `DELETE /models/{id}`.

---

## Enlaces (YouTube y similares)

Además de un archivo local, puedes indicar un enlace público: Voice2Text usa
`yt-dlp` para traer solo el audio (o audio+vídeo, si esa plataforma no ofrece hoy
una pista de audio suelta — no es un fallo, simplemente se descargó algo más de lo
estrictamente necesario) y lo transcribe igual que un archivo local.

Lo que hay que saber de esta vía, sin adornarlo:

- **Por defecto, solo contenido público.** Voice2Text no inicia sesión ni usa tus
  cookies del navegador salvo que tú lo actives: si el contenido exige iniciar
  sesión, es privado o tiene restricción de edad, la descarga falla — es la
  plataforma pidiendo una credencial que esta herramienta, por defecto, no ofrece.
- **X (Twitter) y Facebook exigen sesión a menudo**, así que fallarán con
  frecuencia. De nuevo: no es un fallo de Voice2Text, es la plataforma.
- **Cookies del navegador, opcional y desactivado por defecto.** En **Ajustes
  avanzados** puedes activar "Cookies del navegador" (Chrome, Edge o Firefox) para
  que los enlaces que exigen sesión funcionen con la tuya. Se leen del navegador
  para esa descarga y **nunca se guardan ni se registran en ningún sitio** — ni en
  disco propio, ni en los archivos de texto/consola de la herramienta. Si el
  navegador está abierto puede bloquear el acceso a sus cookies (ciérralo e
  inténtalo de nuevo); si el enlace sigue fallando tras activarlas, puede que la
  sesión haya caducado — vuelve a iniciar sesión en el navegador. En modo servidor
  y en `cli.py` es el mismo interruptor: `settings.json` (`youtube_cookies_from_browser`)
  o `--cookies-from-browser` en `cli.py`.
- **`yt-dlp` es una dependencia viva**: las plataformas cambian sus mecanismos de
  descarga cada pocas semanas y `yt-dlp` se actualiza para seguirles el ritmo. Si un
  enlace que antes funcionaba deja de hacerlo, actualízalo:

  ```
  py -3 -m pip install --upgrade yt-dlp
  ```

  La ventana avisa sola cuando tu `yt-dlp` lleva más de 60 días sin actualizar.

---

## Qué genera

Por cada transcripción, junto al archivo de origen (o en `salida/` si vino de un
enlace):

| Archivo | Contenido |
|---|---|
| `nombre.txt` | Texto corrido, sin marcas de tiempo. UTF-8, saltos `CRLF` (se abre bien en el Bloc de notas) |
| `nombre.md` | El mismo texto en párrafos con `[mm:ss]`, más una cabecera con origen, duración, idioma detectado y modelo usado |

Si ya existe un archivo con ese nombre, nunca se sobrescribe en silencio: se
escribe `nombre (2).md`.

## Modelos: peso y velocidad, sin maquillar

Voice2Text sugiere un modelo según tu hardware, pero puedes elegir otro desde la
pantalla de modelos:

| Modelo | Descarga | Calidad | Nota |
|---|---|---|---|
| `base` | ~145 MB | Básico — más rápido, se equivoca más con nombres y cifras | |
| **`small`** | **464 MB** | Preciso, para uso normal | **el recomendado en equipos sin GPU** |
| `medium` | ~1,5 GB | Preciso | |
| `large-v3-turbo` | ~1,6 GB | Muy preciso | recomendado en algunas GPU |
| `large-v3` | **3,1 GB** | El más preciso | el modelo, solo, pesa esto — aparte de la instalación base |

**Peso de la instalación base:** unos **795 MB** en total (las ~330 MB de
librerías de Python más el modelo `small`, 464 MB, que se descarga la primera vez
que abres la ventana). El complemento de GPU añade **~2 GB más**, aparte. Nada de
esto se esconde: la propia ventana te enseña siempre los dos números — cuánto se
descarga y cuánto ocupará en memoria — antes de que aceptes.

**Velocidad, medida y expresada como manda la casa: minutos de proceso por cada 10
minutos de audio (nunca un multiplicador — un `2,8×` se leyó una vez al revés y
salió un error de 8×, así que aquí no se usa esa notación).** Con el modelo por
defecto (`small`, cuantización `int8`) **en CPU**:

- **Español: 5,8 min de proceso por cada 10 min de audio.**
- **Inglés: 6,5 min de proceso por cada 10 min de audio.**

Medido en la máquina del dueño: **AMD Ryzen 7 1700 (8 núcleos / 16 hilos), Windows
10 Pro, sin GPU implicada en esta medición.** Es un repositorio público: si tu CPU
es más lenta o más rápida, tu tiempo variará — estas cifras son la referencia de
una máquina concreta, no una promesa universal.

**Con GPU** (complemento opcional, ver arriba): acelera **entre 5 y 20 veces según
el modelo**, sin cifra exacta todavía — está pendiente de remedirse en condiciones
aisladas antes de publicarse suelta. Y un detalle importante, porque es
contraintuitivo: **pedir GPU no la garantiza.** Si las librerías del complemento
faltan, están desparejadas o el modelo no cabe en la memoria de tu tarjeta,
Voice2Text **cae a CPU sola y te lo avisa con el motivo** — nunca en silencio. Si
instalaste el complemento y sigues viendo tiempos de CPU, ese aviso (en el
resultado, o en `install-gpu.ps1`) es el primer sitio donde mirar.

En **Ajustes avanzados** puedes fijar la preferencia de dispositivo:
**Automático** (por defecto — dejar que Voice2Text decida), **Forzar CPU** o
**Forzar GPU**. "Forzar GPU" sigue sin ser una garantía: si de verdad no se puede
usar, cae a CPU con aviso, igual que en automático.

**Calidad del texto, honesta:** con el modelo por defecto (`small`) en CPU, verás
errores ocasionales en **nombres propios y cifras** — es el modelo más ligero de
los recomendados, y ese es precisamente el trueque frente a los modelos mayores
(`medium`, `large-v3-turbo`, `large-v3`), más lentos pero más precisos.

---

## Lo que no hace (y por qué)

- **No transcribe en la nube.** Todo ocurre en tu equipo; nada del audio ni del
  texto sale de tu máquina (salvo, claro, la propia descarga si transcribes desde
  un enlace).
- **No inicia sesión en ninguna plataforma por defecto**, ni usa tus cookies del
  navegador salvo que actives esa opción en Ajustes avanzados (ver "Enlaces"
  arriba). Con las cookies desactivadas — el estado de fábrica — algunos enlaces
  (contenido privado, X, Facebook) fallan; es la razón de siempre.
- **No purga tus modelos solo.** `models/` puede crecer si descargas varios; bórralos
  desde la pantalla de gestión de modelos, o borra la carpeta entera a mano —
  se vuelve a descargar si hace falta.
- **El modo servidor no se queda encendido solo.** Arranque manual y en primer
  plano, siempre — ver "Modo servidor" arriba.

---

## Problemas comunes

**No encuentra Python.** Instálalo desde <https://www.python.org/downloads/>
marcando "Add Python to PATH", y vuelve a ejecutar `install.ps1`.

**La ventana no abre / no aparece nada.** Comprueba que tienes el *WebView2
Runtime* de Microsoft (viene ya instalado en Windows 10 2004+ y Windows 11). Si
tienes otra herramienta de BSTools que también use WebView2 (como MDViewer) y algo
falla igualmente, esta herramienta ya usa un perfil propio para evitar ese
conflicto — no debería hacer falta nada más.

**Un enlace de YouTube (o similar) falla.** Primero comprueba que el contenido es
público (sin iniciar sesión, en el navegador). Si lo es y sigue fallando,
actualiza `yt-dlp`: `py -3 -m pip install --upgrade yt-dlp`.

**Instalé el complemento de GPU y sigue tardando lo mismo que en CPU.** Revisa el
aviso que aparece junto al resultado (o la salida de `install-gpu.ps1`): dice el
motivo exacto (librerías que faltan, memoria insuficiente, u otro fallo de CUDA) y
qué hacer en cada caso.

**El modo servidor no responde.** Comprueba que su ventana de consola sigue
abierta: si se cerró, el servidor está apagado — es el trato, no un fallo (ver
"Modo servidor").

**Moviste la carpeta.** Vuelve a ejecutar `install.ps1`.

---

Parte de [BSTools](../../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · CC0 1.0
