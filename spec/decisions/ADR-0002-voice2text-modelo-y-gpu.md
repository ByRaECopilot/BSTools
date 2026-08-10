---
title: "ADR-0002 — Voice2Text: catálogo de modelos por perfil de hardware y GPU como complemento opcional"
status: listo-para-construir
updated: 2026-08-10
---

# ADR-0002 — Voice2Text: catálogo de modelos por perfil de hardware y GPU como complemento opcional

**Supersede de [ADR-0001](ADR-0001-voice2text-stack.md): D5 (modelo por defecto), D20 (techo de
instalación) y la regla por tramos de su §7.** Todo lo demás de ADR-0001 sigue vigente.

**Conclusión primero.** La GPU **se ofrece**: supera el umbral de 3× que se fijó antes de medir, y no por
poco — **6,9× / 12,4× / 20,7×** según el modelo [M-dev], en la tarjeta más floja del parque. Se entrega
como **complemento opcional, nunca por defecto**, porque sus ~2,0-2,1 GB [M-dev] no son un coste simétrico
entre usuarios. El **catálogo recomendado se calcula por perfil de hardware**, con la calidad como criterio
único y un **filtro de viabilidad** que impide recomendar lo impracticable.

**El hallazgo que obliga a cambiar el contrato del núcleo:** `WhisperModel(device="cuda")` **se construye
sin error aunque falten las DLL de CUDA**; el `RuntimeError` llega en la primera `transcribe()`. Detectar
GPU mirando si la construcción funciona es un **falso positivo silencioso**: la herramienta aceptaría el
trabajo y reventaría minutos después con el usuario esperando. Se resuelve con una **prueba de humo activa
fusionada con la primera carga real** (§6), que en el camino feliz cuesta ~0,1 s.

**Y una corrección de dato que afecta a lo que ve el usuario:** `small` en CPU sobre **audio real** da
**1,15× tiempo real** [M-dev], no los 2,8× que midió el spike anterior con audio sintético. Diez minutos
de audio son **~8,7 minutos de CPU**, no 3,5. La cifra publicada cambia (§8).

**Marcas de origen** (heredadas de ADR-0001): **[M-dev]** medido en la GTX 1050 Ti · **[M-prod]** medido en
la RTX 3080 — **sigue sin existir ninguna** · **[E]** estimado · **[O]** observación fechada sobre un
tercero. Un número sin marca es un error de redacción.

---

## 0. Historias de usuario

1. Como usuario **quiero que la herramienta elija sola el mejor modelo que mi máquina puede mover**, para
   no tener que entender de VRAM ni de tipos de cómputo.
2. Como usuario con GPU **quiero instalar un complemento y que se use sola**, y que si algo falla **me lo
   diga y siga funcionando en CPU**, en vez de romperse a los diez minutos de transcripción.
3. Como usuario sin GPU **no quiero descargar 2 GB de librerías CUDA** que no me sirven de nada.
4. Como dueño **quiero saber, antes de que ocurra, cuánto voy a descargar y cuánto va a ocupar**.

---

## 1. Contexto

- ADR-0001 dejó tres decisiones en cuarentena a la espera de este documento, y una nota (§17) con lo que
  había que resolver. El dueño ya respondió: **rama B — "lo mejor que quepa por máquina"**, el techo de
  ~1 GB era **orientativo** y muere como restricción, y el criterio de desempate es **calidad de texto**;
  velocidad después, peso al final.
- Hay **dos perfiles de hardware**: desarrollo (**GTX 1050 Ti**, Pascal, cómputo 6.1, 4 GiB) y producción
  (**RTX 3080**, Ampere, cómputo 8.6, 10 GiB). Más un tercer perfil que importa igual: **CPU sola**, que es
  lo que tendrá casi todo el que clone un repositorio público.
- El **spike de GPU** ([`SPIKE-GPU-RESULTS.md`](../../apps/Voice2Text/SPIKE-GPU-RESULTS.md), 2026-08-10)
  aporta las mediciones. Corrió en un venv desechable fuera del repo, borrado al terminar.

---

## 2. Decisión

| # | Decisión |
|---|---|
| **E1** | **El catálogo recomendado se calcula por perfil de hardware detectado** (§3). No hay un modelo por defecto único. `recommend_profile()` ordena por **calidad**, y solo a igualdad de calidad por velocidad, y a igualdad de ambas por peso. |
| **E2** | **Antes del orden por calidad se aplica un FILTRO DE VIABILIDAD:** un candidato entra solo si (a) su `speed_ratio` estimado supera `min_viable_speed_ratio` (**1,0** por defecto) y (b) en GPU, su pico de VRAM medido deja **al menos 512 MiB libres** (§7). **Si ningún candidato pasa el filtro, se recomienda el más rápido disponible** — nunca se devuelve una lista vacía. |
| **E3** | **Muere el techo de instalación** (supersede D20 y la regla de tramos de ADR-0001 §7). En su lugar, **obligación de transparencia**: antes de cada descarga se muestran **dos** números, **cuánto se descarga** y **cuánto ocupará al ejecutarse** (RAM o VRAM). Mueren con él los campos que lo representaban: `over_model_budget` y `model_budget_bytes`. |
| **E4** | **La GPU se ofrece**, porque supera el umbral prefijado con margen: **6,9× (`small`) / 12,4× (`medium`) / 20,7× (`large-v3-turbo`)** [M-dev], y porque **hace viables modelos que en CPU corren por debajo del tiempo real**. |
| **E5** | **La GPU se entrega como complemento opcional, nunca por defecto**: `install-gpu.ps1` + `requirements-gpu.txt`. La instalación base se queda en CPU. Motivo: **~2,0-2,1 GB [M-dev] triplicarían el peso base (~795 MB)** para el usuario mayoritario, que no tiene GPU NVIDIA. `uninstall-gpu.ps1` lo revierte y el README publica el `pip uninstall` exacto. |
| **E6** | **`requirements-gpu.txt` fija `ctranslate2` y `nvidia-cudnn-cu12` JUNTOS, nunca por separado.** CTranslate2 cambió de cuDNN 8 a 9 en su 4.5 y **pip no comprueba esa correspondencia**: el choque de ABI aparece en ejecución, no al instalar [O]. Son tres paquetes, no dos: `nvidia-cublas-cu12`, `nvidia-cudnn-cu12` y **`nvidia-cuda-nvrtc-cu12`** (transitiva, la trajo pip sin pedirla). |
| **E7** | **Las DLL de CUDA hay que publicarlas en el `PATH` del proceso a mano.** `pip` las deja en `site-packages/nvidia/*/bin` y **no las pone en el `PATH`** [M-dev]: sin ese paso el fallo es idéntico al de no tenerlas instaladas. Consecuencia obligatoria: **`faster_whisper`/`ctranslate2` se importan de forma perezosa**, dentro de las funciones, para que el `PATH` ya esté puesto. Mismo patrón que el import perezoso de `yt_dlp` (ADR-0001 D7). |
| **E8** | **Una construcción exitosa de `WhisperModel(device="cuda")` NO prueba que la GPU funcione.** Prohibido usarla como detección. La única comprobación fiable es una **prueba de humo activa** (§6). |
| **E9** | `DeviceCapabilities.cuda_status` pasa a ser **tri-estado**: `"unavailable"` / `"probable"` / `"confirmed"`. La interfaz **nunca afirma que la GPU funciona** hasta que la prueba de humo lo confirma; dice *"disponible, se confirma en el primer trabajo"*. |
| **E10** | **Los tres modos de fallo de CUDA se clasifican por separado**, porque los tres son `RuntimeError` pero piden acciones distintas: DLL ausentes → `gpu_libraries_missing`; VRAM insuficiente → `gpu_out_of_memory`; el resto → `gpu_unavailable`. Se distinguen por subcadena del mensaje (`"not found or cannot be loaded"` / `"out of memory"`), con el mismo aviso de fragilidad que la clasificación de yt-dlp. |
| **E11** | **`float16` no se codifica en ninguna tabla nuestra**: se pregunta a `ctranslate2.get_supported_compute_types(...)`. Confirmado [M-dev]: en Pascal devuelve `{'int8','float32','int8_float32'}` y forzar `float16` da un `ValueError` **limpio, en la construcción**. Es hardware, no defecto: **no debe reproducirse en la 3080**. |
| **E12** | **El artefacto sigue siendo fp16 y se cuantiza al cargar** (confirma ADR-0001 §17.3). Repos exactos en §3, con una nota de procedencia: **`large-v3-turbo` no tiene repo de `Systran`**; el de referencia de facto es `mobiuslabsgmbh/faster-whisper-large-v3-turbo`, también en fp16. Sigue sin usarse ningún repo pre-cuantizado en int8. |
| **E13** | **El perfil de producción queda condicionado a una medición en la 3080**, con criterio de desempate escrito de antemano (§4). **No se cierra a ciegas.** |

---

## 3. Catálogo y recomendación por perfil

**Descargas y picos de VRAM medidos** [M-dev salvo donde se marque]:

| `model_id` | Repo | Descarga | VRAM pico int8 | VRAM pico float32 | Calidad (orden) |
|---|---|---:|---:|---:|---|
| `base` | `Systran/faster-whisper-base` | ~145 MB [E] | — | — | 5.º |
| `small` | `Systran/faster-whisper-small` | **464 MB** | **997-1314 MiB** | 1662-2032 MiB | 4.º |
| `medium` | `Systran/faster-whisper-medium` | **1,5 GB** | **2416 MiB** | ~3,9 GiB, no concluyente | 3.º |
| `large-v3-turbo` | `mobiuslabsgmbh/faster-whisper-large-v3-turbo` | **1,6 GB** | **1575 MiB** | — | 2.º [E] |
| `large-v3` | `Systran/faster-whisper-large-v3` | **~2,9-3,1 GB** | **3951 MiB → OOM en 4 GiB** | — | 1.º [E] |

El orden de calidad es **[E]**, derivado de tamaño y arquitectura: nunca se ha medido calidad en español.
Es una deuda declarada, no un dato (§10).

**Velocidad medida, mismo vídeo real, `vad_filter=True`** [M-dev]:

| Modelo | CPU int8 | CUDA int8 | Mejora |
|---|---:|---:|---:|
| `small` | **1,15×** | 7,94× | **6,9×** |
| `medium` | 0,30× | 3,73× | **12,4×** |
| `large-v3-turbo` | 0,34× | 7,05× | **20,7×** |
| `large-v3` | ~0,15-0,3× [E] | no cabe en 4 GiB | — |

**Recomendación resultante, aplicando E1 y E2:**

| Perfil | Candidatos que pasan el filtro | **Recomendado** | Por qué |
|---|---|---|---|
| **CPU sola** | `small` (1,15×) y `base`; `medium`, `turbo` y `large-v3` quedan fuera por correr **por debajo del tiempo real** | **`small` int8** | Es el de más calidad entre los viables. `medium` a 0,30× significa **33 minutos por cada 10 de audio**: eso no se recomienda, se elige a mano sabiendo lo que cuesta |
| **DEV** (1050 Ti, 4 GiB) | `small`, `turbo`, `medium` en int8. `large-v3` **excluido por OOM medido**; `medium/float32` excluido por §7 | **`large-v3-turbo` int8** | Máxima calidad entre los que caben, **y además casi el más rápido** (7,05×) con solo 1575 MiB de VRAM |
| **PROD** (3080, 10 GiB) | `large-v3` y `turbo`, ambos en `float16` [E] | **condicionado — §4** | Los dos caben; el desempate exige medir |

**Nota que evita un malentendido:** `large-v3-turbo` es **más rápido que `medium`** en GPU (7,05× frente a
3,73×) pese a tener más parámetros, porque recorta su decodificador a 4 capas y en GPU el decodificador es
el cuello de botella secuencial. No es una anomalía: es la razón de existir de ese modelo.

---

## 4. Producción: las dos ramas y el criterio de desempate (E13)

En 10 GiB caben **los dos**. Como la calidad es el criterio único y `large-v3` es el techo de calidad, la
rama por defecto es esa — pero el spike recomienda `turbo` con un argumento razonable. Se deja decidido
**el criterio**, no el resultado:

- **Rama P1 — `large-v3` en `float16`.** Es la que gana por aplicación directa de "calidad primero".
  VRAM estimada: 3,1 GB de pesos + ~2,3-3 GB de activaciones ≈ **5,4-6,1 GiB** [E, extrapolado del pico
  medido de `large-v3` int8 en Pascal], con ~3,4 GiB de margen sobre los ~9,5 GiB útiles.
- **Rama P2 — `large-v3-turbo` en `float16`.** Gana si al medir en la 3080 se cumple **cualquiera** de:
  1. `large-v3` **no supera el suelo de viabilidad** (RTF < 1,0);
  2. su pico de VRAM deja **menos de 512 MiB libres** (§7);
  3. una comparación de **calidad sobre el mismo audio en español e inglés** no muestra diferencia
     apreciable — y entonces gana `turbo` por la regla "a igualdad de calidad, decide la velocidad".

**Honestidad sobre el punto 3: hoy no se puede evaluar.** Nunca se ha medido calidad en español (no hay
voz SAPI española en la máquina, V1/S11 siguen bloqueadas). **En su ausencia deciden los puntos 1 y 2**, y
el punto 3 queda como la razón por la que este ADR **no cierra** el perfil de producción.

**Qué hay que ejecutar en la 3080, y es un comando, no un proyecto:** el mismo `bench.py` del spike, más
`cli.py --self-check` (ADR-0001 §17.6). Criterio de aceptación de la migración sin cambios:
`device_used.compute_type == "float16"` y las cifras del README **reetiquetadas por perfil, no
sustituidas**.

---

## 5. Entrega de la GPU (E5, E6, E7)

```
apps/Voice2Text/
├── install-gpu.ps1        instala requirements-gpu.txt y verifica con la prueba de humo
├── uninstall-gpu.ps1      revierte, y dice cuantos GB libera
└── requirements-gpu.txt   ctranslate2 y nvidia-cudnn-cu12 FIJADOS JUNTOS (E6)
```

`install-gpu.ps1` **termina ejecutando la prueba de humo de §6 y diciendo el resultado en claro**: si
instala 2 GB y no confirma que funciona, no ha hecho su trabajo. El README declara, como ya hace con
yt-dlp, que **este camino no es autocontenido**: son ~2 GB que vienen de PyPI y dependen del driver NVIDIA
del usuario.

**El paso del `PATH` (E7) es el que más silenciosamente rompe:** las DLL quedan en
`site-packages/nvidia/*/bin` y hasta que no se anteponen esas carpetas al `PATH` del proceso, el síntoma es
**exactamente el mismo** que no tenerlas instaladas — con `pip` diciendo que todo fue bien. De ahí que los
imports de `faster_whisper`/`ctranslate2` tengan que ser **perezosos**.

---

## 6. Detección: la prueba de humo, y dónde vive su coste (E8, E9)

**El problema, medido:** con las librerías CUDA desinstaladas,
`WhisperModel('small', device='cuda', compute_type='int8')` **cargó sin error ni aviso en 2,83 s**. El
`RuntimeError: Library cublas64_12.dll is not found or cannot be loaded` llegó en la primera
`transcribe()`. El patrón ingenuo *"construyo con cuda, si falla uso cpu"* **no detecta nada**.

**Dónde vive el coste — la pregunta que había que decidir, y la respuesta disuelve el dilema:**

> **La prueba de humo no es un paso de arranque: es la primera inferencia, sobre un clip sintético de medio
> segundo generado en memoria, ejecutada inmediatamente después de cargar el modelo que el trabajo necesita
> de todas formas.**

- **Camino feliz: ~0,1 s.** El modelo ya se estaba cargando; solo se añade una inferencia trivial.
- **Camino de fallo:** se pierde una carga en GPU (~5-10 s [M-dev]) y se recarga en CPU. **Una vez por
  sesión.**
- **No hace falta descargar `tiny`** solo para la prueba: se usa el modelo que ya se iba a usar.
- **No hay caché en disco, y por eso no hay problema de obsolescencia.** El resultado se guarda **en
  memoria, para la vida del proceso**. Como la prueba está fusionada con la primera carga, "por proceso"
  cuesta prácticamente cero, y cada arranque parte de cero: si el usuario reinstala librerías entre
  sesiones, la siguiente sesión lo ve. **El dilema "cuesta tiempo vs. se queda obsoleto" no existe.**

**Reporte en dos niveles, para no mentir nunca (E9):**

| Momento | Qué se comprueba | `cuda_status` | Qué dice la interfaz |
|---|---|---|---|
| Arranque, barato | `get_cuda_device_count() > 0` **y** que los ficheros de DLL existan en disco en `site-packages/nvidia/*/bin` **y** `get_supported_compute_types()` | `"probable"` | *"Aceleración GPU: disponible (se confirma en el primer trabajo)"* |
| Primera carga | prueba de humo real | `"confirmed"` / `"unavailable"` + motivo | *"activa (GTX 1050 Ti, int8)"* o el aviso de caída con su causa |

La comprobación de **existencia de los ficheros DLL en disco** no estaba en la recomendación del spike y se
añade a propósito: es gratis y tapa el caso de "instalado pero no en el `PATH`", que produce el mismo error
que "no instalado".

**La caída a CPU nunca es silenciosa** (ADR-0001 D10 y `ARCHITECTURE.md` §3): `fell_back_from` y
`fallback_reason` viajan al estado del trabajo y la cáscara los traduce. **Y los tres motivos dan mensajes
distintos** (E10), porque las acciones son distintas: reparar la instalación, elegir un modelo más pequeño,
o nada.

---

## 7. VRAM: por qué la holgura es absoluta y no porcentual (E2)

**El dato que lo obliga:** `medium` en `float32` subió a **3881-3927 MiB de 4096 MiB** y, pasados 13
minutos, **no produjo resultado ni lanzó excepción**. La hipótesis del spike [O] es *spillover* a memoria
compartida por PCIe del driver WDDM. No se confirmó — y **da igual para el diseño**, porque la lección
práctica es independiente de la causa:

> **Quedarse justo por debajo del límite de VRAM es PEOR que pasarse.** Pasarse da un
> `CUDA out of memory` limpio y capturable. Quedarse al borde da una **degradación silenciosa a un
> rendimiento inaceptable**, sin excepción que capturar y sin nada que enseñarle al usuario.

Por eso la regla no es un porcentaje: **se exige que tras cargar queden al menos 512 MiB libres**, medido
contra el pico real del catálogo. Un porcentaje se comporta mal en los dos extremos —15 % de 4 GiB son
600 MiB (justo), 15 % de 10 GiB son 1,5 GiB (desperdicio)—; un mínimo absoluto encaja en las dos tarjetas.

**Y el escritorio cuenta:** `nvidia-smi` en reposo mostró **459 MiB ya ocupados** por `explorer.exe`,
`msedgewebview2.exe` y varias apps [M-dev]. La VRAM disponible de partida en la 1050 Ti es **~3546 MiB, no
4096**. `vram_free_mb` se lee **en el momento**, nunca se calcula restando de la capacidad nominal.

---

## 8. Lo que este ADR corrige

### 8.1 La cifra que ve el usuario: `small`/CPU es 1,15×, no 2,8×

El spike de CPU midió **2,8×** sobre un clip **sintético de 42,7 s sin `vad_filter`**. El de GPU midió
**1,15×** sobre **audio real de 360 s con `vad_filter=True`**, que es la configuración que se entrega.
**La cifra buena es 1,15×**, y la diferencia no es ruido: es un factor de 2,4.

| | Antes (derivado de 2,8×) | **Ahora [M-dev]** |
|---|---|---|
| 10 min de audio, `small`/CPU | "~3,5-4 min" | **~8,7 min** |

**Causa probable [E]:** el audio sintético de SAPI es habla limpia y poco densa; genera menos tokens que
una conferencia real. **Lección transferible: el audio sintético sirve para probar el mecanismo, no para
medir rendimiento — y su sesgo es OPTIMISTA, en una sola dirección.** Toda cifra de velocidad se mide sobre
audio real.

### 8.4 La unidad se publica en minutos, no en "×" — y por qué

**Incidente del 2026-08-10, detectado al revisar un mensaje al dueño.** La convención de estos documentos
está escrita desde ADR-0001 §3.1: **"× tiempo real" = duración del audio ÷ tiempo de proceso; más alto es
mejor**. Aun así, el `2,8×` se transmitió al dueño como *"10 minutos de audio son 28 minutos de proceso"*,
que es la lectura **invertida** (`10 × 2,8` en vez de `10 ÷ 2,8`). La cifra correcta con aquel dato eran
**3,6 minutos**.

**Son dos errores distintos y hay que separarlos, porque tienen arreglos distintos:**

| Error | Qué lo causó | Magnitud | Arreglo |
|---|---|---|---|
| **Inversión de unidad** | Leer "2,8×" como "2,8 veces más lento" | 28 min frente a los 3,6 reales: **factor 8** | Este apartado |
| **Audio sintético** | Medir rendimiento sobre un clip TTS corto | 2,8× frente a 1,15×: **factor 2,4, siempre optimista** | §8.1 |

**No los mezcles en una sola lección.** El clip sintético **no** erró "en las dos direcciones": erró
siempre hacia arriba. Lo que sobrestimó el proceso en la otra dirección fue la inversión de unidad, que es
un fallo de comunicación, no de medición. Concluir "el clip sintético falla en ambos sentidos, así que no
hay sesgo" institucionalizaría lo contrario de lo que pasó.

**Regla que sale de aquí, y aplica a README, interfaz y a cualquier mensaje a dirección:**

> **La cifra que ve una persona se expresa SIEMPRE en "minutos de proceso por cada 10 minutos de audio",
> nunca como un multiplicador.** El `speed_ratio` sigue existiendo como campo técnico del estado del
> trabajo (`ARCHITECTURE.md` §4.2), pero **no aparece jamás en un texto para humanos.** Una unidad que se
> puede leer del revés acabará leyéndose del revés.

**Y el efecto neto sobre la expectativa del dueño, dicho sin suavizar:** se le dijo 28 minutos, luego se le
corrigió a 8,7. Ambas veces sonó a buena noticia, pero **frente al dato que teníamos entonces (3,6 min),
la herramienta es 2,4 veces MÁS LENTA de lo que aquella medición prometía**, y ~7 veces más lenta que la
estimación original de este arquitecto (4-7×). La dirección de la corrección es a peor, no a mejor. Es el
argumento honesto para el complemento de GPU, y no debe presentarse como una mejora.

Esto refuerza dos cosas ya decididas: la **obligación de publicar la cifra con su perfil**, y el valor del
camino GPU como salida de escape.

### 8.2 Una cita obsoleta del informe del spike, que no debe propagarse

El informe (§7) afirma que *"la cláusula condicional de D5 sigue intacta"*. **No lo está.** Fue
**SUSPENDIDA** por el dueño al declarar la calidad como criterio único: degradar el modelo para ganar
velocidad es exactamente lo contrario de lo que quiere. Está en el bloque de cuarentena de ADR-0001 desde
antes de este spike; el informe cita una versión anterior del documento.

**Efecto práctico:** el dato de 1,15× **no dispara ninguna bajada automática a `base`**. Lo que hace es
(a) fijar la cifra honesta que se publica y (b) alimentar el filtro de viabilidad de E2 — que, con 1,15×,
**deja a `small` como el recomendado en CPU de todos modos**, por ser el de más calidad entre los viables.
El resultado coincide; el mecanismo es otro, y confundirlos llevaría a reactivar una regla muerta.

### 8.3 `ARCHITECTURE.md`

Se enmienda: `cuda_status` tri-estado, prueba de humo fusionada con la primera carga, `PATH` de las DLL e
imports perezosos, holgura absoluta de 512 MiB, `vram_peak_mb` medidos en el catálogo, códigos
`gpu_libraries_missing` / `gpu_out_of_memory` / `gpu_unavailable`, y el filtro de viabilidad con su
respaldo. **Afecta a `transcribe.py`, ya commiteado** (§9).

---

## 9. Consecuencias

**Lo que se gana**

- Una mejora de **7× a 21×** para quien tenga GPU, sin imponer nada a quien no.
- Un catálogo que **se adapta a la máquina** en vez de obligar al usuario a entender de VRAM.
- Una detección que **no miente**: o está confirmada, o dice que no lo está.

**Costes aceptados**

| Coste | Mitigación |
|---|---|
| **~2,0-2,1 GB [M-dev]** para quien instale la GPU | Opcional, aparte, con `uninstall-gpu.ps1` y los dos números delante |
| **El camino GPU no es autocontenido** — segunda grieta en la regla de oro, tras yt-dlp | Se declara en el README con las mismas palabras que se hizo con yt-dlp. La instalación base **sí** lo es |
| **`small`/CPU son ~8,7 min por cada 10 de audio** [M-dev] | Se publica esa cifra, no una mejor. Es el argumento honesto para el complemento de GPU |
| El acoplamiento `ctranslate2` × cuDNN puede romper en ejecución [O] | E6: se fijan juntos. `gpu_libraries_missing` con mensaje accionable |
| **Cambio en `transcribe.py`, ya commiteado**: imports perezosos y firma de capacidades | Aditivo, unas pocas líneas. Detalle en §11 |
| `medium`/`float32` quedó sin concluir | No es decisivo: `medium` se recomienda en `int8`, y la variante `float32` queda **excluida por la regla de holgura**, que es el resultado correcto sin necesidad del dato |
| El orden de calidad del catálogo es **[E]**, nunca medido | Deuda declarada. Se salda con V6 (§10) |

---

## 10. Verificaciones abiertas

| # | Qué | Estado | Consecuencia si falla |
|---|---|---|---|
| **V1 / S11** | Velocidad y detección de idioma con **10 min de audio en español** | **DESBLOQUEADO (2026-08-10)** — el dueño instaló `Microsoft Sabina Desktop` (`es-MX`), **verificada visible para `System.Speech.Synthesis`** con `GetInstalledVoices()`, no de palabra: muchas voces de Windows se instalan solo para el Narrador y SAPI no las ve. En ejecución; entrega en `VERIF-ESPANOL.md` | Afina la cifra publicada; **no cambia el modelo recomendado**. El dialecto `es-MX` es irrelevante para las dos: Whisper detecta `es` sin distinguir variante, y el coste de proceso no depende del acento |
| **V2 / V3 / V4** | Marcas de tiempo y `word_timestamps` (lote 1.b) | en curso | Independientes de este ADR |
| **V5** | ¿`get_supported_compute_types('cuda',0)` funciona **sin** las DLL de CUDA? | **ABIERTO** | Si da un falso positivo, el estado `"probable"` se apoya solo en la existencia de los ficheros DLL en disco — que ya está en el contrato por si acaso |
| **V6** | **Calidad real en español e inglés** de `turbo` frente a `large-v3` sobre el mismo audio | **SIGUE BLOQUEADO** — y la voz española **no lo desbloquea**: ver el recuadro de abajo | Es el punto 3 del desempate de §4 y la única forma de saldar la deuda del orden de calidad |
| **V7** | `bench.py` + `--self-check` **en la RTX 3080** | **ABIERTO** | Cierra §4. Hasta entonces **no hay ninguna cifra [M-prod]** |

> ### Por qué la voz sintética desbloquea V1 y S11 pero NO V6
>
> **Velocidad (V1) e idioma detectado (S11): válidos.** El coste de proceso no depende de la naturalidad de
> la voz —son las mismas matrices sobre el mismo número de muestras— y la detección de idioma opera sobre
> fonética, que el TTS reproduce suficientemente bien.
>
> **Calidad de texto (V6): NO válido, y cualquier número que salga de TTS es OPTIMISTA.** El habla
> sintética no tiene acento marcado, ni ruido de fondo, ni solapamiento de hablantes, ni micrófono
> mediocre, ni muletillas, ni frases cortadas a la mitad — que es exactamente el material donde un modelo
> mayor se separa de uno menor. Medir `turbo` contra `large-v3` sobre TTS mediría el caso fácil y los daría
> por empatados **precisamente cuando el empate es la conclusión que decide el desempate de §4**. Sería el
> peor sitio posible para un falso positivo.
>
> **V6 exige una grabación humana real** con transcripción de referencia. Hasta entonces, el desempate de
> §4 lo deciden sus puntos 1 y 2 (viabilidad y VRAM), nunca el 3.

---

## 11. Impacto en lo ya construido

El lote 1 está commiteado. Lo que este ADR obliga a tocar es **aditivo y acotado**:

1. **`transcribe.py`: imports perezosos** de `faster_whisper`/`ctranslate2`, para que el `PATH` de las DLL
   se pueda poner antes (E7). Unas líneas, mismo patrón que el import perezoso de `yt_dlp`.
2. **`DeviceCapabilities`: `cuda_available: bool` → `cuda_status` tri-estado** (E9), y `unavailable_reason`
   gana `gpu_libraries_missing`.
3. **`resolve_device()`: la holgura pasa a 512 MiB absolutos** en vez de un factor 1,15 (§7), y el filtro
   de viabilidad gana el respaldo de E2.
4. **`ModelSpec`: fuera `over_model_budget`** (E3), dentro `vram_peak_mb` por `compute_type` con los
   valores medidos de §3.
5. **`probe_devices()`: deja de ser un tapón** y pasa a implementar las comprobaciones baratas de §6.

**Nada de esto invalida trabajo hecho**: la política de `resolve_device()` sigue siendo pura y sus casos de
prueba con capacidades sintéticas siguen valiendo — se les añaden las filas de VRAM medidas.

---

## 12. Estado

**Aceptado** — `listo-para-construir`. Cierra las decisiones que ADR-0001 dejó en cuarentena, salvo el
**perfil de producción, que queda condicionado a V7** con el criterio de desempate ya escrito (§4).

Append-only: cualquier cambio será un ADR nuevo. El desempate de §4 **no** necesita ADR nuevo — este
documento lo pre-autoriza, igual que su criterio.
