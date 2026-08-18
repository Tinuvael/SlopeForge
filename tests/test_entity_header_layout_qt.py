import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtWidgets import QApplication

from ui.pages.entity_overview_widgets import EntityHeaderWidget


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_shared_entity_header_order_is_title_status_archive_stretch_edit(qapp):
    header = EntityHeaderWidget()
    top = header.layout.itemAt(0).layout()
    assert top.count() == 5
    assert top.itemAt(0).widget() is header.title
    assert top.itemAt(1).widget() is header.status
    assert top.itemAt(2).widget() is header.archive
    assert top.itemAt(3).spacerItem() is not None
    assert top.itemAt(4).widget() is header.edit_button


def test_shared_entity_header_uses_one_context_line(qapp):
    header = EntityHeaderWidget()
    header.set_content(
        title="Block B1",
        status_text="Blasted",
        status_state="blasted",
        meta_values=("ID: BL-1", "Project / Domain: P / D", "Horizon: 630 m", "Geometry rev.: 2"),
    )
    assert header.context.text() == (
        "ID: BL-1  ·  Project / Domain: P / D  ·  Horizon: 630 m  ·  Geometry rev.: 2"
    )
    header.close(); qapp.processEvents()
