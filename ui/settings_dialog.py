from __future__ import annotations

from app.localization import save_language, selected_language, tr

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from app.config import APP_AUTHOR, APP_COPYRIGHT, APP_DESCRIPTION, APP_ICON_PATH, APP_NAME, APP_REPOSITORY_URL, APP_VERSION
from app.qt import apply_window_icon
from app.resources import resource_path
from app.context import AppContext
from infrastructure.services.session_service import RememberTokenService
from ui.user_admin_page import UserAdminPage
from ui.engineering_catalogues_page import EngineeringCataloguesPage
from app.use_case_factory import create_explosive_catalogue


class SettingsDialog(QDialog):
    catalogue_changed = Signal()
    def __init__(self, context: AppContext | None = None, parent=None):
        super().__init__(parent)
        apply_window_icon(self)
        self.context = context
        self.setWindowTitle(tr("Settings"))
        self.resize(900, 560)

        layout = QHBoxLayout(self)
        self.menu = QListWidget()
        self.menu.setFixedWidth(190)
        self.pages = QStackedWidget()
        self._add_page(tr("General"), self.general_page())
        if context:
            self.catalogues_page = EngineeringCataloguesPage(
                create_explosive_catalogue(context), can_edit=context.current_user.can_edit)
            self._add_page(tr("Engineering catalogues"), self.catalogues_page)
            self.catalogues_page.catalogue_changed.connect(self.catalogue_changed)
        if context and context.current_user.role == "admin":
            self._add_page(tr("Users"), UserAdminPage(context))
        self._add_page(tr("About"), self.about_page())
        self.menu.currentRowChanged.connect(self.pages.setCurrentIndex)
        self.menu.setCurrentRow(0)
        layout.addWidget(self.menu)
        layout.addWidget(self.pages)

    def _add_page(self, title: str, widget: QWidget) -> None:
        self.menu.addItem(title)
        self.pages.addWidget(widget)

    def page(self, text: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(text))
        layout.addStretch()
        return widget

    def general_page(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        layout.addWidget(QLabel(f"<b>{tr('General')}</b>"))
        form = QFormLayout()
        self.language_combo = QComboBox()
        self.language_combo.addItem("English", "en")
        self.language_combo.addItem("Русский", "ru")
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(selected_language())))
        form.addRow(tr("Language"), self.language_combo)
        layout.addLayout(form)
        self.restart_note = QLabel(tr("Restart SlopeForge to apply the language change."))
        self.restart_note.setWordWrap(True)
        self.restart_note.hide()
        layout.addWidget(self.restart_note)
        self.language_combo.currentIndexChanged.connect(self._language_changed)
        if self.context:
            logout = QPushButton(tr("Sign out on this computer"))
            logout.clicked.connect(self.sign_out)
            revoke_all = QPushButton(tr("End all my saved sessions"))
            revoke_all.clicked.connect(self.revoke_my_sessions)
            layout.addWidget(logout)
            layout.addWidget(revoke_all)
        layout.addStretch()
        return widget

    def _language_changed(self) -> None:
        save_language(self.language_combo.currentData())
        self.restart_note.show()

    def sign_out(self) -> None:
        if self.context:
            RememberTokenService(self.context.session_factory).revoke_local()
        self.accept()

    def revoke_my_sessions(self) -> None:
        if self.context:
            RememberTokenService(self.context.session_factory).revoke_all_for_user(self.context.current_user.id)
        self.accept()

    def about_page(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        icon_label = QLabel()
        icon_path = resource_path(APP_ICON_PATH)
        if icon_path is not None:
            pixmap = QPixmap(str(icon_path))
            if not pixmap.isNull():
                icon_label.setPixmap(pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        layout.addWidget(icon_label)
        layout.addWidget(QLabel(f"<b>{APP_NAME}</b>"))
        layout.addWidget(QLabel(f"{tr('Version')}: {APP_VERSION}"))
        layout.addWidget(QLabel(f"{tr('Author')}: {APP_AUTHOR}"))
        description = QLabel(tr(APP_DESCRIPTION))
        description.setWordWrap(True)
        layout.addWidget(description)
        repository = QLabel(f'<a href="{APP_REPOSITORY_URL}">{APP_REPOSITORY_URL}</a>')
        repository.setOpenExternalLinks(True)
        layout.addWidget(repository)
        layout.addWidget(QLabel(APP_COPYRIGHT))
        close_button = QPushButton(tr("Close"))
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addStretch()
        return widget
