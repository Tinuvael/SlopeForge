from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.localization import tr
from ui.pages.entity_overview_widgets import (
    QuickAttachmentPreview,
    RecentActivityCard,
    RelatedEntityList,
    SquareGeometryCard,
)


class BlockRelatedEntityList(RelatedEntityList):
    """Fixed-height Block relationship card with internally scrollable rows."""

    CARD_HEIGHT = 104
    LIST_HEIGHT = 60
    STATE_COLORS = {
        "completed": ("#edf8f0", "#58a66a"),
        "assessed": ("#edf8f0", "#58a66a"),
        "in_progress": ("#f4f8fd", "#9bc2e8"),
        "planned": ("#f4f8fd", "#9bc2e8"),
        "draft": ("#f7f8fa", "#cfd7e2"),
        "in_preparation": ("#f7f8fa", "#cfd7e2"),
        "unknown": ("#ffffff", "#cfd7e2"),
    }

    def __init__(self, title: str):
        super().__init__(title)
        self.setFixedHeight(self.CARD_HEIGHT)
        self.layout.setContentsMargins(14, 12, 18, 12)
        self.layout.setSpacing(4)
        self.list.setMinimumHeight(self.LIST_HEIGHT)
        self.list.setMaximumHeight(self.LIST_HEIGHT)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.empty_label = QLabel()
        self.empty_label.setObjectName("MutedText")
        self.empty_label.setFixedHeight(self.LIST_HEIGHT)
        self.empty_label.setContentsMargins(2, 0, 0, 0)
        self.empty_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.empty_label.hide()
        self.layout.addWidget(self.empty_label)
        self.list.itemSelectionChanged.connect(self._sync_row_styles)

    def set_rows(self, rows, *, empty_text="No linked entities"):
        rows = list(rows)
        if not rows:
            self.list.clear()
            self.list.hide()
            self.empty_label.setText(tr(empty_text))
            self.empty_label.show()
            self.updateGeometry()
            return

        self.empty_label.hide()
        self.list.show()
        super().set_rows(rows, empty_text=empty_text)
        # The shared list changes its own min/max height depending on row count;
        # Block deliberately keeps a constant viewport and scrolls long lists.
        self.list.setMinimumHeight(self.LIST_HEIGHT)
        self.list.setMaximumHeight(self.LIST_HEIGHT)
        for index, row in enumerate(rows):
            item = self.list.item(index)
            item.setData(Qt.ItemDataRole.UserRole + 1, row.status_state or "unknown")
            holder = self.list.itemWidget(item)
            if holder is None:
                continue
            holder.setObjectName("BlockRelatedEntityItem")
            holder.setSizePolicy(
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Fixed,
            )
            layout = holder.layout()
            if layout is not None:
                layout.setContentsMargins(9, 7, 14, 7)
            # Do not let the natural width of title + status + action enlarge the
            # QListWidget item beyond its viewport. Only the row height is a hint;
            # QListView supplies the current viewport width.
            item.setSizeHint(QSize(0, holder.sizeHint().height()))
        self._sync_row_styles()
        self.updateGeometry()

    def _sync_row_styles(self):
        for index in range(self.list.count()):
            item = self.list.item(index)
            holder = self.list.itemWidget(item)
            if holder is None:
                continue
            state = str(item.data(Qt.ItemDataRole.UserRole + 1) or "unknown")
            background, accent = self.STATE_COLORS.get(state, self.STATE_COLORS["unknown"])
            selected = item.isSelected()
            border = "#2563a6" if selected else accent
            width = 2 if selected else 1
            if selected:
                background = "#f8fbff"
            holder.setStyleSheet(
                f"QWidget#BlockRelatedEntityItem{{background:{background};"
                f"border:{width}px solid {border};border-radius:5px;}}"
            )


class BlockRecentActivityCard(RecentActivityCard):
    """Four stable activity slots so Block cards do not change height by history count."""

    SLOT_COUNT = 4
    SLOT_HEIGHT = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows.setSpacing(4)

    def set_entries(self, entries, limit=4):
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        visible = list(entries[: min(int(limit), self.SLOT_COUNT)])
        for index in range(self.SLOT_COUNT):
            slot = QWidget()
            slot.setFixedHeight(self.SLOT_HEIGHT)
            layout = QVBoxLayout(slot)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(0)
            if index < len(visible):
                entry = visible[index]
                title = QLabel(f"●  {tr(entry.title)}")
                title.setObjectName("ActivityTitle")
                stamp = entry.timestamp.strftime("%d.%m.%Y %H:%M") if entry.timestamp else "—"
                actor = entry.actor or "—"
                meta = QLabel(f"   {actor} · {stamp}")
                meta.setObjectName("MutedText")
                layout.addWidget(title)
                layout.addWidget(meta)
            elif index == 0 and not visible:
                empty = QLabel(tr("No history yet"))
                empty.setObjectName("MutedText")
                layout.addWidget(empty)
            self.rows.addWidget(slot)


class BlockAttachmentPreview(QuickAttachmentPreview):
    """Suppress transient old preview rows while a Block is being rerendered."""

    def set_items(self, service, items, empty_text: str, *, can_add=True) -> None:
        for index in range(self.content.count()):
            item = self.content.itemAt(index)
            widget = item.widget()
            if widget is not None:
                widget.hide()
        self.setUpdatesEnabled(False)
        try:
            super().set_items(service, items, empty_text, can_add=can_add)
        finally:
            self.setUpdatesEnabled(True)
        self.update()


class BlockGeometryCard(SquareGeometryCard):
    """Geometry card whose vertical hint never drives the Block Overview row."""

    def __init__(
        self,
        title="Plan / geometry",
        *,
        action_label="Reimport",
        enforce_square=False,
        parent=None,
    ):
        super().__init__(
            title,
            action_label=action_label,
            enforce_square=False,
            parent=parent,
        )
        self.setMinimumHeight(0)
        self.setMaximumHeight(16777215)
        # The three cards on the left are the vertical source of truth. Ignoring
        # this widget's inherited 440 px height hint lets the row be sized by them;
        # QHBoxLayout then gives the plan exactly the same row height.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.plan.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.plan.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

    def sizeHint(self):
        return QSize(540, 0)

    def minimumSizeHint(self):
        return QSize(470, 0)


class BlockSectionHost(QWidget):
    """Permanent QTabWidget page; only its inner editor is replaced."""

    def __init__(self, content: QWidget | None = None, parent=None):
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self._content: QWidget | None = None
        if content is not None:
            self.set_content(content)

    def set_content(self, widget: QWidget) -> None:
        old = self._content
        if old is widget:
            return
        if old is not None:
            self._layout.removeWidget(old)
            old.hide()
            old.setParent(None)
            old.deleteLater()
        self._content = widget
        widget.setParent(self)
        widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._layout.addWidget(widget)
        widget.show()
        self.updateGeometry()
