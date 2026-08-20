"""Small reusable presentation primitives; application behavior stays elsewhere."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEvent, QRect, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QAbstractSpinBox, QDialog, QDoubleSpinBox, QFormLayout,
    QFrame, QHeaderView, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QToolButton, QVBoxLayout, QWidget,
)

from app.localization import tr
from ui.theme import Spacing


_NEUTRAL_ICON_ROOT = (
    Path(__file__).resolve().parents[2] / "app" / "icons" / "ui" / "svg" / "neutral"
)


class ChevronDoubleSpinBox(QDoubleSpinBox):
    """Entity-form number field with real, platform-independent step buttons."""

    _BUTTON_STRIP_WIDTH = 26

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ChevronDoubleSpinBox")
        # Entity dialogs may assign a semantic object name (for example,
        # ``horizon``).  Keep styling attached to the control type even when
        # that happens instead of relying on this initial object name.
        self.setProperty("standardChevronSpinBox", True)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)

        self.up_button = self._step_button("ChevronSpinUpButton", "chevron-up.svg")
        self.down_button = self._step_button("ChevronSpinDownButton", "chevron-down.svg")
        self.up_button.clicked.connect(self.stepUp)
        self.down_button.clicked.connect(self.stepDown)

        # The buttons overlay the spinbox body, so explicitly keep entered text
        # and the cursor out of their dedicated strip.
        self.lineEdit().setTextMargins(7, 0, self._BUTTON_STRIP_WIDTH + 6, 0)
        self._sync_step_buttons()

    def _step_button(self, name: str, icon_name: str) -> QToolButton:
        button = QToolButton(self)
        button.setObjectName(name)
        button.setIcon(QIcon(str(_NEUTRAL_ICON_ROOT / icon_name)))
        button.setIconSize(QSize(12, 12))
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setAutoRepeat(True)
        return button

    def resizeEvent(self, event):
        super().resizeEvent(event)
        strip_x = self.width() - self._BUTTON_STRIP_WIDTH - 1
        available_height = max(0, self.height() - 2)
        upper_height = (available_height + 1) // 2
        self.up_button.setGeometry(
            QRect(strip_x, 1, self._BUTTON_STRIP_WIDTH, upper_height)
        )
        self.down_button.setGeometry(
            QRect(
                strip_x,
                1 + upper_height,
                self._BUTTON_STRIP_WIDTH,
                available_height - upper_height,
            )
        )
        # Keep the real controls above the internal editor on every platform.
        self.up_button.raise_()
        self.down_button.raise_()

    def setReadOnly(self, read_only: bool):
        super().setReadOnly(read_only)
        self._sync_step_buttons()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange:
            self._sync_step_buttons()

    def _sync_step_buttons(self):
        can_step = self.isEnabled() and not self.isReadOnly()
        self.up_button.setEnabled(can_step)
        self.down_button.setEnabled(can_step)


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
