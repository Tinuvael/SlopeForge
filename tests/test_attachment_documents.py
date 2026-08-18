from __future__ import annotations

from datetime import date

import pytest

from application.services.attachments import EntityAttachmentService
from application.state.assessment_domain_state import AssessmentDomainState


def test_document_batch_dialog_prefills_titles_and_applies_bulk_values(tmp_path):
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    core = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    from ui.dialogs.entity_attachment_dialog import DocumentBatchDialog

    app = widgets.QApplication.instance() or widgets.QApplication([])
    first = tmp_path / "blast_design.pdf"; first.write_bytes(b"pdf")
    second = tmp_path / "drilling_report.xlsx"; second.write_bytes(b"xlsx")

    dialog = DocumentBatchDialog("blast_event", [first, second])
    assert [row[1].text() for row in dialog.row_editors] == ["blast_design", "drilling_report"]

    target_category = dialog.bulk_category.findData("drilling_report")
    dialog.bulk_category.setCurrentIndex(target_category)
    dialog._apply_category()
    target_date = core.QDate(2026, 8, 18)
    dialog.bulk_date.setDate(target_date)
    dialog._apply_date()

    entries = dialog.entries()
    assert [metadata["subtype"] for _path, metadata in entries] == ["drilling_report", "drilling_report"]
    assert [metadata["file_date"] for _path, metadata in entries] == [date(2026, 8, 18), date(2026, 8, 18)]
    dialog.close(); app.processEvents()


def test_document_manager_uses_compact_four_column_list(tmp_path):
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.dialogs.entity_attachment_dialog import EntityAttachmentManagerWidget

    app = widgets.QApplication.instance() or widgets.QApplication([])
    source = tmp_path / "passport.pdf"; source.write_bytes(b"pdf")
    state = AssessmentDomainState()
    service = EntityAttachmentService(state, storage_path=tmp_path / "state.json")
    service.add_files_with_metadata(
        "blast_event", "BE-DOC", "document",
        [(source, {"title": "Blast passport", "subtype": "blast_design", "file_date": date(2026, 8, 18)})],
    )

    manager = EntityAttachmentManagerWidget(service, "blast_event", "BE-DOC", "document")
    assert manager.table.columnCount() == 4
    assert [manager.table.horizontalHeaderItem(i).text() for i in range(4)] == [
        "Document", "Category", "Date", "Size"
    ]
    assert manager.table.rowCount() == 1
    assert manager.table.cellWidget(0, 0) is not None
    assert manager.table.item(0, 1).text() == "Blast design"
    assert manager.table.item(0, 2).text() == "18.08.2026"
    assert manager._selected().title == "Blast passport"
    manager.close(); app.processEvents()


def test_document_add_reviews_batch_once_and_persists_per_file_metadata(tmp_path, monkeypatch):
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.dialogs.entity_attachment_dialog import DocumentBatchDialog, EntityAttachmentManagerWidget

    app = widgets.QApplication.instance() or widgets.QApplication([])
    first = tmp_path / "design.pdf"; first.write_bytes(b"pdf")
    second = tmp_path / "survey.dxf"; second.write_bytes(b"dxf")
    state = AssessmentDomainState()
    service = EntityAttachmentService(state, storage_path=tmp_path / "state.json")
    manager = EntityAttachmentManagerWidget(service, "blast_event", "BE-DOC", "document")

    monkeypatch.setattr(
        widgets.QFileDialog, "getOpenFileNames",
        staticmethod(lambda *_args, **_kwargs: ([str(first), str(second)], "Documents")),
    )
    calls = []

    def fake_exec(dialog):
        calls.append(dialog)
        dialog.row_editors[0][2].setCurrentIndex(dialog.row_editors[0][2].findData("blast_design"))
        dialog.row_editors[1][2].setCurrentIndex(dialog.row_editors[1][2].findData("survey"))
        return widgets.QDialog.DialogCode.Accepted

    monkeypatch.setattr(DocumentBatchDialog, "exec", fake_exec)
    manager.add()

    items = service.list_for_owner("blast_event", "BE-DOC", "document")
    assert len(calls) == 1
    assert {item.title for item in items} == {"design", "survey"}
    assert {item.subtype for item in items} == {"blast_design", "survey"}
    assert manager.table.rowCount() == 2
    manager.close(); app.processEvents()


def test_attachment_service_exposes_separate_photo_and_document_folders(tmp_path):
    state = AssessmentDomainState()
    service = EntityAttachmentService(state, storage_path=tmp_path / "state.json")

    photo_folder = service.attachment_folder("blast_event", "BE-FOLDERS", "photo")
    document_folder = service.attachment_folder("blast_event", "BE-FOLDERS", "document")

    assert photo_folder.name == "photos"
    assert document_folder.name == "documents"
    assert photo_folder.parent == document_folder.parent
    assert photo_folder.is_dir()
    assert document_folder.is_dir()


def test_attachment_manager_opens_current_kind_folder():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.dialogs.entity_attachment_dialog import EntityAttachmentManagerWidget

    app = widgets.QApplication.instance() or widgets.QApplication([])

    class StubService:
        def __init__(self): self.calls = []
        def list_for_owner(self, *_args): return []
        def open_attachment_folder(self, owner_type, owner_id, kind):
            self.calls.append((owner_type, owner_id, kind)); return True

    photo_service = StubService()
    document_service = StubService()
    photo = EntityAttachmentManagerWidget(photo_service, "blast_event", "BE-X", "photo")
    document = EntityAttachmentManagerWidget(document_service, "blast_event", "BE-X", "document")

    photo.open_folder(); document.open_folder()

    assert photo_service.calls == [("blast_event", "BE-X", "photo")]
    assert document_service.calls == [("blast_event", "BE-X", "document")]
    photo.close(); document.close(); app.processEvents()


def test_shared_entity_attachment_tab_and_native_scrollbar_contract():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.entity_tabs import ENTITY_TABS_STYLE, create_attachment_tab_page, create_entity_tabs

    app = widgets.QApplication.instance() or widgets.QApplication([])

    class StubService:
        def list_for_owner(self, *_args): return []

    tabs = create_entity_tabs()
    page, manager = create_attachment_tab_page(StubService(), "blast_event", "BE-X", "photo")
    tabs.addTab(page, "Photos")

    assert tabs.styleSheet() == ENTITY_TABS_STYLE
    assert manager.parent() is page
    assert page.layout().indexOf(manager) == 0
    assert manager.gallery_scroll.styleSheet() == ""
    assert manager.gallery_scroll.verticalScrollBar().styleSheet() == ""

    tabs.close(); app.processEvents()
