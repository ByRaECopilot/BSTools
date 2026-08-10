# Voice2Text — UI-SPEC (diseño de interfaz, lote 3)

> **Estado: especificación de diseño, sin implementar.** Contrato de referencia:
> [`ARCHITECTURE.md`](ARCHITECTURE.md) (§4 estados del trabajo, §5 errores, §8 primer arranque, §13 lote 3),
> [`ADR-0001`](../../spec/decisions/ADR-0001-voice2text-stack.md) y
> [`ADR-0002`](../../spec/decisions/ADR-0002-voice2text-modelo-y-gpu.md). Este documento **traduce** ese
> contrato a pantallas, componentes y copy — no lo sustituye. Si algo de aquí contradice `ARCHITECTURE.md`
> o los ADR, **ganan ellos**, y hay que corregir este documento, no al revés.
>
> Para: `atlas-developers`, lote 3 (`app.py`, `ui.html`, `messages.py`, `settings.py`). No incluye
> implementación ni HTML/CSS/JS real — eso es del lote 3.

---

## 0. Conclusión primero (BLUF)

El problema de esta interfaz no es estético: es que **un trabajo dura minutos y hay un tramo sin ningún
número que enseñar** (`detecting_language`, hasta ~22 s en archivos largos, §8 de este documento). Toda la
especificación gira sobre tres decisiones:

1. **Nunca una pantalla quieta.** Toda fase indeterminada lleva un **cronómetro vivo** (`mm:ss`, cuenta
   arriba) además de la animación, aunque no haya porcentaje que enseñar. Es la respuesta directa al riesgo
   #2 del encargo: una ventana quieta se interpreta como colgada, y se cierra.
2. **Una sola acción deliberada arranca el trabajo**, incluso viniendo del menú contextual. Con un coste de
   minutos y opciones que importan (modelo, idioma, formatos), arrancar solo sin que el usuario vea qué va
   a pasar es justo la sorpresa que una interfaz decente evita.
3. **El texto aparece mientras se transcribe.** El panel de transcripción en vivo no es un adorno: convierte
   "espera muerta" en "algo que leer", y el contrato ya lo permite (`since=n`, `ARCHITECTURE.md` §4.2).

Hay **dos huecos entre el contrato del núcleo y una buena experiencia**. Se documentan en el §1 en vez de
ignorarse; ninguno bloquea el lote 3, los dos tienen una salida que funciona con el contrato actual.

---

## 1. Dos brechas del contrato — dichas en voz alta, no rediseñadas en silencio

### 1.1 No existe una operación para elegir carpeta de destino

Las **nueve operaciones** de `ARCHITECTURE.md` §6.3 no incluyen "elegir carpeta". Hay `pick_file()`
(diálogo nativo de archivo) pero ningún equivalente a `create_folder_dialog()` de pywebview. El destino por
defecto (junto al origen, o `salida/` para enlaces) está bien como comportamiento por defecto, pero **una
herramienta de escritorio sin forma de decir "guárdalo aquí" es una limitación que el usuario notará**, y
notarla la primera vez que le importe (un vídeo que quiere guardar en una carpeta de proyecto concreta) es
peor que anunciarla desde el principio.

**Lo que se pide, sin bloquear el lote 3:** añadir una décima operación, mismo patrón que `pick_file()`:

```
elegir_carpeta_destino()  →  window.expose (ventana)  |  no aplica al modo servidor
```

**Mientras no exista** (§7.2 de este documento, pantalla C): el destino se muestra **de solo lectura**, con
la ruta calculada por defecto y un enlace *"cambiar la carpeta de salida por defecto"* que abre el explorador
de Windows sobre `settings.json` — no es elegante, pero es honesto: no promete un control que no existe.

### 1.2 La duración del medio no se conoce (todavía) al empezar `detecting_language`

`ARCHITECTURE.md` §3 dice que la duración "se conoce antes de transcribir", pero eso ocurre **como salida**
del preámbulo bloqueante de `model.transcribe()` — es decir, **después** de la fase que más necesita ese
dato para tranquilizar al usuario (`detecting_language` es precisamente el tramo sin número, §4.3).

**La duración de un contenedor normalmente se lee de la cabecera, sin decodificar nada** (PyAV expone
`container.duration` sin tocar el generador de `faster-whisper`). Si `jobs.py` hiciera esa lectura barata
**antes** de entrar en `detecting_language` y la publicara en `media_duration_seconds` desde el primer
instante, la interfaz podría mostrar una cota superior honesta ("puede tardar hasta ~22 s") en vez de un
cronómetro sin referencia.

**No lo doy por hecho ni lo exijo para el lote 3.** El diseño del §8.3 funciona **sin** ese dato (mensajes
escalonados por tiempo transcurrido, §8.3.2) y **mejora** si el dato llega (cota superior calculada, §8.3.3).
Queda como mejora recomendada, marcada explícitamente para que alguien la evalúe con una medición, no una
suposición — el mismo estándar que el resto del proyecto.

---

## 2. Mapa de pantallas

```
Arranque (app.py, fuera de ui.html)
  │
  ├─ [servidor ya corriendo] ──► diálogo nativo, la ventana NO llega a abrirse (§5)
  │
  └─ [libre] ──► ui.html carga
        │
        ├─ [models/ vacío] ──► B. Primer arranque: consentimiento de descarga (§7.1)
        │                          │
        │                          └─ tras descargar ──► C
        │
        └─ [hay modelo] ──► C. Pantalla principal: origen + opciones (§7.2)
                                │
                                │  clic en "Transcribir"
                                ▼
                            D. Trabajando: una vista, ocho fases posibles (§8)
                                │
                    ┌───────────┼────────────┐
                    ▼           ▼             ▼
                E. Resultado  Cancelado   Error (tarjeta, §11)
                (§10)         (neutro)    ──► "Reintentar" vuelve a C
                    │
                    └─ "Transcribir otro" ──► vuelve a C

Accesibles desde la cabecera en cualquier momento:
  F. Gestión de modelos (§13)      G. Ajustes avanzados (§14)
```

**Una sola ventana, un solo documento.** No hay navegación por pestañas de nivel superior: F y G son
paneles superpuestos (capa por encima de C/D/E, con foco atrapado dentro y `Esc` para cerrar), nunca
pantallas que reemplazan el progreso de un trabajo en curso — cerrar el panel de ajustes con un trabajo
corriendo debe devolver exactamente a D, sin perder el estado.

---

## 3. Tokens de diseño

Coherente con el lenguaje visual de `apps/Mermaid/index.html` (variables CSS, oscuro por defecto, acento
azul-violeta) — sin copiar su estructura, porque aquí la ventana es propia (pywebview), no un editor de tres
paneles.

### 3.1 Color

```css
:root {
  --bg:        #0e1016;   /* fondo de ventana */
  --panel:     #161923;   /* tarjetas, cabecera */
  --panel-2:   #1d212e;   /* campos, filas alternas */
  --line:      #2a2f3d;   /* bordes suaves */
  --line-2:    #363c4d;   /* bordes de foco/hover */
  --text:      #e8eaf0;
  --muted:     #98a0b3;   /* texto secundario, timestamps */
  --accent:    #7c8cff;   /* acción primaria, foco, barra de progreso */
  --accent-soft: #7c8cff22;

  --ok:        #47d18a;   /* éxito, "Listo" */
  --warn:      #f5a623;   /* avisos no bloqueantes (aviso ≠ error) */
  --danger:    #ff6b6b;   /* errores que detienen el trabajo */
  --shadow:    0 10px 30px rgba(0,0,0,.35);
}
@media (prefers-color-scheme: light) {
  :root {
    --bg: #eef1f6; --panel: #ffffff; --panel-2: #f4f6fa;
    --line: #e1e5ec; --line-2: #d3d9e3;
    --text: #1a1f2b; --muted: #667085;
    --accent: #5b6cf0; --accent-soft: #5b6cf01a;
    --ok: #16a34a; --warn: #b45309; --danger: #e5484d;
    --shadow: 0 10px 30px rgba(20,30,60,.12);
  }
}
```

`--warn` es un token **nuevo** frente a Mermaid/BrandAssets (que solo tienen `--ok`/`--danger`): esta
herramienta necesita **tres niveles de severidad**, no dos — un aviso ("se transcribió con la CPU") no es
un error y pintarlo de rojo entrena al usuario a ignorar el rojo de verdad.

### 3.2 Tipografía y espaciado

- Fuente: `-apple-system, "Segoe UI", Roboto, Ubuntu, sans-serif` (igual que el resto de BSTools).
- Monoespaciada para detalle técnico expandible y rutas de archivo: `"Cascadia Code", Consolas, ui-monospace, monospace`.
- Escala: 12 px (metadatos, timestamps) · 14 px (cuerpo, por defecto) · 16 px (títulos de tarjeta) · 20 px
  (título de pantalla, uno por vista).
- Espaciado en múltiplos de 4 px; radios: 8 px (campos, botones), 12 px (tarjetas), 999px (chips/badges).

### 3.3 Iconografía

SVG en línea, `stroke="currentColor"`, `stroke-width="2"` — mismo lenguaje que `apps/Mermaid`. Sin fuente de
iconos ni CDN. Set mínimo: `check`, `alert-triangle`, `info`, `download`, `trash`, `folder`, `cpu`, `zap`
(GPU), `link`, `file`, `x`, `copy`, `chevron-down`.

---

## 4. Componentes reutilizables

### 4.1 Barra de progreso — determinista e indeterminada

**Nunca la misma barra vacía para las dos.** Son dos componentes visualmente distintos para que el usuario
sepa, de un vistazo, si hay un número detrás o no:

| | Determinista | Indeterminada |
|---|---|---|
| Relleno | ancho = `progress * 100%`, transición suave | franja animada en bucle (`background-position`), **nunca estática** |
| Texto bajo la barra | `"42 % · quedan ~3 min 40 s"` (tras 20 s, si no, `"calculando…"`) | **cronómetro vivo** `mm:ss` contando hacia arriba + una frase que explica qué pasa (§8.3) |
| Color | `--accent` | `--accent`, más tenue (`--accent-soft` de fondo) |

El cronómetro de la variante indeterminada es **obligatorio, no decorativo**: es la pieza que responde al
riesgo #2 del encargo. Se implementa con `setInterval` de 1 s sobre `Date.now() - fase_iniciada_en`, no
dependiendo de que el backend lo publique (el backend ya manda `updated_at`, pero un reloj de cliente no se
congela si un sondeo se retrasa).

### 4.2 Banner de severidad (aviso / error)

Tres variantes por color de borde izquierdo y color de icono (`--warn` info/aviso, `--danger` error),
mismo layout:

```
┌────────────────────────────────────────────────────────┐
│ (icono)  Título breve, una línea                        │
│          Cuerpo: qué pasó, en castellano llano.          │
│          Qué puedes hacer: la pista, si la hay.          │
│                                                            │
│          [ Detalle técnico ▾ ]   [Acción secundaria] [Acción primaria] │
└────────────────────────────────────────────────────────┘
```

- **Aviso** (`--warn`): no bloquea nada, tiene un botón de cerrar (×), no reaparece tras cerrarlo para ese
  trabajo. Vive dentro del flujo (pegado al resultado o a la barra de progreso), nunca reemplaza la pantalla.
- **Error** (`--danger`): sí reemplaza el contenido de la pantalla D por una tarjeta a pantalla completa
  (§11). El detalle técnico (`technical`, una línea) va **siempre colapsado por defecto**, en monoespaciada,
  bajo un desplegable — está para quien lo necesite (el propio dueño, o un reporte de fallo), no para
  intimidar al usuario normal.

### 4.3 Chip de dispositivo

Badge pequeño en la cabecera y en la tarjeta de resultado:

| Estado (`cuda_status`) | Texto del chip | Icono |
|---|---|---|
| `"unavailable"` | `CPU` | `cpu` |
| `"probable"` (antes del primer trabajo) | `GPU disponible · se confirma al transcribir` | `zap`, atenuado |
| `"confirmed"` | `GPU activa · <nombre de la tarjeta>` | `zap` |
| `"confirmed"` pero el trabajo cayó a CPU (`fell_back_from`) | `CPU (la GPU falló: <motivo corto>)` | `cpu`, con `--warn` |

**Nunca** el chip afirma "GPU activa" antes de la prueba de humo real (ADR-0002 E9) — es la misma regla que
`ARCHITECTURE.md` ya fija, solo llevada al pixel.

### 4.4 Panel de transcripción en vivo

Lista de párrafos que crece por abajo conforme llegan `new_segments` (sondeo con `since=n`, §4.2 del
contrato). Cada entrada: `[mm:ss]` en `--muted` monoespaciado + texto en `--text`. Auto-scroll al fondo
**solo si el usuario no ha hecho scroll manual hacia arriba** — si está leyendo algo de atrás, no lo
arrastres hacia abajo con cada segmento nuevo; muestra en su lugar un botón flotante discreto
`"↓ nuevo texto"`.

Vacío antes de `transcribing` (fases previas): un estado vacío con un texto tenue, **no una caja en blanco**
— `"El texto aparecerá aquí en cuanto empiece la transcripción."` Esto también amortigua la fase
`detecting_language`: el usuario ve dónde va a aparecer el resultado, aunque todavía no haya nada.

### 4.5 Tarjeta de modelo (primer arranque y gestión de modelos)

```
┌──────────────────────────────────────────┐
│ ⦿  Preciso, para uso normal   RECOMENDADO │
│    small · 464 MB de descarga             │
│    Ocupa ~1 GB en memoria al usarse        │
│    ~5,8 min de proceso por cada 10 min      │
│    de audio en tu equipo (CPU)              │
└──────────────────────────────────────────┘
```

Campos obligatorios en toda tarjeta (ADR-0002 E3, obligación de transparencia): **descarga** y **ocupación
en RAM/VRAM al ejecutarse**, los dos números, siempre — nunca solo uno. El adjetivo de calidad
(§7.1.2) y la velocidad se calculan a partir de `recommend_profile()` y del catálogo; nunca un texto fijo
en el HTML.

---

## 5. Arranque y exclusividad de modos (fuera de `ui.html`)

Si el modo servidor está corriendo (`runtime.lock`), **la ventana no llega a abrirse** (`ARCHITECTURE.md`
§6.4, D21). Es un diálogo nativo de Windows (o el propio `create_confirmation_dialog` de pywebview antes de
`webview.start()`), no HTML — pero el copy es responsabilidad de esta especificación porque `messages.py`
es el único sitio con texto:

> **Voice2Text ya está en marcha en modo servidor** (puerto 8317).
> Ciérralo desde su ventana de consola, o con Ctrl+C, y vuelve a intentarlo.
>
> **[ Entendido ]**

Un solo botón. No hay nada que decidir aquí: es información, no una elección.

---

## 6. Antes de la primera pantalla: qué determina qué se ve

En **menos de 2 s** (`ARCHITECTURE.md` §8.1) la cáscara decide, sin cargar ningún modelo:

```
¿models/ vacío?
  sí ──► Pantalla B (primer arranque)
  no ──► Pantalla C, con el origen PRE-RELLENADO si llegó por sys.argv[1] o asociación de archivo
```

**Decisión de esta especificación, y por qué:** aunque la herramienta se invoque desde el menú contextual
de un archivo concreto, **no se arranca la transcripción sola**. Se pre-rellena el origen y las opciones por
defecto en la pantalla C y se espera un clic en "Transcribir". Razón: un trabajo de minutos con opciones que
cambian el resultado (modelo, idioma, formatos de salida) no debería empezar sin que el usuario vea, aunque
sea un segundo, qué va a pasar y con qué ajustes. El coste es un clic; el beneficio es no transcribir 27
minutos el archivo equivocado, o con el modelo equivocado, sin darse cuenta.

---

## 7. Pantallas B y C, en detalle

### 7.1 Pantalla B — Primer arranque: consentimiento de descarga del modelo

Es **la pantalla más delicada de toda la herramienta** (riesgo #4 del encargo): nadie puede acabar
descargando de 464 MB a 3,1 GB sin haber dicho que sí, explícitamente, sabiendo el tamaño.

#### 7.1.1 Antes de pulsar "Descargar"

```
┌───────────────────────────────────────────────────────────────┐
│  Falta el modelo de reconocimiento de voz                       │
│  Se descarga una sola vez y se queda en tu equipo. Puedes        │
│  borrarlo cuando quieras.                                        │
│                                                                    │
│  [si llegó un archivo por el menú contextual:]                   │
│  ℹ Tras la descarga se transcribirá: reunion-comite.mp4           │
│                                                                    │
│  ⦿ (tarjeta de modelo recomendado — §4.5)                        │
│  ○ (tarjeta de la alternativa ligera)                             │
│  [ Ver más modelos ▾ ]  (despliega el resto del catálogo,        │
│     con los que no pasan el filtro de viabilidad marcados:       │
│     "en tu equipo sería más lento que el propio audio")          │
│                                                                    │
│  Se guardará en: D:\...\apps\Voice2Text\models                    │
│  Espacio libre en ese disco: 214 GB                                │
│                                                                    │
│  🖥 Aceleración GPU: <estado del chip §4.3>                       │
│                                                                    │
│                                    [ Descargar ]                  │
└───────────────────────────────────────────────────────────────┘
```

**Foco inicial:** en el radio del modelo recomendado (permite moverse con flechas y confirmar con Enter,
sin ratón). Botón "Descargar" solo se activa cuando hay un modelo seleccionado — siempre lo hay, porque el
recomendado viene premarcado.

**Regla de unidad, sin excepción** (ADR-0002 §8.4): la velocidad se escribe siempre como *"X min de proceso
por cada 10 min de audio"*. **Jamás** un multiplicador (`×`). Ya hubo un incidente real de lectura invertida
sobre esta misma cifra (ADR-0002 §8.4) — un error de comunicación, no de medición, y esta regla es la
barrera que lo evita en la interfaz.

#### 7.1.2 Vocabulario de calidad, sin jerga

`quality_rank` es un entero ordinal — nunca se enseña. Se traduce con esta tabla fija en `messages.py`:

| `quality_rank` | Adjetivo en pantalla |
|---|---|
| 1 | "El más preciso" |
| 2 | "Muy preciso" |
| 3 | "Preciso" |
| 4 | "Preciso, para uso normal" |
| 5 | "Básico — más rápido, se equivoca más con nombres y cifras" |

`params_millions`, `compute_type`, `int8`, `float16`: **ninguno aparece en una pantalla que ve el usuario.**
Si el detalle técnico se expande (mismo patrón que §4.2), ahí sí puede leerse `small · int8 · CPU` para
quien lo busque a propósito.

#### 7.1.3 Durante la descarga

```
Descargando el modelo de reconocimiento…
[███████████░░░░░░░░]  156 MB de 464 MB · 34 %
Puedes cerrar esta ventana y volver más tarde: se retoma donde se quedó.

                                          [ Cancelar descarga ]
```

- Barra **determinista** (bytes en disco / `expected_bytes`, funciona con o sin *callback* de la librería,
  `ARCHITECTURE.md` §8 punto 3).
- **Cancelación real e inmediata** (`ensure_model()` comprueba `should_cancel()` entre trozos de 256 KiB,
  no es la cancelación de ~27 s de una transcripción): el botón dice "Cancelar descarga" sin advertencia de
  demora, porque aquí sí es instantánea.
- Si se corta la conexión: se reanuda por `Range`, mostrando el progreso desde donde iba, no desde 0.
- **La consola detrás de la ventana también imprime el progreso** (`ARCHITECTURE.md` §8 punto 4) — es la
  red de seguridad si WebView2 se queda pillado; requiere que el lanzador mantenga la consola visible tras
  la ventana (patrón estándar de la casa para `.py`), y que `app.py` escriba a `logging`/consola en paralelo
  al progreso que expone a `ui.html`.

#### 7.1.4 Sin internet

Error `model_download_failed` (§11), con la cifra exacta ya descargada para que se note que no se perdió
nada: *"No he podido descargar el modelo (156 MB de 464 MB). Comprueba la conexión; se reanuda donde se
quedó."*, botón **"Reintentar descarga"**.

Caso límite honesto (`ARCHITECTURE.md` §8 punto 6, `model_missing` con `allow_download=False`, poco probable
desde la ventana porque el botón "Transcribir" está desactivado sin modelo, pero se especifica por si algo
lo alcanza): *"Falta el modelo de reconocimiento."* + *"Descárgalo desde el aviso de arriba (464 MB)."* —
sin ruta a mano en la ventana (eso es para consumidores sin interfaz, como el modo servidor).

---

### 7.2 Pantalla C — Principal: origen + opciones ("Confirmar transcripción")

Es la pantalla de entrada normal, a partir de la segunda vez. Un único formulario, sin pestañas:

```
┌────────────────────────────────────────────────────────────────┐
│  Voice2Text                                    🖥 CPU   ⚙ ⊞      │
├────────────────────────────────────────────────────────────────┤
│                                                                    │
│   ┌──────────────────────────────────────────┐                   │
│   │        (icono archivo)                     │  ← zona de       │
│   │   Arrastra un vídeo o audio aquí            │    arrastrar y   │
│   │        o [ Elegir archivo… ]                │    soltar        │
│   └──────────────────────────────────────────┘                   │
│                                                                    │
│                    — o pega un enlace —                           │
│   ┌────────────────────────────────────────┐  [ Examinar ]        │
│   │ https://…                                │                    │
│   └────────────────────────────────────────┘                    │
│                                                                    │
│   [tras elegir origen, aparece:]                                  │
│   📄 reunion-comite.mp4 · 340 MB · 28:45                          │
│   Se guardará en: D:\Videos  (junto al origen)                    │
│                                                                    │
│   Modelo: small — el más preciso que corre bien en tu equipo      │
│   Idioma: automático                Salida: .txt  .md            │
│   [ Opciones ▾ ]                                                   │
│                                                                    │
│                                        [ Transcribir ]             │
└────────────────────────────────────────────────────────────────┘
```

**Comportamientos:**

- **Arrastrar y soltar** sobre la zona de archivo: resaltado con `--accent` en `dragover`, acepta un solo
  archivo (varios archivos a la vez no está en el contrato de esta versión: se ignoran los extra con un
  aviso breve *"Solo puedo procesar un archivo a la vez; se ha tomado el primero."*).
- **Enlace pegado** → botón "Examinar" llama a `probe_url()` (`probe_only`), y sin descargar nada muestra
  título, duración y extractor (`MediaInfo`, sin miniatura — el contrato no la tiene). Si el esquema no es
  `http`/`https`, **validación en línea bajo el campo**, sin llegar a tocar el núcleo: *"No reconozco ese
  tipo de enlace. Prueba con http:// o https://, o arrastra el archivo directamente."* — esto cubre
  `unsupported_url` en el caso barato de detectar (esquema), antes de que sea un error de pantalla completa.
- **"Opciones ▾"** despliega, sin ocultar el resto: modelo (con reenlace a la pantalla de modelos, §13),
  idioma (automático / español / inglés), formatos de salida (dos casillas, `.txt`/`.md`, al menos una
  marcada siempre), carpeta de destino (de solo lectura hasta que exista la operación del §1.1).
- **"Transcribir"** deshabilitado hasta que haya un origen válido (archivo elegido o enlace examinado con
  éxito) **y** al menos un formato de salida marcado.

---

## 8. Pantalla D — Trabajando

**Una barra por fase, no una barra global** (`ARCHITECTURE.md` §4.3: sumar pesos inventados obliga a saltos
hacia atrás cuando la estimación falla). La pantalla D es una única vista que cambia de contenido según
`phase`, con una **línea de fases** arriba (breadcrumbs de progreso) para que el usuario sepa en qué punto
del camino está, aunque cada fase individual no dé un porcentaje global.

### 8.1 Tabla maestra: fase → lo que se ve → cancelar

| `phase` | Título en pantalla | Tipo de barra | Texto bajo la barra | Cancelar |
|---|---|---|---|---|
| `queued` | "En cola" | — (sin barra) | `"Posición 2 · tiempo estimado ~12 min"` o `"calculando…"` si `estimated_wait_seconds` es `null` | **instantáneo** |
| `probing` | "Consultando el enlace…" | indeterminada | cronómetro + `"Comprobando qué hay en ese enlace, sin descargar nada todavía."` | instantáneo (aún no hay descarga) |
| `detecting_language` | "Preparando el audio…" | indeterminada | ver §8.3 (mensajes escalonados) | **hasta ~27 s** — botón pasa a "Cancelando…" (§9) |
| `fetching` | "Descargando…" | determinista si hay `total_bytes`; si no, indeterminada | `"12,3 MB de 45 MB · 27 %"` o, sin total, cronómetro + `"12,3 MB descargados"` | instantáneo (se corta la descarga) |
| `downloading_model` | "Descargando el modelo…" | determinista (§7.1.3) | igual que §7.1.3 | instantáneo |
| `loading_model` | "Cargando el modelo…" | indeterminada | cronómetro + `"Suele tardar unos segundos."` | rápido, no viene ejecutando el motor todavía |
| `transcribing` | "Transcribiendo…" | determinista (`processed_media_seconds / media_duration_seconds`) | `"18 % · quedan ~19 min"` (tras 20 s; antes, `"calculando…"`) + panel de transcripción en vivo (§4.4) visible | **hasta ~27 s** si el trabajo lleva menos de una vuelta de generador; en la práctica, cooperativo y rápido una vez arrancado |
| `writing` | "Guardando el resultado…" | indeterminada | cronómetro + `"Escribiendo el .txt y el .md."` | ya casi terminado; cancelar aquí pierde un trabajo casi completo — se avisa: `"Está a punto de terminar; cancelar ahora perderá el resultado."` |
| `finished` | — | pasa a Pantalla E | — | — |

**Nota sobre `fetching` sin `total_bytes`:** ocurre en HLS nativo (X, TikTok en algunos casos) donde yt-dlp
no siempre conoce el tamaño total por adelantado. No es un fallo: se trata igual que `detecting_language`,
con cronómetro y sin fingir un porcentaje.

### 8.2 Por qué "una línea de fases" y no ocho pantallas distintas

Cambiar de layout entero en cada fase generaría parpadeo constante en trabajos cortos, donde `probing`,
`loading_model` y `writing` pueden durar bien poco. La pantalla D **mantiene fijos**: la cabecera con el
origen, la línea de fases, el botón de cancelar y (desde `transcribing`) el panel de transcripción en vivo.
Solo cambian el título de fase y el contenido de la barra.

### 8.3 `detecting_language` — el tramo sin número, en detalle

Esta es la fase que el encargo señala como el mayor riesgo de diseño (7 s a los 2 min · 22 s a los 37 min,
`ARCHITECTURE.md` §4.3). Se resuelve con **mensajes escalonados por tiempo transcurrido**, sin necesitar el
dato de duración temprana del §1.2 (aunque mejora si llega):

#### 8.3.1 Componentes fijos, en todo momento de esta fase

- Cronómetro vivo `mm:ss` (§4.1), grande, siempre visible — es lo primero que confirma que no está colgado.
- Animación indeterminada, en bucle continuo (nunca una franja que se detiene).
- El panel de transcripción en vivo, vacío pero visible (§4.4): "aquí va a aparecer el texto".

#### 8.3.2 Mensaje escalonado (sin duración conocida — camino que funciona hoy)

| Tiempo transcurrido | Texto |
|---|---|
| 0-8 s | `"Leyendo el archivo y detectando el idioma…"` |
| 8-20 s | `"Sigue en marcha: los archivos largos tardan más en este paso."` |
| > 20 s | `"Todavía preparando el audio. En archivos de más de media hora esto puede llevar medio minuto; no hace falta reiniciar nada."` |

#### 8.3.3 Con duración conocida (mejora recomendada del §1.2)

Si `media_duration_seconds` llega desde el arranque de la fase, se calcula una **cota superior**, nunca un
porcentaje falso, con la tasa medida (~0,6 s por minuto de audio, interpolando 7 s/2 min · 10,5 s/10 min ·
22 s/37 min de `ARCHITECTURE.md` §4.3):

```
Preparando el audio…  00:14
Puede tardar hasta ~22 s en un archivo de esta duración.
```

Esto **no es un porcentaje**: es una cota, y se rotula como tal para no repetir el error de vender una
estimación como un hecho.

---

## 9. Cancelar: dos situaciones distintas, y el usuario tiene que notar la diferencia

El encargo es explícito: cancelar en cola es instantáneo, cancelar durante `detecting_language` (o el primer
tramo de `transcribing`) puede tardar hasta ~27 s, y **el botón no puede prometer lo que no cumple**.

| Situación | Qué pasa al pulsar "Cancelar" | Texto del botón tras pulsar |
|---|---|---|
| `queued` (en cola, no ha empezado) | Se quita de la cola al instante, la pantalla vuelve a C con un aviso breve `"Cancelado."` (toast, 3 s) | no hace falta estado intermedio: es instantáneo |
| `detecting_language` o los primeros segundos de `transcribing` | El botón se deshabilita, cambia a **"Cancelando…"** con un spinner pequeño, y aparece debajo: `"Puede tardar unos segundos en archivos largos."` | `"Cancelando…"` hasta que `state` pase a `cancelled` |
| Resto de fases (`fetching`, `loading_model`, `transcribing` ya en marcha, `downloading_model`) | Cooperativo y rápido en la práctica (el generador se consulta en cada vuelta) | mismo patrón "Cancelando…", sin la advertencia de demora larga |
| `writing` | Advertencia antes de aceptar el clic: se pierde un resultado casi terminado (§8.1) | tras confirmar, igual que el resto |

**Nunca** un botón de cancelar que desaparece o queda inerte sin explicación: si tarda, lo dice; si es
instantáneo, no finge que tarda.

---

## 10. Pantalla E — Resultado

```
┌────────────────────────────────────────────────────────────────┐
│  ✓ Listo                                                          │
│  reunion-comite.mp4 · 28:45 · idioma detectado: español (99 %)    │
│                                                                    │
│  [si fell_back_from: aviso §4.2, --warn, no bloqueante]           │
│  ℹ Se ha transcrito con la CPU: no se pudo usar la GPU (falta      │
│    el complemento de aceleración). El texto sigue siendo el mismo. │
│                                                                    │
│  📄 reunion-comite.txt · 12 KB       [ Abrir carpeta ]            │
│  📄 reunion-comite.md · 19 KB        [ Abrir carpeta ]            │
│                                                                    │
│  Tiempo de proceso: 4 min 49 s · 🖥 CPU (small, int8)              │
│                                                                    │
│  (panel de transcripción, ahora de solo lectura, con scroll)       │
│                                                                    │
│                              [ Transcribir otro ]                  │
└────────────────────────────────────────────────────────────────┘
```

- El **chip de idioma detectado** lleva su probabilidad siempre visible (no solo cuando es baja), porque es
  información que genera confianza cuando es alta y explica errores cuando es baja.
- **Aviso de confianza baja** (`language_confidence_warn_threshold`, por defecto 0,75 — cifra sin verificar,
  ADR-0002 V9): si `language_probability` cae por debajo, un banner `--warn` junto al idioma detectado:
  *"No estoy muy seguro del idioma detectado. Si el texto no encaja, vuelve a transcribir fijando el idioma
  a mano en Opciones."* — nunca se re-transcribe solo; ofrece el camino, no lo fuerza.
- "Abrir carpeta" abre el explorador de Windows en la carpeta que contiene el archivo (selecciona el
  archivo si el sistema operativo lo permite).
- El **panel de transcripción** pasa a ser el contenido final completo (no solo lo visto en vivo), de solo
  lectura, con posibilidad de seleccionar y copiar texto directamente desde la ventana sin abrir el `.txt`.

---

## 11. Errores: tabla completa, con severidad y presentación

Texto y `details` según `ARCHITECTURE.md` §5 (única fuente de verdad del copy); esta tabla añade **cómo se
presenta** cada uno, que es lo que le falta a esa tabla para ser accionable en pantalla.

**Regla de superficie:** todo código que llega como `job.error` con `state: "error"` reemplaza el contenido
de la pantalla D por una **tarjeta de error a pantalla completa** (patrón del §4.2), salvo que se indique lo
contrario en la columna "Superficie".

| Código | Superficie | Botón principal | Botón secundario |
|---|---|---|---|
| `unsupported_url` | validación en línea si es el esquema (§7.2); tarjeta completa si lo rechaza yt-dlp | "Elegir un archivo en su lugar" | — |
| `login_required` | tarjeta completa | "Descargar el archivo yo mismo" (abre el enlace en el navegador) | "Elegir otro origen" |
| `geo_blocked` | tarjeta completa | "Elegir otro origen" | — |
| `media_unavailable` | tarjeta completa | "Comprobar el enlace en el navegador" (lo abre) | "Elegir otro origen" |
| `download_failed` | tarjeta completa | **"Reintentar"** | "Elegir otro origen" |
| `extractor_outdated` | tarjeta completa | **"Copiar el comando"** (`py -3 -m pip install --upgrade yt-dlp`, a portapapeles con confirmación) | "Reintentar de todos modos" |
| `no_audio_stream` | tarjeta completa | "Elegir otro archivo" | — |
| `decode_failed` | tarjeta completa | "Elegir otro archivo" | — |
| `file_too_large` | tarjeta completa, con los dos tamaños (`size_bytes` vs `limit_bytes`) en texto llano | "Elegir otro archivo" | — |
| `file_not_found` | tarjeta completa | "Elegir otro archivo" | — |
| `model_missing` | tarjeta completa (caso raro desde la ventana, §7.1.4) | "Ir a descargar el modelo" (→ pantalla B/F) | — |
| `model_download_failed` | tarjeta completa, con bytes ya descargados | **"Reintentar descarga"** | — |
| `disk_full` | tarjeta completa, con MB necesarios y ruta en texto llano | **"Reintentar"** (tras liberar espacio) | — |
| `queue_full` | **toast**, no tarjeta — ocurre al intentar encolar, no rompe el trabajo en curso | "Ver la cola" (abre el panel de cola) | — |
| `gpu_out_of_memory` | tarjeta completa (terminó sin texto: no hubo *fallback* automático, ver nota abajo) | **"Reintentar en CPU"** | "Elegir un modelo más ligero" (→ Opciones) |
| `gpu_libraries_missing` | normalmente **no** llega como tarjeta: es un aviso `--warn` sobre un resultado ya terminado (§10) — ver nota abajo | (dentro del aviso) "Cómo instalar el complemento de GPU" | — |
| `gpu_unavailable` | igual que el anterior: normalmente aviso sobre resultado terminado | (dentro del aviso) — | — |
| `cancelled` | **neutro, no rojo** — vuelve a C con un toast `"Cancelado."` | — | — |
| `internal` | tarjeta completa, con detalle técnico expandible siempre presente | **"Reintentar"** | "Copiar el detalle técnico" |

> **Por qué `gpu_out_of_memory` se trata distinto de `gpu_libraries_missing`/`gpu_unavailable`, aunque los
> tres sean primos en el mismo `enum`.** Los dos segundos son el resultado de `resolve_device()` cayendo a
> CPU **antes** de empezar a transcribir: el trabajo termina con texto, y lo único que hace falta es avisar
> — por eso viajan como `fallback_reason` sobre un trabajo `done`, no como `job.error` (`ARCHITECTURE.md`
> §3, "la caída a CPU nunca es silenciosa"). `gpu_out_of_memory` en cambio es lo que pasa cuando el fallo
> ocurre **a mitad de una transcripción que ya estaba corriendo en GPU** — no hay vuelta atrás automática
> ("no se reintenta solo: sería multiplicar el tiempo en silencio", `ARCHITECTURE.md` §5): el trabajo
> termina en `error` sin texto, y el usuario decide con el botón. Si algún día `gpu_libraries_missing` o
> `gpu_unavailable` llegan de verdad como `job.error` (fallo a mitad de una GPU que sí había pasado la
> prueba de humo), se presentan con el mismo patrón de tarjeta completa que `gpu_out_of_memory` — el diseño
> ya cubre ese caso, solo que se espera que sea raro.

---

## 12. Avisos no bloqueantes (nunca tarjeta completa, siempre banner `--warn` cerrable)

| Situación | Dónde aparece | Texto |
|---|---|---|
| `has_video=True` tras descargar de un enlace | pegado a la fase `fetching`/`transcribing`, y se conserva en el resultado | *"Esa plataforma no ofrece hoy una pista de audio suelta: se han descargado \<X\> MB de vídeo además del audio. El texto sale igual — solo se bajó más de lo estrictamente necesario."* |
| yt-dlp con más de `ytdlp_stale_days` | junto al campo de enlace, en pantalla C | *"Tu yt-dlp tiene \<N\> días. Si algún enlace falla, prueba actualizándolo: `py -3 -m pip install --upgrade yt-dlp`"* (con botón de copiar) |
| `yt_dlp` no instalado/importable | reemplaza el campo de enlace por un texto fijo, sin desactivarlo silenciosamente | *"La descarga desde enlaces no está disponible ahora mismo (falta un componente). Puedes seguir usando archivos locales sin ningún problema."* |
| `fell_back_from` en un trabajo terminado | resultado (§10) | ver §10 |
| `language_probability` baja | resultado (§10) | ver §10 |

---

## 13. Pantalla F — Gestión de modelos

Panel superpuesto (§2), accesible desde el icono `⊞` de la cabecera:

```
┌────────────────────────────────────────────┐
│  Modelos instalados                     [×] │
│  Ocupan 464 MB en total                       │
│                                                │
│  ✓ small — el más preciso que corre bien       │
│    en tu equipo · 464 MB           [ Borrar ] │
│                                                │
│  + Añadir otro modelo ▾                        │
│    (misma lista de tarjetas que la pantalla B) │
│                                                │
│  Los modelos no se borran solos. Puedes         │
│  borrar la carpeta "models" entera cuando       │
│  quieras: se volverá a descargar si hace falta. │
└────────────────────────────────────────────┘
```

Borrar pide una confirmación de un solo paso (no un modal aparte, un cambio del botón a *"¿Seguro? →
Borrar"* durante 3 s, patrón ligero) porque es una acción de cientos de MB, pero no es tan grave como para
merecer un cuadro de diálogo modal completo.

---

## 14. Pantalla G — Ajustes avanzados

Panel superpuesto, con los valores de `settings.json` que tiene sentido exponer (no todos: `serve_port`,
`max_queued_jobs`, etc. son de operación, no de uso diario):

| Ajuste | Control | Nota en pantalla |
|---|---|---|
| Idioma | selector: Automático / Español / Inglés | — |
| Formatos de salida | dos casillas, `.txt`/`.md` | al menos una marcada siempre |
| Carpeta de destino | de solo lectura + enlace (§1.1) | hasta que exista la operación de carpeta |
| Preferencia de GPU | selector: Automático / Forzar CPU / Forzar GPU | *"Automático es lo recomendado: la herramienta ya decide lo mejor para tu hardware."* — desincentivar tocarlo sin regañar |
| Recorte de silencios (VAD) | interruptor, activado por defecto | *"Recorta silencios largos; ayuda a evitar texto repetido."* |

---

## 15. Foco, teclado y estados de foco

- **Todo control interactivo tiene un anillo de foco visible** (`outline: 2px solid var(--accent); outline-offset: 2px`), nunca `outline: none` sin sustituto.
- **Orden de tabulación lógico**: cabecera → contenido principal → acción primaria. Los paneles superpuestos
  (F, G) atrapan el foco mientras están abiertos y lo devuelven al elemento que los abrió al cerrarse.
- **`Esc`** cierra paneles superpuestos y colapsa "Opciones ▾"; **no** cancela un trabajo en curso (una
  acción tan destructiva no debe colgar de una tecla que también se usa para "cerrar esto").
- **`Enter`** en el campo de enlace dispara "Examinar" (equivalente al clic).
- **Zona de arrastrar y soltar** operable por teclado: focable, `Enter`/`Espacio` abren el mismo diálogo que
  "Elegir archivo…".
- **Botones destructivos o irreversibles** (Cancelar en curso, Borrar modelo) llevan el patrón de
  confirmación ligera del §13, nunca un modal bloqueante que interrumpa el flujo de foco de toda la ventana.

---

## 16. Responsive: tamaño de ventana, no de pantalla

Es una ventana de escritorio, no una página web: "responsive" aquí significa que la ventana se puede
redimensionar sin romper nada, no adaptarse a un móvil.

- **Tamaño inicial recomendado:** 960×680 px. **Mínimo:** 760×560 px (fijado en `webview.create_window(...,
  min_size=(760, 560))`).
- Por debajo de ~840 px de ancho, el panel de transcripción en vivo (§4.4) deja de estar siempre visible al
  lado del progreso y pasa a ser una **sección plegable** debajo de la barra de fase (mismo contenido, otro
  lugar), para no forzar scroll horizontal en ningún caso.
- Rutas y nombres de archivo largos: `text-overflow: ellipsis` con el nombre completo en el atributo
  `title` (tooltip nativo), nunca desbordamiento ni scroll horizontal de una sola línea.
- Nunca aparece una barra de scroll horizontal en el documento completo; el único scroll vertical interno
  aceptable es el del panel de transcripción en vivo/resultado, con altura máxima fija.

---

## 17. Checklist de copy para `messages.py`

Todo el texto de este documento está pensado para trasladarse **literalmente** a `messages.py` (único
archivo con texto de pantalla, `ARCHITECTURE.md` §2). Lista de lo que no estaba ya en la tabla de errores de
`ARCHITECTURE.md` §5 y que Atlas necesita redactar ahí:

- Diálogo de exclusividad de modos (§5).
- Vocabulario de calidad `quality_rank` → adjetivo (§7.1.2), como tabla de datos, no como código disperso.
- Mensajes escalonados de `detecting_language` por tiempo transcurrido (§8.3.2) y, si se implementa la
  mejora del §1.2, el texto de cota superior (§8.3.3).
- Textos de cada fase (§8.1, columna "Título en pantalla").
- Los cinco avisos no bloqueantes del §12.
- Advertencia de confianza de idioma baja (§10).
- Advertencia de cancelar durante `writing` (§8.1).
- Textos de "Cancelando…" con y sin advertencia de demora (§9).

---

## 18. Doc-as-you-go: manual de usuario

`spec/guides/` no tiene hoy un `manual-usuario.md` para BSTools: el patrón real de esta casa es que **cada
herramienta documenta su propio uso en su `README.md`** (ver `apps/MDViewer/README.md`,
`apps/Mermaid/README.md`), no en un documento central por audiencia. `apps/Voice2Text/README.md` **todavía
no existe** — es un entregable del **lote 5** (`ARCHITECTURE.md` §13), después de que Atlas construya la
interfaz real.

**Por eso este documento no escribe ese README todavía**: haría promesas sobre una interfaz que aún no
existe pixel a pixel. Lo que sí deja listo para cuando llegue el lote 5: **todo el copy de usuario final**
(pantallas B, C, D, E, tabla de errores con su presentación, avisos) ya está redactado arriba, listo para
que quien escriba el README y `messages.py` lo reutilice palabra por palabra en vez de inventar una segunda
versión del mismo texto. Cuando exista `ui.html`, la verificación de este diseño contra el DOM real
(`getBoundingClientRect()`/`getComputedStyle()`) le corresponde a Pixel, en el cierre de ese lote — no a
ciegas contra este documento.

---

Parte de [BSTools](../../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · CC0 1.0
