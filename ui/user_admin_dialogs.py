from __future__ import annotations

from app.localization import tr

from PySide6.QtWidgets import QCheckBox, QComboBox, QDialog, QFormLayout, QHBoxLayout, QLineEdit, QMessageBox, QPushButton, QVBoxLayout

from services.user_admin_service import UserAdminError, UserAdminService


class UserEditDialog(QDialog):
    def __init__(self, service: UserAdminService, actor, user=None):
        super().__init__()
        self.service = service
        self.actor = actor
        self.user = user
        self.setWindowTitle(tr("Create user") if user is None else "Edit user")
        self.setFixedWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.username = QLineEdit()
        self.full_name = QLineEdit()
        self.role = QComboBox(); self.role.addItems(["admin", "editor", "viewer"])
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.repeat = QLineEdit(); self.repeat.setEchoMode(QLineEdit.EchoMode.Password)
        self.is_active = QCheckBox(tr("Active"))
        self.must_change = QCheckBox(tr("Require password change on next sign-in"))
        form.addRow(tr("Username *"), self.username)
        form.addRow(tr("Full name"), self.full_name)
        form.addRow(tr("Role"), self.role)
        if user is None:
            form.addRow(tr("Temporary password *"), self.password)
            form.addRow(tr("Repeat password *"), self.repeat)
        form.addRow("", self.is_active)
        form.addRow("", self.must_change)
        layout.addLayout(form)
        buttons = QHBoxLayout(); buttons.addStretch()
        save = QPushButton(tr("Save")); save.clicked.connect(self.save)
        cancel = QPushButton(tr("Cancel")); cancel.clicked.connect(self.reject)
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
            QMessageBox.warning(self, tr("Could not save user"), str(exc))


class PasswordDialog(QDialog):
    def __init__(self, service: UserAdminService, actor, user_id: int):
        super().__init__()
        self.service = service; self.actor = actor; self.user_id = user_id
        self.setWindowTitle(tr("Change password"))
        layout = QVBoxLayout(self); form = QFormLayout()
        self.password = QLineEdit(); self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.repeat = QLineEdit(); self.repeat.setEchoMode(QLineEdit.EchoMode.Password)
        self.must_change = QCheckBox(tr("Require password change on next sign-in"))
        form.addRow(tr("New password"), self.password); form.addRow(tr("Repeat password"), self.repeat); form.addRow("", self.must_change)
        layout.addLayout(form)
        save = QPushButton(tr("Save")); save.clicked.connect(self.save); layout.addWidget(save)

    def save(self) -> None:
        try:
            self.service.change_password(self.actor, self.user_id, self.password.text(), self.repeat.text(), self.must_change.isChecked())
            self.accept()
        except (UserAdminError, PermissionError) as exc:
            QMessageBox.warning(self, tr("Could not change password"), str(exc))
