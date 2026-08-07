from PySide6.QtWidgets import QMainWindow,QMessageBox,QStackedWidget,QVBoxLayout,QHBoxLayout,QWidget
from app.config import APP_NAME,APP_VERSION
from app.qt import apply_window_icon
from database.app_context import AppContext
from repositories.domain_repository import DomainRepository
from repositories.project_lines_repository import ProjectLinesRepository
from services.project_service import ProjectService
from ui.header import Header
from ui.pages.block_list_page import BlockListPage
from widgets.project_tree import ProjectTree

class MainWindow(QMainWindow):
    def __init__(self, context: AppContext):
        super().__init__(); self.context=context; self.setWindowTitle(f"{APP_NAME} — {APP_VERSION}"); apply_window_icon(self); self.resize(1600,900)
        self.selected_site_id=None; self.selected_site_name=None; self.selected_domain_id=None; self.selected_domain_name=None; self.selected_block_id=None; self.selected_assessment_area_id=None
        self.assessment_page=None; self.assessment_domain_id=None; self.assessment_site_id=None
        self.tree=ProjectTree(context); self.tree.setMaximumWidth(320); self.block_page=BlockListPage(context); self.page=self.block_page; self.page_stack=QStackedWidget(); self.page_stack.addWidget(self.block_page)
        self.header=Header(context); self.domain_repo=DomainRepository(context.session_factory); self.project_service=ProjectService(context.session_factory); self.lines_repo=ProjectLinesRepository(context.session_factory)
        self.tree.site_selected.connect(self.select_site); self.tree.domain_selected.connect(self.select_domain); self.tree.block_selected.connect(self.open_block_from_tree); self.tree.assessment_area_selected.connect(self.open_area_from_tree); self.tree.project_lines_selected.connect(self.open_project_lines)
        self.header.add_mine_requested.connect(self._add_mine); self.header.add_domain_requested.connect(self._add_domain); self.header.add_block_requested.connect(self._add_block); self.header.add_assessment_area_requested.connect(self._add_area)
        self.block_page.data_changed.connect(self.refresh_project_data)
        central=QWidget(); self.setCentralWidget(central); root=QVBoxLayout(central); root.addWidget(self.header); body=QHBoxLayout(); body.addWidget(self.tree,1); body.addWidget(self.page_stack,4); root.addLayout(body); self._update_add()
    def _show(self,page):
        if not self._guard_leave(): return False
        if self.page_stack.indexOf(page)<0: self.page_stack.addWidget(page)
        self.page_stack.setCurrentWidget(page); return True
    def _guard_leave(self):
        page=self.assessment_page
        if page is None or self.page_stack.currentWidget() is not page: return True
        if page.has_active_workflow():
            answer=QMessageBox.warning(self,"Несохранённая геометрия","Имеются несохранённые изменения геометрии.",QMessageBox.StandardButton.Cancel|QMessageBox.StandardButton.Discard,QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Discard: return False
            page.cancel_active_workflow()
        try: page.save_now(); return True
        except Exception as exc: QMessageBox.critical(self,"Ошибка сохранения",f"Не удалось сохранить данные.\n\n{exc}"); return False
    def _set_context(self,site_id,site_name=None,domain_id=None,domain_name=None,block_id=None,area_id=None):
        self.selected_site_id=site_id; self.selected_site_name=site_name or self.selected_site_name; self.selected_domain_id=domain_id; self.selected_domain_name=domain_name; self.selected_block_id=block_id; self.selected_assessment_area_id=area_id; self._update_add()
    def _update_add(self):
        active=bool(self.selected_site_id and self.lines_repo.get_active(self.selected_site_id)); self.header.update_add_availability(self.selected_site_id is not None,self.selected_domain_id is not None,active)
    def select_site(self,site_id,site_name):
        from ui.pages.navigation_pages import SiteDashboardPage
        page=SiteDashboardPage(site_name)
        if self._show(page): self._set_context(site_id,site_name)
    def select_domain(self,domain_id,domain_name,site_id,site_name):
        from ui.pages.navigation_pages import DomainDashboardPage
        page=DomainDashboardPage(domain_name)
        if self._show(page): self._set_context(site_id,site_name,domain_id,domain_name)
    def open_project_lines(self,site_id,site_name):
        from ui.pages.navigation_pages import ProjectLinesPage
        page=ProjectLinesPage(self.context,site_id,site_name)
        if self._show(page): self._set_context(site_id,site_name)
    def open_block_from_tree(self,block_id,domain_id=None,site_id=None):
        domain=self.domain_repo.get(domain_id) if domain_id else None
        if self._show(self.block_page): self.block_page.open_block_id(block_id); self._set_context(site_id,domain.site.name if domain else None,domain_id,domain.name if domain else None,block_id); return True
        return False
    def _assessment(self,domain_id,domain_name,site_id):
        if self.assessment_page is not None and self.assessment_domain_id==domain_id: return self.assessment_page
        if not self._guard_leave(): return None
        from ui.pages.assessment_workspace_page import AssessmentWorkspacePage
        old=self.assessment_page; page=AssessmentWorkspacePage(self.context,domain_id,domain_name,site_id,parent=self.page_stack); self.page_stack.addWidget(page); self.assessment_page=page; self.assessment_domain_id=domain_id; self.assessment_site_id=site_id
        if old is not None: self.page_stack.removeWidget(old); old.deleteLater()
        return page
    def open_area_from_tree(self,area_id,domain_id,site_id,domain_name):
        page=self._assessment(domain_id,domain_name,site_id)
        if page is None:return False
        self.page_stack.setCurrentWidget(page); page.open_assessment_area(area_id); domain=self.domain_repo.get(domain_id); self._set_context(site_id,domain.site.name,domain_id,domain_name,area_id=area_id); return True
    def _add_mine(self):
        from ui.add_dialog import AddDialog
        d=AddDialog("mine / quarry")
        if d.exec(): self.project_service.create_project(d.name.text(),d.description.toPlainText()); self.refresh_project_data()
    def _add_domain(self):
        if self.selected_site_id is None:return
        from ui.add_dialog import AddDialog
        d=AddDialog("domain")
        if d.exec(): self.domain_repo.create(self.selected_site_id,d.name.text(),d.description.toPlainText()); self.refresh_project_data()
    def _add_block(self):
        if self.selected_domain_id is not None: self.block_page.create_block(self.selected_domain_id); self.refresh_project_data()
    def _add_area(self):
        if self.selected_domain_id is None or not self.lines_repo.get_active(self.selected_site_id):return
        page=self._assessment(self.selected_domain_id,self.selected_domain_name,self.selected_site_id)
        if page is not None: self.page_stack.setCurrentWidget(page); page.workspace.start_area_drawing()
    def refresh_project_data(self): self.tree.load_data(); self._update_add()
    def closeEvent(self,event):
        if not self._guard_leave(): event.ignore(); return
        super().closeEvent(event)
