from pathlib import Path

import pytest


def source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_header_uses_project_terminology_and_real_find_shortcut():
    header = source("ui/header.py")
    assert 'QPushButton(tr("Add"))' in header
    assert 'addAction(tr("Add project"))' in header
    assert 'QPushButton("Add ▼")' not in header
    assert "QKeySequence.StandardKey.Find" in header
    assert "self.search.selectAll()" in header


def test_header_search_is_synchronized_with_project_tree():
    main = source("ui/main_window.py")
    assert "header.search.textChanged.connect(self._sync_tree_search)" in main
    assert "tree.search.textChanged.connect(self._sync_header_search)" in main
    tree = source("ui/widgets/project_tree.py")
    assert "number_query=self.search.text()" in tree
    assert "event.name.lower()" in tree


def test_normal_entity_pages_do_not_import_ui_prototype_package():
    for path in (
        "ui/main_window.py",
        "ui/pages/block_page.py",
        "ui/pages/contour_event_page.py",
        "ui/pages/assessment_area_page.py",
    ):
        assert "ui." + "prototype" + "_2d" not in source(path)


def test_all_tree_entity_types_share_show_archived_filter():
    tree = source("ui/widgets/project_tree.py")
    assert "list_areas(self.show_archived.isChecked())" in tree
    assert "list_contour_events(self.show_archived.isChecked())" in tree
    assert "show_archived=self.show_archived.isChecked()" in tree


def test_attachment_owner_ids_are_the_domain_owner_ids():
    block = source("ui/pages/block_page.py")
    contour = source("ui/pages/contour_event_page.py")
    area = source("ui/pages/assessment_area_page.py")
    assert '"blast_event", event.id' in block
    assert '"blast_event",self.blast_event.id' in contour
    assert '"assessment_evaluation",owner_id' in area
    assert "AttachmentRepository" not in block


def test_transient_page_lifecycle_is_bounded_and_disconnect_is_targeted():
    main = source("ui/main_window.py")
    assert "removeWidget(current)" in main and "current.deleteLater()" in main
    block = source("ui/pages/block_page.py")
    assert "disconnect(callback)" in block
    assert "reimport_requested.disconnect()" not in block


def _app():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_header_ctrl_f_focuses_and_selects_search_text():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from types import SimpleNamespace
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from ui.header import Header

    app = _app()
    context = SimpleNamespace(current_user=SimpleNamespace(can_edit=True))
    header = Header(context)
    header.search.setText("C-101")
    header.show()
    QTest.keyClick(header, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    app.processEvents()
    assert header.search.hasFocus()
    assert header.search.selectedText() == "C-101"
    header.close()


def test_project_tree_search_filters_real_displayed_rows(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from types import SimpleNamespace
    from ui.widgets import project_tree as module

    app = _app()
    site = SimpleNamespace(id=1, name="Project")
    domain = SimpleNamespace(id=2, name="Domain")
    blocks = [
        SimpleNamespace(id=10, domain_id=2, block_number="P-101", horizon_m=100, status="planned", is_archived=False),
        SimpleNamespace(id=11, domain_id=2, block_number="P-202", horizon_m=100, status="planned", is_archived=False),
    ]
    contours = [SimpleNamespace(id="C1", domain_id=2, name="C-101", elevation=100, is_archived=False)]
    monkeypatch.setattr(module, "SiteRepository", lambda _factory: SimpleNamespace(list_sites=lambda: [site]))
    monkeypatch.setattr(module, "DomainRepository", lambda _factory: SimpleNamespace(list_for_site=lambda _id: [domain]))
    monkeypatch.setattr(module, "BlastBlockRepository", lambda _factory: SimpleNamespace(
        list_blocks=lambda **kwargs: [b for b in blocks if not kwargs["number_query"] or kwargs["number_query"].lower() in b.block_number.lower()]
    ))
    monkeypatch.setattr(module, "NavigationRepository", lambda _factory: SimpleNamespace(
        list_areas=lambda _archived: [], list_contour_events=lambda _archived: contours
    ))
    tree = module.ProjectTree(SimpleNamespace(session_factory=object()))
    tree.search.setText("C-101")
    app.processEvents()

    labels = []
    def collect(item):
        labels.append(item.text(0))
        for index in range(item.childCount()): collect(item.child(index))
    for index in range(tree.tree.topLevelItemCount()): collect(tree.tree.topLevelItem(index))
    assert "Contour C-101" in labels
    assert "Block P-101" not in labels and "Block P-202" not in labels
    tree.close()


def _block_page(monkeypatch, *, can_edit, archived):
    from types import SimpleNamespace
    from ui.pages import block_page as module

    block = SimpleNamespace(
        id=7, domain_id=2, block_number="P-7", horizon_m=100, site_name="Project",
        domain_name="Domain", status="planned", is_archived=archived, created_at=None,
        updated_at=None, author_name="Engineer", planned_blast_date=None, comment=None,
    )
    event = SimpleNamespace(id="EVENT-7")
    attachments = SimpleNamespace(
        list_for_owner=lambda *_args: [], counts=lambda *_args: (0, 0)
    )
    controller = SimpleNamespace(event_for_block=lambda _id: event, attachments=attachments)
    monkeypatch.setattr(module, "DomainRepository", lambda _factory: SimpleNamespace())
    monkeypatch.setattr(module, "BlastBlockRepository", lambda _factory: SimpleNamespace())
    monkeypatch.setattr(module, "BlastBlockService", lambda *_args: SimpleNamespace(
        list_blocks=lambda **_kwargs: [block], get_block=lambda _id: block
    ))
    monkeypatch.setattr(module, "AuditLogRepository", lambda _factory: SimpleNamespace(list_for_block=lambda _id: []))
    monkeypatch.setattr(module, "EntityPageController", lambda *_args: controller)
    monkeypatch.setattr(module.BlockPage, "_render_engineering", lambda self, _block: None)
    context = SimpleNamespace(
        session_factory=object(), storage_root=Path("."),
        current_user=SimpleNamespace(can_edit=can_edit),
    )
    return module.BlockPage(context)


def test_editable_block_attachment_controls_are_enabled(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    page = _block_page(monkeypatch, can_edit=True, archived=False)
    assert page.photos.add_button.text() == "Manage"
    assert page.photos.add_button.isEnabled()
    assert page.documents.add_button.isEnabled()
    page.close()


def test_archived_and_viewer_block_attachment_dialogs_are_read_only(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    import sys
    from types import ModuleType

    captured = []
    fake_module = ModuleType("ui.dialogs.entity_attachment_dialog")
    class FakeDialog:
        def __init__(self, *_args, **kwargs):
            captured.append(kwargs["read_only"])
            self.tabs = type("Tabs", (), {"setCurrentIndex": lambda self, _index: None})()
        def exec(self): return 0
    fake_module.EntityAttachmentDialog = FakeDialog
    monkeypatch.setitem(sys.modules, "ui.dialogs.entity_attachment_dialog", fake_module)

    archived = _block_page(monkeypatch, can_edit=True, archived=True)
    assert archived.photos.add_button.isEnabled()
    archived._open_attachments("photo")
    viewer = _block_page(monkeypatch, can_edit=False, archived=False)
    assert viewer.documents.add_button.isEnabled()
    viewer._open_attachments("document")
    assert captured == [True, True]
    archived.close(); viewer.close()


def test_attachment_dialog_disables_all_mutations_in_read_only_mode():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from types import SimpleNamespace
    from ui.dialogs.entity_attachment_dialog import EntityAttachmentDialog

    _app()
    service = SimpleNamespace(list_for_owner=lambda *_args: [])
    dialog = EntityAttachmentDialog(service, "blast_event", "EVENT-1", read_only=True)
    assert dialog.mutation_buttons
    assert all(not button.isEnabled() for button in dialog.mutation_buttons)
    dialog.close()


def _bare_main_window():
    from types import SimpleNamespace
    from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget
    from ui.main_window import MainWindow

    window = MainWindow.__new__(MainWindow)
    QMainWindow.__init__(window)
    window.page_stack = QStackedWidget(window)
    window.block_page = QWidget()
    window.page_stack.addWidget(window.block_page)
    window.assessment_page = None
    window._guard_leave = lambda: True
    window.context = SimpleNamespace()
    window.domain_repo = SimpleNamespace(get=lambda _id: SimpleNamespace(site=SimpleNamespace(name="Project")))
    window._set_context = lambda *_args, **_kwargs: None
    return window


def test_failed_assessment_page_construction_preserves_current_widget(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    import sys
    from types import ModuleType
    from PySide6.QtWidgets import QWidget
    from ui.main_window import MainWindow

    _app()
    window = _bare_main_window()
    current = QWidget()
    window.page_stack.addWidget(current)
    window.page_stack.setCurrentWidget(current)
    fake_module = ModuleType("ui.pages.assessment_area_page")
    class BrokenAreaPage:
        def __init__(self, *_args, **_kwargs): raise RuntimeError("construction failed")
    fake_module.AssessmentAreaPage = BrokenAreaPage
    monkeypatch.setitem(sys.modules, "ui.pages.assessment_area_page", fake_module)
    monkeypatch.setattr("ui.main_window.QMessageBox.critical", lambda *_args: None)

    assert MainWindow.open_area_from_tree(window, "A1", 2, 1, "Domain") is False
    assert window.page_stack.currentWidget() is current
    assert window.page_stack.count() == 2
    window.close()


def test_repeated_transient_navigation_keeps_stack_bounded():
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from PySide6.QtWidgets import QWidget

    app = _app()
    window = _bare_main_window()
    for kind in ("Site", "Domain", "Area", "Contour") * 10:
        page = QWidget()
        page.setObjectName(kind)
        window._activate_page(page)
        app.sendPostedEvents()
        app.processEvents()
        assert window.page_stack.count() <= 2
    window.close()


def test_all_technical_card_catalogue_keys_have_english_presentation_labels():
    import re
    from domain.blasting.technical_card import (
        CONTOUR_GROUP_TYPES, CONTROLLED_BLASTING_METHODS, PRODUCTION_GROUP_TYPES,
    )
    from ui.presentation_labels import CONTROLLED_BLASTING_LABELS, technical_group_label

    for catalogue in (PRODUCTION_GROUP_TYPES, CONTOUR_GROUP_TYPES):
        for key in catalogue:
            label = technical_group_label(key)
            assert label
            assert label != key
            assert label != key.replace("_", " ")
            assert not re.search(r"[А-Яа-яЁё]", label)
    for key in CONTROLLED_BLASTING_METHODS:
        label = CONTROLLED_BLASTING_LABELS.get(key, "")
        assert label and label != key and label != key.replace("_", " ")
        assert not re.search(r"[А-Яа-яЁё]", label)


def test_dynamic_domain_validation_messages_are_presented_in_english():
    from ui.presentation_labels import domain_message

    assert domain_message("Не заполнено: Дата оценки, Инспектор") == "Missing required fields: Assessment date, Inspector"
    assert domain_message("Не удалось импортировать CSV: Не удалось прочитать файл как UTF-8. Сохраните CSV в UTF-8 или UTF-8 BOM.") == (
        "Could not import CSV: Could not read the file as UTF-8. Save the CSV as UTF-8 or UTF-8 BOM."
    )
    assert domain_message("Dataset 'D-1' не найден") == "Dataset 'D-1' was not found"
    assert domain_message("BlastEvent 'E-1' не найден") == "BlastEvent 'E-1' was not found"
    incomplete = domain_message("Не заполнено: Недобор угла относительно проекта, °, Дата оценки, Инспектор")
    assert incomplete.startswith("Missing required fields: Bench face angle shortfall")
    assert not __import__("re").search(r"[А-Яа-яЁё]", incomplete)
    assert domain_message("Добавьте группу бурения; Выберите метод контурного взрывания") == (
        "Add a drilling group; Select a controlled blasting method"
    )


def test_zero_revision_evaluation_owner_is_reused_for_first_draft():
    from datetime import date, datetime, timezone
    from domain.geometry.types import PlanPoint, PlanPolygon
    from domain.assessment.entities import AssessmentArea, AssessmentAreaGeometryRevision
    from application.state.assessment_domain_state import AssessmentDomainState
    from domain.assessment.evaluation import AssessmentAreaEvaluationService
    from application.services.entity_editing import AssessmentEditingSession

    polygon = PlanPolygon((PlanPoint(0, 0), PlanPoint(1, 0), PlanPoint(1, 1), PlanPoint(0, 0)))
    geometry = AssessmentAreaGeometryRevision("AGR-1", "AREA-1", 1, datetime.now(timezone.utc), "DATASET-1", polygon, polygon, 100, 110, ())
    area = AssessmentArea("AREA-1", "Wall", date.today(), [geometry], geometry.id)
    state = AssessmentDomainState(assessment_areas=[area])
    controller = AssessmentEditingSession.__new__(AssessmentEditingSession)
    controller.state = state
    controller.evaluations = AssessmentAreaEvaluationService(state)
    from application.ports.domain_version import DomainWriteResult
    class Writes:
        def __getattr__(self, name):
            return lambda domain_id, expected_version, *args: DomainWriteResult(expected_version + 1)
    controller.can_edit = True; controller.domain_id = 1; controller.expected_version = 0
    controller._writes = Writes()

    transient, _draft = controller.evaluation_draft(area)
    owner = controller.ensure_evaluation_owner(area, transient)
    assert owner is transient and owner.revisions == [] and len(state.evaluations) == 1
    assert controller.expected_version == 1

    reused, first_draft = controller.evaluation_draft(area)
    assert reused is owner and first_draft.evaluation_id == owner.id
    controller.save_evaluation(reused, first_draft, "draft")
    assert len(state.evaluations) == 1
    assert reused.revisions[0].revision_number == 1
    assert reused.revisions[0].evaluation_id == owner.id


def test_attachment_owner_can_be_prepared_without_an_intermediate_save():
    from datetime import date, datetime, timezone
    from domain.geometry.types import PlanPoint, PlanPolygon
    from domain.assessment.entities import AssessmentArea, AssessmentAreaGeometryRevision
    from application.state.assessment_domain_state import AssessmentDomainState
    from domain.assessment.evaluation import AssessmentAreaEvaluationService
    from application.services.entity_editing import AssessmentEditingSession

    polygon = PlanPolygon((PlanPoint(0, 0), PlanPoint(1, 0), PlanPoint(1, 1), PlanPoint(0, 0)))
    geometry = AssessmentAreaGeometryRevision("AGR-1", "AREA-1", 1, datetime.now(timezone.utc), "DATASET-1", polygon, polygon, 100, 110, ())
    area = AssessmentArea("AREA-1", "Wall", date.today(), [geometry], geometry.id)
    state = AssessmentDomainState(assessment_areas=[area])
    controller = AssessmentEditingSession.__new__(AssessmentEditingSession)
    controller.state = state; controller.evaluations = AssessmentAreaEvaluationService(state)
    saves = []; controller.can_edit = True; controller.save = lambda: saves.append(True)

    transient, _draft = controller.evaluation_draft(area)
    owner, rollback = controller.prepare_evaluation_attachment_owner(area, transient)
    assert rollback is not None and owner is transient and state.evaluations == [owner] and saves == []
    rollback()
    assert state.evaluations == [] and saves == []

    state.evaluations.append(owner)
    existing, rollback = controller.prepare_evaluation_attachment_owner(area, transient)
    assert existing is owner and rollback is None
    assert state.evaluations == [owner]


def test_assessment_attachment_ui_has_no_saved_revision_gate():
    area = source("ui/pages/assessment_area_page.py")
    assert "Save an assessment draft first" not in area
    assert "prepare_evaluation_attachment_owner" in area
    assert "EntityAttachmentManagerWidget" in area
    assert "ensure_owner=ensure_owner" in area


def test_block_attachment_tabs_are_real_and_ordered():
    block = source("ui/pages/block_page.py")
    expected = ["General information", "Geomechanics", "Blast design", "Execution fact", "Photos", "Documents", "History"]
    positions = [block.index(f'"{title}"') for title in expected]
    assert positions == sorted(positions)
    assert 'self.tabs.addTab(self.photos_tab, tr("Photos"))' in block
    assert 'self.tabs.addTab(self.documents_tab, tr("Documents"))' in block
    assert 'self.tabs.addTab(EmptySection(), "Documents")' not in block


def test_block_attachment_tabs_select_the_requested_manager_tab(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    import sys
    from types import ModuleType

    calls = []
    fake_module = ModuleType("ui.dialogs.entity_attachment_dialog")
    class FakeTabs:
        def setCurrentIndex(self, index): calls[-1]["tab"] = index
    class FakeDialog:
        def __init__(self, _service, owner_type, owner_id, _parent, read_only):
            calls.append({"owner_type": owner_type, "owner_id": owner_id, "read_only": read_only})
            self.tabs = FakeTabs()
        def exec(self): return 0
    fake_module.EntityAttachmentDialog = FakeDialog
    monkeypatch.setitem(sys.modules, "ui.dialogs.entity_attachment_dialog", fake_module)
    page = _block_page(monkeypatch, can_edit=True, archived=False)
    page._open_attachments("photo")
    page._open_attachments("document")
    assert [(item["owner_type"], item["owner_id"], item["tab"]) for item in calls] == [
        ("blast_event", "EVENT-7", 0), ("blast_event", "EVENT-7", 1),
    ]
    page.close()
