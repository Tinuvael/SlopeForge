"""Small permanent architecture ratchets for the canonical layer layout."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOTS = ("app", "application", "database", "domain", "infrastructure", "repositories", "services", "reports", "ui", "widgets")
REMOVED_PACKAGE = "prototype" + "_2d"

# Deliberately retired entry points outside the canonical layer layout.  The
# top-level prototype package also covers all of its former Phase 3A/3B modules.
PERMANENTLY_REMOVED_PATHS = {
    "ui/pages/assessment_workspace_page.py",
    "ui/widgets/assessment_workspace.py",
    "ui/directory_dialog.py",
    "ui/prototype_2d",
    REMOVED_PACKAGE,
}

PERMANENTLY_REMOVED_IMPORTS = {
    "ui.pages.assessment_workspace_page",
    "ui.widgets.assessment_workspace",
    "ui.directory_dialog",
    "ui.prototype_2d",
}

MINE_COMPATIBILITY_FILES = {
    "database/models.py", "repositories/blast_block_repository.py",
    "repositories/mine_repository.py", "repositories/site_repository.py",
    "services/project_service.py", "widgets/project_tree.py", "ui/header.py",
}


def production_files() -> list[Path]:
    return sorted(path for root in PRODUCTION_ROOTS for path in (ROOT / root).rglob("*.py"))


def imports(path: Path) -> set[str]:
    result = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            result.add(node.module)
    return result


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def has_prefix(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)


def test_permanently_removed_compatibility_paths_do_not_return() -> None:
    assert not {path for path in PERMANENTLY_REMOVED_PATHS if (ROOT / path).exists()}


def test_production_and_tests_do_not_import_removed_prototype() -> None:
    candidates = set(production_files()) | set((ROOT / "tests").rglob("*.py"))
    offenders = {
        relative(path) for path in candidates
        if any(has_prefix(name, (REMOVED_PACKAGE,)) for name in imports(path))
    }
    assert offenders == set()


def test_production_and_tests_do_not_import_removed_ui_compatibility() -> None:
    candidates = set(production_files()) | set((ROOT / "tests").rglob("*.py"))
    offenders = {
        relative(path) for path in candidates
        if any(has_prefix(name, tuple(PERMANENTLY_REMOVED_IMPORTS)) for name in imports(path))
    }
    assert offenders == set()


def test_domain_is_framework_and_outer_layer_free() -> None:
    forbidden = ("PySide6", "sqlalchemy", "database", "repositories", "infrastructure", "application", "ui")
    offenders = {
        relative(path) for path in (ROOT / "domain").rglob("*.py")
        if any(has_prefix(name, forbidden) for name in imports(path))
    }
    assert offenders == set()


def test_application_is_qt_and_concrete_persistence_free() -> None:
    forbidden = ("PySide6", "sqlalchemy", "database", "repositories")
    offenders = {
        relative(path) for path in (ROOT / "application").rglob("*.py")
        if any(has_prefix(name, forbidden) for name in imports(path))
    }
    assert offenders == set()


def test_entity_page_controller_has_no_direct_persistence_dependencies() -> None:
    path = ROOT / "ui/pages/entity_page_controller.py"
    assert not any(has_prefix(name, ("repositories", "sqlalchemy", "database"))
                   for name in imports(path))


def test_entity_editing_application_boundary_is_framework_free() -> None:
    paths = [
        ROOT / "application/services/entity_editing.py",
        ROOT / "application/ports/assessment_state.py",
    ]
    forbidden = ("PySide6", "sqlalchemy", "database", "repositories", "ui")
    assert not {
        relative(path) for path in paths
        if any(has_prefix(name, forbidden) for name in imports(path))
    }


def test_attachment_filesystem_adapter_is_qt_free() -> None:
    path = ROOT / "infrastructure/files/attachments.py"
    assert not any(has_prefix(name, ("PySide6", "ui")) for name in imports(path))


def test_geometry_import_adapters_do_not_import_ui() -> None:
    offenders = {
        relative(path) for path in (ROOT / "infrastructure/geometry_import").rglob("*.py")
        if any(has_prefix(name, ("PySide6", "ui")) for name in imports(path))
    }
    assert offenders == set()


def test_mine_term_stays_inside_documented_compatibility_files() -> None:
    offenders = {
        relative(path) for path in production_files()
        if re.search(r"\bmines?\b", path.read_text(encoding="utf-8"), re.IGNORECASE)
    }
    assert offenders <= MINE_COMPATIBILITY_FILES


def test_assessment_type_aliases_are_owned_only_by_assessment_entities() -> None:
    blasting_source = (ROOT / "domain/blasting/entities.py").read_text(encoding="utf-8")
    for name in ("HorizonSliceRole", "LinkStatus", "LinkSource"):
        assert name not in blasting_source


def test_create_blast_event_application_boundary_is_framework_free() -> None:
    paths = [
        ROOT / "application/use_cases/create_blast_event.py",
        ROOT / "application/use_cases/__init__.py",
    ]
    forbidden = ("PySide6", "sqlalchemy", "database", "repositories", "ui")
    assert {
        relative(path) for path in paths
        if any(has_prefix(name, forbidden) for name in imports(path))
    } == set()


def test_main_window_blast_event_creation_is_only_ui_orchestration() -> None:
    source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    method = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef) and node.name == "_add_blast_event")
    method_source = ast.get_source_segment(source, method) or ""
    for forbidden in (
        "EntityPageController", "AssessmentStateRepository", "BlastEventService",
        "BlastBlockService", "database.models", "session_factory", "controller.save",
    ):
        assert forbidden not in method_source
