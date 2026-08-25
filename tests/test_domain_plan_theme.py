from pathlib import Path


def test_domain_geometry_plan_background_uses_application_palette() -> None:
    source = Path("ui/dialogs/domain_geometry_editor.py").read_text(encoding="utf-8")
    draw_background = source.split("def drawBackground", 1)[1].split("class DomainGeometryEditorDialog", 1)[0]

    assert "QPalette.ColorRole.AlternateBase" in draw_background
    assert "QPalette.ColorRole.Dark" in draw_background
    assert 'QColor("#F8FAFC")' not in draw_background
    assert 'QColor("#E2E8F0")' not in draw_background
