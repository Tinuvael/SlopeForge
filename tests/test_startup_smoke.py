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


class FakeMessageBox:
    critical_calls = []
    @classmethod
    def critical(cls, *args):
        cls.critical_calls.append(args)


class FakeSplash:
    statuses = []
    def show(self):
        self.shown = True
    def show_status(self, status):
        type(self).statuses.append(status)
    def close_with_fade(self):
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
    def __init__(self, *args):
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

    fake_modules = {
        "app.platform": {"set_windows_app_user_model_id": lambda: None},
        "app.qt": {"apply_application_icon": lambda app: None},
        "app.splash": {"SlopeForgeSplash": FakeSplash},
        "database.startup": {
            "StartupError": RuntimeError,
            "initialize_database_runtime": lambda: (FakeSettings(Path("/tmp/startup-storage")), object(), lambda: None),
        },
        "infrastructure.services.auth_service": {"AuthService": FakeAuthService},
        "infrastructure.services.session_service": {"RememberTokenService": FakeRememberTokenService},
        "ui.auth_dialogs": {"FirstAdminDialog": FakeDialog, "LoginDialog": FakeDialog},
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
    spec = importlib.util.spec_from_file_location("tested_main_startup", Path("main.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
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
    monkeypatch.setattr(startup, "_expected_alembic_head", lambda: "0001_mvp_baseline")
    monkeypatch.setattr(startup, "_database_alembic_heads", lambda engine: ("0001_mvp_baseline",))
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


def test_main_uses_postgresql_dialog_for_startup_error(monkeypatch):
    module = load_main_with_fakes(monkeypatch)

    class SpecializedStartupError(RuntimeError):
        def __init__(self, message, server=None):
            super().__init__(message); self.server = server

    FakeMessageBox.critical_calls = []
    module.StartupError = SpecializedStartupError
    module.initialize_database_runtime = lambda: (_ for _ in ()).throw(
        SpecializedStartupError("Cannot connect to PostgreSQL. Check DATABASE_URL.",
                                "db.example:5432/slopeforge_test"))

    assert module.main() == 1
    assert len(FakeMessageBox.critical_calls) == 1
    _parent, title, message = FakeMessageBox.critical_calls[0]
    assert title == "PostgreSQL unavailable"
    assert "Cannot connect to PostgreSQL" in message
    assert "db.example:5432/slopeforge_test" in message
    assert "Unexpected startup error" not in message
