from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit

from app.localization import tr
from ui.widgets.design_system import (
    configure_standard_dialog, create_form_section, set_button_role, standard_dialog_actions,
)


class ProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Create Project"))
        root = configure_standard_dialog(self, minimum_width=550)

        general, form = create_form_section("General", self)
        self.name = QLineEdit()
        self.name.setMaxLength(255)
        self.description = QTextEdit()
        self.description.setMaximumHeight(82)
        self.description.setTabChangesFocus(True)
        form.addRow(tr("Name"), self.name)
        form.addRow(tr("Description"), self.description)
        root.addWidget(general)

        lines, lines_form = create_form_section("Project Lines", self)
        self.csv_path = QLineEdit()
        self.csv_path.setReadOnly(True)
        self.csv_path.setPlaceholderText(tr("No file selected"))
        self.csv_path.setToolTip(tr("No file selected"))
        self.browse_button = set_button_role(QPushButton(tr("Browse...")), "secondary")
        icon = Path(__file__).resolve().parent.parent / "app/icons/ui/svg/blue/folder-open.svg"
        self.browse_button.setIcon(QIcon(str(icon)))
        self.browse_button.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.csv_path, 1)
        row.addWidget(self.browse_button)
        lines_form.addRow(tr("Project Lines file"), row)
        helper = QLabel(tr("Project Lines can also be imported later from the Project dashboard."))
        helper.setObjectName("FormHelperText")
        helper.setWordWrap(True)
        lines.layout.addWidget(helper)
        root.addWidget(lines)

        actions, self.cancel_button, self.create_button = standard_dialog_actions(self, "Create")
        root.addWidget(actions)
        self.name.setFocus()

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Select Project Lines file"), "",
            tr("Project Lines (*.csv *.dxf);;Datamine CSV (*.csv);;AutoCAD DXF (*.dxf)"),
        )
        if path:
            self.csv_path.setText(path)
            self.csv_path.setToolTip(path)
