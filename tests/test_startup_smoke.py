from __future__ import annotations

import importlib.util
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import configure_mappers


def test_sqlalchemy_mappers_configure_with_assessment_and_core_models():
    import database.assessment_models  # noqa: F401
    import database.models  # noqa: F401

    configure_mappers()


@dataclass(frozen=True)
class FakeSettings:
    storage_root: Path


class FakeQApplication:
    def __init__(self, argv):
        self.argv = argv
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
    def isVisible(self):
        return False


class FakeAuthService:
    has_users_value = True
    def __init__(self, session_factory):
        self.session_factory = session_factory
    def has_users(self):
        return self.has_users_value


class FakeRemembered:
    def __init__(self, user):
        self.current_user = user


class FakeRememberTokenService:
    def __init__(self, session_factory):
        self.session_factory = session_factory
    def authenticate_local(self):
        return FakeRemembered(types.SimpleNamespace(id=1, username="admin"))
    def create_for_user(self, *args):
        raise AssertionError("remember token should not be created in remembered-session path")


class FakeDialog:
    class DialogCode:
        Accepted = 1
    current_user = None
    remember_requested = False
    def __init__(self, *args, **kwargs):
        raise AssertionError("dialog should not open for remembered-session path")


class FakeMainWindow:
    constructed_contexts = []
    def __init__(self, context):
        type(self).constructed_contexts.append(context)
    def showMaximized(self):
        self.maximized = True


def load_main_with_fakes(monkeypatch):
    qt = types.ModuleType("PySide6.QtWidgets")
    qt.QApplication = FakeQApplication
    qt.QMessageBox = FakeMessageBox
    monkeypatch.setitem(sys.modules, "PySide6", types.ModuleType("PySide6"))
    monkeypatch.setitem(sys.modules, "PySide6.QtWidgets", qt)

    runtime_settings = FakeSettings(Path("/tmp/startup-storage"))
    fake_modules = {
        "app.localization": {"tr": lambda value: value,
                             "install_selected_translator": lambda app: None},
        "app.platform": {"set_windows_app_user_model_id": lambda: None},
        "app.qt": {"apply_application_icon": lambda app: None},
        "app.splash": {"SlopeForgeSplash": FakeSplash},
        "database.startup": {
            "StartupError": RuntimeError,
            "initialize_database_runtime": lambda _settings=None: (
                runtime_settings,
                object(),
                lambda: None,
            ),
        },
        "infrastructure.services.auth_service": {"AuthService": FakeAuthService},
        "infrastructure.services.session_service": {"RememberTokenService": FakeRememberTokenService},
        "ui.auth_dialogs": {"FirstAdminDialog": FakeDialog, "LoginDialog": FakeDialog},
        "ui.connection_dialog": {"ConnectionSetupDialog": FakeDialog},
        "ui.main_window": {"MainWindow": FakeMainWindow},
    }
    from app.context import AppContext
    fake_modules["app.context"] = {"AppContext": AppContext}
    for name, attrs in fake_modules.items():
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        monkeypatch.setitem(sys.modules, name, module)

    FakeMainWindow.constructed_contexts = []
    FakeMessageBox.critical_calls = []
    FakeMessageBox.warning_calls = []
    FakeMessageBox.boxes = []
    FakeMessageBox.next_click_text = None
    spec = importlib.util.spec_from_file_location("tested_main_startup", Path("main.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Startup smoke tests exercise the main() control flow, not the machine's
    # real .env or persisted connection profile. Keep this deterministic on
    # developer workstations with either source configured.
    module.resolve_runtime_settings = lambda _store: (runtime_settings, "test")
    return module


def test_main_startup_smoke_constructs_main_window_with_runtime_context(monkeypatch):
    module = load_main_with_fakes(monkeypatch)

    assert module.main() == 0

    assert len(FakeMainWindow.constructed_contexts) == 1
    context = FakeMainWindow.constructed_contexts[0]
    assert context.session_factory() is None
    assert context.current_user.username == "admin"
    assert context.storage_root == Path("/tmp/startup-storage")
    assert FakeMessageBox.critical_calls == []


def test_startup_mapper_errors_are_reported_as_startup_error(monkeypatch):
    import database.startup as startup
    from database.settings import Settings

    settings = Settings("postgresql+psycopg://u:p@localhost/db", Path("/tmp/storage"))
    monkeypatch.setattr(startup.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(startup, "create_database_engine", lambda value: object())
    monkeypatch.setattr(startup, "check_connection", lambda engine: None)
    monkeypatch.setattr(startup, "_expected_alembic_head", lambda: "1")
    monkeypatch.setattr(startup, "_database_alembic_heads", lambda engine: ("1",))
    monkeypatch.setattr(startup, "configure_mappers", lambda: (_ for _ in ()).throw(SQLAlchemyError("mapper boom")))

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
    guidance = ("Cannot connect to PostgreSQL. Check DATABASE_URL, network access, "
                "credentials, and that the target database exists. Run prepare-db.")
    monkeypatch.setattr(startup.Settings, "from_env", lambda: settings)
    monkeypatch.setattr(startup, "create_database_engine", lambda value: object())
    monkeypatch.setattr(startup, "check_connection", lambda engine: (_ for _ in ()).throw(
        DatabaseConnectionError(guidance)))

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


def test_startup_version_mismatch_can_switch_connection_and_retry(monkeypatch):
    module = load_main_with_fakes(monkeypatch)
    replacement = FakeSettings(Path("/tmp/replacement-storage"))
    attempts = []

    def initialize(settings):
        attempts.append(settings)
        if len(attempts) == 1:
            raise _specialized_error(
                "old database",
                reason="database_upgrade_required",
            )
        return replacement, object(), lambda: None

    module.initialize_database_runtime = initialize
    module._connection_setup = lambda _store, _current=None: replacement
    FakeMessageBox.next_click_text = "Change connection"

    assert module.main() == 0
    assert len(attempts) == 2
    assert attempts[1] is replacement
    assert FakeMainWindow.constructed_contexts[-1].storage_root == Path("/tmp/replacement-storage")
