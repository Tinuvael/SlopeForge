from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_block_general_information_omits_qprime_but_engineering_keeps_it():
    source = Path("ui/pages/block_page.py").read_text(encoding="utf-8")
    render = source[source.index("    def _render_engineering"):source.index("    def _clear_engineering")]
    general_rows = render[render.index("self.general_info.set_rows"):render.index("geo_lines =")]
    engineering = render[render.index("geo_lines ="):]

    assert '"Q′"' not in general_rows
    assert 'f"Q′ {_fmt_number(qprime)}"' in engineering
    assert "self.engineering_summary.set_sections" in engineering


def test_block_geometry_and_related_rows_use_stable_overview_presentation():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    core = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    from ui.pages.block_overview_widgets import BlockGeometryCard, BlockRelatedEntityList
    from ui.pages.entity_overview_widgets import OverviewLinkButton, RelatedEntityRow

    app = widgets.QApplication.instance() or widgets.QApplication([])
    geometry = BlockGeometryCard()
    assert geometry.plan.view.horizontalScrollBarPolicy() == core.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert geometry.plan.view.verticalScrollBarPolicy() == core.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert geometry.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Ignored
    assert geometry.sizeHint().height() == 0
    assert geometry.minimumSizeHint().height() == 0
    assert geometry.sizeHint().width() == 700
    assert geometry.minimumWidth() == geometry.MINIMUM_WIDTH == 610
    assert geometry.maximumWidth() == 800

    related = BlockRelatedEntityList("Related assessment areas")
    related.resize(520, 190)
    related.set_rows([
        RelatedEntityRow(
            "AA-1", "Area 1", "AA-1 · 600–630 m",
            "Completed", "completed", action_text="Go to ›",
        )
    ])
    related.show()
    app.processEvents()
    item = related.list.item(0)
    wrapper = related.list.itemWidget(item)
    holder = related._row_card(item)
    target_width = related._row_available_width() - related.ROW_HORIZONTAL_INSET * 2
    assert related.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Fixed
    assert related.list.minimumHeight() == related.list.maximumHeight()
    assert related.list.height() > 0
    assert related.sizeHint().height() > related.list.height()
    assert related.ROW_HORIZONTAL_INSET == 8
    assert item.sizeHint().width() == related._row_available_width()
    assert wrapper.objectName() == "BlockRelatedEntityWrapper"
    assert wrapper.layout().contentsMargins().left() == related.ROW_HORIZONTAL_INSET
    assert wrapper.layout().contentsMargins().right() == related.ROW_HORIZONTAL_INSET
    assert holder is not None
    assert holder.width() == target_width
    assert holder.width() < related.list.viewport().width()
    holder_left = wrapper.x() + holder.x()
    holder_right_gap = related.list.viewport().width() - (holder_left + holder.width())
    assert holder_left >= related.ROW_HORIZONTAL_INSET
    assert holder_right_gap >= related.ROW_HORIZONTAL_INSET
    assert holder.sizePolicy().horizontalPolicy() == widgets.QSizePolicy.Policy.Fixed
    labels = [label.text() for label in holder.findChildren(widgets.QLabel)]
    assert "Area 1" in labels
    assert "AA-1 · 600–630 m" in labels
    assert "Completed" in labels
    action = holder.findChild(OverviewLinkButton)
    assert action is not None
    assert action.text() == "Go to ›"
    assert "background:#edf8f0" in holder.styleSheet()
    assert "border:1px solid #58a66a" in holder.styleSheet()
    item.setSelected(True)
    app.processEvents()
    assert "border:2px solid #2563a6" in holder.styleSheet()

    geometry.close()
    related.close()
    app.processEvents()


def test_block_related_list_fits_two_rows_and_scrolls_when_more_exist():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.block_overview_widgets import BlockRelatedEntityList
    from ui.pages.entity_overview_widgets import RelatedEntityRow

    app = widgets.QApplication.instance() or widgets.QApplication([])
    related = BlockRelatedEntityList("Related assessment areas")
    related.resize(520, 240)
    rows = [
        RelatedEntityRow(
            f"AA-{index}", f"Area {index}", f"AA-{index} · 600–630 m",
            "Completed", "completed", action_text="Go to ›",
        )
        for index in range(1, 4)
    ]

    related.set_rows(rows[:2])
    related.show()
    app.processEvents()
    second_rect = related.list.visualItemRect(related.list.item(1))
    assert second_rect.isValid()
    assert second_rect.bottom() <= (
        related.list.viewport().rect().bottom() - related.VISIBLE_BOTTOM_MARGIN
    )
    first_rect = related.list.visualItemRect(related.list.item(0))
    assert first_rect.height() < related.LIST_HEIGHT / 2
    assert related.list.viewport().height() >= first_rect.height() + second_rect.height()
    two_row_height = related.list.height()
    assert related.list.horizontalScrollBar().maximum() == 0

    related.set_rows(rows)
    app.processEvents()
    assert related.list.height() == two_row_height
    assert related.list.verticalScrollBar().maximum() > 0
    assert related.list.horizontalScrollBar().maximum() == 0
    for index in range(related.list.count()):
        item = related.list.item(index)
        holder = related._row_card(item)
        wrapper = related.list.itemWidget(item)
        holder_left = wrapper.x() + holder.x()
        holder_right_gap = related.list.viewport().width() - (holder_left + holder.width())
        assert holder_left >= related.ROW_HORIZONTAL_INSET
        assert holder_right_gap >= related.ROW_HORIZONTAL_INSET
    related.close()
    app.processEvents()


def test_block_related_empty_state_uses_same_content_viewport_without_clipping():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.block_overview_widgets import BlockRelatedEntityList

    app = widgets.QApplication.instance() or widgets.QApplication([])
    related = BlockRelatedEntityList("Related assessment areas")
    related.set_rows([], empty_text="No linked assessment areas")
    assert related.list.isHidden()
    assert related.empty_label.text() == "No linked assessment areas"
    assert related.empty_label.height() == related.LIST_HEIGHT
    assert not related.empty_label.isHidden()
    assert related.sizeHint().height() > related.LIST_HEIGHT
    related.close()
    app.processEvents()


def test_block_notes_card_fixes_only_editor_viewport():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.block_overview_widgets import BlockNotesCard

    app = widgets.QApplication.instance() or widgets.QApplication([])
    notes = BlockNotesCard()
    assert notes.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Fixed
    assert notes.editor.minimumHeight() == notes.editor.maximumHeight() == notes.EDITOR_HEIGHT
    assert notes.sizeHint().height() > notes.EDITOR_HEIGHT
    notes.close()
    app.processEvents()


def test_block_recent_activity_always_reserves_four_equal_single_line_slots():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    core = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    from ui.pages.block_overview_widgets import BlockRecentActivityCard

    app = widgets.QApplication.instance() or widgets.QApplication([])
    card = BlockRecentActivityCard()
    entries = [
        SimpleNamespace(title="Created", actor="eugene", timestamp=datetime(2026, 8, 19, 12, i))
        for i in range(2)
    ]
    card.set_entries(entries)
    assert card.layout.alignment() & core.Qt.AlignmentFlag.AlignTop
    assert card.rows.alignment() & core.Qt.AlignmentFlag.AlignTop
    assert card.rows.count() == 4
    assert [card.rows.itemAt(i).widget().height() for i in range(4)] == [card.SLOT_HEIGHT] * 4
    first = card.rows.itemAt(0).widget()
    assert isinstance(first.layout(), widgets.QHBoxLayout)
    labels = first.findChildren(widgets.QLabel)
    assert [label.text() for label in labels] == ["●  Created", "eugene · 19.08.2026 12:00"]
    assert card.rows.itemAt(2).widget().findChildren(widgets.QLabel) == []
    assert card.rows.itemAt(3).widget().findChildren(widgets.QLabel) == []

    card.set_entries(entries * 3)
    assert card.rows.count() == 4
    assert all(card.rows.itemAt(i).widget().findChildren(widgets.QLabel) for i in range(4))
    card.close()
    app.processEvents()


def test_block_attachment_preview_hides_old_rows_before_rebuild():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.block_overview_widgets import BlockAttachmentPreview

    app = widgets.QApplication.instance() or widgets.QApplication([])
    preview = BlockAttachmentPreview("Photos", "photo", max_items=6)
    first = [
        SimpleNamespace(id=f"p{i}", title="", original_filename=f"p{i}.jpg")
        for i in range(4)
    ]
    second = [
        SimpleNamespace(id=f"q{i}", title="", original_filename=f"q{i}.jpg")
        for i in range(2)
    ]
    preview.set_items(None, first, "No photos yet")
    old_rows = list(preview._item_rows)
    preview.set_items(None, second, "No photos yet")
    assert old_rows
    assert all(row.isHidden() for row in old_rows)
    preview.close()
    app.processEvents()


def test_block_section_host_keeps_tab_page_identity_stable_and_expands_editor():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.block_overview_widgets import BlockSectionHost

    app = widgets.QApplication.instance() or widgets.QApplication([])
    first = widgets.QLabel("first")
    second = widgets.QLabel("second")
    host = BlockSectionHost(first)
    identity = id(host)
    host.set_content(second)
    assert id(host) == identity
    assert host._content is second
    assert first.isHidden()
    assert host.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
    assert second.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Expanding
    assert host._layout.stretch(0) == 1
    host.close()
    app.processEvents()


def test_block_page_has_no_layout_feedback_loop_or_tab_reinsertion():
    text = Path("ui/pages/block_page.py").read_text(encoding="utf-8")
    helpers = Path("ui/pages/block_overview_widgets.py").read_text(encoding="utf-8")

    assert "QTimer" not in text
    assert "_sync_top_row_height" not in text
    assert "_settle_visible_layout" not in text
    assert "_finish_show_layout" not in text
    assert "self.geometry_card.setFixedHeight" not in text
    assert ".removeTab(" not in text
    assert ".insertTab(" not in text
    assert "removeItemWidget" not in helpers
    assert "BlockSectionHost" in text
    assert "self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)" in text
    assert "self.overview_stack_widget.setSizePolicy" in text
    assert "QSizePolicy.Policy.Fixed" in text
    assert "BlockRecentActivityCard" in text
    assert "top.addWidget(self.geometry_card, 0)" in text
    assert "PREFERRED_WIDTH = 700" in helpers
    assert "LIST_HEIGHT = 136" in helpers
    assert "ROW_HORIZONTAL_INSET = 8" in helpers
    assert "viewport().installEventFilter(self)" in helpers
    assert "def _sync_row_widths(self)" in helpers
    assert "BlockNotesCard" in helpers


def test_block_sidebar_density_uses_actual_tab_viewport_after_summary_render():
    text = Path("ui/pages/block_page.py").read_text(encoding="utf-8")
    assert "available = max(0, self.tabs.height() - 4)" in text
    assert "while required_height() > available" in text
    render = text.split("def _render_current_block", 1)[1].split("def _render_related_areas", 1)[0]
    assert render.index("self._render_engineering(block)") < render.index("self._sync_sidebar_density()")
