# Mermaid

Editor gráfico de diagramas de flujo. Arrastras formas, las unes con flechas y
el **código Mermaid se genera en tiempo real**. Con vista previa del diagrama
renderizado y exportación a `.mmd`, `.svg` y `.png`.

Doble clic en el icono **Mermaid** de esta carpeta → se abre en tu navegador. Es
una aplicación de una sola página: **no necesita Python, ni servidor, ni
conexión a internet**. Todo (incluida la librería Mermaid) va dentro de la
carpeta.

---

## Instalación

```powershell
cd Mermaid
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

El instalador:

1. Crea el acceso directo **Mermaid** dentro de esta carpeta, con icono propio.
   Apunta directamente al `index.html`, así que al abrirlo no aparece ninguna
   ventana de consola, solo el navegador.
2. Añade al menú contextual de los archivos `.mmd` la opción *Abrir con el
   editor Mermaid*.

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
   cambio. La pestaña *Vista previa* muestra el diagrama renderizado por Mermaid.
5. **Exporta:** botón *Copiar* (al portapapeles), o descarga `.mmd`, `.svg` o
   `.png`.

El diagrama se guarda solo en el navegador (`localStorage`): al reabrir el
editor sigue donde lo dejaste.

### Controles

| Acción | Cómo |
|---|---|
| Mover un nodo | Arrastrarlo |
| Conectar | Arrastrar desde un punto azul del nodo a otro nodo |
| Editar texto | Doble clic en nodo o flecha |
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

## Lo que no hace (y por qué)

- **No importa un `.mmd` existente** para editarlo gráficamente. Convertir texto
  Mermaid arbitrario de vuelta a nodos posicionados es un analizador completo, y
  el objetivo aquí es el camino contrario: del dibujo al código.
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

**No aparece la vista previa.** Cambia a la pestaña *Vista previa*; si el código
tiene algún carácter que Mermaid rechaza, se muestra el error en rojo en vez de
romperse.

**Copiar al portapapeles no funciona.** Algunos navegadores lo bloquean al abrir
por `file://` muy antiguos; usa el botón `.mmd` para descargar, o actualiza el
navegador.

**Moviste la carpeta.** Vuelve a ejecutar `install.ps1`.

---

Parte de [BSTools](../README.md) · [www.byraesoftware.com](https://www.byraesoftware.com) · CC0 1.0
