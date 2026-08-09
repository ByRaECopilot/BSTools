# Principles — BSTools

> Redistribuido desde `SPEC.md` §1 ("La regla de oro"), §5 ("Reglas de código") y §8 ("Antes de dar
> por terminada la herramienta"). Texto literal del dueño, sin reescribir.

## La regla de oro

Una herramienta es una **carpeta autocontenida**. Alguien tiene que poder copiar
solo esa carpeta a otro equipo, ejecutar `install.ps1` y que funcione. Si tu
herramienta necesita algo que vive fuera de su carpeta, está mal diseñada.

*(Origen: `SPEC.md` §1)*

## Reglas de código

**Idioma.** Todo lo que ve el usuario (README, mensajes de consola, interfaz) en
español.

**Acentos.** Los `.cmd`, y la salida por consola de `.ps1` y `.py`, van **sin
acentos ni caracteres no ASCII**: la codepage de la consola de Windows los
destroza. Los `.md` y el HTML sí llevan acentos normales.

**Errores.** El lanzador `.cmd` solo hace `pause` **si algo falla**. Si todo va
bien, la ventana se cierra sola.

**Dependencias.** Doble red: `install.ps1` las instala, y el script comprueba en
el arranque que están y avisa con el comando exacto si faltan. Alguien usará el
script sin pasar por el instalador.

**Legibilidad antes que magia.** El usuario tiene que poder abrir el archivo,
entenderlo y borrarlo.

*(Origen: `SPEC.md` §5)*

## Antes de dar por terminada la herramienta

- [ ] `README.md` de la herramienta, con el orden de secciones de
      [`spec/guides/guia-nueva-herramienta.md`](../guides/guia-nueva-herramienta.md) —
      incluye las decisiones de diseño, las limitaciones conocidas y qué se probó
      exactamente
- [ ] Fila nueva en la tabla de [README.md](../../README.md) raíz
- [ ] Bloque nuevo en el árbol de estructura del README raíz
- [ ] La ficha correspondiente en [`spec/backlog/backlog.md`](../backlog/backlog.md)
      pasa a `cerrada` (si la herramienta partió de una idea del backlog)
- [ ] Commit con versión y qué cambió (`NOMBRE 1.0.0: ...`) — el mensaje de commit
      **es** el changelog versionado de este repo, no hace falta un archivo aparte
- [ ] `.gitignore` si el uso genera archivos locales (`.lnk`, carpetas de salida)
- [ ] `install.ps1` ejecutado de verdad y registro verificado
- [ ] Commit y **push**. No dejes trabajo sin empujar: se desarrolla desde varias
      máquinas y la siguiente sesión empieza con `git pull`.

*(Origen: `SPEC.md` §8. Nota de reparto: este checklist referenciaba `STATUS.md` y
`CHANGELOG.md` de la raíz de este repo. Ambos se retiraron el 2026-08-04 (política de
la casa, ADR-0049: no son fuente viva) — su contenido vivo se repartió a
[`spec/backlog/backlog.md`](../backlog/backlog.md) (las ideas pendientes, como
borradores), [`spec/operations/entorno-local.md`](../operations/entorno-local.md)
(cómo se opera la máquina principal) y el `README.md` propio de cada herramienta
(decisiones de diseño y limitaciones); el histórico completo — incluidas todas las
entradas de versión — quedó archivado íntegro y fuera de git en `_Info/Tools/`. Esta
nota ya no describe una tensión pendiente: describe una migración hecha.)*
