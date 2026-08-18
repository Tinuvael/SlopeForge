from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QLabel, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from app.icons.ui.ui_icons import ui_icon
from app.localization import tr


CATEGORY_ICONS = {
    "change": "edit",
    "archive": "archive",
    "attachment": "document",
    "geometry": "layers",
    "blast_design": "blast-blocks",
    "geomechanics": "geomechanics",
    "execution": "check",
    "technical_card": "check",
    "assessment": "assessment-area",
    "link": "link",
}


class EntityHistoryWidget(QWidget):
    """Read-only, shared History list for operational entity pages."""

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels([
            tr("Date & time"), tr("User"), tr("Change"), tr("Details")
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet(
            "QTableWidget{background:white;border:1px solid #dfe3ea;border-radius:7px;outline:0;}"
            "QHeaderView::section{background:#f8fafc;border:0;border-bottom:1px solid #dfe3ea;"
            "padding:8px;font-weight:600;color:#374151;}"
            "QTableWidget::item{border-bottom:1px solid #edf0f4;padding:8px;}"
            "QTableWidget::item:selected{background:#eef4fb;color:#111827;}"
        )
        self.empty = QLabel(tr("No history yet"))
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setStyleSheet("color:#6b7280;padding:24px;")
        root.addWidget(self.table, 1)
        root.addWidget(self.empty, 1)
        self.set_entries([])

    def set_entries(self, entries) -> None:
        entries = list(entries)
        self.table.setVisible(bool(entries))
        self.empty.setVisible(not entries)
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.table.setRowHeight(row, 46)
            when = entry.timestamp.astimezone().strftime("%d.%m.%Y %H:%M") if entry.timestamp.tzinfo else entry.timestamp.strftime("%d.%m.%Y %H:%M")
            values = (when, entry.actor or "—", entry.title, entry.details or "")
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.ItemDataRole.UserRole, entry.source_id)
                if column == 2:
                    icon = ui_icon(CATEGORY_ICONS.get(entry.category, "edit"))
                    if not icon.isNull():
                        item.setIcon(icon)
                if column == 0:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
