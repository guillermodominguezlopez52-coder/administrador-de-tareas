"""Pestaña Servicios: unidades de systemd del sistema y del usuario."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gio, GLib, Gtk, Pango  # noqa: E402

from ...core.services import (  # noqa: E402
    ServiceInfo,
    list_services,
    run_action,
    service_journal,
)
from ..common import (  # noqa: E402
    add_class,
    confirm_action,
    copy_text,
    make_icon,
    show_message,
)

COL_NAME = 0
COL_STATE = 1
COL_ENABLED = 2
COL_SCOPE = 3
COL_DESCRIPTION = 4
COL_ACTIVE_RAW = 5
COL_ENABLED_RAW = 6
COL_KEY = 7

STATUS_FILTERS = ("all", "running", "stopped", "failed")
CRITICAL_UNITS = {
    "systemd-logind.service",
    "systemd-journald.service",
    "systemd-udevd.service",
    "dbus.service",
    "dbus-broker.service",
    "NetworkManager.service",
    "gdm.service",
    "gdm3.service",
    "sddm.service",
    "lightdm.service",
    "display-manager.service",
    "polkit.service",
}


class ServicesPage(Gtk.Box):
    def __init__(self, window) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self._services: list[ServiceInfo] = []
        self._by_key: dict[str, ServiceInfo] = {}
        self._loading = False
        self._selected_key: str | None = None

        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        info.set_margin_top(12)
        info.set_margin_start(16)
        info.set_margin_end(16)
        add_class(info, "info-banner")
        info.append(make_icon("emblem-system-symbolic", 18))
        text = Gtk.Label(
            label=(
                "Servicios del sistema y de tu sesión gestionados por systemd. "
                "Las acciones sobre servicios del sistema solicitan permisos "
                "de administrador."
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
        self.append(info)

        self.store = Gtk.ListStore(str, str, str, str, str, str, str, str)
        self.filter_model = Gtk.TreeModelFilter(child_model=self.store)
        self.filter_model.set_visible_func(self._visible_func)
        self.sort_model = Gtk.TreeModelSort(model=self.filter_model)
        self.sort_model.set_sort_column_id(COL_NAME, Gtk.SortType.ASCENDING)

        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(16)
        toolbar.set_margin_end(16)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Buscar servicios…")
        self.search.set_size_request(280, -1)
        self.search.connect("search-changed", lambda *_: self._refilter())
        toolbar.append(self.search)

        self.status_dropdown = Gtk.DropDown.new_from_strings(
            ["Todos", "En ejecución", "Detenidos", "Con errores"]
        )
        self.status_dropdown.connect("notify::selected", lambda *_: self._refilter())
        toolbar.append(self.status_dropdown)

        self.count_label = Gtk.Label(label="Cargando…", xalign=0)
        self.count_label.add_css_class("dim-label")
        self.count_label.set_hexpand(True)
        toolbar.append(self.count_label)

        self.start_button = Gtk.Button(label="Iniciar")
        self.start_button.set_action_name("svc.start")
        toolbar.append(self.start_button)
        self.stop_button = Gtk.Button(label="Detener")
        self.stop_button.set_action_name("svc.stop")
        toolbar.append(self.stop_button)
        self.menu_button = Gtk.MenuButton()
        self.menu_button.set_icon_name("open-menu-symbolic")
        self.menu_button.set_tooltip_text("Más acciones")
        self.menu_button.set_menu_model(self._build_menu())
        toolbar.append(self.menu_button)
        self.append(toolbar)

        self.tree = Gtk.TreeView(model=self.sort_model)
        self.tree.set_headers_visible(True)
        self.tree.set_grid_lines(Gtk.TreeViewGridLines.HORIZONTAL)
        add_class(self.tree, "process-tree")
        self.tree.get_selection().connect("changed", self._on_selection_changed)
        self.tree.connect("row-activated", lambda *_: self._show_journal())

        name_renderer = Gtk.CellRendererText()
        name_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        name_col = Gtk.TreeViewColumn(title="Servicio")
        name_col.pack_start(name_renderer, True)
        name_col.add_attribute(name_renderer, "text", COL_NAME)
        name_col.set_sort_column_id(COL_NAME)
        name_col.set_expand(True)
        name_col.set_resizable(True)
        name_col.set_min_width(220)
        self.tree.append_column(name_col)

        state_renderer = Gtk.CellRendererText()
        state_col = Gtk.TreeViewColumn(title="Estado")
        state_col.pack_start(state_renderer, True)
        state_col.add_attribute(state_renderer, "text", COL_STATE)
        state_col.set_sort_column_id(COL_STATE)
        state_col.set_resizable(True)
        state_col.set_min_width(150)
        state_col.set_cell_data_func(state_renderer, self._style_state)
        self.tree.append_column(state_col)

        enabled_renderer = Gtk.CellRendererText()
        enabled_col = Gtk.TreeViewColumn(title="Inicio automático")
        enabled_col.pack_start(enabled_renderer, True)
        enabled_col.add_attribute(enabled_renderer, "text", COL_ENABLED)
        enabled_col.set_sort_column_id(COL_ENABLED)
        enabled_col.set_resizable(True)
        enabled_col.set_min_width(140)
        self.tree.append_column(enabled_col)

        scope_renderer = Gtk.CellRendererText()
        scope_col = Gtk.TreeViewColumn(title="Ámbito")
        scope_col.pack_start(scope_renderer, True)
        scope_col.add_attribute(scope_renderer, "text", COL_SCOPE)
        scope_col.set_sort_column_id(COL_SCOPE)
        scope_col.set_resizable(True)
        scope_col.set_min_width(90)
        self.tree.append_column(scope_col)

        desc_renderer = Gtk.CellRendererText()
        desc_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        desc_col = Gtk.TreeViewColumn(title="Descripción")
        desc_col.pack_start(desc_renderer, True)
        desc_col.add_attribute(desc_renderer, "text", COL_DESCRIPTION)
        desc_col.set_sort_column_id(COL_DESCRIPTION)
        desc_col.set_resizable(True)
        desc_col.set_min_width(240)
        self.tree.append_column(desc_col)

        self.empty_label = Gtk.Label(
            label="No hay servicios que coincidan con el filtro.",
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            wrap=True,
        )
        self.empty_label.add_css_class("dim-label")
        self.empty_label.set_visible(False)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_child(self.tree)
        overlay = Gtk.Overlay()
        overlay.set_child(scrolled)
        overlay.add_overlay(self.empty_label)
        add_class(overlay, "table-card")
        overlay.set_margin_start(16)
        overlay.set_margin_end(16)
        overlay.set_margin_bottom(16)
        self.append(overlay)

        self._build_actions()
        self._update_actions()

    def _build_menu(self):
        menu = Gio.Menu()
        menu.append("Reiniciar", "svc.restart")
        menu.append("Habilitar al iniciar", "svc.enable")
        menu.append("Deshabilitar al iniciar", "svc.disable")
        menu.append("Ver registro", "svc.journal")
        return menu

    def _build_actions(self) -> None:
        group = Gio.SimpleActionGroup()
        for name in ("start", "stop", "restart", "enable", "disable", "journal"):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, n=name: self._run_action(n))
            group.add_action(action)
        self.insert_action_group("svc", group)
        self._action_group = group

    # ------------------------------------------------------------- filtering
    def _refilter(self) -> None:
        self.filter_model.refilter()
        self._update_count()

    def _visible_func(self, model, tree_iter, _data) -> bool:
        selected = self.status_dropdown.get_selected()
        status_filter = STATUS_FILTERS[selected] if 0 <= selected < len(STATUS_FILTERS) else "all"
        active = model.get_value(tree_iter, COL_ACTIVE_RAW)
        if status_filter == "running" and active != "active":
            return False
        if status_filter == "stopped" and active != "inactive":
            return False
        if status_filter == "failed" and active != "failed":
            return False
        query = self.search.get_text().strip().casefold()
        if not query:
            return True
        haystack = " ".join(
            [
                model.get_value(tree_iter, COL_NAME),
                model.get_value(tree_iter, COL_DESCRIPTION),
                model.get_value(tree_iter, COL_SCOPE),
                model.get_value(tree_iter, COL_STATE),
            ]
        ).casefold()
        return all(term in haystack for term in query.split())

    def _update_count(self) -> None:
        visible = self.filter_model.iter_n_children(None)
        total = len(self._services)
        if total == 0:
            self.count_label.set_text("Cargando servicios…")
        elif visible == total:
            self.count_label.set_text(f"{total} servicios")
        else:
            self.count_label.set_text(f"{visible} de {total} servicios")
        self.empty_label.set_visible(visible == 0)

    # ---------------------------------------------------------------- load
    def refresh_async(self) -> None:
        if self._loading:
            return
        self._loading = True
        self.spinner.start()
        self.window.run_async(list_services, self._on_loaded)

    def _on_loaded(self, services, error) -> None:
        self._loading = False
        self.spinner.stop()
        if error is not None:
            show_message(
                self.window,
                "No se pudieron cargar los servicios",
                str(error),
            )
            return
        self._services = services
        self._by_key = {f"{item.scope}:{item.name}": item for item in services}
        selected = self._selected_service()
        selected_key = f"{selected.scope}:{selected.name}" if selected else None
        self.store.clear()
        for service in services:
            self.store.append(
                [
                    service.name,
                    service.state_text,
                    service.enabled_text,
                    service.scope_text,
                    service.description,
                    service.active,
                    service.enabled_state,
                    f"{service.scope}:{service.name}",
                ]
            )
        self._refilter()
        if selected_key:
            self._select_key(selected_key)
        self._update_actions()

    def _select_key(self, key: str) -> None:
        tree_iter = self.sort_model.get_iter_first()
        while tree_iter is not None:
            if self.sort_model.get_value(tree_iter, COL_KEY) == key:
                self.tree.get_selection().select_iter(tree_iter)
                return
            tree_iter = self.sort_model.iter_next(tree_iter)

    # ------------------------------------------------------------- selection
    def _selected_service(self) -> ServiceInfo | None:
        model, tree_iter = self.tree.get_selection().get_selected()
        if tree_iter is None:
            return None
        key = model.get_value(tree_iter, COL_KEY)
        return self._by_key.get(key)

    def _on_selection_changed(self, _selection) -> None:
        self._update_actions()

    def _update_actions(self) -> None:
        service = self._selected_service()
        has_selection = service is not None
        running = service.is_running if service else False
        enabled = service.enabled_state in ("enabled", "enabled-runtime") if service else False
        self._action_group.lookup_action("start").set_enabled(
            has_selection and not running
        )
        self._action_group.lookup_action("stop").set_enabled(
            has_selection and running
        )
        self._action_group.lookup_action("restart").set_enabled(
            has_selection and running
        )
        self._action_group.lookup_action("enable").set_enabled(
            has_selection and not enabled
        )
        self._action_group.lookup_action("disable").set_enabled(
            has_selection and enabled
        )
        self._action_group.lookup_action("journal").set_enabled(has_selection)

    # --------------------------------------------------------------- actions
    def _run_action(self, action: str) -> None:
        service = self._selected_service()
        if service is None:
            return
        if service.name in CRITICAL_UNITS and action in ("stop", "restart", "disable"):
            body = (
                f"«{service.name}» es un servicio esencial del sistema. "
                "Detenerlo o deshabilitarlo puede afectar la sesión, la red o "
                "el inicio del equipo.\n\n¿Quieres continuar?"
            )
            confirm_action(
                self.window,
                "Servicio esencial",
                body,
                {
                    "stop": "Detener servicio",
                    "restart": "Reiniciar servicio",
                    "disable": "Deshabilitar",
                }[action],
                lambda: self._perform_action(service, action),
            )
            return
        if action in ("stop", "restart", "disable"):
            labels = {
                "stop": "Detener servicio",
                "restart": "Reiniciar servicio",
                "disable": "Deshabilitar al iniciar",
            }
            descriptions = {
                "stop": f"Se detendrá «{service.name}». Las aplicaciones que dependen de él podrían dejar de funcionar.",
                "restart": f"Se reiniciará «{service.name}». Habrá una interrupción breve del servicio.",
                "disable": f"«{service.name}» dejará de iniciarse automáticamente en el próximo arranque.",
            }
            confirm_action(
                self.window,
                labels[action],
                descriptions[action],
                labels[action],
                lambda: self._perform_action(service, action),
                destructive=action in ("stop", "disable"),
            )
            return
        self._perform_action(service, action)

    def _perform_action(self, service: ServiceInfo, action: str) -> None:
        def _finished(result, error) -> None:
            if error is not None:
                show_message(self.window, "No se pudo completar", str(error))
                return
            ok, message = result
            if ok:
                self.window.show_toast(message)
                GLib.timeout_add(600, self.refresh_async)
            else:
                show_message(
                    self.window,
                    "No se pudo completar la operación",
                    message,
                )

        self.window.run_async(lambda: run_action(service, action), _finished)

    def _show_journal(self) -> None:
        service = self._selected_service()
        if service is None:
            return

        def _loaded(text, error) -> None:
            if error is not None:
                show_message(self.window, "No se pudo leer el registro", str(error))
                return
            self._present_journal(service, text)

        self.window.run_async(lambda: service_journal(service), _loaded)

    def _present_journal(self, service: ServiceInfo, text: str) -> None:
        win = Adw.Window()
        win.set_transient_for(self.window)
        win.set_modal(True)
        win.set_title(f"Registro de {service.name}")
        win.set_default_size(820, 560)
        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title=service.name,
                subtitle="Últimas 200 líneas del registro",
            )
        )
        toolbar.add_top_bar(header)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        view = Gtk.TextView()
        view.set_editable(False)
        view.set_monospace(True)
        view.set_cursor_visible(False)
        view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        view.get_buffer().set_text(text)
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(view)
        box.append(scrolled)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions.set_margin_top(8)
        actions.set_margin_bottom(10)
        actions.set_margin_start(12)
        actions.set_margin_end(12)
        actions.set_halign(Gtk.Align.END)
        copy_button = Gtk.Button(label="Copiar")
        copy_button.connect("clicked", lambda *_: copy_text(self, text))
        actions.append(copy_button)
        close_button = Gtk.Button(label="Cerrar")
        close_button.connect("clicked", lambda *_: win.close())
        actions.append(close_button)
        box.append(actions)

        toolbar.set_content(box)
        win.set_content(toolbar)
        win.present()

    def _style_state(self, _column, cell, model, tree_iter, _data) -> None:
        active = model.get_value(tree_iter, COL_ACTIVE_RAW)
        if active == "failed":
            cell.set_property("foreground", "#e01b24")
        elif active == "active":
            cell.set_property("foreground", "#26a269")
        else:
            cell.set_property("foreground", None)


__all__ = ["ServicesPage"]
