from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.connection_settings import (
    ConnectionProfile,
    ConnectionSettingsError,
    ConnectionSettingsStore,
)
from app.database_updater_backend import create_database_upgrade_service
from app.qt import apply_window_icon
from app.updater_preferences import (
    backup_directory,
    last_backup,
    save_backup_directory,
    save_last_backup,
)
from application.services.database_upgrade import (
    DatabaseCompatibility,
    DatabaseInspection,
    DatabaseUpgradeError,
    UpgradeResult,
)
from ui.connection_dialog import ConnectionProfileDialog
from ui.theme import Spacing
from ui.widgets.design_system import set_button_role, set_status_role


class _WorkerSignals(QObject):
    result = Signal(object, object)
    error = Signal(object, object)


class _Worker(QRunnable):
    def __init__(self, operation):
        super().__init__()
        self.operation = operation
        self.signals = _WorkerSignals()

    def run(self):
        try:
            self.signals.result.emit(self, self.operation())
        except Exception as exc:
            self.signals.error.emit(self, exc)


_STATE_LABELS = {
    DatabaseCompatibility.UP_TO_DATE: ("Up to date", "success"),
    DatabaseCompatibility.UPGRADE_REQUIRED: ("Upgrade required", "warning"),
    DatabaseCompatibility.NEWER_THAN_RELEASE: ("Newer than this release", "error"),
    DatabaseCompatibility.UNKNOWN_OR_UNSUPPORTED: ("Unknown / unsupported revision", "error"),
}


class SlopeForgeUpdaterWindow(QMainWindow):
    """Small administrative shell for backup-gated production DB migrations."""

    def __init__(self, store: ConnectionSettingsStore | None = None, parent=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.store = store or ConnectionSettingsStore()
        self.thread_pool = QThreadPool.globalInstance()
        self._workers: set[_Worker] = set()
        self._worker_callbacks: dict[_Worker, object] = {}
        self._profile: ConnectionProfile | None = None
        self._service = None
        self._inspection: DatabaseInspection | None = None
        self._busy = False

        self.setWindowTitle("SlopeForge Updater")
        self.resize(820, 690)
        self.setMinimumSize(720, 620)

        central = QWidget(self)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        root.setSpacing(Spacing.MD)

        title = QLabel("SlopeForge Updater")
        title.setObjectName("EntityTitle")
        subtitle = QLabel(
            "Back up and upgrade a SlopeForge PostgreSQL database. "
            "Engineering clients should be closed during an upgrade."
        )
        subtitle.setObjectName("MutedText")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        root.addWidget(self._target_card())
        root.addWidget(self._backup_card())
        root.addLayout(self._action_row())

        log_title = QLabel("Status / log")
        log_title.setObjectName("CardTitle")
        root.addWidget(log_title)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(170)
        root.addWidget(self.log, 1)

        self._reload_profiles()
        self._set_last_backup(last_backup())

    def _target_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("ConnectionCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(
            Spacing.CARD_HORIZONTAL,
            Spacing.CARD_VERTICAL,
            Spacing.CARD_HORIZONTAL,
            Spacing.CARD_VERTICAL,
        )
        layout.setSpacing(Spacing.SM)
        heading = QLabel("Target database")
        heading.setObjectName("CardTitle")
        layout.addWidget(heading)

        select_row = QHBoxLayout()
        select_row.setSpacing(Spacing.SM)
        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(300)
        self.profile_combo.currentIndexChanged.connect(self._profile_changed)
        self.add_profile_button = set_button_role(
            QPushButton("Add connection…"), "secondary"
        )
        self.edit_profile_button = set_button_role(QPushButton("Edit…"), "secondary")
        self.add_profile_button.clicked.connect(self._add_profile)
        self.edit_profile_button.clicked.connect(self._edit_profile)
        select_row.addWidget(self.profile_combo, 1)
        select_row.addWidget(self.add_profile_button)
        select_row.addWidget(self.edit_profile_button)
        layout.addLayout(select_row)

        grid = QGridLayout()
        grid.setHorizontalSpacing(Spacing.LG)
        grid.setVerticalSpacing(Spacing.SM)
        self.location_value = QLabel("—")
        self.current_value = QLabel("—")
        self.required_value = QLabel("—")
        for value in (self.location_value, self.current_value, self.required_value):
            value.setObjectName("InspectorValue")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.compatibility_value = QLabel("Not checked")
        set_status_role(self.compatibility_value, "neutral")
        rows = (
            ("Server / database", self.location_value),
            ("Current schema", self.current_value),
            ("Required schema", self.required_value),
            ("Status", self.compatibility_value),
        )
        for row, (caption, value) in enumerate(rows):
            label = QLabel(caption)
            label.setObjectName("MutedText")
            grid.addWidget(label, row, 0)
            grid.addWidget(value, row, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return card

    def _backup_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("ConnectionCard")
        layout = QGridLayout(card)
        layout.setContentsMargins(
            Spacing.CARD_HORIZONTAL,
            Spacing.CARD_VERTICAL,
            Spacing.CARD_HORIZONTAL,
            Spacing.CARD_VERTICAL,
        )
        layout.setHorizontalSpacing(Spacing.MD)
        layout.setVerticalSpacing(Spacing.SM)
        title = QLabel("Backup")
        title.setObjectName("CardTitle")
        layout.addWidget(title, 0, 0, 1, 3)

        folder_label = QLabel("Backup folder")
        folder_label.setObjectName("MutedText")
        self.backup_folder = QLineEdit(str(backup_directory()))
        self.backup_folder.setReadOnly(True)
        self.browse_button = set_button_role(QPushButton("Browse…"), "secondary")
        self.browse_button.clicked.connect(self._browse_backup_folder)
        layout.addWidget(folder_label, 1, 0)
        layout.addWidget(self.backup_folder, 1, 1)
        layout.addWidget(self.browse_button, 1, 2)

        last_label = QLabel("Last backup")
        last_label.setObjectName("MutedText")
        self.last_backup_value = QLabel("—")
        self.last_backup_value.setObjectName("InspectorValue")
        self.last_backup_value.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(last_label, 2, 0)
        layout.addWidget(self.last_backup_value, 2, 1, 1, 2)
        layout.setColumnStretch(1, 1)
        return card

    def _action_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(Spacing.SM)
        self.test_button = set_button_role(
            QPushButton("Test connection"), "secondary"
        )
        self.backup_button = set_button_role(QPushButton("Create backup"), "secondary")
        self.verify_button = set_button_role(
            QPushButton("Verify database"), "secondary"
        )
        self.upgrade_button = set_button_role(
            QPushButton("Backup & upgrade"), "primary"
        )
        self.test_button.clicked.connect(self._test_connection)
        self.backup_button.clicked.connect(self._create_backup)
        self.verify_button.clicked.connect(self._verify_database)
        self.upgrade_button.clicked.connect(self._backup_and_upgrade)
        row.addWidget(self.test_button)
        row.addWidget(self.backup_button)
        row.addWidget(self.verify_button)
        row.addStretch(1)
        row.addWidget(self.upgrade_button)
        return row

    def _reload_profiles(self, select_id: str | None = None) -> None:
        previous = select_id or self.profile_combo.currentData()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for profile in self.store.list_profiles():
            self.profile_combo.addItem(profile.display_name, profile.profile_id)
        if previous:
            index = self.profile_combo.findData(previous)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)
        if self.profile_combo.count():
            self._profile_changed()
        else:
            self._profile = None
            self._service = None
            self._inspection = None
            self._reset_database_details("No saved connection")
            self._append_log(
                "No saved server profiles. Add a connection to begin.", persist=False
            )
        self._sync_actions()

    @staticmethod
    def _profile_location(profile: ConnectionProfile) -> str:
        username = f"{profile.username}@" if profile.username else ""
        return f"{username}{profile.host}:{profile.port}/{profile.database}"

    def _profile_changed(self, _index: int = -1) -> None:
        profile_id = str(self.profile_combo.currentData() or "")
        self._inspection = None
        if not profile_id:
            self._profile = None
            self._service = None
            self._reset_database_details("No connection selected")
            self._sync_actions()
            return
        try:
            self._profile = self.store.runtime_profile(profile_id)
            settings = self._profile.to_settings()
        except (ConnectionSettingsError, KeyError, ValueError) as exc:
            self._profile = None
            self._service = None
            self._reset_database_details("Connection unavailable")
            self._append_log(f"Connection profile error: {exc}", persist=False)
            self._sync_actions()
            return
        self._service = create_database_upgrade_service(settings)
        self.location_value.setText(self._profile_location(self._profile))
        self.current_value.setText("—")
        self.required_value.setText("—")
        self._set_compatibility("Not checked", "neutral")
        self._sync_actions()
        self._run_operation(
            "Inspecting database…",
            self._service.inspect_database,
            self._inspection_finished,
        )

    def _add_profile(self) -> None:
        dialog = ConnectionProfileDialog(self.store, parent=self)
        if dialog.exec() == dialog.DialogCode.Accepted and dialog.saved_profile:
            self._reload_profiles(dialog.saved_profile.profile_id)

    def _edit_profile(self) -> None:
        if self._profile is None:
            return
        try:
            stored = self.store.profile(self._profile.profile_id)
        except (ConnectionSettingsError, KeyError):
            return
        dialog = ConnectionProfileDialog(self.store, stored, self)
        if dialog.exec() == dialog.DialogCode.Accepted and dialog.saved_profile:
            self._reload_profiles(dialog.saved_profile.profile_id)

    def _browse_backup_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Select backup folder",
            self.backup_folder.text(),
        )
        if not selected:
            return
        folder = save_backup_directory(selected)
        self.backup_folder.setText(str(folder))
        self._append_log(f"Backup folder: {folder}", persist=False)
        self._sync_actions()

    def _test_connection(self) -> None:
        if self._service is None:
            return
        self._run_operation(
            "Testing connection and reading schema…",
            self._service.inspect_database,
            self._inspection_finished,
        )

    def _verify_database(self) -> None:
        if self._service is None:
            return
        self._run_operation(
            "Verifying database…",
            self._service.verify_database,
            self._verification_finished,
        )

    def _create_backup(self) -> None:
        if self._service is None:
            return
        folder = Path(self.backup_folder.text())
        self._run_operation(
            "Creating PostgreSQL backup…",
            lambda: self._service.create_backup(folder),
            self._backup_finished,
        )

    def _backup_and_upgrade(self) -> None:
        if self._service is None or self._profile is None or self._inspection is None:
            return
        if self._inspection.compatibility != DatabaseCompatibility.UPGRADE_REQUIRED:
            return
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Backup & upgrade database?")
        box.setText(
            "Close or disconnect SlopeForge engineering clients before continuing."
        )
        box.setInformativeText(
            f"Target: {self.location_value.text()}\n"
            f"Current schema: {self.current_value.text()}\n"
            f"Required schema: {self.required_value.text()}\n"
            f"Backup folder: {self.backup_folder.text()}\n\n"
            "A verified backup will be created before any schema migration."
        )
        upgrade = box.addButton(
            "Backup & upgrade", QMessageBox.ButtonRole.AcceptRole
        )
        cancel = box.addButton("Cancel", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        if box.clickedButton() is not upgrade:
            return
        folder = Path(self.backup_folder.text())
        self._run_operation(
            "Creating backup and upgrading database…",
            lambda: self._service.backup_and_upgrade(folder),
            self._upgrade_finished,
        )

    def _inspection_finished(self, inspection: DatabaseInspection) -> None:
        self._apply_inspection(inspection)
        self._append_log(
            f"Database inspected: {self.compatibility_value.text()} "
            f"(current={self.current_value.text()}, required={self.required_value.text()})."
        )

    def _verification_finished(self, inspection: DatabaseInspection) -> None:
        self._apply_inspection(inspection)
        if inspection.verified:
            self._append_log("Database verification passed.")
        elif inspection.missing_tables:
            self._append_log(
                "Database verification failed; missing tables: "
                + ", ".join(inspection.missing_tables[:8])
            )
        else:
            self._append_log(
                f"Database verification result: {self.compatibility_value.text()}."
            )

    def _backup_finished(self, backup) -> None:
        self._set_last_backup(backup.path)
        self._append_log(
            f"Backup created: {backup.path} ({backup.size_bytes} bytes)."
        )

    def _upgrade_finished(self, result: UpgradeResult) -> None:
        self._set_last_backup(result.backup.path)
        self._apply_inspection(result.after)
        self._append_log(
            f"Backup created: {result.backup.path} ({result.backup.size_bytes} bytes)."
        )
        self._append_log(
            "Database upgrade completed successfully at schema "
            f"{result.after.required_revision}."
        )

    def _apply_inspection(self, inspection: DatabaseInspection) -> None:
        self._inspection = inspection
        current = (
            inspection.current_revision
            if inspection.current_revision is not None
            else (
                ", ".join(inspection.current_heads)
                if inspection.current_heads
                else "—"
            )
        )
        self.current_value.setText(current)
        self.required_value.setText(inspection.required_revision)
        label, role = _STATE_LABELS[inspection.compatibility]
        if (
            inspection.missing_tables
            and inspection.compatibility == DatabaseCompatibility.UP_TO_DATE
        ):
            label = "Verification failed"
            role = "error"
        self._set_compatibility(label, role)
        self._sync_actions()

    def _reset_database_details(self, status: str) -> None:
        self.location_value.setText("—")
        self.current_value.setText("—")
        self.required_value.setText("—")
        self._set_compatibility(status, "neutral")

    def _set_compatibility(self, text: str, role: str) -> None:
        self.compatibility_value.setText(text)
        set_status_role(self.compatibility_value, role)

    def _set_last_backup(self, path: Path | None) -> None:
        if path is None:
            self.last_backup_value.setText("—")
            return
        saved = save_last_backup(path)
        self.last_backup_value.setText(str(saved))

    def _run_operation(self, status: str, operation, success) -> None:
        if self._busy:
            return
        self._busy = True
        self._sync_actions()
        self._append_log(status, persist=False)
        worker = _Worker(operation)
        self._workers.add(worker)
        self._worker_callbacks[worker] = success
        worker.signals.result.connect(self._worker_result)
        worker.signals.error.connect(self._worker_error)
        self.thread_pool.start(worker)

    @Slot(object, object)
    def _worker_result(self, worker: _Worker, value) -> None:
        callback = self._worker_callbacks.pop(worker, None)
        self._workers.discard(worker)
        self._busy = False
        if callback is not None:
            callback(value)
        self._sync_actions()

    @Slot(object, object)
    def _worker_error(self, worker: _Worker, exc: Exception) -> None:
        self._worker_callbacks.pop(worker, None)
        self._workers.discard(worker)
        self._busy = False
        self._operation_failed(exc)
        self._sync_actions()

    def _operation_failed(self, exc: Exception) -> None:
        message = self._safe_text(str(exc)) or exc.__class__.__name__
        if isinstance(exc, DatabaseUpgradeError) and exc.backup_path:
            self._set_last_backup(exc.backup_path)
            message += f" Backup preserved at: {exc.backup_path}"
        self._set_compatibility("Operation failed", "error")
        self._append_log(f"ERROR: {message}")

    def _safe_text(self, text: str) -> str:
        secret = self._profile.password if self._profile is not None else ""
        rendered = str(text or "")
        if secret:
            for candidate in {secret, quote(secret, safe="")}:
                rendered = rendered.replace(candidate, "<redacted>")
        return rendered

    def _append_log(self, message: str, *, persist: bool = True) -> None:
        stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")
        rendered = self._safe_text(message)
        line = f"[{stamp}] {rendered}"
        self.log.appendPlainText(line)
        if not persist:
            return
        folder_text = (
            self.backup_folder.text().strip()
            if hasattr(self, "backup_folder")
            else ""
        )
        if not folder_text:
            return
        try:
            folder = Path(folder_text)
            folder.mkdir(parents=True, exist_ok=True)
            with (folder / "SlopeForge_updater.log").open(
                "a", encoding="utf-8"
            ) as handle:
                handle.write(line + "\n")
        except OSError:
            pass

    def _sync_actions(self) -> None:
        has_profile = self._service is not None
        has_folder = bool(
            getattr(self, "backup_folder", None)
            and self.backup_folder.text().strip()
        )
        for control in (
            self.profile_combo,
            self.add_profile_button,
            self.edit_profile_button,
            self.browse_button,
        ):
            control.setEnabled(not self._busy)
        self.edit_profile_button.setEnabled(not self._busy and has_profile)
        self.test_button.setEnabled(not self._busy and has_profile)
        self.backup_button.setEnabled(not self._busy and has_profile and has_folder)
        self.verify_button.setEnabled(not self._busy and has_profile)
        self.upgrade_button.setEnabled(
            not self._busy
            and has_profile
            and has_folder
            and self._inspection is not None
            and self._inspection.compatibility == DatabaseCompatibility.UPGRADE_REQUIRED
        )
