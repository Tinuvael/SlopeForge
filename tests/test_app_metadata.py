from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from app import config
from app.resources import resource_path


@pytest.fixture(scope="module")
def qt_app():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets", reason="Qt libraries are not available in this environment", exc_type=ImportError)
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_app_metadata_is_present_and_version_is_semver() -> None:
    assert config.APP_NAME
    assert config.APP_VERSION
    assert config.APP_AUTHOR
    assert re.fullmatch(r"\d+\.\d+\.\d+", config.APP_VERSION)


def test_resource_path_is_safe_for_existing_and_missing_assets() -> None:
    icon_path = resource_path(config.APP_ICON_PATH)
    assert icon_path is not None
    assert icon_path.exists()
    assert resource_path("does/not/exist.png") is None


def test_runtime_ui_does_not_hardcode_current_version() -> None:
    current_version = config.APP_VERSION
    for path in [Path("app/splash.py"), Path("ui/about_dialog.py")]:
        assert current_version not in path.read_text()


def test_splash_and_about_can_be_created_offscreen(qt_app) -> None:
    from app.qt import apply_application_icon
    from app.splash import SlopeForgeSplash
    from ui.about_dialog import AboutDialog

    apply_application_icon(qt_app)
    splash = SlopeForgeSplash()
    splash.show_status("Тест")
    about = AboutDialog()
    assert splash.pixmap().isNull() is False
    assert config.APP_NAME in about.windowTitle()
    splash.close()
    about.close()
