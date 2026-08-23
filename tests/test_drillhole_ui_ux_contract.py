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


def test_actual_import_is_disabled_until_design_drillholes_exist():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    assert 'design_exists = self._current_row("design") is not None' in source
    assert 'tr("Import design drillholes before adding as-drilled holes.")' in source


def test_automatic_values_are_marked_and_read_only_in_existing_group_forms():
    source = Path("ui/pages/technical_card_widgets.py").read_text(encoding="utf-8")
    assert '"Auto from design holes"' in source
    assert '"Auto from as-drilled"' in source
    assert 'widget.setReadOnly(True)' in source


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
