"""Pestaña Usuarios: sesiones activas y recursos que consumen."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk  # noqa: E402

from ...core.processes import ProcessInfo  # noqa: E402
from ...core.users import SessionInfo, list_sessions, terminate_session  # noqa: E402
from ..common import (  # noqa: E402
    add_class,
    confirm_action,
    format_bytes,
    format_datetime,
    format_percent,
    make_icon,
    show_message,
)


class UsersPage(Gtk.Box):
    def __init__(self, window) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self._sessions: list[SessionInfo] = []
        self._row_widgets: dict[str, dict[str, Gtk.Label]] = {}
        self._loading = False

        info = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        info.set_margin_top(12)
        info.set_margin_start(16)
        info.set_margin_end(16)
        add_class(info, "info-banner")
        info.append(make_icon("avatar-default-symbolic", 18))
        text = Gtk.Label(
            label=(
                "Sesiones de usuario abiertas en este equipo. Puedes cerrar "
                "sesiones que no sean la tuya si tienes permisos."
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

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_show_separators(True)
        add_class(self.listbox, "boxed-list")

        self.empty_label = Gtk.Label(
            label="No se encontraron sesiones de usuario.",
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            wrap=True,
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
        processes = list(self.window.last_processes)
        self.window.run_async(
            lambda: list_sessions(processes),
            self._on_loaded,
        )

    def _on_loaded(self, sessions, error) -> None:
        self._loading = False
        self.spinner.stop()
        if error is not None:
            show_message(
                self.window,
                "No se pudieron cargar las sesiones",
                str(error),
            )
            return
        self._sessions = sessions
        self._rebuild()

    def _rebuild(self) -> None:
        child = self.listbox.get_first_child()
        while child is not None:
            self.listbox.remove(child)
            child = self.listbox.get_first_child()
        self._row_widgets.clear()
        for session in self._sessions:
            self.listbox.append(self._make_row(session))
        self.empty_label.set_visible(not self._sessions)

    def _make_row(self, session: SessionInfo) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()
        add_class(row, "user-row")
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        box.set_margin_top(10)
        box.set_margin_bottom(10)
        box.set_margin_start(12)
        box.set_margin_end(12)

        avatar = Gtk.Label(label=(session.username[:1] or "?").upper())
        avatar.set_size_request(38, 38)
        avatar.set_valign(Gtk.Align.CENTER)
        add_class(avatar, "avatar")

        text_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        text_box.set_hexpand(True)
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        name = Gtk.Label(label=session.username, xalign=0)
        add_class(name, "heading")
        name_box.append(name)
        if session.is_current:
            badge = Gtk.Label(label="Sesión actual")
            add_class(badge, "badge")
            add_class(badge, "badge-success")
            name_box.append(badge)
        if session.remote:
            badge = Gtk.Label(label="Remota")
            add_class(badge, "badge")
            badge.add_css_class("badge-warning")
            name_box.append(badge)
        text_box.append(name_box)
        details = Gtk.Label(
            label=(
                f"{session.type_text} · {session.tty or session.seat or 'Sin terminal'}"
                f" · Inicio: {format_datetime(session.started)}"
            ),
            xalign=0,
        )
        details.add_css_class("dim-label")
        text_box.append(details)
        usage = Gtk.Label(label="—", xalign=0)
        usage.add_css_class("dim-label")
        usage.add_css_class("caption")
        text_box.append(usage)

        button = Gtk.Button(label="Cerrar sesión")
        button.add_css_class("destructive-action")
        button.set_valign(Gtk.Align.CENTER)
        if session.is_current:
            button.set_sensitive(False)
            button.set_tooltip_text(
                "No puedes cerrar la sesión desde la que se ejecuta esta aplicación."
            )
        button.connect("clicked", lambda *_: self._confirm_terminate(session))

        box.append(avatar)
        box.append(text_box)
        box.append(button)
        row.set_child(box)
        self._row_widgets[session.session_id or session.username] = {
            "usage": usage,
            "details": details,
            "button": button,
        }
        self._update_row_usage(session)
        return row

    def _update_row_usage(self, session: SessionInfo) -> None:
        widgets = self._row_widgets.get(session.session_id or session.username)
        if not widgets:
            return
        widgets["usage"].set_text(
            f"CPU {format_percent(session.cpu_percent)} · "
            f"Memoria {format_bytes(session.memory_rss)} · "
            f"{session.process_count} procesos"
        )

    def update_usage(self, processes: list[ProcessInfo]) -> None:
        if not self._sessions:
            return
        by_uid: dict[int, list[ProcessInfo]] = {}
        by_user: dict[str, list[ProcessInfo]] = {}
        for process in processes:
            by_uid.setdefault(process.uid, []).append(process)
            by_user.setdefault(process.username, []).append(process)
        for session in self._sessions:
            items = by_uid.get(session.uid) or by_user.get(session.username) or []
            session.cpu_percent = round(sum(item.cpu_percent for item in items), 1)
            session.memory_rss = sum(item.memory_rss for item in items)
            session.process_count = len(items)
            self._update_row_usage(session)

    def _confirm_terminate(self, session: SessionInfo) -> None:
        if session.is_current:
            show_message(
                self.window,
                "Sesión actual",
                "No puedes cerrar la sesión desde la que se está ejecutando "
                "el administrador de tareas.",
            )
            return

        def _run() -> None:
            def _done(_result, error) -> None:
                if error is not None:
                    show_message(
                        self.window,
                        "No se pudo cerrar la sesión",
                        str(error),
                    )
                    return
                self.window.show_toast(f"Se cerró la sesión de {session.username}.")
                self.refresh_async()

            self.window.run_async(lambda: terminate_session(session), _done)

        confirm_action(
            self.window,
            "Cerrar sesión",
            f"Se cerrará la sesión de «{session.username}» "
            f"({session.type_text}, {session.tty or session.seat or 'sin terminal'}).\n\n"
            "Las aplicaciones abiertas en esa sesión podrían cerrarse sin guardar cambios.",
            "Cerrar sesión",
            _run,
        )


__all__ = ["UsersPage"]
