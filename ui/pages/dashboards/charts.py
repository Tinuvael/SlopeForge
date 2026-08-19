"""Small dependency-free dashboard charts painted directly by Qt."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from app.localization import tr
from .widgets import quadrant_presentation


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
        self.setMinimumHeight(118 if kind == "donut" else 92)
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
            painter.setPen(QColor("#64748b"))
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
        for index, (label, value) in enumerate(self.data.items()):
            top = 4 + index * row_height
            painter.setPen(QColor("#334155"))
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
            painter.setBrush(QColor("#2563eb"))
            painter.drawRoundedRect(bar, 3, 3)
            painter.setPen(QColor("#0f172a"))
            painter.drawText(
                QRectF(bar.right() + 5, top, 28, row_height - 3),
                Qt.AlignmentFlag.AlignVCenter,
                str(value),
            )

    def _paint_donut(self, painter):
        size = max(82, min(self.height() - 12, self.width() * 0.42))
        ring = QRectF(4, (self.height() - size) / 2, size, size)
        total = sum(self.data.values())
        start = 90 * 16
        pen = QPen()
        pen.setWidth(max(12, int(size * 0.19)))
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        for key, value in self.data.items():
            pen.setColor(QColor(quadrant_presentation(key).color))
            painter.setPen(pen)
            span = -round(360 * 16 * value / total)
            painter.drawArc(
                ring.adjusted(
                    pen.width() / 2,
                    pen.width() / 2,
                    -pen.width() / 2,
                    -pen.width() / 2,
                ),
                start,
                span,
            )
            start += span
        painter.setPen(QColor("#0f172a"))
        painter.drawText(ring, Qt.AlignmentFlag.AlignCenter, str(total))

        legend_x = ring.right() + 14
        legend_width = max(20, self.width() - int(legend_x) - 4)
        row_height = max(20, min(25, self.height() // max(1, len(self.data))))
        top = max(2, (self.height() - row_height * len(self.data)) // 2)
        metrics = QFontMetrics(painter.font())
        for index, (key, value) in enumerate(self.data.items()):
            presentation = quadrant_presentation(key)
            y = top + index * row_height
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(presentation.color))
            painter.drawRoundedRect(QRectF(legend_x, y + 6, 9, 9), 2, 2)
            painter.setPen(QColor("#334155"))
            label = f"{presentation.label}  {value}"
            painter.drawText(
                QRectF(legend_x + 15, y, legend_width - 15, row_height),
                Qt.AlignmentFlag.AlignVCenter,
                metrics.elidedText(
                    label,
                    Qt.TextElideMode.ElideRight,
                    max(20, legend_width - 15),
                ),
            )
