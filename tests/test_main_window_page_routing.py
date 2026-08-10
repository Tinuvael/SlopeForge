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
    assert "Load Project Lines for the project first." in area
    assert area.index("get_active") < area.index("AssessmentAreaCreationPage")

def test_block_creation_reuses_blast_event_dialog_and_links_event():
    main=source("ui/main_window.py")
    block=main[main.index("def _add_blast_event"):main.index("def _add_area")]
    assert "BlastEventDialog" in block
    assert "event.event_type==\"contour\"" in block
    assert "create_event" in block and "blast_block_id=block_id" in block

def test_site_dashboard_owns_project_lines_management():
    pages=source("ui/pages/dashboards/site_dashboard.py")
    assert "class SiteDashboardPage" in pages
    assert "Import / Update Project Lines" in pages
    assert "ProjectLinesRepository" in pages

def test_archive_button_and_block_service_are_connected():
    assert "archive_button" in source("ui/header.py")
    main=source("ui/main_window.py")
    assert "archive_requested.connect(self._archive_selected)" in main
    assert "set_archived" in source("services/blast_block_service.py")

def test_block_page_embeds_geometry_and_revision_safe_technical_card_tabs():
    block=source("ui/pages/block_page.py")
    assert "event_for_block" in block and "active_geometry_revision" in block
    assert "TechnicalCardEditorWidget" in block
    assert 'take_tab(tr("Geomechanics"))' in block
    assert 'take_tab(tr("Drilling and charging"))' in block
    assert 'take_tab(tr("Execution fact"))' in block

def test_area_page_is_focused_without_legacy_mode_switch():
    area=source("ui/pages/assessment_area_page.py")
    assert "class AssessmentAreaPage" in area
    assert '"Overview"' in area and '"Assessment"' in area and '"Result"' in area
    assert '"Linked events"' in area
    assert "Blast Events / Assessment Areas" not in area
    assert "AssessmentAreaEvaluationDialog" in area and "Matrix" in area
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

def test_entity_page_integration_corrections_are_visible():
    block=source("ui/pages/block_page.py")
    assert 'QPushButton(tr("Save draft"))' in block and 'QPushButton(tr("Complete"))' in block
    assert "save_draft()" in block and "complete()" in block
    area=source("ui/pages/assessment_area_page.py")
    assert "self.assessment_sections=QTabWidget()" in area
    assert 'evaluation_editor.take_tab(tr(title))' in area
    assert "self.assessment_sections.setCurrentIndex(0)" in area
    assert "page.setVisible(True)" not in area
    assert "Save an assessment draft first" not in area
    assert "prepare_evaluation_attachment_owner" in area
    creation=source("ui/pages/assessment_area_creation_page.py")
    for label in ("Fit","Project Lines","Grid","Undo vertex","Finish polygon / Continue","Confirm boundaries","Cancel"):
        assert label in creation

def test_refresh_reloads_filters_and_area_construction_is_guarded():
    main=source("ui/main_window.py")
    refresh=main[main.index("def refresh_project_data"):main.index("def closeEvent")]
    assert refresh.index("reload_filters") < refresh.index("load_data")
    assert main.count("Could not open the assessment area") == 1
    assert "Could not start assessment area creation" in main
    assert "Could not open boundary editing" in main

def test_existing_block_dialog_preserves_zero_and_none_and_locks_linked_domain():
    dialog=source("ui/block_dialog.py")
    assert '"" if block.horizon_m is None else str(block.horizon_m)' in dialog
    assert "self.planned_date.setDate(self.planned_date.minimumDate())" in dialog
    assert "is_linked_to_production_event" in dialog and "self.domain.setEnabled(False)" in dialog

def test_contour_event_ui_and_tree_architecture():
    tree=source("widgets/project_tree.py")
    assert '"Blast events"' in tree and '"Blast blocks"' not in tree
    assert "list_contour_events" in tree and '"type":"contour"' in tree
    header=source("ui/header.py")
    for label in ("Add blast event","Add assessment area"):
        assert label in header
    main=source("ui/main_window.py")
    assert "def _add_blast_event" in main and "open_contour_from_tree" in main
    assert "event.event_type==\"contour\"" in main
    page=source("ui/pages/contour_event_page.py")
    assert "ContourEventPage" in page and "Geomechanics" not in page
    assert '"Blast design"' in page and '"Execution fact"' in page

def test_area_creation_cancel_drawing_is_not_page_cancel():
    creation=source("ui/pages/assessment_area_creation_page.py")
    cancel=creation[creation.index("def _cancel_drawing"):creation.index("def _close_page")]
    assert "cancel_active_workflow" in cancel and "cancelled.emit" not in cancel
    assert "def _start_drawing" in creation and "start_area_drawing" in creation


def test_stale_block_engineering_is_cleared_and_read_only_is_defensive():
    block=source("ui/pages/block_page.py")
    render=block[block.index("def _render_engineering"):block.index("def _reimport_geometry")]
    assert "self._clear_engineering()" in render
    assert "self.technical_card_editor=None" in render
    assert "set_reimport_enabled(False)" in render
    assert "self.current_block.is_archived" in render
    reimport=block[block.index("def _reimport_geometry"):]
    assert "not self.context.current_user.can_edit" in reimport and "self.current_block.is_archived" in reimport

def test_area_and_contour_mutations_are_defensively_read_only():
    area=source("ui/pages/assessment_area_page.py")
    assert "self.read_only=not context.current_user.can_edit or self.area.is_archived" in area
    assert "def _ensure_editable" in area
    for method in ("_change_link","recalculate_links","add_manual_link","_save_evaluation","_request_edit_boundaries"):
        section=area[area.index(f"def {method}"):]
        assert "_ensure_editable" in section[:500]
    contour=source("ui/pages/contour_event_page.py")
    assert "self.read_only=not context.current_user.can_edit or self.blast_event.is_archived" in contour
    assert "if self.read_only" in contour and "set_reimport_enabled(not self.read_only)" in contour

def test_restart_drawing_distinguishes_create_and_edit_modes():
    creation=source("ui/pages/assessment_area_creation_page.py")
    restart=creation[creation.index("def _start_drawing"):creation.index("def _toggle_lines")]
    assert "if self.edit_area_id" in restart
    assert "open_assessment_area(self.edit_area_id)" in restart
    assert "edit_area_boundaries()" in restart
    assert "else:self.controller.workspace.start_area_drawing()" in restart


def test_area_completion_is_not_driven_by_generic_state_saved():
    creation=source("ui/pages/assessment_area_creation_page.py")
    assert "state_saved.connect" not in creation
    confirm=creation[creation.index("def _confirm"):creation.index("def _sync_status")]
    assert confirm.index("confirm_refined_polygon()") < confirm.index('workflow_state!="IDLE"')
    assert "_edit_revision_count" in confirm and "_edit_active_revision_id" in confirm
    assert "_completion_emitted=True" in confirm


def test_successful_area_edit_has_dedicated_unguarded_completion_path():
    main=source("ui/main_window.py")
    finish=main[main.index("def _finish_area_boundary_edit"):main.index("def _cancel_area_boundary_edit")]
    assert "self.assessment_page=None" in finish
    assert "refresh_project_data()" in finish and "open_area_from_tree" in finish
    assert "save_now" not in finish and "_guard_leave" not in finish
    assert "removeWidget(edit_page)" in finish and "deleteLater()" in finish
    cancel=main[main.index("def _cancel_area_boundary_edit"):main.index("def _edit_area_boundaries")]
    assert "open_area_from_tree" in cancel
