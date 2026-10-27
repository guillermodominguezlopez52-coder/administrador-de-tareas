"""Ventana principal del administrador de tareas."""

from __future__ import annotations

import sys
import time
from concurrent.futures import ThreadPoolExecutor

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

from . import APP_NAME, __version__  # noqa: E402
from .core import actions  # noqa: E402
from .core.processes import ProcessCollector, ProcessInfo  # noqa: E402
from .core.system import SystemMonitor, SystemSnapshot  # noqa: E402
from .ui.common import add_class, format_percent, format_time  # noqa: E402
from .ui.pages.performance import PerformancePage  # noqa: E402
from .ui.pages.services_page import ServicesPage  # noqa: E402
from .ui.pages.settings_page import SettingsPage  # noqa: E402
from .ui.pages.startup import StartupPage  # noqa: E402
from .ui.pages.users import UsersPage  # noqa: E402
from .ui.process_table import ProcessTablePage  # noqa: E402

PAGE_TITLES = {
    "processes": "Procesos",
    "performance": "Rendimiento",
    "startup": "Inicio",
    "users": "Usuarios",
    "details": "Detalles",
    "services": "Servicios",
    "settings": "Ajustes",
}

PAGE_SUBTITLES = {
    "processes": "Aplicaciones y procesos en ejecución",
    "performance": "Uso de CPU, memoria, disco y red",
    "startup": "Aplicaciones que se abren al iniciar sesión",
    "users": "Sesiones abiertas y recursos que consumen",
    "details": "Información avanzada de cada proceso",
    "services": "Servicios de systemd del sistema y del usuario",
    "settings": "Preferencias de actualización y apariencia",
}

NAV_ITEMS = [
    ("section", "MONITORIZACIÓN"),
    ("processes", "Procesos", "view-list-symbolic"),
    ("performance", "Rendimiento", "speedometer-symbolic"),
    ("startup", "Inicio", "application-x-executable-symbolic"),
    ("users", "Usuarios", "system-users-symbolic"),
    ("section", "AVANZADO"),
    ("details", "Detalles", "view-list-bullet-symbolic"),
    ("services", "Servicios", "emblem-system-symbolic"),
    ("section", "PREFERENCIAS"),
    ("settings", "Ajustes", "preferences-system-symbolic"),
]


class MainWindow(Adw.ApplicationWindow):
    def __init__(
        self,
        application: Adw.Application,
        settings,
        smoke_test: bool = False,
    ) -> None:
        super().__init__(application=application)
        self.settings = settings
        self.smoke_test = smoke_test
        self._smoke_done = False
        self._smoke_failed = False
        self.last_processes: list[ProcessInfo] = []
        self.last_snapshot: SystemSnapshot | None = None
        self._pending_snapshot: SystemSnapshot | None = None
        self._last_update = 0.0
        self._refreshing = False
        self._paused = False
        self._timer_id = 0
        self._refresh_interval = int(settings.get("refresh_interval"))
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="taskmgr")
        self.monitor = SystemMonitor()
        self.process_collector = ProcessCollector()
        self._nav_rows: dict[str, Gtk.ListBoxRow] = {}
        self._nav_keys: dict[Gtk.ListBoxRow, str] = {}
        self._toast_overlay: Adw.ToastOverlay | None = None

        self.set_title(APP_NAME)
        self.set_default_size(
            int(settings.get("window_width")),
            int(settings.get("window_height")),
        )
        self.set_icon_name("administrador-tareas")
        if settings.get("window_maximized"):
            self.maximize()

        self._build_ui()
        self._install_actions()
        self.apply_color_scheme(settings.get("color_scheme"))
        self.connect("close-request", self._on_close_request)
        GLib.idle_add(self._initial_refresh)
        self._start_timer()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.header = Adw.HeaderBar()
        self.window_title = Adw.WindowTitle(title=APP_NAME, subtitle="Procesos")
        self.header.set_title_widget(self.window_title)

        self.refresh_button = Gtk.Button()
        self.refresh_button.set_icon_name("view-refresh-symbolic")
        self.refresh_button.set_tooltip_text("Actualizar ahora (F5)")
        self.refresh_button.connect("clicked", lambda *_: self.refresh(manual=True))
        self.header.pack_end(self.refresh_button)

        self.pause_button = Gtk.ToggleButton()
        self.pause_button.set_icon_name("media-playback-pause-symbolic")
        self.pause_button.set_tooltip_text("Pausar actualización automática")
        self.pause_button.connect("toggled", self._on_pause_toggled)
        self.header.pack_end(self.pause_button)

        menu = Gio.Menu()
        top = Gio.Menu()
        top.append("Actualizar ahora", "win.refresh")
        top.append("Pausar o reanudar", "win.toggle-pause")
        top.append("Buscar proceso", "win.find")
        menu.append_section(None, top)
        preferences = Gio.Menu()
        preferences.append("Ajustes", "win.settings")
        preferences.append("Acerca de", "win.show-about")
        menu.append_section(None, preferences)
        bottom = Gio.Menu()
        bottom.append("Salir", "app.quit")
        menu.append_section(None, bottom)
        self.menu_button = Gtk.MenuButton()
        self.menu_button.set_icon_name("open-menu-symbolic")
        self.menu_button.set_menu_model(menu)
        self.menu_button.set_tooltip_text("Menú principal")
        self.header.pack_end(self.menu_button)
        root.append(self.header)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        body.set_vexpand(True)
        root.append(body)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(120)
        self.stack.set_vexpand(True)
        self.stack.set_hexpand(True)

        self.process_page = ProcessTablePage(self, mode="processes")
        self.performance_page = PerformancePage(self)
        self.startup_page = StartupPage(self)
        self.users_page = UsersPage(self)
        self.details_page = ProcessTablePage(
            self, mode="details", show_details_panel=False
        )
        self.services_page = ServicesPage(self)
        self.settings_page = SettingsPage(self)
        self.pages = {
            "processes": self.process_page,
            "performance": self.performance_page,
            "startup": self.startup_page,
            "users": self.users_page,
            "details": self.details_page,
            "services": self.services_page,
            "settings": self.settings_page,
        }
        for key, page in self.pages.items():
            self.stack.add_named(page, key)

        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar.set_size_request(225, -1)
        add_class(sidebar, "sidebar")

        brand = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        add_class(brand, "sidebar-brand")
        logo = Gtk.Image.new_from_icon_name("administrador-tareas")
        logo.set_pixel_size(34)
        brand.append(logo)
        brand_text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        brand_text.set_valign(Gtk.Align.CENTER)
        brand_title = Gtk.Label(label=APP_NAME, xalign=0)
        add_class(brand_title, "brand-title")
        brand_subtitle = Gtk.Label(label="Monitor del sistema", xalign=0)
        add_class(brand_subtitle, "brand-subtitle")
        brand_text.append(brand_title)
        brand_text.append(brand_subtitle)
        brand.append(brand_text)
        sidebar.append(brand)

        self.nav_list = Gtk.ListBox()
        self.nav_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.nav_list.add_css_class("nav")
        self.nav_list.set_margin_top(8)
        self.nav_list.connect("row-selected", self._on_nav_selected)
        for item in NAV_ITEMS:
            if item[0] == "section":
                self.nav_list.append(self._nav_section(item[1]))
            else:
                key, label, icon = item
                row = self._nav_row(key, label, icon)
                self.nav_list.append(row)
        self.nav_scroll = Gtk.ScrolledWindow()
        self.nav_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.nav_scroll.set_vexpand(True)
        self.nav_scroll.set_child(self.nav_list)
        sidebar.append(self.nav_scroll)

        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        add_class(footer, "sidebar-footer")
        footer_label = Gtk.Label(
            label=f"Administrador de tareas\nVersión {__version__}",
            xalign=0,
        )
        footer.append(footer_label)
        sidebar.append(footer)

        body.append(sidebar)
        body.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        body.append(self.stack)

        self.statusbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        add_class(self.statusbar, "statusbar")
        self.status_processes = Gtk.Label(label="Iniciando…", xalign=0)
        self.status_metrics = Gtk.Label(label="", xalign=0)
        self.status_updated = Gtk.Label(label="", xalign=1)
        self.status_updated.set_hexpand(True)
        self.statusbar.append(self.status_processes)
        self.statusbar.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        self.statusbar.append(self.status_metrics)
        self.statusbar.append(self.status_updated)
        root.append(self.statusbar)

        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(root)
        self.set_content(self._toast_overlay)

        self.nav_list.select_row(self._nav_rows["processes"])

    def _nav_section(self, text: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        add_class(row, "nav-section-row")
        label = Gtk.Label(label=text, xalign=0)
        add_class(label, "nav-section")
        row.set_child(label)
        return row

    def _nav_row(self, key: str, label: str, icon: str) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        box.set_margin_top(2)
        box.set_margin_bottom(2)
        image = Gtk.Image.new_from_icon_name(icon)
        image.set_pixel_size(16)
        text = Gtk.Label(label=label, xalign=0)
        text.set_hexpand(True)
        box.append(image)
        box.append(text)
        row.set_child(box)
        self._nav_rows[key] = row
        self._nav_keys[row] = key
        return row

    # -------------------------------------------------------------- actions
    def _install_actions(self) -> None:
        actions_map = {
            "refresh": lambda *_: self.refresh(manual=True),
            "toggle-pause": lambda *_: self.set_paused(not self._paused),
            "find": lambda *_: self._find_process(),
            "settings": lambda *_: self._select_page("settings"),
            "show-about": lambda *_: self.show_about(),
        }
        for name, callback in actions_map.items():
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

    # ----------------------------------------------------------- navigation
    def _on_nav_selected(self, _listbox: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        key = self._nav_keys.get(row)
        if key is None:
            return
        self.stack.set_visible_child_name(key)
        self.window_title.set_subtitle(PAGE_SUBTITLES.get(key, ""))
        self._on_page_shown(key)

    def _on_page_shown(self, key: str) -> None:
        if key == "startup":
            self.startup_page.refresh_async()
        elif key == "services":
            self.services_page.refresh_async()
        elif key == "users":
            self.users_page.update_usage(self.last_processes)
            self.users_page.refresh_async()

    def _select_page(self, key: str) -> None:
        row = self._nav_rows.get(key)
        if row is not None:
            self.nav_list.select_row(row)

    def _find_process(self) -> None:
        self._select_page("processes")
        GLib.idle_add(self._focus_search)

    def _focus_search(self) -> bool:
        self.process_page.focus_search()
        return False

    # ------------------------------------------------------------- refresh
    def _initial_refresh(self) -> bool:
        self.refresh()
        return False

    def _start_timer(self) -> None:
        self._stop_timer()
        if not self._paused:
            self._timer_id = GLib.timeout_add_seconds(
                self._refresh_interval, self._on_timer
            )

    def _stop_timer(self) -> None:
        if self._timer_id:
            GLib.source_remove(self._timer_id)
            self._timer_id = 0

    def _on_timer(self) -> bool:
        if not self._paused:
            self.refresh()
        return True

    def refresh(self, manual: bool = False) -> None:
        if self._refreshing:
            return
        self._refreshing = True
        try:
            self._pending_snapshot = self.monitor.sample()
        except Exception as error:  # pragma: no cover - entorno inesperado
            self._pending_snapshot = None
            self._refreshing = False
            self.status_updated.set_text(f"No se pudieron leer las métricas: {error}")
            return
        try:
            future = self._executor.submit(self.process_collector.collect)
        except RuntimeError:
            self._refreshing = False
            return
        future.add_done_callback(self._on_processes_done)

    def _on_processes_done(self, future) -> None:
        try:
            processes = future.result()
        except Exception as error:  # pragma: no cover - entorno inesperado
            GLib.idle_add(self._apply_error, str(error))
            return
        GLib.idle_add(self._apply_processes, processes)

    def _apply_error(self, message: str) -> bool:
        self._refreshing = False
        self.status_updated.set_text("Error al actualizar los procesos")
        print(f"Error al recopilar procesos: {message}", file=sys.stderr)
        if self.smoke_test and not self._smoke_done:
            self._smoke_done = True
            self._smoke_failed = True
            print(f"SMOKE_ERROR {message}", flush=True)
            self.get_application().release()
            self.get_application().quit()
        return False

    def _apply_processes(self, processes: list[ProcessInfo]) -> bool:
        self.last_processes = processes
        self._refreshing = False
        self._last_update = time.monotonic()
        self.process_page.update(processes)
        self.details_page.update(processes)
        self.users_page.update_usage(processes)
        snapshot = self._pending_snapshot
        if snapshot is not None:
            self.last_snapshot = snapshot
            self.performance_page.update(snapshot, len(processes))
            self._update_status(snapshot, len(processes))
        if self.smoke_test and not self._smoke_done:
            self._smoke_done = True
            snapshot_text = ""
            if snapshot is not None:
                snapshot_text = (
                    f" cpu={snapshot.cpu_percent:.1f}"
                    f" mem={snapshot.mem_percent:.1f}"
                    f" cores={snapshot.cpu_count}"
                )
            print(
                f"SMOKE_OK processes={len(processes)} pages={len(self.pages)}"
                f"{snapshot_text}",
                flush=True,
            )
            self.get_application().release()
            self.get_application().quit()
        return False

    def _update_status(self, snapshot: SystemSnapshot, process_count: int) -> None:
        self.status_processes.set_text(f"{process_count} procesos")
        self.status_metrics.set_text(
            f"CPU {format_percent(snapshot.cpu_percent, 0)} · "
            f"Memoria {format_percent(snapshot.mem_percent, 0)}"
        )
        state = "Actualizado a las " + format_time(time.time())
        if self._paused:
            state = "Actualización en pausa · " + state
        self.status_updated.set_text(state)

    def request_refresh(self) -> bool:
        self.refresh(manual=True)
        return False

    def set_paused(self, paused: bool) -> None:
        paused = bool(paused)
        if self._paused == paused:
            if self.pause_button.get_active() != paused:
                self.pause_button.set_active(paused)
            return
        self._paused = paused
        if self.pause_button.get_active() != paused:
            self.pause_button.set_active(paused)
        if paused:
            self._stop_timer()
            self.pause_button.set_icon_name("media-playback-start-symbolic")
            self.pause_button.set_tooltip_text("Reanudar actualización automática")
            self.status_updated.set_text("Actualización en pausa")
        else:
            self.pause_button.set_icon_name("media-playback-pause-symbolic")
            self.pause_button.set_tooltip_text("Pausar actualización automática")
            self._start_timer()
            self.refresh()

    def _on_pause_toggled(self, button: Gtk.ToggleButton) -> None:
        self.set_paused(button.get_active())

    def set_refresh_interval(self, seconds: int) -> None:
        try:
            seconds = max(1, int(seconds))
        except (TypeError, ValueError):
            seconds = 2
        self._refresh_interval = seconds
        if not self._paused:
            self._start_timer()

    def apply_color_scheme(self, scheme: str) -> None:
        manager = Adw.StyleManager.get_default()
        mapping = {
            "system": Adw.ColorScheme.DEFAULT,
            "light": Adw.ColorScheme.FORCE_LIGHT,
            "dark": Adw.ColorScheme.FORCE_DARK,
        }
        manager.set_color_scheme(mapping.get(scheme, Adw.ColorScheme.DEFAULT))

    # -------------------------------------------------------------- helpers
    def show_toast(self, message: str) -> None:
        if self._toast_overlay is None:
            return
        toast = Adw.Toast.new(message)
        toast.set_timeout(3)
        self._toast_overlay.add_toast(toast)

    def run_async(self, function, callback) -> None:
        def _done(future) -> None:
            try:
                result = future.result()
                error = None
            except Exception as caught:  # noqa: BLE001
                result = None
                error = caught

            def _deliver() -> bool:
                callback(result, error)
                return False

            GLib.idle_add(_deliver)

        try:
            self._executor.submit(function).add_done_callback(_done)
        except RuntimeError as error:
            GLib.idle_add(lambda: callback(None, error) or False)

    def run_command_async(self, command: list[str], callback) -> None:
        def _adapted(result, error) -> None:
            if error is not None:
                callback(False, str(error))
            else:
                callback(result[0], result[1])

        self.run_async(lambda: actions.run_command(command), _adapted)

    def show_about(self) -> None:
        dialog = Adw.AboutDialog()
        dialog.set_application_name(APP_NAME)
        dialog.set_application_icon("administrador-tareas")
        dialog.set_developer_name("Proyecto Administrador de tareas")
        dialog.set_version(__version__)
        dialog.set_comments(
            "Una alternativa sencilla al administrador de tareas de Windows, "
            "pensada para Linux. Permite supervisar procesos, rendimiento, "
            "aplicaciones de inicio, usuarios y servicios del sistema."
        )
        dialog.set_developers(["Colaboradores del proyecto"])
        dialog.set_copyright("© 2026")
        dialog.set_license_type(Gtk.License.MIT_X11)
        dialog.present(self)

    # ---------------------------------------------------------------- close
    def cleanup(self) -> None:
        self._stop_timer()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _on_close_request(self, *_args) -> bool:
        self.cleanup()
        try:
            if self.is_maximized():
                self.settings.set("window_maximized", True)
            else:
                self.settings.set("window_maximized", False)
                self.settings.set("window_width", self.get_width())
                self.settings.set("window_height", self.get_height())
        except Exception:
            pass
        return False


__all__ = ["MainWindow"]
