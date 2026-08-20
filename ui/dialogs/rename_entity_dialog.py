from PySide6.QtWidgets import QDialog, QLabel, QLineEdit

from app.localization import tr
from ui.widgets.design_system import configure_standard_dialog, create_form_section, standard_dialog_actions


class RenameEntityDialog(QDialog):
    """Compact Name-only editor shared by Project and Domain dashboards."""

    def __init__(self, entity: str, current_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Edit Project") if entity == "Project" else tr("Edit Domain"))
        root = configure_standard_dialog(self, minimum_width=420)
        general, form = create_form_section("General", self)
        self.name = QLineEdit(current_name)
        self.name.setMaxLength(255)
        self.name.selectAll()
        form.addRow(tr("Name"), self.name)
        self.error_label = QLabel()
        self.error_label.setObjectName("FormValidationText")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        general.layout.addWidget(self.error_label)
        root.addWidget(general)
        actions, self.cancel_button, self.save_button = standard_dialog_actions(
            self, "Save", accept=self._validate,
        )
        root.addWidget(actions)

    def _validate(self):
        name = self.name.text().strip()
        if not name:
            self.show_error(tr("Name is required"))
            return
        self.name.setText(name)
        self.error_label.hide()
        self.accept()

    def show_error(self, message: str):
        self.error_label.setText(message)
        self.error_label.show()
        self.name.setFocus()
