from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QFileInfo, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QIcon, QImageReader, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QFileIconProvider,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.icons.ui.ui_icons import ui_icon
from app.localization import tr
from ui.dialogs.entity_attachment_dialog import PhotoViewer
from ui.widgets.design_system import CardFrame, set_button_role, set_status_role
from ui.pages.plan_geometry_widget import PlanGeometryWidget


WORKFLOW_BADGE_ROLES = {"planned": "info", "in_progress": "info", "blasted": "warning", "assessed": "success", "completed": "success"}


def _state_key(state) -> str:
    value = getattr(state, "value", state)
    return str(value or "unknown").strip().lower().replace(" ", "_")


def apply_status_badge(label: QLabel, state) -> None:
    set_status_role(label, WORKFLOW_BADGE_ROLES.get(_state_key(state), "neutral"))


def apply_archive_badge(label: QLabel) -> None:
    set_status_role(label, "archived")


class EntityHeaderWidget(CardFrame):
    """Shared operational-entity header with one canonical context line."""

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
        self.edit_button.setProperty("role", "secondary")
        self.edit_button.setIcon(ui_icon("edit", "blue"))
        top.addWidget(self.title)
        top.addWidget(self.status)
        top.addWidget(self.archive)
        top.addStretch()
        top.addWidget(self.edit_button)
        self.layout.addLayout(top)
        self.context = QLabel()
        self.context.setObjectName("EntityContextLine")
        self.context.setWordWrap(False)
        self.layout.addWidget(self.context)

    def set_content(
        self,
        *,
        title: str,
        status_text: str,
        status_state,
        meta_values=(),
        archived=False,
        can_edit=False,
    ) -> None:
        self.title.setText(title)
        self.status.setText(status_text)
        apply_status_badge(self.status, status_state)
        self.archive.setVisible(bool(archived))
        self.edit_button.setEnabled(bool(can_edit))
        self.context.setText(
            "  ·  ".join(str(value) for value in meta_values if value not in (None, ""))
        )


class OverviewLinkButton(QPushButton):
    """Small text action used in card headers instead of floating footer buttons."""

    def __init__(self, text="Open", parent=None):
        super().__init__(tr(text), parent)
        set_button_role(self, "link")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFlat(True)


class OverviewKeyValueCard(CardFrame):
    """Compact summary card without dashboard-style nested metric tiles."""

    open_requested = Signal()

    def __init__(self, title: str, *, open_label: str | None = None):
        super().__init__()
        header = QHBoxLayout()
        heading = QLabel(tr(title))
        heading.setObjectName("CardTitle")
        header.addWidget(heading)
        header.addStretch()
        self.open_button = None
        if open_label:
            self.open_button = OverviewLinkButton(open_label)
            self.open_button.clicked.connect(self.open_requested)
            header.addWidget(self.open_button)
        self.layout.addLayout(header)
        self.grid = QGridLayout()
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(7)
        self.layout.addLayout(self.grid)

    def set_rows(self, rows) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        visible = list(rows) or [(tr("No data yet"), "")]
        for row, value in enumerate(visible):
            name, data = value[:2]
            hint = value[2] if len(value) > 2 else None
            key = QLabel(tr(str(name)))
            key.setObjectName("MutedText")
            val = QLabel("—" if data in (None, "") else str(data))
            val.setObjectName("SummaryValue")
            val.setWordWrap(True)
            self.grid.addWidget(key, row, 0)
            self.grid.addWidget(val, row, 1)
            if hint:
                secondary = QLabel(str(hint))
                secondary.setObjectName("MutedText")
                self.grid.addWidget(secondary, row, 2)
        self.grid.setColumnStretch(1, 1)


class _FocusSaveEditor(QPlainTextEdit):
    focus_lost = Signal()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focus_lost.emit()


class InlineAutosaveNotes(CardFrame):
    """Inline notes editor that requests persistence only on focus-out and dirty text."""

    save_requested = Signal(str)

    def __init__(self, title="Notes"):
        super().__init__(title)
        self.editor = _FocusSaveEditor()
        self.editor.setPlaceholderText(tr("No notes"))
        self.editor.setMinimumHeight(74)
        self.editor.setMaximumHeight(110)
        self.editor.focus_lost.connect(self._save_if_dirty)
        self.layout.addWidget(self.editor)
        self._saved_text = ""

    def set_value(self, text: str | None, *, editable: bool) -> None:
        value = text or ""
        self._saved_text = value
        if self.editor.toPlainText() != value:
            self.editor.setPlainText(value)
        self.editor.setReadOnly(not editable)

    def mark_saved(self, text: str) -> None:
        self._saved_text = text

    def restore_saved(self) -> None:
        self.editor.setPlainText(self._saved_text)

    def _save_if_dirty(self) -> None:
        if self.editor.isReadOnly():
            return
        text = self.editor.toPlainText()
        if text != self._saved_text:
            self.save_requested.emit(text)


class EngineeringSummaryCard(CardFrame):
    """One card containing engineering sections, without nested mini-cards."""

    section_open_requested = Signal(str)

    def __init__(self, title="Engineering summary"):
        super().__init__(title)
        self.sections = QVBoxLayout()
        self.sections.setSpacing(8)
        self.layout.addLayout(self.sections)

    def set_sections(self, sections):
        while self.sections.count():
            item = self.sections.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for index, (key, title, lines) in enumerate(sections):
            section = QWidget()
            layout = QVBoxLayout(section)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            header = QHBoxLayout()
            heading = QLabel(tr(title))
            heading.setObjectName("EngineeringSectionTitle")
            action = OverviewLinkButton("Open ›")
            action.clicked.connect(
                lambda _checked=False, k=key: self.section_open_requested.emit(k)
            )
            header.addWidget(heading)
            header.addStretch()
            header.addWidget(action)
            layout.addLayout(header)
            text = QLabel(
                "  ·  ".join(str(line) for line in lines if line not in (None, ""))
                or tr("No data yet")
            )
            text.setWordWrap(True)
            text.setObjectName("EngineeringSummaryText")
            layout.addWidget(text)
            self.sections.addWidget(section)
            if index < len(sections) - 1:
                divider = QFrame()
                divider.setFrameShape(QFrame.Shape.HLine)
                divider.setObjectName("OverviewDivider")
                self.sections.addWidget(divider)


class SquareGeometryCard(CardFrame):
    """Large overview geometry with an optional near-square sizing contract."""

    action_requested = Signal()

    def __init__(
        self,
        title="Plan / geometry",
        *,
        action_label="Reimport geometry",
        enforce_square=True,
        parent=None,
    ):
        super().__init__()
        self.setParent(parent)
        self._enforce_square = bool(enforce_square)
        self.setMinimumWidth(470)
        self.setMaximumWidth(620)
        if self._enforce_square:
            self.setMinimumHeight(500)
            self.setMaximumHeight(640)
        else:
            self.setMinimumHeight(390)
            self.setMaximumHeight(500)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        header = QHBoxLayout()
        heading = QLabel(tr(title))
        heading.setObjectName("CardTitle")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("MutedText")
        self.lines = QCheckBox(tr("Project Lines"))
        self.lines.setChecked(True)
        self.center_button = OverviewLinkButton("Center")
        self.action_button = OverviewLinkButton(action_label)
        header.addWidget(heading)
        header.addSpacing(8)
        header.addWidget(self.subtitle)
        header.addStretch()
        header.addWidget(self.lines)
        header.addWidget(self.center_button)
        header.addWidget(self.action_button)
        self.layout.addLayout(header)

        self.plan = PlanGeometryWidget(self)
        self.plan.set_context_visible(False)
        self.plan.context.hide()
        self.plan.lines.hide()
        self.plan.frame_button.hide()
        self.plan.reimport_button.hide()
        self.lines.toggled.connect(self.plan.lines.setChecked)
        self.center_button.clicked.connect(self.plan.center_on_focus)
        self.action_button.clicked.connect(self.action_requested)
        self.layout.addWidget(self.plan, 1)

    def hasHeightForWidth(self):
        return self._enforce_square

    def heightForWidth(self, width):
        return width if self._enforce_square else -1

    def sizeHint(self):
        return QSize(540, 540 if self._enforce_square else 440)

    def set_geometry(
        self,
        geometry,
        project_lines=(),
        *,
        revision=None,
        source="",
        focus_geometry=None,
    ):
        parts = []
        if revision not in (None, ""):
            parts.append(f"{tr('Geometry rev.')} {revision}")
        if source:
            parts.append(str(source))
        self.subtitle.setText(" · ".join(parts))
        self.subtitle.setVisible(bool(parts))
        self.plan.set_geometry(
            geometry, project_lines, "", focus_geometry=focus_geometry
        )

    def set_action_enabled(self, enabled):
        self.action_button.setEnabled(bool(enabled))


@dataclass(frozen=True)
class RelatedEntityRow:
    entity_id: str
    title: str
    subtitle: str
    status_text: str = ""
    status_state: str = "unknown"
    stale: bool = False
    action_text: str = ""


class RelatedEntityList(CardFrame):
    """Scrollable primary-relationship list shared by blast and assessment overviews."""

    entity_activated = Signal(str)
    entity_action_requested = Signal(str)

    def __init__(self, title: str):
        super().__init__(title)
        self.list = QListWidget()
        self.list.setSpacing(4)
        self.list.setMinimumHeight(110)
        self.list.setMaximumHeight(225)
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setStyleSheet("QListWidget{background:transparent;border:0;}")
        self.list.itemClicked.connect(self._emit_item)
        self.layout.addWidget(self.list)

    def set_rows(self, rows, *, empty_text="No linked entities"):
        self.list.clear()
        if rows:
            self.list.setMinimumHeight(110)
            self.list.setMaximumHeight(225)
        else:
            self.list.setMinimumHeight(38)
            self.list.setMaximumHeight(38)
        for row in rows:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, row.entity_id)
            holder = QWidget()
            holder.setCursor(Qt.CursorShape.PointingHandCursor)
            layout = QVBoxLayout(holder)
            layout.setContentsMargins(7, 5, 7, 5)
            layout.setSpacing(2)
            top = QHBoxLayout()
            title = QLabel(row.title)
            title.setObjectName("RelatedEntityTitle")
            top.addWidget(title)
            top.addStretch()
            if row.status_text:
                badge = QLabel(tr(row.status_text))
                apply_status_badge(badge, row.status_state)
                top.addWidget(badge)
            if row.stale:
                stale = QLabel(tr("Stale"))
                stale.setObjectName("StaleBadge")
                top.addWidget(stale)
            if row.action_text:
                action = OverviewLinkButton(row.action_text)
                action.clicked.connect(
                    lambda _checked=False, entity_id=row.entity_id:
                    self.entity_action_requested.emit(str(entity_id))
                )
                top.addWidget(action)
            layout.addLayout(top)
            subtitle = QLabel(row.subtitle)
            subtitle.setObjectName("MutedText")
            layout.addWidget(subtitle)
            item.setSizeHint(holder.sizeHint())
            self.list.addItem(item)
            self.list.setItemWidget(item, holder)
        if not rows:
            item = QListWidgetItem(tr(empty_text))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(item)

    def _emit_item(self, item):
        entity_id = item.data(Qt.ItemDataRole.UserRole)
        if entity_id:
            self.entity_activated.emit(str(entity_id))


class RecentActivityCard(CardFrame):
    open_history_requested = Signal()

    def __init__(self, parent=None):
        super().__init__()
        self.setParent(parent)
        header = QHBoxLayout()
        title = QLabel(tr("Recent activity"))
        title.setObjectName("CardTitle")
        self.open_button = OverviewLinkButton("History ›")
        self.open_button.clicked.connect(self.open_history_requested)
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.open_button)
        self.layout.addLayout(header)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(8)
        self.layout.addLayout(self.rows)

    def set_entries(self, entries, limit=4):
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        visible = list(entries[:limit])
        if not visible:
            empty = QLabel(tr("No history yet"))
            empty.setObjectName("MutedText")
            self.rows.addWidget(empty)
            return
        for entry in visible:
            box = QWidget()
            layout = QVBoxLayout(box)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(1)
            title = QLabel(f"●  {tr(entry.title)}")
            title.setObjectName("ActivityTitle")
            stamp = entry.timestamp.strftime("%d.%m.%Y %H:%M") if entry.timestamp else "—"
            actor = entry.actor or "—"
            meta = QLabel(f"   {actor} · {stamp}")
            meta.setObjectName("MutedText")
            layout.addWidget(title)
            layout.addWidget(meta)
            self.rows.addWidget(box)


class AssessmentMatrixPreview(QWidget):
    """Large read-only DAI/FCI quadrant using already stored evaluation results."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.dai = None
        self.fci = None
        self.dai_threshold = 0.65
        self.fci_threshold = 0.60
        self.setMinimumSize(300, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def sizeHint(self):
        return QSize(350, 350)

    def set_result(self, *, dai, fci, dai_threshold=0.65, fci_threshold=0.60):
        self.dai = None if dai is None else max(0.0, min(1.0, float(dai)))
        self.fci = None if fci is None else max(0.0, min(1.0, float(fci)))
        self.dai_threshold = max(0.0, min(1.0, float(dai_threshold)))
        self.fci_threshold = max(0.0, min(1.0, float(fci_threshold)))
        self.update()

    def paintEvent(self, event):  # noqa: ARG002
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        side = max(40, min(self.width() - 64, self.height() - 48))
        left = (self.width() - side) / 2
        rect = QRectF(left, 12, side, side)
        painter.fillRect(rect, QColor("#fbfcfd"))
        painter.setPen(QPen(QColor("#cfd6de"), 1))
        painter.drawRect(rect)
        x = rect.left() + rect.width() * self.fci_threshold
        y = rect.bottom() - rect.height() * self.dai_threshold
        painter.setPen(QPen(QColor("#c1c9d2"), 1, Qt.PenStyle.DashLine))
        painter.drawLine(int(x), int(rect.top()), int(x), int(rect.bottom()))
        painter.drawLine(int(rect.left()), int(y), int(rect.right()), int(y))
        painter.setPen(QColor("#667085"))
        painter.drawText(int(rect.left()) - 30, int(rect.center().y()), "DAI")
        painter.drawText(int(rect.center().x()) - 8, int(rect.bottom()) + 24, "FCI")
        if self.dai is None or self.fci is None:
            painter.setPen(QColor("#8a94a3"))
            painter.drawText(
                rect, Qt.AlignmentFlag.AlignCenter, tr("No assessment result yet")
            )
            return
        px = rect.left() + rect.width() * self.fci
        py = rect.bottom() - rect.height() * self.dai
        painter.setPen(QPen(QColor("#ffffff"), 2))
        painter.setBrush(QColor("#1261a0"))
        painter.drawEllipse(int(px) - 7, int(py) - 7, 14, 14)


class QuickAttachmentPreview(CardFrame):
    """Stable sidebar attachment preview; resize only changes row visibility."""

    add_requested = Signal()
    open_page_requested = Signal()
    BASE_VISIBLE_ITEMS = 4
    PHOTO_COLUMNS = 2
    PHOTO_TILE_WIDTH = 106
    PHOTO_TILE_HEIGHT = 78

    def __init__(self, title: str, kind: str, *, max_items: int = BASE_VISIBLE_ITEMS):
        super().__init__()
        self.kind = kind
        self._service = None
        self._items = []
        self._max_items = max(self.BASE_VISIBLE_ITEMS, int(max_items))
        self._empty_text = ""
        self._visible_item_limit = self._max_items
        self._file_icons = QFileIconProvider() if kind == "document" else None
        self._item_rows = []
        header = QHBoxLayout()
        heading = QLabel(tr(title))
        heading.setObjectName("CardTitle")
        self.add_button = OverviewLinkButton("Add")
        self.open_button = OverviewLinkButton("Open ›")
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
        self._empty_text = empty_text
        self.add_button.setEnabled(bool(can_add))
        self.open_button.setEnabled(True)
        self._clear_content()
        if not self._items:
            label = QLabel(tr(self._empty_text))
            label.setObjectName("MutedText")
            self.content.addWidget(label)
            self.updateGeometry()
            return
        if self.kind == "photo":
            self._build_photos()
        else:
            self._build_documents()
        self.set_visible_item_limit(self._visible_item_limit)
        self.updateGeometry()

    def set_visible_item_limit(self, limit: int) -> None:
        self._visible_item_limit = max(0, min(int(limit), self._max_items))
        if not self._item_rows:
            return
        if self.kind == "photo":
            visible_rows = (self._visible_item_limit + self.PHOTO_COLUMNS - 1) // self.PHOTO_COLUMNS
            for index, row in enumerate(self._item_rows):
                row.setVisible(index < visible_rows)
        else:
            for index, row in enumerate(self._item_rows):
                row.setVisible(index < self._visible_item_limit)
        self.updateGeometry()

    def _clear_content(self):
        self._item_rows = []
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                QuickAttachmentPreview._clear_layout(item.layout())

    def _build_photos(self):
        visible = self._items[:self._max_items]
        for row_start in range(0, len(visible), self.PHOTO_COLUMNS):
            holder = QWidget()
            row_layout = QHBoxLayout(holder)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(6)
            row_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            for index in range(row_start, min(row_start + self.PHOTO_COLUMNS, len(visible))):
                attachment = visible[index]
                button = QToolButton()
                button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
                button.setText("")
                button.setToolTip(attachment.title or attachment.original_filename)
                button.setFixedSize(self.PHOTO_TILE_WIDTH, self.PHOTO_TILE_HEIGHT)
                button.setIconSize(QSize(self.PHOTO_TILE_WIDTH, self.PHOTO_TILE_HEIGHT))
                button.setStyleSheet(
                    "QToolButton{padding:0;margin:0;border:1px solid #dfe3ea;border-radius:6px;background:#f3f4f6;}"
                    "QToolButton:hover{border:1px solid #8fb4dc;}"
                    "QToolButton:pressed{border:1px solid #1261a0;}"
                )
                pixmap = self._photo_pixmap(
                    attachment, self.PHOTO_TILE_WIDTH, self.PHOTO_TILE_HEIGHT
                )
                if not pixmap.isNull():
                    button.setIcon(QIcon(pixmap))
                button.clicked.connect(
                    lambda _checked=False, i=index: self._open_photo(i)
                )
                row_layout.addWidget(button)
            row_layout.addStretch()
            self._item_rows.append(holder)
            self.content.addWidget(holder)

    def _photo_pixmap(self, attachment, width: int, height: int) -> QPixmap:
        if self._service is None:
            return QPixmap()
        path = self._service.resolve_path(attachment)
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        source_size = reader.size()
        if source_size.isValid() and source_size.width() > 0 and source_size.height() > 0:
            decode_size = source_size.scaled(
                QSize(width, height), Qt.AspectRatioMode.KeepAspectRatioByExpanding
            )
            if (
                decode_size.width() <= source_size.width()
                and decode_size.height() <= source_size.height()
            ):
                reader.setScaledSize(decode_size)
        image = reader.read()
        if image.isNull():
            return QPixmap()
        scaled = QPixmap.fromImage(image).scaled(
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
        for attachment in self._items[:self._max_items]:
            row = QToolButton()
            row.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            row.setText(attachment.title or attachment.original_filename)
            row.setToolTip(attachment.original_filename)
            if self._file_icons is not None:
                row.setIcon(
                    self._file_icons.icon(QFileInfo(attachment.original_filename))
                )
            row.setAutoRaise(True)
            row.clicked.connect(
                lambda _checked=False, a=attachment: self._open_document(a)
            )
            self._item_rows.append(row)
            self.content.addWidget(row)

    def _open_document(self, attachment):
        if self._service is not None:
            self._service.open_file(attachment)
