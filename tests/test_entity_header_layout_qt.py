from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from ui.pages.assessment_area_page import AssessmentAreaPage
from ui.pages.block_card_widgets import BlockHeaderWidget
from ui.pages.contour_event_page import ContourEventPage


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _assert_title_status_stretch_edit(layout, title, status, edit):
    assert layout.count() == 4
    assert layout.itemAt(0).widget() is title
    assert layout.itemAt(1).widget() is status
    assert layout.itemAt(2).spacerItem() is not None
    assert layout.itemAt(3).widget() is edit


def test_block_header_order_is_title_status_stretch_edit(qapp):
    header = BlockHeaderWidget()
    top = header.layout.itemAt(0).layout()
    _assert_title_status_stretch_edit(top, header.title, header.status,
                                      header.edit_button)


def test_contour_header_order_is_title_status_stretch_edit(qapp):
    host = QWidget(); root = QVBoxLayout(host)
    event = SimpleNamespace(name="c4", id="C4", elevation=640,
                            event_date=None, is_archived=False)
    page = SimpleNamespace(blast_event=event, read_only=False, rev=None,
                           edit_metadata=lambda: None,
                           _refresh_workflow_presentation=lambda: None)
    ContourEventPage._header(page, root)
    top = root.itemAt(0).widget().layout.itemAt(0).layout()
    _assert_title_status_stretch_edit(top, top.itemAt(0).widget(),
                                      page.header_status, page.edit_button)


def test_assessment_header_order_is_title_status_stretch_edit(qapp):
    host = QWidget(); root = QVBoxLayout(host)
    revision = SimpleNamespace(min_elevation=600, max_elevation=650,
                               revision_number=2)
    area = SimpleNamespace(name="f1f1", id="A1", assessment_date=None,
                           is_archived=False,
                           active_geometry_revision=lambda: revision)
    page = SimpleNamespace(area=area, domain_name="North", read_only=False,
                           edit_metadata=lambda: None)
    AssessmentAreaPage._header(page, root)
    top = root.itemAt(0).widget().layout.itemAt(0).layout()
    _assert_title_status_stretch_edit(top, top.itemAt(0).widget(),
                                      page.header_status, page.edit_button)
