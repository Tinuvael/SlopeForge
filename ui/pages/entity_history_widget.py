from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.icons.ui.ui_icons import ui_icon
from app.localization import tr
from ui.presentation_labels import history_text
from ui.widgets.design_system import configure_standard_table, set_button_role


CATEGORY_ICONS = {
    "change": "edit",
    "archive": "archive",
    "attachment": "document",
    "geometry": "layers",
    "blast_design": "blast-blocks",
    "geomechanics": "technical-card",
    "execution": "check",
    "technical_card": "technical-card",
    "assessment": "assessment-area",
    "link": "link",
}
OPENABLE_SOURCE_TYPES = {
    "technical_card", "blast_geometry", "assessment_geometry", "assessment_evaluation"
}


class EntityHistoryWidget(QWidget):
    """Read-only, shared History list for operational entity pages."""

    entryActivated = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries = []
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        toolbar = QHBoxLayout()
        toolbar.addStretch()
        self.open_revision_button = QPushButton(tr("Open revision"))
        self.open_revision_button.setIcon(ui_icon("folder-open"))
        self.open_revision_button.setEnabled(False)
        set_button_role(self.open_revision_button, "secondary")
        self.open_revision_button.clicked.connect(self._activate_selected)
        toolbar.addWidget(self.open_revision_button)
        root.addLayout(toolbar)
        self.table = QTableWidget(0, 4)
        configure_standard_table(self.table)
        self.table.setHorizontalHeaderLabels([
            tr("Date & time"), tr("User"), tr("Change"), tr("Details")
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._sync_open_button)
        self.table.cellDoubleClicked.connect(lambda _row, _column: self._activate_selected())
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.empty = QLabel(tr("No history yet"))
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setObjectName("EmptyState")
        root.addWidget(self.table, 1)
        root.addWidget(self.empty, 1)
        self.set_entries([])

    def set_entries(self, entries) -> None:
        self._entries = list(entries)
        self.table.setVisible(bool(self._entries))
        self.empty.setVisible(not self._entries)
        self.table.setRowCount(len(self._entries))
        for row, entry in enumerate(self._entries):
            self.table.setRowHeight(row, 46)
            when = entry.timestamp.astimezone().strftime("%d.%m.%Y %H:%M") if entry.timestamp.tzinfo else entry.timestamp.strftime("%d.%m.%Y %H:%M")
            values = (
                when, entry.actor or "—", history_text(entry.title),
                history_text(entry.details),
            )
            openable = entry.source_type in OPENABLE_SOURCE_TYPES and bool(entry.source_id)
            tooltip = tr("Double-click to open this historical revision.") if openable else ""
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, entry.source_id)
                if tooltip:
                    item.setToolTip(tooltip)
                if column == 2:
                    icon = ui_icon(CATEGORY_ICONS.get(entry.category, "edit"))
                    if not icon.isNull():
                        item.setIcon(icon)
                if column == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
        self._sync_open_button()

    def _selected_entry(self):
        row = self.table.currentRow()
        return self._entries[row] if 0 <= row < len(self._entries) else None

    def _sync_open_button(self):
        entry = self._selected_entry()
        self.open_revision_button.setEnabled(
            bool(entry and entry.source_type in OPENABLE_SOURCE_TYPES and entry.source_id)
        )

    def _activate_selected(self):
        entry = self._selected_entry()
        if entry and entry.source_type in OPENABLE_SOURCE_TYPES and entry.source_id:
            self.entryActivated.emit(entry)
