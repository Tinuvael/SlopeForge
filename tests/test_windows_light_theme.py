from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_application_bootstrap_initializes_theme_before_translator() -> None:
    source = Path("main.py").read_text(encoding="utf-8")
    theme_call = source.index("initialize_application_theme(app)")
    translator_call = source.index("install_selected_translator(app)")

    assert theme_call < translator_call
    assert "enforce_light_application_appearance" not in source


def test_theme_preference_normalizes_and_persists(tmp_path) -> None:
    QtCore = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    from app.appearance import normalize_theme, save_theme, selected_theme

    store = QtCore.QSettings(str(tmp_path / "appearance.ini"), QtCore.QSettings.Format.IniFormat)
    assert normalize_theme("SYSTEM") == "system"
    assert normalize_theme("light") == "light"
    assert normalize_theme("dark") == "dark"
    assert normalize_theme("unexpected") == "system"

    save_theme("dark", store)
    assert selected_theme(store) == "dark"
    save_theme("light", store)
    assert selected_theme(store) == "light"


def test_light_and_dark_palettes_cover_native_qt_roles() -> None:
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    from ui.application_theme import DarkColor, build_palette
    from ui.theme import Color

    light = build_palette(dark=False)
    dark = build_palette(dark=True)

    assert light.color(QtGui.QPalette.ColorRole.Window).name() == Color.APP_BACKGROUND
    assert light.color(QtGui.QPalette.ColorRole.Base).name() == Color.SURFACE
    assert light.color(QtGui.QPalette.ColorRole.Text).name() == Color.TEXT_PRIMARY
    assert dark.color(QtGui.QPalette.ColorRole.Window).name() == DarkColor.APP_BACKGROUND
    assert dark.color(QtGui.QPalette.ColorRole.Base).name() == DarkColor.SURFACE
    assert dark.color(QtGui.QPalette.ColorRole.Text).name() == DarkColor.TEXT_PRIMARY
    assert dark.color(QtGui.QPalette.ColorGroup.Disabled, QtGui.QPalette.ColorRole.ButtonText).name() == DarkColor.DISABLED


def test_explicit_theme_switch_updates_existing_application_immediately() -> None:
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    QtGui = pytest.importorskip("PySide6.QtGui", exc_type=ImportError)
    from ui.application_theme import DarkColor, apply_application_theme
    from ui.theme import Color

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    apply_application_theme(app, "dark")
    assert app.property("slopeforgeTheme") == "dark"
    assert app.palette().color(QtGui.QPalette.ColorRole.Window).name() == DarkColor.APP_BACKGROUND
    assert DarkColor.APP_BACKGROUND in app.styleSheet()

    line_edit = QtWidgets.QLineEdit()
    menu = QtWidgets.QMenu()
    message_box = QtWidgets.QMessageBox()
    assert line_edit.palette().color(QtGui.QPalette.ColorRole.Base).name() == DarkColor.SURFACE
    assert menu.palette().color(QtGui.QPalette.ColorRole.WindowText).name() == DarkColor.TEXT_PRIMARY
    assert message_box.palette().color(QtGui.QPalette.ColorRole.Window).name() == DarkColor.APP_BACKGROUND

    apply_application_theme(app, "light")
    assert app.property("slopeforgeTheme") == "light"
    assert app.palette().color(QtGui.QPalette.ColorRole.Window).name() == Color.APP_BACKGROUND
    assert DarkColor.APP_BACKGROUND not in app.styleSheet()


def test_dark_qss_covers_high_risk_standard_and_engineering_surfaces() -> None:
    from ui.application_theme import DARK_STYLESHEET

    for selector in (
        "QMenu, QMenuBar",
        "QLineEdit, QTextEdit, QPlainTextEdit",
        "QComboBox QAbstractItemView",
        "QTableView, QTableWidget, QTreeView, QListView, QListWidget",
        "QListWidget#SettingsNavigation",
        "QWidget#EngineeringWorkspace QGroupBox#drillingGroupCard",
        "QTabWidget[entityTabs=\"true\"] QTabBar::tab",
        "QScrollBar:vertical",
    ):
        assert selector in DARK_STYLESHEET


def test_general_settings_exposes_system_light_dark_modes() -> None:
    source = Path("ui/settings_dialog.py").read_text(encoding="utf-8")
    assert 'self.theme_combo.addItem(tr("System"), "system")' in source
    assert 'self.theme_combo.addItem(tr("Light"), "light")' in source
    assert 'self.theme_combo.addItem(tr("Dark"), "dark")' in source
    assert "apply_application_theme(app, self.theme_combo.currentData(), persist=True)" in source
