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

from app.connection_settings import DATABASE_ONLY, FULL_STORAGE, ConnectionProfile, ConnectionSettingsStore
from app.credential_store import MemoryCredentialStore
from ui.auth_dialogs import FirstAdminDialog, LoginDialog
from ui.connection_dialog import ConnectionForm, ServerSelectionDialog


class FakeAuthService:
    pass


def _app():
    return QApplication.instance() or QApplication([])


def _store(tmp_path):
    return ConnectionSettingsStore(
        tmp_path / "connections.json",
        credential_store=MemoryCredentialStore(),
        legacy_path=tmp_path / "connection.ini",
    )


def test_login_identifies_selected_server_and_uses_primary_sign_in_action():
    _app()
    dialog = LoginDialog(
        FakeAuthService(),
        server_name="Birkachan — Production",
        server_location="db01.example:5432 / slopeforge",
        database_only=True,
    )

    assert dialog.server_name_label.text() == "Birkachan — Production"
    assert dialog.server_location_label.text() == "db01.example:5432 / slopeforge"
    assert dialog.server_mode_label.text() == "Database only"
    assert dialog.login_button.property("role") == "primary"
    assert dialog.login_button.isDefault() is True
    assert dialog.cancel_button.property("role") == "secondary"

    dialog.deleteLater()


def test_first_admin_identifies_selected_server():
    _app()
    dialog = FirstAdminDialog(
        FakeAuthService(),
        server_name="Site A — Production",
        server_location="site-a.example:5432 / slopeforge",
        database_only=False,
    )

    assert dialog.server_name_label.text() == "Site A — Production"
    assert dialog.server_location_label.text() == "site-a.example:5432 / slopeforge"
    assert dialog.server_mode_label is None
    assert dialog.create_button.property("role") == "primary"
    assert dialog.cancel_button.property("role") == "secondary"

    dialog.deleteLater()


def test_connection_form_uses_storage_capability_labels_and_progressive_disclosure(tmp_path):
    _app()
    database_only = ConnectionForm(
        ConnectionProfile(
            name="Remote viewer",
            host="remote.example",
            database="slopeforge",
            username="viewer",
            mode=DATABASE_ONLY,
        )
    )
    assert database_only.mode.currentText() == "Database only"
    assert database_only.storage_card.isHidden() is True
    assert database_only.database_only_hint.isHidden() is False
    assert database_only.database_only_hint.property("statusRole") == "info"

    full = ConnectionForm(
        ConnectionProfile(
            name="Production",
            host="db.example",
            database="slopeforge",
            username="engineer",
            mode=FULL_STORAGE,
            storage_root=tmp_path,
        )
    )
    assert full.mode.currentText() == "Database + shared files"
    assert full.storage_card.isHidden() is False
    assert full.database_only_hint.isHidden() is True

    database_only.deleteLater()
    full.deleteLater()


def test_server_selector_rows_expose_endpoint_mode_and_auto_connect_intent(tmp_path):
    _app()
    store = _store(tmp_path)
    saved = store.upsert(
        ConnectionProfile(
            name="Management / Site A",
            host="site-a.example",
            database="slopeforge",
            username="viewer",
            mode=DATABASE_ONLY,
        ),
        password="secret",
        force_new=True,
    )
    dialog = ServerSelectionDialog(store, current_profile_id=saved.profile_id)

    text = dialog.list.item(0).text()
    assert "Management / Site A" in text
    assert "Current" in text
    assert "site-a.example:5432 / slopeforge" in text
    assert "Database only" in text
    assert dialog.skip_selection.text() == "Connect to this server automatically at startup"
    assert dialog.connect_button.property("role") == "primary"
    assert dialog.remove_button.property("role") == "danger"

    dialog.deleteLater()


def test_destructive_saved_session_action_requires_confirmation_contract():
    source = Path("ui/settings_dialog.py").read_text(encoding="utf-8")
    assert "if not _confirm_end_saved_sessions(self, server_name):" in source
    assert "QMessageBox.ButtonRole.DestructiveRole" in source
    assert "You will need to sign in again on remembered devices for this server." in source


def test_runtime_passes_selected_server_context_into_authentication_dialogs():
    source = Path("app/runtime_controller.py").read_text(encoding="utf-8")
    assert '"server_name": target.profile.display_name' in source
    assert '"server_location": self._profile_location(target.profile)' in source
    assert "LoginDialog(auth_service, **dialog_kwargs)" in source
    assert "FirstAdminDialog(auth_service, **dialog_kwargs)" in source
