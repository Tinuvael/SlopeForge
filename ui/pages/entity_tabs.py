"""Shared tab construction for Block, Contour Blast and Assessment Area pages."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget, QSizePolicy

from ui.dialogs.entity_attachment_dialog import EntityAttachmentManagerWidget


ENTITY_TABS_STYLE = """
QTabWidget::pane {
    border: 1px solid #dfe3ea;
    border-radius: 6px;
}
QTabBar::tab:selected {
    color: #0b63ce;
}
"""


class EntityTabWidget(QTabWidget):
    """Stable viewport for operational entity pages.

    Block/Contour Technical Card pages have intentionally tall scrollable
    contents. A normal expanding QTabWidget propagates the active page's large
    vertical size hint into the QMainWindow; on maximized Windows windows that
    can raise the top-level minimum height beyond the available work area and
    push the bottom of the application under the taskbar.

    Conversely, QSizePolicy.Ignored removes ExpandFlag, so the tab widget keeps
    roughly its natural height and leaves unused space above the engineering
    action buttons. The Technical Card then looks vertically clipped.

    This widget separates those concerns: it is always vertically Expanding so
    it consumes the complete viewport allocated by the page layout, while its
    vertical size hints are zero so the current tab can never resize the outer
    window. Scrollable children still keep their own content sizes and scroll
    normally inside that stable viewport.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumHeight(0)
        QTabWidget.setSizePolicy(
            self,
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self.currentChanged.connect(self._enforce_viewport_policy)

    def _enforce_viewport_policy(self, _index: int = -1) -> None:
        policy = self.sizePolicy()
        if (
            policy.horizontalPolicy() != QSizePolicy.Policy.Expanding
            or policy.verticalPolicy() != QSizePolicy.Policy.Expanding
        ):
            QTabWidget.setSizePolicy(
                self,
                QSizePolicy.Policy.Expanding,
                QSizePolicy.Policy.Expanding,
            )
        self.updateGeometry()

    def showEvent(self, event):
        self._enforce_viewport_policy(self.currentIndex())
        super().showEvent(event)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(hint.width(), 0)

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(hint.width(), 0)


def create_entity_tabs(parent: QWidget | None = None) -> QTabWidget:
    """Create the standard stable entity tab container."""
    tabs = EntityTabWidget(parent)
    tabs.setStyleSheet(ENTITY_TABS_STYLE)
    return tabs


def create_attachment_tab_page(
    service,
    owner_type: str,
    owner_id,
    kind: str,
    *,
    read_only: bool = False,
    ensure_owner: Callable | None = None,
) -> tuple[QWidget, EntityAttachmentManagerWidget]:
    """Build one Photos/Documents tab with identical widget/layout hierarchy everywhere."""
    page = QWidget()
    layout = QVBoxLayout(page)
    manager = EntityAttachmentManagerWidget(
        service,
        owner_type,
        owner_id,
        kind,
        page,
        read_only=read_only,
        ensure_owner=ensure_owner,
    )
    layout.addWidget(manager)
    return page, manager