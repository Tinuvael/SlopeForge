"""Small dependency-free dashboard charts painted directly by Qt."""
from __future__ import annotations

from collections import defaultdict
from datetime import date

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from app.localization import tr
from .widgets import DashboardCard, quadrant_presentation


def _palette_color(widget: QWidget, role: QPalette.ColorRole) -> QColor:
    """Resolve semantic chart colours from the current application palette."""
    return widget.palette().color(QPalette.ColorGroup.Active, role)


class CompactChart(QWidget):
    """Native Qt horizontal bars or assessment-result donut."""

    def __init__(self, data, kind="bar", parent=None):
        super().__init__(parent)
        self.data = {
            str(key): int(value)
            for key, value in data.items()
            if value is not None and int(value) > 0
        }
        self.kind = kind
        self.setMinimumHeight(150 if kind == "donut" else 92)
        self.setMaximumHeight(190 if kind == "donut" else 150)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, data):
        self.data = {
            str(key): int(value)
            for key, value in data.items()
            if value is not None and int(value) > 0
        }
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if not self.data:
            painter.setPen(_palette_color(self, QPalette.ColorRole.PlaceholderText))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("No data yet"))
            return
        if self.kind == "donut":
            self._paint_donut(painter)
        else:
            self._paint_bars(painter)

    def _paint_bars(self, painter):
        metrics = QFontMetrics(painter.font())
        label_width = min(
            max(metrics.horizontalAdvance(label) for label in self.data) + 12,
            max(90, self.width() // 2),
        )
        row_height = max(20, min(30, max(1, (self.height() - 8) // len(self.data))))
        maximum = max(self.data.values())
        text = _palette_color(self, QPalette.ColorRole.Text)
        secondary = _palette_color(self, QPalette.ColorRole.WindowText)
        accent = _palette_color(self, QPalette.ColorRole.Link)
        for index, (label, value) in enumerate(self.data.items()):
            top = 4 + index * row_height
            painter.setPen(secondary)
            painter.drawText(
                QRectF(2, top, label_width - 8, row_height - 3),
                Qt.AlignmentFlag.AlignVCenter,
                metrics.elidedText(
                    label,
                    Qt.TextElideMode.ElideRight,
                    max(20, label_width - 10),
                ),
            )
            available = max(20, self.width() - label_width - 34)
            bar = QRectF(
                label_width,
                top + 5,
                max(2, available * value / maximum),
                max(5, row_height - 12),
            )
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(accent)
            painter.drawRoundedRect(bar, 3, 3)
            painter.setPen(text)
            painter.drawText(
                QRectF(bar.right() + 5, top, 28, row_height - 3),
                Qt.AlignmentFlag.AlignVCenter,
                str(value),
            )

    def _paint_donut(self, painter):
        size = max(108, min(self.height() - 12, self.width() * 0.32))
        ring = QRectF(8, (self.height() - size) / 2, size, size)
        total = sum(self.data.values())
        width = max(18, int(size * 0.18))
        arc_rect = ring.adjusted(width / 2, width / 2, -width / 2, -width / 2)

        shadow = QPen(_palette_color(self, QPalette.ColorRole.Mid))
        shadow.setWidth(width + 4)
        shadow.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(shadow)
        painter.drawArc(arc_rect, 0, 360 * 16)

        base = QPen(_palette_color(self, QPalette.ColorRole.AlternateBase))
        base.setWidth(width)
        base.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(base)
        painter.drawArc(arc_rect, 0, 360 * 16)

        start = 90 * 16
        pen = QPen()
        pen.setWidth(width)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        for key, value in self.data.items():
            pen.setColor(QColor(quadrant_presentation(key).color))
            painter.setPen(pen)
            span = -round(360 * 16 * value / total)
            painter.drawArc(arc_rect, start, span)
            start += span

        center_font = QFont(painter.font())
        center_font.setBold(True)
        center_font.setPointSize(max(13, min(18, int(size * 0.10))))
        painter.setFont(center_font)
        painter.setPen(_palette_color(self, QPalette.ColorRole.Text))
        painter.drawText(ring, Qt.AlignmentFlag.AlignCenter, str(total))

        legend_x = ring.right() + 16
        legend_width = max(40, self.width() - int(legend_x) - 8)
        row_height = max(30, (self.height() - 8) // max(1, len(self.data)))
        top = max(4, (self.height() - row_height * len(self.data)) // 2)
        legend_font = QFont(painter.font())
        legend_font.setPointSize(8)
        legend_font.setBold(False)
        painter.setFont(legend_font)
        text_flags = int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        text_flags |= int(Qt.TextFlag.TextWordWrap)
        marker_size = 14
        marker_gap = 8
        marker_border = _palette_color(self, QPalette.ColorRole.Mid)
        legend_text = _palette_color(self, QPalette.ColorRole.WindowText)
        for index, (key, value) in enumerate(self.data.items()):
            presentation = quadrant_presentation(key)
            y = top + index * row_height
            marker_y = y + (row_height - marker_size) / 2
            painter.setPen(QPen(marker_border, 1))
            painter.setBrush(QColor(presentation.color))
            painter.drawRoundedRect(
                QRectF(legend_x, marker_y, marker_size, marker_size),
                2,
                2,
            )
            painter.setPen(legend_text)
            label = f"{presentation.label}  {value}"
            text_x = legend_x + marker_size + marker_gap
            painter.drawText(
                QRectF(text_x, y, legend_width - marker_size - marker_gap, row_height),
                text_flags,
                label,
            )


class IndexTrendChart(QWidget):
    """All-time date-series view of one stored completed assessment index."""

    def __init__(self, label: str, attribute: str, parent=None):
        super().__init__(parent)
        self.label = label
        self.attribute = attribute
        self.points: list[tuple[date, float]] = []
        self.setMinimumHeight(118)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_rows(self, rows):
        grouped: dict[date, list[float]] = defaultdict(list)
        for row in rows:
            when = getattr(row, "assessment_date", None)
            value = getattr(row, self.attribute, None)
            if when is not None and value is not None:
                grouped[when].append(float(value))
        self.points = [
            (when, sum(values) / len(values))
            for when, values in sorted(grouped.items())
            if values
        ]
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        surface = _palette_color(self, QPalette.ColorRole.AlternateBase)
        border = _palette_color(self, QPalette.ColorRole.Mid)
        text = _palette_color(self, QPalette.ColorRole.Text)
        secondary = _palette_color(self, QPalette.ColorRole.WindowText)
        muted = _palette_color(self, QPalette.ColorRole.PlaceholderText)
        accent = _palette_color(self, QPalette.ColorRole.Link)
        base = _palette_color(self, QPalette.ColorRole.Base)

        painter.fillRect(self.rect(), surface)
        painter.setPen(QPen(border, 1))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(.5, .5, -.5, -.5), 5, 5)

        title_font = QFont(painter.font())
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.setPen(secondary)
        painter.drawText(QRectF(10, 5, 50, 20), Qt.AlignmentFlag.AlignVCenter, self.label)

        if not self.points:
            painter.setFont(QFont())
            painter.setPen(muted)
            painter.drawText(
                QRectF(10, 25, self.width() - 20, self.height() - 35),
                Qt.AlignmentFlag.AlignCenter,
                tr("No completed data"),
            )
            return

        latest = self.points[-1][1]
        painter.setFont(QFont())
        painter.setPen(secondary)
        painter.drawText(
            QRectF(self.width() - 75, 5, 65, 20),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"{latest:.2f}",
        )

        plot = QRectF(32, 28, max(30, self.width() - 44), max(34, self.height() - 50))
        small = QFont(painter.font())
        small.setPointSize(max(7, painter.font().pointSize() - 1))
        painter.setFont(small)

        grid = _palette_color(self, QPalette.ColorRole.Midlight)
        for value in (0.0, 0.5, 1.0):
            y = plot.bottom() - value * plot.height()
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(muted)
            painter.drawText(
                QRectF(1, y - 8, 27, 16),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                f"{value:.1f}",
            )

        first_date = self.points[0][0]
        last_date = self.points[-1][0]
        span = max(1, (last_date - first_date).days)

        def point_for(when, value):
            if first_date == last_date:
                x = plot.center().x()
            else:
                x = plot.left() + ((when - first_date).days / span) * plot.width()
            y = plot.bottom() - max(0.0, min(1.0, value)) * plot.height()
            return QPointF(x, y)

        path = QPainterPath()
        first_point = point_for(*self.points[0])
        path.moveTo(first_point)
        for when, value in self.points[1:]:
            path.lineTo(point_for(when, value))

        line_pen = QPen(accent, 2)
        painter.setPen(line_pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        painter.setBrush(accent)
        painter.setPen(QPen(base, 1))
        for when, value in self.points:
            point = point_for(when, value)
            painter.drawEllipse(point, 3.2, 3.2)

        painter.setPen(muted)
        first_label = first_date.strftime("%d.%m.%y")
        last_label = last_date.strftime("%d.%m.%y")
        if first_date == last_date:
            painter.drawText(
                QRectF(plot.left(), plot.bottom() + 3, plot.width(), 16),
                Qt.AlignmentFlag.AlignCenter,
                first_label,
            )
        else:
            painter.drawText(
                QRectF(plot.left(), plot.bottom() + 3, plot.width() / 2, 16),
                Qt.AlignmentFlag.AlignLeft,
                first_label,
            )
            painter.drawText(
                QRectF(plot.center().x(), plot.bottom() + 3, plot.width() / 2, 16),
                Qt.AlignmentFlag.AlignRight,
                last_label,
            )


class AssessmentTrendCard(DashboardCard):
    """Side-by-side all-time DAI and FCI trends from stored completed results."""

    def __init__(self, parent=None):
        super().__init__("DAI / FCI over time", parent)
        self.setMinimumHeight(150)
        charts = QHBoxLayout()
        charts.setContentsMargins(0, 0, 0, 0)
        charts.setSpacing(8)
        self.dai = IndexTrendChart("DAI", "dai")
        self.fci = IndexTrendChart("FCI", "fci")
        charts.addWidget(self.dai, 1)
        charts.addWidget(self.fci, 1)
        self.layout.addLayout(charts, 1)

    def set_rows(self, rows):
        rows = list(rows)
        self.dai.set_rows(rows)
        self.fci.set_rows(rows)