from datetime import date
from types import SimpleNamespace

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QApplication, QLineEdit


def _labels(tree):
    result = []
    def visit(item):
        result.append((item.text(0), item.isExpanded()))
        for index in range(item.childCount()): visit(item.child(index))
    for index in range(tree.tree.topLevelItemCount()): visit(tree.tree.topLevelItem(index))
    return result


@pytest.fixture
def project_tree(monkeypatch):
    from ui.widgets import project_tree as module

    app = QApplication.instance() or QApplication([])
    sites = [SimpleNamespace(id=1, name="North Quarry"), SimpleNamespace(id=2, name="South Project")]
    domains = {
        1: [SimpleNamespace(id=11, name="North1"), SimpleNamespace(id=12, name="West")],
        2: [SimpleNamespace(id=21, name="South Domain")],
    }
    blocks = [
        SimpleNamespace(id=101, domain_id=11, block_number="PB-101", horizon_m=500, planned_blast_date=date(2026, 8, 10), status="planned", is_archived=False),
        SimpleNamespace(id=102, domain_id=12, block_number="OLD-9", horizon_m=490, planned_blast_date=None, status="in_preparation", is_archived=False),
    ]
    contours = [
        SimpleNamespace(id="C1", domain_id=11, name="East Trim", elevation=500, event_date=date(2026, 8, 20), status="planned", is_archived=False),
        SimpleNamespace(id="C2", domain_id=12, name="West Trim", elevation=490, event_date=date(2026, 8, 21), status="planned", is_archived=False),
    ]
    areas = [
        SimpleNamespace(id="A1", domain_id=11, name="North Wall", min_elevation=480, max_elevation=500, assessment_date=date(2026, 8, 15), is_archived=False),
        SimpleNamespace(id="A2", domain_id=12, name="West Wall", min_elevation=470, max_elevation=490, assessment_date=date(2026, 8, 22), is_archived=False),
    ]
    monkeypatch.setattr(module, "SiteRepository", lambda _factory: SimpleNamespace(list_sites=lambda: sites))
    monkeypatch.setattr(module, "DomainRepository", lambda _factory: SimpleNamespace(list_for_site=lambda site_id: domains[site_id]))
    monkeypatch.setattr(module, "BlastBlockRepository", lambda _factory: SimpleNamespace(
        list_blocks=lambda **filters: [row for row in blocks if row.domain_id == filters["domain_id"] and (not filters["status"] or row.status == filters["status"])]))
    monkeypatch.setattr(module, "NavigationRepository", lambda _factory: SimpleNamespace(
        list_areas=lambda _show: areas, list_contour_events=lambda _show: contours))
    widget = module.ProjectTree(SimpleNamespace(session_factory=object()))
    yield widget, app
    widget.close()


@pytest.mark.parametrize("query, expected", [
    ("quarr", "North Quarry"), ("NORTH1", "Block PB-101"), ("b-10", "Block PB-101"),
    ("east tr", "Contour East Trim"), ("north wa", "North Wall"),
])
def test_searches_names_case_insensitively_and_preserves_hierarchy(project_tree, query, expected):
    tree, app = project_tree
    assert tree.findChildren(QLineEdit) == []
    tree.set_search_query(f"  {query}  "); app.processEvents()
    labels = _labels(tree); texts = [text for text, _expanded in labels]
    assert expected in texts
    assert "North Quarry" in texts and "North1" in texts
    assert "West" not in texts and "South Project" not in texts
    expanded = {text: state for text, state in labels}
    assert expanded["North Quarry"] and expanded["North1"]


@pytest.mark.parametrize("start,end,present,absent", [
    (date(2026, 8, 10), date(2026, 8, 20), ("Block PB-101", "Contour East Trim", "North Wall"), ("West Wall",)),
    (date(2026, 8, 20), None, ("Contour East Trim", "West Wall"), ("Block PB-101", "Block OLD-9")),
    (None, date(2026, 8, 15), ("Block PB-101", "North Wall"), ("Contour East Trim", "Block OLD-9")),
])
def test_date_boundaries_are_inclusive_and_undated_entities_are_removed(project_tree, start, end, present, absent):
    tree, app = project_tree
    tree.from_date.set_value(start); tree.to_date.set_value(end); app.processEvents()
    texts = [text for text, _expanded in _labels(tree)]
    for text in present: assert text in texts
    for text in absent: assert text not in texts


def test_reset_clears_every_filter_and_forces_all_domains(project_tree):
    tree, app = project_tree
    header_search = QLineEdit(); header_search.textChanged.connect(tree.set_search_query)
    tree.reset_search_requested.connect(header_search.clear)
    header_search.setText("PB"); tree.project_filter.setCurrentIndex(1); tree.domain_filter.setCurrentIndex(1)
    tree.status_filter.setCurrentIndex(2); tree.from_date.setDate(QDate(2026, 8, 1)); tree.to_date.setDate(QDate(2026, 8, 31)); tree.show_archived.setChecked(True)
    tree.reset_button.click(); app.processEvents()
    assert header_search.text() == "" and tree.search_query == ""
    assert tree.project_filter.currentData() is None and tree.domain_filter.currentData() is None
    assert tree.status_filter.currentData() is None
    assert tree.from_date.value() is None and tree.to_date.value() is None
    assert not tree.show_archived.isChecked()
    assert tree.tree.topLevelItemCount() == 2
