from pathlib import Path


def source(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_header_uses_project_terminology_and_real_find_shortcut():
    header = source("ui/header.py")
    assert 'QPushButton("Add")' in header
    assert 'addAction("Add project")' in header
    assert 'QPushButton("Add ▼")' not in header
    assert "QKeySequence.StandardKey.Find" in header
    assert "self.search.selectAll()" in header


def test_header_search_is_synchronized_with_project_tree():
    main = source("ui/main_window.py")
    assert "header.search.textChanged.connect(self._sync_tree_search)" in main
    assert "tree.search.textChanged.connect(self._sync_header_search)" in main
    tree = source("widgets/project_tree.py")
    assert "number_query=self.search.text()" in tree
    assert "event.name.lower()" in tree


def test_normal_entity_pages_do_not_import_ui_prototype_package():
    for path in (
        "ui/main_window.py",
        "ui/pages/block_page.py",
        "ui/pages/contour_event_page.py",
        "ui/pages/assessment_area_page.py",
    ):
        assert "ui.prototype_2d" not in source(path)


def test_all_tree_entity_types_share_show_archived_filter():
    tree = source("widgets/project_tree.py")
    assert "list_areas(self.show_archived.isChecked())" in tree
    assert "list_contour_events(self.show_archived.isChecked())" in tree
    assert "show_archived=self.show_archived.isChecked()" in tree


def test_attachment_owner_ids_are_the_domain_owner_ids():
    block = source("ui/pages/block_page.py")
    contour = source("ui/pages/contour_event_page.py")
    area = source("ui/pages/assessment_area_page.py")
    assert '"blast_event", event.id' in block
    assert '"blast_event",self.blast_event.id' in contour
    assert '"assessment_evaluation",self.evaluation.id' in area
    assert "AttachmentRepository" not in block


def test_transient_page_lifecycle_is_bounded_and_disconnect_is_targeted():
    main = source("ui/main_window.py")
    assert "removeWidget(current)" in main and "current.deleteLater()" in main
    block = source("ui/pages/block_page.py")
    assert "disconnect(callback)" in block
    assert "reimport_requested.disconnect()" not in block
