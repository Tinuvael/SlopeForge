"""Behavioural tests for the dependency audit itself."""
from tools.architecture_audit import inventory, report, strongly_connected


def test_inventory_resolves_from_imported_internal_modules() -> None:
    graph, _ = inventory()

    assert "database.assessment_models" in graph["repositories.assessment_state_repository"]
    assert "prototype_2d.technical_card" in graph["prototype_2d.domain"]


def test_report_is_deterministic_and_contains_expected_hotspots() -> None:
    first = report()
    second = report()

    assert first == second
    assert "## UI direct persistence/service imports" in first
    assert "prototype_2d.domain <-> prototype_2d.technical_card" in first


def test_cycle_detection_ignores_acyclic_edges() -> None:
    graph = {"a": {"b"}, "b": {"a", "c"}, "c": set()}

    assert strongly_connected(graph) == [("a", "b")]
