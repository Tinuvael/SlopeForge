"""Behavioural MainWindow routing tests using tiny Qt/domain fakes.

The production PySide build needs libGL, which is intentionally absent in CI's
minimal image.  These fakes exercise MainWindow itself without PostgreSQL or the
assessment dependency graph.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest


class Signal:
    def __init__(self): self.slots = []
    def connect(self, slot): self.slots.append(slot)
    def emit(self, *args):
        return [slot(*args) for slot in list(self.slots)]


class Widget:
    def __init__(self, parent=None): self.parent = parent; self.deleted = False
    def setMaximumWidth(self, value): self.maximum_width = value
    def deleteLater(self): self.deleted = True


class MainWidget(Widget):
    def setWindowTitle(self, value): self.title = value
    def resize(self, *value): self.size = value
    def setCentralWidget(self, widget): self.central = widget
    def closeEvent(self, event): event.accept()


class Stack(Widget):
    def __init__(self): super().__init__(); self.widgets = []; self.current = None
    def addWidget(self, widget): self.widgets.append(widget); self.current = self.current or widget
    def removeWidget(self, widget): self.widgets.remove(widget)
    def setCurrentWidget(self, widget): self.current = widget
    def currentWidget(self): return self.current


class Button(Widget):
    def __init__(self, text): super().__init__(); self.text = text; self.clicked = Signal(); self.checked = False
    def setCheckable(self, value): self.checkable = value
    def setChecked(self, value): self.checked = value
    def isChecked(self): return self.checked
    def setEnabled(self, value): self.enabled = value
    def isEnabled(self): return self.enabled
    def setToolTip(self, value): self.tooltip = value


class ButtonGroup(Widget):
    def setExclusive(self, value): self.exclusive = value
    def addButton(self, button): pass


class Layout:
    def __init__(self, parent=None): self.parent = parent; self.items = []
    def addWidget(self, widget, *args): self.items.append(widget)
    def addLayout(self, layout): self.items.append(layout)


class MessageBox:
    class StandardButton:
        Cancel = 1
        Discard = 2
    answer = StandardButton.Cancel
    critical_calls = []
    @classmethod
    def warning(cls, *args): return cls.answer
    @classmethod
    def critical(cls, *args): cls.critical_calls.append(args)


class Tree(Widget):
    def __init__(self, context):
        super().__init__(); self.filters_changed = Signal(); self.block_selected = Signal(); self.site_selected = Signal(); self.domain_selected = Signal()
        self.reload_count = self.load_count = 0
    def reload_filters(self): self.reload_count += 1
    def load_data(self): self.load_count += 1


class BlockPage(Widget):
    def __init__(self, context):
        super().__init__(); self.data_changed = Signal(); self.calls = []
    def set_filters(self, *args): self.calls.append(("filters", args))
    def open_block_id(self, value): self.calls.append(("open", value))
    def create_block(self): self.calls.append(("create",))
    def open_directories(self): self.calls.append(("directories",))


class Header(Widget):
    def __init__(self, context):
        super().__init__(); self.create_block_requested = Signal(); self.directories_requested = Signal()


class Assessment(Widget):
    created = 0
    replacements = 0
    fail_construct = False
    fail_refresh = False
    def __init__(self, context, domain_id, domain_name, site_id=None, parent=None):
        if self.fail_construct: raise ValueError("bad json")
        super().__init__(parent); type(self).created += 1; self.active = False
        self.context, self.domain_id, self.domain_name, self.site_id = context, domain_id, domain_name, site_id
        self.refreshes = self.saves = self.cancels = self.reloads = 0; self.fail_save = False; self.fail_reload = False
    def refresh_workspace(self):
        self.refreshes += 1
        if self.fail_refresh: raise RuntimeError("refresh")
    def reload_from_repository(self):
        self.reloads += 1
        if self.fail_reload: raise RuntimeError("reload")
    def has_active_workflow(self): return self.active
    def cancel_active_workflow(self): self.active = False; self.cancels += 1; return True
    def save_now(self):
        self.saves += 1
        if self.fail_save: raise RuntimeError("save")
        if self.context.current_user.can_edit:
            type(self).replacements += 1


class CloseEvent:
    def __init__(self): self.ignored = self.accepted = False
    def ignore(self): self.ignored = True
    def accept(self): self.accepted = True


@pytest.fixture
def window_module(monkeypatch):
    Assessment.created = 0
    Assessment.replacements = 0
    Assessment.fail_construct = Assessment.fail_refresh = False
    MessageBox.answer = MessageBox.StandardButton.Cancel
    MessageBox.critical_calls = []
    qt = types.ModuleType("PySide6.QtWidgets")
    for name, value in {"QButtonGroup": ButtonGroup, "QMainWindow": MainWidget,
        "QMessageBox": MessageBox, "QWidget": Widget, "QHBoxLayout": Layout,
        "QVBoxLayout": Layout, "QPushButton": Button, "QStackedWidget": Stack}.items(): setattr(qt, name, value)
    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qt)
    modules = {
        "app.config": {"APP_NAME": "SlopeForge", "APP_VERSION": "test"},
        "app.qt": {"apply_window_icon": lambda window: None},
        "widgets.project_tree": {"ProjectTree": Tree},
        "ui.pages.block_list_page": {"BlockListPage": BlockPage},
        "ui.header": {"Header": Header},
        "database.app_context": {"AppContext": object},
    }
    for name, attrs in modules.items():
        module = types.ModuleType(name)
        for key, value in attrs.items(): setattr(module, key, value)
        monkeypatch.setitem(sys.modules, name, module)
    assessment_module = types.ModuleType("ui.pages.assessment_workspace_page")
    assessment_module.AssessmentWorkspacePage = Assessment
    # Prove importing MainWindow does not touch this lazily supplied module.
    monkeypatch.delitem(sys.modules, "ui.pages.assessment_workspace_page", raising=False)
    spec = importlib.util.spec_from_file_location("tested_main_window", Path("ui/main_window.py"))
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    assert "ui.pages.assessment_workspace_page" not in sys.modules
    monkeypatch.setitem(sys.modules, "ui.pages.assessment_workspace_page", assessment_module)
    return module


@pytest.fixture
def window(window_module):
    context = types.SimpleNamespace(current_user=types.SimpleNamespace(can_edit=True))
    return window_module.MainWindow(context)


def test_startup_is_lazy_and_keeps_tree_outside_stack(window):
    assert window.page is window.block_page
    assert window.page_stack.currentWidget() is window.block_page
    assert window.assessment_page is None and Assessment.created == 0
    assert window.tree not in window.page_stack.widgets
    assert window.block_nav_button.isChecked() and not window.assessment_nav_button.isChecked()
    assert not window.assessment_nav_button.isEnabled()
    assert not hasattr(window, "blast_events_window")


def test_assessment_created_once_added_and_navigation_reused(window):
    assert not window.show_assessment_page()
    assert window.open_assessment_for_domain(7, "North")
    page = window.assessment_page
    assert Assessment.created == 1 and page in window.page_stack.widgets
    assert window.page_stack.currentWidget() is page
    assert window.assessment_nav_button.isChecked() and not window.block_nav_button.isChecked()
    assert window.show_assessment_page() and window.assessment_page is page
    assert Assessment.created == 1 and page.refreshes == 1 and page.reloads == 0
    assert window.show_block_page() and window.page_stack.currentWidget() is window.block_page
    assert window.show_assessment_page() and window.assessment_page is page
    assert page.reloads == 1


def test_same_site_reopen_reload_failure_keeps_blocks_visible(window):
    assert window.open_assessment_for_domain(7, "North")
    page = window.assessment_page
    assert window.show_block_page()
    page.fail_reload = True
    assert not window.show_assessment_page()
    assert window.assessment_page is page and window.assessment_domain_id == 7
    assert window.page_stack.currentWidget() is window.block_page
    assert window.block_nav_button.isChecked() and not window.assessment_nav_button.isChecked()


def test_same_site_reopen_active_workflow_blocks_reload(window):
    assert window.open_assessment_for_domain(7, "North")
    page = window.assessment_page
    window.page_stack.setCurrentWidget(window.block_page)
    page.active = True
    assert not window.show_assessment_page()
    assert page.reloads == 0
    assert window.page_stack.currentWidget() is window.block_page


def test_tree_header_and_filters_route_without_postgresql(window):
    window.tree.domain_selected.emit(7, "North", 70); page = window.assessment_page
    window.tree.filters_changed.emit("mine")
    assert window.page_stack.currentWidget() is page
    assert window.block_page.calls[-1] == ("filters", ("mine",))
    window.tree.block_selected.emit(42)
    assert window.block_page.calls[-1] == ("open", 42)
    window.show_assessment_page(); window.header.create_block_requested.emit()
    assert window.block_page.calls[-1] == ("create",)
    window.show_assessment_page(); window.header.directories_requested.emit()
    assert window.block_page.calls[-1] == ("directories",)


def test_cancel_preserves_active_workflow_and_restores_buttons(window):
    window.open_assessment_for_domain(7, "North"); page = window.assessment_page; page.active = True
    MessageBox.answer = MessageBox.StandardButton.Cancel
    assert not window.show_block_page()
    assert page.active and page.cancels == 0 and page.saves == 0
    assert window.page_stack.currentWidget() is page and window.assessment_nav_button.isChecked()


def test_discard_cancels_saves_once_and_switches(window):
    window.open_assessment_for_domain(7, "North"); page = window.assessment_page; page.active = True
    MessageBox.answer = MessageBox.StandardButton.Discard
    assert window.show_block_page()
    assert not page.active and page.cancels == 1 and page.saves == 1


def test_save_failure_blocks_leave_and_actions(window):
    window.open_assessment_for_domain(7, "North"); page = window.assessment_page; page.fail_save = True
    assert not window.open_block_from_tree(7)
    assert window.page_stack.currentWidget() is page
    assert ("open", 7) not in window.block_page.calls
    assert window.assessment_nav_button.isChecked() and not window.block_nav_button.isChecked()


def test_close_saves_and_save_failure_ignores(window):
    window.open_assessment_for_domain(7, "North"); page = window.assessment_page
    event = CloseEvent(); window.closeEvent(event)
    assert page.saves == 1 and event.accepted
    page.fail_save = True; event = CloseEvent(); window.closeEvent(event)
    assert event.ignored and not event.accepted


def test_close_workflow_cancel_and_discard(window):
    window.open_assessment_for_domain(7, "North"); page = window.assessment_page; page.active = True
    event = CloseEvent(); window.closeEvent(event)
    assert event.ignored and page.active and page.saves == 0
    MessageBox.answer = MessageBox.StandardButton.Discard
    event = CloseEvent(); window.closeEvent(event)
    assert event.accepted and page.cancels == 1 and page.saves == 1


def test_viewer_can_leave_switch_site_and_close_without_writing(window):
    window.context.current_user.can_edit = False
    assert window.open_assessment_for_domain(7, "North")
    first = window.assessment_page

    assert window.show_block_page()
    assert first.saves == 1 and Assessment.replacements == 0
    assert window.open_assessment_for_domain(8, "South")
    second = window.assessment_page
    assert first.deleted and first.saves == 2

    event = CloseEvent()
    window.closeEvent(event)
    assert event.accepted and second.saves == 1
    assert Assessment.replacements == 0


def test_editor_navigation_save_still_persists(window):
    assert window.open_assessment_for_domain(7, "North")
    assert window.show_block_page()
    assert Assessment.replacements == 1


def test_construction_failure_stays_on_blocks(window):
    Assessment.fail_construct = True
    assert not window.open_assessment_for_domain(7, "North")
    assert window.assessment_page is None
    assert window.page_stack.currentWidget() is window.block_page
    assert window.block_nav_button.isChecked() and MessageBox.critical_calls


def test_existing_refresh_failure_preserves_page_and_instance(window):
    assert window.open_assessment_for_domain(7, "North"); page = window.assessment_page
    page.fail_refresh = True
    assert not window.show_assessment_page()
    assert window.assessment_page is page and not page.deleted
    assert window.page_stack.currentWidget() is page


def test_switching_site_saves_then_replaces_and_deletes_old_page(window):
    assert window.open_assessment_for_domain(7, "North")
    old = window.assessment_page
    assert window.open_assessment_for_domain(8, "South")
    assert old.saves == 1 and old.deleted
    assert old not in window.page_stack.widgets
    assert window.assessment_page.domain_id == 8
    assert window.assessment_domain_id == 8 and window.assessment_domain_name == "South"


def test_site_switch_cancel_save_and_target_load_failures_preserve_old(window):
    window.open_assessment_for_domain(7, "North")
    old = window.assessment_page
    old.active = True
    assert not window.open_assessment_for_domain(8, "South")
    assert window.assessment_page is old and window.assessment_domain_id == 7

    old.active = False; old.fail_save = True
    assert not window.open_assessment_for_domain(8, "South")
    assert window.assessment_page is old and not old.deleted

    old.fail_save = False; Assessment.fail_construct = True
    assert not window.open_assessment_for_domain(8, "South")
    assert window.assessment_page is old and window.assessment_domain_id == 7
    assert window.page_stack.currentWidget() is old


def test_site_switch_discard_cancels_workflow_and_proceeds(window):
    window.open_assessment_for_domain(7, "North")
    old = window.assessment_page; old.active = True
    MessageBox.answer = MessageBox.StandardButton.Discard
    assert window.open_assessment_for_domain(8, "South")
    assert old.cancels == 1 and old.saves == 1 and old.deleted


def test_obsolete_prototype_launcher_is_absent(window, window_module):
    assert not hasattr(window, "prototype_button")
    assert not hasattr(window, "prototype_2d_window")
    assert not hasattr(window, "open_2d_plan_prototype")
    assert "ui.prototype_2d.window" not in sys.modules
    assert "2D Plan Prototype" not in Path("ui/main_window.py").read_text(encoding="utf-8")
