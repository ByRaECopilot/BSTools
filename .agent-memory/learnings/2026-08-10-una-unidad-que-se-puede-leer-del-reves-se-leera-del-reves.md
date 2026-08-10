# Learning — Una unidad que se puede leer del revés se leerá del revés

**[Error]** Transmití al dueño que "10 minutos de audio tardan ~28 minutos de proceso",
citando una medición de **2,8× tiempo real**. La convención del proyecto, escrita en
ADR-0001 §3.1, es *duración del audio ÷ tiempo de proceso; más alto es mejor*. Con esa
convención, 2,8× sobre 10 minutos son **3,6 minutos**, no 28. **Multipliqué donde había que
dividir: error de factor 8.**

Peor todavía fue el encadenado. Al llegar la medición buena (1,15×, es decir 8,7 minutos), se
la presenté como una **mejora** frente a mis 28 falsos. La realidad es la contraria: frente al
dato que teníamos entonces (3,6 min), la herramienta resultó ser **2,4 veces más lenta** de lo
prometido. Le di una corrección a peor disfrazada de buena noticia — el peor resultado
posible, porque destruye la señal justo cuando más falta hace: era el argumento honesto a
favor del complemento de GPU.

**[Causa raíz]** Publiqué un **ratio adimensional** en un mensaje dirigido a una persona, con
la convención documentada en otro archivo. Un "2,8×" no lleva encima su propio sentido: sirve
igual para "2,8 veces más rápido" que para "2,8 veces más lento", y quien lo lee completa el
hueco con su intuición. La mía completó mal, y como el número resultante era plausible, nada
lo delató.

**[Solución]** La magnitud que ve una persona —README, interfaz, informes a dirección— se
expresa **en unidades absolutas**: "8,7 minutos de proceso por cada 10 minutos de audio". El
ratio sobrevive como campo técnico interno y **no aparece jamás en un texto para humanos**.

Reutilizable fuera de este proyecto, en cualquier métrica con dirección ambigua: "veces más
rápido", "veces más lento", tasas, factores de compresión, ratios de mejora. Si la unidad
admite dos lecturas opuestas, no se publica cruda — se publica ya interpretada.

**Corolario que no debe fundirse con esto** (son dos errores distintos con arreglos
distintos): el **dato sintético** también falló, pero de otra forma. Su sesgo es
**sistemáticamente optimista** — un clip TTS corto midió 2,8× donde el audio real da 1,15×.
Fundir ambos en un "las cifras fallan en las dos direcciones" guardaría en el canon lo
contrario de lo ocurrido, y llevaría a alguien a confiar en una medición sintética creyéndola
neutra. **El sintético siempre miente hacia arriba; lo que falló hacia abajo fue la
comunicación.**
