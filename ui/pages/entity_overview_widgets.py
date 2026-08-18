from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QImageReader, QPixmap
from PySide6.QtWidgets import (
    QFileIconProvider, QFileInfo, QGridLayout, QHBoxLayout, QLabel, QPushButton,
    QToolButton, QVBoxLayout, QWidget,
)

from app.localization import tr
from ui.dialogs.entity_attachment_dialog import PhotoViewer
from ui.pages.block_card_widgets import CardFrame


WORKFLOW_BADGE_STYLES = {
    "in_preparation": ("#f3f4f6", "#4b5563", "#d1d5db"),
    "planned": ("#eaf3ff", "#155fa0", "#9bc2e8"),
    "blasted": ("#fff4d6", "#8a5a00", "#f4c76b"),
    "assessed": ("#edf8f0", "#2f6f3e", "#9bcaa6"),
    "in_progress": ("#eaf3ff", "#155fa0", "#9bc2e8"),
    "completed": ("#edf8f0", "#2f6f3e", "#9bcaa6"),
    "unknown": ("#f3f4f6", "#4b5563", "#d1d5db"),
}


def _state_key(state) -> str:
    value = getattr(state, "value", state)
    return str(value or "unknown").strip().lower().replace(" ", "_")


def apply_status_badge(label: QLabel, state) -> None:
    background, foreground, border = WORKFLOW_BADGE_STYLES.get(
        _state_key(state), WORKFLOW_BADGE_STYLES["unknown"]
    )
    label.setObjectName("StatusBadge")
    label.setStyleSheet(
        f"background:{background};color:{foreground};border:1px solid {border};"
        "border-radius:5px;padding:4px 8px;font-weight:600;"
    )


def apply_archive_badge(label: QLabel) -> None:
    label.setStyleSheet(
        "background:#eef0f3;color:#4b5563;border:1px solid #cfd4dc;"
        "border-radius:5px;padding:4px 8px;font-weight:600;"
    )


class EntityHeaderWidget(CardFrame):
    """Shared operational-entity header without embedding domain behavior."""

    def __init__(self, placeholder="Select entity"):
        super().__init__()
        top = QHBoxLayout()
        self.title = QLabel(tr(placeholder))
        self.title.setObjectName("EntityTitle")
        self.status = QLabel(tr("—"))
        apply_status_badge(self.status, "unknown")
        self.archive = QLabel(tr("Archived"))
        apply_archive_badge(self.archive)
        self.archive.hide()
        self.edit_button = QPushButton(tr("Edit"))
        top.addWidget(self.title)
        top.addWidget(self.status)
        top.addWidget(self.archive)
        top.addStretch()
        top.addWidget(self.edit_button)
        self.layout.addLayout(top)
        self.meta = QHBoxLayout()
        self.layout.addLayout(self.meta)

    def set_content(self, *, title: str, status_text: str, status_state,
                    meta_values=(), archived=False, can_edit=False) -> None:
        self.title.setText(title)
        self.status.setText(status_text)
        apply_status_badge(self.status, status_state)
        self.archive.setVisible(bool(archived))
        self.edit_button.setEnabled(bool(can_edit))
        while self.meta.count():
            item = self.meta.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for value in meta_values:
            badge = QLabel(str(value))
            badge.setObjectName("MetaBadge")
            self.meta.addWidget(badge)
        self.meta.addStretch()


class OverviewKeyValueCard(CardFrame):
    """Compact read-only summary card used by all entity overviews."""

    open_requested = Signal()

    def __init__(self, title: str, *, open_label: str | None = None):
        super().__init__(title)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(5)
        self.layout.addLayout(self.grid)
        self.layout.addStretch()
        self.open_button = None
        if open_label:
            self.open_button = QPushButton(tr(open_label))
            self.open_button.clicked.connect(self.open_requested)
            self.layout.addWidget(self.open_button)

    def set_rows(self, rows) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        visible = list(rows)
        if not visible:
            visible = [(tr("No data yet"), "")]
        for row, (name, value) in enumerate(visible):
            key = QLabel(tr(str(name)))
            key.setObjectName("MutedText")
            val = QLabel("—" if value in (None, "") else str(value))
            val.setWordWrap(True)
            self.grid.addWidget(key, row, 0)
            self.grid.addWidget(val, row, 1)
        self.grid.setColumnStretch(1, 1)


class QuickAttachmentPreview(CardFrame):
    """Sidebar attachment preview with direct Add and Open-page actions."""

    add_requested = Signal()
    open_page_requested = Signal()

    def __init__(self, title: str, kind: str):
        super().__init__()
        self.kind = kind
        self._service = None
        self._items = []
        self._file_icons = QFileIconProvider() if kind == "document" else None

        header = QHBoxLayout()
        heading = QLabel(tr(title)); heading.setObjectName("CardTitle")
        self.add_button = QPushButton(tr("Add"))
        self.open_button = QPushButton(tr("Open"))
        self.add_button.clicked.connect(self.add_requested)
        self.open_button.clicked.connect(self.open_page_requested)
        header.addWidget(heading)
        header.addStretch()
        header.addWidget(self.add_button)
        header.addWidget(self.open_button)
        self.layout.addLayout(header)

        self.content = QVBoxLayout()
        self.content.setSpacing(6)
        self.layout.addLayout(self.content)

    def set_items(self, service, items, empty_text: str, *, can_add=True) -> None:
        self._service = service
        self._items = list(items)
        self.add_button.setEnabled(bool(can_add))
        self.open_button.setEnabled(True)
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

        if not self._items:
            label = QLabel(tr(empty_text))
            label.setObjectName("MutedText")
            self.content.addWidget(label)
            return
        if self.kind == "photo":
            self._build_photos()
        else:
            self._build_documents()

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                QuickAttachmentPreview._clear_layout(item.layout())

    def _build_photos(self):
        grid = QGridLayout()
        grid.setSpacing(6)
        for index, attachment in enumerate(self._items[:4]):
            button = QToolButton()
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setText(attachment.title or attachment.original_filename)
            button.setToolTip(attachment.original_filename)
            button.setFixedSize(120, 96)
            button.setIconSize(QSize(112, 66))
            pixmap = self._photo_pixmap(attachment)
            if not pixmap.isNull():
                button.setIcon(QIcon(pixmap.scaled(
                    112, 66, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )))
            button.clicked.connect(lambda _checked=False, i=index: self._open_photo(i))
            grid.addWidget(button, index // 2, index % 2)
        holder = QWidget()
        holder.setLayout(grid)
        self.content.addWidget(holder)

    def _photo_pixmap(self, attachment) -> QPixmap:
        if self._service is None:
            return QPixmap()
        path = self._service.resolve_path(attachment)
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        return QPixmap.fromImage(image) if not image.isNull() else QPixmap()

    def _open_photo(self, index: int):
        if self._service is None or not self._items:
            return
        PhotoViewer(self._service, self._items, index, self).exec()

    def _build_documents(self):
        for attachment in self._items[:4]:
            row = QToolButton()
            row.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            row.setText(attachment.title or attachment.original_filename)
            row.setToolTip(attachment.original_filename)
            if self._file_icons is not None:
                row.setIcon(self._file_icons.icon(QFileInfo(attachment.original_filename)))
            row.setAutoRaise(True)
            row.clicked.connect(lambda _checked=False, a=attachment: self._open_document(a))
            self.content.addWidget(row)

    def _open_document(self, attachment):
        if self._service is not None:
            self._service.open_file(attachment)
