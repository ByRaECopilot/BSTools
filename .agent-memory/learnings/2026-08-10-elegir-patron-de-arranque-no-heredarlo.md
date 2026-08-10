# Learning — Elegir el patrón de arranque, no heredarlo del vecino

**[Error]** Al definir el stack de `apps/Voice2Text` fijé el patrón "Interfaz web local"
casi por reflejo, y mandé a ARIADNA a mapear únicamente BrandAssets y Mermaid — las dos
herramientas que ya usan ese patrón. El dueño tuvo que corregir: *"no tiene que ser
exactamente como los que vio, por ejemplo este es otro, MDViewer"*.

**[Causa raíz]** Confundí "cuál es el precedente más parecido" con "cuál es el patrón
correcto". `spec/constitution/tech-stack.md` define **cinco** patrones de arranque y dice
explícitamente *"elige uno antes de escribir nada"* — es una decisión de diseño, no una
herencia. Al pedir el mapeo solo de las apps del patrón que yo ya había asumido, convertí
al subagente en confirmador de mi sesgo: ARIADNA no podía cuestionar la premisa porque
nunca se le dio el espacio para hacerlo. Peor, la comparación que devolvió (BrandAssets vs
Mermaid) era una elección entre dos variantes del mismo patrón, disfrazada de análisis de
alternativas.

Detalle agravante: uno de los argumentos con los que se eligió plantilla ("Mermaid gana
porque no tiene dependencias externas") era irrelevante para una app que iba a arrastrar
faster-whisper, CTranslate2, PyAV y yt-dlp. El razonamiento venía copiado del contexto de
otra herramienta junto con la plantilla.

**[Solución]** Antes de fijar el patrón de arranque de una herramienta nueva:

1. Enumerar los **cinco** patrones de la constitución y descartar explícitamente los que no
   aplican, con una línea de por qué. El descarte escrito es lo que impide el reflejo.
2. Cuando se delegue el mapeo de precedentes, encargar el barrido sobre **todos** los
   patrones plausibles, no solo sobre el que ya se dio por bueno. Un subagente al que se le
   nombra el destino no audita el destino.
3. Al copiar una plantilla, revalidar sus **razones** contra la herramienta nueva. Una razón
   heredada sin verificar es peor que no tener razón, porque parece justificada.

Detonante genérico y reutilizable en cualquier proyecto: **si la premisa de la delegación ya
contiene la respuesta, el subagente solo puede confirmarla.** Cuando una decisión de diseño
esté realmente abierta, hay que decírselo al agente y darle las alternativas a comparar,
incluso las que uno cree perdedoras.
