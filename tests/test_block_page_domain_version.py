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
