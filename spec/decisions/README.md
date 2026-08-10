# Decisiones (ADR) — BSTools

Un archivo por decisión, `ADR-NNNN-<slug>.md`, *append-only*: **un ADR no se edita para cambiar la
decisión** — se escribe uno nuevo que lo supersede y el viejo pasa a `derogado` con su `superseded_by`.

Aquí solo entra lo **caro de revertir**: stack, dependencias, topología, desviaciones de una regla de la
casa. Lo barato de deshacer no merece un ADR, merece un commit con buen mensaje.

## Aviso de numeración (importante)

La numeración local **empieza en 0001**. Los números altos que se citan en la constitución de este
repositorio — ADR-0042, ADR-0045, ADR-0047, ADR-0049 — son **ADRs del canon de la casa**, viven en el
repositorio padre y **no están en esta carpeta**. No los busques aquí y no reserves su hueco.

## Índice

| ADR | Decisión | Estado |
|---|---|---|
| [ADR-0001-voice2text-stack.md](ADR-0001-voice2text-stack.md) | Voice2Text: transcripción local con faster-whisper, PyAV sin ffmpeg del sistema, modelos fuera del repo, ventana propia y modo servidor manual | parcialmente-derogado |
| [ADR-0002-voice2text-modelo-y-gpu.md](ADR-0002-voice2text-modelo-y-gpu.md) | Voice2Text: catálogo de modelos por perfil de hardware y GPU como complemento opcional — supersede D5, D20 y la regla de peso de ADR-0001 §7 | listo-para-construir |
| [ADR-0003-voice2text-cookies-del-navegador.md](ADR-0003-voice2text-cookies-del-navegador.md) | Voice2Text: cookies del navegador del usuario, desactivadas por defecto — matizaría D6 y sustituiría §11 de ADR-0001. **Condicionado a un diagnóstico en curso** | propuesto |
