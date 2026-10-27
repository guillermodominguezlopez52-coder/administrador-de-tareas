"""Gráficos ligeros dibujados con Gsk para la pestaña Rendimiento."""

from __future__ import annotations

from collections import deque

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gsk", "4.0")
gi.require_version("Graphene", "1.0")

from gi.repository import Gdk, Graphene, Gsk, Gtk, Pango  # noqa: E402

from .common import add_class, format_percent  # noqa: E402


def _color(value: str, alpha: float | None = None) -> Gdk.RGBA:
    color = Gdk.RGBA()
    color.parse(value)
    if alpha is not None:
        color.alpha = alpha
    return color


class SparkGraph(Gtk.Widget):
    def __init__(
        self,
        color: str = "#3584e4",
        max_value: float = 100.0,
        auto_scale: bool = False,
        min_scale: float = 1.0,
        height: int = 160,
        points: int = 60,
    ) -> None:
        super().__init__()
        self.color = color
        self.max_value = max_value
        self.auto_scale = auto_scale
        self.min_scale = min_scale
        self.height = height
        self.history: deque[float] = deque(maxlen=points)
        self.set_hexpand(True)
        self.set_valign(Gtk.Align.FILL)
        self.set_size_request(-1, height)
        add_class(self, "spark-graph")

    def do_measure(self, orientation, _for_size):
        if orientation == Gtk.Orientation.VERTICAL:
            return self.height, self.height, -1, -1
        return 0, 0, -1, -1

    def push(self, value: float) -> None:
        try:
            value = max(0.0, float(value))
        except (TypeError, ValueError):
            value = 0.0
        self.history.append(value)
        self.queue_draw()

    def set_history(self, values) -> None:
        self.history.clear()
        for value in values:
            self.history.append(max(0.0, float(value)))
        self.queue_draw()

    def clear(self) -> None:
        self.history.clear()
        self.queue_draw()

    def _scale(self) -> float:
        if not self.auto_scale:
            return max(self.max_value, 1.0)
        peak = max(self.history, default=0.0)
        return max(self.min_scale, peak * 1.15, 1.0)

    def do_snapshot(self, snapshot: Gtk.Snapshot) -> None:
        width = self.get_width()
        height = self.get_height()
        if width <= 1 or height <= 1:
            return

        grid = Gsk.PathBuilder.new()
        for index in range(1, 4):
            y = height * index / 4.0
            grid.move_to(0.0, y)
            grid.line_to(float(width), y)
        snapshot.append_stroke(
            grid.to_path(),
            Gsk.Stroke.new(1.0),
            _color("#8a8a8a", 0.18),
        )

        count = len(self.history)
        if count == 0:
            layout = self.create_pango_layout("Recopilando datos…")
            layout.set_font_description(Pango.FontDescription.from_string("Sans 12"))
            text_width, text_height = layout.get_pixel_size()
            point = Graphene.Point().init(
                (width - text_width) / 2.0,
                (height - text_height) / 2.0,
            )
            snapshot.save()
            snapshot.translate(point)
            snapshot.append_layout(layout, _color("#8a8a8a", 0.75))
            snapshot.restore()
            return

        scale = self._scale()
        points: list[tuple[float, float]] = []
        span = max(count - 1, 1)
        for index, value in enumerate(self.history):
            x = index / span * width
            y = height - min(value / scale, 1.0) * (height - 8) - 4
            points.append((x, y))

        if len(points) == 1:
            points.insert(0, (0.0, points[0][1]))

        fill = Gsk.PathBuilder.new()
        fill.move_to(points[0][0], float(height))
        for x, y in points:
            fill.line_to(x, y)
        fill.line_to(points[-1][0], float(height))
        fill.close()

        top = Gsk.ColorStop()
        top.offset = 0.0
        top.color = _color(self.color, 0.35)
        bottom = Gsk.ColorStop()
        bottom.offset = 1.0
        bottom.color = _color(self.color, 0.02)

        snapshot.push_fill(fill.to_path(), Gsk.FillRule.WINDING)
        snapshot.append_linear_gradient(
            Graphene.Rect().init(0, 0, float(width), float(height)),
            Graphene.Point().init(0, 0),
            Graphene.Point().init(0, float(height)),
            [top, bottom],
        )
        snapshot.pop()

        line = Gsk.PathBuilder.new()
        line.move_to(points[0][0], points[0][1])
        for x, y in points[1:]:
            line.line_to(x, y)
        stroke = Gsk.Stroke.new(2.0)
        stroke.set_line_join(Gsk.LineJoin.ROUND)
        stroke.set_line_cap(Gsk.LineCap.ROUND)
        snapshot.append_stroke(line.to_path(), stroke, _color(self.color, 0.95))

        dot = Gsk.PathBuilder.new()
        dot.add_circle(
            Graphene.Point().init(points[-1][0], points[-1][1]),
            2.6,
        )
        snapshot.append_fill(dot.to_path(), Gsk.FillRule.WINDING, _color(self.color))


class CpuCoresWidget(Gtk.Box):
    """Cuadrícula con una barra de progreso por núcleo lógico."""

    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self._bars: list[tuple[Gtk.Label, Gtk.ProgressBar]] = []
        self._flow = Gtk.FlowBox()
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_column_spacing(12)
        self._flow.set_row_spacing(10)
        self._flow.set_min_children_per_line(2)
        self._flow.set_max_children_per_line(8)
        self._flow.set_hexpand(True)
        self.append(self._flow)

    def _rebuild(self, count: int) -> None:
        while self._flow.get_first_child() is not None:
            self._flow.remove(self._flow.get_first_child())
        self._bars.clear()
        for index in range(count):
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            add_class(box, "core-card")
            label = Gtk.Label(label=f"Núcleo {index + 1}", xalign=0)
            add_class(label, "core-label")
            bar = Gtk.ProgressBar()
            bar.set_fraction(0.0)
            bar.set_show_text(True)
            bar.set_text("0 %")
            add_class(bar, "core-bar")
            box.append(label)
            box.append(bar)
            self._flow.append(box)
            self._bars.append((label, bar))

    def update(self, per_cpu: list[float]) -> None:
        if len(per_cpu) != len(self._bars):
            self._rebuild(len(per_cpu))
        for (_label, bar), value in zip(self._bars, per_cpu):
            value = max(0.0, min(100.0, float(value)))
            bar.set_fraction(value / 100.0)
            bar.set_text(format_percent(value, 0))
            if value >= 80:
                bar.add_css_class("core-high")
            else:
                bar.remove_css_class("core-high")


__all__ = ["CpuCoresWidget", "SparkGraph"]
