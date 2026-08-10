# Learning — Inicializar sin error no prueba que el dispositivo funcione

**[Error]** En el spike de GPU de Voice2Text se descubrió que `WhisperModel(device="cuda")`
**se construye sin lanzar excepción aunque falten las DLL de CUDA**. El fallo real
(`RuntimeError`) no aparece hasta la primera llamada a `transcribe()`. Cualquier detección
del tipo *"intento construir el modelo en GPU; si no revienta, hay GPU"* habría dado un
falso positivo: la herramienta se declararía en modo GPU, aceptaría el trabajo, y reventaría
minutos después con el usuario esperando.

**[Causa raíz]** Se asumió que el constructor valida el entorno de ejecución. En librerías
que cargan dependencias nativas de forma perezosa, **la construcción solo valida argumentos**;
la carga real de las bibliotecas ocurre en la primera operación de cómputo. La inicialización
y la capacidad son dos cosas distintas, y solo una de las dos se estaba comprobando.

Lo que lo hace especialmente traicionero es que **el falso positivo es silencioso y tardío**:
no falla al arrancar, cuando sería barato y evidente, sino en mitad de un trabajo largo.

**[Solución]** Para detectar una capacidad de hardware o una dependencia nativa opcional,
**la comprobación tiene que ejercitar la ruta de verdad**: una prueba de humo activa al
arrancar —modelo mínimo, entrada trivial, inferencia real— y solo entonces declarar el
dispositivo disponible. Nunca inferirlo de que un constructor no lanzó excepción.

Contraste útil que salió del mismo spike: cuando la librería **sí** sabe validar, lo hace
bien. `float16` en una GPU Pascal falla con un `ValueError` limpio **en la construcción**,
porque CTranslate2 consulta la capacidad real de cómputo antes de tocar los pesos. O sea: el
constructor valida lo que puede consultar barato (capacidades declaradas del hardware) y no
valida lo que exige cargar bibliotecas nativas. Saber dónde cae cada comprobación es lo que
distingue una detección fiable de una ilusión.

Generalizable a cualquier dependencia opcional con backend nativo (CUDA, aceleradores de
vídeo, drivers de base de datos, bibliotecas criptográficas): **si la ausencia se manifiesta
tarde, la detección tiene que provocarla temprano.**
