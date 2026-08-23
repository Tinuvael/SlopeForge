from pathlib import Path


def test_assignment_dialog_supports_individual_and_polygon_selection():
    source = Path("ui/dialogs/drillhole_group_assignment_dialog.py").read_text(encoding="utf-8")
    assert '"individual"' in source
    assert '"polygon"' in source
    assert "hole_ids_in_polygon" in source
    assert 'tr("Select individually")' in source
    assert 'tr("Select by polygon")' in source
