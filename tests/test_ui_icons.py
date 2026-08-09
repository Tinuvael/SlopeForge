import pytest
try:
    from app.icons.ui.ui_icons import ui_icon
except ImportError as exc:
    pytest.skip(f"Qt runtime unavailable: {exc}", allow_module_level=True)

@pytest.mark.parametrize("name,variant",[("domain","neutral"),("block","neutral"),("assessment-area","neutral"),("analytics","neutral"),("success","semantic")])
def test_committed_ui_icon_loads(name,variant):
    assert not ui_icon(name,variant).isNull()

def test_missing_icon_fails_clearly():
    with pytest.raises(FileNotFoundError): ui_icon("not-a-real-icon")
