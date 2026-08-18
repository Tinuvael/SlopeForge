from __future__ import annotations

from PySide6.QtCore import QFileInfo, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFileIconProvider, QGridLayout, QHBoxLayout, QLabel, QPushButton,
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


class AssessmentMatrixPreview(QWidget):
    """Tiny read-only DAI/FCI quadrant using already stored evaluation results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dai = None
        self.fci = None
        self.dai_threshold = 0.65
        self.fci_threshold = 0.60
        self.setMinimumHeight(170)

    def set_result(self, *, dai, fci, dai_threshold=0.65, fci_threshold=0.60):
        self.dai = None if dai is None else max(0.0, min(1.0, float(dai)))
        self.fci = None if fci is None else max(0.0, min(1.0, float(fci)))
        self.dai_threshold = max(0.0, min(1.0, float(dai_threshold)))
        self.fci_threshold = max(0.0, min(1.0, float(fci_threshold)))
        self.update()

    def paintEvent(self, event):  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(34, 12, max(40, self.width() - 48), max(40, self.height() - 42))

        painter.fillRect(rect, QColor("#fbfcfd"))
        painter.setPen(QPen(QColor("#cfd6de"), 1))
        painter.drawRect(rect)

        x = rect.left() + rect.width() * self.fci_threshold
        y = rect.bottom() - rect.height() * self.dai_threshold
        painter.setPen(QPen(QColor("#c1c9d2"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
        painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))

        painter.setPen(QColor("#667085"))
        painter.drawText(4, int(rect.center().y()), "DAI")
        painter.drawText(int(rect.center().x()) - 8, self.height() - 6, "FCI")

        if self.dai is None or self.fci is None:
            painter.setPen(QColor("#8a94a3"))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, tr("No assessment result yet"))
            return

        px = rect.left() + rect.width() * self.fci
        py = rect.bottom() - rect.height() * self.dai
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(QColor("#1261a0"))
        painter.drawEllipse(int(px) - 6, int(py) - 6, 12, 12)


class QuickAttachmentPreview(CardFrame):
    """Sidebar attachment preview with direct Add and Open-page actions."""

    add_requested = Signal()
    open_page_requested = Signal()

    PHOTO_TILE_WIDTH = 120
    PHOTO_TILE_HEIGHT = 88

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
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        for index, attachment in enumerate(self._items[:4]):
            button = QToolButton()
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            button.setText("")
            button.setToolTip(attachment.title or attachment.original_filename)
            button.setFixedSize(self.PHOTO_TILE_WIDTH, self.PHOTO_TILE_HEIGHT)
            button.setIconSize(QSize(self.PHOTO_TILE_WIDTH, self.PHOTO_TILE_HEIGHT))
            button.setStyleSheet(
                "QToolButton{padding:0;margin:0;border:1px solid #dfe3ea;"
                "border-radius:6px;background:#f3f4f6;}"
                "QToolButton:hover{border:1px solid #8fb4dc;}"
                "QToolButton:pressed{border:1px solid #1261a0;}"
            )
            pixmap = self._photo_pixmap(
                attachment, self.PHOTO_TILE_WIDTH, self.PHOTO_TILE_HEIGHT
            )
            if not pixmap.isNull():
                button.setIcon(QIcon(pixmap))
            button.clicked.connect(lambda _checked=False, i=index: self._open_photo(i))
            grid.addWidget(button, index // 2, index % 2)
        holder = QWidget()
        holder.setLayout(grid)
        self.content.addWidget(holder)

    def _photo_pixmap(self, attachment, width: int, height: int) -> QPixmap:
        """Return a center-cropped cover thumbnail that fills the tile completely."""
        if self._service is None:
            return QPixmap()
        path = self._service.resolve_path(attachment)
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        image = reader.read()
        if image.isNull():
            return QPixmap()
        pixmap = QPixmap.fromImage(image)
        scaled = pixmap.scaled(
            width,
            height,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )
        left = max(0, (scaled.width() - width) // 2)
        top = max(0, (scaled.height() - height) // 2)
        return scaled.copy(left, top, width, height)

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
