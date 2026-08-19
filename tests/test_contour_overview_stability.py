from pathlib import Path

import pytest


def test_contour_overview_helpers_share_block_dimensions_and_behaviour():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.contour_overview_widgets import (
        ContourAttachmentPreview,
        ContourGeometryCard,
        ContourNotesCard,
        ContourRecentActivityCard,
        ContourRelatedEntityList,
    )

    app = widgets.QApplication.instance() or widgets.QApplication([])

    geometry = ContourGeometryCard()
    related = ContourRelatedEntityList("Related assessment areas")
    notes = ContourNotesCard()
    activity = ContourRecentActivityCard()
    photos = ContourAttachmentPreview("Photos", "photo", max_items=6)
    documents = ContourAttachmentPreview("Documents", "document", max_items=7)

    assert geometry.sizeHint().width() == 700
    assert geometry.minimumWidth() == 610
    assert geometry.maximumWidth() == 800
    assert related.LIST_HEIGHT == 136
    assert related.ROW_RIGHT_INSET == 14
    assert notes.EDITOR_HEIGHT == 46
    assert activity.SLOT_COUNT == 4
    assert activity.SLOT_HEIGHT == 32
    assert photos._max_items == 6
    assert documents._max_items == 7

    for widget in (geometry, related, notes, activity, photos, documents):
        widget.close()
    app.processEvents()


def test_contour_keeps_hidden_general_widgets_required_by_technical_card_save():
    page = Path("ui/pages/contour_event_page.py").read_text(encoding="utf-8")

    assert 'take_tab(tr("Contour drilling"))' in page
    assert 'take_tab(tr("Execution fact"))' in page
    assert 'take_tab(tr("General"))' not in page
    assert "general_page.deleteLater()" not in page
    assert "self.editor.save_draft()" in page
    assert "self.editor.complete()" in page


def test_contour_engineering_notes_keep_natural_height_and_top_alignment():
    page = Path("ui/pages/contour_event_page.py").read_text(encoding="utf-8")

    assert "self.engineering_notes.setSizePolicy(" in page
    assert "QSizePolicy.Policy.Fixed" in page
    assert "bottom.setAlignment(Qt.AlignmentFlag.AlignTop)" in page
    assert "bottom.addWidget(self.engineering_notes, 3, Qt.AlignmentFlag.AlignTop)" in page
    assert "bottom.addWidget(self.recent_activity, 2, Qt.AlignmentFlag.AlignTop)" in page
