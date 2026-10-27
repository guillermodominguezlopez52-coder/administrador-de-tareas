"""Pestaña Ajustes: frecuencia de actualización, tema y preferencias."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gtk  # noqa: E402

from ... import __version__  # noqa: E402
from ..common import confirm_action  # noqa: E402

REFRESH_OPTIONS = (1, 2, 3, 5, 10)
THEME_OPTIONS = ("system", "light", "dark")


class SettingsPage(Gtk.Box):
    def __init__(self, window) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.settings = window.settings

        page = Adw.PreferencesPage()
        page.set_vexpand(True)
        self.append(page)

        update_group = Adw.PreferencesGroup()
        update_group.set_title("Actualización")
        update_group.set_description(
            "Controla con qué frecuencia se actualizan las métricas y los procesos."
        )
        page.add(update_group)

        self.interval_row = Adw.ComboRow()
        self.interval_row.set_title("Frecuencia de actualización")
        self.interval_row.set_subtitle("Más frecuencia usa más recursos del sistema.")
        labels = Gtk.StringList.new(
            [
                "1 segundo",
                "2 segundos",
                "3 segundos",
                "5 segundos",
                "10 segundos",
            ]
        )
        self.interval_row.set_model(labels)
        current = self.settings.get("refresh_interval")
        try:
            index = REFRESH_OPTIONS.index(current)
        except ValueError:
            index = 1
        self.interval_row.set_selected(index)
        self.interval_row.connect("notify::selected", self._on_interval_changed)
        update_group.add(self.interval_row)

        self.confirm_row = Adw.SwitchRow()
        self.confirm_row.set_title("Confirmar antes de finalizar tareas")
        self.confirm_row.set_subtitle(
            "Muestra un diálogo de confirmación antes de cerrar un proceso."
        )
        self.confirm_row.set_active(bool(self.settings.get("confirm_end_task")))
        self.confirm_row.connect("notify::active", self._on_confirm_changed)
        update_group.add(self.confirm_row)

        appearance_group = Adw.PreferencesGroup()
        appearance_group.set_title("Apariencia")
        page.add(appearance_group)

        self.theme_row = Adw.ComboRow()
        self.theme_row.set_title("Tema de la interfaz")
        self.theme_row.set_model(Gtk.StringList.new(["Sistema", "Claro", "Oscuro"]))
        try:
            theme_index = THEME_OPTIONS.index(self.settings.get("color_scheme"))
        except ValueError:
            theme_index = 0
        self.theme_row.set_selected(theme_index)
        self.theme_row.connect("notify::selected", self._on_theme_changed)
        appearance_group.add(self.theme_row)

        info_group = Adw.PreferencesGroup()
        info_group.set_title("Información")
        page.add(info_group)

        version_row = Adw.ActionRow()
        version_row.set_title("Versión")
        version_row.set_subtitle(__version__)
        version_row.add_prefix(self._icon("application-x-executable-symbolic"))
        info_group.add(version_row)

        data_row = Adw.ActionRow()
        data_row.set_title("Datos del sistema")
        data_row.set_subtitle("psutil, /proc y systemd")
        data_row.add_prefix(self._icon("utilities-system-monitor-symbolic"))
        info_group.add(data_row)

        ui_row = Adw.ActionRow()
        ui_row.set_title("Interfaz")
        ui_row.set_subtitle("GTK 4 y libadwaita")
        ui_row.add_prefix(self._icon("applications-graphics-symbolic"))
        info_group.add(ui_row)

        about_row = Adw.ActionRow()
        about_row.set_title("Acerca de este administrador de tareas")
        about_row.set_subtitle("Créditos, versión y tecnologías utilizadas")
        about_row.set_activatable(True)
        about_row.add_suffix(
            Gtk.Image.new_from_icon_name("go-next-symbolic")
        )
        about_row.connect("activated", lambda *_: self.window.show_about())
        info_group.add(about_row)

        reset_group = Adw.PreferencesGroup()
        page.add(reset_group)
        reset_row = Adw.ActionRow()
        reset_row.set_title("Restaurar valores predeterminados")
        reset_row.set_subtitle("No afecta a procesos ni servicios")
        reset_button = Gtk.Button(label="Restaurar")
        reset_button.add_css_class("destructive-action")
        reset_button.set_valign(Gtk.Align.CENTER)
        reset_button.connect("clicked", lambda *_: self._confirm_reset())
        reset_row.add_suffix(reset_button)
        reset_group.add(reset_row)

    def _icon(self, name: str) -> Gtk.Image:
        image = Gtk.Image.new_from_icon_name(name)
        image.set_pixel_size(18)
        image.add_css_class("dim-label")
        return image

    def _on_interval_changed(self, row: Adw.ComboRow, _param) -> None:
        index = row.get_selected()
        if not (0 <= index < len(REFRESH_OPTIONS)):
            return
        value = REFRESH_OPTIONS[index]
        if self.settings.get("refresh_interval") == value:
            return
        self.settings.set("refresh_interval", value)
        self.window.set_refresh_interval(value)

    def _on_confirm_changed(self, row: Adw.SwitchRow, _param) -> None:
        self.settings.set("confirm_end_task", bool(row.get_active()))

    def _on_theme_changed(self, row: Adw.ComboRow, _param) -> None:
        index = row.get_selected()
        if not (0 <= index < len(THEME_OPTIONS)):
            return
        scheme = THEME_OPTIONS[index]
        self.settings.set("color_scheme", scheme)
        self.window.apply_color_scheme(scheme)

    def _confirm_reset(self) -> None:
        def _reset() -> None:
            self.settings.set("refresh_interval", 2)
            self.settings.set("confirm_end_task", True)
            self.settings.set("color_scheme", "system")
            self.interval_row.set_selected(REFRESH_OPTIONS.index(2))
            self.confirm_row.set_active(True)
            self.theme_row.set_selected(0)
            self.window.set_refresh_interval(2)
            self.window.apply_color_scheme("system")
            self.window.show_toast("Ajustes restaurados.")

        confirm_action(
            self.window,
            "Restaurar valores predeterminados",
            "Se restaurarán la frecuencia de actualización, el tema y las "
            "confirmaciones. Esta acción no afecta a los procesos ni servicios.",
            "Restaurar",
            _reset,
        )


__all__ = ["SettingsPage"]
