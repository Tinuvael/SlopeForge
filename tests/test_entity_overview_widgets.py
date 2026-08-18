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
        assert "SquareGeometryCard" in text
        assert "OverviewKeyValueCard" in text
        assert "RecentActivityCard" in text
    assert "focus_geometry=geometry.plan_geometry" in block
    assert "focus_geometry=self.rev.plan_geometry" in contour
    assert "focus_geometry=rev.final_geometry_frozen" in assessment
    assert "AssessmentMatrixPreview" in assessment


def test_shared_square_geometry_card_prefers_near_square_size():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.entity_overview_widgets import SquareGeometryCard

    app = widgets.QApplication.instance() or widgets.QApplication([])
    card = SquareGeometryCard()
    assert card.hasHeightForWidth()
    assert card.heightForWidth(390) == 390
    assert card.sizeHint().width() == card.sizeHint().height()
    assert card.maximumWidth() == 440
    card.close(); app.processEvents()


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


def test_header_uses_one_context_line_instead_of_duplicate_meta_cards():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.entity_overview_widgets import EntityHeaderWidget

    app = widgets.QApplication.instance() or widgets.QApplication([])
    header = EntityHeaderWidget()
    header.set_content(
        title="Block X", status_text="Blasted", status_state="blasted",
        meta_values=("ID: BL-X", "Project / Domain: P / D", "Horizon: 630 m", "Geometry rev.: 2"),
    )
    assert header.context.text() == "ID: BL-X  ·  Project / Domain: P / D  ·  Horizon: 630 m  ·  Geometry rev.: 2"
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
    assert 'f"{tr(\'Project / Domain\')}: {self.project_name} / {self.domain_name}"' in text


def test_block_overview_has_single_kpi_summary_and_qprime_stability_categories():
    page = Path("ui/pages/block_page.py").read_text(encoding="utf-8")
    assert "polygon_area_m2" in page
    assert "_qprime_and_category" in page
    for label in ("Very unstable", "Unstable", "Moderately stable", "Stable"):
        assert label in page
    assert '("Blast date",' in page
    assert '("Block area",' in page
    assert '("Bench height",' in page
    assert '("Stability",' in page
    assert "EngineeringSummaryCard" in page
    assert "GeneralInfoCard" in page
    assert "self.recent_activity.set_entries(history_entries)" in page
    assert "Created" not in page.split("meta_values=(", 1)[1].split("),", 1)[0]
    assert "Updated" not in page.split("meta_values=(", 1)[1].split("),", 1)[0]


def test_contour_overview_exposes_geometry_oriented_summary_without_status_duplication():
    text = Path("ui/pages/contour_event_page.py").read_text(encoding="utf-8")
    for label in ("Average depth", "Azimuth", "Inclination", "Spacing"):
        assert label in text
    assert "_primary_contour_group" in text
    assert 'self._open_tab("blast_design")' in text
    assert "actual.actual_average_depth_m" in text
    assert "actual_group.spacing_m" in text
    assert '("Method",' in text
    assert '("Technical Card",' in text
    assert 'f"{tr(\'Project / Domain\')}: {self.project_name} / {self.domain_name}"' in text
