from __future__ import annotations

from pathlib import Path

import pytest

from application.services.attachments import EntityAttachmentService
from application.state.assessment_domain_state import AssessmentDomainState


def test_attachment_service_preserves_per_file_metadata_atomically(tmp_path):
    first = tmp_path / "face_before.jpg"
    second = tmp_path / "face_after.jpg"
    first.write_bytes(b"first")
    second.write_bytes(b"second")
    state = AssessmentDomainState()
    service = EntityAttachmentService(state, storage_path=tmp_path / "state.json")

    added = service.add_files_with_metadata(
        "blast_event", "BE-TEST", "photo",
        [
            (first, {"title": "face_before", "subtype": "before_blast"}),
            (second, {"title": "face_after", "subtype": "after_blast"}),
        ],
    )

    assert [item.title for item in added] == ["face_before", "face_after"]
    assert [item.subtype for item in added] == ["before_blast", "after_blast"]
    assert all(service.resolve_path(item).is_file() for item in added)


def test_photo_metadata_dialog_prefills_title_from_filename(tmp_path):
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.dialogs.entity_attachment_dialog import AttachmentMetadataDialog

    app = widgets.QApplication.instance() or widgets.QApplication([])
    source = tmp_path / "B630e_wall_01.jpg"
    source.write_bytes(b"not-an-image-is-fine-for-title-test")

    dialog = AttachmentMetadataDialog("blast_event", "photo", source_path=source)

    assert dialog.title.text() == "B630e_wall_01"
    dialog.close()
    app.processEvents()


def test_photo_manager_reviews_each_selected_file_and_uses_embedded_gallery(tmp_path, monkeypatch):
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    gui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    from ui.dialogs.entity_attachment_dialog import AttachmentMetadataDialog, EntityAttachmentManagerWidget

    app = widgets.QApplication.instance() or widgets.QApplication([])
    sources = []
    for name in ("before.jpg", "after.jpg"):
        path = tmp_path / name
        pixmap = gui.QPixmap(40, 30)
        pixmap.fill()
        assert pixmap.save(str(path), "JPG")
        sources.append(path)

    state = AssessmentDomainState()
    service = EntityAttachmentService(state, storage_path=tmp_path / "state.json")
    manager = EntityAttachmentManagerWidget(service, "blast_event", "BE-TEST", "photo")

    monkeypatch.setattr(
        widgets.QFileDialog,
        "getOpenFileNames",
        staticmethod(lambda *_args, **_kwargs: ([str(path) for path in sources], "Photos")),
    )
    reviewed = []

    def fake_exec(dialog):
        reviewed.append(dialog.windowTitle())
        dialog.category.setCurrentIndex(0 if len(reviewed) == 1 else 4)
        return widgets.QDialog.DialogCode.Accepted

    monkeypatch.setattr(AttachmentMetadataDialog, "exec", fake_exec)
    manager.add()

    items = service.list_for_owner("blast_event", "BE-TEST", "photo")
    assert len(reviewed) == 2
    assert reviewed[0].endswith("1/2") and reviewed[1].endswith("2/2")
    assert {item.title for item in items} == {"before", "after"}
    assert {item.subtype for item in items} == {"before_blast", "after_blast"}
    assert manager.table is None

    tiles = manager.findChildren(widgets.QToolButton, "PhotoTile")
    titles = [
        label
        for label in manager.findChildren(widgets.QLabel, "RelatedEntityTitle")
        if label.parentWidget() is not None
        and label.parentWidget().findChild(widgets.QToolButton, "PhotoTile") is not None
    ]
    assert len(tiles) == 2
    assert {label.text() for label in titles} == {"before", "after"}
    assert all(not tile.text() for tile in tiles)

    tiles[0].click()
    app.processEvents()
    assert manager.stack.currentWidget() is manager.viewer_page
    selected = manager._selected()
    assert selected is not None
    assert manager.viewer_title.text() == selected.title
    assert manager.viewer_category.text()
    assert manager.viewer_date.text() == selected.file_date.strftime("%d.%m.%Y")
    assert manager.viewer_file.text() == selected.original_filename

    manager._show_gallery()
    assert manager.stack.currentWidget() is manager.gallery_page

    manager.close()
    app.processEvents()
