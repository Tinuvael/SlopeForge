from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QLineEdit,
    QTextEdit,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
)


class AddDialog(QDialog):

    def __init__(self, item_type: str):
        super().__init__()

        self.item_type = item_type

        self.setWindowTitle(f"Create {item_type}")
        self.setFixedSize(420, 230)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Name"))

        self.name = QLineEdit()
        self.name.setPlaceholderText(f"{item_type} name...")
        layout.addWidget(self.name)

        layout.addWidget(QLabel("Description"))

        self.description = QTextEdit()
        self.description.setMaximumHeight(80)
        layout.addWidget(self.description)

        buttons = QHBoxLayout()

        buttons.addStretch()

        cancel = QPushButton("Cancel")
        create = QPushButton("Create")

        cancel.clicked.connect(self.reject)
        create.clicked.connect(self.accept)

        buttons.addWidget(cancel)
        buttons.addWidget(create)

        layout.addStretch()
        layout.addLayout(buttons)
