import ast
from pathlib import Path


def test_drillhole_dataset_application_service_does_not_import_infrastructure():
    source = Path("application/services/drillhole_datasets.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(node.module)
    assert not any(name == "infrastructure" or name.startswith("infrastructure.") for name in imports)
    assert not any(name == "PySide6" or name.startswith("PySide6.") for name in imports)
