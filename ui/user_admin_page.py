from __future__ import annotations

from app.localization import tr

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QHBoxLayout, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget

from app.context import AppContext
from infrastructure.services.session_service import RememberTokenService
from infrastructure.services.user_admin_service import UserAdminService
from ui.user_admin_dialogs import PasswordDialog, UserEditDialog
from ui.widgets.design_system import configure_standard_table, set_button_role


class UserAdminPage(QWidget):
    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.service = UserAdminService(context.session_factory)
        layout = QVBoxLayout(self)
        title = QLabel(tr("Users")); title.setObjectName("SectionTitle"); layout.addWidget(title)
        self.empty = QLabel(tr("No users found.")); self.empty.setObjectName("EmptyState")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(self.empty)
        buttons = QHBoxLayout()
        self.create = QPushButton(tr("Create user"))
        self.edit = QPushButton(tr("Edit user"))
        self.password = QPushButton(tr("Change password"))
        self.toggle = QPushButton(tr("Activate / block"))
        self.revoke = QPushButton(tr("End all saved sessions"))
        for button in (self.create, self.edit, self.password, self.toggle, self.revoke):
            buttons.addWidget(button)
        set_button_role(self.create, "primary")
        for button in (self.edit, self.password, self.toggle, self.revoke):
            set_button_role(button, "secondary")
        buttons.addStretch(); layout.addLayout(buttons)
        self.table = QTableWidget(0, 8)
        configure_standard_table(self.table)
        self.table.setHorizontalHeaderLabels([tr("Username"), tr("Full name"), tr("Role"), tr("Active"), tr("Created"), tr("Last login"), tr("Created by"), tr("Updated by")])
        layout.addWidget(self.table)
        self.create.clicked.connect(self.create_user); self.edit.clicked.connect(self.edit_user); self.password.clicked.connect(self.change_password); self.toggle.clicked.connect(self.toggle_active); self.revoke.clicked.connect(self.revoke_sessions)
        enabled = context.current_user.role == "admin"
        for button in (self.create, self.edit, self.password, self.toggle, self.revoke):
            button.setEnabled(enabled)
        self.rows = []
        self.refresh()

    def refresh(self):
        if self.context.current_user.role != "admin":
            return
        self.rows = self.service.list_users(self.context.current_user)
        self.table.setRowCount(len(self.rows))
        for row, user in enumerate(self.rows):
            values = [user.username, user.full_name or "", user.role, "Yes" if user.is_active else "No", user.created_at.strftime("%Y-%m-%d %H:%M"), user.last_login_at.strftime("%Y-%m-%d %H:%M") if user.last_login_at else "", user.created_by or "", user.updated_by or ""]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(value))
        self.table.setVisible(bool(self.rows)); self.empty.setVisible(not self.rows)
        self.table.resizeColumnsToContents(); self.table.horizontalHeader().setStretchLastSection(True)

    def selected_user(self):
        row = self.table.currentRow()
        return self.rows[row] if 0 <= row < len(self.rows) else None

    def create_user(self):
        if UserEditDialog(self.service, self.context.current_user).exec(): self.refresh()

    def edit_user(self):
        user = self.selected_user()
        if user and UserEditDialog(self.service, self.context.current_user, user).exec(): self.refresh()

    def change_password(self):
        user = self.selected_user()
        if user and PasswordDialog(self.service, self.context.current_user, user.id).exec(): self.refresh()

    def toggle_active(self):
        user = self.selected_user()
        if not user: return
        self.service.set_active(self.context.current_user, user.id, not user.is_active); self.refresh()

    def revoke_sessions(self):
        user = self.selected_user()
        if not user: return
        self.service.revoke_all_sessions(self.context.current_user, user.id)
        QMessageBox.information(self, tr("Saved sessions"), tr("Saved sessions were revoked for this user."))
