# Learning — `git add` con una ruta inexistente aborta TODA la orden y puede pushear un estado roto

Detectado cerrando la deduplicación de DLL de MDViewer.

[Error] Pushee a `main` un estado que no compilaba: el borrado de `apps/MDViewer/lib/` entró
en el commit, pero `build.ps1` —que todavía apuntaba a esa carpeta— se quedó fuera. Cualquiera
que clonara en ese intervalo no habría podido compilar. El commit se veía exitoso, el push se
veía exitoso, y la línea de verificación `local == remoto` daba verde.

[Causa raíz] Ejecuté:

    git add apps/MDViewer/lib apps/MDViewer/build.ps1 apps/MDViewer/README.md ...

`apps/MDViewer/lib` **ya no existía en disco** (el agente lo había borrado tras
`git rm -r --cached`). Git respondió `fatal: pathspec 'apps/MDViewer/lib' did not match any
files` y **abortó la orden entera**: ninguna de las otras rutas quedó preparada. Como el
`git rm --cached` previo ya había dejado los borrados en el índice, el `git commit` siguiente
sí tenía algo que commitear — solo que exactamente la mitad equivocada. Dos comportamientos
razonables por separado que juntos producen una regresión silenciosa:

1. `git add` es todo-o-nada con sus pathspecs.
2. `git commit` publica lo que haya en el índice, venga de donde venga.

El error de `git add` iba a stderr, en medio de una salida ruidosa de avisos `LF will be
replaced by CRLF`, y la orden estaba encadenada con `if ($?) { git push }` — pero `$?`
reflejaba el `git commit`, que fue exitoso. **Nada en la cadena delataba el fallo.**

[Solución] Tres reglas, por orden de valor:

1. **Después de `git commit`, comprueba que la lista de archivos del commit es la que
   esperabas** — no solo que el commit y el push hayan funcionado. `git show --stat HEAD` o
   un `git status --short` posterior lo delata al instante: si quedan modificaciones sin
   preparar que creías haber incluido, el commit está incompleto.
2. **Nunca metas en `git add` una ruta que acabas de borrar.** Un borrado ya rastreado por git
   viaja solo en el índice; nombrarlo otra vez no aporta nada y tumba el resto de la orden.
3. **Verifica coherencia, no solo sincronía.** `local == remoto` prueba que el push llegó, no
   que lo enviado sea consistente. Aquí bastaba con preguntarle al commit publicado si seguía
   mencionando la carpeta borrada (`git show HEAD:<archivo> | Select-String lib`).

Nota de proceso: el fallo lo cometió el coordinador al integrar, no el agente que hizo el
trabajo — su entrega estaba correcta y verificada. **El punto de integración también necesita
verificación**, no solo el trabajo que se integra.
