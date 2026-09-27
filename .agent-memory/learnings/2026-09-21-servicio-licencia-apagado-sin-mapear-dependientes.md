# Learning — Recomendar apagar un servicio sin mapear quién depende de él

[Error] Atenea recomendó pasar `hasplms` (Sentinel LDK License Manager) a Manual en la limpieza de servicios de arranque de Windows. Tras aplicarlo, un programa del dueño (probablemente Wasp3D, que estaba en ejecución) mostró "Sentinel key not found".

[Causa raíz] Se clasificó el servicio por su nombre ("¿usas llave Sentinel?") y se delegó la respuesta al dueño, que no sabía que un programa suyo dependía de él. No se cruzó el servicio contra los procesos y el software instalados (vendor de cada .exe en ejecución, carpetas de Program Files) antes de recomendar.

[Solución] Antes de recomendar apagar un servicio de licencias, drivers o middleware de terceros (HASP/Sentinel, FlexLM, CodeMeter, etc.), cruzarlo con los procesos activos y el software instalado; ante la duda, clasificarlo como "no tocar" y explicar por qué. Los servicios de licencias NUNCA van en la lista verde: la falla aparece al día siguiente, lejos de la causa.
