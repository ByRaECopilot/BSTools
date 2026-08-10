---
title: "ADR-0003 — Voice2Text: cookies del navegador del usuario, desactivadas por defecto"
status: propuesto
updated: 2026-08-10
---

# ADR-0003 — Voice2Text: cookies del navegador del usuario, desactivadas por defecto

**Estado: PROPUESTO, y a propósito.** El dueño ha autorizado el uso de sus cookies, pero **hay un
diagnóstico en curso** sobre el enlace que motivó la petición (`CU24iC3grq8`). **Puede que las cookies no
hagan falta.** Este ADR **cierra la política** —bajo qué reglas se podrían usar jamás— y **condiciona la
construcción** al diagnóstico (§7). No se construye una puerta de credenciales para un problema que quizá
se arregle editando un valor.

**Supersede parcialmente [ADR-0001](ADR-0001-voice2text-stack.md) D6**, y solo si se acepta.

---

## 0. Historias de usuario

1. Como dueño **quiero poder descargar un vídeo que mi navegador sí puede ver**, aunque YouTube exija
   sesión, usando **mis propias cookies**.
2. Como dueño **quiero que esté apagado por defecto** y que se note cuando está encendido: no quiero
   descubrir que una herramienta lee mi navegador.
3. Como cualquiera que clone este repositorio público **quiero que la herramienta no toque mi navegador**
   salvo que yo lo pida explícitamente.
4. **Lo que NO se hace, ni ahora ni luego:** tokens de atestación, resolución de desafíos antibot, rotación
   de identidades, proxies, cuentas ajenas o descifrado de DRM (§3).

---

## 1. Contexto

- ADR-0001 **D6** declaró *"sin cookies ni credenciales jamás — ni de fichero ni del navegador"*, y lo hizo
  **invariante de diseño, no recorte de alcance**: era la base de la postura de §11 de aquel ADR (*"la
  herramienta nunca se autentica"*). Yo mismo escribí que cambiarlo **exigiría un ADR nuevo**. Este es.
- **Autorización del dueño, textual:** *"yo creo que si puedes usar mis cookies, ademas bajare en el mejor
  de los casos 2 videos por dia, y eso es optimisamente, lo mas seguro es 1 por semana"*.
- **Detonante:** un enlace de YouTube falló en la herramienta mientras un servicio comercial sí lo
  descargó. **La causa está sin confirmar** y hay un diagnóstico en curso.
- El spike de CPU ya midió, el 2026-08-10, que **sin cookies YouTube deja un único formato accesible y ya
  muxeado**, y que la extracción por defecto responde *"Sign in to confirm you're not a bot"*
  [O, fechado]. Es decir: la fricción es real y está documentada desde antes de esta petición.

### Sobre el volumen declarado — es un argumento de hecho, no un permiso

1-2 vídeos por semana es **indistinguible de una persona navegando**. Eso hace **irrelevante** el riesgo
de bloqueo o suspensión por abuso automatizado: no hay patrón que detectar.

**Pero eso responde a "¿me van a bloquear?", no a "¿me está permitido?".** Son preguntas distintas y este
ADR no las mezcla: el volumen elimina un **riesgo operativo**, no concede un **permiso**. Lo que se puede
o no se puede hacer se decide en §3 y §5, y sería exactamente igual con un vídeo al año.

**Consecuencia práctica, eso sí:** no se construye ningún limitador de ritmo. A ese volumen sería
maquinaria sin comprador. La salvaguarda que ya existe —**`noplaylist: True`**, que impide que un enlace
de lista dispare doscientas descargas (ADR-0001 D3)— **gana aquí una segunda justificación**: con la
cuenta identificada, una descarga desbocada ya no es solo ruido, es ruido **con tu nombre**.

---

## 2. Decisión

| # | Decisión |
|---|---|
| **C1** | **D6 se matiza, no se deroga entera.** Sigue en pie: solo `http`/`https`, **nunca una contraseña ni un usuario tecleados en la herramienta**, y **cookies jamás en la ruta de archivos locales**. Lo único que cambia: se permite que **yt-dlp lea las cookies del navegador del propio usuario** cuando este lo activa explícitamente. |
| **C2** | **Desactivado por defecto, sin excepción.** `settings.json` → `youtube_cookies_from_browser: null`. `null` = comportamiento de hoy. Ni `install.ps1` ni ninguna cáscara lo activan nunca. El repositorio es público: quien lo clone **no puede encontrarse la herramienta leyendo su navegador**. |
| **C3** | **Solo `cookiesfrombrowser`. `cookiefile` sigue prohibido.** Un fichero de cookies exportado es un **artefacto de credenciales duradero** que queda en disco y que el usuario olvida; leer del navegador no crea nada nuevo. Si algún día hiciera falta, es otra decisión y otro ADR, con ese coste declarado. |
| **C4** | **Nuestro código nunca ve una cookie.** Se le pasa a yt-dlp **el nombre del navegador**, y yt-dlp hace el resto. Esta es la forma fuerte de la invariante de privacidad: **no es disciplina, es arquitectura** (§4). |
| **C5** | **Cuando está activo, se ve.** La interfaz y `GET /health` indican que la descarga usa cookies. Un uso silencioso de credenciales es exactamente lo que este ADR existe para impedir — mismo principio que ADR-0002 §8.7: el estado observable dice lo que **pasa**. |
| **C6** | **La frontera de §3 es parte de la decisión, no un comentario.** Autenticarse como uno mismo, sí. Fingir ser otra cosa o vencer un control, no — ni con ADR. |
| **C7** | **La construcción queda condicionada al diagnóstico** (§7). Si el remedio es editar `settings.json`, **no se construye**: este ADR queda como autorización registrada y política escrita, lista para activarse el día que haga falta. |

---

## 3. La frontera que no se cruza

**El principio, en una línea:** la línea está entre **presentarse como quien uno es** y **fingir ser otra
cosa o vencer un control**.

**De este lado (permitido, C1):** usar las cookies del propio usuario es **autenticarse como él mismo**.
La herramienta **no puede acceder a nada que el dueño no pueda ver ya con su navegador abierto**. No hay
elevación de privilegio, no hay suplantación, no hay control de acceso ajeno rodeado: se presenta la
credencial que la plataforma le dio a él.

**Del otro lado (fuera, y se escribe ahora que es barato):**

| Fuera | Por qué |
|---|---|
| Generar **tokens de atestación** (PO tokens y similares) | Es fabricar una prueba de ser un cliente oficial que no somos. Eso es fingir, no identificarse |
| Resolver **desafíos antibot** o CAPTCHAs | El desafío **es** el control. Vencerlo es eludirlo |
| **Rotar identidades**, proxies, o cuentas que no sean del usuario | Deja de ser "su sesión" y pasa a ser evasión |
| Cookies de **terceros**, compartidas o incluidas en el repositorio | Credenciales ajenas. Ni se plantea |
| **Descifrar DRM** | Ya estaba fuera (ADR-0001 §11) y sigue fuera |

**Ninguna de estas se resuelve con "otro ADR que lo argumente".** Se listan aquí para que la propuesta
llegue ya contestada: **quedan fuera del producto.** La única que admitiría discusión futura es
`cookiefile` (C3), y solo por ser un mecanismo distinto para lo mismo, no por cruzar la frontera.

---

## 4. Privacidad: invariante verificable, no intención

Las cookies son **credenciales de sesión vivas**. Las reglas, en forma comprobable:

1. **Nuestro código nunca lee una cookie.** Se pasa `cookiesfrombrowser=(navegador,)` en las opciones de
   yt-dlp y nada más. **Verificable:** `grep` de `youtube_cookies_from_browser` debe devolver **exactamente
   dos sitios** — donde se lee el ajuste y donde se pasa a yt-dlp. Si aparece un tercero, algo está
   tocando lo que no debe.
2. **No se copian, no se persisten, no se escriben en `work/`.** No creamos ningún artefacto de
   credenciales: es la razón de C3.
3. **No se registran.** `error.technical` sigue siendo **una línea** y **nunca** incluye el diccionario de
   opciones de yt-dlp — que es por donde se filtraría.
4. **No salen a ningún sitio** salvo a la propia plataforma con la que yt-dlp habla.
5. **Solo en la ruta de enlaces.** La transcripción de archivos locales no las toca jamás.

**Y una consecuencia que el usuario merece saber antes de activarlo, no después** [E, a confirmar en la
implementación]: yt-dlp **lee el almacén de cookies completo de ese navegador**, no solo las de YouTube;
no ofrece un filtro por dominio. Además, en Windows puede exigir **cerrar el navegador** para poder leer
el almacén. Las dos cosas van al README (§6), en la sección de activación, no en las notas al pie.

---

## 5. Términos de servicio: la sección de ADR-0001 §11 hay que reescribirla

ADR-0001 §11 dice: *"lo defendible es que **la herramienta nunca se autentica**… es una invariante de
diseño"*. **Eso deja de ser cierto cuando el usuario activa esta opción**, y dejarlo contradicho sería
peor que cambiarlo. Texto que lo sustituye:

- **Por defecto, la herramienta sigue sin autenticarse.** Es el modo de fábrica y el que ve cualquiera que
  clone el repositorio. Ahí la postura de ADR-0001 §11 sigue intacta palabra por palabra.
- **Cuando el usuario activa las cookies, la herramienta actúa como su navegador.** Accede a lo que él ya
  puede ver. **No elude ningún control**: presenta la credencial que la plataforma le dio.
- **Lo que el usuario asume al activarlo, y debe entender:** descargar contenido puede **contravenir los
  términos** de la plataforma, y a partir de ese momento lo hace **con su cuenta identificada**, no de
  forma anónima. Cualquier consecuencia —limitación, suspensión— recae sobre **esa cuenta**. Es su
  decisión y es su cuenta.
- **Lo que la herramienta sigue sin hacer, esté activado o no:** eludir medidas técnicas de protección,
  descifrar DRM, resolver desafíos antibot o usar cuentas ajenas (§3).
- Sigue **sin ser asesoramiento legal**.

---

## 6. Qué debe decir el README

Sección propia, **"Cookies del navegador (desactivado por defecto)"**, con estos puntos y en este orden:

1. **Para qué sirve:** algunos vídeos exigen sesión iniciada; con esto la herramienta los ve como los ve
   tu navegador.
2. **Es TU cuenta.** Lo que descargues queda asociado a ella, y las consecuencias también.
3. **Qué lee:** yt-dlp lee el almacén de cookies **completo** del navegador que indiques, no solo el de
   YouTube. En Windows puede pedir que **cierres el navegador**.
4. **Qué NO hace:** no guarda ninguna cookie en la carpeta de la herramienta, no las registra en ningún
   log, y **no puede acceder a nada que tú no puedas ver ya**.
5. **Cómo se activa y cómo se apaga:** una clave en `settings.json`, y volver a `null` lo desactiva.
6. **Sigue sin poder** con contenido de otras cuentas, DRM ni bloqueos regionales.

---

## 7. La condición: qué dice el diagnóstico (C7)

**No se construye nada hasta saber la causa real.** La tabla, para que el diagnóstico sea directamente
accionable:

| Diagnóstico | Remedio | ¿Se construyen cookies? |
|---|---|---|
| **`player_client` caducado** | editar `youtube_player_clients` en `settings.json` | **NO** — y sería la prueba de que **D26 pagó exactamente como se justificó**: el dato que más rápido caduca vive en datos y se arregla sin tocar un `.py` ni esperar una versión |
| **Bloqueo antibot** (*"confirm you're not a bot"*) | cookies | **Sí** |
| **Restricción de edad** | cookies de una cuenta verificada | **Sí** |
| **Restricción de región** | **ninguno de los dos**: haría falta un proxy, que está **fuera** por §3 | **NO** — se documenta como límite |
| **Vídeo privado, borrado o con DRM** | ninguno | **NO** |

**Mi preferencia, dicha antes de conocer el resultado para que no parezca acomodada:** si aplica la
primera fila, **no se construye**. No construir es más barato que construir, y **cada camino de
credenciales es superficie permanente**: un ajuste que hoy nadie usa es un ajuste que dentro de un año
alguien activa sin leer esta sección. La autorización del dueño queda registrada y la política, escrita:
el día que de verdad haga falta, esto se acepta y se construye en un lote pequeño.

---

## 8. Consecuencias

**Lo que se gana**

- Acceso a lo que el dueño ya puede ver, en los casos en que la fricción de YouTube lo impedía.
- Una frontera dibujada **antes** de que alguien proponga cruzarla, que es cuando es barata (§3).

**Costes aceptados**

| Coste | Mitigación |
|---|---|
| **La postura "nunca se autentica" deja de ser absoluta** | Sigue siéndolo **por defecto** (C2), que es lo que ve quien clona el repositorio. §5 lo dice sin adornos en vez de dejarlo contradicho |
| Credenciales de sesión vivas en juego durante la descarga | C4: **nuestro código nunca las ve**. La invariante es arquitectónica, no disciplinaria |
| yt-dlp lee el almacén **completo** del navegador | Se declara en el README **antes** de activar (§4, §6), no se descubre después |
| Una opción más que puede activarse sin entender el alcance | Apagada por defecto, visible cuando está encendida (C5), y explicada en el README |
| Superficie permanente para un uso de 1-2 vídeos por semana | Es justo el argumento de §7 para **no construirla** si el diagnóstico dice que no hacía falta |

---

## 9. Estado

**Propuesto.** Se acepta —o se archiva— cuando llegue el diagnóstico del enlace `CU24iC3grq8`, aplicando
la tabla de §7.

- Si se acepta: **matiza D6** de ADR-0001 y **sustituye su §11** por el texto de §5.
- Si se archiva: ADR-0001 D6 y §11 **siguen íntegros**, y este documento queda como **autorización
  registrada con su política ya escrita**, listo para retomarse sin volver a discutir nada de esto.
