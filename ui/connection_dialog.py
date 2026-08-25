from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.connection_settings import (
    DATABASE_ONLY,
    FULL_STORAGE,
    ConnectionProfile,
    ConnectionSettingsError,
    ConnectionSettingsStore,
    effective_profile,
    validate_storage_root,
)
from app.icons.ui.ui_icons import ui_icon
from app.localization import tr
from app.qt import apply_window_icon
from database.connection import DatabaseConnectionError, check_connection, create_database_engine
from database.settings import ConfigurationError, Settings


def _confirm_remove(parent) -> bool:
    box = QMessageBox(
        QMessageBox.Icon.Warning,
        tr("Remove connection"),
        tr("Remove this saved connection from this computer?"),
        parent=parent,
    )
    remove = box.addButton(tr("Remove"), QMessageBox.ButtonRole.DestructiveRole)
    cancel = box.addButton(tr("Cancel"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel)
    box.setEscapeButton(cancel)
    box.exec()
    return box.clickedButton() is remove


class ConnectionForm(QWidget):
    def __init__(self, profile: ConnectionProfile | None = None, parent=None):
        super().__init__(parent)
        self._original = (profile or ConnectionProfile()).normalized()
        profile = self._original
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        identity_card = QFrame()
        identity_card.setObjectName("ConnectionCard")
        identity_form = QFormLayout(identity_card)
        identity_form.setContentsMargins(14, 12, 14, 12)
        identity_form.setHorizontalSpacing(12)
        identity_form.setVerticalSpacing(8)
        self.name = QLineEdit(profile.name)
        self.name.setPlaceholderText(tr("e.g. Birkachan production"))
        self.mode = QComboBox()
        self.mode.addItem(tr("Full"), FULL_STORAGE)
        self.mode.addItem(tr("Database only"), DATABASE_ONLY)
        self.mode.setCurrentIndex(max(0, self.mode.findData(profile.mode)))
        identity_form.addRow(tr("Connection name"), self.name)
        identity_form.addRow(tr("Mode"), self.mode)
        root.addWidget(identity_card)

        database_card = QFrame()
        database_card.setObjectName("ConnectionCard")
        database_layout = QVBoxLayout(database_card)
        database_layout.setContentsMargins(14, 12, 14, 12)
        database_layout.setSpacing(8)
        database_title = QLabel(tr("PostgreSQL server"))
        database_title.setObjectName("CardTitle")
        database_layout.addWidget(database_title)
        database_form = QFormLayout()
        database_form.setLabelAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        database_form.setHorizontalSpacing(12)
        database_form.setVerticalSpacing(8)
        self.host = QLineEdit(profile.host)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(profile.port or 5432))
        self.database = QLineEdit(profile.database)
        self.username = QLineEdit(profile.username)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText(
            tr("Leave blank to keep the saved password")
            if profile.profile_id
            else tr("PostgreSQL password")
        )
        database_form.addRow(tr("Server / Host"), self.host)
        database_form.addRow(tr("Port"), self.port)
        database_form.addRow(tr("Database"), self.database)
        database_form.addRow(tr("User"), self.username)
        database_form.addRow(tr("Password"), self.password)
        database_layout.addLayout(database_form)
        root.addWidget(database_card)

        self.storage_card = QFrame()
        self.storage_card.setObjectName("ConnectionCard")
        storage_layout = QVBoxLayout(self.storage_card)
        storage_layout.setContentsMargins(14, 12, 14, 12)
        storage_layout.setSpacing(8)
        storage_title = QLabel(tr("File storage"))
        storage_title.setObjectName("CardTitle")
        storage_layout.addWidget(storage_title)
        storage_hint = QLabel(tr("Use a folder that all SlopeForge users can access."))
        storage_hint.setObjectName("MutedText")
        storage_hint.setWordWrap(True)
        storage_layout.addWidget(storage_hint)
        storage_row = QHBoxLayout()
        storage_row.setSpacing(8)
        self.storage = QLineEdit(str(profile.storage_root or ""))
        self.browse = QPushButton(tr("Browse…"))
        self.browse.setIcon(ui_icon("folder-open"))
        self.browse.clicked.connect(self._browse_storage)
        storage_row.addWidget(self.storage, 1)
        storage_row.addWidget(self.browse)
        storage_layout.addLayout(storage_row)
        root.addWidget(self.storage_card)

        self.database_only_hint = QLabel(
            tr("Database only reads database-backed SlopeForge data without opening shared files, photos or source geometry.")
        )
        self.database_only_hint.setObjectName("MutedText")
        self.database_only_hint.setWordWrap(True)
        root.addWidget(self.database_only_hint)

        self.status = QLabel("")
        self.status.setObjectName("ConnectionStatus")
        self.status.setProperty("statusState", "info")
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(22)
        root.addWidget(self.status)
        self.mode.currentIndexChanged.connect(self._sync_mode)
        self._sync_mode()

    def _sync_mode(self) -> None:
        full = self.mode.currentData() == FULL_STORAGE
        self.storage_card.setEnabled(full)
        self.database_only_hint.setVisible(not full)

    def _browse_storage(self) -> None:
        current = self.storage.text().strip()
        selected = QFileDialog.getExistingDirectory(
            self,
            tr("Select file storage folder"),
            current if current else str(Path.home()),
        )
        if selected:
            self.storage.setText(selected)

    def profile(self) -> ConnectionProfile:
        return ConnectionProfile(
            profile_id=self._original.profile_id,
            name=self.name.text(),
            host=self.host.text(),
            port=self.port.value(),
            database=self.database.text(),
            username=self.username.text(),
            password=self.password.text(),
            mode=str(self.mode.currentData()),
            storage_root=self.storage.text().strip(),
            last_used_at=self._original.last_used_at,
        )

    def set_status(self, text: str, *, error=False, success=False) -> None:
        self.status.setText(text)
        state = "error" if error else "success" if success else "info"
        self.status.setProperty("statusState", state)
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def validate_and_test(
        self, *, saved_password: str = ""
    ) -> tuple[ConnectionProfile, Settings] | None:
        profile = self.profile()
        if not profile.password and saved_password:
            profile = replace(profile, password=saved_password)
        engine = None
        self.set_status(
            tr("Testing PostgreSQL and file storage…")
            if profile.mode == FULL_STORAGE
            else tr("Testing PostgreSQL…")
        )
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            profile.validate_required()
            settings = profile.to_settings()
            engine = create_database_engine(settings)
            check_connection(engine)
            if profile.mode == FULL_STORAGE:
                validate_storage_root(profile.storage_root)
        except (
            ConnectionSettingsError,
            ConfigurationError,
            DatabaseConnectionError,
            OSError,
            ValueError,
        ) as exc:
            self.set_status(f"{tr('Connection test failed')}: {exc}", error=True)
            return None
        finally:
            if engine is not None:
                engine.dispose()
            QApplication.restoreOverrideCursor()
        self.set_status(
            tr("Connection and file storage are available.")
            if profile.mode == FULL_STORAGE
            else tr("Database connection is available."),
            success=True,
        )
        return profile.normalized(), settings


class ConnectionProfileDialog(QDialog):
    def __init__(
        self,
        store: ConnectionSettingsStore,
        profile: ConnectionProfile | None = None,
        parent=None,
    ):
        super().__init__(parent)
        apply_window_icon(self)
        self.store = store
        self.original = profile
        self.saved_profile: ConnectionProfile | None = None
        self.runtime_settings: Settings | None = None
        self.setWindowTitle(tr("Edit connection") if profile else tr("Add connection"))
        self.resize(620, 610)
        self.setMinimumWidth(560)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        self.form = ConnectionForm(profile)
        root.addWidget(self.form, 1)
        buttons = QHBoxLayout()
        test = QPushButton(tr("Test connection"))
        test.setIcon(ui_icon("analytics", "blue"))
        test.clicked.connect(self._test)
        cancel = QPushButton(tr("Cancel"))
        cancel.clicked.connect(self.reject)
        save = QPushButton(tr("Save"))
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(test)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _saved_password(self) -> str:
        if self.original is None or not self.original.profile_id:
            return ""
        try:
            return self.store.runtime_profile(self.original.profile_id).password
        except (ConnectionSettingsError, KeyError):
            return ""

    def _test(self) -> None:
        self.form.validate_and_test(saved_password=self._saved_password())

    def _save(self) -> None:
        result = self.form.validate_and_test(saved_password=self._saved_password())
        if result is None:
            return
        profile, settings = result
        entered_password = self.form.password.text()
        try:
            saved = self.store.upsert(
                profile,
                password=entered_password if entered_password else None,
                force_new=self.original is None,
            )
        except ConnectionSettingsError as exc:
            self.form.set_status(str(exc), error=True)
            return
        self.saved_profile = saved
        self.runtime_settings = settings
        self.accept()


class ConnectionSetupDialog(ConnectionProfileDialog):
    """Compatibility first-run/recovery wrapper around the profile editor."""

    def __init__(
        self,
        store: ConnectionSettingsStore | None = None,
        parent=None,
        *,
        initial_profile: ConnectionProfile | None = None,
    ):
        store = store or ConnectionSettingsStore()
        super().__init__(store, initial_profile, parent)
        self.setWindowTitle(tr("SlopeForge connection setup"))


class ServerSelectionDialog(QDialog):
    """Compact startup/server-switch selector. User authentication happens afterwards."""

    def __init__(
        self,
        store: ConnectionSettingsStore | None = None,
        parent=None,
        *,
        title: str = "Select server",
        current_profile_id: str | None = None,
    ):
        super().__init__(parent)
        apply_window_icon(self)
        self.store = store or ConnectionSettingsStore()
        self.current_profile_id = current_profile_id
        self.selected_profile: ConnectionProfile | None = None
        self.runtime_settings: Settings | None = None
        self.auto_connect_requested = False
        self.setWindowTitle(tr(title))
        self.setModal(True)
        self.resize(650, 430)
        self.setMinimumWidth(600)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(10)
        heading = QLabel(tr(title))
        heading.setObjectName("EntityTitle")
        root.addWidget(heading)
        helper = QLabel(tr("Choose the PostgreSQL server used for this SlopeForge session."))
        helper.setObjectName("MutedText")
        helper.setWordWrap(True)
        root.addWidget(helper)

        body = QHBoxLayout()
        body.setSpacing(12)
        self.list = QListWidget()
        self.list.setObjectName("ConnectionProfileList")
        self.list.setMinimumWidth(260)
        self.list.currentItemChanged.connect(self._selection_changed)
        self.list.itemDoubleClicked.connect(lambda _item: self._connect())
        body.addWidget(self.list, 1)
        details = QFrame()
        details.setObjectName("ConnectionCard")
        details_layout = QVBoxLayout(details)
        details_layout.setContentsMargins(14, 12, 14, 12)
        self.profile_name = QLabel(tr("No connection selected"))
        self.profile_name.setObjectName("CardTitle")
        self.profile_details = QLabel("")
        self.profile_details.setObjectName("MutedText")
        self.profile_details.setWordWrap(True)
        self.mode_label = QLabel("")
        self.mode_label.setObjectName("MutedText")
        details_layout.addWidget(self.profile_name)
        details_layout.addWidget(self.profile_details)
        details_layout.addWidget(self.mode_label)
        details_layout.addStretch()
        body.addWidget(details, 1)
        root.addLayout(body, 1)

        manage = QHBoxLayout()
        self.add_button = QPushButton(tr("Add"))
        self.edit_button = QPushButton(tr("Edit"))
        self.remove_button = QPushButton(tr("Remove"))
        self.test_button = QPushButton(tr("Test"))
        self.add_button.clicked.connect(self._add)
        self.edit_button.clicked.connect(self._edit)
        self.remove_button.clicked.connect(self._remove)
        self.test_button.clicked.connect(self._test)
        for button in (self.add_button, self.edit_button, self.remove_button, self.test_button):
            manage.addWidget(button)
        manage.addStretch()
        root.addLayout(manage)

        self.skip_selection = QCheckBox(tr("Skip server selection on startup"))
        root.addWidget(self.skip_selection)
        actions = QHBoxLayout()
        cancel = QPushButton(tr("Cancel"))
        cancel.clicked.connect(self.reject)
        self.connect_button = QPushButton(tr("Connect"))
        self.connect_button.setDefault(True)
        self.connect_button.clicked.connect(self._connect)
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(self.connect_button)
        root.addLayout(actions)
        self._reload()

    def _reload(self, select_id: str | None = None) -> None:
        selected = select_id or self.current_profile_id or self.store.last_profile_id()
        self.list.clear()
        for profile in self.store.list_profiles():
            item = QListWidgetItem(profile.display_name)
            item.setData(Qt.ItemDataRole.UserRole, profile.profile_id)
            item.setToolTip(f"{profile.username}@{profile.host}:{profile.port}/{profile.database}")
            self.list.addItem(item)
            if selected and profile.profile_id == selected:
                self.list.setCurrentItem(item)
        if self.list.currentRow() < 0 and self.list.count():
            self.list.setCurrentRow(0)
        self._selection_changed(self.list.currentItem(), None)

    def _current_profile(self) -> ConnectionProfile | None:
        item = self.list.currentItem()
        if item is None:
            return None
        try:
            return self.store.profile(str(item.data(Qt.ItemDataRole.UserRole)))
        except (ConnectionSettingsError, KeyError):
            return None

    def _selection_changed(self, _current, _previous) -> None:
        profile = self._current_profile()
        enabled = profile is not None
        for button in (self.edit_button, self.remove_button, self.test_button, self.connect_button):
            button.setEnabled(enabled)
        if profile is None:
            self.profile_name.setText(tr("No connection selected"))
            self.profile_details.clear()
            self.mode_label.clear()
            self.skip_selection.setChecked(False)
            return
        self.profile_name.setText(profile.display_name)
        self.profile_details.setText(
            f"{profile.username}@{profile.host}:{profile.port}/{profile.database}"
        )
        self.mode_label.setText(
            tr("Full — database and shared files")
            if profile.mode == FULL_STORAGE
            else tr("Database only — shared files unavailable")
        )
        self.skip_selection.setChecked(
            self.store.auto_connect_profile_id() == profile.profile_id
        )

    def _add(self) -> None:
        dialog = ConnectionProfileDialog(self.store, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_profile:
            self._reload(dialog.saved_profile.profile_id)

    def _edit(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        dialog = ConnectionProfileDialog(self.store, profile, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_profile:
            self._reload(dialog.saved_profile.profile_id)

    def _remove(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        if profile.profile_id == self.current_profile_id:
            QMessageBox.information(
                self,
                tr("Connection in use"),
                tr("Switch to another server before removing the current connection."),
            )
            return
        if not _confirm_remove(self):
            return
        try:
            self.store.remove(profile.profile_id)
        except ConnectionSettingsError as exc:
            QMessageBox.warning(self, tr("Connection settings"), str(exc))
            return
        self._reload()

    def _test(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        try:
            runtime = self.store.runtime_profile(profile.profile_id)
        except ConnectionSettingsError as exc:
            QMessageBox.warning(self, tr("Connection settings"), str(exc))
            return
        probe = ConnectionForm(runtime)
        result = probe.validate_and_test(saved_password=runtime.password)
        QMessageBox.information(
            self,
            tr("Connection test") if result else tr("Connection test failed"),
            probe.status.text(),
        )
        probe.deleteLater()

    def _connect(self) -> None:
        profile = self._current_profile()
        if profile is None:
            return
        try:
            runtime = self.store.runtime_profile(profile.profile_id)
            self.runtime_settings = runtime.to_settings()
        except (ConnectionSettingsError, ConfigurationError, KeyError) as exc:
            QMessageBox.warning(self, tr("Connection settings"), str(exc))
            return
        self.auto_connect_requested = self.skip_selection.isChecked()
        self.selected_profile = runtime
        self.accept()


class ConnectionSettingsPage(QWidget):
    """Manage saved profiles; the current DB runtime is switched by runtime_control."""

    connection_changed = Signal()

    def __init__(
        self,
        parent=None,
        store: ConnectionSettingsStore | None = None,
        context=None,
    ):
        super().__init__(parent)
        self.store = store or ConnectionSettingsStore()
        self.context = context
        _profile, source = effective_profile(self.store)
        self.environment_pinned = source == "environment"
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(10)
        root.addWidget(QLabel(f"<b>{tr('Connections')}</b>"))
        description = QLabel(
            tr("Manage PostgreSQL servers saved on this computer. PostgreSQL passwords are stored separately from profile metadata.")
        )
        description.setWordWrap(True)
        description.setObjectName("MutedText")
        root.addWidget(description)
        if self.environment_pinned:
            override = QLabel(
                tr("This installation is currently pinned by DATABASE_URL. Saved profiles can be managed, but runtime switching is disabled until the environment override is removed.")
            )
            override.setObjectName("ConnectionEnvironmentWarning")
            override.setWordWrap(True)
            root.addWidget(override)

        self.list = QListWidget()
        self.list.setObjectName("ConnectionProfileList")
        self.list.currentItemChanged.connect(self._sync_actions)
        root.addWidget(self.list, 1)
        self.details = QLabel("")
        self.details.setObjectName("MutedText")
        self.details.setWordWrap(True)
        root.addWidget(self.details)
        self.startup_checkbox = QCheckBox(
            tr("Skip server selection on startup for this connection")
        )
        self.startup_checkbox.toggled.connect(self._startup_preference_changed)
        root.addWidget(self.startup_checkbox)

        actions = QHBoxLayout()
        self.add_button = QPushButton(tr("Add"))
        self.edit_button = QPushButton(tr("Edit"))
        self.remove_button = QPushButton(tr("Remove"))
        self.test_button = QPushButton(tr("Test"))
        self.switch_button = QPushButton(tr("Switch server…"))
        self.add_button.clicked.connect(self._add)
        self.edit_button.clicked.connect(self._edit)
        self.remove_button.clicked.connect(self._remove)
        self.test_button.clicked.connect(self._test)
        self.switch_button.clicked.connect(self._switch)
        for button in (self.add_button, self.edit_button, self.remove_button, self.test_button):
            actions.addWidget(button)
        actions.addStretch()
        actions.addWidget(self.switch_button)
        root.addLayout(actions)
        self._reload()

    def _current(self) -> ConnectionProfile | None:
        item = self.list.currentItem()
        if item is None:
            return None
        try:
            return self.store.profile(str(item.data(Qt.ItemDataRole.UserRole)))
        except (ConnectionSettingsError, KeyError):
            return None

    def _reload(self, selected_id: str | None = None) -> None:
        selected_id = selected_id or getattr(self.context, "connection_profile_id", "")
        self.list.clear()
        auto_id = self.store.auto_connect_profile_id()
        current_id = getattr(self.context, "connection_profile_id", "")
        for profile in self.store.list_profiles():
            labels = [profile.display_name]
            if profile.profile_id == current_id:
                labels.append(tr("Current"))
            if profile.profile_id == auto_id:
                labels.append(tr("Startup"))
            item = QListWidgetItem("  ·  ".join(labels))
            item.setData(Qt.ItemDataRole.UserRole, profile.profile_id)
            self.list.addItem(item)
            if selected_id and profile.profile_id == selected_id:
                self.list.setCurrentItem(item)
        if self.list.currentRow() < 0 and self.list.count():
            self.list.setCurrentRow(0)
        self._sync_actions(self.list.currentItem(), None)

    def _sync_actions(self, _current, _previous) -> None:
        profile = self._current()
        enabled = profile is not None
        current_id = getattr(self.context, "connection_profile_id", "")
        self.edit_button.setEnabled(enabled)
        self.test_button.setEnabled(enabled)
        self.remove_button.setEnabled(enabled and profile.profile_id != current_id)
        self.switch_button.setEnabled(
            enabled
            and not self.environment_pinned
            and self.context is not None
            and getattr(self.context, "runtime_control", None) is not None
            and profile.profile_id != current_id
        )
        with QSignalBlocker(self.startup_checkbox):
            self.startup_checkbox.setEnabled(enabled and not self.environment_pinned)
            self.startup_checkbox.setChecked(
                enabled and self.store.auto_connect_profile_id() == profile.profile_id
            )
        if profile is None:
            self.details.clear()
            return
        mode = tr("Full") if profile.mode == FULL_STORAGE else tr("Database only")
        storage = (
            str(profile.storage_root)
            if profile.mode == FULL_STORAGE
            else tr("Shared file storage disabled")
        )
        self.details.setText(
            f"{profile.username}@{profile.host}:{profile.port}/{profile.database}\n"
            f"{tr('Mode')}: {mode}  ·  {tr('File storage')}: {storage}"
        )

    def _startup_preference_changed(self, checked: bool) -> None:
        profile = self._current()
        if profile is None or self.environment_pinned:
            return
        try:
            self.store.set_auto_connect_profile(profile.profile_id if checked else None)
        except (ConnectionSettingsError, KeyError) as exc:
            QMessageBox.warning(self, tr("Connection settings"), str(exc))
            return
        self._reload(profile.profile_id)
        self.connection_changed.emit()

    def _add(self) -> None:
        dialog = ConnectionProfileDialog(self.store, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_profile:
            self._reload(dialog.saved_profile.profile_id)
            self.connection_changed.emit()

    def _edit(self) -> None:
        profile = self._current()
        if profile is None:
            return
        dialog = ConnectionProfileDialog(self.store, profile, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.saved_profile:
            self._reload(dialog.saved_profile.profile_id)
            self.connection_changed.emit()

    def _remove(self) -> None:
        profile = self._current()
        if profile is None or profile.profile_id == getattr(self.context, "connection_profile_id", ""):
            return
        if not _confirm_remove(self):
            return
        try:
            self.store.remove(profile.profile_id)
        except ConnectionSettingsError as exc:
            QMessageBox.warning(self, tr("Connection settings"), str(exc))
            return
        self._reload()
        self.connection_changed.emit()

    def _test(self) -> None:
        profile = self._current()
        if profile is None:
            return
        try:
            runtime = self.store.runtime_profile(profile.profile_id)
        except ConnectionSettingsError as exc:
            QMessageBox.warning(self, tr("Connection settings"), str(exc))
            return
        probe = ConnectionForm(runtime)
        result = probe.validate_and_test(saved_password=runtime.password)
        QMessageBox.information(
            self,
            tr("Connection test") if result else tr("Connection test failed"),
            probe.status.text(),
        )
        probe.deleteLater()

    def _switch(self) -> None:
        profile = self._current()
        control = getattr(self.context, "runtime_control", None)
        if profile is None or control is None:
            return
        control.request_switch(profile.profile_id, parent=self.window())
