# CLAUDE.md

Instrucciones para Claude Code al trabajar en este repositorio.

- **Para crear o modificar una herramienta: [SPEC.md](SPEC.md).** Lleva la
  especificación completa y las plantillas copiables de `install.ps1`,
  `uninstall.ps1` y el lanzador. **No hace falta abrir otra herramienta para
  copiar su estructura**; si SPEC.md se queda corto en algo, arréglalo ahí.
- **Para saber en qué punto está el trabajo: [STATUS.md](STATUS.md).**

## El proyecto

**BSTools**: herramientas pequeñas para Windows que se integran en el menú
contextual del Explorador. Autor: [www.byraesoftware.com](https://www.byraesoftware.com).
Licencia CC0 1.0 (dominio público) — todo lo que se añada va bajo CC0.

- Repositorio: https://github.com/ByRaECopilot/BSTools.git (público, rama `main`)
- Se desarrolla desde **varias máquinas distintas**. Antes de empezar: `git pull`.
  Al terminar una tarea: commit y push. No dejes trabajo sin empujar.

## Lo imprescindible

Cada herramienta es una carpeta **autocontenida**: alguien debe poder copiar solo
esa carpeta y que funcione. La estructura, los tres patrones de arranque, el
contrato con el registro de Windows y las plantillas están en [SPEC.md](SPEC.md).

Cuatro reglas que no se negocian:

- **Registro** siempre en `HKCU:\Software\Classes` (nunca `HKLM` ni `HKCR`), con
  el verbo `BSTools.<HERRAMIENTA>`.
- **Rutas absolutas deducidas en tiempo de instalación**, nunca escritas a mano.
- **Sin acentos** en `.cmd` ni en la salida por consola de `.ps1`/`.py`. Los
  `.md` sí.
- **Prueba en tres niveles**: script suelto, lanzador desde ruta con espacios y
  registro verificado. La entrada de prueba se genera sintéticamente.

Al terminar una herramienta, la lista de documentos que hay que actualizar está
al final de [SPEC.md](SPEC.md).

## Trampas del entorno

- **PowerShell 5.1**: no existen `&&`, `||`, ni el operador ternario. Encadena
  con `;` o `if ($?) { ... }`.
- **`git push` desde PowerShell** escupe su salida por stderr y PowerShell la
  presenta como `NativeCommandError` aunque haya funcionado. No es un fallo:
  verifica de verdad con `git ls-remote origin` o `git status -sb`.
- **Windows 11**: las entradas clásicas del menú contextual viven dentro de
  *Mostrar más opciones* (`Shift+F10`). Menciónalo siempre en los README.
- **Identidad de git**: puede no estar configurada en una máquina nueva. Se
  configura **local al repositorio** (`git config user.name` sin `--global`).
- **`gh` (GitHub CLI) no está instalado** en la máquina principal; usa `git`.

## Filosofía

Scripts legibles antes que magia. El usuario tiene que poder abrir el archivo,
entenderlo y borrarlo. Nada de instaladores binarios, servicios en segundo plano
ni dependencias de gigabytes salvo que aporten algo que no se pueda conseguir de
otra forma.
