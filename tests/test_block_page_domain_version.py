"""Regression: later Block commands use the open controller's advanced token."""
import ast
from pathlib import Path


def test_block_edit_uses_controller_version_after_focused_write():
    tree = ast.parse(Path("ui/pages/block_page.py").read_text(encoding="utf-8"))
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "BlockDialog"]
    edit_call = next(call for call in calls if any(
        keyword.arg == "block" for keyword in call.keywords))
    expected = next(keyword.value for keyword in edit_call.keywords
                    if keyword.arg == "expected_version")
    assert ast.unparse(expected) == "self.entity_controller.expected_version"


def test_global_archive_uses_controller_version_not_frozen_block_row():
    tree = ast.parse(Path("ui/main_window.py").read_text(encoding="utf-8"))
    attributes = [ast.unparse(node) for node in ast.walk(tree)
                  if isinstance(node, ast.Attribute)]
    assert "self.block_page.entity_controller.expected_version" in attributes


def test_successful_archive_reopens_block_at_new_version_and_state():
    source = Path("ui/main_window.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == "_archive_selected")
    calls = [ast.unparse(node.func) for node in ast.walk(method) if isinstance(node, ast.Call)]
    assert "self.refresh_project_data" in calls
    assert "self.open_block_from_tree" in calls
    # The old behavior cleared selection and left the open controller at N.
    assert "self.selected_block_id = None" not in ast.unparse(method)
