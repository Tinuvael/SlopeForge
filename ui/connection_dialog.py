from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.connection_settings import (
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


CARD_STYLE = (
    "QFrame#ConnectionCard{background:#ffffff;border:1px solid #d7dde6;"
    "border-radius:7px;}"
)
STATUS_OK_STYLE = "color:#2f6f3e;font-weight:600;"
STATUS_ERROR_STYLE = "color:#a33a32;font-weight:600;"
STATUS_INFO_STYLE = "color:#64748b;"


class ConnectionForm(QWidget):
    def __init__(self, profile: ConnectionProfile | None = None, parent=None):
        super().__init__(parent)
        profile = profile or ConnectionProfile()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        database_card = QFrame()
        database_card.setObjectName("ConnectionCard")
        database_card.setStyleSheet(CARD_STYLE)
        database_layout = QVBoxLayout(database_card)
        database_layout.setContentsMargins(14, 12, 14, 12)
        database_layout.setSpacing(8)
        database_title = QLabel(tr("PostgreSQL server"))
        database_title.setStyleSheet("font-weight:600;color:#1f2937;")
        database_layout.addWidget(database_title)

        database_form = QFormLayout()
        database_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        database_form.setHorizontalSpacing(12)
        database_form.setVerticalSpacing(8)
        self.host = QLineEdit(profile.host)
        self.port = QSpinBox()
        self.port.setRange(1, 65535)
        self.port.setValue(int(profile.port or 5432))
        self.database = QLineEdit(profile.database)
        self.username = QLineEdit(profile.username)
        self.password = QLineEdit(profile.password)
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        database_form.addRow(tr("Server / Host"), self.host)
        database_form.addRow(tr("Port"), self.port)
        database_form.addRow(tr("Database"), self.database)
        database_form.addRow(tr("User"), self.username)
        database_form.addRow(tr("Password"), self.password)
        database_layout.addLayout(database_form)
        root.addWidget(database_card)

        storage_card = QFrame()
        storage_card.setObjectName("ConnectionCard")
        storage_card.setStyleSheet(CARD_STYLE)
        storage_layout = QVBoxLayout(storage_card)
        storage_layout.setContentsMargins(14, 12, 14, 12)
        storage_layout.setSpacing(8)
        storage_title = QLabel(tr("File storage"))
        storage_title.setStyleSheet("font-weight:600;color:#1f2937;")
        storage_layout.addWidget(storage_title)
        storage_hint = QLabel(tr("Use a folder that all SlopeForge users can access."))
        storage_hint.setObjectName("MutedText")
        storage_hint.setStyleSheet("color:#64748b;")
        storage_layout.addWidget(storage_hint)
        storage_row = QHBoxLayout()
        storage_row.setSpacing(8)
        self.storage = QLineEdit(str(profile.storage_root or ""))
        browse = QPushButton(tr("Browse…"))
        browse.setIcon(ui_icon("folder-open"))
        browse.clicked.connect(self._browse_storage)
        storage_row.addWidget(self.storage, 1)
        storage_row.addWidget(browse)
        storage_layout.addLayout(storage_row)
        root.addWidget(storage_card)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(STATUS_INFO_STYLE)
        self.status.setMinimumHeight(22)
        root.addWidget(self.status)

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
            host=self.host.text(),
            port=self.port.value(),
            database=self.database.text(),
            username=self.username.text(),
            password=self.password.text(),
            storage_root=self.storage.text().strip(),
        )

    def set_status(self, text: str, *, error: bool = False, success: bool = False) -> None:
        self.status.setText(text)
        if error:
            self.status.setStyleSheet(STATUS_ERROR_STYLE)
        elif success:
            self.status.setStyleSheet(STATUS_OK_STYLE)
        else:
            self.status.setStyleSheet(STATUS_INFO_STYLE)

    def validate_and_test(self) -> tuple[ConnectionProfile, Settings] | None:
        profile = self.profile()
        engine = None
        self.set_status(tr("Testing PostgreSQL and file storage…"))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            profile.validate_required()
            settings = profile.to_settings()
            engine = create_database_engine(settings)
            check_connection(engine)
            validate_storage_root(profile.storage_root)
        except (ConnectionSettingsError, ConfigurationError, DatabaseConnectionError, OSError, ValueError) as exc:
            self.set_status(f"{tr('Connection test failed')}: {exc}", error=True)
            return None
        finally:
            if engine is not None:
                engine.dispose()
            QApplication.restoreOverrideCursor()
        self.set_status(tr("Connection and file storage are available."), success=True)
        return profile.normalized(), settings


class ConnectionSetupDialog(QDialog):
    """First-run connection setup shown before authentication."""

    def __init__(
        self,
        store: ConnectionSettingsStore | None = None,
        parent=None,
    ):
        super().__init__(parent)
        apply_window_icon(self)
        self.store = store or ConnectionSettingsStore()
        self.runtime_settings: Settings | None = None
        self.saved_profile: ConnectionProfile | None = None
        self.setWindowTitle(tr("SlopeForge connection setup"))
        self.setModal(True)
        self.resize(620, 520)
        self.setMinimumWidth(560)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 16, 18, 16)
        root.setSpacing(12)
        title = QLabel(tr("Connect SlopeForge"))
        title.setStyleSheet("font-size:20px;font-weight:700;color:#0f172a;")
        root.addWidget(title)
        description = QLabel(
            tr("Configure the PostgreSQL server and shared file storage before signing in.")
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#64748b;")
        root.addWidget(description)

        self.form = ConnectionForm()
        root.addWidget(self.form, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.test_button = QPushButton(tr("Test connection"))
        self.test_button.setIcon(ui_icon("analytics", "blue"))
        self.test_button.clicked.connect(self.form.validate_and_test)
        cancel = QPushButton(tr("Cancel"))
        cancel.clicked.connect(self.reject)
        save = QPushButton(tr("Save and continue"))
        save.setDefault(True)
        save.clicked.connect(self._save)
        buttons.addWidget(self.test_button)
        buttons.addStretch()
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def _save(self) -> None:
        result = self.form.validate_and_test()
        if result is None:
            return
        profile, settings = result
        try:
            self.store.save(profile)
        except ConnectionSettingsError as exc:
            self.form.set_status(str(exc), error=True)
            return
        self.saved_profile = profile
        self.runtime_settings = settings
        self.accept()


class ConnectionSettingsPage(QWidget):
    """Settings page. Changes are persisted for the next application start."""

    def __init__(self, parent=None, store: ConnectionSettingsStore | None = None):
        super().__init__(parent)
        self.store = store or ConnectionSettingsStore()
        profile, source = effective_profile(self.store)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(10)

        title = QLabel(f"<b>{tr('Connection')}</b>")
        root.addWidget(title)
        description = QLabel(
            tr("Edit the PostgreSQL server and shared file storage used on the next SlopeForge start.")
        )
        description.setWordWrap(True)
        description.setStyleSheet("color:#64748b;")
        root.addWidget(description)

        if source == "environment":
            override = QLabel(
                tr("DATABASE_URL and STORAGE_ROOT currently override saved connection settings.")
            )
            override.setWordWrap(True)
            override.setStyleSheet(
                "background:#fff7e6;border:1px solid #e8c77d;border-radius:5px;"
                "padding:7px;color:#725514;"
            )
            root.addWidget(override)

        self.form = ConnectionForm(profile)
        root.addWidget(self.form, 1)

        actions = QHBoxLayout()
        test_button = QPushButton(tr("Test connection"))
        test_button.clicked.connect(self.form.validate_and_test)
        save_button = QPushButton(tr("Save changes"))
        save_button.setIcon(ui_icon("edit", "blue"))
        save_button.clicked.connect(self._save)
        actions.addWidget(test_button)
        actions.addStretch()
        actions.addWidget(save_button)
        root.addLayout(actions)

    def _save(self) -> None:
        result = self.form.validate_and_test()
        if result is None:
            return
        profile, _settings = result
        try:
            self.store.save(profile)
        except ConnectionSettingsError as exc:
            self.form.set_status(str(exc), error=True)
            return
        QMessageBox.information(
            self,
            tr("Connection settings saved"),
            tr("Restart SlopeForge to use the new connection and file storage settings."),
        )
