# Learning — WebView2: el perfil de usuario rompe la promesa de "carpeta autocontenida"

**[Error]** En el spike de Voice2Text, el primer intento de abrir una ventana con pywebview
**falló**, y no por un defecto de la librería: heredó un perfil de WebView2 dejado por otro
proceso. Se resolvió fijando un `storage_path` propio de la herramienta.

**[Causa raíz]** BSTools promete que copiar una carpeta basta para que la herramienta
funcione, y el repo hace bien su parte: rutas absolutas deducidas en instalación, nada
escrito fuera. Pero **WebView2 no guarda su estado en la carpeta de la aplicación**: crea un
perfil de usuario en `%LOCALAPPDATA%`, fuera del alcance de todo lo que controlamos. Si dos
herramientas del repo comparten ese perfil por defecto —y ya van dos sobre WebView2,
MDViewer y Voice2Text— **una puede dejar el motor en un estado que rompe el arranque de la
otra**. La carpeta es autocontenida; el estado del runtime no lo es. Esa grieta no la cierra
ninguna de las cuatro reglas innegociables del repo, porque todas hablan del registro y de
las rutas, no de dónde guarda sus datos un runtime de terceros.

Lo que lo hace peligroso es cómo se manifiesta: en la máquina de desarrollo funciona (el
perfil está limpio o es el nuestro), y en la máquina del usuario aparece como **"la app no
abre"**, sin error legible y sin relación aparente con nada que hayamos escrito.

**[Solución]** Regla para toda herramienta de BSTools que use WebView2, presente o futura:
**debe poseer su propio perfil**, con un `storage_path` explícito y exclusivo, fijado antes
de crear la ventana. Nunca el perfil por defecto, nunca uno compartido.

Generalización que vale más allá de WebView2: cuando se adopte un runtime de terceros con
ventana propia (navegadores embebidos, motores gráficos), preguntar siempre **dónde guarda
su estado**. Si es fuera de la carpeta de la herramienta, hay que tomar posesión de esa
ubicación explícitamente o la promesa de "copia la carpeta y funciona" es falsa en la
segunda instalación, no en la primera — que es cuando ya nadie sospecha del runtime.
