"""Small reusable presentation primitives; application behavior stays elsewhere."""
from __future__ import annotations

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QVBoxLayout

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
