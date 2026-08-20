from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def source(path):
    return (ROOT / path).read_text(encoding="utf-8")


def test_users_table_uses_stable_header_policy_without_refresh_resizing():
    users = source("ui/user_admin_page.py")
    refresh = users.split("    def refresh(self):", 1)[1].split("    def selected_user", 1)[0]
    assert "setSectionResizeMode" in users
    assert "QHeaderView.ResizeMode.Stretch" in users
    assert "QHeaderView.ResizeMode.Interactive" in users
    assert "resizeColumnsToContents" not in refresh


def test_engineering_combo_style_preserves_native_dropdown_subcontrol():
    theme = source("ui/theme.py")
    assert "QWidget#EngineeringWorkspace QComboBox" in theme
    assert "QComboBox::drop-down" not in theme


def test_entity_tabs_keep_sizing_contract_with_compact_padding():
    theme = source("ui/theme.py")
    assert "padding: 7px 8px; margin-right: 0;" in theme
    tabs = source("ui/pages/entity_tabs.py")
    assert "return QSize(hint.width(), 0)" in tabs


def test_block_and_contour_share_the_split_save_control():
    block = source("ui/pages/block_page.py")
    contour = source("ui/pages/contour_event_page.py")
    assert "TechnicalCardSaveButton(" in block
    assert "TechnicalCardSaveButton(" in contour
    assert 'QPushButton(tr("Save draft"))' not in block
    assert 'QPushButton(tr("Save draft"))' not in contour
