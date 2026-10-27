"""Tabla de procesos con búsqueda, filtros, detalles y acciones."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, Gio, GLib, Gtk, Pango  # noqa: E402

from ..core import actions  # noqa: E402
from ..core.processes import ProcessInfo  # noqa: E402
from .common import (  # noqa: E402
    add_class,
    confirm_action,
    copy_text,
    format_bytes,
    format_datetime,
    format_percent,
    format_rate,
    format_time,
    make_icon,
    show_message,
)

COL_PID = 0
COL_PPID = 1
COL_NAME = 2
COL_NAME_LOWER = 3
COL_STATUS = 4
COL_CPU = 5
COL_CPU_TEXT = 6
COL_MEM = 7
COL_MEM_TEXT = 8
COL_DISK = 9
COL_DISK_TEXT = 10
COL_USER = 11
COL_KIND = 12
COL_KIND_TEXT = 13
COL_ICON = 14
COL_THREADS = 15
COL_PRIORITY = 16
COL_START = 17
COL_EXE = 18
COL_CMDLINE = 19
COL_TOOLTIP = 20
COL_MEM_PERCENT = 21
COL_START_RAW = 22

ROW_TYPES = [
    int,
    int,
    str,
    str,
    str,
    float,
    str,
    int,
    str,
    float,
    str,
    str,
    str,
    str,
    str,
    int,
    str,
    str,
    str,
    str,
    str,
    float,
    float,
]

KIND_FILTERS = ("all", "app", "background", "system")

PRIORITY_OPTIONS = (
    ("Muy alta", -15),
    ("Alta", -5),
    ("Normal", 0),
    ("Baja", 5),
    ("Muy baja", 15),
)


class ProcessDetailsPanel(Gtk.Box):
    def __init__(self, page: "ProcessTablePage") -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.page = page
        self.set_size_request(320, -1)
        add_class(self, "details-panel")

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.append(self.stack)

        empty = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        empty.set_valign(Gtk.Align.CENTER)
        empty.set_halign(Gtk.Align.CENTER)
        empty.set_margin_top(24)
        empty.set_margin_bottom(24)
        empty.set_margin_start(20)
        empty.set_margin_end(20)
        icon = make_icon("utilities-system-monitor-symbolic", 48)
        icon.add_css_class("dim-label")
        empty.append(icon)
        title = Gtk.Label(label="Selecciona un proceso")
        add_class(title, "title-4")
        empty.append(title)
        description = Gtk.Label(
            label="Haz clic en una fila para ver sus detalles y acciones.",
            wrap=True,
            justify=Gtk.Justification.CENTER,
        )
        description.add_css_class("dim-label")
        empty.append(description)
        self.stack.add_named(empty, "empty")

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        scrolled.set_child(content)

        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.icon = make_icon("application-x-executable-symbolic", 28)
        self.name_label = Gtk.Label(xalign=0)
        self.name_label.set_wrap(True)
        add_class(self.name_label, "title-3")
        header.append(self.icon)
        header.append(self.name_label)
        content.append(header)

        self.kind_label = Gtk.Label(xalign=0, halign=Gtk.Align.START)
        add_class(self.kind_label, "badge")
        content.append(self.kind_label)

        content.append(Gtk.Separator())

        grid = Gtk.Grid()
        grid.set_column_spacing(14)
        grid.set_row_spacing(8)
        content.append(grid)
        self.fields: dict[str, Gtk.Label] = {}
        rows = [
            ("PID", "pid"),
            ("Proceso padre", "ppid"),
            ("Usuario", "user"),
            ("Estado", "status"),
            ("CPU", "cpu"),
            ("Memoria", "memory"),
            ("Disco", "disk"),
            ("Prioridad", "priority"),
            ("Subprocesos", "threads"),
            ("Inicio", "start"),
        ]
        for row, (label_text, key) in enumerate(rows):
            label = Gtk.Label(label=label_text, xalign=0)
            label.add_css_class("dim-label")
            value = Gtk.Label(label="—", xalign=0)
            value.set_selectable(True)
            value.set_hexpand(True)
            value.set_wrap(True)
            grid.attach(label, 0, row, 1, 1)
            grid.attach(value, 1, row, 1, 1)
            self.fields[key] = value

        content.append(Gtk.Separator())
        section = Gtk.Label(label="Ejecutable", xalign=0)
        add_class(section, "heading")
        content.append(section)
        self.exe_label = Gtk.Label(label="—", xalign=0)
        self.exe_label.set_selectable(True)
        self.exe_label.set_wrap(True)
        self.exe_label.add_css_class("monospace")
        self.exe_label.add_css_class("caption")
        content.append(self.exe_label)

        section = Gtk.Label(label="Línea de comandos", xalign=0)
        add_class(section, "heading")
        content.append(section)
        self.cmdline_label = Gtk.Label(label="—", xalign=0)
        self.cmdline_label.set_selectable(True)
        self.cmdline_label.set_wrap(True)
        self.cmdline_label.set_lines(4)
        self.cmdline_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.cmdline_label.add_css_class("monospace")
        self.cmdline_label.add_css_class("caption")
        content.append(self.cmdline_label)

        footer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        footer.set_margin_top(8)
        footer.set_margin_bottom(12)
        footer.set_margin_start(16)
        footer.set_margin_end(16)
        footer.append(Gtk.Separator())
        self.end_button = Gtk.Button(label="Finalizar tarea")
        self.end_button.add_css_class("destructive-action")
        self.end_button.set_action_name("proc.end")
        footer.append(self.end_button)
        self.suspend_button = Gtk.Button(label="Suspender")
        self.suspend_button.set_action_name("proc.suspend")
        footer.append(self.suspend_button)
        self.properties_button = Gtk.Button(label="Propiedades")
        self.properties_button.set_action_name("proc.properties")
        footer.append(self.properties_button)

        detail_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        detail_box.append(scrolled)
        detail_box.append(footer)
        self.stack.add_named(detail_box, "content")
        self.stack.set_visible_child_name("empty")

    def update_info(self, info: ProcessInfo | None) -> None:
        if info is None:
            self.stack.set_visible_child_name("empty")
            return
        self.stack.set_visible_child_name("content")
        self.name_label.set_text(info.name)
        self.icon.set_from_icon_name(info.icon)
        self.kind_label.set_text(info.kind_text)
        self.fields["pid"].set_text(str(info.pid))
        self.fields["ppid"].set_text(str(info.ppid))
        self.fields["user"].set_text(info.username)
        self.fields["status"].set_text(info.status_text)
        self.fields["cpu"].set_text(format_percent(info.cpu_percent))
        self.fields["memory"].set_text(
            f"{format_bytes(info.memory_rss)} ({format_percent(info.memory_percent)})"
        )
        self.fields["disk"].set_text(
            format_rate(info.io_read_bps + info.io_write_bps)
        )
        self.fields["priority"].set_text(f"{info.priority_text} ({info.nice})")
        self.fields["threads"].set_text(str(info.num_threads))
        self.fields["start"].set_text(format_datetime(info.create_time))
        self.exe_label.set_text(info.exe or "No disponible")
        self.exe_label.set_tooltip_text(info.exe or "")
        self.cmdline_label.set_text(info.cmdline or "No disponible")
        self.cmdline_label.set_tooltip_text(info.cmdline or "")
        if info.status == "stopped":
            self.suspend_button.set_label("Reanudar")
            self.suspend_button.set_action_name("proc.resume")
        else:
            self.suspend_button.set_label("Suspender")
            self.suspend_button.set_action_name("proc.suspend")


class ProcessTablePage(Gtk.Box):
    def __init__(
        self,
        window,
        mode: str = "processes",
        show_details_panel: bool = True,
    ) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.mode = mode
        self.show_details_panel = show_details_panel
        self._infos: list[ProcessInfo] = []
        self._by_pid: dict[int, ProcessInfo] = {}
        self._selected_pid: int | None = None
        self._popover: Gtk.Popover | None = None
        self._actions: dict[str, Gio.SimpleAction] = {}
        self._details_revealer: Gtk.Revealer | None = None
        self._details_panel: ProcessDetailsPanel | None = None
        self._details_toggle: Gtk.ToggleButton | None = None
        self._updating = False

        self.store = Gtk.ListStore(*ROW_TYPES)
        self.filter_model = Gtk.TreeModelFilter(child_model=self.store)
        self.filter_model.set_visible_func(self._visible_func)
        self.sort_model = Gtk.TreeModelSort(model=self.filter_model)

        self._build_actions()
        self._build_ui()
        self._build_columns()
        if mode == "details":
            self.sort_model.set_sort_column_id(COL_NAME_LOWER, Gtk.SortType.ASCENDING)
        else:
            self.sort_model.set_sort_column_id(COL_CPU, Gtk.SortType.DESCENDING)
        self._update_action_sensitivity()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        toolbar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        toolbar.set_margin_top(12)
        toolbar.set_margin_bottom(8)
        toolbar.set_margin_start(12)
        toolbar.set_margin_end(12)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Buscar por nombre, PID o usuario…")
        self.search.set_size_request(300, -1)
        self.search.connect("search-changed", self._on_search_changed)
        toolbar.append(self.search)
        key_controller = Gtk.EventControllerKey()
        key_controller.connect("key-pressed", self._on_search_key)
        self.search.add_controller(key_controller)

        labels = ["Todos", "Aplicaciones", "Segundo plano", "Sistema"]
        self.kind_dropdown = Gtk.DropDown.new_from_strings(labels)
        self.kind_dropdown.set_tooltip_text("Filtrar por tipo de proceso")
        self.kind_dropdown.connect("notify::selected", self._on_kind_changed)
        toolbar.append(self.kind_dropdown)

        self.count_label = Gtk.Label(label="Cargando…", xalign=0)
        self.count_label.add_css_class("dim-label")
        self.count_label.set_hexpand(True)
        self.count_label.set_margin_start(6)
        toolbar.append(self.count_label)

        self.end_toolbar_button = Gtk.Button(label="Finalizar tarea")
        self.end_toolbar_button.add_css_class("destructive-action")
        self.end_toolbar_button.set_action_name("proc.end")
        toolbar.append(self.end_toolbar_button)

        self.menu_button = Gtk.MenuButton()
        self.menu_button.set_icon_name("open-menu-symbolic")
        self.menu_button.set_tooltip_text("Más acciones")
        self.menu_model = self._build_menu_model()
        self.menu_button.set_menu_model(self.menu_model)
        toolbar.append(self.menu_button)

        if self.show_details_panel:
            self._details_toggle = Gtk.ToggleButton()
            self._details_toggle.set_icon_name("sidebar-show-symbolic")
            self._details_toggle.set_active(True)
            self._details_toggle.set_tooltip_text("Mostrar u ocultar el panel de detalles")
            self._details_toggle.connect("toggled", self._on_toggle_details)
            toolbar.append(self._details_toggle)

        self.append(toolbar)

        body = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        body.set_vexpand(True)
        body.set_margin_start(12)
        body.set_margin_end(12)
        body.set_margin_bottom(12)
        self.append(body)

        table_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        table_box.set_hexpand(True)
        table_box.set_vexpand(True)
        add_class(table_box, "table-card")

        self.tree = Gtk.TreeView(model=self.sort_model)
        self.tree.set_headers_visible(True)
        self.tree.set_enable_search(False)
        self.tree.set_grid_lines(Gtk.TreeViewGridLines.HORIZONTAL)
        self.tree.set_tooltip_column(COL_TOOLTIP)
        add_class(self.tree, "process-tree")
        self.tree.get_selection().set_mode(Gtk.SelectionMode.SINGLE)
        self.tree.get_selection().connect("changed", self._on_selection_changed)
        self.tree.connect("row-activated", self._on_row_activated)

        self.empty_label = Gtk.Label(
            label="No hay procesos que coincidan con el filtro.",
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
        table_box.append(overlay)

        click = Gtk.GestureClick()
        click.set_button(3)
        click.connect("pressed", self._on_right_click)
        self.tree.add_controller(click)

        body.append(table_box)

        if self.show_details_panel:
            self._details_panel = ProcessDetailsPanel(self)
            self._details_revealer = Gtk.Revealer()
            self._details_revealer.set_transition_type(
                Gtk.RevealerTransitionType.SLIDE_LEFT
            )
            self._details_revealer.set_transition_duration(180)
            self._details_revealer.set_child(self._details_panel)
            self._details_revealer.set_hexpand(False)
            self._details_revealer.set_hexpand_set(True)
            self._details_revealer.set_reveal_child(True)
            body.append(self._details_revealer)

    def _build_columns(self) -> None:
        name_renderer = Gtk.CellRendererPixbuf()
        name_text = Gtk.CellRendererText()
        name_text.set_property("ellipsize", Pango.EllipsizeMode.END)
        name_col = Gtk.TreeViewColumn(title="Nombre")
        name_col.pack_start(name_renderer, False)
        name_col.add_attribute(name_renderer, "icon-name", COL_ICON)
        name_col.pack_start(name_text, True)
        name_col.add_attribute(name_text, "text", COL_NAME)
        name_col.set_sort_column_id(COL_NAME_LOWER)
        name_col.set_min_width(200)
        name_col.set_expand(True)
        name_col.set_resizable(True)
        self.tree.append_column(name_col)

        if self.mode == "details":
            self.tree.append_column(
                self._text_column("PID", COL_PID, COL_PID, 70)
            )
            self.tree.append_column(
                self._text_column("PPID", COL_PPID, COL_PPID, 70)
            )

        status_col = self._text_column("Estado", COL_STATUS, COL_STATUS, 110)
        status_col.set_cell_data_func(
            status_col.get_cells()[0], self._style_status
        )
        self.tree.append_column(status_col)

        cpu_col = self._text_column("CPU", COL_CPU_TEXT, COL_CPU, 86)
        cpu_col.set_cell_data_func(cpu_col.get_cells()[0], self._style_cpu)
        self.tree.append_column(cpu_col)
        self.cpu_column = cpu_col

        self.tree.append_column(
            self._text_column("Memoria", COL_MEM_TEXT, COL_MEM, 100)
        )
        self.tree.append_column(
            self._text_column("Disco", COL_DISK_TEXT, COL_DISK, 100)
        )
        self.tree.append_column(
            self._text_column("Usuario", COL_USER, COL_USER, 110)
        )

        if self.mode == "details":
            self.tree.append_column(
                self._text_column("Subprocesos", COL_THREADS, COL_THREADS, 95)
            )
            self.tree.append_column(
                self._text_column("Prioridad", COL_PRIORITY, COL_PRIORITY, 100)
            )
            self.tree.append_column(
                self._text_column("Tipo", COL_KIND_TEXT, COL_KIND_TEXT, 160)
            )
            self.tree.append_column(
                self._text_column("Inicio", COL_START, COL_START_RAW, 140)
            )
            cmdline_col = self._text_column(
                "Línea de comandos", COL_CMDLINE, COL_CMDLINE, 260
            )
            self.tree.append_column(cmdline_col)
        else:
            self.tree.append_column(
                self._text_column("PID", COL_PID, COL_PID, 74)
            )

    def _text_column(
        self,
        title: str,
        text_column: int,
        sort_column: int,
        width: int,
    ) -> Gtk.TreeViewColumn:
        renderer = Gtk.CellRendererText()
        renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        column = Gtk.TreeViewColumn(title=title)
        column.pack_start(renderer, True)
        column.add_attribute(renderer, "text", text_column)
        column.set_sort_column_id(sort_column)
        column.set_min_width(width)
        column.set_fixed_width(width)
        column.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        column.set_resizable(True)
        return column

    def _style_cpu(self, _column, cell, model, tree_iter, _data) -> None:
        value = model.get_value(tree_iter, COL_CPU)
        if value >= 80:
            cell.set_property("foreground", "#e01b24")
        elif value >= 40:
            cell.set_property("foreground", "#e66100")
        else:
            cell.set_property("foreground", None)

    def _style_status(self, _column, cell, model, tree_iter, _data) -> None:
        value = model.get_value(tree_iter, COL_STATUS)
        if value == "Zombi":
            cell.set_property("foreground", "#e01b24")
        elif value == "Suspendido":
            cell.set_property("foreground", "#e66100")
        else:
            cell.set_property("foreground", None)

    # ------------------------------------------------------------- actions
    def _build_actions(self) -> None:
        group = Gio.SimpleActionGroup()
        action_names = [
            "end",
            "force-end",
            "end-tree",
            "suspend",
            "resume",
            "properties",
            "location",
            "copy",
            "priority-15",
            "priority-5",
            "priority-0",
            "priority-5b",
            "priority-15b",
        ]
        callbacks = {
            "end": lambda: self._confirm_end(force=False, tree=False),
            "force-end": lambda: self._confirm_end(force=True, tree=False),
            "end-tree": lambda: self._confirm_end(force=False, tree=True),
            "suspend": self._suspend_selected,
            "resume": self._resume_selected,
            "properties": self._show_properties_selected,
            "location": self._open_location_selected,
            "copy": self._copy_selected,
            "priority-15": lambda: self._set_priority(-15),
            "priority-5": lambda: self._set_priority(-5),
            "priority-0": lambda: self._set_priority(0),
            "priority-5b": lambda: self._set_priority(5),
            "priority-15b": lambda: self._set_priority(15),
        }
        for name in action_names:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda _a, _p, cb=callbacks[name]: cb())
            group.add_action(action)
            self._actions[name] = action
        self.insert_action_group("proc", group)

        page_group = Gio.SimpleActionGroup()
        find_action = Gio.SimpleAction.new("find", None)
        find_action.connect("activate", lambda *_: self.focus_search())
        page_group.add_action(find_action)
        self.insert_action_group("page", page_group)

    def _build_menu_model(self) -> Gio.Menu:
        menu = Gio.Menu()
        first = Gio.Menu()
        first.append("Finalizar tarea", "proc.end")
        first.append("Forzar finalización", "proc.force-end")
        first.append("Finalizar árbol de procesos", "proc.end-tree")
        menu.append_section(None, first)

        second = Gio.Menu()
        second.append("Suspender", "proc.suspend")
        second.append("Reanudar", "proc.resume")
        priority = Gio.Menu()
        for label, value in PRIORITY_OPTIONS:
            action = {
                -15: "proc.priority-15",
                -5: "proc.priority-5",
                0: "proc.priority-0",
                5: "proc.priority-5b",
                15: "proc.priority-15b",
            }[value]
            item = Gio.MenuItem.new(label, action)
            priority.append_item(item)
        second.append_submenu("Prioridad", priority)
        menu.append_section(None, second)

        third = Gio.Menu()
        third.append("Abrir ubicación del ejecutable", "proc.location")
        third.append("Copiar detalles", "proc.copy")
        third.append("Propiedades", "proc.properties")
        menu.append_section(None, third)
        return menu

    def _update_action_sensitivity(self) -> None:
        info = self._selected_info()
        has_selection = info is not None
        suspended = info is not None and info.status == "stopped"
        for key in ("end", "force-end", "end-tree", "properties", "copy"):
            self._actions[key].set_enabled(has_selection)
        self._actions["suspend"].set_enabled(has_selection and not suspended)
        self._actions["resume"].set_enabled(has_selection and suspended)
        self._actions["location"].set_enabled(bool(info and info.exe))
        for key in (
            "priority-15",
            "priority-5",
            "priority-0",
            "priority-5b",
            "priority-15b",
        ):
            self._actions[key].set_enabled(has_selection)

    def _selected_info(self) -> ProcessInfo | None:
        if self._selected_pid is None:
            return None
        return self._by_pid.get(self._selected_pid)

    # ------------------------------------------------------------ filtering
    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        self.filter_model.refilter()
        self._update_count()

    def _on_search_key(self, _controller, keyval, _keycode, state) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.search.set_text("")
            return True
        return False

    def _on_kind_changed(self, dropdown: Gtk.DropDown, _param) -> None:
        self.filter_model.refilter()
        self._update_count()

    def _visible_func(self, model, tree_iter, _data) -> bool:
        selected = self.kind_dropdown.get_selected()
        kind_filter = KIND_FILTERS[selected] if 0 <= selected < len(KIND_FILTERS) else "all"
        if kind_filter != "all":
            kind = model.get_value(tree_iter, COL_KIND)
            if kind_filter == "system":
                if kind not in ("system", "service"):
                    return False
            elif kind != kind_filter:
                return False

        query = self.search.get_text().strip().casefold()
        if not query:
            return True
        name = model.get_value(tree_iter, COL_NAME)
        pid = model.get_value(tree_iter, COL_PID)
        user = model.get_value(tree_iter, COL_USER)
        cmdline = model.get_value(tree_iter, COL_CMDLINE)
        haystack = f"{name} {pid} {user} {cmdline}".casefold()
        return all(term in haystack for term in query.split())

    def _update_count(self) -> None:
        visible = self.filter_model.iter_n_children(None)
        total = len(self._infos)
        if visible == 0 and total == 0:
            self.count_label.set_text("Cargando procesos…")
            self.empty_label.set_visible(False)
            return
        if visible == total:
            self.count_label.set_text(f"{total} procesos")
        else:
            self.count_label.set_text(f"{visible} de {total} procesos")
        self.empty_label.set_visible(visible == 0)
        self.empty_label.set_text(
            "No hay procesos que coincidan con el filtro."
            if total
            else "Esperando datos del sistema…"
        )

    # ------------------------------------------------------------- updates
    def update(self, processes: list[ProcessInfo]) -> None:
        self._infos = processes
        self._by_pid = {process.pid: process for process in processes}
        current = set(self._by_pid)
        removal_paths: list[Gtk.TreePath] = []
        existing: set[int] = set()

        self._updating = True
        try:
            tree_iter = self.store.get_iter_first()
            while tree_iter is not None:
                pid = self.store.get_value(tree_iter, COL_PID)
                process = self._by_pid.get(pid)
                if process is None:
                    removal_paths.append(self.store.get_path(tree_iter))
                else:
                    existing.add(pid)
                    self._set_row(tree_iter, process)
                tree_iter = self.store.iter_next(tree_iter)

            for path in reversed(removal_paths):
                iter_to_remove = self.store.get_iter(path)
                if iter_to_remove is not None:
                    self.store.remove(iter_to_remove)

            for process in processes:
                if process.pid not in existing:
                    self.store.append(self._row_values(process))

            if self._selected_pid is not None and self._selected_pid not in current:
                self._selected_pid = None
            if self._selected_pid is not None:
                self._restore_selection(self._selected_pid)
        finally:
            self._updating = False

        self._refresh_details()
        self._update_action_sensitivity()
        self._update_count()

    def _restore_selection(self, pid: int) -> None:
        selection = self.tree.get_selection()
        model, tree_iter = selection.get_selected()
        if tree_iter is not None and model.get_value(tree_iter, COL_PID) == pid:
            return
        tree_iter = self.sort_model.get_iter_first()
        while tree_iter is not None:
            if self.sort_model.get_value(tree_iter, COL_PID) == pid:
                selection.select_iter(tree_iter)
                return
            tree_iter = self.sort_model.iter_next(tree_iter)

    def _row_values(self, process: ProcessInfo) -> list:
        disk = process.io_read_bps + process.io_write_bps
        tooltip = (
            f"{process.name}\nPID {process.pid} · {process.username}\n"
            f"{process.cmdline[:500]}"
        )
        return [
            process.pid,
            process.ppid,
            process.name,
            process.name.casefold(),
            process.status_text,
            process.cpu_percent,
            format_percent(process.cpu_percent),
            process.memory_rss,
            format_bytes(process.memory_rss),
            disk,
            format_rate(disk),
            process.username,
            process.kind,
            process.kind_text,
            process.icon,
            process.num_threads,
            f"{process.priority_text} ({process.nice})",
            format_time(process.create_time),
            process.exe or "",
            process.cmdline,
            tooltip,
            process.memory_percent,
            process.create_time,
        ]

    def _set_row(self, tree_iter: Gtk.TreeIter, process: ProcessInfo) -> None:
        values = self._row_values(process)
        arguments: list = []
        for column, value in enumerate(values):
            arguments.extend((column, value))
        self.store.set(tree_iter, *arguments)

    def _refresh_details(self) -> None:
        if self._details_panel is None:
            return
        self._details_panel.update_info(self._selected_info())

    # ----------------------------------------------------------- selection
    def _on_selection_changed(self, selection: Gtk.TreeSelection) -> None:
        if self._updating:
            return
        model, tree_iter = selection.get_selected()
        if tree_iter is None:
            self._selected_pid = None
        else:
            self._selected_pid = model.get_value(tree_iter, COL_PID)
        self._refresh_details()
        self._update_action_sensitivity()

    def _on_row_activated(self, _tree, _path, _column) -> None:
        self._show_properties_selected()

    def focus_search(self) -> None:
        self.search.grab_focus()

    def _on_toggle_details(self, button: Gtk.ToggleButton) -> None:
        if self._details_revealer is not None:
            self._details_revealer.set_reveal_child(button.get_active())

    # -------------------------------------------------------------- actions
    def _confirm_end(self, force: bool, tree: bool) -> None:
        info = self._selected_info()
        if info is None:
            return
        critical = actions.is_critical(info.pid)
        if tree:
            try:
                children = len(actions.process_tree(info.pid)) - 1
            except actions.ProcessActionError:
                children = 0
            heading = "Finalizar árbol de procesos"
            action_label = "Finalizar árbol"
            body = (
                f"Se solicitará finalizar «{info.name}» (PID {info.pid}) y "
                f"{children} proceso(s) hijo(s).\n\n"
                "Se enviará una señal de cierre ordenado."
            )
        elif force:
            heading = "Forzar finalización"
            action_label = "Forzar finalización"
            body = (
                f"«{info.name}» (PID {info.pid}) se cerrará inmediatamente.\n\n"
                "Esta acción no permite guardar cambios y puede provocar pérdida de datos."
            )
        else:
            heading = "Finalizar tarea"
            action_label = "Finalizar tarea"
            body = (
                f"Se solicitará cerrar «{info.name}» (PID {info.pid}).\n\n"
                "Si la aplicación no responde, puedes usar «Forzar finalización»."
            )
        if critical:
            body += (
                "\n\nAdvertencia: este proceso parece ser esencial para el sistema. "
                "Finalizarlo podría cerrar la sesión o dejar el equipo inestable."
            )

        def _perform() -> None:
            self._perform_end(info, force=force, tree=tree)

        if self.window.settings.get("confirm_end_task"):
            confirm_action(
                self.window,
                heading,
                body,
                action_label,
                _perform,
                destructive=True,
            )
        else:
            _perform()

    def _perform_end(self, info: ProcessInfo, force: bool, tree: bool) -> None:
        try:
            if tree:
                actions.end_process_tree(info.pid, force=force)
            else:
                actions.end_process(info.pid, force=force)
        except PermissionError:
            if tree:
                try:
                    pids = [item.pid for item in actions.process_tree(info.pid)]
                except actions.ProcessActionError:
                    pids = [info.pid]
                command = actions.admin_tree_command(pids, force)
            else:
                command = actions.admin_end_command(info.pid, force)
            self._offer_admin(
                "No se pudo finalizar el proceso porque pertenece a otro usuario "
                "o requiere privilegios elevados.",
                command,
                f"Se solicitó finalizar «{info.name}» con permisos de administrador.",
            )
            return
        except actions.ProcessActionError as error:
            show_message(self.window, "No se pudo finalizar", str(error))
            return
        except OSError as error:
            show_message(self.window, "No se pudo finalizar", str(error))
            return
        self.window.show_toast(f"Se solicitó finalizar «{info.name}».")
        GLib.timeout_add(400, self.window.request_refresh)

    def _suspend_selected(self) -> None:
        info = self._selected_info()
        if info is None:
            return

        def _perform() -> None:
            try:
                actions.suspend_process(info.pid)
            except PermissionError:
                self._offer_admin(
                    "No se pudo suspender el proceso por falta de permisos.",
                    actions.admin_suspend_command(info.pid),
                    f"Se suspendió «{info.name}» con permisos de administrador.",
                )
                return
            except actions.ProcessActionError as error:
                show_message(self.window, "No se pudo suspender", str(error))
                return
            self.window.show_toast(f"Se suspendió «{info.name}».")
            GLib.timeout_add(400, self.window.request_refresh)

        if actions.is_critical(info.pid):
            confirm_action(
                self.window,
                "Suspender proceso esencial",
                f"«{info.name}» parece ser un proceso esencial del sistema. "
                "Suspenderlo puede congelar la interfaz. ¿Continuar?",
                "Suspender",
                _perform,
            )
        else:
            _perform()

    def _resume_selected(self) -> None:
        info = self._selected_info()
        if info is None:
            return
        try:
            actions.resume_process(info.pid)
        except PermissionError:
            self._offer_admin(
                "No se pudo reanudar el proceso por falta de permisos.",
                actions.admin_suspend_command(info.pid, resume=True),
                f"Se reanudó «{info.name}» con permisos de administrador.",
            )
            return
        except actions.ProcessActionError as error:
            show_message(self.window, "No se pudo reanudar", str(error))
            return
        self.window.show_toast(f"Se reanudó «{info.name}».")
        GLib.timeout_add(400, self.window.request_refresh)

    def _set_priority(self, nice: int) -> None:
        info = self._selected_info()
        if info is None:
            return
        if info.nice == nice:
            self.window.show_toast("El proceso ya tiene esa prioridad.")
            return
        try:
            actions.set_process_nice(info.pid, nice)
        except PermissionError:
            self._offer_admin(
                "Cambiar a una prioridad alta requiere permisos de administrador.",
                actions.admin_nice_command(info.pid, nice),
                f"Se cambió la prioridad de «{info.name}».",
            )
            return
        except actions.ProcessActionError as error:
            show_message(self.window, "No se pudo cambiar la prioridad", str(error))
            return
        self.window.show_toast(f"Prioridad de «{info.name}» actualizada.")
        GLib.timeout_add(400, self.window.request_refresh)

    def _open_location_selected(self) -> None:
        info = self._selected_info()
        if info is None:
            return
        if not actions.open_executable_location(info.exe):
            show_message(
                self.window,
                "Ubicación no disponible",
                "No se pudo encontrar la carpeta del ejecutable de este proceso.",
            )

    def _copy_selected(self) -> None:
        info = self._selected_info()
        if info is None:
            return
        text = "\n".join(
            [
                f"Nombre: {info.name}",
                f"PID: {info.pid}",
                f"Proceso padre: {info.ppid}",
                f"Usuario: {info.username}",
                f"Estado: {info.status_text}",
                f"CPU: {format_percent(info.cpu_percent)}",
                f"Memoria: {format_bytes(info.memory_rss)}",
                f"Disco: {format_rate(info.io_read_bps + info.io_write_bps)}",
                f"Prioridad: {info.priority_text} ({info.nice})",
                f"Subprocesos: {info.num_threads}",
                f"Inicio: {format_datetime(info.create_time)}",
                f"Ejecutable: {info.exe or 'No disponible'}",
                f"Línea de comandos: {info.cmdline}",
            ]
        )
        copy_text(self, text)
        self.window.show_toast("Detalles copiados al portapapeles.")

    def _show_properties_selected(self) -> None:
        info = self._selected_info()
        if info is None:
            return

        def _loaded(details, error) -> None:
            if error is not None:
                show_message(
                    self.window,
                    "Propiedades no disponibles",
                    str(error),
                )
                return
            self._present_properties(details)

        self.window.run_async(
            lambda: actions.get_process_details(info.pid),
            _loaded,
        )

    def _present_properties(self, details: actions.ProcessDetails) -> None:
        win = Adw.Window()
        win.set_transient_for(self.window)
        win.set_modal(True)
        win.set_title(f"Propiedades de {details.name}")
        win.set_default_size(620, 560)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar()
        header.set_title_widget(
            Adw.WindowTitle(
                title=details.name,
                subtitle=f"PID {details.pid}",
            )
        )
        toolbar.add_top_bar(header)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(20)
        content.set_margin_bottom(20)
        content.set_margin_start(22)
        content.set_margin_end(22)
        scrolled.set_child(content)

        grid = Gtk.Grid()
        grid.set_column_spacing(18)
        grid.set_row_spacing(9)
        content.append(grid)
        rows = [
            ("Nombre", details.name),
            ("PID", str(details.pid)),
            ("Proceso padre", str(details.parent)),
            ("Usuario", details.username),
            ("Estado", details.status),
            ("Prioridad", details.priority),
            ("Subprocesos", str(details.threads)),
            ("Inicio", details.started or "—"),
            ("Memoria residente", format_bytes(details.memory_rss)),
            ("Tiempo de CPU acumulado", f"{details.cpu_time:.1f} s"),
            ("Archivos abiertos", str(details.open_files)),
            ("Conexiones de red", str(details.connections)),
        ]
        for row, (label_text, value_text) in enumerate(rows):
            label = Gtk.Label(label=label_text, xalign=0)
            label.add_css_class("dim-label")
            value = Gtk.Label(label=value_text, xalign=0)
            value.set_selectable(True)
            value.set_wrap(True)
            value.set_hexpand(True)
            grid.attach(label, 0, row, 1, 1)
            grid.attach(value, 1, row, 1, 1)

        for heading, text in (
            ("Ejecutable", details.exe or "No disponible"),
            ("Directorio de trabajo", details.cwd or "No disponible"),
            ("Línea de comandos", details.cmdline or "No disponible"),
        ):
            content.append(Gtk.Separator())
            title = Gtk.Label(label=heading, xalign=0)
            add_class(title, "heading")
            content.append(title)
            value = Gtk.Label(label=text, xalign=0)
            value.set_selectable(True)
            value.set_wrap(True)
            value.add_css_class("monospace")
            value.add_css_class("caption")
            content.append(value)

        if details.warnings:
            content.append(Gtk.Separator())
            warning = Gtk.Label(label="\n".join(details.warnings), xalign=0)
            warning.set_wrap(True)
            add_class(warning, "dim-label")
            content.append(warning)

        actions_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        actions_box.set_halign(Gtk.Align.END)
        if details.exe:
            location_button = Gtk.Button(label="Abrir ubicación")
            location_button.connect(
                "clicked",
                lambda *_: actions.open_executable_location(details.exe),
            )
            actions_box.append(location_button)
        copy_button = Gtk.Button(label="Copiar información")
        copy_button.connect("clicked", lambda *_: self._copy_properties(details))
        actions_box.append(copy_button)
        close_button = Gtk.Button(label="Cerrar")
        close_button.connect("clicked", lambda *_: win.close())
        actions_box.append(close_button)
        content.append(actions_box)

        toolbar.set_content(scrolled)
        win.set_content(toolbar)
        win.present()

    def _copy_properties(self, details: actions.ProcessDetails) -> None:
        text = "\n".join(
            [
                f"Nombre: {details.name}",
                f"PID: {details.pid}",
                f"Proceso padre: {details.parent}",
                f"Usuario: {details.username}",
                f"Estado: {details.status}",
                f"Prioridad: {details.priority}",
                f"Subprocesos: {details.threads}",
                f"Inicio: {details.started}",
                f"Memoria: {format_bytes(details.memory_rss)}",
                f"Tiempo de CPU: {details.cpu_time:.1f} s",
                f"Ejecutable: {details.exe}",
                f"Directorio: {details.cwd}",
                f"Comando: {details.cmdline}",
            ]
        )
        copy_text(self, text)
        self.window.show_toast("Información copiada al portapapeles.")

    def _offer_admin(self, body: str, command: list[str], success_message: str) -> None:
        def _run() -> None:
            def _finished(ok: bool, message: str) -> None:
                if ok:
                    self.window.show_toast(success_message)
                    GLib.timeout_add(400, self.window.request_refresh)
                else:
                    show_message(
                        self.window,
                        "No se pudo completar la operación",
                        message,
                    )

            self.window.run_command_async(command, _finished)

        confirm_action(
            self.window,
            "Permisos de administrador",
            body + "\n\n¿Quieres intentarlo con privilegios elevados?",
            "Usar privilegios",
            _run,
            destructive=False,
        )

    # ---------------------------------------------------------- context menu
    def _on_right_click(self, _gesture, _n_press, x: float, y: float) -> None:
        path = self._path_at(x, y)
        if path is None:
            return
        self.tree.get_selection().select_path(path)
        if self._popover is not None:
            self._popover.unparent()
            self._popover = None
        popover = Gtk.PopoverMenu.new_from_model(self.menu_model)
        popover.set_has_arrow(False)
        popover.set_parent(self.tree)
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        popover.set_pointing_to(rect)
        popover.connect("closed", self._on_popover_closed)
        self._popover = popover
        popover.popup()

    def _on_popover_closed(self, popover: Gtk.Popover) -> None:
        popover.unparent()
        if self._popover is popover:
            self._popover = None

    def _path_at(self, x: float, y: float) -> Gtk.TreePath | None:
        try:
            bin_x, bin_y = self.tree.convert_widget_to_bin_window_coords(
                int(x), int(y)
            )
        except (TypeError, AttributeError):
            bin_x, bin_y = int(x), int(y)
        try:
            result = self.tree.get_path_at_pos(bin_x, bin_y)
        except (TypeError, AttributeError):
            return None
        if not result:
            return None
        if isinstance(result, tuple):
            for item in result:
                if isinstance(item, Gtk.TreePath):
                    return item
            if len(result) > 1 and isinstance(result[1], Gtk.TreePath):
                return result[1]
            if isinstance(result[0], Gtk.TreePath):
                return result[0]
            return None
        return result


__all__ = ["ProcessTablePage"]
