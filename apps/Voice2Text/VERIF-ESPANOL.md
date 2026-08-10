---
title: "Verificacion V1 (velocidad en espanol) y S11 (deteccion automatica de idioma)"
status: "V1 y S11 completados en verde (repeticion limpia del 2026-08-10, segunda sesion)"
fecha: 2026-08-10
autor: Veritas (QA) -- verificacion independiente, sobre copias fuera del repo
---

# Verificacion en espanol -- V1 y S11 (lote 1.b)

> **BLUF (actualizado tras la repeticion limpia):** **V1 y S11 quedan cerrados en VERDE.** Se
> repitio V1 en una maquina confirmada sin contencion (cero `python.exe` competidor, verificado
> con `tasklist` antes y despues de cada corrida) y con el codigo ACTUAL del repo (commit
> `032a3a1`, `vad_filter=True` + `word_timestamps=True`). **Resultado limpio: `small`/int8/CPU
> procesa espanol a 1.725x tiempo real -- 5.80 min de proceso por cada 10 min de audio.** Un
> control en ingles sobre el mismo hardware, misma sesion, mismo codigo (fragmento de 10:18 del
> video real del dueno) dio 1.534x -- 6.52 min por cada 10 min. **Pregunta que quedaba
> abierta, respondida: el espanol NO es mas lento que el ingles.** Si acaso, en esta medicion
> salio ~11% MAS RAPIDO. La cifra de 0.93x/1.31x obtenida en el primer intento (mas abajo,
> conservada como historial) fue enteramente explicable por la contencion de CPU documentada
> entonces, no por el idioma. **Numero definitivo para ARCHITECTURE.md Sec.8 y la pantalla del
> usuario: ~5.8 min de proceso por cada 10 min de audio en espanol con `small`/CPU/int8**
> (ver cierre, mas abajo, para el detalle de que mas hay que actualizar).

---

## Veredicto en una tabla

| # | Verificacion | Veredicto |
|---|---|---|
| **Voz Sabina** | Confirmar `Microsoft Sabina Desktop` (es-MX) disponible para `System.Speech.Synthesis` | **VERDE** -- reconfirmado por esta maquina, no solo por lo dicho en el encargo (ver abajo) |
| **V1 (intento 1, misma fecha, sesion anterior)** | Velocidad real, 10 min de audio en espanol, `small`/int8/CPU/`language="es"` | **AMARILLO -- medido, pero contaminado.** Cifra obtenida: `speed_ratio` 0.93x (mas lento que tiempo real). Contencion de CPU documentada durante toda la corrida. **Conservado como historial, INVALIDADO, no usar** |
| **V1 (repeticion limpia, misma fecha, sesion nueva)** | Igual que arriba, mas control en ingles sobre audio real (10:18) para separar idioma de contencion | **VERDE.** `speed_ratio` 1.725x en espanol (5.80 min/10min), 1.534x en ingles (6.52 min/10min). Maquina confirmada sin `python.exe` competidor antes y despues de cada corrida. Codigo actual del repo (`vad_filter=True`, `word_timestamps=True`) |
| **S11** | Deteccion automatica (`language=None`) en espanol e ingles, incluido el video real sin recortar | **VERDE.** 4/4 detecciones correctas, probabilidad >= 99.5% en todos los casos. Coste de deteccion: 7-22 s segun la duracion total del archivo (no es gratis para archivos largos, ver hallazgo abajo) |

---

## Aislamiento y entorno

Todo el codigo ejecutado es una **copia** de `apps/Voice2Text/*.py`, tomada al empezar y
guardada en `%TEMP%\...\scratchpad\v1-s11\py\`. No se edito ningun `.py` del repo. La unica
escritura en el repositorio es este archivo.

**Venv desechable**, fuera del Python global: se reutilizo un venv ya existente en el mismo
directorio temporal de esta sesion (`scratchpad\v2t-verify`), creado en un trabajo de
verificacion anterior de este mismo lote, con `faster-whisper 1.2.1`, `ctranslate2 4.8.1`,
`av 18.0.0`, `numpy 2.4.6` -- mismas versiones con las que se corrio todo lo demas del lote
1. Confirmado con `where ffmpeg` (sin resultados) antes y despues de cada corrida: la
invariante "cero ffmpeg del sistema" se mantuvo todo el tiempo.

**Modelo:** se leyo el `small` ya descargado en `apps/Voice2Text/models/` (carpeta ignorada
por git, no versionada) con `allow_download=False`. Solo lectura: la carpeta no cambio de
tamano ni de fecha durante la verificacion.

**Video del dueno:** `apps/Voice2Text/test/uvlVg3c2fCxBzKVk.mp4` no se toco ni se movio.
Confirmado antes y despues (mismo tamano, 23 201 476 bytes, y misma fecha de modificacion).
Los recortes usados en S11 se generaron por remuxado con PyAV (sin reencode, sin ffmpeg)
sobre una copia en el directorio temporal.

### Confirmacion de la voz Sabina -- no se dio por supuesto

Se reconfirmo en esta maquina, no se acepto el dato del encargo sin mas:

```
Microsoft David Desktop  | en-US
Microsoft Zira Desktop   | en-US
Microsoft Sabina Desktop | es-MX
```

**[M-dev]** `Microsoft Sabina Desktop` esta instalada y visible para
`System.Speech.Synthesis.SpeechSynthesizer.GetInstalledVoices()`. Confirmado.

---

## V1 -- INTENTO 1 (INVALIDADO por contencion de CPU) -- conservado como historial

**No usar esta cifra para nada.** Se deja completa, sin editar, porque el historial de
cifras erroneas de este proyecto es informacion valiosa (ya paso dos veces con la pantalla
de Sec.8: "~2 min", luego "~3-4 min", ver Sec.8 de ARCHITECTURE.md). La version limpia y
valida esta en la seccion siguiente ("V1 -- REPETICION LIMPIA").

### Metodo

Se replico la receta del spike (`SPIKE-RESULTS.md`): voz SAPI -> `.wav` -> contenedor `.mp4`
con PyAV puro (video trivial `libx264` + audio `aac`, sin ffmpeg). Texto en espanol de
~1585 palabras (reunion de comite, con cifras, nombres propios y fechas, tal como pide
ARCHITECTURE.md Sec.14), hablado por Sabina a `SetOutputToWaveFile` (sintesis no ligada a
tiempo real: la sintesis tardo 5.6 s en generar 10:17 de audio).

**Duracion exacta del audio generado: 617.697 s (10:17.70) [M-dev].** Cerca del objetivo de
10 minutos, dentro de lo esperable de una calibracion previa por palabras/segundo.

Transcripcion con la copia aislada de `transcribe.py`: `probe_devices()` +
`resolve_device("small", caps, preference="cpu")` -> `compute_type="int8"`,
`load_model(allow_download=False)`, y `transcribe(..., language="es", vad_filter=True)`.
Mismo camino de codigo que usara `cli.py` en produccion.

### Resultado directo

**[M-dev]**

| Métrica | Valor |
|---|---|
| Duracion del audio | 617.697 s (10:17.70) |
| Tiempo de proceso (`elapsed_seconds`) | 664.531 s (11:04.53) |
| `speed_ratio` (duracion/proceso) | **0.930x** -- MAS LENTO que tiempo real |
| Idioma | `es`, probabilidad 1.00 (forzado por `language="es"`, no detectado -- ver S11 para la probabilidad real de deteccion) |
| Minutos de proceso por cada 10 min de audio | **~10.76 min** |

Comparado con el **2.8x** medido en el spike (`SPIKE-RESULTS.md`, clip de 42.69 s en ingles,
idioma forzado y coincidente con el audio) esto es una caida de **~3x**, y ademas cruza de
"mas rapido que tiempo real" a "mas lento que tiempo real". Esa es precisamente la pregunta
que V1 debia resolver -- pero la respuesta que salio no es fiable tal cual, por lo siguiente.

### Hallazgo critico: contencion de CPU con otro proceso, documentada con evidencia de sistema

**Mientras la transcripcion de 10 min corria, `tasklist` mostro otro `python.exe` en la
misma maquina (PID 20160, mismo directorio temporal de esta sesion, ejecutando
`scratchpad\verify_v3.py`) con **1 h 16 min de tiempo de CPU acumulado y subiendo**, y la
carga total de CPU del sistema (`wmic cpu get loadpercentage`) en **65%** justo al terminar
mi corrida. `git status` sobre el repo, comprobado en esta misma sesion, confirma que
`transcribe.py`, `export.py` y `cli.py` estaban siendo modificados por otro agente en
paralelo -- coincide con el aviso del encargo de que hay un agente en `transcribe.py`/
`export.py` y sugiere que ese archivo `verify_v3.py` es su propia bateria de pruebas (V2/V3/V4)
corriendo faster-whisper al mismo tiempo que la mia, sobre la misma CPU de 16 hilos logicos.

**Control para acotar el efecto**, no solo para declararlo: se genero un recorte de **2
minutos** del mismo audio (remuxado con PyAV, sin reencode) y se repitio la misma
transcripcion, muestreando `wmic cpu get loadpercentage` cada 15 s durante la corrida:

| Ventana | Carga de CPU del sistema |
|---|---|
| t+15s | 57% |
| t+30s | 59% |
| t+45s | 70% (corrida terminada en este punto) |
| t+60s (ya sin mi corrida) | 76% |
| t+75s | 68% |
| justo despues, con un unico proceso mio corriendo | 87% |

**[M-dev]** El proceso ajeno (visto con distintos PID a lo largo de la sesion: 20160, luego
2612, con tiempos de CPU acumulados creciendo sin parar -- 12, 20, 29 minutos en chequeos
sucesivos) nunca desaparecio durante toda la ventana de verificacion. La carga de fondo del
sistema, **sin ningun proceso mio corriendo**, se mantuvo entre 37% y 87% segun el momento.
Esto no es ruido de un instante: es carga sostenida de otro agente trabajando en este mismo
lote, en esta misma maquina, en paralelo.

Resultado del control de 2 minutos, bajo esa misma contencion (menos tiempo de exposicion
que el clip de 10 min, pero no aislado):

| Métrica (clip de control, 2 min) | Valor |
|---|---|
| Duracion del audio | 118.979 s |
| Tiempo de proceso | 90.703 s |
| `speed_ratio` | **1.312x** |
| Minutos de proceso por cada 10 min de audio | **~7.62 min** |

**Interpretacion honesta, no una conclusion disfrazada de limpia:** el clip de 2 minutos
salio mejor que el de 10 minutos (1.31x contra 0.93x), pero los dos estan muy por debajo del
2.8x del spike. Con la contencion documentada como variable de confusion activa **todo el
tiempo** de ambas corridas, **no puedo separar** cuanto de esa caida es (a) contencion de
CPU con el otro agente, (b) un efecto real de que el audio largo tiene mucho menos silencio
proporcional que recortar con VAD (mas segundos reales de habla por segundo de reloj que en
el clip corto del spike), o (c) un efecto real del idioma. **Las tres hipotesis siguen
abiertas.** Lo unico que se puede afirmar con la evidencia de proceso es que **la contencion
fue real, sostenida y suficiente para explicar por si sola una degradacion de este orden**.

**Lo que esto significa para ADR-0001 D5 (regla del lote 13 de ARCHITECTURE.md):** *"si 10
minutos de audio en espanol dan menos de 3x tiempo real, `base` pasa a ser el modelo por
defecto, sin ADR nuevo."* La cifra medida (0.93x) tecnicamente dispara esa clausula. **No
recomiendo dispararla con este dato.** Es una decision de producto con consecuencia real
(cambiar el modelo por defecto que ve todo usuario nuevo) y la medicion que la sustentaria
esta contaminada de forma documentada. Pedir una repeticion limpia antes de decidir.

---

## V1 -- REPETICION LIMPIA (2026-08-10, sesion nueva) -- ESTA ES LA CIFRA VALIDA

### Por que se repite y que cambia respecto al intento 1

El intento 1 (arriba) obtuvo una cifra real pero contaminada: `tasklist` mostro otro
`python.exe` corriendo faster-whisper en paralelo durante toda la medicion, con evidencia de
PID y tiempo de CPU acumulado documentada en su momento. Antes de repetir se confirmo con el
dueno que **la maquina esta en reposo** (cero procesos Python activos) y que **nadie mas
lanzaria nada** hasta terminar. Se repite ademas con una diferencia deliberada respecto al
intento 1: **se anade un control en ingles de duracion comparable**, sobre el video real del
dueno (no TTS), para poder separar por fin "efecto del idioma" de "efecto de la contencion" --
la pregunta que quedo abierta la vez anterior.

### Protocolo de medicion limpia -- evidencia de sistema en cada corrida

**[M-dev]**

| Momento | Comprobacion | Resultado |
|---|---|---|
| Antes de V1 (espanol) | `tasklist \| findstr python` | **0 procesos** `python.exe` |
| Antes de V1 (espanol) | `wmic cpu get loadpercentage` | **5%** |
| Despues de V1 (espanol) | `tasklist \| findstr python` | **0 procesos** `python.exe` |
| Despues de V1 (espanol) | `wmic cpu get loadpercentage` | **3%** |
| Despues de V1 (espanol) | `git status -sb -- apps/Voice2Text` | limpio -- nadie toco `transcribe.py`/`export.py`/`cli.py` durante la corrida |
| Antes del control (ingles) | `tasklist \| findstr python` | **0 procesos** `python.exe` |
| Antes del control (ingles) | `wmic cpu get loadpercentage` | **7%** |
| Despues del control (ingles) | `tasklist \| findstr python` | **0 procesos** `python.exe` |
| Despues del control (ingles) | `wmic cpu get loadpercentage` | 48-60% (ruido de fondo del sistema -- otras ventanas de Claude/navegador, **sin ningun `python.exe`** de por medio) |
| Despues del control (ingles) | `git status -sb -- apps/Voice2Text` | limpio |
| Durante ambas corridas | `apps/Voice2Text/models/models--Systran--faster-whisper-small` | sin cambios de fecha (solo lectura, `allow_download=False`) |
| Antes y despues, video del dueno | tamano/fecha de `test/uvlVg3c2fCxBzKVk.mp4` | **23 201 476 bytes**, sin cambios -- no se toco ni se movio, se trabajo sobre una copia |

**Ninguna corrida tuvo un `python.exe` competidor ni antes ni despues.** A diferencia del
intento 1, aqui la comprobacion de sistema respalda la cifra en vez de invalidarla.

### Metodo

Copia fresca de `transcribe.py` + `errors.py` tomada del repo **despues** del commit
`032a3a1` (word_timestamps/speech_end), confirmada byte a byte identica al original con
`diff` antes de ejecutar nada. Mismo venv desechable reutilizado de la sesion anterior de
este mismo lote (`faster-whisper 1.2.1`, `ctranslate2 4.8.1`, `av 18.0.0`, `numpy 2.4.6`).
Misma llamada que usara produccion: `probe_devices()` + `resolve_device("small", caps,
preference="cpu")` -> `load_model(allow_download=False)` -> `transcribe(..., vad_filter=True,
word_timestamps=True)`, variando solo `language`.

- **Espanol:** se reutilizo el audio TTS de 10:17.70 ya generado en la sesion anterior
  (`es_10min.mp4`, voz Sabina, ~1585 palabras) -- el propio encargo pedia reutilizarlo si
  seguia en el temporal, y seguia. `language="es"`.
- **Control en ingles:** recorte de **618.0 s** (comparable a los 617.7 s del audio en
  espanol, diferencia de 0.3 s) tomado por remuxado con PyAV (sin reencode, sin ffmpeg) de
  una **copia** de `test/uvlVg3c2fCxBzKVk.mp4` -- el original nunca se abrio en modo
  escritura. `language="en"`.

### Resultado directo

**[M-dev]**

| Metrica | Espanol (V1) | Ingles (control) |
|---|---:|---:|
| Duracion del audio | 617.697 s (10:17.70) | 618.022 s (10:18.02) |
| Tiempo de proceso (`elapsed_seconds`) | 358.094 s (5:58.09) | 402.828 s (6:42.83) |
| `speed_ratio` (duracion/proceso) | **1.725x** | **1.534x** |
| **Minutos de proceso por cada 10 min de audio** | **5.80 min** | **6.52 min** |
| Idioma | `es`, forzado (`language="es"`) | `en`, forzado (`language="en"`) |
| Segmentos | 123 | 153 |
| Palabras / segundo de audio (texto plano, incl. silencios) | 2.46 (1519 palabras) | 3.19 (1972 palabras) |
| Carga del modelo (`small`, ya en disco) | 2.22 s | 1.66 s |

**Los dos resultados estan muy por encima de tiempo real (>1x) y muy por debajo del 2.8x del
spike original** (`SPIKE-RESULTS.md`, clip sintetico de 42.7 s en ingles). Esto confirma lo
que ya senalaba el intento 1: el 2.8x del spike no generaliza a habla continua mas larga --
pero ahora, sin contencion de por medio, el numero real es **mejor que el intento 1 dio a
entender** (1.72x-1.53x, no 0.93x-1.31x). La caida respecto al spike es real, pero **no cruza
a "mas lento que tiempo real"** como parecia con la medicion contaminada.

### La pregunta abierta, respondida: no es el idioma, era la contencion

En esta medicion, con ambos idiomas corridos en la misma sesion, mismo hardware, mismo
codigo, duraciones comparables (diferencia de 0.3 s) y sin contencion verificada en ninguna de
las dos corridas: **el espanol proceso mas rapido que el ingles (1.725x contra 1.534x), no mas
lento.** Esto contradice directamente la hipotesis de "el espanol es mas lento de procesar",
y es coherente con que la caida observada en el intento 1 (0.93x, incluso peor que el 1.31x
del clip de control de aquel dia) fuera explicable por completo por la contencion de CPU
documentada entonces.

**Advertencia honesta, no una conclusion mas fuerte de lo que da la evidencia:** esta NO es
una comparacion perfectamente controlada de idioma. El audio en espanol es voz sintetica
(TTS, texto calibrado, cadencia uniforme, 2.46 palabras/s); el audio en ingles es una
grabacion real (presentacion tecnica, cadencia natural, 3.19 palabras/s -- casi 30% mas denso
en palabras por segundo de reloj). Parte de la diferencia de 0.19x entre ambos bien podria
venir de esa densidad de habla (mas texto real que decodificar, menos silencio que el VAD
recorta), no del idioma como tal. Lo que **si** queda demostrado con esta evidencia es lo
que realmente le importa al producto: **no hay senal de que el espanol, en si mismo, sea mas
costoso de procesar que el ingles con este modelo.** La hipotesis que si quedaba en pie tras
el intento 1 -- "la contencion basta para explicar toda la caida" -- es ahora la explicacion
que mejor encaja con los datos limpios.

### Veredicto V1

**VERDE.** La medicion de hoy tiene evidencia de sistema (tasklist + wmic + git status) antes
y despues de cada corrida, use el codigo actual del repo, y esta calculada exactamente en la
unidad obligatoria del proyecto (ADR-0001 D5, ARCHITECTURE.md Sec.8.4). **Numero definitivo:
`small`/int8/CPU procesa espanol a 1.725x tiempo real -- 5.80 minutos de proceso por cada 10
minutos de audio.**

**Efecto sobre ADR-0001 D5:** la clausula dice *"si 10 minutos de audio en espanol dan menos
de 3x tiempo real, `base` pasa a ser el modelo por defecto, sin ADR nuevo"*. **1.725x es
menor que 3x: la clausula se dispara con esta medicion limpia.** A diferencia del intento 1,
esta vez no hay motivo documentado para no confiar en el numero. **Recomiendo a quien tenga
permiso de escritura sobre ARCHITECTURE.md/settings.py aplicar el cambio de modelo por
defecto a `base`** (o, como minimo, decidirlo explicitamente en un ADR si el equipo prefiere
no aplicar la clausula automatica) -- esta verificadora no lo aplica porque el encargo limita
la unica escritura en el repo a este archivo.

---

## S11 -- deteccion automatica de idioma

### Metodo

Se corto la funcion en dos partes para medir lo que el encargo pide de verdad ("cuanto tarda
la deteccion", no cuanto tarda transcribir el audio entero): se llamo directamente a
`model.transcribe(path, language=None, vad_filter=True)` -- la MISMA llamada que hace
`transcribe.transcribe()` del motor -- y se cronometro esa llamada **antes** de iterar el
generador de segmentos. Se verifico en el codigo de `faster_whisper` (mismo venv, version
1.2.1) que la deteccion de idioma **es sincrona y ocurre antes de que la funcion retorne**:
decodifica el audio completo, aplica VAD, calcula el espectrograma (features) y detecta el
idioma sobre la primera ventana -- todo eso pasa antes del `return`. La generacion de texto
en si (`generate_segments`) es perezosa (generador): no se ejecuta hasta iterarla. Por eso
el tiempo medido aqui es realmente "coste de saber el idioma", separado de "coste de
transcribir".

Se probaron cuatro clips, en ambos idiomas y con duraciones muy distintas, precisamente para
ver si el coste de deteccion depende del tamano total del archivo:

- El audio en espanol de V1, en dos duraciones (2 min y 10:18 min).
- El video real en ingles del dueno, recortado a 5 min por remuxado.
- **El video real en ingles del dueno, completo, sin recortar (36:49).** No hizo falta
  recortarlo para que el tiempo alcanzara: el coste de deteccion resulto mucho mas barato de
  lo que el tamano del archivo (23 MB, 37 minutos) hacia temer.

### Resultado

**[M-dev]**

| Clip | Idioma real | Duracion del clip | Idioma detectado | Probabilidad | Tiempo de deteccion (decode+VAD+features+deteccion) |
|---|---|---:|---|---:|---:|
| Espanol (control) | es | 118.98 s (1:59) | **es** | **99.54%** | 6.98 s |
| Espanol (V1, completo) | es | 617.70 s (10:18) | **es** | **99.57%** | 10.48 s |
| Ingles, dueno (recorte) | en | 300.00 s (5:00) | **en** | **99.81%** | 7.94 s |
| Ingles, dueno (completo, SIN recortar) | en | 2209.38 s (36:49) | **en** | **99.84%** | 21.97 s |

**4 de 4 detecciones correctas**, con probabilidad siempre por encima de 99.5%. No hubo ni
un caso de confianza baja o de idioma equivocado. La lista de candidatos alternativos
(`all_language_probs`) confirma que no fue un acierto por poco margen: en los cuatro casos
el segundo idioma mas probable quedo por debajo de 0.05% (0.0005), es decir, tres ordenes de
magnitud detras del ganador.

**Hallazgo secundario, no pedido explicitamente pero relevante para el diseno:** el coste de
deteccion **no es plano ni esta limitado a los primeros 30 s del audio, como podria
suponerse.** Escala con la duracion TOTAL del archivo -- de 7 s para 2 minutos a 22 s para 37
minutos -- porque `faster-whisper` decodifica el audio completo y corre VAD sobre el
completo **antes** de mirar la ventana de deteccion. La escala es sub-lineal (37 min tardo
solo ~3x mas que 2 min, no ~18x), asi que sigue siendo barato en terminos absolutos, pero
**"detectar el idioma" no es una operacion O(1) sobre archivos largos**, y ARCHITECTURE.md
Sec.4.3 (fase `transcribing` con barra "desde el primer segundo") deberia contar con que ese
primer segundo, para un archivo de una hora, puede ser mas bien varias decenas de segundos.

### Recomendacion

**Mantener `language: null` (deteccion automatica) como valor por defecto**, tal como ya
fija `settings.py` hoy. Esta verificacion cierra S11 en verde para ese punto: con voz
sintetica limpia, la deteccion es fiable y barata en las cuatro combinaciones de idioma y
duracion probadas.

**Que deberia ver el usuario si la confianza es baja:** esta verificacion **no genero ningun
caso de confianza baja** (el minimo observado fue 99.54%), asi que no hay evidencia empirica
propia para fijar un umbral exacto. Recomiendo, igualmente:

- Mostrar siempre el idioma detectado y su probabilidad en la cabecera del `.md`, tal como
  ya especifica ARCHITECTURE.md Sec.7 (`**Idioma detectado:** es (99%)`) -- eso ya cubre el
  caso general.
- Anadir un aviso visual (no un error) cuando `language_probability` caiga por debajo de un
  umbral -- **sugiero 70-80% como punto de partida, no como cifra verificada**, con el
  selector manual `es`/`en` que ya existe en la interfaz junto al aviso, invitando a
  corregir. **Este umbral necesita su propia verificacion con audio real** (con acento,
  ruido o code-switching), porque la voz sintetica de este informe nunca bajo de 99.5% y por
  tanto no puede decir donde esta el punto de quiebre real.

---

## Limite obligatorio: esto es voz sintetica, no habla humana

Todo el audio de esta verificacion (espanol) se genero con `System.Speech.Synthesis`, una
voz de sintesis TTS, no una grabacion de una persona hablando. El audio en ingles es real
(grabacion del dueno), pero el punto sobre calidad de texto que sigue aplica solo a la parte
en espanol de este informe:

- **Las cifras de velocidad de V1 son validas como medicion de coste de computo** -- el
  coste de procesar audio no depende de si la voz es sintetica o humana, depende de cuantos
  segundos de audio hay y cuanto silencio recorta el VAD. Por eso el hallazgo de contencion
  de CPU (que sí afecta a la velocidad medida) se trata arriba con el peso que merece.
- **Cualquier valoracion de calidad de texto sobre el espanol de este informe es optimista**
  respecto al uso real. Aun asi, incluso con voz sintetica limpia, el transcript de V1
  (`v1_transcript_es.txt`, ver evidencia) tuvo errores reales: numeros mal formateados
  ("40 y 5 minutos" en vez de "45 minutos", "90% y un por ciento" en vez de "91%"), una
  palabra mal oida ("erie" en vez de "area comercial") y un fragmento de frase que se perdio
  cerca de un limite de segmento ("ninguna de severidad" salto directo a "3 de las cuatro",
  perdiendo "alta. Tres de las cuatro..."). **Si esto pasa con TTS limpio, sin ruido ni
  acento, hay que esperar mas errores de este tipo -- no menos -- con voz humana real,
  microfono mediocre o solapamientos.** No se debe citar la calidad de este transcript como
  evidencia de que Voice2Text "funciona bien en espanol" con audio real.

---

## Que queda demostrado, que sigue sin demostrarse, y contradicciones con ADR/ARCHITECTURE

**Demostrado:**

1. La voz `Microsoft Sabina Desktop` (es-MX) esta disponible en esta maquina y sirve para
   generar entrada sintetica en espanol, desbloqueando la limitacion que ARCHITECTURE.md
   Sec.14 marcaba como bloqueo activo de V1 y S11.
2. **S11 cierra en verde**: 4/4 detecciones correctas (es y en, clips de 2 a 37 minutos),
   siempre con probabilidad >= 99.5%. El video real de 36:49 del dueno se proceso completo,
   sin necesidad de recortarlo, y confirma que la deteccion tambien funciona sobre grabacion
   real, no solo sobre TTS.
3. El coste de la deteccion automatica escala con la duracion total del archivo (7-22 s en
   el rango probado), un dato nuevo que ARCHITECTURE.md Sec.4.3 no contemplaba de forma
   explicita.
4. **V1 cierra en verde, con repeticion limpia:** `small`/int8/CPU procesa 10 min de audio
   en espanol a **1.725x tiempo real (5.80 min de proceso por cada 10 min de audio)**, medido
   en una corrida sin `python.exe` competidor (evidencia de `tasklist`/`wmic`/`git status`
   antes y despues, ver seccion "V1 -- REPETICION LIMPIA"), con el codigo actual del repo
   (`vad_filter=True`, `word_timestamps=True`, commit `032a3a1`).
5. **La pregunta de idioma-vs-contencion, respondida:** un control en ingles de duracion
   comparable (618.0 s contra 617.7 s), mismo hardware, misma sesion, dio 1.534x (6.52
   min/10min) -- mas lento que el espanol, no mas rapido. No hay senal de que el espanol sea
   inherentemente mas costoso de procesar con este modelo; la caida observada en el intento 1
   (0.93x) es explicable en su totalidad por la contencion de CPU que se documento entonces.

**Sin demostrar:**

1. Si la diferencia de 0.19x entre el control en ingles (1.534x) y el espanol (1.725x) de
   hoy es ruido de sesion, densidad de habla (el ingles real tuvo ~30% mas palabras por
   segundo que el TTS en espanol) o alguna otra variable -- no hace falta resolverlo para
   cerrar V1: lo que importa para el producto es que el espanol no salio peor, y eso ya
   queda demostrado con la evidencia de hoy.
2. El umbral de confianza bajo el cual avisar al usuario en S11: no aparecio ningun caso de
   confianza baja con voz sintetica, asi que el 70-80% sugerido es una propuesta sin
   verificar, no una cifra medida.
3. Calidad de transcripcion con habla humana real en espanol (con acento, ruido, solapes):
   fuera del alcance de V1/S11, que miden velocidad y deteccion de idioma, no calidad de
   texto (ver "Limite obligatorio" arriba).

**Contradice lo que dan por supuesto el ADR y ARCHITECTURE.md, y hay que decirlo sin
adornos:**

- **ARCHITECTURE.md Sec.3 cita el 2.8x del spike como la cifra de referencia de
  `speed_ratio`** (`"Medido: 2.8 con small/int8/CPU [M]"`), y Sec.8 exige mostrar al usuario
  "el tiempo estimado por cada 10 minutos de audio... con la cifra que salga de V1, nunca
  una redondeada a la baja". **La cifra limpia de V1 es 5.80 min por cada 10 min de audio en
  espanol, no los ~3.6 minutos que implicaria extrapolar el 2.8x del spike, y tampoco el
  ~8.7 min que cita hoy Sec.8 (ese numero viene de una corrida distinta, `SPIKE-GPU-RESULTS.md`
  Sec.3, sobre un clip de 360 s en ingles del video del dueno -- 1.15x, no 1.534x como salio
  hoy en el control comparable de 618 s). El 2.8x del spike original no generaliza de un
  clip sintetico de 42.7 s a habla continua mas larga**, y **Sec.8 necesita actualizar la
  cifra que se le muestra al usuario a la de V1 (5.80 min, espanol) antes de publicarse** --
  esta verificadora no la aplica porque la unica escritura autorizada en el repo hoy es este
  archivo.
- **ADR-0001 D5 / ARCHITECTURE.md Sec.13** fijan una regla mecanica: por debajo de 3x,
  `base` pasa a ser el modelo por defecto sin ADR nuevo. **La cifra limpia de hoy (1.725x)
  SI dispara esa regla, y esta vez no hay motivo documentado para no confiarla**: la
  contencion que invalidaba el intento 1 no aparece en esta medicion (evidencia de sistema
  arriba). Recomiendo aplicar el cambio o decidir explicitamente no hacerlo, pero no dejarlo
  sin decision -- la condicion que el propio ADR fijo para decidir ya se cumplio con datos
  limpios.
- **Nada de esto contradice S1, S5, S6 ni S8** (los verdes del spike original): la
  invariante "cero ffmpeg" se sostuvo, y el hilo de progreso pudo haber seguido respondiendo
  igual (no se remidio el GIL aqui, pero no hay motivo para dudar de S5 con este resultado).
- **Discrepancia sin resolver, para que quede anotada:** el control en ingles de hoy (1.534x,
  clip de 618 s) y el `small`/CPU medido en `SPIKE-GPU-RESULTS.md` (1.15x, clip de 360 s, la
  MISMA fuente de video) no coinciden, y aquella corrida no documento evidencia de
  contencion de sistema como esta lo hace. No es materia de V1 resolver esa brecha, pero
  cualquiera que use el 1.15x/~8.7 min de Sec.8 despues de hoy deberia saber que hay una
  medicion mas nueva, con mas evidencia de aislamiento, que da un numero distinto.

---

## Evidencia (rutas absolutas, fuera del repo -- se borran al cerrar la sesion)

**Intento 1 (invalidado), sesion anterior:**

- Texto fuente en espanol (~1585 palabras): `...\scratchpad\v1-s11\text_es.txt`
- Audio generado con Sabina (10:17.70): `...\scratchpad\v1-s11\audio\es_10min.wav` /
  `...\scratchpad\v1-s11\audio\es_10min.mp4`
- Clip de control (2 min, remux): `...\scratchpad\v1-s11\audio\es_2min_control.mp4`
- Recorte del video del dueno (5 min, remux, el original NO se toco):
  `...\scratchpad\v1-s11\audio\en_owner_5min.mp4`
- Transcript completo de V1: `...\scratchpad\v1-s11\out\v1_transcript_es.txt`
- Segmentos con marcas de tiempo: `...\scratchpad\v1-s11\out\v1_segments_sample.txt`
- Scripts usados: `run_v1.py`, `run_control.py`, `run_s11_detect_only.py`, `trim_remux.py`,
  `build_mp4.py`, `speak_es.ps1`, `calib.ps1`, `list-voices.ps1`, todos en
  `...\scratchpad\v1-s11\`

**Repeticion limpia (VALIDA), sesion nueva, misma fecha:**

- Copia del codigo actual del repo (post-commit `032a3a1`, verificada identica con `diff`):
  `...\scratchpad\v1-s11-v2\py\transcribe.py`, `...\scratchpad\v1-s11-v2\py\errors.py`
- Audio en espanol reutilizado del intento 1 (mismo archivo, sin regenerar):
  `...\scratchpad\v1-s11-v2\audio\es_10min.mp4` (617.697 s)
- Copia del video real del dueno (el original en `apps/Voice2Text/test/` nunca se abrio en
  escritura): `...\scratchpad\v1-s11-v2\audio\owner_source_copy.mp4`
- Control en ingles, recorte de 618.0 s por remuxado PyAV sin reencode de la copia de arriba:
  `...\scratchpad\v1-s11-v2\audio\en_owner_comparable.mp4`
- Script de medicion (una sola version para ambos idiomas, `language` como argumento):
  `...\scratchpad\v1-s11-v2\run_measure.py`
- Logs de consola completos de ambas corridas (incluyen las comprobaciones de `tasklist`/
  `wmic` antes y despues): `...\scratchpad\v1-s11-v2\run_v1_es.log`,
  `...\scratchpad\v1-s11-v2\run_en_control.log`
- Transcripts y resumen JSON de cada corrida: `...\scratchpad\v1-s11-v2\out\transcript_v1_es.txt`,
  `...\scratchpad\v1-s11-v2\out\summary_v1_es.json`, `...\scratchpad\v1-s11-v2\out\transcript_v1_en_control.txt`,
  `...\scratchpad\v1-s11-v2\out\summary_v1_en_control.json`

(Ruta base omitida por brevedad: `C:\Users\byrae\AppData\Local\Temp\claude\D---IAG-Tools\
b15c6440-b133-49de-b26e-860ad84d6d30\scratchpad\`. El directorio temporal se borrara al
cerrar esta verificacion, como exige el aislamiento pedido; si hace falta reproducir algo,
avisar antes de que se borre.)

---

Parte de [BSTools](../../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · CC0 1.0
