from __future__ import annotations

from pathlib import Path

import pytest


def test_overview_geometry_focus_uses_two_span_context():
    text = Path("ui/pages/plan_geometry_widget.py").read_text(encoding="utf-8")
    assert "factor = 2.0" in text
    assert "sqrt(2.0)" not in text


def test_operational_pages_use_shared_overview_primitives():
    block = Path("ui/pages/block_page.py").read_text(encoding="utf-8")
    contour = Path("ui/pages/contour_event_page.py").read_text(encoding="utf-8")
    assessment = Path("ui/pages/assessment_area_page.py").read_text(encoding="utf-8")
    for text in (block, contour, assessment):
        assert "EntityHeaderWidget" in text
        assert "QuickAttachmentPreview" in text
    assert "focus_geometry=geometry.plan_geometry" in block
    assert "focus_geometry=self.rev.plan_geometry" in contour
    assert "focus_geometry=rev.final_geometry_frozen" in assessment
    assert "AssessmentMatrixPreview" in assessment


def test_status_badges_have_distinct_semantic_workflow_colors():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.entity_overview_widgets import EntityHeaderWidget

    app = widgets.QApplication.instance() or widgets.QApplication([])
    header = EntityHeaderWidget()
    styles = {}
    for state in ("in_preparation", "planned", "blasted", "assessed", "in_progress", "completed"):
        header.set_content(title="X", status_text=state, status_state=state)
        styles[state] = header.status.styleSheet()
    assert styles["in_preparation"] != styles["planned"]
    assert styles["planned"] != styles["blasted"]
    assert styles["blasted"] != styles["assessed"]
    assert styles["in_progress"] == styles["planned"]
    assert styles["completed"] == styles["assessed"]
    header.set_content(title="X", status_text="Completed", status_state="completed", archived=True)
    assert header.archive.isVisible() or not header.isVisible()
    header.close(); app.processEvents()


def test_quick_attachment_preview_exposes_add_and_open_actions():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.entity_overview_widgets import QuickAttachmentPreview

    app = widgets.QApplication.instance() or widgets.QApplication([])
    preview = QuickAttachmentPreview("Photos", "photo")
    added=[]; opened=[]
    preview.add_requested.connect(lambda: added.append(True))
    preview.open_page_requested.connect(lambda: opened.append(True))
    preview.set_items(None, [], "No photos yet", can_add=False)
    assert not preview.add_button.isEnabled()
    assert preview.open_button.isEnabled()
    preview.set_items(None, [], "No photos yet", can_add=True)
    preview.add_button.click(); preview.open_button.click(); app.processEvents()
    assert added == [True]
    assert opened == [True]
    preview.close(); app.processEvents()


def test_assessment_matrix_preview_only_accepts_stored_indices():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.entity_overview_widgets import AssessmentMatrixPreview

    app = widgets.QApplication.instance() or widgets.QApplication([])
    preview = AssessmentMatrixPreview()
    preview.set_result(dai=.71, fci=.58, dai_threshold=.65, fci_threshold=.60)
    assert preview.dai == pytest.approx(.71)
    assert preview.fci == pytest.approx(.58)
    assert preview.dai_threshold == pytest.approx(.65)
    assert preview.fci_threshold == pytest.approx(.60)
    preview.close(); app.processEvents()


def test_assessment_overview_uses_saved_revision_results_without_scoring_call():
    text = Path("ui/pages/assessment_area_page.py").read_text(encoding="utf-8")
    assert "active.design_achievement_index" in text
    assert "active.face_condition_index" in text
    assert "matrix_template_snapshot" in text
    assert "calculate_revision(" not in text
    assert "photo_manager.add()" in text
    assert "document_manager.add()" in text
