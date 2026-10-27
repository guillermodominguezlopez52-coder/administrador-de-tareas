"""Configuración persistente del administrador de tareas."""

from __future__ import annotations

import json
import os
from pathlib import Path


def _config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "administrador-tareas"
    return Path.home() / ".config" / "administrador-tareas"


def _autostart_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME")
    if base:
        return Path(base) / "autostart"
    return Path.home() / ".config" / "autostart"


class Settings:
    """Preferencias del usuario guardadas en un archivo JSON."""

    DEFAULTS = {
        "refresh_interval": 2,
        "confirm_end_task": True,
        "color_scheme": "system",
        "window_width": 1180,
        "window_height": 760,
        "window_maximized": False,
    }

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (_config_dir() / "settings.json")
        self.values = dict(self.DEFAULTS)
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if isinstance(data, dict):
            for key in self.DEFAULTS:
                if key in data:
                    self.values[key] = data[key]
        self._sanitize()

    def _sanitize(self) -> None:
        try:
            interval = int(self.values["refresh_interval"])
        except (TypeError, ValueError):
            interval = self.DEFAULTS["refresh_interval"]
        if interval not in (1, 2, 3, 5, 10):
            interval = self.DEFAULTS["refresh_interval"]
        self.values["refresh_interval"] = interval
        if self.values.get("color_scheme") not in ("system", "light", "dark"):
            self.values["color_scheme"] = "system"
        for key in ("window_width", "window_height"):
            try:
                self.values[key] = max(720, int(self.values[key]))
            except (TypeError, ValueError):
                self.values[key] = self.DEFAULTS[key]
        self.values["confirm_end_task"] = bool(self.values["confirm_end_task"])
        self.values["window_maximized"] = bool(self.values["window_maximized"])

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps(self.values, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self.path)
        except OSError:
            pass

    def get(self, key: str, default=None):
        return self.values.get(key, self.DEFAULTS.get(key, default))

    def set(self, key: str, value) -> None:
        self.values[key] = value
        self._sanitize()
        self.save()


__all__ = ["Settings", "_autostart_dir"]
