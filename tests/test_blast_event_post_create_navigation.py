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


def _dialog(monkeypatch, event_type):
    class Dialog:
        def __init__(self, _parent): pass
        def exec(self): return True
        def values(self):
            return {"name": "B-17" if event_type == "production" else "Contour",
                    "event_type": event_type, "event_date": date.today(),
                    "elevation": 610, "csv_path": "event.csv"}
    dialog_module = ModuleType("ui.dialogs.blast_event_dialog")
    dialog_module.BlastEventDialog = Dialog
    monkeypatch.setitem(sys.modules, "ui.dialogs.blast_event_dialog", dialog_module)


def _window(result):
    window = SimpleNamespace()
    window.selected_domain_id = 4; window.selected_site_id = 2; window.selected_domain_name = "D"
    window.context = SimpleNamespace(current_user=SimpleNamespace(id=7, can_edit=True))
    window.create_blast_event = SimpleNamespace(execute=lambda _command: result)
    window.refresh_project_data = lambda: None
    return window


def test_successful_contour_create_followed_by_open_failure_is_not_reported_as_create_failure(monkeypatch):
    method, namespace = _real_add_blast_event_method(); _dialog(monkeypatch, "contour")
    window = _window(SimpleNamespace(event_type="contour", event_id="BE-1"))
    window.open_contour_from_tree = lambda *_args: False
    warnings = []; namespace["QMessageBox"].warning = lambda _parent, title, message: warnings.append((title, message))

    method(window)

    assert len(warnings) == 1
    assert warnings[0][0] == "Blast event created"
    assert "created successfully" in warnings[0][1]


def test_successful_production_create_opens_block_page_with_same_event_id(monkeypatch):
    method, namespace = _real_add_blast_event_method(); _dialog(monkeypatch, "production")
    window = _window(SimpleNamespace(event_type="production", event_id="BE-PROD-17"))
    opened = []
    window.open_block_from_tree = lambda event_id, domain_id, site_id: opened.append((event_id, domain_id, site_id)) or True
    window.open_contour_from_tree = lambda *_args: False
    warnings = []; namespace["QMessageBox"].warning = lambda *_args: warnings.append(True)

    method(window)

    assert opened == [("BE-PROD-17", 4, 2)]
    assert warnings == []
