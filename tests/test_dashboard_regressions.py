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
        {"type": "MultiPoint", "coordinates": [[5, 6], [7, 8]]
        }
    ) == ((5.0, 6.0), (7.0, 8.0))
    assert _geometry_points({}) == ()


def test_plan_overview_is_read_only_and_actions_live_in_single_card_header():
    plan = source("ui/pages/dashboards/plan_overview.py")
    project = source("ui/pages/dashboards/site_dashboard.py")
    domain = source("ui/pages/dashboards/domain_dashboard.py")
    assert 'QCheckBox(tr("Project Lines"))' in plan
    assert 'OverviewLinkButton("Center")' in plan
    assert "primary_action_requested = Signal()" in plan
    assert "secondary_action_requested = Signal()" in plan
    assert "self.header.addWidget(self.lines)" in plan
    assert "self.layout.addLayout(self.controls)" not in plan
    assert "def wheelEvent" in plan
    assert "AnchorUnderMouse" in plan
    assert "self.scale(factor, factor)" in plan
    assert 'primary_action_label="Project Lines"' in project
    assert 'tr("Import lines")' in project
    assert 'tr("Update lines")' in project
    assert 'add_header_action("Clear")' not in domain
    for forbidden in ("edit_vertices", "setFlag", "ItemIsMovable", "ItemIsSelectable"):
        assert forbidden not in plan


def test_project_dashboard_data_cards_keep_one_bounded_aligned_row():
    project = source("ui/pages/dashboards/site_dashboard.py")
    geometry = source("ui/pages/dashboards/project_geometry_card.py")
    widgets = source("ui/pages/dashboards/widgets.py")

    assert "PROJECT_DATA_CARD_HEIGHT = 192" in project
    assert "PROJECT_DATA_ROW_HEIGHT = 44" in project
    assert "PROJECT_DATA_ROW_SPACING = 3" in project
    assert "data_row.setFixedHeight(PROJECT_DATA_CARD_HEIGHT)" in project
    assert "(self.domain_summary, self.lines_card, self.geometry_card)" in project
    assert "row_height=PROJECT_DATA_ROW_HEIGHT" in project
    assert "row_spacing=PROJECT_DATA_ROW_SPACING" in project
    assert "card.setMinimumWidth(0)" in project
    assert "QSizePolicy.Policy.Ignored" in project

    # A header action such as Project Lines -> Add must not increase the header
    # band and shift only that card's title/body downward.
    assert "HEADER_HEIGHT = 26" in widgets
    assert "self.header_host.setFixedHeight(self.HEADER_HEIGHT)" in widgets
    assert "button.setFixedHeight(self.HEADER_HEIGHT)" in widgets
    assert "ROW_HEIGHT = 44" in widgets

    # Design occupies the first body row and Actual survey the bottom row with
    # one flexible row-sized gap between them.
    assert "ROW_HEIGHT = 44" in geometry
    assert "host.setFixedHeight(self.ROW_HEIGHT)" in geometry
    assert 'self._add_dataset_row("design"' in geometry
    assert "self.body.addStretch(1)" in geometry
    assert 'self._add_dataset_row("actual"' in geometry
    assert "QSizePolicy.Policy.Ignored" in geometry


def test_dashboard_trends_use_stored_completed_revision_history_only():
    repository = source("repositories/dashboard_repository.py")
    assert "class TrendRow" in repository
    assert 'a.AssessmentAreaEvaluationRevision.status == "completed"' in repository
    assert "a.AssessmentAreaEvaluationRevision.assessment_date.is_not(None)" in repository
    assert "revision.design_achievement_index" in repository
    assert "revision.face_condition_index" in repository
    assert "calculate_revision" not in repository


def test_recent_activity_identifies_entity_and_uses_real_actor_sources():
    repository = source("repositories/dashboard_repository.py")
    widgets = source("ui/pages/dashboards/widgets.py")
    assert 'ActivityRow(\n                        "Block"' in repository
    assert 'ActivityRow(\n                        "Contour blast"' in repository
    assert '"Assessment Area"' in repository
    assert "AuditLogEntry" in repository
    assert "revision_actor.get(evaluation.logical_id" in repository
    assert "created_by_user" in repository
    assert "entity_name" in widgets
    assert "actor" in widgets


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
