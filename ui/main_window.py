from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QLabel
)

from widgets.project_tree import ProjectTree
from ui.pages.block_list_page import BlockListPage
from ui.header import Header
from database.app_context import AppContext


class MainWindow(QMainWindow):

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context

        self.setWindowTitle("SlopeForge")
        self.resize(1600, 900)

        self.tree = ProjectTree()
        self.tree.setMaximumWidth(320)

        self.page = BlockListPage(context)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        header = Header()
        main_layout.addWidget(header)

        if context.db_mode == "sqlite-dev":
            warning = QLabel("SQLite development mode — не использовать для рабочих данных")
            warning.setStyleSheet("background:#8B0000;color:white;font-weight:bold;padding:8px;")
            main_layout.addWidget(warning)

        content = QWidget()
        content_layout = QHBoxLayout(content)

        content_layout.addWidget(self.tree, 1)
        content_layout.addWidget(self.page, 4)

        main_layout.addWidget(content)

