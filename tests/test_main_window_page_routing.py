from pathlib import Path


def source(path): return Path(path).read_text(encoding="utf-8")


def test_pages_use_application_services_for_runtime_data():
    project=source("ui/pages/dashboards/site_dashboard.py")
    domain=source("ui/pages/dashboards/domain_dashboard.py")
    block=source("ui/pages/block_page.py")
    contour=source("ui/pages/contour_event_page.py")
    area=source("ui/pages/assessment_area_page.py")
    assert "DashboardRepository" in project and "ProjectSurfaceDatasetService" not in project
    assert "DashboardRepository" in domain
    assert "ProductionBlastService" in block
    assert "ContourBlastService" in contour
    assert "AssessmentAreaContextRepository" not in area


def test_main_window_routes_tree_activation_without_unbounded_page_accumulation():
    main=source("ui/main_window.py")
    assert "self.stack=QStackedWidget()" in main
    assert "self.block_page=BlockPage(context)" in main
    assert "self.contour_page=ContourEventPage(context)" in main
    assert "self.assessment_page=AssessmentAreaPage(context)" in main
    assert "self.stack.addWidget(self.block_page)" in main
    assert "self.stack.addWidget(self.contour_page)" in main
    assert "self.stack.addWidget(self.assessment_page)" in main
    assert "def _replace_assessment_page" in main
    assert "removeWidget(old)" in main
    assert "old.deleteLater()" in main


def test_header_add_workflow_is_unified_for_blast_events():
    header=source("ui/header.py")
    assert 'tr("Add blast event")' in header
    assert "Add production" not in header
    assert "Add contour" not in header


def test_tree_has_virtual_horizon_and_interval_groups():
    tree=source("ui/widgets/project_tree.py")
    assert '"horizon"' in tree
    assert '"interval"' in tree
    assert "Horizon" in tree
    assert "Interval" in tree


def test_project_lines_are_project_wide_not_tree_branch():
    tree=source("ui/widgets/project_tree.py")
    dashboard=source("ui/pages/dashboards/site_dashboard.py")
    assert "project_lines" not in tree.lower()
    assert "Project Lines" in dashboard


def test_block_and_contour_tabs_match_product_model():
    block=source("ui/pages/block_page.py")
    contour=source("ui/pages/contour_event_page.py")
    for label in ("General information", "Blast design", "Execution fact", "Photos", "Documents", "History"):
        assert label in block
        assert label in contour
    assert "Geomechanics" in block
    assert "Geomechanics" not in contour


def test_assessment_area_tabs_match_product_model():
    page=source("ui/pages/assessment_area_page.py")
    for label in ("Overview", "Assessment", "Result", "Linked events", "Photos", "Documents", "History"):
        assert label in page


def test_assessment_result_keeps_separate_dai_fci_axes():
    source_text=source("ui/pages/assessment_area_page.py")
    assert "DAI" in source_text and "FCI" in source_text
    assert "average" not in source_text.lower()


def test_block_page_uses_one_persistent_entity_page():
    main=source("ui/main_window.py")
    assert "self.block_page=BlockPage(context)" in main
    assert "BlockPage(self.context)" not in main[main.index("def open_block_from_tree"):]


def test_contour_page_uses_one_persistent_entity_page():
    main=source("ui/main_window.py")
    assert "self.contour_page=ContourEventPage(context)" in main
    assert "ContourEventPage(self.context)" not in main[main.index("def open_contour_from_tree"):]


def test_successful_area_edit_has_dedicated_unguarded_completion_path():
    main=source("ui/main_window.py")
    finish=main[main.index("def _finish_area_boundary_edit"):main.index("def _cancel_area_boundary_edit")]
    assert "self.assessment_page=None" in finish
    assert "refresh_project_data()" in finish and "open_area_from_tree" in finish
    assert "save_now" not in finish and "_guard_leave" not in finish
    assert "removeWidget(edit_page)" in finish and "deleteLater()" in finish
    cancel=main[main.index("def _cancel_area_boundary_edit"):main.index("def _edit_area_boundaries")]
    assert "open_area_from_tree" in cancel


def test_analysis_button_opens_persistent_placeholder_before_report():
    header=source("ui/header.py")
    main=source("ui/main_window.py")
    page=source("ui/pages/analysis_page.py")
    assert "analysis_requested" in header and "Signal()" in header
    assert 'QPushButton(tr("Analysis"))' in header
    assert 'self.analysis_button.setIcon(ui_icon("analytics"))' in header
    assert header.index("layout.addWidget(self.analysis_button)") < header.index("layout.addWidget(self.report_button)")
    assert "AnalysisPlaceholderPage" in main
    assert "analysis_requested.connect(self._open_analysis)" in main
    assert "self._activate_page(self.analysis_page)" in main
    assert "current is self.analysis_page" in main
    assert 'tr("Analysis section is under development.")' in page
