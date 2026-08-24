from pathlib import Path


def test_group_assignment_action_is_kept_in_group_header():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    assert 'assign = set_button_role(QPushButton(tr("Assign holes")), "secondary")' in source
    assert "header.insertWidget(max(0, header.count() - 1), assign)" in source
    assert "box.layout().addLayout(row)" not in source


def test_production_assignment_only_updates_assigned_or_explicitly_changed_groups():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    start = source.index("    def _apply_production_design_assignments")
    end = source.index("    def _primary_contour_group", start)
    method = source[start:end]
    assert "if assigned or group.id in changed_group_ids:" in method


def test_design_reimport_recalculates_groups_that_lost_all_holes():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    start = source.index("    def import_drillholes")
    end = source.index("    def assign_holes_to_group", start)
    method = source[start:end]
    assert "previous_design_group_ids = {" in method
    assert "changed_group_ids=previous_design_group_ids" in method


def test_actual_import_is_disabled_until_design_drillholes_exist():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    assert 'design_exists = self._current_row("design") is not None' in source
    assert 'tr("Import design drillholes before adding as-drilled holes.")' in source


def test_automatic_values_are_marked_and_read_only_in_existing_group_forms():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    assert '"Auto from design holes"' in source
    assert '"Auto from as-drilled"' in source
    assert 'widget.setReadOnly(True)' in source


def test_contour_fact_uses_same_design_hole_matches_as_production_when_grouped():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    start = source.index("    def _apply_contour_actual")
    end = source.index("    def _apply_actual_group_matches", start)
    method = source[start:end]
    assert 'design_holes = self._current_holes("design")' in method
    assert "if any(hole.engineering_group_id for hole in design_holes):" in method
    assert "self._apply_actual_group_matches(" in method
    assert "group_ids_to_refresh" in method


def test_contour_fact_auto_fields_follow_any_explicit_design_group():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    start = source.index("    def _actual_auto_fields")
    end = source.index("    def _actual_angle_metrics", start)
    method = source[start:end]
    assert "hole.engineering_group_id == group.design_group_id" in method
    assert "not any_assigned" in method


def test_angular_qa_is_shown_globally_and_per_actual_group():
    page = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    card = Path("ui/pages/drillhole_dataset_widgets.py").read_text(encoding="utf-8")
    for label in ("Mean azimuth deviation, °", "Mean inclination deviation, °"):
        assert label in page
        assert label in card
    assert 'abs(float(item[key]))' in page
    assert 'abs(float(item["azimuth_deviation_deg"]))' in card
    assert 'abs(float(item["inclination_deviation_deg"]))' in card


def test_collar_qa_is_plan_xy_and_is_labeled_explicitly():
    page = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    card = Path("ui/pages/drillhole_dataset_widgets.py").read_text(encoding="utf-8")
    assert 'collar = self._deviation_values(matches, "collar_distance_xy_m")' in page
    assert 'float(item["collar_distance_xy_m"])' in card
    assert '"Mean collar plan deviation"' in card
    assert '"Max collar plan deviation"' in card
    assert '"Mean collar plan deviation, m"' in page
    assert '"Max collar plan deviation, m"' in page
    assert 'collar = self._deviation_values(matches, "collar_deviation_3d_m")' not in page


def test_drillhole_dataset_card_has_small_gap_below_tabs():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    start = source.index("class _DrillholeEngineeringPage")
    end = source.index("class TechnicalCardEditorWidget", start)
    page = source[start:end]
    assert "layout.setContentsMargins(0, 8, 0, 0)" in page


def test_successful_import_uses_inline_feedback_instead_of_modal_confirmation():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    assert "Imported successfully. Automatic values were updated" in source
    assert "QMessageBox.information(" not in source


def test_assignment_dialog_has_visible_mode_state_and_fit_action():
    source = Path("ui/dialogs/drillhole_group_assignment_dialog.py").read_text(encoding="utf-8")
    assert "self.mode_group.setExclusive(True)" in source
    assert 'set_button_role(self.individual, "secondary" if polygon_mode else "primary")' in source
    assert 'QPushButton(tr("Fit view"))' in source
    assert "self.finish_polygon.setVisible(polygon_mode)" in source
