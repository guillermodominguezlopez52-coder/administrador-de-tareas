#!/usr/bin/env bash
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DEST="$DATA_HOME/administrador-tareas"
BIN_DIR="$HOME/.local/bin"
APPS_DIR="$DATA_HOME/applications"
ICONS_DIR="$DATA_HOME/icons/hicolor/scalable/apps"

if ! python3 -c "import gi, psutil" >/dev/null 2>&1; then
  echo "Faltan dependencias de Python. En Ubuntu/Debian ejecuta:"
  echo "  sudo apt install python3-gi python3-psutil gir1.2-gtk-4.0 gir1.2-adw-1"
  exit 1
fi

if ! python3 - <<'PY' >/dev/null 2>&1
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw
if (Gtk.get_major_version(), Gtk.get_minor_version()) < (4, 14):
    raise SystemExit(1)
if (Adw.MAJOR_VERSION, Adw.MINOR_VERSION) < (1, 5):
    raise SystemExit(1)
PY
then
  echo "Se requieren GTK 4.14 o superior y libadwaita 1.5 o superior."
  echo "En Ubuntu/Debian ejecuta:"
  echo "  sudo apt install gir1.2-gtk-4.0 gir1.2-adw-1"
  exit 1
fi

mkdir -p "$DEST" "$BIN_DIR" "$APPS_DIR" "$ICONS_DIR"
rm -rf "$DEST"
mkdir -p "$DEST"
cp -r "$SRC/administrador_tareas" "$DEST/"
cp -r "$SRC/assets" "$DEST/"
cp "$SRC/main.py" "$SRC/README.md" "$SRC/LICENSE" "$DEST/"
find "$DEST" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
cp "$SRC/assets/administrador-tareas.svg" "$ICONS_DIR/administrador-tareas.svg"
for size in 48 64 128 256 512; do
  size_dir="$DATA_HOME/icons/hicolor/${size}x${size}/apps"
  mkdir -p "$size_dir"
  cp "$SRC/assets/administrador-tareas-${size}.png" "$size_dir/administrador-tareas.png"
done

cat > "$BIN_DIR/administrador-tareas" <<EOF
#!/usr/bin/env bash
export PYTHONDONTWRITEBYTECODE=1
exec python3 "$DEST/main.py" "\$@"
EOF
chmod +x "$BIN_DIR/administrador-tareas"

DESKTOP_ID="io.github.administrador_tareas.Linux"
cat > "$APPS_DIR/$DESKTOP_ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Administrador de tareas
GenericName=Monitor del sistema
Comment=Supervisa procesos, rendimiento, inicio, usuarios y servicios
Exec=$BIN_DIR/administrador-tareas
Icon=administrador-tareas
Terminal=false
Categories=System;Monitor;
Keywords=procesos;rendimiento;monitor;tareas;system;monitor;
StartupNotify=true
StartupWMClass=$DESKTOP_ID
EOF
chmod +x "$APPS_DIR/$DESKTOP_ID.desktop"
rm -f "$APPS_DIR/administrador-tareas.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$APPS_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -f -t "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
fi

SHORTCUT_DIR=""
if [ -d "$HOME/Escritorio" ]; then
  SHORTCUT_DIR="$HOME/Escritorio"
elif [ -d "$HOME/Desktop" ]; then
  SHORTCUT_DIR="$HOME/Desktop"
fi
if [ -n "$SHORTCUT_DIR" ]; then
  SHORTCUT_FILE="$SHORTCUT_DIR/Administrador de tareas.desktop"
  cp "$APPS_DIR/$DESKTOP_ID.desktop" "$SHORTCUT_FILE"
  chmod +x "$SHORTCUT_FILE"
  if command -v gio >/dev/null 2>&1; then
    gio set "$SHORTCUT_FILE" metadata::trusted true >/dev/null 2>&1 || true
  fi
fi

echo "Instalado en: $DEST"
echo "Lanzador: $BIN_DIR/administrador-tareas"
echo "Menú de aplicaciones: Administrador de tareas"
if [ -n "$SHORTCUT_DIR" ]; then
  echo "Acceso directo: $SHORTCUT_FILE"
fi
echo
echo "Si $BIN_DIR no está en PATH, puedes ejecutar:"
echo "  $BIN_DIR/administrador-tareas"
