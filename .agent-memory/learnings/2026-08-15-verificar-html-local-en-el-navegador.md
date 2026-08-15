# Learning — Verificar HTML local en el navegador del agente

[Error] Para comprobar de verdad si un diagrama Mermaid renderizaba (en vez de teorizar sobre la
sintaxis), escribi un `_render-test.html` junto al `vendor/mermaid.min.js` de la herramienta y trate de
abrirlo. Dos intentos fallidos seguidos antes de acertar:

1. `preview_start` con `file:///D:/_IAG/Tools/apps/Mermaid/_render-test.html` — la pagina se abrio,
   pero como **snapshot estatico**: los `<script src="...">` externos no se ejecutan. Sintoma que
   despista: `ERROR: mermaid is not defined`, que parece un problema del bundle y no lo es.
2. Levantar `python -m http.server` con Bash y `navigate` a `http://127.0.0.1:4499/...` —
   *"blocked by policy and cannot be opened in the Browser pane"*.

[Causa raiz] El panel de navegador solo confia en servidores que **el mismo** ha arrancado via
`preview_start`. `file://` no ejecuta scripts externos y la IP cruda `127.0.0.1` no esta en la
politica; `localhost` servido por un preview server si.

[Solucion] La via que funciona, en este orden:

1. Crear `.claude/launch.json` con una entrada que sirva la carpeta:
   `runtimeExecutable: "python"`, `runtimeArgs: ["-m","http.server","<puerto>","--bind","127.0.0.1","--directory","<carpeta>"]`.
   Ojo: **si ya dejaste un `http.server` suelto en ese puerto, `preview_start` se niega** ("port in use
   by python.exe, not a preview server") — matalo antes.
2. `preview_start` por `name` → devuelve `tabId`, y `navigate` a `http://localhost:<puerto>/...`.
3. Medir con `javascript_tool` en vez de screenshot: `getBBox()`, contar `.node` / `.cluster` /
   `.edgePaths path`. El **screenshot falla si el panel no esta visible** ("not compositing frames"),
   asi que los numeros son mas fiables que la imagen. Bonus: permite comparar variantes en la misma
   pagina (renderice el mismo grafo en `LR` y en `TD` y compare proporciones).
4. Limpiar al terminar: `preview_stop`, borrar el HTML de prueba y el `launch.json` temporal.

Vale la pena: gracias a esto la respuesta al dueno dejo de ser "deberia renderizar" y paso a ser
"29 nodos, 5 cajas, 42 flechas, cero errores, y estas proporciones exactas".
