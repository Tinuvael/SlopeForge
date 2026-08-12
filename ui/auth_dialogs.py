from __future__ import annotations

from app.localization import tr

from PySide6.QtWidgets import QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from app.config import APP_NAME
from app.qt import apply_window_icon
from infrastructure.services.auth_service import AuthError, AuthService


class FirstAdminDialog(QDialog):
    def __init__(self, auth_service: AuthService):
        super().__init__()
        self.auth_service = auth_service
        apply_window_icon(self)
        self.current_user = None
        self.setWindowTitle(f"Initial setup {APP_NAME}")
        self.setFixedWidth(420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("There are no users in the database. Create the first administrator.")))
        form = QFormLayout()
        self.username = QLineEdit()
        self.full_name = QLineEdit()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_repeat = QLineEdit(); self.password_repeat.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(tr("Username *"), self.username)
        form.addRow(tr("Full name"), self.full_name)
        form.addRow(tr("Password *"), self.password)
        form.addRow(tr("Repeat password *"), self.password_repeat)
        layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        create = QPushButton(tr("Create administrator"))
        create.clicked.connect(self._create)
        buttons.addWidget(create)
        layout.addLayout(buttons)

    def _create(self) -> None:
        if not self.username.text().strip():
            QMessageBox.warning(self, tr("Check input"), tr("Username is required."))
            return
        if self.password.text() != self.password_repeat.text():
            QMessageBox.warning(self, tr("Check input"), tr("Passwords do not match."))
            return
        try:
            self.current_user = self.auth_service.create_first_admin(self.username.text(), self.full_name.text().strip() or None, self.password.text())
            self.accept()
        except (AuthError, ValueError) as exc:
            QMessageBox.critical(self, tr("Could not create administrator"), str(exc))


class LoginDialog(QDialog):
    def __init__(self, auth_service: AuthService):
        super().__init__()
        self.auth_service = auth_service
        apply_window_icon(self)
        self.current_user = None
        self.remember_requested = False
        self.setWindowTitle(f"Sign in to {APP_NAME}")
        self.setFixedWidth(360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(tr("Username"), self.username)
        form.addRow(tr("Password"), self.password)
        self.remember = QCheckBox(tr("Remember me on this computer"))
        layout.addLayout(form)
        layout.addWidget(self.remember)
        buttons = QHBoxLayout(); buttons.addStretch()
        login = QPushButton(tr("Sign in"))
        login.clicked.connect(self._login)
        buttons.addWidget(login)
        layout.addLayout(buttons)

    def _login(self) -> None:
        try:
            self.current_user = self.auth_service.authenticate(self.username.text(), self.password.text())
            self.remember_requested = self.remember.isChecked()
            self.accept()
        except AuthError as exc:
            QMessageBox.warning(self, tr("Sign in failed"), str(exc))
