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
        self.tree.site_selected.connect(self.select_site); self.tree.domain_selected.connect(self.select_domain); self.tree.block_selected.connect(self.open_block_from_tree); self.tree.assessment_area_selected.connect(self.open_area_from_tree)
        self.header.add_mine_requested.connect(self._add_mine); self.header.add_domain_requested.connect(self._add_domain); self.header.add_block_requested.connect(self._add_block); self.header.add_assessment_area_requested.connect(self._add_area)
        self.header.archive_requested.connect(self._archive_selected)
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
        self.selected_site_id=site_id; self.selected_site_name=site_name or self.selected_site_name; self.selected_domain_id=domain_id; self.selected_domain_name=domain_name; self.selected_block_id=block_id; self.selected_assessment_area_id=area_id; self._update_add(); self.header.set_archive_context(area_id is not None)
    def _update_add(self):
        active=bool(self.selected_site_id and self.lines_repo.get_active(self.selected_site_id)); self.header.update_add_availability(self.selected_site_id is not None,self.selected_domain_id is not None,active)
    def select_site(self,site_id,site_name):
        from ui.pages.navigation_pages import SiteDashboardPage
        page=SiteDashboardPage(self.context,site_id,site_name)
        if self._show(page): self._set_context(site_id,site_name)
    def select_domain(self,domain_id,domain_name,site_id,site_name):
        from ui.pages.navigation_pages import DomainDashboardPage
        page=DomainDashboardPage(domain_name)
        if self._show(page): self._set_context(site_id,site_name,domain_id,domain_name)
    def open_block_from_tree(self,block_id,domain_id=None,site_id=None):
        domain=self.domain_repo.get(domain_id) if domain_id else None
        if self._show(self.block_page):
            self.block_page.open_block_id(block_id); self._set_context(site_id,domain.site.name if domain else None,domain_id,domain.name if domain else None,block_id); self.header.set_archive_context(True,self.block_page.current_block.is_archived); return True
        return False
    def open_area_from_tree(self,area_id,domain_id,site_id,domain_name):
        from ui.pages.assessment_area_page import AssessmentAreaPage
        page=AssessmentAreaPage(self.context,domain_id,domain_name,area_id,self.page_stack)
        page.edit_boundaries_requested.connect(self._edit_area_boundaries)
        if not self._show(page):return False
        domain=self.domain_repo.get(domain_id); self.area_page=page; self._set_context(site_id,domain.site.name,domain_id,domain_name,area_id=area_id); return True
    def _add_mine(self):
        from ui.project_dialog import ProjectDialog
        from prototype_2d.domain import AssessmentDomainState
        from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService
        d=ProjectDialog(self)
        if not d.exec(): return
        dataset=None
        try:
            if d.csv_path.text(): dataset,_=ProjectLinesDatasetService(AssessmentDomainState()).import_dataset(d.csv_path.text())
            site_id=self.project_service.create_project(d.name.text(),d.description.toPlainText())
            if dataset:
                try: self.lines_repo.import_dataset(site_id,dataset,make_active=True)
                except Exception as exc:
                    QMessageBox.warning(self,"Проект создан без линий",f"Проект создан, но линии не сохранены: {exc}\nПовторите импорт на странице проекта.")
            self.refresh_project_data(); self.select_site(site_id,d.name.text())
        except Exception as exc: QMessageBox.warning(self,"Не удалось создать проект",str(exc))
    def _add_domain(self):
        if self.selected_site_id is None:return
        from ui.add_dialog import AddDialog
        d=AddDialog("domain")
        if d.exec(): self.domain_repo.create(self.selected_site_id,d.name.text(),d.description.toPlainText()); self.refresh_project_data()
    def _add_block(self):
        if self.selected_domain_id is None:return
        from ui.pages.entity_page_controller import EntityPageController
        from prototype_2d.blast_event_service import BlastEventService
        controller=EntityPageController(self.context,self.selected_domain_id); event_service=BlastEventService(controller.state)
        from ui.prototype_2d.assessment_workspace import BlastEventDialog
        dialog=BlastEventDialog(self,event_service); dialog.kind.setCurrentText("production"); dialog.kind.setEnabled(False)
        if not dialog.exec():return
        event=None; block_id=None
        try:
            event=event_service.create_event(**dialog.values())
            from services.blast_block_service import BlastBlockInput
            block_id=self.block_page.block_service.create_block(BlastBlockInput(self.selected_domain_id,event.name,str(event.elevation),event.event_date,"planned",None),self.context.current_user)
            event.blast_block_id=block_id
            controller.save()
            self.refresh_project_data(); self.open_block_from_tree(block_id,self.selected_domain_id,self.selected_site_id)
        except Exception as exc:
            if event in controller.state.blast_events:
                controller.state.blast_events.remove(event)
                try: controller.save()
                except Exception: pass
            if block_id:
                from database.models import BlastBlock
                with self.context.session_factory.begin() as session:
                    row=session.get(BlastBlock,block_id)
                    if row: session.delete(row)
            QMessageBox.warning(self,"Не удалось создать блок",str(exc))
    def _add_area(self):
        if self.selected_domain_id is None:return
        if not self.lines_repo.get_active(self.selected_site_id):
            QMessageBox.information(self,"Проектные линии","Сначала загрузите проектные линии для карьера."); self.select_site(self.selected_site_id,self.selected_site_name); return
        from ui.pages.assessment_area_creation_page import AssessmentAreaCreationPage
        page=AssessmentAreaCreationPage(self.context,self.selected_domain_id,self.selected_domain_name,self.selected_site_id,self.page_stack)
        page.area_created.connect(lambda area_id:self._area_created(area_id,page)); page.cancelled.connect(lambda:self.select_domain(self.selected_domain_id,self.selected_domain_name,self.selected_site_id,self.selected_site_name))
        if self._show(page): self.assessment_page=page; self.assessment_domain_id=self.selected_domain_id; self.page_stack.setCurrentWidget(page)
    def _area_created(self,area_id,creation_page):
        self.assessment_page=None; self.refresh_project_data(); self.open_area_from_tree(area_id,self.selected_domain_id,self.selected_site_id,self.selected_domain_name); self.page_stack.removeWidget(creation_page); creation_page.deleteLater()
    def _edit_area_boundaries(self,area_id):
        from ui.pages.assessment_area_creation_page import AssessmentAreaCreationPage
        page=AssessmentAreaCreationPage(self.context,self.selected_domain_id,self.selected_domain_name,self.selected_site_id,self.page_stack,edit_area_id=area_id)
        page.area_created.connect(lambda _ignored:self.open_area_from_tree(area_id,self.selected_domain_id,self.selected_site_id,self.selected_domain_name)); page.cancelled.connect(lambda:self.open_area_from_tree(area_id,self.selected_domain_id,self.selected_site_id,self.selected_domain_name)); self.assessment_page=page; self.page_stack.addWidget(page); self.page_stack.setCurrentWidget(page)
    def _archive_selected(self):
        if self.selected_block_id is not None:
            block=self.block_page.current_block; action="восстановить" if block.is_archived else "архивировать"
            if QMessageBox.question(self,"Archive",f"{action.capitalize()} Block {block.block_number}?") != QMessageBox.StandardButton.Yes:return
            self.block_page.block_service.set_archived(block.id,not block.is_archived,self.context.current_user); self.selected_block_id=None; self.header.set_archive_context(False); self.refresh_project_data(); return
        if self.selected_assessment_area_id and getattr(self,"area_page",None):
            area=self.area_page.area; area.restore() if area.is_archived else area.archive(); self.area_page.controller.save(); self.header.set_archive_context(False); self.refresh_project_data()
    def refresh_project_data(self): self.tree.load_data(); self._update_add()
    def closeEvent(self,event):
        if not self._guard_leave(): event.ignore(); return
        super().closeEvent(event)
