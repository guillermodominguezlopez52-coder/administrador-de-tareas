#!/usr/bin/env python3
"""Punto de entrada del Administrador de tareas para Linux."""

from __future__ import annotations

import argparse
import os
import sys

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from administrador_tareas import APP_NAME, __version__  # noqa: E402
from administrador_tareas.application import TaskManagerApplication  # noqa: E402
from administrador_tareas.core.settings import Settings  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="administrador-tareas",
        description=(
            "Administrador de tareas gráfico para Linux con procesos, "
            "rendimiento, inicio, usuarios y servicios."
        ),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"{APP_NAME} {__version__}",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
        print(
            "No se detectó un entorno gráfico (DISPLAY o WAYLAND_DISPLAY). "
            "Ejecuta esta aplicación desde tu sesión de escritorio.",
            file=sys.stderr,
        )
        return 1
    if (Gtk.get_major_version(), Gtk.get_minor_version()) < (4, 14):
        print(
            "Se requiere GTK 4.14 o superior. Actualiza las bibliotecas GTK "
            "de tu distribución.",
            file=sys.stderr,
        )
        return 1
    if (Adw.MAJOR_VERSION, Adw.MINOR_VERSION) < (1, 5):
        print(
            "Se requiere libadwaita 1.5 o superior. Actualiza libadwaita "
            "de tu distribución.",
            file=sys.stderr,
        )
        return 1
    try:
        settings = Settings()
        application = TaskManagerApplication(
            settings=settings,
            smoke_test=args.smoke_test,
        )
        return application.run([sys.argv[0]])
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
