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

    related = BlockRelatedEntityList("Related assessment areas")
    related.set_rows([
        RelatedEntityRow(
            "AA-1", "Area 1", "AA-1 · 600–630 m",
            "Completed", "completed", action_text="Go to ›",
        )
    ])
    item = related.list.item(0)
    holder = related.list.itemWidget(item)
    assert "background:#edf8f0" in holder.styleSheet()
    assert "border:1px solid #58a66a" in holder.styleSheet()
    assert holder.layout().contentsMargins().right() == 14
    item.setSelected(True)
    app.processEvents()
    assert "border:2px solid #2563a6" in holder.styleSheet()

    geometry.close()
    related.close()
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


def test_block_page_settles_reentry_before_repaint_and_matches_left_stack_height():
    text = Path("ui/pages/block_page.py").read_text(encoding="utf-8")
    assert "from PySide6.QtCore import QEvent, QTimer, Qt, Signal" in text
    assert "self.setUpdatesEnabled(False)" in text
    assert "QTimer.singleShot(0, self._finish_show_layout)" in text
    assert "def _settle_visible_layout(self)" in text
    assert "layout.activate()" in text
    assert "self.setUpdatesEnabled(True)" in text
    assert "target = max(360, self.overview_stack_widget.sizeHint().height())" in text
    assert "min(520" not in text
    assert "self.geometry_card.plan.center_on_focus()" in text
