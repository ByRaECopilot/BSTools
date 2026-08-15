---
title: "ADR-0004 — Mermaid: subgraph como concepto de primera clase y color libre por nodo"
status: propuesto
updated: 2026-08-15
---

# ADR-0004 — Mermaid: `subgraph` de primera clase y color libre

**BLUF.** La caja del grupo se **deriva** de sus hijos: no se guarda `x/y/w/h` de la caja. El requisito
del dueño *"que las cajas mantengan sus posiciones al guardar"* se cumple igual — y de hecho **solo se
cumple así**. La pertenencia se guarda como **puntero del hijo al padre** (`node.parent`), no como lista
de hijos. El color pasa a `colors:{fill,stroke,text}` en hex libre, con migración perezosa desde la
paleta. **V1 verificada empíricamente el 2026-08-15 [M]: falló en parte** — el emisor deja de ser
uniforme (nodos con `style`, grupos con `classDef`+`class`, §2bis); el modelo de datos aguanta intacto.
Queda solo el visto del dueño sobre §1.

**El requisito, tal como está redactado, está mal planteado** y conviene decirlo: pide *guardar la
posición de la caja*, es decir **un campo**; lo que el dueño quiere es un **observable** ("la caja
aparece donde la dejé"). Guardar el campo es precisamente lo que rompería el observable — una caja con
`x/y` propios y unos hijos con `x/y` propios divergen en cuanto se arrastra un hijo, y acabas con una
caja que no contiene a sus hijos. Lo que hoy falla **no es geometría**: es que `subgraph` no existe en el
modelo (`parseCode` lo descarta, `editor.js:502`) y que `setStateFrom` (`editor.js:1126`) reconstruye el
estado campo a campo, así que cualquier clave nueva se pierde al cargar del servidor. Se arregla la
pertenencia y la persistencia; la geometría sale gratis.

---

## 1. Las seis decisiones

**D1 — Geometría del grupo: DERIVADA de los hijos.** La caja es `bbox(descendientes) + PAD 24 +
cabecera 26`, recalculada en cada `render()`. No se persiste ni `w/h` ni el origen.
*Por qué:* las posiciones de los hijos ya se persisten y ya sobreviven a guardar/recargar, así que la
caja también; y una caja almacenada es dato derivado que puede divergir → el estado inconsistente que el
criterio prohíbe. *Alternativa descartada:* caja con `x/y/w/h` propios (permitiría cajas vacías grandes y
márgenes a mano, a cambio de un invariante "la caja contiene a sus hijos" que habría que reimponer en
cada arrastre).
**Única excepción:** un grupo **sin hijos** no tiene nada de lo que derivar. Lleva `anchor:{x,y}` — que
no es dato derivado, es el único dato que hay. **Invariante de esquema: `anchor` existe si y solo si el
grupo no tiene descendientes.** En cuanto gana un hijo, `normalizeState` borra el `anchor`.

**D2 — Pertenencia: explícita, y guardada en el hijo.** `node.parent = '<idGrupo>'` (ausente = raíz).
*Por qué:* con puntero único la doble pertenencia es **irrepresentable**, y borrar un nodo no obliga a
limpiar listas en ningún grupo (con `children:[...]` sí, y ese olvido es un clásico). *Alternativa
descartada:* pertenencia geométrica ("lo que caiga dentro"): con cajas derivadas es circular — la caja
sale de los hijos, los hijos saldrían de la caja.
**Sacar un nodo del grupo solo por comando** (`Sacar del grupo` en la barra flotante), nunca arrastrando.
*Por qué:* el arrastre soltando fuera es ambiguo con grupos anidados o solapados, y convertiría cada
arrastre en una mutación silenciosa del modelo. *Coste asumido:* arrastrar un hijo lejos estira la caja;
eso **es** el feedback de que sigue dentro.

**D3 — Coordenadas de los hijos: absolutas, como hoy.** *Por qué:* `drawEdge`, `borderPoint`, `nodeAt`,
`fitView` y `placeNodes` trabajan en mundo; con coordenadas relativas habría que transformar en los cinco
sitios y todo `.layout.json` existente cambiaría de significado. *Alternativa descartada:* relativas +
transform SVG anidado (elegante para el dibujo, cara en todo lo demás).
**Contrato de arrastre del grupo:** se calcula **un delta entero** `(dx,dy)` ya redondeado a 10 y se suma
igual a todos los descendientes. Nunca se redondea nodo a nodo: eso destruiría los offsets relativos.

**D4 — Anidamiento: el modelo lo soporta entero, la UI v1 no lo crea.** `group.parent` igual que
`node.parent`. El parser reconstruye la profundidad que venga y el emisor la re-emite; el lienzo dibuja
las cajas anidadas (la derivación ya es recursiva, sale gratis). Lo que v1 **no** ofrece es un comando
para anidar a mano ni re-parentar arrastrando. **Nada se pierde en silencio.** *Alternativa descartada:*
aplanar al parsear (es lo que se hace hoy y es justo el bug).

**D5 — Color libre: `colors:{fill,stroke,text,strokeWidth}` en hex, clave NUEVA.** La paleta
`NODE_COLORS` sobrevive solo como **presets** de la barra flotante. Migración **perezosa** en
`normalizeState`: si un nodo trae `color` (clave de paleta) y no trae `colors`, se expande a
`{fill,stroke,text:textOn(fill),strokeWidth:'2px'}` y se borra `color`; `color:'default'` → sin `colors`.
Se escribe siempre en formato nuevo. *Por qué clave nueva y no reusar `color`:* el valor viejo
`color:'#3b82f6'` significa *"preset azul"* (relleno `#dbeafe`), no *"rellena de #3b82f6"* — una unión
hex/clave sobre el mismo campo es ambigua para siempre. *Alternativa descartada:* migración en bloque con
versión de esquema (obligaría a versionar localStorage, que no tiene envoltura).

**D6 — Compatibilidad: detección estructural, sin ramas por versión.** `normalizeState(s)` es idempotente
y es el **único** camino de entrada al estado (desde `load()`, `setStateFrom()` y `restore()`): rellena
`groups:[]` si falta, migra `color`→`colors`, borra `parent` que apunte a un grupo inexistente, rompe
ciclos de `parent` y quita `anchor` a los grupos con hijos. Un `.layout.json` de 1.3.x carga sin tocar
nada. El `.mmd` emitido es Mermaid válido para cualquier renderer (§2). `server.py` sube el sobre a
`'version': 2` (una línea, `server.py:174`) y **nadie lo lee**: el cliente normaliza por estructura.

---

## 2. Estado y `.layout.json`

```js
state = {
  dir: 'LR', seq: 71,
  nodes:  [{ id, shape, x, y, label, w, h, parent?, colors?, styleExtra? }],
  edges:  [{ id, from, to, label, style }],          // sin cambios
  groups: [{ id, label, parent?, dir?, anchor?, colors?, styleExtra? }],
}
// colors = { fill:'#c62828', stroke:'#6b1414', text:'#ffffff', strokeWidth:'2px' }  (todas opcionales)
//   · hex SIEMPRE normalizado a 6 dígitos en minúscula al entrar (parser y UI): '#fff' -> '#ffffff'.
//     Sin esto, el nombre de clase de §2bis no sería determinista.
//   · `text` es OPCIONAL y NO se almacena si se puede derivar: ausente = textOn(fill) (WCAG,
//     editor.js:191-213). Solo se guarda cuando venía explícito en el fichero o el usuario lo forzó.
//     Es la misma regla de D1 aplicada al color: no se persiste lo derivable.
// styleExtra = declaraciones no reconocidas, verbatim: 'stroke-dasharray:5 5'
// w/h de nodo siguen siendo derivados (sizeNode) y siguen persistiéndose: no se toca eso aquí.
```

`.layout.json` — el sobre no cambia de forma, solo de contenido:

```json
{ "tool": "BSTools Mermaid", "version": 2, "name": "SDG", "savedAt": "...",
  "state": { "dir": "LR", "seq": 71,
    "nodes": [ { "id": "SF", "shape": "rect", "x": -300, "y": 40, "label": "search-frontend<br>...",
                 "w": 210, "h": 52, "parent": "Frontends",
                 "colors": { "fill": "#c62828", "stroke": "#c62828", "text": "#fff", "strokeWidth": "2px" } } ],
    "edges": [ { "id": "e30", "from": "SF", "to": "SB", "label": "", "style": "arrow" } ],
    "groups": [ { "id": "Frontends", "label": "Frontends" },
                { "id": "g7", "label": "Sin puerto", "anchor": { "x": 300, "y": 500 } } ] } }
```

**Contrato de generación (`buildCode`).** Indentación de 4 espacios por nivel; `subgraph`/`end` al nivel
del padre, contenido a +4.

```
flowchart LR
    <declaraciones de los nodos huérfanos (parent ausente), en orden de state.nodes>
    subgraph Frontends["Frontends"]
        direction LR                      ← solo si group.dir existe (dato transportado, el lienzo no lo interpreta)
        SF["search-frontend<br>..."]
        subgraph Interno["Interno"]       ← anidado, mismo esquema
            ...
        end
    end
    <TODAS las aristas, al nivel raíz, en orden de state.edges>

    style SF fill:#c62828,stroke:#6b1414,stroke-width:2px,color:#ffffff      ← NODOS: style
    classDef bs_c62828_6b1414_ffffff fill:#c62828,stroke:#6b1414,stroke-width:2px,color:#ffffff
    class Frontends,Backends bs_c62828_6b1414_ffffff                          ← GRUPOS: classDef + class
```

- **Huérfanos primero, aristas después de todos los grupos, bloque de estilos al final**, separado por
  una línea en blanco — como hoy. Dentro del bloque, el orden es fijo: (a) `style` de nodos en orden de
  `state.nodes`; (b) `classDef` **ordenados alfabéticamente por nombre de clase**; (c) `class`, una línea
  por clase en ese mismo orden alfabético, con los ids de grupo separados por coma en orden de
  `state.groups`.
- Las aristas **nunca** se emiten dentro de un `subgraph`: renderiza igual y evita la sutileza de
  Mermaid por la que una arista declarada dentro pertenece a la caja.
- **Cada nodo se declara exactamente una vez**: el emisor lleva un `Set` y, si un nodo quedara sin
  emitir (grupo huérfano no saneado), lo emite en la raíz. Ninguna rama puede terminar sin declararlo.
- Orden de declaraciones dentro de `style` y de `classDef`: `fill, stroke, stroke-width, color,
  styleExtra`. Fijo, para que el ida y vuelta sea **byte-idéntico** (criterio A2).
- `color:` se emite siempre que haya `fill`, con `colors.text ?? textOn(colors.fill)`. En los grupos esto
  **no es cosmético**: sin él Mermaid pinta el título en negro sobre el `#c62828` del dueño (medido).

## 2bis. La asimetría medida y el nombrado de clases

**Medición del 2026-08-15 [M]** (render real con `vendor/mermaid.min.js` 11.16.0 por HTTP,
`getComputedStyle()` sobre el `rect` del cluster y sobre el label):

| Destino | `style ... fill/stroke` | `style ... color:` | `classDef` + `class` |
|---|---|---|---|
| Nodo (`N1`) | se aplica | **se aplica** | idéntico resultado |
| Grupo (`G1`) | se aplica | **se IGNORA** (título en `rgb(0,0,0)`) | **se aplica**, título en `rgb(255,255,255)` |

Por eso el emisor deja de ser uniforme. **Nodos con `style`** (funciona para las tres propiedades y es lo
que la herramienta ya emite hoy: diff mínimo). **Grupos con `classDef` + `class`** (único camino que
colorea el título). No se unifica todo a `classDef` porque obligaría a reescribir el estilado de nodos,
que está medido como correcto, sin ganar nada.

**Nombre de clase — determinista y derivado del contenido, nunca de un contador de sesión:**

```
bs_<fill>_<stroke>_<text>            p. ej.  bs_c62828_6b1414_ffffff
```

- Hexes sin `#`, ya normalizados a 6 dígitos minúscula; componente ausente → `none`
  (`bs_c62828_none_ffffff`). `stroke-width` no entra en el nombre: se deriva de `stroke`.
- Si `styleExtra` no está vacío, se añade `_x<hash8>`, con `hash8` = FNV-1a de 32 bits de la cadena
  canónica completa de declaraciones, en hex de 8 dígitos. Sin ese sufijo, dos grupos con los mismos
  colores y distintos `styleExtra` compartirían nombre con contenidos distintos.
- **Consecuencia buscada:** dos grupos con los mismos colores comparten `classDef`, el nombre es función
  pura del contenido (estable ante insertar o borrar grupos, y ante el orden de creación en la sesión) y
  el punto fijo de A2 se sostiene. Un contador `bs_1..bs_n` habría bastado para renderizar y habría roto
  la idempotencia en cuanto cambiara el orden.

**Contrato de parseo (`parseCode`).**
- Cabecera: `^subgraph\s+(.*)$`. Si lo que sigue es `id["Etiqueta"]` o `id[Etiqueta]` → id + etiqueta;
  si es un token válido a secas (`subgraph Frontends`) → id = etiqueta = ese token; si lleva espacios o
  comillas → etiqueta literal e id sintético `g<seq>`. El emisor siempre normaliza a `id["Etiqueta"]`.
- Pila de grupos: `subgraph` empuja, `end` desempila; `end` sobrante → error explícito; `subgraph` sin
  cerrar al terminar → error explícito. Nunca se ignora ninguno de los dos.
- **Pertenencia = primera aparición del id dentro de un cuerpo `subgraph`** (regla de Mermaid). Menciones
  posteriores no re-parentan.
- `direction XX` dentro de un grupo → `group.dir`. Ya no se descarta.
- **Colisión id de grupo con id de nodo → error visible** ("El grupo X usa el mismo id que un nodo"),
  nunca se resuelve solo.
- `style <id> ...`: se parte por comas y se leen `fill`, `stroke`, `color`→`text`, `stroke-width`; el
  resto va a `styleExtra` **saneado** a pares `[A-Za-z-]+:[^;<>"']+` (§6, R7). Aplica a nodos **y** a
  grupos. Se acabó el `COLOR_BY_STROKE`: un `fill:` suelto ya se recupera.
- **`classDef <nombre> <declaraciones>` y `class <id1,id2,...> <nombre>` son OBLIGATORIOS en el parser**,
  no opcionales: son lo que el propio emisor escribe para los grupos (§2bis). Sin ellos, recargar un
  `.mmd` generado por esta misma herramienta perdería el color de las cajas — el bug exacto que la
  feature viene a matar. `classDef` se lee con el mismo troceador que `style`; `class` aplica esos
  colores a cada id, sea nodo o grupo. Precedencia: si un id recibe `class` y `style`, **gana `style`**
  (es lo más específico, y es lo que hace Mermaid).
- **Las clases se disuelven al importar**: no se guarda el nombre de clase en el estado, solo los colores
  por elemento; al emitir se regeneran por contenido. Consecuencia declarada: un `.mmd` ajeno con
  `classDef` compartidos sale **reescrito**, no idéntico. A2 exige punto fijo **a partir de la segunda
  pasada**, no identidad con la entrada.
- El `seq` de arranque considera también los ids de grupo.
- **Fuera de alcance, y sigue fallando en voz alta:** la forma abreviada `A:::miClase`, `linkStyle`,
  `click` y `%%`. Hoy revientan el parseo con "Forma no reconocida"; no es una regresión y no se toca en v1.

---

## 3. Funciones a tocar (en orden de implementación)

1. `state` inicial (`editor.js:39`) — añadir `groups: []`.
2. **`serializeState()` / `normalizeState(s)` (nuevas)** — una sola serialización y un solo saneador;
   `normalizeState` hace la migración de D5 y las cuatro reparaciones de D6.
3. `snapshot`/`restore`/`undo`/`redo` (`118-142`) — las **cuatro** literales `{nodes,edges,dir,seq}` pasan
   a `serializeState()`. Si queda una sin cambiar, se pierden los grupos al deshacer.
4. `setStateFrom` (`1124`) — construir con `normalizeState(s)`, **no** con un literal campo a campo.
5. `load` (`926`) — `state = normalizeState(JSON.parse(raw))`. `save` (`923`) no se toca.
6. `groupBox(g)` (nueva) — bbox recursivo de descendientes + `PAD_G 24` + cabecera 26; si no hay hijos,
   caja fija de 180×80 en `anchor`.
7. `drawGroup(g)` (nueva) + capa `<g id="groups">` en `index.html:320`, **antes** de `#edges`.
8. `render` (`331`) — limpiar y dibujar grupos primero (raíz→hojas, para que el anidado quede encima).
9. `drawNode` (`216`, líneas 224-227) — pintar desde `n.colors`, no desde `NODE_COLORS[n.color]`.
10. **`classNameFor(colors, styleExtra)` (nueva)** — el nombrado determinista de §2bis, con el FNV-1a de
    32 bits en una función aparte de 6 líneas (legible, sin dependencias).
11. `buildCode` (`347`) — contrato §2 completo: `style` para nodos, `classDef`+`class` para grupos,
    `color:` siempre con `colors.text ?? textOn(colors.fill)`.
12. `parseCode` (`460`, línea 502 y 504-507) — contrato §2 completo, **incluidos `classDef` y `class`**
    con la precedencia `style` > `class`.
13. `applyParsed` (`546`) — reconstruir `state.groups`, arrastrar `parent`/`colors`, y **conservar el
    `anchor` de los grupos que ya existían**.
14. `layeredLayout` (`600`, bloque 620-631) — ordenar cada capa por ruta de grupo antes de repartir, para
    que los miembros de un grupo caigan juntos (una comparación, sin layout jerárquico real).
15. `groupAt()` (nueva) — hit-test **solo en la cabecera y el borde**, nunca en el interior: el interior
    debe seguir siendo paneo y clic a los nodos. `nodeAt` (`706`) no se toca.
16. `startGroupDrag` + rama `drag.type === 'group'` en `pointermove` (`665`) — delta entero de D3.
17. `select`/`positionFloatbar` (`720`/`724`) — aceptar `type:'group'` y `type:'multi'` (`ids:[]`,
    acumulado con Shift+clic sobre nodos; el rectángulo de selección queda para v2).
18. `deleteSelection` (`102`) — borrar un grupo **borra solo la caja**; los hijos sobreviven y pierden
    `parent`. Borrar un nodo no toca ningún grupo (regalo de D2).
19. Barra flotante (`1001`) y `index.html:326` — dos `<input type="color">` (relleno y trazo) + campo hex,
    los 5 presets actuales, y para grupos: `Desagrupar`, `Sacar del grupo`. Botón `Agrupar` (activo con
    selección múltiple) en la barra superior. **No hay selector de color de texto en v1**: se deriva con
    `textOn(fill)` y solo se respeta el explícito que venga de un fichero.
20. `fitView` (`820`) — incluir las cajas en el bbox.
21. `highlight` (`382`) — añadir `subgraph|end|direction|classDef|class` a la regex de palabra clave
    (`editor.js:386`).
22. `server.py:174` — `'version': 2`. Nada más en el servidor.

---

## 4. Criterios de aceptación (verificables)

- **A1 (el principal — ida y vuelta idempotente).** Pegar en el panel el `.mmd` nuevo del dueño (29 nodos,
  42 aristas, 5 `subgraph`, 7 líneas `style ... fill:#c62828,color:#fff`) → arrastrar una caja → Guardar →
  F5 → Cargar. **Debe quedar: 5 `subgraph`, 7 `style` con `fill:#c62828`, 29 nodos, 42 aristas y las
  posiciones exactas de antes de guardar** (incluida la caja movida).
- **A2 (punto fijo).** `buildCode(parseCode(buildCode(parseCode(x))))` === `buildCode(parseCode(x))`,
  byte a byte, para ese mismo `.mmd`. Incluye los `classDef`/`class` de los grupos: mismos nombres,
  mismo orden alfabético, misma agrupación de ids.
- **A2b (nombre estable ante inserción).** Añadir un grupo nuevo con colores distintos **no cambia** el
  nombre de clase de ninguno de los que ya estaban.
- **A3 (retro).** Cargar `graphs/SDG.layout.json` y `graphs/OPC Office.layout.json` tal como están hoy:
  cargan sin error, sin grupos, y los nodos con color de paleta conservan su color.
- **A4 (arrastre exacto).** Tras mover una caja, la diferencia de posición de **todos** sus hijos es el
  mismo `(dx,dy)`; los offsets relativos entre hijos no cambian ni un píxel.
- **A5 (sin estado inconsistente).** Arrastrar un hijo a cualquier punto: la caja sigue conteniéndolo.
- **A6 (renderer ajeno).** El `.mmd` generado renderiza sin error en la vista previa (mermaid 11.16 de
  `vendor/`), con las 5 cajas visibles y coloreadas. **Se comprueba con `getComputedStyle()`, no a ojo**:
  sobre `fill:#c62828`, el título de la caja debe salir claro (`rgb(255,255,255)` o el `TEXT_LIGHT` que
  elija `textOn`), **nunca `rgb(0,0,0)`** — ese negro es la regresión que delata que se volvió a `style`.
- **A10 (recarga de fichero propio).** Guardar, cerrar, y **pegar el `.mmd` generado** en el panel de
  código: los colores de las 5 cajas se recuperan. Es el camino que hoy no existe (`classDef`/`class`) y
  el que convierte esta feature en algo que no se pierde a sí misma.
- **A7 (undo).** Un `Ctrl+Z` tras mover una caja devuelve **todos** los hijos de golpe.
- **A8 (grupo vacío).** Crear un grupo vacío, guardar, recargar: sigue ahí, en su sitio.
- **A9 (anidado).** Pegar `subgraph A / subgraph B / ... / end / end`: se dibuja anidado y se re-emite con
  la misma profundidad.

---

## 5. Riesgos y mitigantes

| # | Riesgo | Mitigante |
|---|---|---|
| R1 | **CERRADO [M, 2026-08-15].** `style` sí colorea el `rect` del cluster pero **ignora `color:`**: el título sale negro sobre el `#c62828` del dueño | Resuelto por diseño en §2bis: grupos por `classDef`+`class` (medido, título `rgb(255,255,255)`). Vigilado por A6, que compara el color computado y no la impresión visual |
| R1b | El nombre de `classDef` acaba dependiendo del orden de creación (un contador) y el ida y vuelta deja de ser idempotente | Nombre = función pura del contenido (§2bis), vigilado por A2 y A2b |
| R1c | El parser lee `style` pero no `classDef`/`class`, y al recargar el `.mmd` propio las cajas pierden el color | Contrato §2 (obligatorio, no opcional) + criterio A10, que recorre justo ese camino |
| R2 | Se olvida una de las **cuatro** serializaciones de `snapshot/restore/undo/redo` → los grupos desaparecen al deshacer | Paso 3 de §3: se sustituyen por `serializeState()` **antes** de tocar nada más |
| R3 | `setStateFrom` vuelve a construir un literal campo a campo y pierde la clave nueva (es el bug de hoy, repetido) | Paso 4 de §3 + criterio A1, que pasa justo por ese camino (Guardar → Cargar) |
| R4 | La caja se estira de forma absurda si un hijo se arrastra lejos | Es el feedback previsto (D2); `Sacar del grupo` está a un clic en la barra flotante |
| R5 | `layeredLayout` reparte por capas sin saber de grupos → un `.mmd` importado sale con cajas entrelazadas | Paso 13: ordenar cada capa por ruta de grupo. No se promete layout jerárquico en v1 |
| R6 | Redibujado completo en cada `pointermove` al arrastrar un grupo de 29 nodos | Ya es el comportamiento actual al arrastrar un nodo (`render()` en `editor.js:673`): no es regresión. Si se nota, se mide antes de optimizar |
| R7 | **`styleExtra` es texto pegado por el usuario que vuelve al código y al renderer** (mermaid corre con `securityLevel:'loose'`) | Saneado a pares `[A-Za-z-]+:[^;<>"']+` al parsear; los hex de la UI validados contra `^#([0-9a-fA-F]{3}\|[0-9a-fA-F]{6})$` antes de entrar al estado y antes de tocar `style.fill` del SVG |
| R8 | Un `.layout.json` a mano con `parent` cíclico o colgando cuelga el render recursivo | `normalizeState` rompe ciclos y borra padres inexistentes; es la única puerta de entrada al estado |

---

## 6. Fuera de alcance de v1 (declarado, no olvidado)

Rectángulo de selección; re-parentar arrastrando; la forma abreviada `A:::miClase`; `linkStyle`/`click`;
conservar los **nombres** de clase de un `.mmd` ajeno (se disuelven, §2); selector manual de color de
texto; layout jerárquico real por grupos; estilos de arista libres; `direction` por grupo interpretado
por el lienzo.

## 7. Qué bloquea pasar a `listo-para-construir`

1. ~~**V1** verificada en el navegador~~ — **hecha el 2026-08-15 [M]**, con render real por HTTP y
   `getComputedStyle()`. Resultado en §2bis: la suposición era falsa para los clusters y el diseño se
   corrigió **antes** de escribir una línea de producción. De haberla asumido, el título de las cajas
   habría salido en negro ilegible justo en el diagrama rojo del dueño.
2. El visto del dueño a §1: la caja **no** guarda su posición; la conserva porque la derivan sus hijos.
   **Único bloqueo vivo.**
