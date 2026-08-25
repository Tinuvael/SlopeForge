from __future__ import annotations

import sys
from pathlib import Path

import pytest

if sys.platform != "win32":
    pytest.skip(
        "Windows desktop Qt UX test; PostgreSQL Linux CI does not install Qt platform libraries",
        allow_module_level=True,
    )

from PySide6.QtWidgets import QApplication

from app.connection_settings import ConnectionProfile, ConnectionSettingsStore
from app.credential_store import MemoryCredentialStore
from application.services.database_upgrade import DatabaseCompatibility, DatabaseInspection
import ui.updater_window as updater_window


def _app():
    return QApplication.instance() or QApplication([])


def _store(tmp_path: Path) -> ConnectionSettingsStore:
    return ConnectionSettingsStore(
        tmp_path / "connections.json",
        credential_store=MemoryCredentialStore(),
        legacy_path=tmp_path / "connection.ini",
    )


def _window(monkeypatch, tmp_path: Path):
    _app()
    monkeypatch.setattr(updater_window, "backup_directory", lambda: tmp_path / "backups")
    monkeypatch.setattr(updater_window, "last_backup", lambda: None)
    monkeypatch.setattr(updater_window, "save_backup_directory", lambda path: Path(path))
    monkeypatch.setattr(updater_window, "save_last_backup", lambda path: Path(path))
    return updater_window.SlopeForgeUpdaterWindow(_store(tmp_path))


def test_updater_starts_safe_without_saved_server(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)

    assert window.windowTitle() == "SlopeForge Updater"
    assert window.profile_combo.count() == 0
    assert window.compatibility_value.text() == "No saved connection"
    assert window.test_button.text() == "Test connection"
    assert window.backup_button.text() == "Create backup"
    assert window.verify_button.text() == "Verify database"
    assert window.upgrade_button.text() == "Backup & upgrade"
    assert window.upgrade_button.isEnabled() is False

    window.deleteLater()


def test_upgrade_action_is_enabled_only_for_known_upgrade_required_state(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    window._service = object()

    window._apply_inspection(DatabaseInspection(
        current_heads=("1",),
        required_revision="2",
        compatibility=DatabaseCompatibility.UPGRADE_REQUIRED,
    ))
    assert window.upgrade_button.isEnabled() is True

    window._apply_inspection(DatabaseInspection(
        current_heads=("2",),
        required_revision="2",
        compatibility=DatabaseCompatibility.UP_TO_DATE,
    ))
    assert window.upgrade_button.isEnabled() is False

    window._apply_inspection(DatabaseInspection(
        current_heads=("legacy",),
        required_revision="2",
        compatibility=DatabaseCompatibility.UNKNOWN_OR_UNSUPPORTED,
    ))
    assert window.upgrade_button.isEnabled() is False

    window.deleteLater()


def test_updater_log_redacts_profile_password(monkeypatch, tmp_path: Path) -> None:
    window = _window(monkeypatch, tmp_path)
    window._profile = ConnectionProfile(
        profile_id="profile-1",
        name="Admin",
        host="localhost",
        database="slopeforge",
        username="postgres",
        password="s/ecret:word",
        mode="database_only",
    )

    rendered = window._safe_text(
        "database error password=s/ecret:word encoded=s%2Fecret%3Aword"
    )

    assert "s/ecret:word" not in rendered
    assert "s%2Fecret%3Aword" not in rendered
    assert rendered.count("<redacted>") == 2

    window.deleteLater()


def test_updater_entry_point_remains_english_only() -> None:
    source = Path("updater_main.py").read_text(encoding="utf-8")
    assert "install_selected_translator" not in source
    assert 'setApplicationName("SlopeForge Updater")' in source
