# Learning — Commitear por rutas explícitas deja trabajo huérfano fuera de esas rutas

**[Error]** Durante una sesión con muchos agentes en paralelo sobre el mismo repositorio,
comiteé cada lote con rutas explícitas (`git add apps/<herramienta>/...`) para no arrastrar
trabajo ajeno a medias. Funcionó para lo que buscaba. Pero **el arquitecto estaba editando
`spec/decisions/`**, fuera de esas rutas, y **173 líneas de decisiones —incluidas dos que
gobernaban el código que sí se comiteó— se quedaron solo en el árbol de trabajo**. Lo
descubrió un agente al final del día, no yo: durante horas anuncié "todo commiteado y subido"
mientras la mitad del razonamiento vivía únicamente en disco.

**[Causa raíz]** Adopté la regla correcta —*añadir por ruta, nunca `git add -A`*, para no
mezclar trabajo de agentes concurrentes— y no vi su punto ciego: **protege de lo que no
quieres incluir, pero no avisa de lo que sí falta.** Cada commit era correcto y el conjunto
estaba incompleto. Y como cada uno terminaba en un `push` con éxito, la señal que yo leía era
"todo salvado".

Agravante propio de este reparto: los agentes tenían **prohibido tocar los documentos de
arquitectura** justamente para evitar choques, así que ninguno de ellos podía comitearlos. Al
centralizar esa escritura en un solo rol, centralicé también la responsabilidad de guardarla —
y no la asumí.

**[Solución]** Cuando se comitee por rutas explícitas en una sesión con varios agentes:

1. **Después de cada commit, mirar `git status` completo, no solo las rutas comiteadas.** Lo
   que quede modificado es la lista de lo que nadie está salvando.
2. **Antes de anunciar "todo subido", verificarlo** en vez de deducirlo del éxito del último
   `push`. Un `push` correcto solo prueba que se subió lo que se añadió.
3. Si un rol tiene la escritura exclusiva de una carpeta (aquí, el arquitecto sobre
   `spec/decisions/`), **el commit de esa carpeta necesita dueño explícito**. Nadie más puede
   hacerlo, así que si su dueño no lo hace, no lo hace nadie.
4. El síntoma a vigilar: **documentos de decisión modificados durante horas sin aparecer en
   ningún commit.** El código se comitea solo porque alguien lo construye y lo entrega; la
   documentación se queda atrás porque su autor sigue editándola.

Generalizable: la regla "añade por ruta, nunca `-A`" es buena y se mantiene. Lo que faltaba es
su contrapartida — **una revisión periódica de lo que queda fuera**.
