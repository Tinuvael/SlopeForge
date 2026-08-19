from pathlib import Path

import pytest


def test_assessment_overview_helpers_use_stabilized_entity_dimensions():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    core = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    from ui.pages.assessment_overview_widgets import (
        AssessmentAttachmentPreview,
        AssessmentCommentsCard,
        AssessmentGeometryCard,
        AssessmentMatrixCard,
        AssessmentRecentActivityCard,
        AssessmentRelatedEventList,
    )

    app = widgets.QApplication.instance() or widgets.QApplication([])
    geometry = AssessmentGeometryCard()
    related = AssessmentRelatedEventList("Related blast events")
    comments = AssessmentCommentsCard()
    matrix = AssessmentMatrixCard()
    activity = AssessmentRecentActivityCard()
    photos = AssessmentAttachmentPreview("Photos", "photo", max_items=6)
    documents = AssessmentAttachmentPreview("Documents", "document", max_items=7)

    comments.set_sections((
        ("comments", "Comments", ["Comment"]),
        ("recommendations", "Recommendations", ["Recommendation"]),
    ))

    assert geometry.sizeHint().width() == 700
    assert geometry.minimumWidth() == 610
    assert geometry.maximumWidth() == 800
    assert related.LIST_HEIGHT == 184
    assert related.LIST_HEIGHT > 136
    assert related.ROW_RIGHT_INSET == 14
    assert activity.SLOT_COUNT == 4
    assert activity.SLOT_HEIGHT == 32
    assert photos._max_items == 6
    assert documents._max_items == 7
    assert matrix.minimumWidth() == 250
    assert matrix.maximumWidth() == 310
    assert matrix.preview.minimumWidth() == 190
    assert matrix.preview.minimumHeight() == 190
    assert matrix.preview.sizeHint().width() == 220
    assert matrix.preview.sizeHint().height() == 220

    section_indexes = []
    for index in range(comments.sections.count()):
        item = comments.sections.itemAt(index)
        widget = item.widget()
        if widget is not None and widget.objectName() != "OverviewDivider":
            section_indexes.append(index)
            assert comments.sections.stretch(index) == 1
            assert widget.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
            assert widget.layout().alignment() & core.Qt.AlignmentFlag.AlignTop
    assert len(section_indexes) == 2

    for widget in (geometry, related, comments, matrix, activity, photos, documents):
        widget.close()
    app.processEvents()


def test_assessment_overview_page_uses_saved_geometry_and_stored_result_only():
    page = Path("ui/pages/assessment_area_page.py").read_text(encoding="utf-8")

    assert "calculate_revision(" not in page
    assert "active.design_achievement_index" in page
    assert "active.face_condition_index" in page
    assert "active.matrix_template_snapshot" in page
    assert "active.design_inputs" in page
    assert 'abs(float(rev.max_elevation) - float(rev.min_elevation))' in page
    assert 'AssessmentAttachmentPreview("Photos", "photo", max_items=6)' in page
    assert 'AssessmentAttachmentPreview("Documents", "document", max_items=7)' in page
    assert 'AssessmentGeometryCard("Plan / geometry", action_label="Edit boundaries")' in page
    assert 'AssessmentRelatedEventList("Related blast events")' in page
    assert "entity_activated.connect(self._preview_related_event)" in page
    assert "entity_action_requested.connect(self._open_related_event)" in page
    assert "escape_requested.connect(self._clear_related_event_preview)" in page
    assert "self.controller.links.linked_revision(event, link)" in page
    assert 'action_text="Go to ›"' in page
    assert "set_visible_item_limit(photo_limit)" in page
    assert "set_visible_item_limit(document_limit)" in page
    assert "self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)" in page
