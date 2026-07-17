from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from repositories.attachment_repository import AttachmentRow
from repositories.audit_log_repository import AuditLogEntryRow
from repositories.blast_block_repository import BlastBlockRow
from services.blast_block_service import AUDIT_FIELD_LABELS, STATUS_LABELS

ACTION_LABELS = {"create": "Create", "update": "Update", "delete": "Delete", "attach": "Attach", "detach": "Detach"}


def _dash(value) -> str:
    return str(value) if value not in (None, "") else "—"


def format_datetime(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else "—"


def format_date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else "—"


def format_decimal(value) -> str:
    if value is None:
        return "—"
    text = format(value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class CardFrame(QFrame):
    def __init__(self, title: str | None = None):
        super().__init__()
        self.setObjectName("CardFrame")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setSpacing(8)
        if title:
            label = QLabel(title)
            label.setObjectName("CardTitle")
            self.layout.addWidget(label)


class EmptySection(QWidget):
    def __init__(self, text: str = "This section will be implemented in the next stage"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addStretch()
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("MutedText")
        layout.addWidget(label)
        layout.addStretch()


class BlockHeaderWidget(CardFrame):
    def __init__(self):
        super().__init__()
        top = QHBoxLayout()
        self.title = QLabel("Select a block")
        self.title.setObjectName("BlockTitle")
        self.status = QLabel("—")
        self.status.setObjectName("StatusBadge")
        self.edit_button = QPushButton("Edit")
        top.addWidget(self.title)
        top.addWidget(self.status)
        top.addStretch()
        top.addWidget(self.edit_button)
        self.layout.addLayout(top)
        self.meta = QHBoxLayout()
        self.layout.addLayout(self.meta)

    def set_block(self, block: BlastBlockRow | None, can_edit: bool) -> None:
        while self.meta.count():
            item = self.meta.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.edit_button.setEnabled(bool(block and can_edit))
        if block is None:
            self.title.setText("Select a block")
            self.status.setText("—")
            return
        self.title.setText(f"Block {block.block_number}")
        self.status.setText(STATUS_LABELS.get(block.status, block.status))
        values = [
            f"ID: {block.id}",
            f"Horizon: {format_decimal(block.horizon_m)}",
            f"Site: {block.site_name}",
            f"Mine: {block.mine_name}",
            f"Created: {format_datetime(block.created_at)}",
            f"Updated: {format_datetime(block.updated_at)}",
        ]
        for value in values:
            badge = QLabel(value)
            badge.setObjectName("MetaBadge")
            self.meta.addWidget(badge)
        self.meta.addStretch()


class BlockOverviewWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.info = CardFrame("General information")
        self.grid = QGridLayout()
        self.info.layout.addLayout(self.grid)
        self.scheme = BlockSchemePlaceholder()
        layout.addWidget(self.info, 3)
        layout.addWidget(self.scheme, 2)

    def set_block(self, block: BlastBlockRow | None) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = []
        if block:
            rows = [
                ("Block number", block.block_number),
                ("ID", block.id),
                ("Created", format_datetime(block.created_at)),
                ("Author", block.author_name),
                ("Horizon", format_decimal(block.horizon_m)),
                ("Mine", block.mine_name),
                ("Site", block.site_name),
                ("Status", STATUS_LABELS.get(block.status, block.status)),
                ("Comment", block.comment),
            ]
        else:
            rows = [("Block", "—")]
        for row, (name, value) in enumerate(rows):
            left = QLabel(name)
            left.setObjectName("MutedText")
            right = QLabel(_dash(value))
            right.setWordWrap(True)
            self.grid.addWidget(left, row, 0)
            self.grid.addWidget(right, row, 1)
        self.scheme.set_block(block)


class BlockSchemePlaceholder(CardFrame):
    def __init__(self):
        super().__init__("Block scheme")
        self.box = QLabel("Block scheme is not loaded yet")
        self.box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.box.setMinimumHeight(220)
        self.box.setObjectName("SchemePlaceholder")
        self.layout.addWidget(self.box)

    def set_block(self, block: BlastBlockRow | None) -> None:
        number = block.block_number if block else "—"
        self.box.setText(f"{number}\nBlock scheme is not loaded yet")


class CompactInfoCards(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.cards = []
        for title in ("Geomechanical parameters", "Blast design parameters", "Execution fact"):
            card = CardFrame(title)
            label = QLabel("—")
            label.setObjectName("MutedText")
            card.layout.addWidget(label)
            card.layout.addStretch()
            self.cards.append(label)
            layout.addWidget(card)

    def set_block(self, block: BlastBlockRow | None) -> None:
        for label in self.cards:
            label.setText("—")


class BlockSummaryWidget(CardFrame):
    def __init__(self):
        super().__init__("Summary")
        self.grid = QGridLayout()
        self.layout.addLayout(self.grid)

    def set_data(self, block: BlastBlockRow | None, photo_count: int, document_count: int, audit_count: int) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        rows = [
            ("Status", STATUS_LABELS.get(block.status, block.status) if block else "—"),
            ("Planned blast date", format_date(block.planned_blast_date) if block else "—"),
            ("Photos", photo_count),
            ("Documents", document_count),
            ("History records", audit_count),
        ]
        for row, (name, value) in enumerate(rows):
            self.grid.addWidget(QLabel(name), row, 0)
            self.grid.addWidget(QLabel(_dash(value)), row, 1)


class AttachmentPreviewWidget(CardFrame):
    def __init__(self, title: str):
        super().__init__(title)
        header = QHBoxLayout()
        self.add_button = QPushButton("Add")
        self.add_button.setEnabled(False)
        header.addStretch()
        header.addWidget(self.add_button)
        self.layout.addLayout(header)
        self.content = QVBoxLayout()
        self.layout.addLayout(self.content)

    def set_items(self, items: list[AttachmentRow], empty_text: str) -> None:
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        if not items:
            label = QLabel(empty_text)
            label.setObjectName("MutedText")
            self.content.addWidget(label)
            return
        for attachment in items[:5]:
            label = QLabel(attachment.original_filename)
            label.setWordWrap(True)
            self.content.addWidget(label)


class AuditPreviewWidget(CardFrame):
    def __init__(self, title: str = "Change history"):
        super().__init__(title)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Date", "User", "Action", "Field", "Old", "New"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.layout.addWidget(self.table)

    def set_entries(self, entries: list[AuditLogEntryRow], limit: int = 5) -> None:
        visible = entries[:limit]
        self.table.setRowCount(len(visible))
        for row, entry in enumerate(visible):
            values = [
                format_datetime(entry.created_at),
                entry.user_display_name,
                ACTION_LABELS.get(entry.action, entry.action),
                AUDIT_FIELD_LABELS.get(entry.field_name or "", entry.field_name or ""),
                entry.old_value or "",
                entry.new_value or "",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))


class CommentsWidget(CardFrame):
    def __init__(self):
        super().__init__("Comments")
        self.text = QTextEdit()
        self.text.setReadOnly(True)
        self.layout.addWidget(self.text)

    def set_block(self, block: BlastBlockRow | None) -> None:
        self.text.setPlainText(block.comment if block and block.comment else "—")
