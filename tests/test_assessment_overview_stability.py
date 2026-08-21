from pathlib import Path

import pytest


def test_assessment_related_events_stays_expanding_after_deferred_callbacks():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.assessment_overview_widgets import AssessmentRelatedEventList
    from ui.pages.entity_overview_widgets import RelatedEntityRow

    app = widgets.QApplication.instance() or widgets.QApplication([])
    related = AssessmentRelatedEventList("Related blast events")
    related.set_rows([
        RelatedEntityRow("BE-1", "Production 1", "Horizon 600 m"),
        RelatedEntityRow("BE-2", "Contour 2", "Horizon 590 m"),
    ])
    related.resize(520, 320); related.show()
    app.processEvents(); app.processEvents()

    assert related.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
    assert related.list.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
    assert related.list.minimumHeight() == related.LIST_HEIGHT
    assert related.list.maximumHeight() > related.LIST_HEIGHT
    related.close(); app.processEvents()


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
        AssessmentStateSummaryCard,
    )

    app = widgets.QApplication.instance() or widgets.QApplication([])
    geometry = AssessmentGeometryCard()
    related = AssessmentRelatedEventList("Related blast events")
    comments = AssessmentCommentsCard()
    state = AssessmentStateSummaryCard()
    matrix = AssessmentMatrixCard()
    activity = AssessmentRecentActivityCard()
    photos = AssessmentAttachmentPreview("Photos", "photo", max_items=6)
    documents = AssessmentAttachmentPreview("Documents", "document", max_items=7)

    comments.set_sections((
        ("comments", "Comments", ["Comment"]),
        ("recommendations", "Recommendations", ["Recommendation"]),
    ))
    state.set_sections((
        ("Geometry", ["Angle deviation: 1°", "Berm deviation: 1 m"]),
        ("Face condition", ["Contour hole traces: 75 %"]),
    ))

    assert geometry.sizeHint().width() == 700
    assert geometry.minimumWidth() == geometry.MINIMUM_WIDTH == 610
    assert geometry.maximumWidth() == 800
    assert related.LIST_HEIGHT == 184
    assert related.LIST_HEIGHT > 136
    assert related.ROW_HORIZONTAL_INSET == 8
    assert related.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
    assert related.list.minimumHeight() == 184
    assert related.list.maximumHeight() > 184
    assert activity.SLOT_COUNT == 4
    assert activity.SLOT_HEIGHT == 32
    assert photos._max_items == 6
    assert documents._max_items == 7
    assert state.minimumWidth() == state.MINIMUM_WIDTH == 320
    assert state.maximumWidth() == state.MAXIMUM_WIDTH == 400
    assert state.sizePolicy().horizontalPolicy() == widgets.QSizePolicy.Policy.Preferred
    assert state.layout.contentsMargins().top() == 8
    assert matrix.minimumWidth() == 250
    assert matrix.maximumWidth() == 310
    assert matrix.preview.minimumWidth() == 190
    assert matrix.preview.minimumHeight() == 190
    assert matrix.preview.sizeHint().width() == 220
    assert matrix.preview.sizeHint().height() == 220
    assert state.sections.count() == 3
    assert state.open_button.text() == "Open ›"

    state_sections = []
    for index in range(state.sections.count()):
        widget = state.sections.itemAt(index).widget()
        if widget is None or widget.objectName() == "OverviewDivider":
            continue
        state_sections.append(widget)
        assert widget.layout().alignment() & core.Qt.AlignmentFlag.AlignTop
        labels = widget.findChildren(widgets.QLabel)
        assert labels[-1].alignment() & core.Qt.AlignmentFlag.AlignTop
        assert labels[-1].sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Fixed
    assert len(state_sections) == 2
    assert state_sections[0].sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Fixed
    assert state_sections[1].sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
    face_index = state.sections.indexOf(state_sections[1])
    assert state.sections.stretch(face_index) == 1
    assert state_sections[1].layout().stretch(state_sections[1].layout().count() - 1) == 1

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

    for widget in (geometry, related, comments, state, matrix, activity, photos, documents):
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
    assert 'AssessmentStateSummaryCard("Geometry / face condition")' in page
    assert "workspace.addWidget(self.related_events, 1, 0, 2, 1)" in page
    assert "workspace.addWidget(self.geometry_card, 0, 1, 2, 1)" in page
    assert "workspace.addWidget(state_row, 2, 1)" in page
    assert "workspace.setRowMinimumHeight(1, self.related_events.LIST_HEIGHT)" in page
    assert "self.state_summary_card.open_requested.connect" in page
    assert "self.state_summary_card.set_sections" in page
    assert "self.geometry_summary_card" not in page
    assert "self.face_condition_card" not in page
    assert 'visible_links = [x for x in self.area.links_for_revision() if x.status != "excluded"]' in page
    assert 'item.status != "excluded" and item.blast_event_id == event_id' in page
    assert 'if link.status == "suggested"' in page
    assert "entity_activated.connect(self._preview_related_event)" in page
    assert "entity_action_requested.connect(self._open_related_event)" in page
    assert "escape_requested.connect(self._clear_related_event_preview)" in page
    assert "self.controller.links.linked_revision(event, link)" in page
    assert 'action_text=tr("Go to ›")' in page
    assert "set_visible_item_limit(photo_limit)" in page
    assert "set_visible_item_limit(document_limit)" in page
    assert "self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)" in page
