from pathlib import Path

from repositories.dashboard_repository import _geometry_points, _number


def source(path):
    return Path(path).read_text(encoding="utf-8")


def test_dashboard_charts_never_import_matplotlib_qt_backend():
    charts = source("ui/pages/dashboards/charts.py")
    assert "backend_qtagg" not in charts
    assert "matplotlib" not in charts
    assert "QPainter" in charts


def test_dashboard_read_model_uses_entity_ids_not_domain_ids():
    repository = source("repositories/dashboard_repository.py")
    assert "area.logical_id" in repository
    assert "item.logical_id" in repository
    assert "AreaRow(area.domain_id" not in repository
    assert "BlastRow(item.domain_id" not in repository


def test_dashboard_slots_guard_constructor_failures():
    main = source("ui/main_window.py")
    site = main[main.index("def select_site"):main.index("def _open_domain_dashboard")]
    domain = main[main.index("def select_domain"):main.index("def open_block_from_tree")]
    assert "try:" in site and "Could not open project dashboard" in site
    assert "try:" in domain and "Could not open domain dashboard" in domain
    assert site.index("except Exception") < site.index("_set_context")
    assert domain.index("except Exception") < domain.index("_set_context")


def test_map_geometry_decoder_supports_persisted_plan_types():
    assert _geometry_points(
        {"type": "Polygon", "coordinates": [[[1, 2], [3, 4], [1, 2]]]}
    ) == ((1.0, 2.0), (3.0, 4.0), (1.0, 2.0))
    assert _geometry_points(
        {"type": "MultiPoint", "coordinates": [[5, 6], [7, 8]]}
    ) == ((5.0, 6.0), (7.0, 8.0))
    assert _geometry_points({}) == ()


def test_plan_overview_is_read_only_and_actions_live_in_card_header():
    plan = source("ui/pages/dashboards/plan_overview.py")
    project = source("ui/pages/dashboards/site_dashboard.py")
    assert 'QCheckBox(tr("Project Lines"))' in plan
    assert 'OverviewLinkButton("Center")' in plan
    assert "primary_action_requested = Signal()" in plan
    assert "secondary_action_requested = Signal()" in plan
    assert 'primary_action_label="Project Lines"' in project
    assert 'tr("Import Project Lines")' in project
    assert 'tr("Update Project Lines")' in project
    for forbidden in ("edit_vertices", "setFlag", "ItemIsMovable", "ItemIsSelectable"):
        assert forbidden not in plan


def test_real_quadrant_values_drive_shared_assessment_presentation():
    presentation = source("ui/assessment_result_presentation.py")
    for value in (
        "good_results",
        "geometry_achieved_condition_insufficient",
        "condition_good_geometry_unacceptable",
        "unacceptable",
    ):
        assert value in presentation
    assert '"good_results": AssessmentResultPresentation' in presentation
    assert '"#94a3b8"' in presentation


def test_dashboard_pages_do_not_restore_outer_scroll_or_tabs():
    for path in (
        "ui/pages/dashboards/site_dashboard.py",
        "ui/pages/dashboards/domain_dashboard.py",
    ):
        page = source(path)
        assert "QScrollArea" not in page
        assert "QTabWidget" not in page
        assert "QTableWidget" not in page


def test_dashboard_nullable_elevation_formatting_does_not_invent_values():
    assert _number(None) == "—"
