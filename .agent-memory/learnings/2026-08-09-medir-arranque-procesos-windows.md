# Learning — Medir el arranque de un proceso en Windows: el instrumento mentía

Detectado cerrando MDViewer. El coordinador (Atenea) fue quien introdujo el error;
el desarrollador (Atlas) fue quien lo refutó.

[Error] Reporté una regresión de rendimiento grave —1033 ms para abrir el segundo archivo,
6× peor que el arranque en frío— y mandé a un agente a investigarla con una hipótesis
elaborada sobre carga de ensamblados y JIT. La regresión no existía. Se perdió un ciclo
completo de un agente persiguiendo un fantasma.

[Causa raíz] Medí con `Measure-Command { Start-Process ... -Wait }`. El cmdlet
`Start-Process -Wait` de PowerShell añade ~900-1000 ms de sobrecarga propia que no tiene
nada que ver con el programa medido. El número era plausible (mil milisegundos es
exactamente lo que "se siente lento"), coherente entre corridas, y encajaba con una
hipótesis técnica creíble — por eso no lo dudé. **Un número reproducible no es un número
correcto: la reproducibilidad también confirma un sesgo constante del instrumento.**

[Solución] Dos reglas, en este orden:

1. **Antes de acusar al código, mide el control.** Compila un `.exe` vacío —`static void
   Main() {}`, cero líneas— y mídelo con el mismo instrumento. Si el binario vacío también
   marca ~1000 ms, el problema es el instrumento, no el código. Este experimento cuesta dos
   minutos y es lo que refutó la falsa regresión. Aplica igual a latencia de red, de disco o
   de arranque de cualquier cosa: **siempre existe un "control vacío" que se puede medir.**
2. **Para tiempos de proceso en Windows, usa `[Diagnostics.Process]::Start()` +
   `WaitForExit()`**, no `Start-Process -Wait`. Con el método correcto, el mismo binario
   medía 52-235 ms según la máquina y el momento.

Corolario de proceso, para quien coordina: al devolver un hallazgo a un especialista,
entrégalo **como síntoma, no como diagnóstico**, y dile explícitamente "mide antes de
arreglar; si resulta ser un límite físico, dilo con datos y lo aceptamos". Esa frase fue lo
único que impidió que el agente implementara mi hipótesis equivocada — de hecho la probó,
midió que no cambiaba nada (57.8 ms vs 58.4 ms) y **revirtió el cambio**. Si la hubiera
mandado como orden, hoy habría una optimización inútil en el código y la causa real seguiría
sin encontrarse.
