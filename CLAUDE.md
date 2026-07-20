# CLAUDE.md

Instrucciones para Claude Code al trabajar en este repositorio.
Lee también [STATUS.md](STATUS.md) para saber en qué punto está el trabajo.

## El proyecto

**BSTools**: herramientas pequeñas para Windows que se integran en el menú
contextual del Explorador. Autor: [www.byraesoftware.com](https://www.byraesoftware.com).
Licencia CC0 1.0 (dominio público) — todo lo que se añada va bajo CC0.

- Repositorio: https://github.com/ByRaECopilot/BSTools.git (público, rama `main`)
- Se desarrolla desde **varias máquinas distintas**. Antes de empezar: `git pull`.
  Al terminar una tarea: commit y push. No dejes trabajo sin empujar.

## Anatomía de una herramienta

Cada herramienta es una carpeta **autocontenida**: alguien debe poder copiar solo
esa carpeta y que funcione. `PDF2MD/` es la plantilla de referencia.

```
NOMBRE/
├── install.ps1        instala dependencias + registra el menú contextual
├── uninstall.ps1      revierte el registro por completo
├── lanzador.cmd       puente entre el Explorador y el script
├── script.py          la lógica
├── requirements.txt   dependencias de Python (si las hay)
└── README.md          qué hace, cómo se instala, cómo se usa, problemas comunes
```

Al añadir una herramienta nueva, actualiza también:
la tabla de herramientas del [README.md](README.md) raíz, [STATUS.md](STATUS.md)
y [CHANGELOG.md](CHANGELOG.md).

## Convenciones

**Registro de Windows.** Escribe siempre en `HKCU:\Software\Classes`, nunca en
`HKLM` ni `HKCR`. Así no hace falta ser administrador y el usuario puede
desinstalar sin fricción. Nombra el verbo `BSTools.<HERRAMIENTA>` para que las
entradas sean identificables y borrables.

**Rutas.** `install.ps1` deduce su propia ubicación con
`Split-Path -Parent $MyInvocation.MyCommand.Path` y escribe rutas absolutas en el
registro. Nunca escribas una ruta a mano: rompe el repo para quien se lo baje.
Consecuencia: si el usuario mueve la carpeta, debe reejecutar `install.ps1`.

**Idioma.** Texto de cara al usuario (README, mensajes de consola) en español.

**Acentos.** Los `.cmd` y la salida por consola de `.ps1`/`.py` van **sin
acentos ni caracteres no ASCII**: la consola de Windows usa una codepage que los
destroza. Los `.md` sí llevan acentos normales.

**Errores.** El lanzador `.cmd` solo hace `pause` si algo falla. Si todo va bien,
la ventana se cierra sola.

**Dependencias.** `install.ps1` las instala. Además, el script de Python
comprueba e intenta instalar lo que falte en la primera ejecución, por si alguien
lo usa sin pasar por el instalador.

## Cómo probar

No hace falta tener archivos reales a mano: genera la entrada sintéticamente.
Para PDF2MD, se creó un PDF de prueba con PyMuPDF que incluía encabezados,
pies con número de página, palabras partidas con guion, listas y una tabla —
justamente los casos que la limpieza tiene que resolver.

Comprueba siempre estos tres niveles:

1. El script directamente: `python script.py entrada`
2. El lanzador: `cmd /c "ruta\lanzador.cmd" "entrada"` (usa una ruta **con
   espacios**, es el fallo clásico)
3. El registro quedó bien escrito:
   `(Get-ItemProperty 'HKCU:\Software\Classes\...\command').'(default)'`

## Trampas del entorno

- **PowerShell 5.1**: no existen `&&`, `||`, ni el operador ternario. Encadena
  con `;` o `if ($?) { ... }`.
- **`git push` desde PowerShell** escupe su salida por stderr y PowerShell la
  presenta como `NativeCommandError` aunque haya funcionado. No es un fallo:
  verifica de verdad con `git ls-remote origin` o `git status -sb`.
- **Windows 11**: las entradas clásicas del menú contextual viven dentro de
  *Mostrar más opciones* (`Shift+F10`). Menciónalo siempre en los README.
- **`gh` (GitHub CLI) no está instalado** en la máquina principal; usa `git`.

## Filosofía

Scripts legibles antes que magia. El usuario tiene que poder abrir el archivo,
entenderlo y borrarlo. Nada de instaladores binarios, servicios en segundo plano
ni dependencias de gigabytes salvo que aporten algo que no se pueda conseguir de
otra forma.
