"""Small permanent architecture ratchets for the canonical layer layout."""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCTION_ROOTS = ("app", "application", "database", "domain", "infrastructure", "repositories", "ui")
REMOVED_PACKAGE = "prototype" + "_2d"

# Deliberately retired entry points outside the canonical layer layout.  The
# top-level prototype package also covers all of its former Phase 3A/3B modules.
PERMANENTLY_REMOVED_PATHS = {
    "ui/pages/assessment_workspace_page.py",
    "ui/widgets/assessment_workspace.py",
    "ui/directory_dialog.py",
    "ui/prototype_2d",
    REMOVED_PACKAGE,
    "database/database.py",
    "data/slopeforge.db",
    "reports",
    "widgets",
    "services",
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
    "infrastructure/db/project_creation.py", "ui/widgets/project_tree.py", "ui/header.py",
}

RETIRED_ROOT_IMPORTS = ("reports", "widgets", "services", "database.database")

# These three pre-Phase-7A application services directly select existing file
# and geometry adapters. Replacing them requires real ports/composition work and
# is explicitly outside this package-only follow-up; no other exception is allowed.
APPLICATION_INFRASTRUCTURE_EXCEPTIONS = {
    "application/services/attachments.py",
    "application/services/blast_events.py",
    "application/services/project_lines.py",
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


def absolute_imports(path: Path) -> set[str]:
    """Return imports without confusing ``from . import widgets`` with a root package."""
    result = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
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


def test_retired_package_imports_do_not_return() -> None:
    candidates = set(production_files()) | set((ROOT / "tests").rglob("*.py"))
    offenders = {
        relative(path) for path in candidates
        if any(has_prefix(name, RETIRED_ROOT_IMPORTS) for name in absolute_imports(path))
    }
    assert offenders == set()


def test_phase_7a_canonical_module_locations() -> None:
    assert (ROOT / "ui/widgets/project_tree.py").is_file()
    assert (ROOT / "infrastructure/reports/excel_project_report.py").is_file()
    assert (ROOT / "app/context.py").is_file()
    assert (ROOT / "application/dto/current_user.py").is_file()


def test_domain_is_framework_and_outer_layer_free() -> None:
    forbidden = ("PySide6", "sqlalchemy", "app", "database", "repositories", "infrastructure", "application", "ui")
    offenders = {
        relative(path) for path in (ROOT / "domain").rglob("*.py")
        if any(has_prefix(name, forbidden) for name in imports(path))
    }
    assert offenders == set()


def test_explosive_catalogue_has_one_canonical_orm_and_no_local_settings_storage() -> None:
    models = ast.parse((ROOT / "database/models.py").read_text(encoding="utf-8"))
    class_names = {node.name for node in models.body if isinstance(node, ast.ClassDef)}
    assert not class_names.intersection({"BlastDesign", "DrillingPattern", "ChargeSegment", "ExplosiveType"})
    assert "ExplosiveProduct" in class_names
    catalogue_sources = [
        ROOT / "domain/blasting/charge_design.py",
        ROOT / "application/use_cases/explosive_catalogue.py",
        ROOT / "infrastructure/db/explosive_catalogue.py",
        ROOT / "ui/engineering_catalogues_page.py",
    ]
    assert not {relative(path) for path in catalogue_sources
                if "QSettings" in path.read_text(encoding="utf-8")}


def test_application_is_qt_and_concrete_persistence_free() -> None:
    forbidden = ("PySide6", "sqlalchemy", "app", "database", "repositories", "infrastructure", "ui")
    offenders = {
        relative(path) for path in (ROOT / "application").rglob("*.py")
        if any(has_prefix(name, forbidden) for name in imports(path))
    }
    assert offenders == APPLICATION_INFRASTRUCTURE_EXCEPTIONS
    assert all(
        any(has_prefix(name, ("infrastructure",)) for name in imports(ROOT / path))
        for path in APPLICATION_INFRASTRUCTURE_EXCEPTIONS
    )


def test_infrastructure_does_not_import_bootstrap_layer() -> None:
    offenders = {
        relative(path) for path in (ROOT / "infrastructure").rglob("*.py")
        if any(has_prefix(name, ("app",)) for name in imports(path))
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


def test_desktop_factory_always_supplies_focused_assessment_writer() -> None:
    source = (ROOT / "app/use_case_factory.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    factory = next(node for node in ast.walk(tree)
                   if isinstance(node, ast.FunctionDef)
                   and node.name == "create_entity_editing_session")
    factory_source = ast.get_source_segment(source, factory) or ""
    assert "writes=SqlAlchemyAssessmentWrites(context.session_factory)" in factory_source


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


def test_phase_4b2_ui_mutation_orchestration_does_not_return() -> None:
    controller = ROOT / "ui/pages/entity_page_controller.py"
    assert "application.services.assessment_event_links" not in controller.read_text(encoding="utf-8")
    for relative_path in ("ui/pages/block_page.py", "ui/pages/contour_event_page.py"):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert "BlastEventService" not in source
    source = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
    method = next(node for node in ast.walk(ast.parse(source))
                  if isinstance(node, ast.FunctionDef) and node.name == "_archive_selected")
    method_source = ast.get_source_segment(source, method) or ""
    for forbidden in (".archive(", ".restore(", "block_service.set_archived", "controller.save"):
        assert forbidden not in method_source


def test_block_archive_use_case_has_clean_application_dependencies() -> None:
    path = ROOT / "application/use_cases/set_blast_block_archived.py"
    forbidden = ("PySide6", "sqlalchemy", "database", "repositories", "ui")
    assert not any(has_prefix(name, forbidden) for name in imports(path))


def test_phase_4c_final_orchestration_boundaries() -> None:
    main = ROOT / "ui/main_window.py"
    imported = imports(main)
    assert not any(name in imported for name in (
        "repositories.domain_repository", "repositories.project_lines_repository",
        "services.project_service",
    ))
    source = main.read_text(encoding="utf-8")
    tree = ast.parse(source)
    methods = {node.name: ast.get_source_segment(source, node) or "" for node in ast.walk(tree)
               if isinstance(node, ast.FunctionDef)}
    assert not any(name in methods["_add_project"] for name in (
        "AssessmentDomainState", "ProjectLinesDatasetService", "ProjectLinesRepository", "ProjectService"))
    assert "DomainRepository.create" not in methods["_add_domain"]

    report_dialog = ROOT / "ui/dialogs/project_report_dialog.py"
    assert not ({"services.project_report_service", "reports.excel_project_report"} & imports(report_dialog))

    editor_source = (ROOT / "ui/editors/assessment_geometry_editor.py").read_text(encoding="utf-8")
    editor_tree = ast.parse(editor_source)
    confirm = next(node for node in ast.walk(editor_tree)
                   if isinstance(node, ast.FunctionDef) and node.name == "confirm_boundaries")
    confirm_source = ast.get_source_segment(editor_source, confirm) or ""
    assert not any(call in confirm_source for call in (
        "create_area(", "revise_area(", "refresh_suggestions(", "_save_callback("))


def test_phase_4c_application_modules_are_framework_free() -> None:
    paths = list((ROOT / "application/use_cases").glob("*.py")) + [
        ROOT / "application/ports/project_creation.py",
        ROOT / "application/ports/domain_creation.py",
        ROOT / "application/ports/project_navigation.py",
        ROOT / "application/ports/project_report.py",
        ROOT / "application/dto/project_report.py",
    ]
    forbidden = ("PySide6", "sqlalchemy", "database", "repositories", "ui", "infrastructure")
    assert not {relative(path) for path in paths
                if any(has_prefix(name, forbidden) for name in imports(path))}
