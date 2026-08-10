# Learning — El paralelismo por defecto invalida las mediciones de rendimiento

**[Error]** Lancé en paralelo tres agentes sobre la misma máquina: uno midiendo velocidad de
transcripción con audio en español (V1), otro verificando marcas de tiempo (lote 1.b) y otro
midiendo GPU. Los tres ejecutaban faster-whisper, que satura CPU por diseño. La medición de
V1 salió **0,93× tiempo real** frente a los 2,8× de una medición anterior, y el agente
—correctamente— **se negó a darla por válida**: documentó con `tasklist` otro `python.exe`
con más de una hora de CPU acumulada y subiendo. La cifra no sirve, y hay que repetir el
trabajo en una ventana limpia.

**[Causa raíz]** Mi regla de orquestación es "paralelismo por defecto: lo independiente se
despacha concurrentemente". Apliqué el criterio de independencia **lógica** —ninguna tarea
necesitaba el resultado de otra— sin ver que compartían un **recurso físico exclusivo**: la
CPU. Para casi todo el trabajo (leer, escribir, razonar) esa contención solo cuesta tiempo de
reloj y no cambia el resultado. **En una medición de rendimiento, el recurso compartido ES lo
que se está midiendo**, así que la contención no ralentiza el experimento: lo falsea.

Agravante: la cifra contaminada era lo bastante verosímil como para haber pasado. Si el
agente no llega a comprobar qué más corría en la máquina, hoy tendríamos un número falso en
un ADR y una promesa falsa en la pantalla del usuario — y sería ya la cuarta cifra de
velocidad equivocada de este proyecto.

**[Solución]** El paralelismo por defecto tiene una excepción que hay que nombrar antes de
despachar el lote: **una tarea que mide rendimiento (tiempo, throughput, memoria, VRAM) se
ejecuta SOLA.** Concretamente:

1. Al partir el trabajo, además de "¿qué es independiente?", preguntar **"¿qué mide un
   recurso compartido?"**. Eso se serializa aunque sea lógicamente independiente.
2. Al encargar una medición, instruir explícitamente al agente que **verifique la máquina
   antes de confiar en el número** (`tasklist`, uso de CPU/GPU) y que reporte la cifra como
   contaminada si encuentra competencia. Aquí funcionó porque el agente lo hizo por criterio
   propio; no puedo depender de eso.
3. Vale para GPU y disco igual que para CPU: dos agentes midiendo VRAM en la misma tarjeta se
   estorban tanto como dos midiendo CPU.

Regla corta: **paralelizar el trabajo, serializar las mediciones.**
