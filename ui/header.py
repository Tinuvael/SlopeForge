from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QMenu, QPushButton, QWidget
from ui.settings_dialog import SettingsDialog
from app.icons.ui.ui_icons import ui_icon
class Header(QWidget):
    add_mine_requested=Signal(); add_domain_requested=Signal(); add_blast_event_requested=Signal(); add_assessment_area_requested=Signal(); archive_requested=Signal()
    def __init__(self, context):
        super().__init__(); self.context=context; self.setFixedHeight(60); layout=QHBoxLayout(self)
        self.add_button=QPushButton("Add ▼"); self.add_menu=QMenu(self)
        self.add_mine_action=self.add_menu.addAction("Add mine"); self.add_domain_action=self.add_menu.addAction("Add domain"); self.add_blast_event_action=self.add_menu.addAction("Add blast event"); self.add_assessment_area_action=self.add_menu.addAction("Add assessment area")
        self.add_button.setIcon(ui_icon("add","blue")); self.add_mine_action.setIcon(ui_icon("mine")); self.add_domain_action.setIcon(ui_icon("domain")); self.add_blast_event_action.setIcon(ui_icon("blast-blocks")); self.add_assessment_area_action.setIcon(ui_icon("assessment-area"))
        self.add_mine_action.triggered.connect(self.add_mine_requested); self.add_domain_action.triggered.connect(self.add_domain_requested); self.add_blast_event_action.triggered.connect(self.add_blast_event_requested); self.add_assessment_area_action.triggered.connect(self.add_assessment_area_requested)
        self.add_button.setMenu(self.add_menu); self.archive_button=QPushButton("Archive"); self.archive_button.setEnabled(False); self.archive_button.clicked.connect(self.archive_requested)
        self.archive_button.setIcon(ui_icon("archive")); self.search=QLineEdit(); self.search.setPlaceholderText("Search (Ctrl+F)"); self.search.setMaximumWidth(350); self.settings=QPushButton("Settings"); self.settings.setIcon(ui_icon("settings")); self.settings.clicked.connect(self.open_settings)
        layout.addWidget(self.add_button); layout.addWidget(self.archive_button); layout.addStretch(); layout.addWidget(self.search); layout.addStretch(); layout.addWidget(self.settings); self.update_add_availability(False,False,False)
    def update_add_availability(self, has_site, has_domain, has_active_dataset):
        editable=self.context.current_user.can_edit; self.add_button.setEnabled(editable); self.add_mine_action.setEnabled(editable); self.add_domain_action.setEnabled(editable and has_site); self.add_blast_event_action.setEnabled(editable and has_domain); self.add_assessment_area_action.setEnabled(editable and has_domain and has_active_dataset)
    def set_archive_context(self, enabled, archived=False):
        self.archive_button.setEnabled(self.context.current_user.can_edit and enabled); self.archive_button.setText("Restore" if archived else "Archive"); self.archive_button.setIcon(ui_icon("restore" if archived else "archive"))
    def open_settings(self): SettingsDialog(self.context,self).exec()
