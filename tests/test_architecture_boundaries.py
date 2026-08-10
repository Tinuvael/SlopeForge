"""Small architecture ratchets: allow known debt, reject new coupling."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOTS = ("app", "database", "domain", "infrastructure", "repositories", "services", "reports", "prototype_2d", "ui", "widgets")

# Temporary compatibility debt.  Every entry should disappear in a later phase;
# additions require an architecture review rather than silently widening the net.
ARCHITECTURE_DEBT_ALLOWLIST = {
    "prototype_packages": {"prototype_2d"},
    "domain_qt_imports": {
        "prototype_2d/entity_attachments.py",
    },
    "mine_compatibility_files": {
        "database/models.py",
        "repositories/blast_block_repository.py",
        "repositories/mine_repository.py",
        "repositories/site_repository.py",
        "services/project_service.py",
        "widgets/project_tree.py",
        "ui/header.py",
    },
}

MIGRATED_GEOMETRY_SYMBOLS = {
    "DatamineLine",
    "DataminePoint",
    "PlanGeometry",
    "PlanLineString",
    "PlanMultiPoint",
    "PlanPoint",
    "PlanPolygon",
    "plan_geometry_from_dict",
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


def imported_names(path: Path, module: str) -> set[str]:
    """Return names imported with ``from module import ...``."""
    return {
        alias.name
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom) and node.module == module
        for alias in node.names
    }


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def test_normal_entity_pages_do_not_import_ui_prototype() -> None:
    pages = (ROOT / "ui/pages").rglob("*.py")
    offenders = {relative(path) for path in pages if any(name.startswith("ui.prototype_2d") for name in imports(path))}
    assert offenders == set()


def test_compatibility_ui_is_not_imported_by_production() -> None:
    offenders = {relative(path) for path in production_files()
                 if not relative(path).startswith("ui/prototype_2d/")
                 and any(name.startswith("ui.prototype_2d") for name in imports(path))}
    assert offenders == set()


def test_no_new_ui_prototype_modules() -> None:
    assert not (ROOT / "ui/prototype_2d").exists()


def test_removed_workspace_and_json_compatibility_modules_do_not_return() -> None:
    removed = {
        "ui/pages/assessment_workspace_page.py",
        "ui/widgets/assessment_workspace.py",
        "prototype_2d/blast_event_storage.py",
        "ui/directory_dialog.py",
    }
    assert not {path for path in removed if (ROOT / path).exists()}
    forbidden_imports = {
        "ui.pages.assessment_workspace_page",
        "ui.widgets.assessment_workspace",
        "prototype_2d.blast_event_storage",
    }
    offenders = {relative(path) for path in production_files() if imports(path) & forbidden_imports}
    assert offenders == set()


def test_no_new_prototype_named_production_packages() -> None:
    found = set()
    for path in production_files():
        for parent in path.relative_to(ROOT).parents:
            if parent.name.startswith("prototype_"):
                found.add(parent.as_posix())
    assert found <= ARCHITECTURE_DEBT_ALLOWLIST["prototype_packages"]


def test_pure_algorithm_modules_do_not_import_ui_frameworks() -> None:
    candidates = (ROOT / "prototype_2d").glob("*.py")
    offenders = {relative(path) for path in candidates
                 if any(name.startswith("PySide6") for name in imports(path))}
    assert offenders <= ARCHITECTURE_DEBT_ALLOWLIST["domain_qt_imports"]


def test_pure_algorithm_modules_do_not_import_persistence_frameworks() -> None:
    candidates = (ROOT / "prototype_2d").glob("*.py")
    offenders = {
        relative(path)
        for path in candidates
        if any(name == "database" or name.startswith(("database.", "sqlalchemy"))
               for name in imports(path))
    }
    assert offenders == set()


def test_geometry_domain_is_framework_and_infrastructure_free() -> None:
    candidates = list((ROOT / "domain/geometry").rglob("*.py"))
    candidates.append(ROOT / "domain/project/domain_geometry.py")
    forbidden = ("PySide6", "sqlalchemy", "database", "repositories", "infrastructure", "ui")
    offenders = {relative(path) for path in candidates
                 if any(name == item or name.startswith(item + ".")
                        for name in imports(path) for item in forbidden)}
    assert offenders == set()


def test_geometry_import_adapters_do_not_import_ui() -> None:
    offenders = {relative(path) for path in (ROOT / "infrastructure/geometry_import").rglob("*.py")
                 if any(name == "PySide6" or name.startswith(("PySide6.", "ui."))
                        for name in imports(path))}
    assert offenders == set()


def test_removed_prototype_geometry_modules_do_not_return() -> None:
    modules = {"models", "geometry", "domain_geometry", "csv_importer", "dxf_importer",
               "line_geometry_importer", "blast_geometry"}
    assert not {name for name in modules if (ROOT / "prototype_2d" / f"{name}.py").exists()}
    forbidden = {f"prototype_2d.{name}" for name in modules}
    offenders = {relative(path) for path in production_files() if imports(path) & forbidden}
    assert offenders == set()


def test_migrated_geometry_symbols_use_the_canonical_module() -> None:
    """Keep callers off the temporary Phase 3A compatibility re-export."""
    candidates = set(production_files()) | set((ROOT / "tests").rglob("*.py"))
    offenders = {
        relative(path)
        for path in candidates
        if imported_names(path, "prototype_2d.domain") & MIGRATED_GEOMETRY_SYMBOLS
    }
    assert offenders == set()


def test_mine_term_stays_inside_documented_compatibility_files() -> None:
    offenders = set()
    for path in production_files():
        if re.search(r"\bmines?\b", path.read_text(encoding="utf-8"), re.IGNORECASE):
            offenders.add(relative(path))
    assert offenders <= ARCHITECTURE_DEBT_ALLOWLIST["mine_compatibility_files"]


def test_phase_3b_domain_modules_are_framework_free() -> None:
    candidates = (
        list((ROOT / "domain/blasting").rglob("*.py"))
        + list((ROOT / "domain/assessment").rglob("*.py"))
        + list((ROOT / "domain/attachments").rglob("*.py"))
        + [ROOT / "domain/project/project_lines.py"]
    )
    forbidden = ("PySide6", "sqlalchemy", "database", "repositories", "infrastructure", "application", "ui")
    offenders = {relative(path) for path in candidates
                 if any(name == item or name.startswith(item + ".")
                        for name in imports(path) for item in forbidden)}
    assert offenders == set()


def test_transitional_application_state_has_no_framework_or_persistence_imports() -> None:
    path = ROOT / "application/state/assessment_domain_state.py"
    forbidden = ("PySide6", "sqlalchemy", "database", "repositories")
    assert not {name for name in imports(path)
                if any(name == item or name.startswith(item + ".") for item in forbidden)}


def test_removed_phase_3b_modules_do_not_return() -> None:
    removed = {
        "prototype_2d/domain.py",
        "prototype_2d/technical_card.py",
        "prototype_2d/wall_assessment.py",
    }
    assert not {path for path in removed if (ROOT / path).exists()}
    forbidden = {
        "prototype_2d.domain",
        "prototype_2d.technical_card",
        "prototype_2d.wall_assessment",
    }
    candidates = set(production_files()) | set((ROOT / "tests").rglob("*.py"))
    offenders = {relative(path) for path in candidates if imports(path) & forbidden}
    assert offenders == set()


def test_assessment_type_aliases_are_owned_only_by_assessment_entities() -> None:
    blasting_source = (ROOT / "domain/blasting/entities.py").read_text(encoding="utf-8")
    for name in ("HorizonSliceRole", "LinkStatus", "LinkSource"):
        assert name not in blasting_source
