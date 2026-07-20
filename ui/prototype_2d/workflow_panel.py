from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget


class WorkflowPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMaximumHeight(160)
        layout = QVBoxLayout(self)
        self.title = QLabel("Workflow")
        self.step = QLabel()
        self.instruction = QLabel(); self.instruction.setWordWrap(True)
        self.summary = QTextEdit(); self.summary.setReadOnly(True); self.summary.setMaximumHeight(55)
        buttons = QHBoxLayout()
        self.back_button = QPushButton("Назад")
        self.cancel_button = QPushButton("Отмена")
        self.primary_button = QPushButton()
        buttons.addWidget(self.back_button); buttons.addWidget(self.cancel_button); buttons.addStretch(1); buttons.addWidget(self.primary_button)
        for item in (self.title, self.step, self.instruction, self.summary): layout.addWidget(item)
        layout.addLayout(buttons)
