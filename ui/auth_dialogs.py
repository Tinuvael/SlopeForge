from __future__ import annotations

from app.localization import tr

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.config import APP_NAME
from app.qt import apply_window_icon
from infrastructure.services.auth_service import AuthError, AuthService
from ui.widgets.design_system import set_button_role, set_status_role


def _add_server_context(
    layout: QVBoxLayout,
    *,
    server_name: str,
    server_location: str,
    database_only: bool,
) -> tuple[QLabel | None, QLabel | None, QLabel | None]:
    if not server_name and not server_location:
        return None, None, None

    card = QFrame()
    card.setObjectName("ConnectionCard")
    card_layout = QVBoxLayout(card)
    card_layout.setContentsMargins(12, 10, 12, 10)
    card_layout.setSpacing(3)

    caption = QLabel(tr("Server"))
    caption.setObjectName("MutedText")
    name_label = QLabel(server_name or tr("Selected server"))
    name_label.setObjectName("CardTitle")
    location_label = QLabel(server_location)
    location_label.setObjectName("MutedText")
    location_label.setWordWrap(True)
    card_layout.addWidget(caption)
    card_layout.addWidget(name_label)
    if server_location:
        card_layout.addWidget(location_label)

    mode_label = None
    if database_only:
        mode_label = QLabel(tr("Database only"))
        set_status_role(mode_label, "info")
        card_layout.addWidget(mode_label)

    layout.addWidget(card)
    return name_label, location_label, mode_label


class FirstAdminDialog(QDialog):
    def __init__(
        self,
        auth_service: AuthService,
        *,
        server_name: str = "",
        server_location: str = "",
        database_only: bool = False,
    ):
        super().__init__()
        self.auth_service = auth_service
        apply_window_icon(self)
        self.current_user = None
        self.setWindowTitle(f"Initial setup {APP_NAME}")
        self.setFixedWidth(440)
        layout = QVBoxLayout(self)
        (
            self.server_name_label,
            self.server_location_label,
            self.server_mode_label,
        ) = _add_server_context(
            layout,
            server_name=server_name,
            server_location=server_location,
            database_only=database_only,
        )
        intro = QLabel(
            tr("There are no users in the database. Create the first administrator.")
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.username = QLineEdit()
        self.full_name = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_repeat = QLineEdit()
        self.password_repeat.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(tr("Username *"), self.username)
        form.addRow(tr("Full name"), self.full_name)
        form.addRow(tr("Password *"), self.password)
        form.addRow(tr("Repeat password *"), self.password_repeat)
        layout.addLayout(form)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = set_button_role(QPushButton(tr("Cancel")), "secondary")
        self.cancel_button.clicked.connect(self.reject)
        self.create_button = set_button_role(
            QPushButton(tr("Create administrator")), "primary"
        )
        self.create_button.setDefault(True)
        self.create_button.clicked.connect(self._create)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.create_button)
        layout.addLayout(buttons)

    def _create(self) -> None:
        if not self.username.text().strip():
            QMessageBox.warning(self, tr("Check input"), tr("Username is required."))
            return
        if self.password.text() != self.password_repeat.text():
            QMessageBox.warning(self, tr("Check input"), tr("Passwords do not match."))
            return
        try:
            self.current_user = self.auth_service.create_first_admin(
                self.username.text(),
                self.full_name.text().strip() or None,
                self.password.text(),
            )
            self.accept()
        except (AuthError, ValueError) as exc:
            QMessageBox.critical(self, tr("Could not create administrator"), str(exc))


class LoginDialog(QDialog):
    def __init__(
        self,
        auth_service: AuthService,
        *,
        server_name: str = "",
        server_location: str = "",
        database_only: bool = False,
    ):
        super().__init__()
        self.auth_service = auth_service
        apply_window_icon(self)
        self.current_user = None
        self.remember_requested = False
        self.setWindowTitle(f"Sign in to {APP_NAME}")
        self.setFixedWidth(400)
        layout = QVBoxLayout(self)
        (
            self.server_name_label,
            self.server_location_label,
            self.server_mode_label,
        ) = _add_server_context(
            layout,
            server_name=server_name,
            server_location=server_location,
            database_only=database_only,
        )
        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(tr("Username"), self.username)
        form.addRow(tr("Password"), self.password)
        self.remember = QCheckBox(tr("Remember me on this server"))
        self.remember.setToolTip(
            tr("Saved sign-in is kept separately for each SlopeForge server connection.")
        )
        layout.addLayout(form)
        layout.addWidget(self.remember)
        buttons = QHBoxLayout()
        buttons.addStretch()
        self.cancel_button = set_button_role(QPushButton(tr("Cancel")), "secondary")
        self.cancel_button.clicked.connect(self.reject)
        self.login_button = set_button_role(QPushButton(tr("Sign in")), "primary")
        self.login_button.setDefault(True)
        self.login_button.clicked.connect(self._login)
        buttons.addWidget(self.cancel_button)
        buttons.addWidget(self.login_button)
        layout.addLayout(buttons)

    def _login(self) -> None:
        try:
            self.current_user = self.auth_service.authenticate(
                self.username.text(), self.password.text()
            )
            self.remember_requested = self.remember.isChecked()
            self.accept()
        except AuthError as exc:
            QMessageBox.warning(self, tr("Sign in failed"), str(exc))
