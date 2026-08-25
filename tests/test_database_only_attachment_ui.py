from __future__ import annotations

from PySide6.QtWidgets import QApplication

from ui.pages.entity_tabs import StorageAwareAttachmentManagerWidget


class FakeAttachmentService:
    def __init__(self, storage_available: bool):
        self.storage_available = storage_available

    def list_for_owner(self, *_args, **_kwargs):
        return []


def _app():
    return QApplication.instance() or QApplication([])


def test_database_only_attachment_tab_disables_physical_actions_but_keeps_metadata_edit():
    _app()
    manager = StorageAwareAttachmentManagerWidget(
        FakeAttachmentService(False),
        "blast_event",
        "BE-001",
        "document",
        read_only=False,
    )

    assert manager.action_buttons["Add"].isEnabled() is False
    assert manager.action_buttons["Open"].isEnabled() is False
    assert manager.action_buttons["Open folder"].isEnabled() is False
    assert manager.action_buttons["Delete"].isEnabled() is False
    assert manager.action_buttons["Edit metadata"].isEnabled() is True
    assert manager.storage_notice.isHidden() is False

    manager.deleteLater()


def test_full_attachment_tab_preserves_normal_action_availability():
    _app()
    manager = StorageAwareAttachmentManagerWidget(
        FakeAttachmentService(True),
        "blast_event",
        "BE-001",
        "document",
        read_only=False,
    )

    assert manager.action_buttons["Add"].isEnabled() is True
    assert manager.action_buttons["Open"].isEnabled() is True
    assert manager.action_buttons["Open folder"].isEnabled() is True
    assert manager.action_buttons["Delete"].isEnabled() is True
    assert manager.action_buttons["Edit metadata"].isEnabled() is True
    assert manager.storage_notice.isHidden() is True

    manager.deleteLater()


def test_database_only_respects_application_read_only_permissions_for_metadata():
    _app()
    manager = StorageAwareAttachmentManagerWidget(
        FakeAttachmentService(False),
        "blast_event",
        "BE-001",
        "document",
        read_only=True,
    )

    assert manager.action_buttons["Edit metadata"].isEnabled() is False
    assert manager.action_buttons["Add"].isEnabled() is False
    assert manager.action_buttons["Delete"].isEnabled() is False

    manager.deleteLater()
