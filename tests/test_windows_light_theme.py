from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest


def test_application_bootstrap_pins_light_appearance_before_qss() -> None:
    source = Path("main.py").read_text(encoding="utf-8")
    palette_call = source.index("enforce_light_application_appearance(app)")
    qss_call = source.index("apply_theme(app)")
    translator_call = source.index("install_selected_translator(app)")

    assert palette_call < qss_call < translator_call


def test_windows_palette_is_light_for_standard_unstyled_qt_controls() -> None:
    if sys.platform != "win32":
        pytest.skip("Windows appearance regression is exercised by Windows CI")

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QLineEdit,
        QMenu,
        QMessageBox,
        QTableWidget,
    )

    from ui.application_theme import enforce_light_application_appearance
    from ui.theme import Color, apply_theme

    app = QApplication.instance() or QApplication([])
    enforce_light_application_appearance(app)
    apply_theme(app)

    palette = app.palette()
    assert palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Window).name() == Color.APP_BACKGROUND
    assert palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Base).name() == Color.SURFACE
    assert palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Text).name() == Color.TEXT_PRIMARY
    assert palette.color(QPalette.ColorGroup.Active, QPalette.ColorRole.Highlight).name() == Color.SELECTED
    assert palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Base).name() == Color.SURFACE_SUBTLE
    assert palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText).name() == Color.DISABLED

    if hasattr(app.styleHints(), "colorScheme"):
        assert app.styleHints().colorScheme() == Qt.ColorScheme.Light

    line_edit = QLineEdit()
    combo = QComboBox()
    table = QTableWidget()
    menu = QMenu()
    message_box = QMessageBox()

    assert line_edit.palette().color(QPalette.ColorRole.Base).name() == Color.SURFACE
    assert combo.palette().color(QPalette.ColorRole.ButtonText).name() == Color.TEXT_PRIMARY
    assert table.palette().color(QPalette.ColorRole.Base).name() == Color.SURFACE
    assert menu.palette().color(QPalette.ColorRole.WindowText).name() == Color.TEXT_PRIMARY
    assert message_box.palette().color(QPalette.ColorRole.Window).name() == Color.APP_BACKGROUND
