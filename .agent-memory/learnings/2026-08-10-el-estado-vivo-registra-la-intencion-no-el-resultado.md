# Learning — El estado vivo registra la intención, no el resultado

**[Error]** En Voice2Text se pidió GPU explícitamente (`--device-preference cuda`) y la
transcripción corrió en CPU **sin emitir un solo aviso**, violando una regla dura del ADR
("la caída de GPU a CPU nunca es silenciosa"). Al diagnosticarlo apareció el mismo patrón en
dos sitios distintos: el arnés de línea de comandos y, más grave, la capa de trabajos que
alimenta la interfaz de usuario.

**[Causa raíz]** El dispositivo se decide en dos momentos, no en uno:

1. **Antes de cargar** — `resolve_device()` dice qué se *va a intentar*. Es una **intención**.
2. **Al cargar** — la prueba de humo puede fallar (una DLL ausente solo se manifiesta en la
   primera inferencia real) y el sistema cae a CPU. Ese es el **resultado**.

Ambas capas guardaban el valor del paso 1 y **descartaban el del paso 2**. El motor hacía su
trabajo bien: registraba la caída y su motivo. Nadie los leía. El campo existía, el
serializador ya lo contemplaba, y la intención de diseño era correcta — solo que la
implementación guardaba el dato equivocado.

Lo que lo hace peligroso es que **el fallo es asimétrico**: el archivo exportado al final sí
llevaba el dato correcto, porque se construye a partir del resultado real. Solo mentía el
**estado en vivo**, que es justo el que la interfaz consulta mientras el usuario espera. Un
indicador "GPU activa" construido sobre él habría sido falso precisamente en el caso que la
regla existía para prevenir: alguien instala 2 GB de librerías, corre a velocidad de CPU y no
se entera nunca.

**[Solución]** Cuando una decisión pueda revisarse durante la ejecución, **el estado
observable se actualiza con el resultado, nunca se deja con la intención**. En concreto:

1. Si una operación devuelve la decisión efectiva, **léela y sobreescribe** la previsión. Un
   valor de retorno descartado suele ser un bug esperando.
2. Al revisar código, sospechar de todo campo de estado que se asigne **una sola vez, antes**
   de la operación que puede cambiarlo.
3. Cuando el usuario **pidió algo explícitamente** y no se le da, avisar de forma prominente
   y con el motivo concreto — no basta con registrarlo. Degradar en silencio algo que se
   solicitó de forma expresa es peor que fallar.
4. Un aviso enviado al registro de errores (`logger.warning` a *stderr*) **no es un aviso al
   usuario** si la herramienta nunca configura el registro y el usuario mira otra salida.
   Aquí el motor sí avisaba, y aun así nadie lo vio.

Generalizable: reintentos con otro proveedor, degradación de calidad, rutas alternativas de
red. Siempre que exista un plan B silencioso, **el estado tiene que contar cuál se ejecutó**.
