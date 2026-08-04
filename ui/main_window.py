from PySide6.QtWidgets import (
    QButtonGroup,
    QMainWindow,
    QMessageBox,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QPushButton,
    QStackedWidget,
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
        self.assessment_page = None

        self.setWindowTitle(f"{APP_NAME} — {APP_VERSION}")
        apply_window_icon(self)
        self.resize(1600, 900)

        self.tree = ProjectTree(context)
        self.tree.setMaximumWidth(320)

        self.block_page = BlockListPage(context)
        self.page = self.block_page  # compatibility alias
        self.page_stack = QStackedWidget()
        self.page_stack.addWidget(self.block_page)
        self.page_stack.setCurrentWidget(self.block_page)

        self.tree.filters_changed.connect(self.block_page.set_filters)
        self.tree.block_selected.connect(self.open_block_from_tree)
        self.block_page.data_changed.connect(self.refresh_project_data)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        self.header = Header(context)
        self.header.create_block_requested.connect(self._create_block)
        self.header.directories_requested.connect(self._open_directories)

        self.block_nav_button = QPushButton("Blast blocks")
        self.block_nav_button.setCheckable(True)
        self.assessment_nav_button = QPushButton("2D Assessment")
        self.assessment_nav_button.setCheckable(True)
        self.navigation_group = QButtonGroup(self)
        self.navigation_group.setExclusive(True)
        self.navigation_group.addButton(self.block_nav_button)
        self.navigation_group.addButton(self.assessment_nav_button)
        self.block_nav_button.setChecked(True)
        self.block_nav_button.clicked.connect(self.show_block_page)
        self.assessment_nav_button.clicked.connect(self.show_assessment_page)

        self.prototype_button = QPushButton("2D Plan Prototype")
        self.prototype_button.clicked.connect(self.open_2d_plan_prototype)
        header_layout = QHBoxLayout()
        header_layout.addWidget(self.header, 1)
        header_layout.addWidget(self.block_nav_button)
        header_layout.addWidget(self.assessment_nav_button)
        header_layout.addWidget(self.prototype_button)
        main_layout.addLayout(header_layout)

        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.addWidget(self.tree, 1)
        content_layout.addWidget(self.page_stack, 4)
        main_layout.addWidget(content)

    def _sync_navigation_buttons(self) -> None:
        assessment_visible = (
            self.assessment_page is not None
            and self.page_stack.currentWidget() is self.assessment_page
        )
        self.assessment_nav_button.setChecked(assessment_visible)
        self.block_nav_button.setChecked(not assessment_visible)

    def _ensure_assessment_page(self):
        if self.assessment_page is not None:
            return self.assessment_page
        try:
            # Keep the assessment dependency graph out of normal block-app startup.
            from ui.pages.assessment_workspace_page import AssessmentWorkspacePage

            page = AssessmentWorkspacePage(parent=self.page_stack)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка загрузки 2D Assessment",
                f"Не удалось загрузить данные 2D Assessment.\n\n{exc}",
            )
            self.page_stack.setCurrentWidget(self.block_page)
            self._sync_navigation_buttons()
            return None
        self.assessment_page = page
        self.page_stack.addWidget(page)
        return page

    def show_assessment_page(self) -> bool:
        previous_page = self.page_stack.currentWidget()
        page_was_created = self.assessment_page is None
        page = self._ensure_assessment_page()
        if page is None:
            return False
        try:
            page.refresh_workspace()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка обновления 2D Assessment",
                f"Не удалось обновить данные 2D Assessment.\n\n{exc}",
            )
            if page_was_created:
                self.page_stack.removeWidget(page)
                page.deleteLater()
                self.assessment_page = None
                self.page_stack.setCurrentWidget(self.block_page)
            else:
                self.page_stack.setCurrentWidget(previous_page)
            self._sync_navigation_buttons()
            return False
        self.page_stack.setCurrentWidget(page)
        self._sync_navigation_buttons()
        return True

    def _prepare_to_leave_assessment_workspace(self) -> bool:
        page = self.assessment_page
        if page is None or self.page_stack.currentWidget() is not page:
            return True
        if page.has_active_workflow():
            answer = QMessageBox.warning(
                self,
                "Несохранённая геометрия",
                "Имеются несохранённые изменения геометрии.",
                QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Discard,
                QMessageBox.StandardButton.Cancel,
            )
            if answer != QMessageBox.StandardButton.Discard:
                self._sync_navigation_buttons()
                return False
            page.cancel_active_workflow()
        try:
            page.save_now()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка сохранения",
                f"Не удалось сохранить данные. Страница 2D Assessment останется открытой.\n\n{exc}",
            )
            self._sync_navigation_buttons()
            return False
        return True

    def show_block_page(self) -> bool:
        if not self._prepare_to_leave_assessment_workspace():
            return False
        self.page_stack.setCurrentWidget(self.block_page)
        self._sync_navigation_buttons()
        return True

    def open_block_from_tree(self, block_id: int) -> bool:
        if not self.show_block_page():
            return False
        self.block_page.open_block_id(block_id)
        return True

    def _create_block(self) -> None:
        if self.show_block_page():
            self.block_page.create_block()

    def _open_directories(self) -> None:
        if self.show_block_page():
            self.block_page.open_directories()

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

    def closeEvent(self, event) -> None:
        page = self.assessment_page
        if page is not None:
            if page.has_active_workflow():
                answer = QMessageBox.warning(
                    self,
                    "Несохранённая геометрия",
                    "Имеются несохранённые изменения геометрии.",
                    QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Discard,
                    QMessageBox.StandardButton.Cancel,
                )
                if answer != QMessageBox.StandardButton.Discard:
                    event.ignore()
                    self._sync_navigation_buttons()
                    return
                page.cancel_active_workflow()
            try:
                page.save_now()
            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Ошибка сохранения",
                    f"Не удалось сохранить данные. Приложение останется открытым.\n\n{exc}",
                )
                event.ignore()
                self._sync_navigation_buttons()
                return
        super().closeEvent(event)
