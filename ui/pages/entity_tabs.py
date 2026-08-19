"""Shared tab construction for Block, Contour Blast and Assessment Area pages."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QTabWidget, QVBoxLayout, QWidget

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


def create_entity_tabs(parent: QWidget | None = None) -> QTabWidget:
    """Create the standard entity tab container used by all operational pages.

    The operational pages deliberately choose their own stable vertical policy.
    Do not change that policy from ``currentChanged``: Technical Card pages have
    much larger size hints than Overview, and propagating those hints while a
    maximized Windows window is live can increase the top-level minimum height
    beyond the available work area.  The current page still receives the full
    QTabWidget viewport; embedded engineering hosts are responsible for filling
    that viewport.
    """
    tabs = QTabWidget(parent)
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