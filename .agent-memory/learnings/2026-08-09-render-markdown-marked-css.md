# Learning — Renderizar Markdown con marked + github-markdown-css: dos trampas

Detectado construyendo MDViewer (apps/MDViewer), verificado en DOM vivo con navegador real.

## Trampa 1: `breaks: true` rompe la documentación hard-wrapped

[Error] Los párrafos de los `.md` del repo se renderizaban como escalera rota, con saltos
de línea falsos a mitad de frase.

[Causa raíz] Se configuró `marked` con `breaks: true` razonando "es un visor de notas
locales, la gente no pone doble salto entre párrafos". El razonamiento ignoró la evidencia:
los `.md` de este repo (`CLAUDE.md`, todo `spec/`) están *hard-wrapped a ~80 columnas*, así
que cada salto del wrap manual se convertía en un `<br>`. GitHub.com usa `breaks:false`
justamente por esto.

[Solución] `breaks: false` siempre que el corpus a renderizar sea documentación técnica
hard-wrapped. Antes de tocar esta opción, mirar cómo están escritos los `.md` reales que
se van a visualizar — no asumir el caso de uso. Verificación barata y definitiva: contar
`<br>` dentro de un `<p>` en el DOM renderizado; debe ser 0.

## Trampa 2: marked no emite las clases que `github-markdown-css` espera

[Error] Las task lists (`- [x]`) mostraban viñeta **y** casilla a la vez, en vez del look
limpio de GitHub.

[Causa raíz] `github-markdown-css` trae las reglas `.task-list-item { list-style-type: none }`
y `.task-list-item-checkbox { margin: ... }`, pero el renderer por defecto de `marked` v12
**no añade esas clases** al `<li>` ni al `<input>`. Las reglas existen y nunca disparan.
Es un desajuste silencioso entre dos librerías que se suelen usar juntas: nada falla, solo
se ve mal, y leer el CSS hace creer que está cubierto.

[Solución] Re-enganchar con un selector estructural en vez de por clase, sin tocar el JS ni
recorrer el DOM en cada render:

    li:has(> input[type="checkbox"]) { list-style-type: none; }
    li > input[type="checkbox"] { margin: 0 .2em .25em -1.4em; vertical-align: middle; }

Reutilizar los mismos valores de margen que el vendor CSS ya definía, para no inventar
espaciado. `:has()` está soportado en WebView2/Chromium moderno.

## Meta-lección de proceso

Ambos defectos sobrevivieron a la revisión estática del agente que escribió el archivo, y
**los dos cayeron en el primer render-verify con navegador real**. El agente declaró con
honestidad que no tenía herramientas de navegador; el coordinador sí las tenía. Regla:
cuando un rol entrega UI y declara que no pudo verificar visualmente, el render-verify no
es opcional ni se aplaza a QA — se hace en el acto con quien tenga las herramientas, porque
el defecto es barato de encontrar ahí y caro después.
