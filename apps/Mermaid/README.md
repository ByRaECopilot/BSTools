# Mermaid

Editor gráfico de diagramas de flujo. Arrastras formas, las unes con flechas y
el **código Mermaid se genera en tiempo real**. Con vista previa del diagrama
renderizado y exportación a `.mmd`, `.svg` y `.png`.

Doble clic en el icono **Mermaid** de esta carpeta → arranca un pequeño servidor
local (en `127.0.0.1`) y se abre en tu navegador. Necesita **Python** (solo la
biblioteca estándar; no instala nada) y funciona **sin conexión a internet** —
la librería Mermaid va empaquetada en la carpeta. El servidor solo sirve para
**guardar y cargar** tus diagramas en la subcarpeta `graphs/`.

---

## Instalación

```powershell
cd Mermaid
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

El instalador:

1. Comprueba que hay **Python** (no instala dependencias: el servidor usa solo la
   biblioteca estándar).
2. Crea el acceso directo **Mermaid** dentro de esta carpeta, con icono propio.
   Apunta al lanzador, que arranca el servidor **minimizado** (la consola no
   molesta) y abre el navegador.
3. Añade al menú contextual de los archivos `.mmd` la opción *Abrir con el
   editor Mermaid*, que lo abre **ya cargado** (con sus posiciones si al lado hay
   un `.layout.json`).

Escribe en `HKCU:\Software\Classes`: **no necesita administrador**.

> En Windows 11, la opción del menú contextual está dentro de
> *Mostrar más opciones* (`Shift+F10`).

Para desinstalar: `powershell -ExecutionPolicy Bypass -File .\uninstall.ps1`

Si mueves la carpeta, vuelve a ejecutar `install.ps1` (el acceso directo y el
registro guardan rutas absolutas).

---

## Uso

1. **Añade formas.** Haz clic en una forma de la barra izquierda para soltarla en
   el centro, o arrástrala al lienzo.
2. **Conéctalas.** Pasa el ratón sobre un nodo: aparecen cuatro puntos azules en
   sus lados. Arrastra desde uno de ellos hasta otro nodo para crear una flecha.
3. **Edita el texto.** Doble clic en un nodo o en una flecha.
4. **El código aparece solo** en el panel derecho, actualizándose con cada
   cambio. Y al revés: **puedes editar el código a mano y el diagrama se
   actualiza** — cambia una etiqueta, añade un nodo o una flecha en el texto y
   el lienzo se reconstruye solo. La pestaña *Vista previa* muestra el diagrama
   renderizado por Mermaid.
5. **Exporta:** botón *Copiar* (al portapapeles), o descarga `.mmd`, `.svg` o
   `.png`.

El diagrama se guarda solo en el navegador (`localStorage`): al reabrir el
editor sigue donde lo dejaste.

## Guardar y cargar (carpeta `graphs/`)

En la barra izquierda, sección **Diagramas**: escribe un nombre y pulsa
*Guardar*. Cada diagrama se guarda como **dos archivos** en `graphs/`:

- `nombre.mmd` — el código Mermaid, reutilizable en cualquier sitio.
- `nombre.layout.json` — posiciones, formas, colores y dirección, para restaurar
  el lienzo **exactamente** como lo dejaste.

Debajo aparece la lista de diagramas guardados: clic en uno para cargarlo, o en
la **✕** para borrarlo (borra sus dos archivos). Al abrir un `.mmd` desde el
menú contextual del Explorador, se carga directamente; si tiene un
`.layout.json` al lado, con sus posiciones.

La carpeta `graphs/` está en `.gitignore`: tus diagramas son locales, no se
suben al repositorio.

### Controles

| Acción | Cómo |
|---|---|
| Mover un nodo | Arrastrarlo |
| Conectar | Arrastrar desde un punto azul del nodo a otro nodo |
| Editar texto | Doble clic en nodo o flecha |
| Editar el código | Escribir en el panel derecho (el diagrama se actualiza) |
| Seleccionar | Clic (aparece una barra con color / editar / borrar) |
| Borrar | Tecla `Supr` con algo seleccionado |
| Deshacer / rehacer | `Ctrl+Z` / `Ctrl+Y` |
| Mover el lienzo | Arrastrar el fondo |
| Zoom | Rueda del ratón, o los botones `+` / `−` / *Ajustar* |
| Cambiar dirección | Botones `TD` / `LR` / `BT` / `RL` arriba |
| Tema claro / oscuro | Botón del sol arriba |

---

## Formas y flechas

**8 formas** de Mermaid: Proceso `[ ]`, Redondeado `( )`, Terminal `([ ])`,
Subproceso `[[ ]]`, Base de datos `[( )]`, Círculo `(( ))`, Decisión `{ }` y
Preparar/hexágono `{{ }}`.

**4 tipos de flecha:** flecha `-->`, línea `---`, punteada `-.->` y gruesa `==>`.
Elige el tipo en la barra izquierda **antes** de conectar; para cambiar una
flecha ya creada, selecciónala y pulsa otro tipo.

**Color de nodo:** selecciona un nodo y elige un color en la barra flotante. Se
traduce a una línea `style` en el código.

---

## Editar el código a mano

El panel de código es editable y funciona en los dos sentidos: lo que escribas
se parsea y se vuelca al lienzo. Se conserva la posición de los nodos que ya
existían (por su id) y los nuevos se colocan cerca de sus vecinos. Si el texto
tiene un error de sintaxis, el lienzo se queda como estaba y aparece un aviso
rojo hasta que lo corrijas.

El parser entiende el `flowchart` habitual, no solo lo que genera el editor:

- Las 8 formas y las 4 flechas.
- Etiqueta de flecha en las dos notaciones: con tubería `-->|"texto"|` **y en
  línea** `-- texto -->`, `-. texto .->`, `== texto ==>`.
- Multidestino con `&`: `A --> B & C` (y `A & B --> C`) se expanden a varias
  flechas.
- Cadenas `A --> B --> C`.
- **Subgráficos** (`subgraph ... end`): se *aplanan* — se conservan sus nodos y
  flechas, pero la caja del grupo no se dibuja en el lienzo (sí aparece en la
  *Vista previa*, que usa el Mermaid real).
- Líneas `style` (color de nodo) y entidades HTML en las etiquetas
  (`&lt;`, `&gt;`, `<br/>`).

Puedes pegar directamente el `flowchart` que te genere Claude u otra IA. Lo que
quede fuera de este subconjunto (otros tipos de diagrama, sintaxis exótica) dará
un aviso en el lienzo, pero la **Vista previa lo renderiza igual** porque usa el
motor completo de Mermaid.

---

## Lo que no hace (y por qué)

- **Solo diagramas de flujo** (`flowchart`). Secuencia, Gantt, clases, etc.
  tienen otra gramática y otra interacción; se puede añadir más adelante si hace
  falta.
- **No usa la última versión de Mermaid automáticamente.** La librería está
  empaquetada en `vendor/` para funcionar sin internet; para actualizarla, baja
  un `mermaid.min.js` nuevo a esa carpeta.

---

## Problemas comunes

**El navegador dice que el archivo no es seguro / no carga el código.** Ábrelo
con un navegador moderno (Edge, Chrome, Firefox). El acceso directo ya usa el
predeterminado del sistema.

**Pegué un diagrama y el lienzo da error, pero quiero verlo.** Cambia a la
pestaña *Vista previa*: usa el motor completo de Mermaid y renderiza cualquier
`flowchart` válido (y otros tipos de diagrama), aunque el lienzo editable no
sepa reconstruirlo. El aviso rojo solo afecta a la reconstrucción gráfica, no a
la vista previa.

**No aparece la vista previa.** Cambia a la pestaña *Vista previa*; si el código
tiene algún carácter que Mermaid rechaza, se muestra el error en rojo en vez de
romperse.

**Copiar al portapapeles no funciona.** Algunos navegadores lo bloquean al abrir
por `file://` muy antiguos; usa el botón `.mmd` para descargar, o actualiza el
navegador.

**Moviste la carpeta.** Vuelve a ejecutar `install.ps1`.

---

Parte de [BSTools](../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · CC0 1.0
