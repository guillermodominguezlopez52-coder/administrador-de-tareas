"""Pestaña Rendimiento: CPU, memoria, disco y red."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Pango  # noqa: E402

from ...core.system import SystemSnapshot  # noqa: E402
from ..common import add_class, format_bytes, format_duration, format_percent, format_rate  # noqa: E402
from ..graph import CpuCoresWidget, SparkGraph  # noqa: E402


COLOR_CPU = "#3584e4"
COLOR_MEMORY = "#9141ac"
COLOR_DISK = "#e66100"
COLOR_DISK_READ = "#1c71d8"
COLOR_NET_DOWN = "#26a269"
COLOR_NET_UP = "#3584e4"


class PerformancePage(Gtk.Box):
    def __init__(self, window) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.window = window
        self.graphs: dict[str, SparkGraph] = {}
        self.graph_values: dict[str, Gtk.Label] = {}
        self.summary_values: dict[str, Gtk.Label] = {}
        self.summary_captions: dict[str, Gtk.Label] = {}
        self.stat_labels: dict[str, Gtk.Label] = {}
        self._last_snapshot: SystemSnapshot | None = None
        self._process_count = 0

        cards = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            homogeneous=True,
            spacing=12,
        )
        cards.set_margin_top(14)
        cards.set_margin_start(16)
        cards.set_margin_end(16)
        cards.append(
            self._summary_card(
                "cpu",
                "Procesador",
                "computer-chip-symbolic",
                COLOR_CPU,
            )
        )
        cards.append(
            self._summary_card(
                "memory",
                "Memoria",
                "memory-symbolic",
                COLOR_MEMORY,
            )
        )
        cards.append(
            self._summary_card(
                "disk",
                "Disco",
                "drive-harddisk-symbolic",
                COLOR_DISK,
            )
        )
        cards.append(
            self._summary_card(
                "network",
                "Red",
                "network-wired-symbolic",
                COLOR_NET_DOWN,
            )
        )
        self.append(cards)

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.set_transition_duration(120)
        self.stack.set_vexpand(True)

        self.switcher = Gtk.StackSwitcher(stack=self.stack)
        self.switcher.set_halign(Gtk.Align.START)
        self.switcher.set_margin_top(10)
        self.switcher.set_margin_start(16)
        self.switcher.set_margin_end(16)
        self.append(self.switcher)
        self.append(self.stack)

        self.stack.add_titled(self._build_summary(), "resumen", "Resumen")
        self.stack.add_titled(self._build_cpu(), "cpu", "CPU")
        self.stack.add_titled(self._build_memory(), "memory", "Memoria")
        self.stack.add_titled(self._build_disk(), "disk", "Disco")
        self.stack.add_titled(self._build_network(), "network", "Red")

    # -------------------------------------------------------------- helpers
    def _summary_card(
        self, key: str, title: str, icon_name: str, color: str
    ) -> Gtk.Widget:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        add_class(card, "stat-card")
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.set_pixel_size(18)
        icon.add_css_class("dim-label")
        header.append(icon)
        label = Gtk.Label(label=title, xalign=0)
        label.add_css_class("stat-label")
        header.append(label)
        card.append(header)
        value = Gtk.Label(label="—", xalign=0)
        add_class(value, "stat-value")
        card.append(value)
        caption = Gtk.Label(label="Esperando datos…", xalign=0)
        caption.set_ellipsize(Pango.EllipsizeMode.END)
        caption.add_css_class("stat-caption")
        card.append(caption)
        self.summary_values[key] = value
        self.summary_captions[key] = caption
        return card

    def _graph_card(
        self,
        key: str,
        title: str,
        color: str,
        *,
        height: int = 160,
        auto_scale: bool = False,
        min_scale: float = 1.0,
        formatter=format_percent,
    ) -> tuple[Gtk.Box, SparkGraph, Gtk.Label]:
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        add_class(card, "card")
        add_class(card, "graph-card")
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        title_label = Gtk.Label(label=title, xalign=0)
        add_class(title_label, "card-title")
        title_label.set_hexpand(True)
        header.append(title_label)
        value = Gtk.Label(label="—", xalign=1)
        add_class(value, "graph-value")
        header.append(value)
        card.append(header)
        graph = SparkGraph(
            color=color,
            max_value=100.0,
            auto_scale=auto_scale,
            min_scale=min_scale,
            height=height,
        )
        card.append(graph)
        self.graphs[key] = graph
        self.graph_values[key] = value
        return card, graph, value

    def _scroll(self, content: Gtk.Widget) -> Gtk.ScrolledWindow:
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_child(content)
        return scrolled

    def _page_content(self) -> Gtk.Box:
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
        content.set_margin_top(14)
        content.set_margin_bottom(18)
        content.set_margin_start(16)
        content.set_margin_end(16)
        return content

    def _make_stats(self, pairs: list[tuple[str, str]]) -> Gtk.Grid:
        grid = Gtk.Grid()
        grid.set_column_spacing(18)
        grid.set_row_spacing(9)
        grid.set_hexpand(True)
        for index, (label_text, key) in enumerate(pairs):
            row = index // 2
            column = (index % 2) * 2
            label = Gtk.Label(label=label_text, xalign=0)
            label.add_css_class("dim-label")
            value = Gtk.Label(label="—", xalign=0)
            value.set_selectable(True)
            value.set_wrap(True)
            value.set_hexpand(True)
            grid.attach(label, column, row, 1, 1)
            grid.attach(value, column + 1, row, 1, 1)
            self.stat_labels[key] = value
        grid.set_column_homogeneous(False)
        return grid

    def _section_title(self, text: str) -> Gtk.Label:
        label = Gtk.Label(label=text, xalign=0)
        add_class(label, "section-title")
        return label

    # --------------------------------------------------------------- pages
    def _build_summary(self) -> Gtk.Widget:
        content = self._page_content()
        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_row_spacing(12)
        grid.set_column_homogeneous(True)
        grid.set_row_homogeneous(True)
        cards = {
            "summary_cpu": ("CPU", COLOR_CPU, False, 1.0, format_percent),
            "summary_memory": ("Memoria", COLOR_MEMORY, False, 1.0, format_percent),
            "summary_disk": ("Disco", COLOR_DISK, True, 1024 * 1024, format_rate),
            "summary_network": (
                "Red",
                COLOR_NET_DOWN,
                True,
                64 * 1024,
                format_rate,
            ),
        }
        for index, (key, (title, color, auto, minimum, formatter)) in enumerate(
            cards.items()
        ):
            card, _graph, _value = self._graph_card(
                key,
                title,
                color,
                height=110,
                auto_scale=auto,
                min_scale=minimum,
                formatter=formatter,
            )
            grid.attach(card, index % 2, index // 2, 1, 1)
        content.append(grid)
        content.append(self._section_title("Información del sistema"))
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        add_class(info, "card")
        info.set_margin_top(2)
        info.append(
            self._make_stats(
                [
                    ("Tiempo de actividad", "sum_uptime"),
                    ("Procesos", "sum_processes"),
                    ("Temperatura de la CPU", "sum_temp"),
                    ("Carga media (1 / 5 / 15 min)", "sum_load"),
                ]
            )
        )
        content.append(info)
        return self._scroll(content)

    def _build_cpu(self) -> Gtk.Widget:
        content = self._page_content()
        card, _graph, value = self._graph_card(
            "cpu",
            "Utilización de la CPU",
            COLOR_CPU,
            height=200,
        )
        self.stat_labels["cpu_graph_value"] = value
        content.append(card)
        stats_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        add_class(stats_box, "card")
        stats_box.append(
            self._make_stats(
                [
                    ("Utilización", "cpu_util"),
                    ("Velocidad", "cpu_speed"),
                    ("Núcleos lógicos", "cpu_cores"),
                    ("Procesos", "cpu_processes"),
                    ("Temperatura", "cpu_temp"),
                    ("Tiempo de actividad", "cpu_uptime"),
                    ("Carga media (1 / 5 / 15 min)", "cpu_load"),
                ]
            )
        )
        content.append(stats_box)
        content.append(self._section_title("Núcleos lógicos"))
        self.cpu_cores = CpuCoresWidget()
        cores_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        add_class(cores_box, "card")
        cores_box.append(self.cpu_cores)
        content.append(cores_box)
        return self._scroll(content)

    def _build_memory(self) -> Gtk.Widget:
        content = self._page_content()
        card, _graph, value = self._graph_card(
            "memory",
            "Uso de memoria",
            COLOR_MEMORY,
            height=200,
        )
        self.stat_labels["memory_graph_value"] = value
        content.append(card)

        usage_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        add_class(usage_box, "card")
        title = Gtk.Label(label="Memoria física", xalign=0)
        add_class(title, "card-title")
        usage_box.append(title)
        self.memory_progress = Gtk.ProgressBar()
        self.memory_progress.set_show_text(True)
        usage_box.append(self.memory_progress)
        self.swap_progress = Gtk.ProgressBar()
        self.swap_progress.set_show_text(True)
        swap_label = Gtk.Label(label="Memoria de intercambio (swap)", xalign=0)
        add_class(swap_label, "dim-label")
        usage_box.append(swap_label)
        usage_box.append(self.swap_progress)
        content.append(usage_box)

        stats = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        add_class(stats, "card")
        stats.append(
            self._make_stats(
                [
                    ("En uso", "mem_used"),
                    ("Disponible", "mem_available"),
                    ("Total", "mem_total"),
                    ("En caché", "mem_cached"),
                    ("Swap en uso", "mem_swap_used"),
                    ("Swap total", "mem_swap_total"),
                ]
            )
        )
        content.append(stats)
        return self._scroll(content)

    def _build_disk(self) -> Gtk.Widget:
        content = self._page_content()
        read_card, _read_graph, read_value = self._graph_card(
            "disk_read",
            "Lectura del disco",
            COLOR_DISK_READ,
            height=150,
            auto_scale=True,
            min_scale=1024 * 1024,
            formatter=format_rate,
        )
        self.stat_labels["disk_read_graph"] = read_value
        content.append(read_card)
        write_card, _write_graph, write_value = self._graph_card(
            "disk_write",
            "Escritura del disco",
            COLOR_DISK,
            height=150,
            auto_scale=True,
            min_scale=1024 * 1024,
            formatter=format_rate,
        )
        self.stat_labels["disk_write_graph"] = write_value
        content.append(write_card)

        usage_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        add_class(usage_box, "card")
        title = Gtk.Label(label="Uso del disco del sistema (/)" , xalign=0)
        add_class(title, "card-title")
        usage_box.append(title)
        self.disk_progress = Gtk.ProgressBar()
        self.disk_progress.set_show_text(True)
        usage_box.append(self.disk_progress)
        content.append(usage_box)

        stats = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        add_class(stats, "card")
        stats.append(
            self._make_stats(
                [
                    ("Actividad total", "disk_activity"),
                    ("Velocidad de lectura", "disk_read"),
                    ("Velocidad de escritura", "disk_write"),
                    ("Uso", "disk_usage"),
                    ("Capacidad total", "disk_total"),
                    ("Espacio libre", "disk_free"),
                ]
            )
        )
        content.append(stats)
        return self._scroll(content)

    def _build_network(self) -> Gtk.Widget:
        content = self._page_content()
        down_card, _down_graph, down_value = self._graph_card(
            "net_down",
            "Descarga",
            COLOR_NET_DOWN,
            height=150,
            auto_scale=True,
            min_scale=64 * 1024,
            formatter=format_rate,
        )
        self.stat_labels["net_down_graph"] = down_value
        content.append(down_card)
        up_card, _up_graph, up_value = self._graph_card(
            "net_up",
            "Subida",
            COLOR_NET_UP,
            height=150,
            auto_scale=True,
            min_scale=64 * 1024,
            formatter=format_rate,
        )
        self.stat_labels["net_up_graph"] = up_value
        content.append(up_card)

        stats = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        add_class(stats, "card")
        stats.append(
            self._make_stats(
                [
                    ("Interfaz", "net_iface"),
                    ("Dirección IP", "net_ip"),
                    ("Dirección MAC", "net_mac"),
                    ("Velocidad del enlace", "net_speed"),
                    ("Descarga actual", "net_down"),
                    ("Subida actual", "net_up"),
                ]
            )
        )
        content.append(stats)
        return self._scroll(content)

    # --------------------------------------------------------------- update
    def update(self, snapshot: SystemSnapshot, process_count: int) -> None:
        self._last_snapshot = snapshot
        self._process_count = process_count
        s = snapshot

        self.graphs["cpu"].push(s.cpu_percent)
        self.graphs["memory"].push(s.mem_percent)
        self.graphs["disk_read"].push(s.disk_read_bps)
        self.graphs["disk_write"].push(s.disk_write_bps)
        self.graphs["net_down"].push(s.net_down_bps)
        self.graphs["net_up"].push(s.net_up_bps)
        self.graphs["summary_cpu"].push(s.cpu_percent)
        self.graphs["summary_memory"].push(s.mem_percent)
        self.graphs["summary_disk"].push(s.disk_read_bps + s.disk_write_bps)
        self.graphs["summary_network"].push(s.net_down_bps + s.net_up_bps)

        temp_text = f"{s.cpu_temp:.1f} °C" if s.cpu_temp is not None else "No disponible"
        speed_text = f"{s.cpu_freq_mhz:.0f} MHz" if s.cpu_freq_mhz else "No disponible"
        if s.cpu_freq_max:
            speed_text += f" (máx. {s.cpu_freq_max:.0f} MHz)"
        load_text = f"{s.load_avg[0]:.2f}  /  {s.load_avg[1]:.2f}  /  {s.load_avg[2]:.2f}"

        self.summary_values["cpu"].set_text(format_percent(s.cpu_percent, 0))
        self.summary_captions["cpu"].set_text(
            f"{s.cpu_count} núcleos · {temp_text}"
        )
        self.summary_values["memory"].set_text(format_percent(s.mem_percent, 0))
        self.summary_captions["memory"].set_text(
            f"{format_bytes(s.mem_used)} de {format_bytes(s.mem_total)}"
        )
        disk_total_rate = s.disk_read_bps + s.disk_write_bps
        self.summary_values["disk"].set_text(format_rate(disk_total_rate))
        self.summary_captions["disk"].set_text(
            f"Uso del disco: {format_percent(s.disk_percent, 0)}"
        )
        net_total_rate = s.net_down_bps + s.net_up_bps
        self.summary_values["network"].set_text(format_rate(net_total_rate))
        self.summary_captions["network"].set_text(
            f"{s.net_iface or 'Sin interfaz'} · {s.net_ip or 'Sin IP'}"
        )

        self.graph_values["summary_cpu"].set_text(
            format_percent(s.cpu_percent, 0)
        )
        self.graph_values["summary_memory"].set_text(
            format_percent(s.mem_percent, 0)
        )
        self.graph_values["summary_disk"].set_text(format_rate(disk_total_rate))
        self.graph_values["summary_network"].set_text(format_rate(net_total_rate))

        self.stat_labels["sum_uptime"].set_text(format_duration(s.uptime))
        self.stat_labels["sum_processes"].set_text(f"{process_count}")
        self.stat_labels["sum_temp"].set_text(temp_text)
        self.stat_labels["sum_load"].set_text(load_text)

        self.stat_labels["cpu_graph_value"].set_text(format_percent(s.cpu_percent))
        self.stat_labels["cpu_util"].set_text(format_percent(s.cpu_percent))
        self.stat_labels["cpu_speed"].set_text(speed_text)
        self.stat_labels["cpu_cores"].set_text(str(s.cpu_count))
        self.stat_labels["cpu_processes"].set_text(str(process_count))
        self.stat_labels["cpu_temp"].set_text(temp_text)
        self.stat_labels["cpu_uptime"].set_text(format_duration(s.uptime))
        self.stat_labels["cpu_load"].set_text(load_text)
        self.cpu_cores.update(s.per_cpu)

        self.stat_labels["memory_graph_value"].set_text(
            format_percent(s.mem_percent)
        )
        self.stat_labels["mem_used"].set_text(format_bytes(s.mem_used))
        self.stat_labels["mem_available"].set_text(format_bytes(s.mem_available))
        self.stat_labels["mem_total"].set_text(format_bytes(s.mem_total))
        self.stat_labels["mem_cached"].set_text(format_bytes(s.mem_cached))
        self.stat_labels["mem_swap_used"].set_text(format_bytes(s.swap_used))
        self.stat_labels["mem_swap_total"].set_text(format_bytes(s.swap_total))
        self.memory_progress.set_fraction(min(1.0, max(0.0, s.mem_percent / 100.0)))
        self.memory_progress.set_text(
            f"{format_percent(s.mem_percent)} — {format_bytes(s.mem_used)} de "
            f"{format_bytes(s.mem_total)}"
        )
        swap_fraction = (
            (s.swap_used / s.swap_total) if s.swap_total else 0.0
        )
        self.swap_progress.set_fraction(min(1.0, max(0.0, swap_fraction)))
        self.swap_progress.set_text(
            f"{format_bytes(s.swap_used)} de {format_bytes(s.swap_total)}"
        )

        self.stat_labels["disk_read_graph"].set_text(format_rate(s.disk_read_bps))
        self.stat_labels["disk_write_graph"].set_text(format_rate(s.disk_write_bps))
        self.stat_labels["disk_activity"].set_text(format_rate(disk_total_rate))
        self.stat_labels["disk_read"].set_text(format_rate(s.disk_read_bps))
        self.stat_labels["disk_write"].set_text(format_rate(s.disk_write_bps))
        self.stat_labels["disk_usage"].set_text(format_percent(s.disk_percent))
        self.stat_labels["disk_total"].set_text(format_bytes(s.disk_total))
        self.stat_labels["disk_free"].set_text(format_bytes(s.disk_free))
        self.disk_progress.set_fraction(
            min(1.0, max(0.0, s.disk_percent / 100.0))
        )
        self.disk_progress.set_text(
            f"{format_percent(s.disk_percent)} — {format_bytes(s.disk_used)} de "
            f"{format_bytes(s.disk_total)}"
        )

        self.stat_labels["net_down_graph"].set_text(format_rate(s.net_down_bps))
        self.stat_labels["net_up_graph"].set_text(format_rate(s.net_up_bps))
        self.stat_labels["net_iface"].set_text(s.net_iface or "No disponible")
        self.stat_labels["net_ip"].set_text(s.net_ip or "No disponible")
        self.stat_labels["net_mac"].set_text(s.net_mac or "No disponible")
        self.stat_labels["net_speed"].set_text(
            f"{s.net_speed} Mb/s" if s.net_speed else "No disponible"
        )
        self.stat_labels["net_down"].set_text(format_rate(s.net_down_bps))
        self.stat_labels["net_up"].set_text(format_rate(s.net_up_bps))


__all__ = ["PerformancePage"]
