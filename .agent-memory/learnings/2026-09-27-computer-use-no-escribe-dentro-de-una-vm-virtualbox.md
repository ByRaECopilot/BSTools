# Learning — computer-use no puede teclear dentro de una VM de VirtualBox

[Error] Intenté automatizar con computer-use el rescate de una VM Ubuntu (editar la línea de GRUB para añadir `init=/bin/bash`). Las teclas de navegación parecieron funcionar, pero el texto escrito con la acción `type` nunca llegó al invitado: la máquina arrancó normal, a la pantalla de login. La verificación fue teclear una cadena inocua en el prompt de login y comprobar que no aparecía ni un carácter.

[Causa raíz] VirtualBox captura el teclado a bajo nivel; las pulsaciones sintéticas que inyecta computer-use (SendInput) no llegan a la ventana del invitado, aunque sí funcionen sobre las ventanas normales de Windows (menús, diálogos de VirtualBox). No es un problema de foco ni de captura del ratón.

[Solución] Todo lo que se pueda hacer desde el anfitrión se hace con `VBoxManage` (estado, arranque, storageattach, modifyvm, natpf, guestproperty) — ahí sí hay control total. Lo que exige teclear DENTRO del invitado (GRUB, consola, instalador) se le entrega al dueño con pasos exactos, o se hace por SSH una vez haya credenciales. Antes de dar por buena una automatización de teclado sobre una VM, verificarla con una cadena visible y desechable, no asumir que funcionó.
