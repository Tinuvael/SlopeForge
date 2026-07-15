from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QTabWidget
)


class BlockPage(QWidget):

    def __init__(self):
        super().__init__()

        layout = QVBoxLayout(self)

        title = QLabel("Block 24-017")

        title.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
        """)

        layout.addWidget(title)

        tabs = QTabWidget()

        tabs.addTab(QWidget(), "General information")
        tabs.addTab(QWidget(), "Geomechanics")
        tabs.addTab(QWidget(), "Blast design")
        tabs.addTab(QWidget(), "Blast execution")
        tabs.addTab(QWidget(), "Documents")
        tabs.addTab(QWidget(), "History")

        layout.addWidget(tabs)
