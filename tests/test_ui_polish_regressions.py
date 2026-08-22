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


def test_engineering_combo_style_defines_chevron_without_touching_spinboxes():
    theme = source("ui/theme.py")
    assert "QWidget#EngineeringWorkspace QComboBox" in theme
    assert "QComboBox::drop-down" in theme
    assert "QComboBox::down-arrow" in theme
    assert "chevron-down.svg" in theme
    for selector in ("QSpinBox::up-button", "QSpinBox::down-button",
                     "QDoubleSpinBox::up-button", "QDoubleSpinBox::down-button"):
        assert selector not in theme


def test_settings_navigation_prioritizes_selected_over_hover():
    theme = source("ui/theme.py")
    assert "QListWidget#SettingsNavigation::item:selected:hover" in theme
    hover = theme.split("QListWidget#SettingsNavigation::item:hover:!selected", 1)[1].split("}", 1)[0]
    assert "background: #ffffff" not in hover


def test_entity_tabs_keep_sizing_contract_with_compact_padding():
    theme = source("ui/theme.py")
    assert "padding: 7px 8px; margin-right: 0;" in theme
    tabs = source("ui/pages/entity_tabs.py")
    assert "return QSize(hint.width(), 0)" in tabs


def test_block_and_contour_expose_one_technical_card_save_action():
    block = source("ui/pages/block_page.py")
    contour = source("ui/pages/contour_event_page.py")
    assert 'QPushButton(tr("Save"))' in block
    assert 'QPushButton(tr("Save"))' in contour
    for text in (block, contour):
        assert "TechnicalCardSaveButton(" not in text
        assert "Save & complete" not in text
        assert ".complete()" not in text
