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
    assert related.ROW_RIGHT_INSET == 10
    assert notes.EDITOR_HEIGHT == 46
    assert activity.SLOT_COUNT == 4
    assert activity.SLOT_HEIGHT == 32
    assert photos._max_items == 6
    assert documents._max_items == 7

    for widget in (geometry, related, notes, activity, photos, documents):
        widget.close()
    app.processEvents()
