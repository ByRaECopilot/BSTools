# Learning — No vender cifras de rendimiento sin medirlas

**[Error]** Al proponer el soporte de enlaces en Voice2Text le dije al dueño que `yt-dlp`
*"puede bajar solo la pista de audio — 10-20x menos descarga que el video"*. El spike del
lote 0 lo desmintió parcialmente: hoy, sin cookies, el único cliente de yt-dlp que esquiva
el bloqueo anti-bot de YouTube devolvió **un stream ya muxeado (video+audio)** en los tres
vídeos probados, no una pista de audio pura. El ahorro existe (el muxeado cae en resolución
baja), pero no es el que anuncié, y el dueño tomó una decisión con mi cifra delante.

**[Causa raíz]** Confundí *lo que la herramienta es capaz de hacer* con *lo que la
plataforma entrega hoy*. `yt-dlp` sí sabe pedir audio-only; YouTube es quien decide si lo
ofrece a un cliente anónimo, y eso cambia con sus defensas anti-bot. Cité la capacidad
teórica como si fuera un resultado medido, y lo hice con la falsa precisión de un rango
numérico ("10-20x"), que es justo lo que hace que un dato suene verificado.

**[Solución]** Al presentar un beneficio cuantitativo que el dueño va a usar para decidir:

1. **Etiquetar el origen de cada cifra**: medida en esta máquina / estimada / capacidad
   teórica del proveedor. Un número sin etiqueta se lee como medido.
2. Cuando la cifra dependa de un **tercero que puede cambiarla unilateralmente** (una
   plataforma, una API), no es una propiedad del diseño: es una observación con fecha de
   caducidad. Se dice así.
3. Si la cifra sostiene una decisión, **medirla antes de que se decida**, no después. Aquí
   el spike llegó tarde: el dueño ya había aprobado el alcance de enlaces.
4. Corregirse ante el dueño en cuanto la medición contradiga lo afirmado, señalando la
   afirmación original — no dejar que el dato nuevo pase como si siempre hubiera sido ese.

Vale para cualquier proyecto: **una cifra afirmada sin medir es una deuda que cobra el
spike, y a veces la cobra producción.**
