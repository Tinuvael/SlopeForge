from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest


def test_block_geometry_and_related_rows_use_stable_overview_presentation():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    core = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    from ui.pages.block_overview_widgets import BlockGeometryCard, BlockRelatedEntityList
    from ui.pages.entity_overview_widgets import RelatedEntityRow

    app = widgets.QApplication.instance() or widgets.QApplication([])
    geometry = BlockGeometryCard()
    assert geometry.plan.view.horizontalScrollBarPolicy() == core.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert geometry.plan.view.verticalScrollBarPolicy() == core.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert geometry.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Ignored
    assert geometry.sizeHint().height() == 0
    assert geometry.minimumSizeHint().height() == 0

    related = BlockRelatedEntityList("Related assessment areas")
    related.set_rows([
        RelatedEntityRow(
            "AA-1", "Area 1", "AA-1 · 600–630 m",
            "Completed", "completed", action_text="Go to ›",
        )
    ])
    item = related.list.item(0)
    holder = related.list.itemWidget(item)
    assert related.minimumHeight() == related.maximumHeight() == related.CARD_HEIGHT
    assert related.list.minimumHeight() == related.list.maximumHeight() == related.LIST_HEIGHT
    assert item.sizeHint().width() == 0
    assert holder.sizePolicy().horizontalPolicy() == widgets.QSizePolicy.Policy.Expanding
    assert related.layout.contentsMargins().right() == 18
    assert "background:#edf8f0" in holder.styleSheet()
    assert "border:1px solid #58a66a" in holder.styleSheet()
    assert holder.layout().contentsMargins().right() == 14
    item.setSelected(True)
    app.processEvents()
    assert "border:2px solid #2563a6" in holder.styleSheet()

    geometry.close()
    related.close()
    app.processEvents()


def test_block_related_empty_state_keeps_same_fixed_card_height():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.block_overview_widgets import BlockRelatedEntityList

    app = widgets.QApplication.instance() or widgets.QApplication([])
    related = BlockRelatedEntityList("Related assessment areas")
    related.set_rows([], empty_text="No linked assessment areas")
    assert related.list.isHidden()
    assert related.empty_label.text() == "No linked assessment areas"
    assert related.empty_label.height() == related.LIST_HEIGHT
    assert not related.empty_label.isHidden()
    assert related.minimumHeight() == related.maximumHeight() == related.CARD_HEIGHT
    related.close()
    app.processEvents()


def test_block_recent_activity_always_reserves_four_equal_slots():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.block_overview_widgets import BlockRecentActivityCard

    app = widgets.QApplication.instance() or widgets.QApplication([])
    card = BlockRecentActivityCard()
    entries = [
        SimpleNamespace(title="Created", actor="eugene", timestamp=datetime(2026, 8, 19, 12, i))
        for i in range(2)
    ]
    card.set_entries(entries)
    assert card.rows.count() == 4
    assert [card.rows.itemAt(i).widget().height() for i in range(4)] == [card.SLOT_HEIGHT] * 4
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


def test_block_section_host_keeps_tab_page_identity_stable():
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
    assert host.sizePolicy().verticalPolicy() == widgets.QSizePolicy.Policy.Ignored
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
    assert "BlockSectionHost" in text
    assert "self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)" in text
    assert "self.overview_stack_widget.setSizePolicy" in text
    assert "QSizePolicy.Policy.Fixed" in text
    assert "self.notes.setFixedHeight(108)" in text
    assert "self.notes.editor.setFixedHeight(58)" in text
    assert "BlockRecentActivityCard" in text
    assert "top.addWidget(self.geometry_card, 0)" in text
    assert "QSizePolicy.Policy.Ignored" in helpers
    assert "def sizeHint(self):" in helpers
    assert "return QSize(540, 0)" in helpers


def test_block_sidebar_density_uses_actual_tab_viewport_after_summary_render():
    text = Path("ui/pages/block_page.py").read_text(encoding="utf-8")
    assert "available = max(0, self.tabs.height() - 4)" in text
    assert "while required_height() > available" in text
    render = text.split("def _render_current_block", 1)[1].split("def _render_related_areas", 1)[0]
    assert render.index("self._render_engineering(block)") < render.index("self._sync_sidebar_density()")
