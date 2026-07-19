from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton
)

from app.config import APP_NAME, APP_VERSION
from app.qt import apply_window_icon
from widgets.project_tree import ProjectTree
from ui.pages.block_list_page import BlockListPage
from ui.header import Header
from ui.prototype_2d.window import Prototype2DWindow
from database.app_context import AppContext


class MainWindow(QMainWindow):

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context

        self.setWindowTitle(f"{APP_NAME} — {APP_VERSION}")
        apply_window_icon(self)
        self.resize(1600, 900)

        self.tree = ProjectTree(context)
        self.tree.setMaximumWidth(320)

        self.page = BlockListPage(context)
        self.tree.filters_changed.connect(self.page.set_filters)
        self.tree.block_selected.connect(self.page.open_block_id)
        self.page.data_changed.connect(self.refresh_project_data)

        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        header = Header(context)
        header.create_block_requested.connect(self.page.create_block)
        header.directories_requested.connect(self.page.open_directories)
        prototype_button = QPushButton("2D Plan Prototype")
        prototype_button.clicked.connect(self.open_2d_plan_prototype)
        header_layout = QHBoxLayout()
        header_layout.addWidget(header, 1)
        header_layout.addWidget(prototype_button)
        main_layout.addLayout(header_layout)

        content = QWidget()
        content_layout = QHBoxLayout(content)

        content_layout.addWidget(self.tree, 1)
        content_layout.addWidget(self.page, 4)

        main_layout.addWidget(content)


    def refresh_project_data(self) -> None:
        self.tree.reload_filters()
        self.tree.load_data()


    def open_2d_plan_prototype(self) -> None:
        existing = getattr(self, "prototype_2d_window", None)
        if existing is not None:
            existing.showNormal()
            existing.raise_()
            existing.activateWindow()
            return
        self.prototype_2d_window = Prototype2DWindow(self)
        self.prototype_2d_window.closed.connect(self._prototype_2d_closed)
        self.prototype_2d_window.show()


    def _prototype_2d_closed(self) -> None:
        self.prototype_2d_window = None
