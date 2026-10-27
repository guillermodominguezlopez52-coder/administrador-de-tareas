"""Aplicación GTK4/librería Adwaita."""

from __future__ import annotations

import sys
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk  # noqa: E402

from . import APP_ID, APP_NAME  # noqa: E402
from .core.settings import Settings  # noqa: E402
from .window import MainWindow  # noqa: E402


class TaskManagerApplication(Adw.Application):
    def __init__(self, settings: Settings | None = None, smoke_test: bool = False):
        super().__init__(application_id=APP_ID)
        self.settings = settings or Settings()
        self.smoke_test = smoke_test
        self._smoke_timeout_id = 0
        self.connect("startup", self._on_startup)
        self.connect("activate", self._on_activate)

    def _on_startup(self, _application) -> None:
        GLib.set_application_name(APP_NAME)
        GLib.set_prgname(APP_ID)
        self._install_app_actions()
        self._install_accelerators()
        self._load_css()
        manager = Adw.StyleManager.get_default()
        scheme = self.settings.get("color_scheme")
        manager.set_color_scheme(
            {
                "light": Adw.ColorScheme.FORCE_LIGHT,
                "dark": Adw.ColorScheme.FORCE_DARK,
            }.get(scheme, Adw.ColorScheme.DEFAULT)
        )

    def _load_css(self) -> None:
        display = Gdk.Display.get_default()
        if display is None:
            return
        base = Path(__file__).resolve().parent
        assets = base.parent / "assets"
        if assets.is_dir():
            theme = Gtk.IconTheme.get_for_display(display)
            theme.add_search_path(str(assets))
        css_path = base / "style.css"
        if not css_path.exists():
            return
        provider = Gtk.CssProvider()
        try:
            provider.load_from_path(str(css_path))
        except GLib.Error as error:
            print(f"No se pudo cargar el estilo: {error}", file=sys.stderr)
            return
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _install_app_actions(self) -> None:
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

    def _install_accelerators(self) -> None:
        self.set_accels_for_action("app.quit", ["<Primary>q"])
        self.set_accels_for_action("win.refresh", ["F5"])
        self.set_accels_for_action("win.find", ["<Primary>f"])
        self.set_accels_for_action("win.settings", ["<Primary>comma"])

    def _on_about(self, *_args) -> None:
        window = self.props.active_window
        if isinstance(window, MainWindow):
            window.show_about()

    def _on_activate(self, _application) -> None:
        window = self.props.active_window
        if window is None:
            if self.smoke_test:
                self.hold()
            window = MainWindow(self, self.settings, smoke_test=self.smoke_test)
            if not self.smoke_test:
                window.present()
            else:
                self._smoke_timeout_id = GLib.timeout_add_seconds(
                    20, self._on_smoke_timeout, window
                )
        elif not self.smoke_test:
            window.present()

    def _on_smoke_timeout(self, window: MainWindow) -> bool:
        if not window._smoke_done:
            print("SMOKE_TIMEOUT", flush=True)
            window._smoke_failed = True
            self.release()
            self.quit()
        return False

    def do_shutdown(self) -> None:
        if self._smoke_timeout_id:
            GLib.source_remove(self._smoke_timeout_id)
            self._smoke_timeout_id = 0
        window = self.props.active_window
        if isinstance(window, MainWindow):
            window.cleanup()
        Adw.Application.do_shutdown(self)


__all__ = ["TaskManagerApplication"]
