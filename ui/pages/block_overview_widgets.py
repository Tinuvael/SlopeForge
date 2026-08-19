from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QSizePolicy

from ui.pages.entity_overview_widgets import (
    QuickAttachmentPreview,
    RelatedEntityList,
    SquareGeometryCard,
)


class BlockRelatedEntityList(RelatedEntityList):
    """Block-specific related-area rows styled like Assessment linked-event cards."""

    def __init__(self, title: str):
        super().__init__(title)
        self.list.itemSelectionChanged.connect(self._sync_row_styles)

    def set_rows(self, rows, *, empty_text="No linked entities"):
        super().set_rows(rows, empty_text=empty_text)
        for index in range(self.list.count()):
            item = self.list.item(index)
            holder = self.list.itemWidget(item)
            if holder is None:
                continue
            holder.setObjectName("BlockRelatedEntityItem")
            layout = holder.layout()
            if layout is not None:
                layout.setContentsMargins(9, 7, 14, 7)
            item.setSizeHint(holder.sizeHint())
        self._sync_row_styles()

    def _sync_row_styles(self):
        for index in range(self.list.count()):
            item = self.list.item(index)
            holder = self.list.itemWidget(item)
            if holder is None:
                continue
            selected = item.isSelected()
            border = "#2563a6" if selected else "#cfd7e2"
            width = 2 if selected else 1
            background = "#f8fbff" if selected else "#ffffff"
            holder.setStyleSheet(
                f"QWidget#BlockRelatedEntityItem{{background:{background};"
                f"border:{width}px solid {border};border-radius:5px;}}"
            )


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
    """Block Overview geometry card driven by the neighbouring stack height."""

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
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.plan.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.plan.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
