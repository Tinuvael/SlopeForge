"""Small reusable presentation primitives; application behavior stays elsewhere."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHeaderView, QLabel, QPushButton, QTableWidget,
    QVBoxLayout,
)

from app.localization import tr
from ui.theme import Spacing


class CardFrame(QFrame):
    def __init__(self, title: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("CardFrame")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(
            Spacing.CARD_HORIZONTAL, Spacing.CARD_VERTICAL,
            Spacing.CARD_HORIZONTAL, Spacing.CARD_VERTICAL,
        )
        self.layout.setSpacing(Spacing.SM)
        if title:
            label = QLabel(tr(title))
            label.setObjectName("CardTitle")
            self.layout.addWidget(label)


def set_button_role(button: QPushButton, role: str) -> QPushButton:
    if role not in {"primary", "secondary", "link", "danger"}:
        raise ValueError(f"Unknown button role: {role}")
    button.setProperty("role", role)
    button.style().unpolish(button)
    button.style().polish(button)
    return button


def set_status_role(label: QLabel, role: str) -> QLabel:
    label.setObjectName("StatusBadge")
    label.setProperty("statusRole", role)
    label.style().unpolish(label)
    label.style().polish(label)
    return label


def configure_standard_table(table: QTableWidget) -> QTableWidget:
    """Give active management/history tables one compact visual contract."""
    table.setObjectName("StandardTable")
    table.setShowGrid(False)
    table.setAlternatingRowColors(False)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    table.horizontalHeader().setMinimumSectionSize(72)
    table.horizontalHeader().setHighlightSections(False)
    return table


def high_contrast_icon(icon: QIcon, color: str = "#ffffff", size: int = 20) -> QIcon:
    """Tint an existing SVG-derived icon for a filled button without a new icon set."""
    source = icon.pixmap(size, size)
    result = QPixmap(source.size())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.drawPixmap(0, 0, source)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(result.rect(), QColor(color))
    painter.end()
    return QIcon(result)
