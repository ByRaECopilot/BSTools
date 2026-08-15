# Backlog — BSTools

> Rescatado de `STATUS.md` § "Pendiente / ideas" (existía hasta 2026-08-04; archivado íntegro y
> fuera de git en `_Info/Tools/STATUS.md`, retiro justificado por la política de la casa —
> ADR-0049: `STATUS.md`/`CHANGELOG.md` no son fuente viva). Texto literal del dueño; el bullet
> original que mezclaba varias ideas en una línea se separó en un borrador por idea, sin
> reescribir el texto.
>
> Estado `borrador`: nadie más que el dueño decide qué de esto se construye, y solo cuando él lo
> mueva a un estado siguiente. No se ha inventado ningún campo adicional (alcance, tipo, criterio
> de aceptación...) que el dueño no haya declarado.

## Borradores

- OCR en PDF2MD para escaneados (solo si surge la necesidad).
- Descripción y *topics* del repositorio en GitHub, para que se encuentre.
- Herramientas nuevas: aún sin decidir.
- BrandAssets: generar `favicon.svg` cuando la entrada ya sea un SVG.
- BrandAssets: plantillas de captura para el `screenshots` del manifest.
- Mermaid: más tipos de diagrama (secuencia, clases).
- Mermaid: cargar el `.mmd` del menú contextual directamente en el editor (hoy hay que pegar el
  contenido).
- Mermaid: autoruteo ortogonal de las flechas.
- Mermaid: grupos (`subgraph`) de primera clase en el lienzo y colores libres en hex — diseño cerrado en
  `spec/decisions/ADR-0004-mermaid-grupos-y-estilos-libres.md` (`propuesto`: la verificación en navegador
  ya está hecha —§2bis, medida el 2026-08-15—; solo falta el visto del dueño a §1). Hoy el editor aplana
  los `subgraph` y pierde los `fill:` al pegar código.
- Voice2Text: transcribe un audio/vídeo local o un enlace público a `.txt` y `.md`, en la propia máquina
  (diseño en `spec/decisions/ADR-0001-voice2text-stack.md` y `spec/decisions/ADR-0002-voice2text-modelo-y-gpu.md`).
  **v1.0 construida y verificada** (`apps/Voice2Text/VERIF-FINAL.md`): los seis recorridos de uso funcionan
  de punta a punta. Queda abierto el lote 10 (`ARCHITECTURE.md` §13): `cuda_required` y el bloque de
  dispositivo de `GET /health` (distinguir "sin GPU" de "GPU rota"). El perfil de producción (RTX 3080)
  sigue condicionado a medir en esa tarjeta (ADR-0002 §4, V7).
