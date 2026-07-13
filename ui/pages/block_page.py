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

        title = QLabel("Блок 24-017")

        title.setStyleSheet("""
            font-size:24px;
            font-weight:bold;
        """)

        layout.addWidget(title)

        tabs = QTabWidget()

        tabs.addTab(QWidget(), "Общая информация")
        tabs.addTab(QWidget(), "Геомеханика")
        tabs.addTab(QWidget(), "Проект БВР")
        tabs.addTab(QWidget(), "Факт отработки")
        tabs.addTab(QWidget(), "Документы")
        tabs.addTab(QWidget(), "История")

        layout.addWidget(tabs)
