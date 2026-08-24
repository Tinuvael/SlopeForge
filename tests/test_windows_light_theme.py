from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_application_bootstrap_initializes_theme_before_translator() -> None:
    source = Path("main.py").read_text(encoding="utf-8")
    theme_call = source.index("initialize_application_theme(app)")
    compat_call = source.index("install_legacy_entity_page_theme_cleanup(app)")
    translator_call = source.index("install_selected_translator(app)")

    assert theme_call < compat_call < translator_call
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


def test_block_related_entity_list_constructs_and_survives_theme_switch() -> None:
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.application_theme import apply_application_theme
    from ui.pages.block_overview_widgets import BlockRelatedEntityList

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    apply_application_theme(app, "light")
    widget = BlockRelatedEntityList("Related assessment areas")
    assert widget.list is not None

    apply_application_theme(app, "dark")
    app.processEvents()
    apply_application_theme(app, "light")
    app.processEvents()

    assert widget.list is not None
    widget.close()


def test_linked_entity_rows_use_dark_surfaces_and_readable_text() -> None:
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.application_theme import apply_application_theme
    from ui.pages.block_overview_widgets import BlockRelatedEntityList

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    apply_application_theme(app, "dark")
    widget = BlockRelatedEntityList("Related events")
    widget.set_rows([
        SimpleNamespace(
            entity_id="BE-1",
            title="Contour blast",
            subtitle="630 m · revision R1",
            status_text="Completed",
            status_state="completed",
            stale=False,
            action_text="Go to ›",
        )
    ])
    holder = widget._row_card(widget.list.item(0))
    style = holder.styleSheet()
    assert "#1f3829" in style
    assert "#f2f5f8" in style
    assert "#c5ced8" in style
    widget.close()


def test_dark_numeric_spinbox_right_side_remains_clickable() -> None:
    QtCore = pytest.importorskip("PySide6.QtCore", exc_type=ImportError)
    QtTest = pytest.importorskip("PySide6.QtTest", exc_type=ImportError)
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.application_theme import apply_application_theme
    from ui.theme_compat import install_legacy_entity_page_theme_cleanup

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    install_legacy_entity_page_theme_cleanup(app)
    apply_application_theme(app, "dark")

    spin = QtWidgets.QDoubleSpinBox()
    spin.setRange(0, 10)
    spin.setSingleStep(1)
    spin.setValue(2)
    spin.resize(120, 28)
    spin.show()
    app.processEvents()

    QtTest.QTest.mouseClick(
        spin,
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(spin.width() - 6, 5),
    )
    assert spin.value() == pytest.approx(3.0)

    QtTest.QTest.mouseClick(
        spin,
        QtCore.Qt.MouseButton.LeftButton,
        pos=QtCore.QPoint(spin.width() - 6, spin.height() - 5),
    )
    assert spin.value() == pytest.approx(2.0)
    spin.close()


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
        "QGraphicsView#DashboardPlanView, QGraphicsView#BoreholeView",
        "QFrame#DocumentBatchBulk, QFrame#PhotoMetadataCard",
        "QToolButton#AttachmentPreviewTile",
        "QProgressBar#DashboardProgressBar",
        "QScrollBar:vertical",
    ):
        assert selector in DARK_STYLESHEET


def test_light_qss_covers_custom_surfaces_too() -> None:
    from ui.application_theme import LIGHT_STYLESHEET

    for selector in (
        "QGraphicsView#DashboardPlanView, QGraphicsView#BoreholeView",
        "QFrame#DocumentBatchBulk, QFrame#PhotoMetadataCard",
        "QToolButton#AttachmentPreviewTile",
        "QProgressBar#DashboardProgressBar",
        "QLabel#ConnectionEnvironmentWarning",
    ):
        assert selector in LIGHT_STYLESHEET


def test_manual_smoke_regressions_do_not_reintroduce_light_only_local_surfaces() -> None:
    attachment = Path("ui/dialogs/entity_attachment_dialog.py").read_text(encoding="utf-8")
    dashboard_plan = Path("ui/pages/dashboards/plan_overview.py").read_text(encoding="utf-8")
    borehole = Path("ui/widgets/borehole_charge_builder.py").read_text(encoding="utf-8")
    cards = Path("ui/widgets/design_system.py").read_text(encoding="utf-8")
    compat = Path("ui/theme_compat.py").read_text(encoding="utf-8")
    plan = Path("ui/pages/plan_geometry_widget.py").read_text(encoding="utf-8")
    assessment = Path("ui/pages/assessment_overview_widgets.py").read_text(encoding="utf-8")

    assert "ATTACHMENT_WORKSPACE_COLOR" not in attachment
    assert "QTableWidget{background:white" not in attachment
    assert "background:#f8fafc" not in attachment
    assert 'setObjectName("StandardTable")' in attachment
    assert 'setObjectName("DashboardPlanView")' in dashboard_plan
    assert "QGraphicsView{border:1px solid #e4e8ee" not in dashboard_plan
    assert 'setObjectName("BoreholeView")' in borehole
    assert "background: #FAFBFC" not in borehole
    assert "QPalette.ColorRole.AlternateBase" in borehole
    assert "setStyleSheet(desired)" not in cards
    assert "setStyleSheet(\"\")" not in cards
    assert 'widget.objectName() == "geomechanicsWorkspace"' in compat
    assert '"#38bdf8"' in plan
    assert "_QUADRANT_COLORS" in assessment
    assert "fill.setAlpha(alpha)" in assessment


def test_legacy_entity_page_light_qss_is_neutralized_until_page_cleanup() -> None:
    source = Path("ui/theme_compat.py").read_text(encoding="utf-8")
    for class_name in ("BlockPage", "ContourEventPage", "AssessmentAreaPage"):
        assert class_name in source
    assert 'widget.setStyleSheet("")' in source
    before_install = source.split("def install_legacy_entity_page_theme_cleanup", 1)[0]
    assert "from PySide6" not in before_install


def test_general_settings_exposes_system_light_dark_modes() -> None:
    source = Path("ui/settings_dialog.py").read_text(encoding="utf-8")
    assert 'self.theme_combo.addItem(tr("System"), "system")' in source
    assert 'self.theme_combo.addItem(tr("Light"), "light")' in source
    assert 'self.theme_combo.addItem(tr("Dark"), "dark")' in source
    assert "apply_application_theme(app, self.theme_combo.currentData(), persist=True)" in source
