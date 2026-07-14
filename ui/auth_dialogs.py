from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from services.auth_service import AuthError, AuthService


class FirstAdminDialog(QDialog):
    def __init__(self, auth_service: AuthService):
        super().__init__()
        self.auth_service = auth_service
        self.current_user = None
        self.setWindowTitle("Первичная настройка SlopeForge")
        self.setFixedWidth(420)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("В базе нет пользователей. Создайте первого администратора."))
        form = QFormLayout()
        self.username = QLineEdit()
        self.full_name = QLineEdit()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_repeat = QLineEdit(); self.password_repeat.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Логин *", self.username)
        form.addRow("Полное имя", self.full_name)
        form.addRow("Пароль *", self.password)
        form.addRow("Повтор пароля *", self.password_repeat)
        layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        create = QPushButton("Создать администратора")
        create.clicked.connect(self._create)
        buttons.addWidget(create)
        layout.addLayout(buttons)

    def _create(self) -> None:
        if not self.username.text().strip():
            QMessageBox.warning(self, "Проверьте данные", "Логин обязателен.")
            return
        if self.password.text() != self.password_repeat.text():
            QMessageBox.warning(self, "Проверьте данные", "Пароли не совпадают.")
            return
        try:
            self.current_user = self.auth_service.create_first_admin(self.username.text(), self.full_name.text().strip() or None, self.password.text())
            self.accept()
        except (AuthError, ValueError) as exc:
            QMessageBox.critical(self, "Не удалось создать администратора", str(exc))


class LoginDialog(QDialog):
    def __init__(self, auth_service: AuthService):
        super().__init__()
        self.auth_service = auth_service
        self.current_user = None
        self.setWindowTitle("Вход в SlopeForge")
        self.setFixedWidth(360)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Логин", self.username)
        form.addRow("Пароль", self.password)
        layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        login = QPushButton("Войти")
        login.clicked.connect(self._login)
        buttons.addWidget(login)
        layout.addLayout(buttons)

    def _login(self) -> None:
        try:
            self.current_user = self.auth_service.authenticate(self.username.text(), self.password.text())
            self.accept()
        except AuthError as exc:
            QMessageBox.warning(self, "Вход не выполнен", str(exc))
