from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from app.config import APP_NAME
from app.qt import apply_window_icon
from services.auth_service import AuthError, AuthService


class FirstAdminDialog(QDialog):
    def __init__(self, auth_service: AuthService):
        super().__init__()
        self.auth_service = auth_service
        apply_window_icon(self)
        self.current_user = None
        self.setWindowTitle(f"Initial setup {APP_NAME}")
        self.setFixedWidth(420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("There are no users in the database. Create the first administrator."))
        form = QFormLayout()
        self.username = QLineEdit()
        self.full_name = QLineEdit()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_repeat = QLineEdit(); self.password_repeat.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Username *", self.username)
        form.addRow("Full name", self.full_name)
        form.addRow("Password *", self.password)
        form.addRow("Repeat password *", self.password_repeat)
        layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        create = QPushButton("Create administrator")
        create.clicked.connect(self._create)
        buttons.addWidget(create)
        layout.addLayout(buttons)

    def _create(self) -> None:
        if not self.username.text().strip():
            QMessageBox.warning(self, "Check input", "Username is required.")
            return
        if self.password.text() != self.password_repeat.text():
            QMessageBox.warning(self, "Check input", "Passwords do not match.")
            return
        try:
            self.current_user = self.auth_service.create_first_admin(self.username.text(), self.full_name.text().strip() or None, self.password.text())
            self.accept()
        except (AuthError, ValueError) as exc:
            QMessageBox.critical(self, "Could not create administrator", str(exc))


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
        form.addRow("Username", self.username)
        form.addRow("Password", self.password)
        self.remember = QCheckBox("Remember me on this computer")
        layout.addLayout(form)
        layout.addWidget(self.remember)
        buttons = QHBoxLayout(); buttons.addStretch()
        login = QPushButton("Sign in")
        login.clicked.connect(self._login)
        buttons.addWidget(login)
        layout.addLayout(buttons)

    def _login(self) -> None:
        try:
            self.current_user = self.auth_service.authenticate(self.username.text(), self.password.text())
            self.remember_requested = self.remember.isChecked()
            self.accept()
        except AuthError as exc:
            QMessageBox.warning(self, "Sign in failed", str(exc))
