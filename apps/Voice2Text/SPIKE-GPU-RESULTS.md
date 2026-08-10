---
title: "Spike tecnico de GPU — Voice2Text, GeForce GTX 1050 Ti (peor caso del parque, no el hardware de destino)"
status: completado
fecha: 2026-08-10
---

# Spike tecnico de GPU — Voice2Text

Responde con cifras, no con supuestos, si compensa ofrecer GPU como opcion en Voice2Text y a que costo.
No se escribio codigo de produccion: todo corrio en un venv desechable fuera del repo
(`%TEMP%\v2t-gpu-spike`), borrado al terminar. La unica escritura de este spike en el repositorio es este
archivo.

**Maquina:** Windows 10 Pro, Python 3.11.9. **GPU:** NVIDIA GeForce GTX 1050 Ti, 4096 MiB VRAM, driver
560.94, CUDA (nivel de driver) 12.6, arquitectura Pascal, **compute capability 6.1** — verificado por
direccion antes de empezar. **Esta tarjeta es el peor caso del parque de hardware, no el objetivo final**;
donde haga falta extrapolar a una RTX 3080 de 10 GiB se marca `[E]` y se explica el porque.

**Convencion de etiquetas de este documento** (pedida explicitamente por la coordinacion, distinta a la del
spike de CPU porque aqui no intervino direccion verificando el hardware con sus propias manos):

| Marca | Significado |
|---|---|
| **[M-dev]** | Medido hoy, en esta sesion, en esta maquina, por quien escribe este documento. Reproducible con los comandos exactos que se citan |
| **[E]** | Estimado o extrapolado, sin medir directamente |
| **[O]** | Observacion fechada sobre el comportamiento de un tercero (pip, CTranslate2, el driver WDDM de Windows) — puede cambiar sin aviso en otra version |

Un numero sin marca es un error de redaccion.

---

## Veredicto en una tabla

| # | Pregunta | Veredicto |
|---|---|---|
| 1 | Peso real de las dependencias CUDA | **VERDE** — anaden **~2,0-2,1 GB [M-dev]**, en el extremo bajo de la horquilla de 2-2,5 GB que estimaba direccion |
| 2 | ?Funciona de verdad en Pascal? | **VERDE con matiz** — `int8` y `float32` funcionan y transcriben correctamente. `float16` **falla limpio por hardware**, no por bug (ver seccion 2) |
| 3 | Velocidad comparada con CPU, mismo audio | **VERDE, con margen amplio** — 6,9x a 20,7x mas rapido que CPU segun el modelo, muy por encima del umbral de 3x que fijo Kronos |
| 4 | VRAM y que cabe en 4 GiB | **VERDE para `small`/`medium`/`large-v3-turbo` en int8; ROJO para `large-v3`** (no cabe, `CUDA out of memory` limpio) |
| 5 | Degradacion limpia sin librerias CUDA | **AMARILLO** — el fallo **es** capturable, pero **no donde uno esperaria**: la construccion del modelo miente (dice que si), el fallo real llega en la primera transcripcion |
| Extra | `medium`/`float32` en GPU | **NO CONCLUYENTE** — la corrida no termino a tiempo para la entrega; hay una hipotesis fundada de por que (ver seccion 4) |

**Recomendacion a direccion, adelantada:** **GPU como instalador aparte, opcional, nunca por defecto.**
Argumento completo en la seccion final.

---

## 0. Metodologia y honestidad sobre el audio usado

El spike de CPU (`SPIKE-RESULTS.md`) uso un `.mp4` sintetico generado con voz SAPI que se borro junto con su
venv al terminar aquel spike — no quedaba ningun rastro que reutilizar. Para no fabricar una comparacion
falsa, este spike hizo dos cosas:

1. **Regenero un clip sintetico casi identico** (mismo texto, misma voz `Microsoft David Desktop`, mismo
   metodo PyAV) para las primeras pruebas de humo, con la duracion resultante en 34,64 s en vez de los
   42,69 s originales — la sintesis de voz no es determinista al 100 % entre corridas.
2. **Encontro un video real ya presente en `apps/Voice2Text/test/`** (`uvlVg3c2fCxBzKVk.mp4`, 2209,4 s = 36,8
   min, conferencia en ingles, video `h264` 480x270 + audio `aac` 44,1 kHz mono) y lo uso como **fuente unica
   para todas las comparaciones de velocidad de la seccion 3 en adelante**, sin tocarlo ni moverlo — se leyo
   con PyAV y se extrajeron **copias de audio** (`.wav`, mono, mismo sample rate) de duraciones fijas
   (360 s, 120 s, 60 s) hacia el directorio de trabajo temporal, nunca escribiendo sobre el original.

**Por que duraciones distintas segun el modelo/dispositivo** (360 s para GPU y para `small`/CPU, 120 s para
`medium`/CPU, 60 s para `large-v3-turbo`/CPU): en CPU, `medium` y `large-v3-turbo` corren por debajo de
tiempo real (ver seccion 3), y con el clip completo de 360 s cada corrida habria tardado 15-20 minutos. La
coordinacion pidio explicitamente no dejar que una sola medicion bloquee la entrega. **El RTF (factor sobre
tiempo real) no depende de la duracion del clip** una vez amortizado el costo fijo de carga — que aqui se
reporta aparte, por eso la comparacion sigue siendo valida aunque las duraciones no coincidan exactamente.
Se marca en cada fila de la tabla que duracion se uso.

**Idioma: sigue sin haber voz SAPI en espanol en esta maquina** (mismo hallazgo que el spike de CPU). El
video real usado es en ingles. **Este spike no dice nada nuevo sobre la calidad de transcripcion en
espanol**; mide unicamente el mecanismo y la velocidad de la ruta GPU, que es agnostica al idioma (la GPU
ejecuta la misma matriz de pesos sin importar que idioma se este decodificando). Si direccion quiere validar
calidad en espanol sobre GPU, es un spike aparte.

**Comando de instalacion CUDA, exacto, reproducible:**

```
py -3 -m venv v2t-gpu-spike
v2t-gpu-spike\Scripts\python.exe -m pip install faster-whisper
v2t-gpu-spike\Scripts\python.exe -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

---

## 1. Peso real de las dependencias CUDA

**faster-whisper 1.2.1** resolvio **CTranslate2 4.8.1** — version vigente en PyPI hoy. Su metadata
(`ctranslate2-4.8.1.dist-info/METADATA`) declara compatibilidad con **CUDA 12.4**, pero **no exige por pip**
ninguna libreria CUDA como dependencia**: `cublas` y `cudnn` son responsabilidad del usuario, instalados
aparte.

**Venv solo-CPU** (`faster-whisper` sin nada de GPU): **293 MB [M-dev]**.

**Al anadir `nvidia-cublas-cu12` + `nvidia-cudnn-cu12`**, pip resolvio automaticamente una tercera pieza que
direccion no habia nombrado — `nvidia-cuda-nvrtc-cu12` (compilacion JIT, dependencia transitiva de
`cublas`)**:

```
Collecting nvidia-cublas-cu12
Collecting nvidia-cudnn-cu12
Collecting nvidia-cuda-nvrtc-cu12 (from nvidia-cublas-cu12)
Successfully installed nvidia-cuda-nvrtc-cu12-12.9.86 nvidia-cublas-cu12-12.9.2.10 nvidia-cudnn-cu12-9.24.0.43
```

| Paquete | Version resuelta hoy | Peso en disco [M-dev] |
|---|---|---:|
| `nvidia-cublas-cu12` | 12.9.2.10 | 736 MiB (772 MB) |
| `nvidia-cudnn-cu12` | 9.24.0.43 | 1071 MiB (1123 MB) |
| `nvidia-cuda-nvrtc-cu12` (transitiva, no pedida a mano) | 12.9.86 | 178 MiB (187 MB) |
| **Subtotal carpeta `nvidia/`** | | **1986 MiB (~2,08 GB)** |
| **Venv completo tras instalar CUDA** | | **2278 MiB (~2,39 GB)** |

**Confirma la estimacion de direccion (~2-2,5 GB), en el extremo bajo**: ~2,0-2,1 GB medidos frente al piso
de 2 GB estimado. **VERDE.**

**Riesgo operativo que no estaba en la lista de preguntas y conviene anotar** `[O]`: **`pip install
ctranslate2` no exige ninguna version de `cublas`/`cudnn`**, y CTranslate2 cambio de cuDNN 8 a cuDNN 9 en su
version 4.5 (dato historico conocido del proyecto, no verificado hoy con codigo). Hoy pip resolvio
`cudnn-9.24` para `ctranslate2==4.8.1`, coherente. **Pero si en el futuro `requirements.txt` fija una
version vieja de `ctranslate2` (por ejemplo por un pin de seguridad) sin fijar tambien la version de
`nvidia-cudnn-cu12`, pip instalara igual la ultima cuDNN 9.x sin quejarse — el choque de ABI solo aparece en
tiempo de ejecucion**, con el mismo tipo de error que se documenta en la seccion 5 (`Library ... not found or
cannot be loaded`), no en tiempo de instalacion. Si algun dia se escribe un `requirements-gpu.txt`, **las dos
versiones deben fijarse juntas**, nunca por separado.

---

## 2. ?Funciona de verdad en Pascal?

**Si, con `int8` y `float32`. `float16` esta bloqueado por el propio CTranslate2, no falla a medias.**

Con las DLL de `cublas`/`cudnn` localizables (anadiendo sus carpetas al `PATH` del proceso — ver seccion 5,
esto **no** ocurre solo), se pregunto a CTranslate2 que tipos de computo soporta esta GPU concreta:

```python
import ctranslate2
ctranslate2.get_cuda_device_count()                              # -> 1
ctranslate2.get_supported_compute_types('cuda', device_index=0)  # -> {'int8', 'float32', 'int8_float32'}
```

**`float16` e `int8_float16` no estan en esa lista.** Al forzarlo de todas formas:

```python
WhisperModel('small', device='cuda', compute_type='float16')
```

```
ValueError: Requested float16 compute type, but the target device or backend do not support
efficient float16 computation.
```

**Esto es exactamente la distincion que pedia la coordinacion, y la respuesta es clara: es hardware, no
codigo ni libreria.** CTranslate2 **consulta la compute capability real de la tarjeta** (Pascal / 6.1 no
tiene nucleos tensor de FP16 eficientes — solo aritmetica FP16 "empaquetada" sin aceleracion dedicada) y
**rechaza el modo antes de tocar un solo peso**, en la construccion del modelo, no a mitad de una
transcripcion. No es una degradacion silenciosa a "lento": es un `ValueError` inmediato y legible. **Esta
misma libreria, en una GPU Ampere (RTX 3080, compute capability 8.6, con nucleos tensor FP16 reales),
deberia devolver `float16` en la lista de tipos soportados** — es una prediccion `[E]`, no medida aqui, pero
respaldada por como CTranslate2 decide (consulta la arquitectura real de la tarjeta, no un numero de
version de CUDA).

**Transcripcion real, confirmada con `int8` y con `float32`**, sobre el video real (ver seccion 3 para los
tiempos): el texto transcrito coincide palabra por palabra con lo que dice el video (verificado a ojo sobre
los primeros segmentos), sin artefactos atribuibles al modo de computo.

**Veredicto: VERDE con matiz.** `int8`/`float32` funcionan de verdad en Pascal. `float16` no es una opcion en
esta tarjeta, **por diseno de CTranslate2, no por un defecto que arreglar**.

---

## 3. Velocidad comparada, mismo audio real, misma sesion

Todas las filas usan `uvlVg3c2fCxBzKVk.mp4` (ver seccion 0), `language="en"`, `vad_filter=True`. Carga y
transcripcion medidas por separado.

| Modelo | Dispositivo | `compute_type` | Audio usado | Carga [M-dev] | Transcripcion [M-dev] | **RTF [M-dev]** |
|---|---|---|---:|---:|---:|---:|
| `small` | CPU | int8 | 360,0 s | 3,72 s | 314,53 s | **1,15x** |
| `small` | CUDA | int8 | 360,0 s | 4,28 s | 45,34 s | **7,94x** |
| `small` | CUDA | float32 | 360,0 s | 4,34 s | 46,75 s | **7,70x** |
| `small` | CUDA | float16 | — | — | — | **falla al construir** (ValueError, hardware — seccion 2) |
| `medium` | CPU | int8 | 120,0 s | 17,42 s | 397,80 s | **0,30x** |
| `medium` | CUDA | int8 | 360,0 s | 9,44 s | 96,45 s | **3,73x** |
| `medium` | CUDA | float32 | 360,0 s | — | — | **NO CONCLUYENTE** (seccion 4) |
| `medium` | CUDA | float16 | — | — | — | **falla al construir** (mismo motivo que `small`, no repetido) |
| `large-v3-turbo` | CPU | int8 | 60,0 s | 11,65 s | 175,22 s | **0,34x** |
| `large-v3-turbo` | CUDA | int8 | 360,0 s | 85,15 s¹ | 51,10 s | **7,05x** |
| `large-v3` | CUDA | int8 | 120,0 s | ok | **falla en `generate()`** | `CUDA out of memory` (seccion 4) |
| `large-v3` | CPU | — | — | — | — | **no medido** (ver nota) |

¹ Incluye la descarga del modelo (1,6 GB) la primera vez; con el modelo ya en cache, la carga de `medium`
mostro 7,3-9,4 s en corridas repetidas — se puede tomar **~5-10 s** como costo de carga en frio (peso ya en
disco) para modelos de este tamano en esta maquina.

**`large-v3` en CPU: no medido, y es una omision deliberada, no un descuido.** Con `medium` ya en 0,30x y
`large-v3-turbo` en 0,34x, un modelo aun mas grande en CPU cae claramente por debajo de 0,3x — habria exigido
minutos por cada minuto de audio solo para un numero que ya se puede acotar por interpolacion `[E]`: **entre
0,15x y 0,3x**, es decir, entre 3 y 7 veces mas lento que el propio audio. No cambia ninguna conclusion:
sirve para confirmar que en CPU ese modelo es impracticable, cosa que ya se sabe sin necesitar el numero
exacto.

**Factor de mejora GPU sobre CPU, mismo modelo `[M-dev]`:**

| Modelo | CPU RTF | GPU RTF (int8) | **Mejora** |
|---|---:|---:|---:|
| `small` | 1,15x | 7,94x | **6,9x** |
| `medium` | 0,30x | 3,73x | **12,4x** |
| `large-v3-turbo` | 0,34x | 7,05x | **20,7x** |

**Las tres mejoras superan con margen amplio el umbral de 3x que fijo Kronos antes de ver resultados.** No
es un resultado al filo: la GPU no es "algo mejor", es entre 7 y 21 veces mas rapida segun el modelo, en la
tarjeta mas floja del parque.

**Dato curioso que vale la pena anotar, no una anomalia a corregir:** `large-v3-turbo` (7,05x) es **mas
rapido en GPU que `medium`** (3,73x), a pesar de tener casi el triple de parametros (809 M vs 244 M... perdon,
`small` tiene 244 M; `medium` tiene 769 M, `large-v3-turbo` 809 M). La explicacion mas probable **`[E]`**:
`large-v3-turbo` reduce su decodificador a 4 capas (frente a las 24 de `medium` y `large-v3`), y en GPU el
decodificador —que corre token a token, secuencial, sin poder paralelizar tanto como el codificador— suele
ser el cuello de botella real, no el numero total de parametros. No se investigo mas a fondo: no cambia
ninguna recomendacion de este documento, pero es relevante para la seccion 6 (extrapolacion).

---

## 4. VRAM: lo que cabe y lo que no en 4 GiB

**Lo primero, y direccion tenia razon en preguntarlo: el escritorio de Windows ya esta usando la GPU.**

```
nvidia-smi --query-gpu=memory.total,memory.used,memory.free --format=csv
4096 MiB, 459 MiB, 3546 MiB     (medido en reposo, antes de cargar ningun modelo)
```

**VRAM realmente disponible de partida: ~3546-3630 MiB, no 4096 MiB [M-dev].** El compositor de escritorio
de Windows (WDDM) y el resto de procesos que ya tocan la GPU (se ve en `nvidia-smi`: `explorer.exe`,
`msedgewebview2.exe`, varias apps de UWP) se quedan con **~450-470 MiB de forma permanente**, midan lo que
midan los modelos.

**Picos de VRAM medidos durante carga + transcripcion** (muestreo de `nvidia-smi` cada ~0,25 s, se reporta el
**maximo**, no el promedio, como pidio la coordinacion):

| Modelo | `compute_type` | VRAM pico `[M-dev]` | ?Cabe en 4 GiB? |
|---|---|---:|---|
| `small` | int8 | 997-1314 MiB | Si, con mucho margen |
| `small` | float32 | 1662-2032 MiB | Si |
| `medium` | int8 | 2416 MiB | Si, ~1,5 GiB de margen |
| `medium` | float32 | **3881-3927 MiB, subiendo** | **NO CONCLUYENTE — ver abajo** |
| `large-v3-turbo` | int8 | 1575 MiB | Si, con margen amplio |
| `large-v3` | int8 | **3951 MiB, y luego `CUDA out of memory`** | **No** |

**`large-v3` en `int8`: falla limpio, y es un dato util, no un fallo del spike.** El modelo cargo bien
(los pesos en `int8` caben), pero `generate()` (la fase de decodificacion) revento con:

```
RuntimeError: CUDA failed with error out of memory
```

con un pico de 3951 MiB justo antes de la excepcion — practicamente toda la tarjeta, escritorio incluido.
**Excepcion clara, capturable, con un mensaje que un `except RuntimeError` distingue sin ambiguedad de la
falta de librerias (seccion 5).** `large-v3` **no es una opcion viable en una GTX 1050 Ti de 4 GiB**, ni
siquiera en el modo de computo mas liviano.

**`medium`/`float32`: NO CONCLUYENTE, con hipotesis fundada.** La corrida se lanzo, la VRAM subio hasta
3881-3927 MiB (dejando 78-170 MiB libres de los 4096 MiB totales) y, pasados mas de 13 minutos, **no habia
producido ningun resultado ni habia lanzado ninguna excepcion** — se interrumpio para no bloquear la entrega,
siguiendo la instruccion explicita de la coordinacion. **Hipotesis `[O]`, no confirmada con evidencia
adicional:** cuando la VRAM dedicada se agota casi del todo pero no del todo, el driver WDDM de Windows puede
recurrir a "memoria de GPU compartida" (parte de la RAM del sistema, accedida por PCIe) en vez de fallar de
inmediato — eso explicaria una corrida que no truena pero se arrastra a una fraccion de su velocidad normal,
en vez de un `CUDA out of memory` limpio como el de `large-v3`. **La distincion practica para el diseno:
quedarse justo al borde de la VRAM disponible en esta tarjeta no es un fallo ruidoso, es una degradacion
silenciosa a un rendimiento inaceptable** — mas peligroso que un error claro, porque no hay excepcion que
capturar. No se pudo confirmar la causa exacta hoy; si se retoma este spike, vale la pena repetir esta
corrida con un `timeout` explicito y monitorizando `memory.used` de Windows (RAM del sistema) en paralelo
para confirmar si de verdad hubo "spillover" a memoria compartida.

**Resumen de la seccion 4:** en una GTX 1050 Ti de 4 GiB, con el escritorio de Windows ya restando ~460 MiB,
**`small` y `large-v3-turbo` en `int8` caben con margen comodo; `medium` en `int8` cabe justo; `medium` en
`float32` y `large-v3` en cualquier modo estan fuera de rango** — el primero de forma sospechosamente lenta
en vez de con error, el segundo con un error limpio.

---

## 5. Degradacion limpia: la trampa esta en donde falla, no en si falla

**Hallazgo central de esta seccion, y es el mas importante para quien escriba el codigo de deteccion:**
**`WhisperModel(..., device="cuda")` no lanza ninguna excepcion aunque las librerias CUDA esten completamente
ausentes del sistema.**

Prueba, con `nvidia-cublas-cu12`/`nvidia-cudnn-cu12` **desinstalados** (venv recien creado, solo
`faster-whisper`):

```python
model = WhisperModel('small', device='cuda', compute_type='int8')
# LOADED OK (2,83 s) -- sin ningun error, sin ningun aviso
```

**El fallo real llega en la primera llamada a `transcribe()`**, dentro de `model.encode()`:

```
RuntimeError: Library cublas64_12.dll is not found or cannot be loaded
```

Con las librerias CUDA instaladas pero **sin anadir sus carpetas al `PATH` del proceso** (`pip install` las
deja en `site-packages/nvidia/*/bin`, pero no las publica en el `PATH` de Windows por si solo), **el mismo
error exacto vuelve a aparecer**, aunque `pip` haya dicho que la instalacion fue exitosa. Solo funciona
anadiendo explicitamente esas dos carpetas al `PATH` del proceso antes de importar `ctranslate2`:

```python
import os
os.environ["PATH"] = (
    r"...\site-packages\nvidia\cublas\bin" + os.pathsep +
    r"...\site-packages\nvidia\cudnn\bin" + os.pathsep +
    os.environ["PATH"]
)
```

**Y hay un tercer modo de fallo tardio, distinto del anterior: sin VRAM suficiente** (seccion 4), el error
tambien llega dentro de `transcribe()`, pero es otro tipo y otro mensaje:

```
RuntimeError: CUDA failed with error out of memory
```

**Los tres casos son `RuntimeError` capturable, ningun crash duro, ninguna violacion de acceso.** Pero
**ninguno de los dos primeros aparece donde alguien esperaria mirar** (la construccion del modelo), y **los
dos ultimos son indistinguibles por tipo de excepcion** (ambos `RuntimeError`) aunque tengan causas y
remedios completamente distintos — uno pide instalar/reparar las librerias, el otro pide un modelo mas
chico.

**Recomendacion concreta para la deteccion en tiempo de ejecucion, en orden de coste creciente:**

1. **`ctranslate2.get_cuda_device_count() > 0` no basta.** Esta llamada solo consulta el driver NVIDIA (ya
   presente si hay una tarjeta y `nvidia-smi` funciona), **no** si `cublas`/`cudnn` estan instalados ni
   cargables. Sirve como filtro rapido de "no hay ninguna GPU NVIDIA visible", nada mas.
2. **La unica comprobacion confiable es una "prueba de humo" real al arrancar**: construir `WhisperModel`
   con el modelo mas chico disponible (`tiny`/`base`) en `device="cuda"` y ejecutar `transcribe()` sobre un
   clip trivial (medio segundo, sintetico, generado en memoria), envuelto en un `try/except RuntimeError`.
   Cuesta unos pocos segundos, una sola vez por sesion, y es la unica forma real de saber si las DLL cargan
   *y* si hay VRAM para lo minimo.
3. **Distinguir el texto del `RuntimeError` para dar el mensaje correcto**, no solo capturar y caer a CPU en
   silencio: si el mensaje contiene `"is not found or cannot be loaded"` es un problema de instalacion
   (falta el paquete GPU o el `PATH`); si contiene `"out of memory"` es un problema de VRAM insuficiente para
   ese modelo concreto — la solucion de cada uno es distinta y el usuario deberia verla distinta.
4. **Nunca tratar una construccion exitosa de `WhisperModel(device="cuda")` como confirmacion de que la GPU
   funciona.** Es la trampa concreta que este spike encontro: el codigo "parece" andar hasta que llega la
   primera transcripcion real.

**Veredicto: AMARILLO, no verde limpio.** La degradacion es capturable y nunca es un crash duro, pero el
patron ingenuo ("intento construir con cuda, si falla uso cpu") **no detecta nada** porque la construccion
nunca falla. Hace falta el patron de prueba de humo activa del punto 2.

---

## 6. Extrapolacion a una RTX 3080 de 10 GiB `[E]`

**Todo lo que sigue es estimado, no medido.** Se explica el razonamiento para que se pueda auditar, no para
que se tome como cifra cerrada.

**VRAM.** 10 GiB frente a los 4 GiB medidos aqui cambian la conversacion por completo: `large-v3` peso en
disco 3,087 GB `[M-dev]` (fp16); incluso sin cuantizar, sus pesos en VRAM mas el espacio de activaciones y
cache de decodificacion (que en esta tarjeta hizo que `int8` llegara a 3951 MiB) caben con margen holgado en
10 GiB. **En una RTX 3080, `large-v3` deja de ser un modelo descartado y pasa a ser una opcion real** — el
`CUDA out of memory` de la seccion 4 es una limitacion de *esta* tarjeta, no del modelo ni del enfoque.

**`float16`.** La RTX 3080 es arquitectura Ampere, compute capability 8,6, con nucleos tensor FP16 reales —
justo lo que la seccion 2 identifico que le falta a Pascal. **Prediccion con base solida (no una corazonada):
`ctranslate2.get_supported_compute_types('cuda', ...)` en una 3080 deberia incluir `float16` e
`int8_float16`**, porque esa lista la genera CTranslate2 consultando la arquitectura real de la tarjeta, el
mismo mecanismo que en Pascal la excluyo. Es razonable esperar que **`float16` sea alli el modo mas rapido**,
no un dato exotico: los nucleos tensor estan hechos para ese formato exactamente.

**Velocidad.** No hay manera honesta de dar un numero medido para la 3080 sin tenerla delante. Lo que si se
puede decir con los datos de hoy: la 1050 Ti (Pascal, sin nucleos tensor, ~2 TFLOPS FP32 de clase) ya
alcanzo 7-8x tiempo real con `small`/`large-v3-turbo` en `int8` — un modo de computo que en la propia 1050
Ti **no es el optimo posible**, es el unico disponible. Una 3080 con nucleos tensor FP16 nativos y varias
veces mas capacidad de computo bruto deberia, como orden de magnitud, **superar comodamente esas cifras**,
plausiblemente dejando incluso `large-v3` por encima de tiempo real. **Esto no se mide aqui — se recomienda
correr exactamente `bench.py` (el script de este spike, reproducible con los comandos citados) en cuanto
haya una 3080 disponible, antes de fijar nada en la arquitectura.**

**`large-v3` contra `large-v3-turbo`: la decision que de verdad importa para produccion.** Con los datos de
hoy en Pascal: `large-v3-turbo` en `int8` (7,05x) es **mas rapido que `medium`** (3,73x) por su decodificador
recortado (seccion 3), a la vez que comparte el mismo codificador — y por tanto buena parte de la misma
calidad de transcripcion — que `large-v3`. En una 3080 con 10 GiB, donde ambos modelos caben sin problema y
`float16` esta disponible para los dos, **la ventaja de velocidad de `large-v3-turbo` debería mantenerse o
crecer** (el decodificador sigue siendo el cuello de botella secuencial, y eso no lo resuelve mas VRAM).
**Recomendacion tentativa para cuando se pueda medir en la 3080: `large-v3-turbo` en `float16` como techo de
calidad practico, con `large-v3` disponible como opcion manual para quien prefiera exprimir la ultima
fraccion de precision a cambio de latencia.** Es una hipotesis razonada, no una decision — debe confirmarse
con el mismo script sobre la tarjeta real antes de escribirla en un ADR.

---

## 7. Recomendacion final a direccion

**El umbral que fijo Kronos antes de ver ningun resultado era: la GPU solo compensa el costo de ~2 GB de
librerias si da 3x o mas sobre CPU con el mismo modelo, o si hace viable un modelo que en CPU no lo es.**

Los tres modelos medidos de punta a punta lo superan, y no por poco:

| Modelo | Mejora GPU/CPU medida | ?Supera el umbral de 3x? |
|---|---:|---|
| `small` | 6,9x | Si, mas del doble del umbral |
| `medium` | 12,4x | Si, mas de 4 veces el umbral |
| `large-v3-turbo` | 20,7x | Si, casi 7 veces el umbral, y ademas **hace viable un modelo que en CPU corre a 0,34x** (mas lento que el propio audio) |

**Con la tarjeta mas floja del parque, en su modo de computo mas restringido (`int8`, porque `float16` esta
vetado por hardware), la GPU ya es una mejora clara, no marginal.** Y el costo (2,0-2,1 GB `[M-dev]`) es fijo
independientemente de que tan buena sea la tarjeta del usuario: quien tenga una 3080 paga el mismo disco por
un beneficio mayor (seccion 6).

**Recomendacion: GPU como instalador aparte, opcional, nunca por defecto.** No "GPU descartada" —los numeros
no lo sostienen, seria tirar una mejora de 7-21x por escrupulo— y no "GPU por defecto", por tres motivos
concretos, no genericos:

1. **El costo no es simetrico entre usuarios.** ~2 GB es una fraccion enorme frente a los ~795 MB que ya
   pesa la instalacion base de Voice2Text (ADR-0001 §7) — practicamente triplicaria el peso instalado por
   defecto para todo usuario, tenga o no una GPU NVIDIA. La mayoria de las maquinas Windows que instalan
   herramientas de BSTools **no tienen GPU NVIDIA dedicada**, y forzarles esa descarga no tiene contrapartida.
2. **La deteccion en tiempo de ejecucion (seccion 5) exige una prueba de humo activa, no un simple
   `try/except` en la construccion.** Eso es codigo real que hay que escribir y mantener bien, sea cual sea
   el modo de instalacion. Hacerlo opcional no ahorra ese costo, pero **tampoco lo aumenta**: quien instala el
   complemento de GPU ya sabe que tiene una tarjeta, así que la prueba de humo es una confirmacion rapida, no
   una apuesta a ciegas.
3. **`float16` es una variable que cambia por generacion de GPU** (vetado en Pascal, se espera disponible en
   Ampere — seccion 2 y 6). Un instalador de GPU aparte da el lugar natural para resolver el `compute_type`
   correcto en tiempo de instalacion o de arranque, en vez de que el nucleo tenga que adivinarlo con logica
   condicional dispersa.

**Lo que esto no cambia:** la clausula condicional de D5 en ADR-0001 (si V1 confirma menos de 3x tiempo real
con 10 minutos de audio en espanol en CPU, el modelo por defecto pasa a `base`) sigue intacta y sigue siendo
sobre CPU — este spike no la sustituye ni la contradice. Lo que si aporta es un dato a favor de tomarla en
serio: el `small`/CPU medido hoy con audio real dio **1,15x** (mas lento que el 2,8x que dio el spike
original con audio sintetico y sin `vad_filter`), lo que refuerza que la ruta CPU-solamente es ajustada, y
hace que un camino GPU opcional sea una salida de escape razonable para quien la necesite, sin comprometer
la promesa de "cero requisitos manuales fuera de `pip`" para quien no.

---

## Limpieza tras medir

Todo lo generado en este spike vivio fuera del repositorio y se borro al terminar:

```
C:\Users\<usuario>\AppData\Local\Temp\v2t-gpu-spike            (venv completo)         2,39 GB
C:\Users\<usuario>\AppData\Local\Temp\v2t-gpu-spike-work        (scripts + clips .wav)   48 MB
~/.cache/huggingface/hub/models--Systran--faster-whisper-small                          464 MB
~/.cache/huggingface/hub/models--Systran--faster-whisper-medium                         1,5 GB
~/.cache/huggingface/hub/models--Systran--faster-whisper-large-v3                       2,9 GB
~/.cache/huggingface/hub/models--mobiuslabsgmbh--faster-whisper-large-v3-turbo          1,6 GB
```

**Total borrado: ~8,53 GiB (~9,16 GB) `[M-dev]`.** Verificado despues del borrado: ninguna de esas rutas
existe, y `git status` en el repositorio no muestra ningun archivo tocado por este spike salvo este mismo
documento.
