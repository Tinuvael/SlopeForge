"""Shared tab construction for Block, Contour Blast and Assessment Area pages."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QFileInfo, QSize, Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.localization import tr
from ui.dialogs.entity_attachment_dialog import EntityAttachmentManagerWidget
from ui.widgets.design_system import set_status_role

# Kept for callers/tests that imported the old page-local style. Presentation is
# now supplied by the application theme through the ``entityTabs`` property.
ENTITY_TABS_STYLE = ""


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
        self.setProperty("entityTabs", True)
        self.setDocumentMode(True)
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
    return tabs


class StorageAwareAttachmentManagerWidget(EntityAttachmentManagerWidget):
    """Keep metadata usable while physical file actions are unavailable."""

    def _storage_available(self) -> bool:
        return bool(getattr(self.service, "storage_available", True))

    def _build_attachment_actions(self, root):
        self.storage_notice = QLabel(
            tr(
                "File storage is unavailable for this connection. "
                "Attachment metadata remains available."
            )
        )
        self.storage_notice.setWordWrap(True)
        set_status_role(self.storage_notice, "info")
        self.storage_notice.hide()
        root.addWidget(self.storage_notice)

        actions = QHBoxLayout()
        self.action_buttons: dict[str, QPushButton] = {}
        for text_, handler, mutation in (
            ("Add", self.add, True),
            ("Open", self.open_selected, False),
            ("Open folder", self.open_folder, False),
            ("Edit metadata", self.edit, True),
            ("Delete", self.delete, True),
        ):
            button = QPushButton(tr(text_))
            button.clicked.connect(handler)
            if text_ == "Edit metadata":
                actions.addStretch()
            actions.addWidget(button)
            self.action_buttons[text_] = button
            if mutation:
                self.mutation_buttons.append(button)
        root.addLayout(actions)
        self._sync_storage_actions()

    def _sync_storage_actions(self) -> None:
        if not hasattr(self, "action_buttons"):
            return
        storage_available = self._storage_available()
        mutation_allowed = not self.read_only and not self.unsaved
        self.storage_notice.setVisible(not storage_available)
        self.action_buttons["Add"].setEnabled(storage_available and mutation_allowed)
        self.action_buttons["Open"].setEnabled(storage_available)
        self.action_buttons["Open folder"].setEnabled(
            storage_available and bool(self.owner_id)
        )
        # Metadata lives in PostgreSQL and remains editable according to the
        # normal user/archive permissions even when shared storage is absent.
        self.action_buttons["Edit metadata"].setEnabled(mutation_allowed)
        self.action_buttons["Delete"].setEnabled(storage_available and mutation_allowed)

    def refresh(self):
        super().refresh()
        self._sync_storage_actions()

    def _document_name_widget(self, item):
        if self._storage_available():
            return super()._document_name_widget(item)

        # Database-only mode must not resolve attachment.relative_path at all.
        # Use the filename solely as icon/metadata input; no filesystem probe is
        # made against the configured shared-storage location.
        wrapper = QWidget()
        wrapper.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout = QHBoxLayout(wrapper)
        layout.setContentsMargins(7, 4, 7, 4)
        layout.setSpacing(10)
        icon_label = QLabel()
        icon_label.setFixedSize(38, 38)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if self._file_icon_provider is not None:
            icon = self._file_icon_provider.icon(QFileInfo(item.original_filename))
            icon_label.setPixmap(icon.pixmap(32, 32))
        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)
        title = QLabel(item.title or Path(item.original_filename).stem)
        title.setObjectName("RelatedEntityTitle")
        filename = QLabel(item.original_filename)
        filename.setObjectName("AttachmentFilename")
        text.addWidget(title)
        text.addWidget(filename)
        layout.addWidget(icon_label)
        layout.addLayout(text, 1)
        if item.description:
            wrapper.setToolTip(item.description)
        return wrapper

    def add(self, _checked=False):
        if not self._storage_available():
            return
        return super().add(_checked)

    def open_selected(self, row=None):
        if not self._storage_available():
            return
        return super().open_selected(row)

    def open_folder(self, _checked=False):
        if not self._storage_available():
            return
        return super().open_folder(_checked)

    def delete(self, _checked=False):
        if not self._storage_available():
            return
        return super().delete(_checked)

    def _open_photo_id(self, attachment_id):
        if not self._storage_available():
            return
        return super()._open_photo_id(attachment_id)

    def _photo_tile(self, item, tile_width, image_height, wrapper_height):
        wrapper = super()._photo_tile(item, tile_width, image_height, wrapper_height)
        if not self._storage_available():
            for button in wrapper.findChildren(QToolButton):
                button.setEnabled(False)
                button.setToolTip(
                    tr("File storage is unavailable for this connection.")
                )
        return wrapper


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
    manager = StorageAwareAttachmentManagerWidget(
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
