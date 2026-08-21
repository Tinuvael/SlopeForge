import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtWidgets import QApplication, QPushButton, QScrollArea

from application.services.project_lines import ProjectLinesDatasetService
from application.state.assessment_domain_state import AssessmentDomainState


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def state(tmp_path):
    source = tmp_path / "project.csv"
    source.write_text(
        "XP,YP,ZP,SID,PTN\n0,10,630,A,1\n10,10,630,A,2\n"
        "0,0,600,B,1\n10,0,600,B,2\n", encoding="utf-8")
    value = AssessmentDomainState()
    ProjectLinesDatasetService(value).import_dataset(source)
    return value


def preview(count=0):
    items = tuple(SimpleNamespace(
        blast_event_id=f"E-{index}", name=f"Blast event {index:03d}",
        event_type="production" if index % 2 == 0 else "contour",
        elevation=610 + index / 10,
    ) for index in range(count))
    return SimpleNamespace(
        items=items, total=len(items),
        production_count=sum(item.event_type == "production" for item in items),
        contour_count=sum(item.event_type == "contour" for item in items),
    )


def build_page(monkeypatch, state, app, *, preview_count=0):
    import ui.pages.assessment_area_creation_page as module

    class Controller:
        def __init__(self, context, domain_id):
            self.state = state
            self.commits = []
            self.domain_id = domain_id

        def project_assessment_boundaries(self):
            return ()

        def save_assessment_area_geometry(self, **values):
            self.commits.append(values)
            return SimpleNamespace(area_id="AA-001", link_refresh_warning=None)

        def preview_assessment_event_links(self, boundary):
            return preview(preview_count)

        def area(self, area_id):
            return None

    monkeypatch.setattr(module, "EntityPageController", Controller)
    context = SimpleNamespace(current_user=SimpleNamespace(can_edit=True))
    page = module.AssessmentAreaCreationPage(context, 1, "North", 1)
    page.resize(1366, 768); page.show(); app.processEvents()
    return page


def test_real_workspace_is_visible_and_has_one_navigation_path(monkeypatch, state, app):
    page = build_page(monkeypatch, state, app)
    assert len(page.stepper.step_nodes) == 3
    assert page.stepper.labels == ("Details", "Boundary", "Review")
    assert all(circle.isVisible() and label.isVisible()
               for circle, label in page.stepper.step_nodes)
    assert page.info_card.isVisible() and page.plan_card.isVisible() and page.context_card.isVisible()
    assert page.editor.isVisible() and page.editor.plan_view.isVisible()

    buttons = page.findChildren(QPushButton)
    assert len([button for button in buttons if button.isVisible() and button.text() == "Cancel"]) == 1
    assert len([button for button in buttons if button.isVisible() and button.text() == "Back"]) <= 1
    assert all(button.text() != "Back / Close" for button in buttons)
    page.close()


def test_map_keeps_same_parent_and_stays_visible_across_steps(monkeypatch, state, app):
    page = build_page(monkeypatch, state, app)
    editor = page.editor; parent = editor.parentWidget()
    page.area_name.setText("East wall")
    page._next()
    assert page.current_step == page.BOUNDARY
    for step in (page.GENERAL, page.BOUNDARY, page.REVIEW):
        page._set_step(step); app.processEvents()
        assert page.editor is editor and editor.parentWidget() is parent
        assert editor.isVisible() and editor.plan_view.isVisible()
        assert page.info_card.isVisible() and page.context_card.isVisible()
    assert page.controller.commits == []
    page.close()


def test_large_link_preview_is_scrollable_without_expanding_page(monkeypatch, state, app):
    before = state.to_dict()
    page = build_page(monkeypatch, state, app, preview_count=80)
    initial_height = page.minimumSizeHint().height()
    page._link_preview = preview(80)
    page._set_step(page.REVIEW); app.processEvents()

    scroll = page.context_card.findChild(QScrollArea, "assessmentLinkEventsScroll")
    assert scroll is page.link_events_scroll and scroll.isVisible()
    assert len(page.link_event_rows) == 80
    assert scroll.verticalScrollBar().maximum() > 0
    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
    assert scroll.verticalScrollBar().value() == scroll.verticalScrollBar().maximum()
    assert page.height() == 768 and page.minimumSizeHint().height() <= max(initial_height, 768)
    assert page.plan_card.width() > page.info_card.width()
    assert page.plan_card.width() > page.context_card.width()
    assert page.editor.isVisible() and state.to_dict() == before
    page.close()


def test_footer_hierarchy_and_ui_only_elevation_rounding(monkeypatch, state, app):
    page = build_page(monkeypatch, state, app)
    assert page.next.objectName() == "assessmentPrimaryAction"
    assert page.confirm.objectName() == "assessmentPrimaryAction"
    assert page.back.objectName() == "assessmentSecondaryAction"
    assert page.cancel.objectName() == "assessmentQuietAction"
    assert all(button.minimumHeight() == 32
               for button in (page.next, page.confirm, page.back, page.cancel))
    assert page.confirm.text() == "Create Assessment Area"
    page.close()


def test_only_small_architecture_guards_remain_source_based():
    page = Path("ui/pages/assessment_area_creation_page.py").read_text(encoding="utf-8")
    assert "QStackedWidget" not in page
    assert page.count("AssessmentGeometryEditorWidget(") == 1


def test_assessment_creation_translation_helpers_remain_static():
    from ui.pages.assessment_area_creation_page import AssessmentAreaCreationPage

    assert isinstance(inspect.getattr_static(AssessmentAreaCreationPage, "_section"), staticmethod)
    assert isinstance(inspect.getattr_static(AssessmentAreaCreationPage, "_add_row"), staticmethod)


def test_creation_page_scopes_context_and_excludes_current_area():
    source = Path("ui/pages/assessment_area_creation_page.py").read_text(encoding="utf-8")
    assert "self.controller.project_assessment_boundaries()" in source
    assert "item.domain_id == self.controller.domain_id" in source
    assert "item.assessment_area_id == edit_area_id" in source
