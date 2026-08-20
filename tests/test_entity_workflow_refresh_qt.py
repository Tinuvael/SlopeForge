from types import SimpleNamespace

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtWidgets import QApplication, QLabel

from ui.pages.assessment_area_page import AssessmentAreaPage
from ui.pages.block_page import BlockPage
from ui.pages.contour_event_page import ContourEventPage
from ui.pages.entity_overview_widgets import apply_status_badge


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class SavedEditor:
    def __init__(self, callback): self.callback = callback
    def save_draft(self): self.callback(); return True
    def complete(self): self.callback(); return True


class HeaderStub:
    def set_content(self, **kwargs):
        self.status_text = kwargs["status_text"]


class RowsStub:
    def set_rows(self, rows): self.rows = tuple(rows)


class NotesStub:
    def set_value(self, value, editable):
        self.value = value; self.editable = editable


def test_production_save_refreshes_persisted_status_and_can_demote(app):
    visible = QLabel("Planned")
    persisted = {"status": "planned"}
    page = SimpleNamespace(
        technical_card_editor=SavedEditor(lambda: persisted.update(status="blasted")),
        context=SimpleNamespace(current_user=SimpleNamespace(can_edit=True)),
        current_block=SimpleNamespace(is_archived=False),
    )
    page.refresh = lambda: visible.setText(persisted["status"].title())
    page._refresh_preserving_active_tab = page.refresh
    BlockPage._save_technical_card_draft(page)
    assert visible.text() == "Blasted"

    page.technical_card_editor = SavedEditor(lambda: persisted.update(status="planned"))
    BlockPage._complete_technical_card(page)
    assert visible.text() == "Planned"


def _contour_page(actual_date=None):
    event = SimpleNamespace(
        id="E", name="C1", elevation=630, comment="",
        event_date=__import__("datetime").date(2026, 8, 20),
        active_geometry_revision_id="E-R1", is_archived=False,
    )
    revision = SimpleNamespace(
        actual_execution=SimpleNamespace(actual_blast_date=actual_date),
        revision_number=1, status="draft",
    )
    card = SimpleNamespace(blast_event_id="E", active_revision=lambda: revision)
    state = SimpleNamespace(technical_cards=[card], assessment_areas=[], evaluations=[])
    page = SimpleNamespace(
        controller=SimpleNamespace(state=state), blast_event=event,
        card=card, draft=revision, rev=None,
        header=HeaderStub(), summary=RowsStub(), notes=NotesStub(),
        project_name="Project", domain_name="Domain", read_only=False,
    )
    return page, revision


def test_contour_persisted_actual_date_refreshes_visible_status(app):
    page, revision = _contour_page()
    ContourEventPage._refresh_header_and_summary(page, [], [], [])
    assert page.header.status_text == "Planned"
    revision.actual_execution.actual_blast_date = "2026-08-21"
    ContourEventPage._refresh_header_and_summary(page, [], [], [])
    assert page.header.status_text == "Blasted"


def test_assessment_complete_refreshes_header_without_navigation(app):
    header = QLabel("In progress")
    evaluation = {"completed": False}
    page = SimpleNamespace(
        evaluation_editor=SimpleNamespace(
            save=lambda status: evaluation.update(completed=status == "completed") or True,
            refresh_history=lambda: None,
        ),
        _ensure_editable=lambda: True,
        _refresh_attachment_controls=lambda: None,
        _refresh_overview_and_sidebar=lambda: header.setText(
            "Completed" if evaluation["completed"] else "In progress"),
    )
    AssessmentAreaPage._save_evaluation(page, "completed")
    assert header.text() == "Completed"


def test_entity_workflow_badges_use_semantic_roles(app):
    badges = {state: QLabel(state) for state in ("planned", "blasted", "completed")}
    for state, badge in badges.items():
        apply_status_badge(badge, state)
    assert badges["planned"].property("statusRole") == "info"
    assert badges["blasted"].property("statusRole") == "warning"
    assert badges["completed"].property("statusRole") == "success"
