---
title: "Verificacion V1 (velocidad en espanol) y S11 (deteccion automatica de idioma)"
status: completado, con una contaminacion metodologica declarada en V1
fecha: 2026-08-10
autor: Veritas (QA) -- verificacion independiente, sobre copias fuera del repo
---

# Verificacion en espanol -- V1 y S11 (lote 1.b)

> **BLUF:** S11 queda cerrado en verde: la deteccion automatica de idioma acierta espanol e
> ingles con >99.5% de confianza en los cuatro clips probados, incluido el video real de
> 36:49 del dueno sin recortar. **V1 NO queda cerrado en verde.** Se obtuvo una cifra real de
> velocidad en espanol (algo que no existia hasta hoy), pero la maquina tenia **otro agente
> corriendo transcripciones de faster-whisper en paralelo durante toda la medicion**
> (evidencia de proceso incluida abajo), lo que degrado el resultado de forma medible y no
> separable del efecto de idioma/duracion que V1 queria aislar. **Recomiendo no fijar
> `base` como modelo por defecto (ADR-0001 D5) ni cerrar V1 con esta cifra** hasta repetir la
> medicion en una maquina sin otros procesos de faster-whisper activos.

---

## Veredicto en una tabla

| # | Verificacion | Veredicto |
|---|---|---|
| **Voz Sabina** | Confirmar `Microsoft Sabina Desktop` (es-MX) disponible para `System.Speech.Synthesis` | **VERDE** -- reconfirmado por esta maquina, no solo por lo dicho en el encargo (ver abajo) |
| **V1** | Velocidad real, 10 min de audio en espanol, `small`/int8/CPU/`language="es"` | **AMARILLO -- medido, pero contaminado.** Cifra obtenida: `speed_ratio` 0.93x (mas lento que tiempo real). No es comparable de forma limpia con el 2.8x del spike: hubo contencion de CPU documentada durante toda la corrida |
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

## V1 -- velocidad real con audio en espanol

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

**Sin demostrar:**

1. **La velocidad real de V1 en condiciones limpias.** El numero obtenido (0.93x en el clip
   de 10 min, 1.31x en el de control de 2 min) esta contaminado por contencion de CPU con
   otro agente trabajando en paralelo en esta misma maquina, con evidencia de proceso
   (PID, tiempo de CPU acumulado, carga de sistema) documentada arriba. **Hace falta una
   repeticion en una maquina sin otros procesos de faster-whisper activos** antes de tratar
   cualquiera de estas cifras como definitiva.
2. Si el factor sobre tiempo real cambia genuinamente por audio largo o por idioma -- la
   pregunta original de V1 -- sigue sin poder responderse: la contencion es una explicacion
   alternativa suficiente para toda la caida observada, y no se puede descartar con los
   datos de hoy.
3. El umbral de confianza bajo el cual avisar al usuario en S11: no aparecio ningun caso de
   confianza baja con voz sintetica, asi que el 70-80% sugerido es una propuesta sin
   verificar, no una cifra medida.

**Contradice lo que dan por supuesto el ADR y ARCHITECTURE.md, y hay que decirlo sin
adornos:**

- **ARCHITECTURE.md Sec.3 cita el 2.8x del spike como la cifra de referencia de
  `speed_ratio`** (`"Medido: 2.8 con small/int8/CPU [M]"`), y Sec.8 exige mostrar al usuario
  "el tiempo estimado por cada 10 minutos de audio... con la cifra que salga de V1, nunca
  una redondeada a la baja". La cifra que salio de V1 hoy (incluso en su version menos
  contaminada, el control de 2 minutos) implica **~7.6 a ~10.8 minutos de proceso por cada
  10 minutos de audio**, no los ~3.6 minutos que implicaria extrapolar el 2.8x del spike.
  Si esta brecha se confirma en una repeticion limpia -- y no es pura contencion --, el
  2.8x del spike **no generaliza** de un clip de 42.7 s en ingles a habla continua mas larga
  en espanol, y **la copia de la pantalla de primer arranque (Sec.8) necesitaria la cifra
  real, no el 2.8x**, antes de publicarse.
- **ADR-0001 D5 / ARCHITECTURE.md Sec.13** fijan una regla mecanica: por debajo de 3x,
  `base` pasa a ser el modelo por defecto sin ADR nuevo. La cifra de hoy dispara esa regla,
  pero **no deberia aplicarse todavia**: la contencion de CPU documentada es motivo
  suficiente para no confiar en el numero como base de una decision de producto.
- **Nada de esto contradice S1, S5, S6 ni S8** (los verdes del spike original): la
  invariante "cero ffmpeg" se sostuvo, y el hilo de progreso pudo haber seguido respondiendo
  igual (no se remidio el GIL aqui, pero no hay motivo para dudar de S5 con este resultado).

---

## Evidencia (rutas absolutas, fuera del repo -- se borran al cerrar la sesion)

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

(Ruta base omitida por brevedad: `C:\Users\byrae\AppData\Local\Temp\claude\D---IAG-Tools\
b15c6440-b133-49de-b26e-860ad84d6d30\scratchpad\`. El directorio temporal se borrara al
cerrar esta verificacion, como exige el aislamiento pedido; si hace falta reproducir algo,
avisar antes de que se borre.)

---

Parte de [BSTools](../../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · CC0 1.0
