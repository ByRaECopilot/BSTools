# CLAUDE.md

Instrucciones para Claude Code al trabajar en este repositorio.

- **Para crear o modificar una herramienta: [spec/guides/guia-nueva-herramienta.md](spec/guides/guia-nueva-herramienta.md).**
  Lleva la estructura de carpeta y las plantillas copiables de `install.ps1`,
  `uninstall.ps1` y el lanzador. **No hace falta abrir otra herramienta para
  copiar su estructura**; si la guía se queda corta en algo, arréglala ahí.
- **Para saber en qué punto está el trabajo:** qué falta en
  [spec/backlog/backlog.md](spec/backlog/backlog.md); dónde se cortó la última sesión, en
  `spec/sessions/` (si existe un handoff).
- **Para registrar cambios: el propio mensaje del commit** (versión + qué cambió, p.ej.
  `Mermaid 1.3.0: guardar/cargar en graphs/`) — no hay un archivo de changelog aparte.

## El proyecto

**BSTools**: herramientas pequeñas para Windows que se integran en el menú
contextual del Explorador. Autor: [www.byraesoftware.com](https://www.byraesoftware.com).
Licencia CC0 1.0 (dominio público) — todo lo que se añada va bajo CC0.

- Repositorio: https://github.com/ByRaECopilot/BSTools.git (público, rama `main`)
- Se desarrolla desde **varias máquinas distintas**. Antes de empezar: `git pull`.
  Al terminar una tarea: commit y push. No dejes trabajo sin empujar.

## Lo imprescindible

Cada herramienta es una carpeta **autocontenida**: alguien debe poder copiar solo
esa carpeta y que funcione. La estructura y los cuatro patrones de arranque están en
[spec/constitution/tech-stack.md](spec/constitution/tech-stack.md), junto con el
contrato con el registro de Windows; las plantillas de `install.ps1`, `uninstall.ps1`
y el lanzador están en [spec/guides/guia-nueva-herramienta.md](spec/guides/guia-nueva-herramienta.md).

Cuatro reglas que no se negocian:

- **Registro** siempre en `HKCU:\Software\Classes` (nunca `HKLM` ni `HKCR`), con
  el verbo `BSTools.<HERRAMIENTA>`.
- **Rutas absolutas deducidas en tiempo de instalación**, nunca escritas a mano.
- **Sin acentos** en `.cmd` ni en la salida por consola de `.ps1`/`.py`. Los
  `.md` sí.
- **Prueba en tres niveles**: script suelto, lanzador desde ruta con espacios y
  registro verificado. La entrada de prueba se genera sintéticamente.

Al terminar una herramienta, la lista de documentos que hay que actualizar está
en el checklist de cierre de
[spec/constitution/principles.md](spec/constitution/principles.md).

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
