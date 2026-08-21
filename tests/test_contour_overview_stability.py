from pathlib import Path

import pytest


def test_contour_overview_helpers_share_block_dimensions_and_behaviour():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    core = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    from ui.pages.contour_overview_widgets import (
        ContourAttachmentPreview,
        ContourEngineeringNotesCard,
        ContourGeometryCard,
        ContourNotesCard,
        ContourRecentActivityCard,
        ContourRelatedEntityList,
    )

    app = widgets.QApplication.instance() or widgets.QApplication([])

    geometry = ContourGeometryCard()
    related = ContourRelatedEntityList("Related assessment areas")
    notes = ContourNotesCard()
    engineering_notes = ContourEngineeringNotesCard()
    activity = ContourRecentActivityCard()
    photos = ContourAttachmentPreview("Photos", "photo", max_items=6)
    documents = ContourAttachmentPreview("Documents", "document", max_items=7)

    engineering_notes.set_sections((
        ("blast_design", "Blast design", ["Design note"]),
        ("execution", "Execution fact", ["Execution note"]),
    ))

    assert geometry.sizeHint().width() == 700
    assert geometry.minimumWidth() == geometry.MINIMUM_WIDTH == 610
    assert geometry.maximumWidth() == 800
    assert related.LIST_HEIGHT == 136
    assert related.ROW_HORIZONTAL_INSET == 8
    assert notes.EDITOR_HEIGHT == 46
    assert activity.SLOT_COUNT == 4
    assert activity.SLOT_HEIGHT == 32
    assert photos._max_items == 6
    assert documents._max_items == 7

    assert engineering_notes.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Preferred
    assert engineering_notes.layout.stretch(engineering_notes.layout.count() - 1) == 1
    section_items = []
    divider_items = []
    for index in range(engineering_notes.sections.count()):
        item = engineering_notes.sections.itemAt(index)
        widget = item.widget()
        if widget is not None and widget.objectName() == "OverviewDivider":
            divider_items.append(index)
        elif widget is not None:
            section_items.append(index)
            assert widget.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
            assert widget.layout().alignment() & core.Qt.AlignmentFlag.AlignTop
    assert len(section_items) == 2
    assert all(engineering_notes.sections.stretch(index) == 1 for index in section_items)
    assert all(engineering_notes.sections.stretch(index) == 0 for index in divider_items)

    for widget in (geometry, related, notes, engineering_notes, activity, photos, documents):
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


def test_nominal_contour_line_length_uses_hole_count_times_spacing():
    from types import SimpleNamespace
    from domain.blasting.technical_card import nominal_contour_line_length

    assert nominal_contour_line_length(SimpleNamespace(hole_count=25, spacing_m=.2)) == 5.0
    assert nominal_contour_line_length(SimpleNamespace(hole_count=None, spacing_m=.2)) is None


def test_contour_overview_method_uses_canonical_translated_label(monkeypatch):
    pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    import ui.pages.contour_event_page as module

    seen = []
    monkeypatch.setattr(module, "tr", lambda source: seen.append(source) or f"translated:{source}")
    assert module._method_label("presplit") == "translated:Presplitting"
    assert seen == ["Presplitting"]


def test_contour_bottom_cards_share_row_height_and_notes_split_space_evenly():
    page = Path("ui/pages/contour_event_page.py").read_text(encoding="utf-8")

    assert 'self.engineering_notes = ContourEngineeringNotesCard("Engineering notes")' in page
    assert "bottom.setAlignment(Qt.AlignmentFlag.AlignTop)" in page
    assert "QSizePolicy.Policy.Preferred" in page
    assert "bottom.addWidget(self.engineering_notes, 3)" in page
    assert "bottom.addWidget(self.recent_activity, 2)" in page
    assert "bottom.addWidget(self.recent_activity, 2, Qt.AlignmentFlag.AlignTop)" not in page
