from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import configure_mappers


def test_sqlalchemy_mappers_configure_with_assessment_and_core_models():
    import database.assessment_models  # noqa: F401
    import database.models  # noqa: F401

    configure_mappers()


class FakeQApplication:
    instances = []

    def __init__(self, argv):
        self.argv = argv
        type(self).instances.append(self)

    def exec(self):
        return 0

    def setStyleSheet(self, stylesheet):
        self.stylesheet = stylesheet


class FakeButton:
    def __init__(self, text):
        self.text = text


class FakeMessageBox:
    class Icon:
        Warning = 1

    class ButtonRole:
        AcceptRole = 1
        ActionRole = 2
        RejectRole = 3

    critical_calls = []
    warning_calls = []
    boxes = []
    next_click_text = None

    def __init__(self):
        self.window_title = ""
        self.text = ""
        self.informative_text = ""
        self.buttons = []
        self.default_button = None
        self.escape_button = None
        self._clicked = None
        type(self).boxes.append(self)

    @classmethod
    def critical(cls, *args):
        cls.critical_calls.append(args)

    @classmethod
    def warning(cls, *args):
        cls.warning_calls.append(args)

    def setIcon(self, icon):
        self.icon = icon

    def setWindowTitle(self, title):
        self.window_title = title

    def setText(self, text):
        self.text = text

    def setInformativeText(self, text):
        self.informative_text = text

    def addButton(self, text, role):
        button = FakeButton(text)
        self.buttons.append((button, role))
        return button

    def setDefaultButton(self, button):
        self.default_button = button

    def setEscapeButton(self, button):
        self.escape_button = button

    def exec(self):
        requested = type(self).next_click_text
        if requested is not None:
            self._clicked = next(
                button for button, _role in self.buttons if button.text == requested
            )
        else:
            self._clicked = self.escape_button or self.default_button
        return 0

    def clickedButton(self):
        return self._clicked


class FakeSplash:
    statuses = []

    def show(self):
        self.shown = True

    def show_status(self, status):
        type(self).statuses.append(status)

    def close_with_fade(self):
        self.closed = True

    def close(self):
        self.closed = True


class FakeConnectionStore:
    pass


class FakeRuntimeController:
    instances = []
    start_result = True

    def __init__(self, app, connection_store, *, startup_error_handler, splash_factory):
        self.app = app
        self.connection_store = connection_store
        self.startup_error_handler = startup_error_handler
        self.splash_factory = splash_factory
        self.started = False
        type(self).instances.append(self)

    def start(self):
        self.started = True
        return type(self).start_result


def load_main_with_fakes(monkeypatch):
    qt = types.ModuleType("PySide6.QtWidgets")
    qt.QApplication = FakeQApplication
    qt.QMessageBox = FakeMessageBox
    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qt)

    fake_modules = {
        "app.connection_settings": {
            "ConnectionProfile": type("ConnectionProfile", (), {"from_settings": classmethod(lambda cls, settings: cls())}),
            "ConnectionSettingsStore": FakeConnectionStore,
        },
        "app.localization": {
            "tr": lambda value: value,
            "install_selected_translator": lambda app: None,
        },
        "app.platform": {"set_windows_app_user_model_id": lambda: None},
        "app.qt": {"apply_application_icon": lambda app: None},
        "app.runtime_controller": {"DesktopRuntimeController": FakeRuntimeController},
        "app.splash": {"SlopeForgeSplash": FakeSplash},
        "ui.application_theme": {"initialize_application_theme": lambda app: None},
        "ui.connection_dialog": {"ConnectionSetupDialog": type("ConnectionSetupDialog", (), {})},
        "ui.theme_compat": {"install_legacy_entity_page_theme_cleanup": lambda app: None},
    }
    for name, attrs in fake_modules.items():
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        monkeypatch.setitem(sys.modules, name, module)

    FakeRuntimeController.instances = []
    FakeRuntimeController.start_result = True
    FakeQApplication.instances = []
    FakeMessageBox.critical_calls = []
    FakeMessageBox.warning_calls = []
    FakeMessageBox.boxes = []
    FakeMessageBox.next_click_text = None
    spec = importlib.util.spec_from_file_location("tested_main_startup", Path("main.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_main_startup_smoke_delegates_runtime_lifecycle_to_controller(monkeypatch):
    module = load_main_with_fakes(monkeypatch)

    assert module.main() == 0

    assert len(FakeRuntimeController.instances) == 1
    controller = FakeRuntimeController.instances[0]
    assert controller.started is True
    assert isinstance(controller.connection_store, FakeConnectionStore)
    assert controller.startup_error_handler is module.show_startup_error
    assert controller.splash_factory is module._create_splash
    assert FakeMessageBox.critical_calls == []


def test_main_returns_without_event_loop_when_server_selection_is_cancelled(monkeypatch):
    module = load_main_with_fakes(monkeypatch)
    FakeRuntimeController.start_result = False

    assert module.main() == 0
    assert FakeRuntimeController.instances[-1].started is True


def test_startup_mapper_errors_are_reported_as_startup_error(monkeypatch):
    import database.startup as startup
    from database.settings import Settings

    settings = Settings("postgresql+psycopg://u:p@localhost/db", Path("/tmp/storage"))
    monkeypatch.setattr(startup.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(startup, "create_database_engine", lambda value: object())
    monkeypatch.setattr(startup, "check_connection", lambda engine: None)
    monkeypatch.setattr(startup, "_expected_alembic_head", lambda: "1")
    monkeypatch.setattr(startup, "_database_alembic_heads", lambda engine: ("1",))
    monkeypatch.setattr(
        startup,
        "configure_mappers",
        lambda: (_ for _ in ()).throw(SQLAlchemyError("mapper boom")),
    )

    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()

    assert "Could not connect to the database or verify tables." in str(caught.value)
    assert caught.value.__cause__.args == ("mapper boom",)


def test_connection_error_becomes_startup_error_with_safe_context(monkeypatch):
    import database.startup as startup
    from database.connection import DatabaseConnectionError
    from database.settings import Settings

    settings = Settings(
        "postgresql+psycopg://slopeforge:top-secret@db.example:5432/slopeforge_test",
        Path("/tmp/storage"),
    )
    guidance = (
        "Cannot connect to PostgreSQL. Check DATABASE_URL, network access, "
        "credentials, and that the target database exists. Run prepare-db."
    )
    monkeypatch.setattr(startup.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(startup, "create_database_engine", lambda value: object())
    monkeypatch.setattr(
        startup,
        "check_connection",
        lambda engine: (_ for _ in ()).throw(DatabaseConnectionError(guidance)),
    )

    with pytest.raises(startup.StartupError) as caught:
        startup.initialize_database_runtime()

    assert str(caught.value) == guidance
    assert caught.value.server == "slopeforge@db.example:5432/slopeforge_test"
    assert "top-secret" not in caught.value.server


def _specialized_error(message, *, reason, server="db.example:5432/slopeforge"):
    class SpecializedStartupError(RuntimeError):
        def __init__(self):
            super().__init__(message)
            self.reason = reason
            self.server = server

    return SpecializedStartupError()


def test_database_upgrade_dialog_hides_migration_internals(monkeypatch):
    module = load_main_with_fakes(monkeypatch)
    FakeMessageBox.next_click_text = "Close"
    error = _specialized_error(
        "internal revision 0003_drillhole_datasets python -m database.cli reset-dev-db",
        reason="database_upgrade_required",
    )

    assert module.show_startup_error(error) == module._CLOSE
    box = FakeMessageBox.boxes[-1]
    rendered = f"{box.window_title}\n{box.text}\n{box.informative_text}"
    assert "Database update required" in rendered
    assert "database administrator" in rendered
    assert "0003_drillhole_datasets" not in rendered
    assert "python -m" not in rendered
    assert "Alembic" not in rendered
    assert any(button.text == "Change connection" for button, _role in box.buttons)


def test_newer_database_dialog_links_to_latest_release(monkeypatch):
    module = load_main_with_fakes(monkeypatch)
    FakeMessageBox.next_click_text = "Get latest release"
    opened = []
    monkeypatch.setattr(module.webbrowser, "open", opened.append)
    error = _specialized_error(
        "internal unknown revision 2",
        reason="application_upgrade_required",
    )

    assert module.show_startup_error(error) == module._CLOSE
    box = FakeMessageBox.boxes[-1]
    assert "requires a newer version of SlopeForge" in box.text
    assert opened == [module.APP_RELEASES_URL]
    assert any(button.text == "Change connection" for button, _role in box.buttons)