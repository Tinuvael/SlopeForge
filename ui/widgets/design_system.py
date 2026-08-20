"""Small reusable presentation primitives; application behavior stays elsewhere."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFormLayout, QFrame, QHeaderView, QHBoxLayout,
    QLabel, QPushButton, QTableWidget, QVBoxLayout, QWidget,
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


def configure_standard_dialog(dialog: QDialog, *, minimum_width: int = 520) -> QVBoxLayout:
    """Apply the compact entity-dialog shell without owning dialog behavior."""
    dialog.setObjectName("StandardEntityDialog")
    dialog.setMinimumWidth(minimum_width)
    root = QVBoxLayout(dialog)
    root.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.MD)
    root.setSpacing(Spacing.MD)
    return root


def create_form_section(title: str, parent=None) -> tuple[QFrame, QFormLayout]:
    """Create a standard white card and its aligned two-column form."""
    card = CardFrame(title, parent)
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(Spacing.MD)
    form.setVerticalSpacing(Spacing.SM)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    card.layout.addLayout(form)
    return card, form


def standard_dialog_actions(
    dialog: QDialog, primary_text: str, *, accept=None,
) -> tuple[QWidget, QPushButton, QPushButton]:
    """Return a right-aligned Cancel + single-primary action row."""
    container = QWidget(dialog)
    container.setObjectName("DialogActions")
    actions = QHBoxLayout(container)
    actions.setContentsMargins(0, 0, 0, 0)
    actions.setSpacing(Spacing.SM)
    actions.addStretch(1)
    cancel = set_button_role(QPushButton(tr("Cancel"), container), "secondary")
    primary = set_button_role(QPushButton(tr(primary_text), container), "primary")
    # Do not leave the native style to derive tiny, text-sized action targets.
    # Explicit geometry also keeps the painted button and its mouse hit rect equal
    # on Windows styles.
    cancel.setMinimumWidth(96)
    primary.setMinimumWidth(108)
    cancel.setFixedHeight(32)
    primary.setFixedHeight(32)
    cancel.setAutoDefault(False)
    primary.setDefault(True)
    cancel.clicked.connect(dialog.reject)
    primary.clicked.connect(accept or dialog.accept)
    actions.addWidget(cancel)
    actions.addWidget(primary)
    return container, cancel, primary


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
