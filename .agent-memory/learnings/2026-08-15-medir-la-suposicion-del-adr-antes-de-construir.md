# Learning — Medir la suposicion marcada [E] del ADR antes de mandar a construir

[Error] El ADR-0004 (grupos + estilos libres del editor Mermaid) llego con el diseno cerrado y **una
suposicion marcada [E], sin verificar**: que un `style <idSubgraph> fill:#...,color:#fff` colorearia la
caja del subgraph igual que colorea un nodo. Todo el contrato de emision colgaba de eso. Si se hubiera
mandado a construir tal cual, Atlas habria escrito un emisor uniforme (todo con `style`), y el fallo no
habria aparecido como error: habria aparecido como **titulos negros ilegibles sobre fondo rojo**, es
decir, como "un detalle cosmetico" descubierto al final, cuando el emisor, el parser y los tests ya
estaban escritos alrededor de la premisa equivocada.

[Causa raiz] Un ADR puede estar impecable en su razonamiento y aun asi apoyarse en un hecho del entorno
que nadie midio. El arquitecto no tiene por que tener herramientas para medirlo; el director si. Marcar
la suposicion con [E] es la mitad buena del trabajo — la otra mitad es que **alguien la cobre antes de
que se convierta en codigo**.

[Solucion] Regla: **ninguna suposicion marcada como no verificada pasa al constructor**. Antes de
despachar a ATLAS, el director la mide con el mismo motor real que usara el producto (aqui: el
`vendor/mermaid.min.js` v11.16.0 de la propia herramienta, servido por HTTP, leyendo `getComputedStyle()`
del SVG). Coste: ~10 minutos. Resultado en este caso: la suposicion era **falsa a medias**, que es el
peor caso posible porque el fallo parcial no salta a la vista —

- en un **nodo**, `style` aplica `fill` y `color` de texto: correcto;
- en un **subgraph**, `style` aplica `fill`/`stroke` pero **ignora `color:`**;
- `classDef` + `class` si aplica las tres, tambien en subgraph.

El contrato de emision paso a ser asimetrico (nodos con `style`, grupos con `classDef`), y de ahi
salieron dos requisitos que nadie habia visto: los nombres de `classDef` tienen que ser **funcion pura
del color** (un contador rompe el punto fijo del ida y vuelta en la primera reordenacion) y el **parser
tiene que aprender a leer `classDef`/`class`**, porque si no, recargar el `.mmd` que genera la propia
herramienta pierde el color de las cajas — el mismo bug que la feature venia a matar, reencarnado.

Medir movio el emisor y el parser; **no movio ni una de las seis decisiones del modelo de datos**. Esa
es la senal de un buen ADR: la medicion corrige la implementacion, no la arquitectura.
