"""Utilidades de formato y diálogos compartidos por la interfaz."""

from __future__ import annotations

import datetime as _datetime
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402


def format_bytes(value: float | int | None) -> str:
    if value is None:
        return "—"
    value = float(value)
    if value < 1024:
        return f"{value:.0f} B"
    for unit in ("KB", "MB", "GB", "TB"):
        value /= 1024.0
        if value < 1024 or unit == "TB":
            if value >= 100:
                return f"{value:.0f} {unit}"
            if value >= 10:
                return f"{value:.1f} {unit}"
            return f"{value:.2f} {unit}"
    return f"{value:.2f} TB"


def format_rate(value: float | int | None) -> str:
    if value is None:
        return "—"
    return f"{format_bytes(value)}/s"


def format_percent(value: float | int | None, decimals: int = 1) -> str:
    if value is None:
        return "—"
    if decimals <= 0:
        return f"{float(value):.0f} %"
    return f"{float(value):.{decimals}f} %"


def format_duration(seconds: float | int | None) -> str:
    if not seconds or seconds < 0:
        return "—"
    seconds = int(seconds)
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days:
        return f"{days} d {hours} h {minutes} min"
    if hours:
        return f"{hours} h {minutes} min"
    if minutes:
        return f"{minutes} min {seconds} s"
    return f"{seconds} s"


def format_datetime(timestamp: float | int | None) -> str:
    if not timestamp:
        return "—"
    try:
        return _datetime.datetime.fromtimestamp(timestamp).strftime("%d/%m/%Y %H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return "—"


def format_time(timestamp: float | int | None) -> str:
    if not timestamp:
        return "—"
    try:
        return _datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
    except (OSError, OverflowError, ValueError):
        return "—"


def add_class(widget: Gtk.Widget, css_class: str) -> None:
    if not widget.has_css_class(css_class):
        widget.add_css_class(css_class)


def remove_class(widget: Gtk.Widget, css_class: str) -> None:
    if widget.has_css_class(css_class):
        widget.remove_css_class(css_class)


def make_badge(text: str, css_class: str = "badge") -> Gtk.Label:
    label = Gtk.Label(label=text, halign=Gtk.Align.START)
    add_class(label, "badge")
    if css_class and css_class != "badge":
        add_class(label, css_class)
    return label


def make_icon(name: str, size: int = 16) -> Gtk.Image:
    image = Gtk.Image.new_from_icon_name(name)
    image.set_pixel_size(size)
    return image


def show_message(
    parent: Gtk.Window | None,
    heading: str,
    body: str,
    close_label: str = "Cerrar",
) -> Adw.AlertDialog:
    dialog = Adw.AlertDialog(heading=heading, body=body)
    dialog.add_response("close", close_label)
    dialog.set_default_response("close")
    dialog.set_close_response("close")
    dialog.present(parent)
    return dialog


def confirm_action(
    parent: Gtk.Window | None,
    heading: str,
    body: str,
    confirm_label: str,
    on_confirm,
    destructive: bool = True,
    cancel_label: str = "Cancelar",
) -> Adw.AlertDialog:
    dialog = Adw.AlertDialog(heading=heading, body=body)
    dialog.add_response("cancel", cancel_label)
    dialog.add_response("confirm", confirm_label)
    dialog.set_default_response("cancel")
    dialog.set_close_response("cancel")
    appearance = (
        Adw.ResponseAppearance.DESTRUCTIVE
        if destructive
        else Adw.ResponseAppearance.SUGGESTED
    )
    dialog.set_response_appearance("confirm", appearance)

    def _finished(dialog, result) -> None:
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response == "confirm":
            on_confirm()

    dialog.choose(parent, None, _finished)
    return dialog


def copy_text(widget: Gtk.Widget, text: str) -> None:
    clipboard = widget.get_clipboard()
    clipboard.set(text)


def open_folder(folder: str | Path) -> bool:
    path = Path(folder)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    try:
        Gio.AppInfo.launch_default_for_uri(path.resolve().as_uri(), None)
        return True
    except (TypeError, ValueError, GLib.Error):
        return False


def activation_label(value: float) -> str:
    return f"{value:.0f} %"


__all__ = [
    "add_class",
    "confirm_action",
    "copy_text",
    "format_bytes",
    "format_datetime",
    "format_duration",
    "format_percent",
    "format_rate",
    "format_time",
    "make_badge",
    "make_icon",
    "open_folder",
    "remove_class",
    "show_message",
]
