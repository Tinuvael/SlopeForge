from __future__ import annotations

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from services.user_admin_service import UserAdminError, UserAdminService


class UserEditDialog(QDialog):
    def __init__(self, service: UserAdminService, actor, user=None):
        super().__init__()
        self.service = service
        self.actor = actor
        self.user = user
        self.setWindowTitle("Create user" if user is None else "Edit user")
        self.setFixedWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit()
        self.full_name = QLineEdit()
        self.role = QComboBox(); self.role.addItems(["admin", "editor", "viewer"])
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.repeat = QLineEdit(); self.repeat.setEchoMode(QLineEdit.EchoMode.Password)
        self.is_active = QCheckBox("Active")
        self.must_change = QCheckBox("Require password change on next sign-in")
        form.addRow("Username *", self.username)
        form.addRow("Full name", self.full_name)
        form.addRow("Role", self.role)
        if user is None:
            form.addRow("Temporary password *", self.password)
            form.addRow("Repeat password *", self.repeat)
        form.addRow("", self.is_active)
        form.addRow("", self.must_change)
        layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        save = QPushButton("Save"); save.clicked.connect(self.save)
        cancel = QPushButton("Cancel"); cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel); buttons.addWidget(save)
        layout.addLayout(buttons)
        self.is_active.setChecked(True)
        if user:
            self.username.setText(user.username); self.username.setEnabled(False)
            self.full_name.setText(user.full_name or "")
            self.role.setCurrentText(user.role)
            self.is_active.setChecked(user.is_active)
            self.must_change.setChecked(user.must_change_password)

    def save(self) -> None:
        try:
            if self.user is None:
                self.service.create_user(self.actor, self.username.text(), self.full_name.text().strip() or None, self.role.currentText(), self.password.text(), self.repeat.text(), self.is_active.isChecked(), self.must_change.isChecked())
            else:
                self.service.update_user(self.actor, self.user.id, self.full_name.text().strip() or None, self.role.currentText(), self.is_active.isChecked(), self.must_change.isChecked())
            self.accept()
        except (UserAdminError, PermissionError) as exc:
            QMessageBox.warning(self, "Could not save user", str(exc))


class PasswordDialog(QDialog):
    def __init__(self, service: UserAdminService, actor, user_id: int):
        super().__init__()
        self.service = service; self.actor = actor; self.user_id = user_id
        self.setWindowTitle("Change password")
        layout = QVBoxLayout(self); form = QFormLayout()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.repeat = QLineEdit(); self.repeat.setEchoMode(QLineEdit.EchoMode.Password)
        self.must_change = QCheckBox("Require password change on next sign-in")
        form.addRow("New password", self.password); form.addRow("Repeat password", self.repeat); form.addRow("", self.must_change)
        layout.addLayout(form)
        save = QPushButton("Save"); save.clicked.connect(self.save); layout.addWidget(save)

    def save(self) -> None:
        try:
            self.service.change_password(self.actor, self.user_id, self.password.text(), self.repeat.text(), self.must_change.isChecked())
            self.accept()
        except (UserAdminError, PermissionError) as exc:
            QMessageBox.warning(self, "Could not change password", str(exc))
