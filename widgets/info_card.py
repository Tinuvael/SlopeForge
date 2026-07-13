from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout
)


class InfoCard(QFrame):

    def __init__(self, title):

        super().__init__()

        self.setFrameShape(QFrame.Box)

        layout = QVBoxLayout(self)

        self.title = QLabel(title)

        self.title.setStyleSheet("""
            font-size:16px;
            font-weight:bold;
        """)

        layout.addWidget(self.title)
