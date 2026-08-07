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
from database.app_context import AppContext


class MainWindow(QMainWindow):

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.assessment_page = None
        self.assessment_domain_id: int | None = None
        self.assessment_domain_name: str | None = None
        self.assessment_site_id: int | None = None
        self.assessment_site_name: str | None = None

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
        self.tree.site_selected.connect(self.select_site)
        self.tree.domain_selected.connect(self.open_assessment_for_domain)
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
        self.assessment_nav_button.setEnabled(False)
        self.assessment_nav_button.setToolTip(
            "Выберите площадку/домен в дереве проекта"
        )
        self.navigation_group = QButtonGroup(self)
        self.navigation_group.setExclusive(True)
        self.navigation_group.addButton(self.block_nav_button)
        self.navigation_group.addButton(self.assessment_nav_button)
        self.block_nav_button.setChecked(True)
        self.block_nav_button.clicked.connect(self.show_block_page)
        self.assessment_nav_button.clicked.connect(self.show_assessment_page)

        header_layout = QHBoxLayout()
        header_layout.addWidget(self.header, 1)
        header_layout.addWidget(self.block_nav_button)
        header_layout.addWidget(self.assessment_nav_button)
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

    def _construct_assessment_page(self, domain_id: int, domain_name: str | None, site_id: int):
        try:
            # Keep the assessment dependency graph out of normal block-app startup.
            from ui.pages.assessment_workspace_page import AssessmentWorkspacePage

            return AssessmentWorkspacePage(
                self.context, domain_id, domain_name, site_id, parent=self.page_stack
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Ошибка загрузки 2D Assessment",
                f"Не удалось загрузить данные 2D Assessment.\n\n{exc}",
            )
            self._sync_navigation_buttons()
            return None

    def show_assessment_page(self) -> bool:
        if self.assessment_domain_id is None or self.assessment_site_id is None:
            self.page_stack.setCurrentWidget(self.block_page)
            self._sync_navigation_buttons()
            return False
        return self.open_assessment_for_domain(
            self.assessment_domain_id, self.assessment_domain_name or "", self.assessment_site_id
        )

    def select_site(self, site_id: int, site_name: str) -> None:
        """Select Site context without guessing or opening a Domain workspace."""
        if self.assessment_site_id != site_id:
            self.assessment_domain_id = None
            self.assessment_domain_name = None
            self.assessment_nav_button.setEnabled(False)
            self.assessment_nav_button.setToolTip("Выберите домен в дереве проекта")
            self.page_stack.setCurrentWidget(self.block_page)
            self._sync_navigation_buttons()
            return
        self.assessment_nav_button.setEnabled(self.assessment_domain_id is not None)

    def open_assessment_for_domain(self, domain_id: int, domain_name: str, site_id: int) -> bool:
        if self.assessment_page is not None and domain_id == self.assessment_domain_id:
            page = self.assessment_page
            if self.page_stack.currentWidget() is page:
                try:
                    page.refresh_workspace()
                except Exception as exc:
                    QMessageBox.critical(
                        self, "Ошибка обновления 2D Assessment",
                        f"Не удалось обновить данные 2D Assessment.\n\n{exc}",
                    )
                    self._sync_navigation_buttons()
                    return False
                self._sync_navigation_buttons()
                return True
            if page.has_active_workflow():
                QMessageBox.warning(
                    self, "Несохранённая геометрия",
                    "Завершите или отмените активное редактирование геометрии перед обновлением домена.",
                )
                self.page_stack.setCurrentWidget(self.block_page)
                self._sync_navigation_buttons()
                return False
            try:
                page.reload_from_repository()
            except Exception as exc:
                QMessageBox.critical(
                    self, "Ошибка загрузки 2D Assessment",
                    f"Не удалось обновить данные 2D Assessment из PostgreSQL.\n\n{exc}",
                )
                self.page_stack.setCurrentWidget(self.block_page)
                self._sync_navigation_buttons()
                return False
            self.page_stack.setCurrentWidget(page)
            self._sync_navigation_buttons()
            return True

        old_page = self.assessment_page
        if old_page is not None and not self._prepare_assessment_for_site_switch():
            return False

        page = self._construct_assessment_page(domain_id, domain_name, site_id)
        if page is None:
            return False
        self.page_stack.addWidget(page)
        self.page_stack.setCurrentWidget(page)
        self.assessment_page = page
        self.assessment_domain_id = domain_id
        self.assessment_domain_name = domain_name
        self.assessment_site_id = site_id
        self.assessment_nav_button.setEnabled(True)
        self.assessment_nav_button.setToolTip("")
        if old_page is not None:
            self.page_stack.removeWidget(old_page)
            old_page.deleteLater()
        self._sync_navigation_buttons()
        return True

    def _prepare_assessment_for_site_switch(self) -> bool:
        """Guard and persist the old Site before constructing another Site page."""
        page = self.assessment_page
        if page is None:
            return True
        if page.has_active_workflow():
            answer = QMessageBox.warning(
                self, "Несохранённая геометрия",
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
                self, "Ошибка сохранения",
                f"Не удалось сохранить данные. Текущий домен останется открытым.\n\n{exc}",
            )
            self._sync_navigation_buttons()
            return False
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
