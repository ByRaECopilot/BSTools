# Banco de pruebas — grupos + estilos libres (ADR-0004)

Runner de Node **sin dependencias** (no hay `npm install`, no hay build). Carga el
`editor.js` real de la herramienta y ejercita sus funciones puras o casi-puras
dentro de un `vm.Script` de Node con un shim mínimo de `document`/`localStorage`.
No abre navegador, no simula arrastre ni SVG real: eso queda para pruebas E2E
(ver "Qué queda fuera" más abajo).

## Cómo correrlo

Una línea, desde cualquier sitio (funciona con rutas con espacios):

```
node "D:\_IAG\Tools\apps\Mermaid\test\run-tests.js"
```

O, parado dentro de la carpeta del proyecto:

```
node test/run-tests.js
```

Sale con código `0` si todo está en verde, `1` si hay al menos un fallo (para
que un CI o un hook de commit lo pueda usar como gate).

## Qué esperar mientras Atlas construye la feature

Este banco se escribió **en paralelo** a la implementación (ADR-0004). Varios
casos referencian funciones que hoy (2026-08-15) todavía no existen en
`editor.js` (`normalizeState`, `serializeState`, `classNameFor`) o sintaxis que
el parser actual descarta a propósito (`subgraph`, `classDef`, `class` — ver
el comentario en `editor.js:499-501`, "Los subgrupos se aplanan"). Esos casos
**nacen en rojo** con un mensaje explícito tipo:

```
FALLO A9: subgraph anidado - el grupo interno lleva parent al externo (D4)
  Error: classNameFor() no existe todavia en editor.js (se esperaba que
  Atlas la anadiera - ADR-0004 S3)
```

Eso es correcto y esperado — no es un fallo del banco. La regla de oro: los
casos del archivo `01-regresion-formas-y-parser.cases.js` **sí** deben estar
en verde desde ya (protegen lo que la herramienta ya hace hoy).

## Estructura

```
test/
  README.md            este archivo
  dom-shim.js           el shim de document/localStorage + la tecnica del "puente"
  assert.js              aserciones minimas (assertEqual, assertThrows...)
  fnv1a.js                referencia independiente de FNV-1a-32 (para verificar
                          el sufijo _x<hash8> de classNameFor)
  run-tests.js           el runner: descubre cases/*.cases.js y los corre
  cases/
    01-regresion-formas-y-parser.cases.js        (verde HOY)
    02-idempotencia-ida-y-vuelta.cases.js         A1, A2, A2b, A10
    03-classname-determinismo.cases.js            classNameFor (S2bis)
    04-anidamiento.cases.js                       A9, D4
    05-retrocompat-normalizestate.cases.js        A3, D5, D6, D1
    06-emision-orden-y-errores.cases.js           orden de emision + R7 + errores
```

Para añadir un caso: crear (o editar) un `*.cases.js` en `test/cases/` que
exporte `module.exports = function (t) { t.test('nombre', () => { ... }); }`.
El objeto `t` trae `test`, las aserciones (`assertEqual`, `assertDeepEqual`,
`assertTrue`, `assertMatch`, `assertThrows`), `fresh()` (una instancia nueva
del editor cargado, aislada de otros casos) y los atajos `parseOk`,
`buildFrom`, `roundTrip` (ver `run-tests.js`).

## La técnica: cómo se carga `editor.js` real sin tocarlo

`editor.js` no es un módulo (no tiene `module.exports`) y se apoya en mucho
DOM global (`document.querySelector('#canvas')`, etc.) que solo existe en un
navegador. `dom-shim.js` construye un DOM falso mínimo (solo los ids/clases
que `editor.js` toca de verdad — ver el árbol en `buildDom()`) y ejecuta el
archivo con `vm.Script#runInContext` sobre un objeto contextificado.

Los `function nombre(){}` de nivel superior (incluidas las que Atlas todavía
tiene que añadir: `normalizeState`, `serializeState`, `classNameFor`...) se
cuelgan como propiedades de ese objeto — es el comportamiento estándar de
`function`/`var` en el ámbito superior de un script, incluso en modo
estricto — así que son invocables directamente como `sandbox.parseCode(...)`.

Las variables `let`/`const` de nivel superior (`state`, `selection`, `view`...)
**no** se cuelgan como propiedades: viven en un entorno léxico propio del
contexto. Para leerlas o inyectarlas desde el test se usa un "puente": se dejan
en `sandbox.__bridge__` (una propiedad normal, visible en ambas direcciones) y
se ejecuta un `vm.Script` de una línea que hace `state = __bridge__;` o
`__bridge__ = state;`. Ver `getVar()`/`setVar()` en `dom-shim.js`.

Por eso `buildCode()` (que lee el `state` de módulo) se prueba como si fuera
pura: `buildFrom(sandbox, data)` primero inyecta `data` como `state` y luego
llama a `buildCode()`.

## Qué cubre el banco

- **Prioridad 1 — ida y vuelta idempotente y punto fijo** (`02-*`): A1 (sin la
  parte de arrastre, que es E2E), A2 (`buildCode(parseCode(buildCode(parseCode(x))))`
  === `buildCode(parseCode(x))`, comparado **desde la segunda pasada**, no
  contra la entrada — corrección explícita del encargo, las clases ajenas se
  disuelven), A2b (nombre de clase estable al insertar/borrar un grupo), A10
  (recargar el propio `.mmd` generado recupera el color del grupo).
- **Prioridad 2 — determinismo de `classNameFor`** (`03-*`): los dos ejemplos
  literales que trae el propio ADR-0004 (S2bis), `stroke-width` fuera del
  nombre, formato con regex, y el sufijo `_x<hash8>` verificado contra una
  implementación independiente de FNV-1a-32 (ver "Punto abierto" abajo).
- **Prioridad 3 — anidamiento sin pérdida silenciosa** (`04-*`): A9, D4.
- **Prioridad 4 — regresión de lo que hoy funciona** (`01-*`): las 8 formas,
  `<br/>`, cilindro `[( )]`, `-. "texto" .->`, `==>`, `A & B -->`, etiquetas
  con tubería. Esto debe estar en verde **ya**, antes de que Atlas toque nada.
- **Prioridad 5 — retrocompatibilidad `.layout.json`** (`05-*`): usa como
  fixtures los DOS `.layout.json` reales que ya existen en `graphs/` (`SDG` y
  `"OPC Office"`), sin tocarlos. Migración `color`→`colors`, invariante de
  `anchor` (D1), ruptura de ciclos y padres colgantes (D6), normalización de
  hex a 6 dígitos minúscula.
- **Contrato de emisión + OWASP** (`06-*`): orden fijo (huérfanos → grupos →
  aristas fuera de subgraph → `style` → `classDef` alfabético → `class`),
  ningún nodo se declara dos veces, precedencia `style` > `class`, saneado de
  `styleExtra` a pares `[A-Za-z-]+:[^;<>"']+` (evita que un valor con
  `<script>` vuelva al código — Mermaid corre con `securityLevel:'loose'`),
  y los tres errores que el ADR exige que **nunca** se resuelvan en silencio
  (`end` sobrante, `subgraph` sin cerrar, colisión de id grupo/nodo).

## Qué queda FUERA (exige navegador — no es responsabilidad de este banco)

- **Arrastre real** (D3, A4, A5, A7): el delta entero `(dx,dy)` al mover una
  caja, que la caja siga conteniendo a un hijo arrastrado, y el undo tras
  arrastrar. Requiere simular `pointerdown/pointermove/pointerup` reales sobre
  elementos SVG posicionados y coordenadas de pantalla — el propio encargo lo
  marca como fuera de este banco.
- **SVG real / `getComputedStyle()`** (A6): que el título de una caja salga
  realmente claro (`rgb(255,255,255)`) y no negro sobre el fondo — eso ya se
  midió una vez con un render real por HTTP (ADR-0004 §2bis, "Medición del
  2026-08-15"); este banco solo prueba que el generador de código *elige* el
  camino `classDef`+`class` para grupos, no que el renderer lo pinte bien.
- **Guardar/recargar contra el servidor** (`server.py`, `/save`, `/load`):
  necesita un servidor HTTP real corriendo. Este banco sí prueba
  `normalizeState` directamente con los ficheros reales de `graphs/`, que es
  la parte de la retrocompatibilidad que sí es lógica pura.
- **La UI de color** (dos `<input type="color">` + hex, presets, `Agrupar`,
  `Desagrupar`, `Sacar del grupo`): son controles del DOM real, no lógica.

## Qué necesito de Atlas para que el banco corra en verde

1. **Nombres y firmas exactos** de las funciones nuevas del ADR (`S3`):
   `normalizeState(s)` (pura, recibe y devuelve el estado), `serializeState()`
   y `classNameFor(colors, styleExtra)`. El banco asume estas firmas por
   lectura del ADR; si Atlas necesita desviarse, avisar para ajustar los
   casos (`03-*`, `05-*`) en vez de que queden en rojo por un desajuste de
   contrato en lugar de un bug real.
2. **Punto abierto sin resolver en el ADR**: el sufijo `_x<hash8>` de
   `classNameFor` se define como "FNV-1a-32 de la cadena canónica completa de
   declaraciones" pero no hay un ejemplo con número. El banco (`03-*`) asume
   la lectura más literal — que la "cadena canónica" es `styleExtra` tal cual
   (verbatim), ya el propio `styleExtra` se describe como "verbatim" en el
   esquema (ADR §2). Si Atlas hashea otra cosa (p. ej. concatenando
   fill/stroke/text también), ese caso concreto se ajusta con un cambio de una
   línea — el resto de la prueba (determinismo, formato, mismo prefijo con
   distinto sufijo) sigue siendo válido igual.
3. **`colors.text` no persistido si es derivable** (D5): el banco no asume una
   representación exacta (con o sin `text` explícito) al comparar el color
   recuperado tras un round trip — compara el **efectivo** (`text` guardado o
   `textOn(fill)`). Si `normalizeState`/`parseCode` terminan teniendo un
   comportamiento más estricto que eso, decírmelo para afinar el caso de A10.
4. **`$('#groups')`**: el shim ya incluye una capa `<g id="groups">` en el SVG
   falso (antes de `#edges`, como pide el ADR §3 paso 7) por si `drawGroup()`
   la busca por id — así ese paso del plan no bloquea la carga del script en
   el banco aunque no se pruebe el dibujo en sí (es DOM/E2E).

## Verificación de este banco

Se corrió `node run-tests.js` contra el `editor.js` de HOY (sin la feature) y
salió con el reparto esperado: `01-*` (regresión) en verde completo,
`02-06` en rojo con mensajes claros de "función/comportamiento no existe
todavía". El detalle exacto de OK/FALLO queda en el informe de esta entrega,
no en este README (para no tener que mantenerlo sincronizado a mano en cada
commit de Atlas).
