"""Architecture-level routing regressions for the tree-driven MainWindow."""
from pathlib import Path


def source(path): return Path(path).read_text(encoding="utf-8")

def test_tree_is_primary_navigation_without_project_lines_branch():
    tree=source("widgets/project_tree.py")
    assert '"Project Lines"' not in tree
    assert '"type":"horizon"' in tree and '"type":"interval"' in tree
    assert 'kind in {"folder","horizon","interval"}' in tree

def test_project_and_domain_filters_are_user_facing():
    tree=source("widgets/project_tree.py")
    assert "project_filter" in tree and "domain_filter" in tree and "status_filter" in tree
    assert "mine_filter" not in tree and "site_filter" not in tree
    assert "Show archived" in tree

def test_site_domain_block_and_area_routes_exist():
    main=source("ui/main_window.py")
    for method in ("select_site", "select_domain", "open_block_from_tree", "open_area_from_tree"):
        assert f"def {method}" in main
    assert "AssessmentAreaPage" in main

def test_cancel_and_discard_share_one_leave_guard():
    main=source("ui/main_window.py")
    assert main.count("def _guard_leave") == 1
    guard=main[main.index("def _guard_leave"):main.index("def _set_context")]
    assert "StandardButton.Discard" in guard
    assert "cancel_active_workflow" in guard
    assert "return False" in guard

def test_missing_project_lines_warning_and_no_drawing_before_check():
    main=source("ui/main_window.py")
    area=main[main.index("def _add_area"):main.index("def _archive_selected")]
    assert "Сначала загрузите проектные линии для карьера." in area
    assert area.index("get_active") < area.index("AssessmentAreaCreationPage")

def test_block_creation_reuses_blast_event_dialog_and_links_event():
    main=source("ui/main_window.py")
    block=main[main.index("def _add_block"):main.index("def _add_area")]
    assert "BlastEventDialog" in block
    assert 'setCurrentText("production")' in block
    assert "create_event" in block and "blast_block_id=block_id" in block

def test_site_dashboard_owns_project_lines_management():
    pages=source("ui/pages/navigation_pages.py")
    assert "class SiteDashboardPage" in pages
    assert "Import / Update Project Lines" in pages
    assert "ProjectLinesRepository" in pages

def test_archive_button_and_block_service_are_connected():
    assert "archive_button" in source("ui/header.py")
    main=source("ui/main_window.py")
    assert "archive_requested.connect(self._archive_selected)" in main
    assert "set_archived" in source("services/blast_block_service.py")

def test_block_page_embeds_geometry_and_revision_safe_technical_card_tabs():
    block=source("ui/pages/block_list_page.py")
    assert "event_for_block" in block and "active_geometry_revision" in block
    assert "TechnicalCardEditorWidget" in block
    assert 'take_tab("Геомеханика")' in block
    assert 'take_tab("Бурение и заряды")' in block
    assert 'take_tab("Факт")' in block

def test_area_page_is_focused_without_legacy_mode_switch():
    area=source("ui/pages/assessment_area_page.py")
    assert "class AssessmentAreaPage" in area
    assert '"Overview"' in area and '"Assessment"' in area and '"Result"' in area
    assert '"Linked events"' in area
    assert "Blast Events / Assessment Areas" not in area
    assert "AssessmentAreaEvaluationDialog" in area and "Матрица" in area
    assert "Design Achievement Index" not in area  # calculated by reused dialog/QuadrantPlot

def test_area_links_and_focused_creation_are_reused():
    area=source("ui/pages/assessment_area_page.py")
    for action in ("confirm_link","exclude_link","restore_suggestion","refresh_suggestions"):
        assert action in area
    creation=source("ui/pages/assessment_area_creation_page.py")
    assert "AssessmentAreaCreationPage" in creation and "plan_view" in creation
    assert "Blast Events" not in creation and "TechnicalCard" not in creation
    main=source("ui/main_window.py")
    assert "AssessmentAreaCreationPage" in main and "_area_created" in main
