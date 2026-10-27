"""Pestaña Inicio: aplicaciones que se ejecutan al iniciar sesión."""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gdk, Gtk, Pango  # noqa: E402

from ...core.startup import (  # noqa: E402
    StartupEntry,
    autostart_dir,
    list_startup_entries,
    set_startup_enabled,
)
from ..common import add_class, make_icon, open_folder, show_message  # noqa: E402


class StartupPage(Gtk.Box):
    def __init__(self, window) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self._entries: list[StartupEntry] = []
        self._loading = False
        self._updating = False

        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        info.set_margin_top(12)
        info.set_margin_start(16)
        info.set_margin_end(16)
        add_class(info, "info-banner")
        info.append(make_icon("dialog-information-symbolic", 18))
        text = Gtk.Label(
            label=(
                "Estas aplicaciones se abren automáticamente al iniciar sesión. "
                "Los cambios se aplican en el próximo inicio."
            ),
            xalign=0,
            wrap=True,
        )
        text.set_hexpand(True)
        info.append(text)
        self.spinner = Gtk.Spinner()
        info.append(self.spinner)
        refresh_button = Gtk.Button(label="Actualizar")
        refresh_button.connect("clicked", lambda *_: self.refresh_async())
        info.append(refresh_button)
        folder_button = Gtk.Button(label="Abrir carpeta")
        folder_button.connect("clicked", lambda *_: self._open_folder())
        info.append(folder_button)
        self.append(info)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_show_separators(True)
        self.listbox.add_css_class("boxed-list")

        self.empty_label = Gtk.Label(
            label="No hay aplicaciones configuradas para iniciar con la sesión.",
            wrap=True,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )
        self.empty_label.add_css_class("dim-label")
        self.empty_label.set_margin_top(30)
        self.empty_label.set_margin_bottom(30)
        self.empty_label.set_visible(False)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_margin_top(12)
        scrolled.set_margin_bottom(16)
        scrolled.set_margin_start(16)
        scrolled.set_margin_end(16)
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        container.append(self.listbox)
        container.append(self.empty_label)
        scrolled.set_child(container)
        self.append(scrolled)

    def refresh_async(self) -> None:
        if self._loading:
            return
        self._loading = True
        self.spinner.start()
        self.window.run_async(list_startup_entries, self._on_loaded)

    def _on_loaded(self, entries, error) -> None:
        self._loading = False
        self.spinner.stop()
        if error is not None:
            show_message(
                self.window,
                "No se pudieron cargar las aplicaciones de inicio",
                str(error),
            )
            return
        self._entries = entries
        self._rebuild()

    def _rebuild(self) -> None:
        self._updating = True
        child = self.listbox.get_first_child()
        while child is not None:
            self.listbox.remove(child)
            child = self.listbox.get_first_child()
        for entry in self._entries:
            self.listbox.append(self._make_row(entry))
        self._updating = False
        self.empty_label.set_visible(not self._entries)

    def _make_row(self, entry: StartupEntry) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        add_class(row, "startup-row")
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)
        box.append(self._entry_icon(entry))

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)
        name = Gtk.Label(label=entry.name, xalign=0)
        add_class(name, "heading")
        name.set_ellipsize(Pango.EllipsizeMode.END)
        text_box.append(name)
        if entry.comment:
            comment = Gtk.Label(label=entry.comment, xalign=0)
            comment.add_css_class("dim-label")
            comment.set_ellipsize(Pango.EllipsizeMode.END)
            text_box.append(comment)
        subtitle = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        source = Gtk.Label(label=entry.source, halign=Gtk.Align.START)
        add_class(source, "badge")
        add_class(source, "badge-source")
        subtitle.append(source)
        if entry.exec_line:
            exec_label = Gtk.Label(label=entry.exec_line, xalign=0)
            exec_label.add_css_class("monospace")
            exec_label.add_css_class("caption")
            exec_label.add_css_class("dim-label")
            exec_label.set_ellipsize(Pango.EllipsizeMode.END)
            exec_label.set_hexpand(True)
            exec_label.set_tooltip_text(entry.exec_line)
            subtitle.append(exec_label)
        text_box.append(subtitle)
        box.append(text_box)

        switch = Gtk.Switch()
        switch.set_active(entry.enabled)
        switch.set_valign(Gtk.Align.CENTER)
        switch.connect("notify::active", self._on_switch_changed, entry, switch)
        box.append(switch)

        row.set_child(box)
        return row

    def _entry_icon(self, entry: StartupEntry) -> Gtk.Widget:
        image: Gtk.Image | None = None
        icon = entry.icon or ""
        if icon and Path(icon).exists():
            try:
                image = Gtk.Image.new_from_file(icon)
            except Exception:
                image = None
        if image is None:
            theme = Gtk.IconTheme.get_for_display(Gdk.Display.get_default())
            icon_name = icon if icon and theme.has_icon(icon) else "application-x-executable-symbolic"
            image = Gtk.Image.new_from_icon_name(icon_name)
        image.set_pixel_size(28)
        image.set_valign(Gtk.Align.CENTER)
        return image

    def _on_switch_changed(
        self, switch: Gtk.Switch, _param, entry: StartupEntry, widget: Gtk.Switch
    ) -> None:
        if self._updating:
            return
        target = switch.get_active()
        try:
            set_startup_enabled(entry, target)
        except OSError as error:
            self._updating = True
            widget.set_active(not target)
            self._updating = False
            show_message(
                self.window,
                "No se pudo cambiar el inicio automático",
                str(error),
            )
            return
        self.window.show_toast(
            "Se activará al iniciar sesión."
            if target
            else "Ya no se iniciará automáticamente."
        )
        self.refresh_async()

    def _open_folder(self) -> None:
        folder = autostart_dir()
        if not open_folder(folder):
            show_message(
                self.window,
                "No se pudo abrir la carpeta",
                f"Ruta: {folder}",
            )


__all__ = ["StartupPage"]
