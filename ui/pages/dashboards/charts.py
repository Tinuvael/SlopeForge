"""Small dependency-free dashboard charts painted directly by Qt."""
from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QWidget

from .widgets import quadrant_presentation


class CompactChart(QWidget):
    """Native Qt horizontal bars or donut, including an intentional empty state."""

    def __init__(self, data, kind="bar", parent=None):
        super().__init__(parent)
        self.data = {str(key): int(value) for key, value in data.items() if value is not None and value > 0}
        self.kind = kind
        self.setMinimumHeight(150)
        self.setMaximumHeight(240)

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#FFFFFF"))
        if not self.data:
            painter.setPen(QColor("#64748B"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data yet")
            return
        if self.kind == "donut":
            self._paint_donut(painter)
        else:
            self._paint_bars(painter)

    def _paint_bars(self, painter):
        metrics = QFontMetrics(painter.font())
        label_width = min(max(metrics.horizontalAdvance(x) for x in self.data) + 12, self.width() // 2)
        row_height = max(22, min(34, (self.height() - 12) // len(self.data)))
        maximum = max(self.data.values())
        for index, (label, value) in enumerate(self.data.items()):
            top = 7 + index * row_height
            painter.setPen(QColor("#334155"))
            painter.drawText(QRectF(4, top, label_width - 8, row_height - 5), Qt.AlignmentFlag.AlignVCenter, metrics.elidedText(label, Qt.TextElideMode.ElideRight, label_width - 10))
            bar = QRectF(label_width, top + 5, max(2, (self.width() - label_width - 38) * value / maximum), row_height - 14)
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor("#2563EB")); painter.drawRoundedRect(bar, 3, 3)
            painter.setPen(QColor("#0F172A")); painter.drawText(QRectF(bar.right() + 6, top, 30, row_height - 5), Qt.AlignmentFlag.AlignVCenter, str(value))

    def _paint_donut(self, painter):
        size = min(self.height() - 20, self.width() * .42)
        ring = QRectF(10, 10, size, size); total = sum(self.data.values()); start = 90 * 16
        pen = QPen(); pen.setWidth(max(12, int(size * .20))); pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        for key, value in self.data.items():
            pen.setColor(QColor(quadrant_presentation(key).color)); painter.setPen(pen)
            span = -round(360 * 16 * value / total); painter.drawArc(ring.adjusted(pen.width()/2, pen.width()/2, -pen.width()/2, -pen.width()/2), start, span); start += span
        painter.setPen(QColor("#0F172A")); painter.drawText(ring, Qt.AlignmentFlag.AlignCenter, str(total))
        x = ring.right() + 18
        for index, (key, value) in enumerate(self.data.items()):
            presentation = quadrant_presentation(key); y = 18 + index * 25
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(presentation.color)); painter.drawEllipse(QRectF(x, y, 9, 9))
            painter.setPen(QColor("#334155")); painter.drawText(QRectF(x + 15, y - 5, self.width() - x - 18, 20), Qt.AlignmentFlag.AlignVCenter, f"{presentation.label}  {value}")
