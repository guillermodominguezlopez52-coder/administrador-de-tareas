# Administrador de tareas para Linux

Una alternativa gráfica y sencilla al Administrador de tareas de Windows, pensada
para escritorios Linux. Usa **GTK 4 + libadwaita** para la interfaz y **psutil**,
`/proc` y **systemd** para leer y controlar el sistema.

![Icono](assets/administrador-tareas.svg)

## Características

### Procesos
- Lista de procesos con nombre, estado, uso de CPU, memoria, disco, usuario y PID.
- Búsqueda instantánea por nombre, PID, usuario o línea de comandos.
- Filtro por tipo: aplicaciones, procesos en segundo plano y procesos del sistema.
- Ordenación por cualquier columna (por ejemplo, CPU o memoria).
- Panel lateral con detalles del proceso seleccionado.
- Finalizar tarea, forzar finalización y finalizar el árbol de procesos.
- Suspender y reanudar procesos.
- Cambiar la prioridad (normal, baja, alta, etc.).
- Abrir la carpeta del ejecutable, copiar detalles y ver propiedades completas.
- Si un proceso necesita permisos, se ofrece reintentar con `pkexec`.

### Rendimiento
- Tarjetas resumen de CPU, memoria, disco y red.
- Gráficos en tiempo real de CPU, memoria, lectura/escritura de disco y red.
- Uso por núcleo lógico.
- Temperatura, velocidad de CPU, carga media y tiempo de actividad.
- Uso de memoria física, caché y swap.
- Uso del disco del sistema.
- Información de la interfaz de red (IP, MAC, velocidad).

### Inicio
- Lista de aplicaciones que se abren al iniciar sesión (`XDG autostart`).
- Interruptor para activarlas o desactivarlas.
- Distingue entradas personales y del sistema.
- Los cambios se aplican en el próximo inicio de sesión.

### Usuarios
- Sesiones abiertas en el equipo.
- Tipo de sesión (Wayland, X11, terminal), terminal, equipo e inicio.
- Consumo de CPU, memoria y número de procesos por usuario.
- Cierre de sesiones que no sean la actual (puede requerir permisos).

### Detalles
- Vista avanzada con PID, PPID, usuario, estado, CPU, memoria, subprocesos,
  prioridad, tipo, hora de inicio y línea de comandos.

### Servicios
- Servicios de systemd del sistema y de la sesión del usuario.
- Estado actual e inicio automático.
- Iniciar, detener, reiniciar, habilitar y deshabilitar.
- Registro reciente con `journalctl`.
- Las operaciones del sistema piden autorización con `pkexec`.

### Ajustes
- Frecuencia de actualización: 1, 2, 3, 5 o 10 segundos.
- Confirmación antes de finalizar procesos.
- Tema del sistema, claro u oscuro.
- Restaurar valores predeterminados.

## Atajos de teclado

| Atajo | Acción |
| --- | --- |
| `F5` | Actualizar ahora |
| `Ctrl+F` | Buscar proceso |
| `Ctrl+,` | Abrir ajustes |
| `Ctrl+Q` | Salir |

## Requisitos

- Linux con una sesión gráfica (X11 o Wayland).
- Python 3.10 o superior.
- GTK 4.14 o superior y libadwaita 1.5 o superior.
- `psutil` 5.9 o superior.
- `systemd` y `loginctl` para las pestañas de servicios y usuarios.
- `pkexec` (polkit) para acciones administrativas.

En Ubuntu / Debian:

```bash
sudo apt install python3 python3-gi python3-psutil gir1.2-gtk-4.0 gir1.2-adw-1
```

En Fedora:

```bash
sudo dnf install python3 python3-gobject python3-psutil gtk4 libadwaita
```

En Arch Linux:

```bash
sudo pacman -S python python-gobject python-psutil gtk4 libadwaita polkit
```

## Ejecutar sin instalar

```bash
cd "Administrador de Tareas"
python3 main.py
```

o:

```bash
./run.sh
```

## Instalar en el menú de aplicaciones

```bash
./install.sh
```

El instalador copia la aplicación a `~/.local/share/administrador-tareas`,
crea el lanzador `~/.local/bin/administrador-tareas` y añade la entrada al menú.
Después puedes abrirla desde el menú como **Administrador de tareas**.

El instalador registra el icono del programa en varios tamaños (`48`, `64`,
`128`, `256` y `512` píxeles) para el menú, el dock, la ventana y el diálogo
**Acerca de**. También se crea un acceso directo en el escritorio cuando existe
la carpeta `~/Escritorio` o `~/Desktop`.

Si `~/.local/bin` no está en tu `PATH`, ejecuta la ruta completa.

## Pasar la aplicación a otro equipo Linux

Copia el archivo `Administrador-de-tareas-1.0.0.tar.gz` al otro equipo (USB,
red, etc.) y ejecuta:

```bash
tar -xzf Administrador-de-tareas-1.0.0.tar.gz
cd Administrador-de-tareas-1.0.0
./install.sh
```

Antes debes instalar las dependencias indicadas en **Requisitos**. El
instalador crea el lanzador, el icono y el acceso directo del escritorio para
el usuario actual, sin necesidad de permisos de administrador.

## Permisos

- La mayoría de procesos del usuario se pueden finalizar sin contraseña.
- Finalizar procesos de otros usuarios, cambiar prioridades altas o controlar
  servicios del sistema requiere autorización. La aplicación usa `pkexec`, por
  lo que aparecerá el diálogo de autenticación de tu escritorio.
- Cerrar la sesión actual está desactivado para evitar cerrar la aplicación y
  perder el trabajo de la sesión.
- Detener servicios esenciales muestra una advertencia adicional.

## Privacidad

Todo se ejecuta localmente. La aplicación no envía datos a Internet.

## Estructura del proyecto

```
Administrador de Tareas/
├── main.py                     # Punto de entrada
├── administrador_tareas/
│   ├── application.py          # Aplicación Adw.Application
│   ├── window.py               # Ventana principal y actualización
│   ├── style.css               # Estilos de la interfaz
│   ├── core/                   # Lógica del sistema (sin interfaz)
│   │   ├── actions.py          # Acciones sobre procesos
│   │   ├── processes.py        # Recolector de procesos
│   │   ├── services.py         # Servicios de systemd
│   │   ├── settings.py         # Preferencias
│   │   ├── startup.py          # Aplicaciones de inicio
│   │   ├── system.py           # Métricas globales
│   │   └── users.py            # Sesiones de usuario
│   └── ui/
│       ├── common.py           # Formatos y diálogos
│       ├── graph.py            # Gráficos con Gsk
│       ├── process_table.py    # Tabla de procesos y detalles
│       └── pages/              # Rendimiento, inicio, usuarios, servicios, ajustes
├── assets/administrador-tareas.svg
├── assets/administrador-tareas-*.png
├── assets/memory-symbolic.svg
├── tests/test_core.py
├── INSTALAR.txt
├── install.sh
├── run.sh
├── requirements.txt
└── LICENSE
```

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

También hay una prueba de humo de la interfaz que crea la ventana, recolecta
datos y sale sin mostrar la ventana:

```bash
python3 main.py --smoke-test
```

## Solución de problemas

- **No abre / error de GTK**: comprueba que GTK 4 y libadwaita están instalados
  y que ejecutas la aplicación desde una sesión gráfica.
- **No aparecen servicios del usuario**: comprueba que `systemctl --user` funciona
  en tu sesión.
- **No se puede leer la temperatura**: algunos equipos o máquinas virtuales no
  exponen sensores. Se muestra «No disponible».
- **Las acciones administrativas no abren el diálogo**: instala un agente polkit
  (`polkit-gnome`, `lxpolkit` o el que use tu escritorio).

## Licencia

Distribuido bajo la licencia MIT. Consulta el archivo `LICENSE`.
