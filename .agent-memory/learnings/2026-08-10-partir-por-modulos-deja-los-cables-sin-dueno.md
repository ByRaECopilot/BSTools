# Learning — Partir el trabajo por módulos deja los cables sin dueño

**[Error]** En Voice2Text repartí la construcción en lotes definidos por **archivo**: uno hizo
`fetch.py` (descargar desde un enlace), otro `jobs.py` (la cola de trabajos), otro la ventana.
Los tres pasaron su criterio de aceptación y se dieron por cerrados. Al construir la interfaz
apareció que **pegar un enlace y obtener texto no funciona en absoluto**: `jobs.py` rechaza
cualquier origen que no sea un archivo local, y nadie conectó nunca el descargador con la
cola. La funcionalidad que el dueño pidió expresamente —*"pega un link de YouTube y pásalo a
texto"*— no existía, pese a que sus dos mitades estaban construidas y verificadas.

**[Causa raíz]** Definí cada lote por **lo que produce** (un archivo, un módulo) y no por
**lo que el usuario puede hacer al terminarlo**. Con ese corte, el "cable" que une dos módulos
no cae dentro de ninguno: el de `fetch.py` no podía tocar `jobs.py` (fuera de alcance), el de
`jobs.py` construyó antes de que `fetch.py` existiera, y el de la ventana tenía prohibido
tocar el motor. **Cada agente hizo exactamente lo correcto dentro de su encargo**, y el hueco
quedó entre los encargos, que es donde nadie mira.

Agravante: los criterios de aceptación también eran por módulo, así que **todos dieron verde**
sobre una función que no se puede ejecutar de principio a fin. Un tablero de lotes en verde
describía un sistema incompleto.

**[Solución]** Al descomponer trabajo entre varios agentes:

1. **Definir al menos un lote por recorrido completo de usuario**, no solo por módulo. "Pegar
   un enlace y obtener un `.txt`" es un lote; "escribir `fetch.py`" es una tarea dentro de él.
2. **Nombrar al dueño de cada cable en el momento de partir**, no después. Si el trabajo A
   produce algo que el trabajo B debe consumir, la conexión pertenece explícitamente a uno de
   los dos, y se escribe en su encargo.
3. **Al menos un criterio de aceptación debe ser de extremo a extremo.** Si todos los
   criterios se pueden cumplir sin ejecutar el recorrido entero, el tablero mentirá.
4. Cuando un agente reporte "esto lo rechaza el módulo de al lado, fuera de mi alcance",
   tratarlo como **hallazgo de coordinación propio**, no como una pieza pendiente más: es la
   señal de que la descomposición tenía un hueco.

Vale para cualquier fan-out. **El paralelismo reparte el trabajo, pero no reparte las
costuras** — esas se asignan a mano o no las hace nadie.
