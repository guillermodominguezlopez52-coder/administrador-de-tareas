"""Aplicaciones que se inician automáticamente al iniciar sesión."""

from __future__ import annotations

import configparser
import os
from dataclasses import dataclass
from pathlib import Path


SYSTEM_AUTOSTART = Path("/etc/xdg/autostart")


def autostart_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "autostart"
    return Path.home() / ".config" / "autostart"


def _parse_desktop(path: Path) -> dict[str, str]:
    parser = configparser.ConfigParser(
        interpolation=None, strict=False, delimiters=("=",)
    )
    parser.optionxform = str
    try:
        parser.read(path, encoding="utf-8")
        if not parser.has_section("Desktop Entry"):
            return {}
        return {key: value for key, value in parser.items("Desktop Entry")}
    except (OSError, configparser.Error, UnicodeError):
        return {}


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in ("1", "true", "yes", "on")


def _is_disabled(data: dict[str, str]) -> bool:
    if _truthy(data.get("Hidden")):
        return True
    if data.get("X-GNOME-Autostart-enabled") is not None:
        return not _truthy(data.get("X-GNOME-Autostart-enabled"))
    return False


@dataclass(slots=True)
class StartupEntry:
    key: str
    name: str
    comment: str
    exec_line: str
    icon: str
    source: str
    enabled: bool
    user_path: Path | None
    system_path: Path | None
    user_has_exec: bool


def _entry_from_paths(key: str, user_path: Path | None, system_path: Path | None) -> StartupEntry | None:
    user_data = _parse_desktop(user_path) if user_path else {}
    system_data = _parse_desktop(system_path) if system_path else {}
    data = user_data or system_data
    if not data:
        return None
    name = data.get("Name") or system_data.get("Name") or key
    comment = data.get("Comment") or system_data.get("Comment") or ""
    exec_line = data.get("Exec") or system_data.get("Exec") or ""
    icon = data.get("Icon") or system_data.get("Icon") or "application-x-executable"
    if not exec_line and not _is_disabled(data):
        return None
    return StartupEntry(
        key=key,
        name=name,
        comment=comment,
        exec_line=exec_line,
        icon=icon,
        source="Personal" if user_path else "Sistema",
        enabled=not _is_disabled(data),
        user_path=user_path,
        system_path=system_path,
        user_has_exec=bool(user_data.get("Exec")),
    )


def list_startup_entries() -> list[StartupEntry]:
    user_dir = autostart_dir()
    system_files: dict[str, Path] = {}
    user_files: dict[str, Path] = {}
    try:
        for path in SYSTEM_AUTOSTART.glob("*.desktop"):
            system_files[path.name] = path
    except OSError:
        pass
    try:
        for path in user_dir.glob("*.desktop"):
            user_files[path.name] = path
    except OSError:
        pass

    entries: list[StartupEntry] = []
    for key in sorted(set(system_files) | set(user_files), key=str.lower):
        entry = _entry_from_paths(key, user_files.get(key), system_files.get(key))
        if entry:
            entries.append(entry)
    entries.sort(key=lambda item: item.name.casefold())
    return entries


def _set_hidden(path: Path, hidden: bool) -> None:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    section = "[Desktop Entry]"
    start = None
    end = len(lines)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == section:
            start = index
        elif start is not None and stripped.startswith("[") and stripped.endswith("]"):
            end = index
            break
    if start is None:
        lines = [section] + lines
        start = 0
        end = len(lines)
    filtered = [
        line
        for line in lines[start + 1 : end]
        if not line.strip().startswith(("Hidden=", "X-GNOME-Autostart-enabled="))
    ]
    if hidden:
        inserted = ["Hidden=true", "X-GNOME-Autostart-enabled=false"]
    else:
        inserted = ["Hidden=false", "X-GNOME-Autostart-enabled=true"]
    lines = lines[: start + 1] + inserted + filtered + lines[end:]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def set_startup_enabled(entry: StartupEntry, enabled: bool) -> None:
    """Activa o desactiva una entrada respetando la configuración del sistema."""
    user_dir = autostart_dir()

    if entry.user_path is not None:
        if entry.system_path is not None and not entry.user_has_exec:
            if enabled:
                try:
                    entry.user_path.unlink()
                except OSError:
                    pass
            else:
                _set_hidden(entry.user_path, True)
            return
        _set_hidden(entry.user_path, not enabled)
        return

    if entry.system_path is not None:
        if enabled:
            return
        user_dir.mkdir(parents=True, exist_ok=True)
        override = user_dir / entry.key
        override.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={entry.name}\n"
            "Hidden=true\n"
            "X-GNOME-Autostart-enabled=false\n",
            encoding="utf-8",
        )


__all__ = [
    "StartupEntry",
    "autostart_dir",
    "list_startup_entries",
    "set_startup_enabled",
]
