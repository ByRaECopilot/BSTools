# Learning — En PowerShell, `return $LASTEXITCODE` desde una funcion se mezcla con la salida del proceso hijo

**[Error]** Construyendo `install-gpu.ps1` (Voice2Text, lote 7), se escribio una funcion
ayudante para no repetir la logica de "usar `py -3` o `python` segun cual exista":

```powershell
function Invoke-Py {
    param([string[]]$PyArgs)
    $fullArgs = $PyArgs
    if ($python -eq 'py') { $fullArgs = @('-3') + $PyArgs }
    & $python @fullArgs
    return $LASTEXITCODE
}

$exitCode = Invoke-Py @('-m', 'pip', 'install', '-r', $reqFile)
if ($exitCode -ne 0) { ... }
```

Al ejecutarlo de verdad (no en un dry-run: instalando ~2 GB de librerias CUDA reales), `pip`
termino con exito (`Successfully installed ...`), pero `$exitCode` NO fue `0`: contenia
**toda la salida de consola de `pip` pegada al numero**, y el `if` de arriba disparo la rama
de error con un mensaje sin sentido (`"pip devolvio el codigo Requirement already satisfied:
... Successfully installed ... 0. Revisa el mensaje de arriba."`).

**[Causa raíz]** En PowerShell, el valor de retorno de una funcion **es la agregacion de
TODO lo que la funcion emite al pipeline de salida sin suprimir**, no solo lo que sigue a
`return`. `& $python @fullArgs` no esta redirigido ni capturado dentro de la funcion, asi
que cada linea que `pip` imprime a stdout se convierte en un elemento mas de la salida de
la funcion. Cuando quien llama hace `$exitCode = Invoke-Py ...`, PowerShell asigna **el
array completo** (salida de pip + el entero de `$LASTEXITCODE`) a esa variable. Si luego se
interpola esa variable en una cadena (`"$exitCode"` o dentro de un `Write-Warning "...:
$exitCode"`), PowerShell la convierte a texto uniendo todos los elementos — de ahi el
mensaje mezclado. El bug **no aparece en pruebas rapidas con comandos silenciosos**
(`--version`, algo con salida minima): solo se manifiesta con un proceso que imprime mucho
por consola, como `pip install` de verdad. Una prueba de humo con `py -3 --version` no lo
habria detectado.

**[Solución]** No envolver `& $comando ...; return $LASTEXITCODE` en una funcion que se
asigna a una variable con `$x = Mi-Funcion`. Alternativas que si funcionan:

1. **Llamar al proceso directo, sin funcion intermedia**, y leer `$LASTEXITCODE`
   inmediatamente despues, en el mismo scope:
   ```powershell
   & py -3 -m pip install -r $reqFile
   $exitCode = $LASTEXITCODE
   ```
2. Si hace falta encapsular, **suprimir explicitamente la salida del proceso hijo** dentro
   de la funcion (`| Out-Null` o redirigir a un archivo) y devolver solo el codigo.
3. Nunca asumir que "la funcion solo tiene un `return`" implica "la funcion solo devuelve
   eso": en PowerShell hay que auditar TODO lo que la funcion ejecuta sin capturar.

Esto es generalizable a **cualquier `.ps1` de la casa que envuelva una llamada a un proceso
externo verboso** (pip, git, cualquier CLI) dentro de una funcion pensada solo para
devolver un codigo de salida. La correccion real llego al ejecutar el instalador CONTRA
UNA INSTALACION REAL (2 GB, salida larga de pip) en vez de contra un smoke test barato:
**un ensayo con poca salida por consola no habria revelado el bug.**
