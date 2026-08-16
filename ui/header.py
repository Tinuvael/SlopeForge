
from app.localization import tr
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLineEdit, QMenu, QPushButton, QWidget
from ui.settings_dialog import SettingsDialog
from app.icons.ui.ui_icons import ui_icon
class SearchLineEdit(QLineEdit):
    """Header-only search behavior; Escape remains untouched elsewhere."""
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.clear()
            event.accept()
            return
        super().keyPressEvent(event)

class Header(QWidget):
    add_project_requested=Signal(); add_domain_requested=Signal(); add_blast_event_requested=Signal(); add_assessment_area_requested=Signal(); archive_requested=Signal(); report_requested=Signal(); navigation_toggle_requested=Signal()
    def __init__(self, context):
        super().__init__(); self.context=context; self.setFixedHeight(60); layout=QHBoxLayout(self)
        # Use a normal QPushButton so the navigation control has the same native
        # border/hover/focus treatment as Add and Archive on Windows.
        self.navigation_button=QPushButton(); self.navigation_button.setObjectName("navigationToggleButton"); self.navigation_button.setFixedSize(36,32); self.navigation_button.clicked.connect(self.navigation_toggle_requested); self.set_navigation_visible(True)
        self.add_button=QPushButton(tr("Add")); self.add_menu=QMenu(self)
        self.add_project_action=self.add_menu.addAction(tr("Add project")); self.add_domain_action=self.add_menu.addAction(tr("Add domain")); self.add_blast_event_action=self.add_menu.addAction(tr("Add blast event")); self.add_assessment_area_action=self.add_menu.addAction(tr("Add assessment area"))
        self.add_button.setIcon(ui_icon("add","blue")); self.add_project_action.setIcon(ui_icon("mine")); self.add_domain_action.setIcon(ui_icon("domain")); self.add_blast_event_action.setIcon(ui_icon("blast-blocks")); self.add_assessment_area_action.setIcon(ui_icon("assessment-area"))
        self.add_button.setToolTip(tr("Create a project, domain, blast event, or assessment area"))
        self.add_project_action.triggered.connect(self.add_project_requested); self.add_domain_action.triggered.connect(self.add_domain_requested); self.add_blast_event_action.triggered.connect(self.add_blast_event_requested); self.add_assessment_area_action.triggered.connect(self.add_assessment_area_requested)
        self.add_button.setMenu(self.add_menu); self.archive_button=QPushButton(tr("Archive")); self.archive_button.setEnabled(False); self.archive_button.clicked.connect(self.archive_requested)
        self.archive_button.setIcon(ui_icon("archive")); self.search=SearchLineEdit(); self.search.setClearButtonEnabled(True); self.search.setPlaceholderText(tr("Search...")); self.search.setMaximumWidth(350); self.report_button=QPushButton(tr("Report")); self.report_button.setEnabled(False); self.report_button.clicked.connect(self.report_requested); self.settings=QPushButton(tr("Settings")); self.settings.setIcon(ui_icon("settings")); self.settings.clicked.connect(self.open_settings)
        self.search_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        self.search_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        self.search_shortcut.activated.connect(self.focus_search)
        layout.addWidget(self.navigation_button); layout.addWidget(self.add_button); layout.addWidget(self.archive_button); layout.addStretch(); layout.addWidget(self.search); layout.addStretch(); layout.addWidget(self.report_button); layout.addWidget(self.settings); self.update_add_availability(False,False,False)
    def update_add_availability(self, has_site, has_domain, has_active_dataset):
        self.report_button.setEnabled(has_site)
        editable=self.context.current_user.can_edit; self.add_button.setEnabled(editable); self.add_project_action.setEnabled(editable); self.add_domain_action.setEnabled(editable and has_site); self.add_blast_event_action.setEnabled(editable and has_domain); self.add_assessment_area_action.setEnabled(editable and has_domain and has_active_dataset)
    def set_archive_context(self, enabled, archived=False):
        self.archive_button.setEnabled(self.context.current_user.can_edit and enabled); self.archive_button.setText(tr("Restore") if archived else tr("Archive")); self.archive_button.setIcon(ui_icon("restore" if archived else "archive"))
    def set_navigation_visible(self, visible):
        self.navigation_button.setIcon(ui_icon("hide" if visible else "eye"))
        self.navigation_button.setToolTip(tr("Hide navigation") if visible else tr("Show navigation"))
        self.navigation_button.setAccessibleName(self.navigation_button.toolTip())
    def open_settings(self): SettingsDialog(self.context,self).exec()
    def focus_search(self):
        self.search.setFocus(Qt.FocusReason.ShortcutFocusReason)
        self.search.selectAll()