from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

import pytest

QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
QApplication = QtWidgets.QApplication
QWidget = QtWidgets.QWidget

from database.app_context import AppContext, CurrentUser  # noqa: E402


@dataclass
class MineRow:
    id: int
    name: str


@dataclass
class SiteRow:
    id: int
    mine_id: int
    name: str


@dataclass
class BlockRow:
    id: int
    site_id: int
    block_number: str
    horizon_m: Decimal | None


class FakeMineRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory
    def list_mines(self):
        return [MineRow(1, "Mine")]


class FakeSiteRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory
    def list_sites(self, mine_id=None):
        return [SiteRow(10, 1, "Domain")]


class FakeBlastBlockRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory


class FakeBlastBlockService:
    queries = 0
    def __init__(self, block_repo, site_repo):
        self.block_repo = block_repo
        self.site_repo = site_repo
    def list_blocks(self, **filters):
        type(self).queries += 1
        return [BlockRow(100, 10, "B-1", Decimal("123.45"))]


class FakeBlockListPage(QWidget):
    def __init__(self, context):
        super().__init__()
        from PySide6.QtCore import Signal, QObject
        class Emitter(QObject):
            data_changed = Signal()
        self._emitter = Emitter()
        self.data_changed = self._emitter.data_changed
    def set_filters(self, filters):
        self.filters = filters
    def open_block_id(self, block_id):
        self.block_id = block_id
    def create_block(self):
        self.created = True
    def open_directories(self):
        self.directories = True


class FakeHeader(QWidget):
    def __init__(self, context):
        super().__init__()
        from PySide6.QtCore import Signal, QObject
        class Emitter(QObject):
            create_block_requested = Signal()
            directories_requested = Signal()
        self._emitter = Emitter()
        self.create_block_requested = self._emitter.create_block_requested
        self.directories_requested = self._emitter.directories_requested


def test_real_main_window_constructs_lazily_without_assessment_query(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])

    import widgets.project_tree as project_tree
    import ui.main_window as main_window

    FakeBlastBlockService.queries = 0
    monkeypatch.setattr(project_tree, "MineRepository", FakeMineRepository)
    monkeypatch.setattr(project_tree, "SiteRepository", FakeSiteRepository)
    monkeypatch.setattr(project_tree, "BlastBlockRepository", FakeBlastBlockRepository)
    monkeypatch.setattr(project_tree, "BlastBlockService", FakeBlastBlockService)
    monkeypatch.setattr(main_window, "BlockListPage", FakeBlockListPage)
    monkeypatch.setattr(main_window, "Header", FakeHeader)
    monkeypatch.setattr(main_window, "apply_window_icon", lambda window: None)

    def fail_import(*args, **kwargs):
        raise AssertionError("AssessmentWorkspacePage must stay lazy during MainWindow construction")
    monkeypatch.setattr(main_window.MainWindow, "_construct_assessment_page", fail_import)

    context = AppContext(
        session_factory=lambda: None,
        current_user=CurrentUser(1, "admin", None, "admin"),
        storage_root=tmp_path,
    )
    window = main_window.MainWindow(context)

    assert hasattr(window.tree, "site_selected")
    assert not window.assessment_nav_button.isEnabled()
    assert window.assessment_page is None
    assert window.assessment_site_id is None
    assert FakeBlastBlockService.queries >= 1
    assert "ui.pages.assessment_workspace_page" not in __import__("sys").modules
