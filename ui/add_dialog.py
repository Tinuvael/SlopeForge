from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QTextEdit

from app.localization import tr
from ui.widgets.design_system import configure_standard_dialog, create_form_section, standard_dialog_actions


class AddDialog(QDialog):
    """Active compact Domain creator; public field contract is retained."""

    def __init__(self, item_type: str, parent=None):
        super().__init__(parent)
        self.item_type = item_type
        title = tr("Create Domain") if item_type.lower() == "domain" else tr(f"Create {item_type}")
        self.setWindowTitle(title)
        root = configure_standard_dialog(self, minimum_width=520)
        heading = QLabel(title); heading.setObjectName("EntityTitle"); root.addWidget(heading)
        if item_type.lower() == "domain":
            subtitle = QLabel(tr("Create a working domain for blast events and assessment areas."))
            subtitle.setObjectName("MutedText"); subtitle.setWordWrap(True); root.addWidget(subtitle)
        general, form = create_form_section("Domain details" if item_type.lower() == "domain" else "General", self)
        self.name = QLineEdit()
        self.name.setPlaceholderText(tr("Domain name") if item_type.lower() == "domain" else tr(f"{item_type} name"))
        self.description = QTextEdit()
        self.description.setMaximumHeight(82)
        self.description.setTabChangesFocus(True)
        form.addRow(tr("Name"), self.name)
        form.addRow(tr("Description"), self.description)
        if item_type.lower() == "domain":
            note = QLabel(tr("Domain geometry can be imported or drawn from the Domain dashboard after creation."))
            note.setObjectName("FormHelperText"); note.setWordWrap(True); general.layout.addWidget(note)
        root.addWidget(general)
        actions, self.cancel_button, self.create_button = standard_dialog_actions(self, "Create")
        root.addWidget(actions)
        self.name.setFocus()
