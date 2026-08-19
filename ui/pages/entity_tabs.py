"""Shared tab construction for Block, Contour Blast and Assessment Area pages."""
from __future__ import annotations

from collections.abc import Callable

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
    """Ignore tall Overview hints only while Overview is active.

    The unified Overview deliberately contains geometry cards whose vertical
    hints must not drive the whole entity page.  Applying ``Ignored`` to the
    QTabWidget permanently also suppresses the preferred height of the embedded
    Technical Card scroll areas, which can leave Blast design / Execution fact
    occupying only part of the available viewport.  Switch the policy with the
    active tab instead: Overview keeps the stable no-feedback layout, while all
    working tabs expand normally to the available page height.
    """

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.currentChanged.connect(self._sync_vertical_policy)

    def _sync_vertical_policy(self, index: int) -> None:
        vertical = (
            QSizePolicy.Policy.Ignored
            if index <= 0
            else QSizePolicy.Policy.Expanding
        )
        policy = self.sizePolicy()
        if policy.horizontalPolicy() == QSizePolicy.Policy.Expanding and policy.verticalPolicy() == vertical:
            return
        self.setSizePolicy(QSizePolicy.Policy.Expanding, vertical)
        current = self.currentWidget()
        if current is not None:
            current.updateGeometry()
        self.updateGeometry()


def create_entity_tabs(parent: QWidget | None = None) -> QTabWidget:
    """Create the standard entity tab container used by all operational pages."""
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