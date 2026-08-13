import ast
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys


def _real_add_blast_event_method():
    """Compile the real method without importing the Qt-heavy module."""
    source = Path("ui/main_window.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == "_add_blast_event")
    namespace = {
        "QMessageBox": SimpleNamespace(warning=lambda *_args: None),
        "tr": lambda text: text,
        "domain_message": str,
        "CreateBlastEventCommand": lambda **values: SimpleNamespace(**values),
    }
    ast.fix_missing_locations(method)
    exec(compile(ast.Module(body=[method], type_ignores=[]), "ui/main_window.py", "exec"), namespace)
    return namespace["_add_blast_event"], namespace


def test_successful_create_followed_by_open_failure_is_not_reported_as_create_failure(monkeypatch):
    method, namespace = _real_add_blast_event_method()
    calls = []
    result = SimpleNamespace(event_type="contour", event_id="BE-1", blast_block_id=None)

    class UseCase:
        def execute(self, command):
            calls.append(command)
            return result

    class Dialog:
        def __init__(self, _parent): pass
        def exec(self): return True
        def values(self):
            return {"name": "Contour", "event_type": "contour", "event_date": date.today(),
                    "elevation": 610, "csv_path": "contour.csv"}

    dialog_module = ModuleType("ui.dialogs.blast_event_dialog")
    dialog_module.BlastEventDialog = Dialog
    monkeypatch.setitem(sys.modules, "ui.dialogs.blast_event_dialog", dialog_module)
    warnings = []
    namespace["QMessageBox"].warning = (
        lambda _parent, title, message: warnings.append((title, message)))

    window = SimpleNamespace()
    window.selected_domain_id = 4; window.selected_site_id = 2; window.selected_domain_name = "D"
    window.context = SimpleNamespace(current_user=SimpleNamespace(id=7, can_edit=True))
    window.create_blast_event = UseCase()
    refreshes = []
    window.refresh_project_data = lambda: refreshes.append(True)
    window.open_contour_from_tree = lambda *_args: False

    method(window)

    assert len(calls) == 1
    assert refreshes == [True]
    assert len(warnings) == 1
    assert warnings[0][0] == "Blast event created"
    assert "created successfully" in warnings[0][1]
    assert "Could not create blast event" not in warnings[0][1]
