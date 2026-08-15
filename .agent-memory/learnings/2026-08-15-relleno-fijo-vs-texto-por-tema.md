# Learning — Relleno fijo + texto por variable de tema = bug garantizado

**[Error]** En el editor Mermaid (`apps/Mermaid`), al aplicar color a un nodo el texto de la
etiqueta quedaba ilegible. Ratio de contraste medido: **1.01:1** — texto prácticamente invisible.
El fallo solo se veía en tema oscuro, así que sobrevivió a las pruebas hechas en tema claro.

**[Causa raíz]** Dos decisiones de color tomadas en sitios distintos y nunca reconciliadas:
el *relleno* del nodo era un pastel **fijo y hardcodeado** en JS (`NODE_COLORS`, p.ej. `#dbeafe`),
mientras que el *texto* se pintaba con una **variable de tema** en CSS (`fill: var(--node-text)`,
que vale `#e8eaf0` en oscuro). Cuando el fondo deja de seguir el tema y el texto sí lo sigue, uno
de los dos temas queda roto por construcción. Nadie lo vio porque el export a Mermaid sí forzaba
`color:#111`, así que la **vista previa se leía bien y el lienzo no** — la discrepancia entre dos
superficies de render enmascaró el bug.

**[Solución]** El color del texto se **calcula**, no se hereda ni se hardcodea: función pura
`textOn(hexFill)` con luminancia relativa WCAG, que elige entre un candidato oscuro y uno claro
comparando el **ratio de contraste real** contra ambos (no un umbral `> 0.5` a ojo). Se aplica en
el mismo sitio donde se decide el relleno, y la misma función alimenta el export a Mermaid — así
lienzo y export no pueden volver a divergir. Cuando el nodo no tiene color propio no se toca el
fill, para que siga heredando el tema.

**Regla generalizable (candidata a canon):** en cuanto un color de fondo deje de venir del sistema
de temas, el color del texto que va encima **deja de poder venir del sistema de temas**. Se calcula
por contraste, o se elige explícitamente junto al fondo. Nunca uno fijo y el otro por variable.

**Regla de proceso:** un bug de color hay que verificarlo en **los dos temas** — y la evidencia
válida es el ratio de contraste numérico, no "se ve bien". Cuando hay más de una superficie de
render (lienzo, vista previa, export), la decisión de color debe salir de **una sola función**;
dos caminos que deciden lo mismo por separado esconden el fallo en el camino menos mirado.
