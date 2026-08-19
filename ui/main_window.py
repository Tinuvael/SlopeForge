from __future__ import annotations
import logging, sys
from pathlib import Path
from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox, QStackedWidget
from app.localization import tr
from app.settings import StorageSettings
from application.commands.project import CreateDomainCommand, CreateProjectCommand
from application.commands.blasting import CreateBlastEventCommand
from application.use_cases.project import CreateDomainUseCase, CreateProjectUseCase
from application.use_cases.blasting import CreateBlastEventUseCase
from application.use_cases.archive import ArchiveActionUseCase
from application.services.app_context import AppContext
from domain.project.errors import ProjectError
from ui.header import AppHeader
from ui.widgets.project_tree import ProjectTreeWidget
from ui.presentation_labels import domain_message

logger=logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self,context:AppContext,storage_root=None):
        super().__init__();self.context=context;self.setWindowTitle(f"SlopeForge — {context.current_user.username}")
        self.navigation_queries=context.navigation_queries
        self.create_project=CreateProjectUseCase(context.session_factory);self.create_domain=CreateDomainUseCase(context.session_factory);self.create_blast_event=CreateBlastEventUseCase(context.session_factory)
        self.archive_action=ArchiveActionUseCase(context.session_factory)
        self.storage_root=storage_root or StorageSettings().storage_root
        from ui.shell import MainShell
        self.shell=MainShell();self.setCentralWidget(self.shell);self.header=AppHeader();self.shell.set_header(self.header);self.tree=ProjectTreeWidget(context);self.shell.set_sidebar(self.tree);self.page_stack=QStackedWidget();self.shell.set_content(self.page_stack)
        self.selected_site_id=None;self.selected_site_name=None;self.selected_domain_id=None;self.selected_domain_name=None;self.selected_block_id=None;self.selected_contour_event_id=None;self.selected_assessment_area_id=None
        self.block_page=None;self.contour_page=None;self.area_page=None;self.assessment_page=None;self.assessment_domain_id=None;self.assessment_site_id=None;self.analysis_page=None
        self._connect();self.refresh_project_data()
    def _connect(self):
        self.tree.site_selected.connect(self.select_site);self.tree.domain_selected.connect(self.select_domain);self.tree.block_selected.connect(self.open_block_from_tree);self.tree.contour_selected.connect(self.open_contour_from_tree);self.tree.area_selected.connect(self.open_area_from_tree)
        self.header.add_project_requested.connect(self._add_project);self.header.add_domain_requested.connect(self._add_domain);self.header.add_blast_event_requested.connect(self._add_blast_event);self.header.add_assessment_area_requested.connect(self._add_area);self.header.archive_requested.connect(self._archive_selected);self.header.analysis_requested.connect(self._open_analysis);self.header.report_requested.connect(self._project_report)
    def _activate_page(self,page):
        current=self.page_stack.currentWidget()
        if current is page:return
        self.page_stack.addWidget(page);self.page_stack.setCurrentWidget(page)
        if current and current not in (self.block_page,self.analysis_page):
            self.page_stack.removeWidget(current);current.deleteLater()
    def _show(self,page):
        if page is None:return False
        self.page_stack.setCurrentWidget(page);return True
    def refresh_project_data(self):
        self.tree.reload_filters();self.tree.load_data()
    def _open_analysis(self):
        if not self._guard_leave():return False
        from ui.pages.analysis_page import AnalysisPlaceholderPage
        if self.analysis_page is None:self.analysis_page=AnalysisPlaceholderPage()
        self._activate_page(self.analysis_page);self.header.set_archive_context(False);return True
    def _guard_leave(self):
        page=self.assessment_page
        if page is None or self.page_stack.currentWidget() is not page: return True
        if page.has_active_workflow():
            answer=QMessageBox.warning(self,tr("Unsaved geometry"),tr("There are unsaved geometry changes."),QMessageBox.StandardButton.Cancel|QMessageBox.StandardButton.Discard,QMessageBox.StandardButton.Cancel)
            if answer != QMessageBox.StandardButton.Discard: return False
            page.cancel_active_workflow()
        try:
            page.save_now()
            self.assessment_page = None
            self.assessment_domain_id = None
            self.assessment_site_id = None
            return True
        except Exception as exc: QMessageBox.critical(self,tr("Save error"),f"Could not save data.\n\n{domain_message(str(exc))}"); return False
    def _set_context(self,site_id,site_name=None,domain_id=None,domain_name=None,block_id=None,area_id=None,contour_id=None):
        self.selected_site_id=site_id; self.selected_site_name=site_name or self.selected_site_name; self.selected_domain_id=domain_id; self.selected_domain_name=domain_name; self.selected_block_id=block_id; self.selected_contour_event_id=contour_id; self.selected_assessment_area_id=area_id; self._update_add(); self.header.set_archive_context(area_id is not None or contour_id is not None)
    def _update_add(self):
        active=bool(self.selected_site_id and self.navigation_queries.project_has_active_lines(self.selected_site_id)); self.header.update_add_availability(self.selected_site_id is not None,self.selected_domain_id is not None,active)
    def select_site(self,site_id,site_name):
        if not self._guard_leave(): return False
        try:
            from ui.pages.dashboards import SiteDashboardPage
            page=SiteDashboardPage(self.context,site_id,site_name)
        except Exception as exc:
            QMessageBox.critical(self,tr("Could not open project dashboard"),domain_message(str(exc))); return False
        page.domain_requested.connect(lambda domain_id:self._open_domain_dashboard(domain_id,site_id,site_name))
        page.assessment_area_requested.connect(lambda area_id,domain_id:self._open_project_dashboard_area(area_id,domain_id,site_id))
        page.project_renamed.connect(self._project_renamed)
        self._activate_page(page); self._set_context(site_id,site_name); return True
    def _open_project_dashboard_area(self,area_id,domain_id,site_id):
        domain=self.navigation_queries.get_domain_context(domain_id)
        return self.open_area_from_tree(area_id,domain_id,site_id,domain.domain_name)
    def _open_domain_dashboard(self,domain_id,site_id,site_name):
        domain=self.navigation_queries.get_domain_context(domain_id); self.select_domain(domain_id,domain.domain_name,site_id,domain.site_name)
    def select_domain(self,domain_id,domain_name,site_id,site_name):
        if not self._guard_leave(): return False
        try:
            from ui.pages.dashboards import DomainDashboardPage
            page=DomainDashboardPage(self.context,domain_id,domain_name)
        except Exception as exc:
            QMessageBox.critical(self,tr("Could not open domain dashboard"),domain_message(str(exc))); return False
        page.block_requested.connect(lambda block_id:self.open_block_from_tree(block_id,domain_id,site_id))
        page.contour_requested.connect(lambda event_id:self.open_contour_from_tree(event_id,domain_id,site_id,self.navigation_queries.get_domain_context(domain_id).domain_name))
        page.assessment_area_requested.connect(lambda area_id:self.open_area_from_tree(area_id,domain_id,site_id,self.navigation_queries.get_domain_context(domain_id).domain_name))
        page.domain_renamed.connect(self._domain_renamed)
        self._activate_page(page); self._set_context(site_id,site_name,domain_id,domain_name); return True
    def _project_renamed(self,site_id,new_name):
        if self.selected_site_id==site_id:self.selected_site_name=new_name
        self.refresh_project_data()
    def _domain_renamed(self,domain_id,new_name,_new_version):
        if self.selected_domain_id==domain_id:self.selected_domain_name=new_name
        self.refresh_project_data()
    def open_block_from_tree(self,block_id,domain_id=None,site_id=None):
        domain=self.navigation_queries.get_domain_context(domain_id) if domain_id else None
        if self._show(self.block_page):
            self.block_page.open_block_id(block_id); self._set_context(site_id,domain.site_name if domain else None,domain_id,domain.domain_name if domain else None,block_id); self.header.set_archive_context(True,self.block_page.current_block.is_archived); return True
        return False
    def _open_related_assessment(self,area_id,domain_id):
        domain=self.navigation_queries.get_domain_context(domain_id)
        return self.open_area_from_tree(area_id,domain_id,domain.site_id,domain.domain_name)
    def _open_related_blast(self,event_id,event_type,domain_id):
        domain=self.navigation_queries.get_domain_context(domain_id)
        if event_type=="production":
            return self.open_block_from_tree(event_id,domain_id,domain.site_id)
        return self.open_contour_from_tree(event_id,domain_id,domain.site_id,domain.domain_name)
    def open_area_from_tree(self,area_id,domain_id,site_id,domain_name):
        if not self._guard_leave(): return False
        from ui.pages.assessment_area_page import AssessmentAreaPage
        try: page=AssessmentAreaPage(self.context,domain_id,domain_name,area_id)
        except Exception as exc:
            QMessageBox.critical(self,tr("Assessment Area"),f"Could not open the assessment area. The current page was preserved.\n\n{domain_message(str(exc))}"); return False
        page.edit_boundaries_requested.connect(self._edit_area_boundaries)
        page.metadata_saved.connect(lambda entity_id,target_id:self._metadata_move_saved("area",entity_id,target_id))
        page.related_blast_event_requested.connect(self._open_related_blast)
        self._activate_page(page)
        domain=self.navigation_queries.get_domain_context(domain_id); self.assessment_page=None; self.area_page=page; self._set_context(site_id,domain.site_name,domain_id,domain_name,area_id=area_id); self.header.set_archive_context(True,page.area.is_archived); return True
    def open_contour_from_tree(self,event_id,domain_id,site_id,domain_name):
        if not self._guard_leave(): return False
        from ui.pages.contour_event_page import ContourEventPage
        try: page=ContourEventPage(self.context,domain_id,domain_name,event_id)
        except Exception as exc: QMessageBox.critical(self,tr("Contour blast"),f"Could not open the contour blast.\n\n{domain_message(str(exc))}"); return False
        page.metadata_saved.connect(lambda entity_id,target_id:self._metadata_move_saved("contour",entity_id,target_id))
        page.related_assessment_requested.connect(self._open_related_assessment)
        self._activate_page(page)
        domain=self.navigation_queries.get_domain_context(domain_id); self.contour_page=page; self._set_context(site_id,domain.site_name,domain_id,domain_name,contour_id=event_id); self.header.set_archive_context(True,page.blast_event.is_archived); return True

    def _metadata_move_saved(self, kind, entity_id, target_domain_id):
        """Discard the old Domain snapshot and reopen the same logical entity."""
        domain=self.navigation_queries.get_domain_context(target_domain_id)
        self.refresh_project_data()
        if kind=="contour":self.open_contour_from_tree(entity_id,target_domain_id,domain.site_id,domain.domain_name)
        elif kind=="block":self.open_block_from_tree(entity_id,target_domain_id,domain.site_id)
        else:self.open_area_from_tree(entity_id,target_domain_id,domain.site_id,domain.domain_name)
    def _add_project(self):
        from ui.project_dialog import ProjectDialog
        d=ProjectDialog(self)
        if not d.exec(): return
        try:
            user=self.context.current_user
            result=self.create_project.execute(CreateProjectCommand(d.name.text(),d.description.toPlainText(),d.csv_path.text() or None,user.id,user.can_edit))
            if result.project_lines_warning:
                QMessageBox.warning(self,tr("Project created without lines"),f"The project was created, but Project Lines were not saved: {domain_message(result.project_lines_warning)}\nImport them again from the project page.")
            self.refresh_project_data(); self.select_site(result.site_id,result.project_name)
        except Exception as exc: QMessageBox.warning(self,tr("Could not create project"),domain_message(str(exc)))
    def _project_report(self):
        if self.selected_site_id is None:return
        from ui.dialogs.project_report_dialog import ProjectReportDialog
        ProjectReportDialog(self.generate_project_report,self.selected_site_id,self.selected_site_name or tr("Project"),self).exec()
    def _add_domain(self):
        if self.selected_site_id is None:return
        from ui.add_dialog import AddDialog
        d=AddDialog("domain")
        if not d.exec(): return
        try:
            user=self.context.current_user
            self.create_domain.execute(CreateDomainCommand(self.selected_site_id,d.name.text(),d.description.toPlainText(),user.id,user.can_edit))
            self.refresh_project_data()
        except Exception as exc:
            QMessageBox.warning(self,tr("Could not create domain"),domain_message(str(exc)))
    def _add_blast_event(self):
        if self.selected_domain_id is None:return
        from ui.dialogs.blast_event_dialog import BlastEventDialog
        dialog=BlastEventDialog(self)
        if not dialog.exec():return
        try:
            values=dialog.values()
            user=self.context.current_user
            result=self.create_blast_event.execute(CreateBlastEventCommand(
                domain_id=self.selected_domain_id,
                name=values["name"], event_type=values["event_type"],
                event_date=values["event_date"], elevation=values["elevation"],
                geometry_file_path=values["csv_path"], actor_id=user.id,
                can_edit=user.can_edit,
            ))
        except Exception as exc:
            QMessageBox.warning(self,tr("Could not create blast event"),domain_message(str(exc)))
            return
        try:
            self.refresh_project_data()
            if result.event_type=="contour":
                opened=self.open_contour_from_tree(result.event_id,self.selected_domain_id,self.selected_site_id,self.selected_domain_name)
            else:
                opened=self.open_block_from_tree(result.event_id,self.selected_domain_id,self.selected_site_id)
            if not opened:
                raise RuntimeError("The created Blast Event page could not be opened")
        except Exception as exc:
            QMessageBox.warning(self,tr("Blast event created"),
                tr("The Blast Event was created successfully, but its page could not be opened. Refresh the project tree and open it again.")
                + f"\n\n{domain_message(str(exc))}")
    def _add_area(self):
        if self.selected_domain_id is None:return
        if not self.navigation_queries.project_has_active_lines(self.selected_site_id):
            QMessageBox.information(self,tr("Project Lines"),tr("Load Project Lines for the project first.")); self.select_site(self.selected_site_id,self.selected_site_name); return
        if not self._guard_leave(): return
        from ui.pages.assessment_area_creation_page import AssessmentAreaCreationPage
        try: page=AssessmentAreaCreationPage(self.context,self.selected_domain_id,self.selected_domain_name,self.selected_site_id)
        except Exception as exc:
            QMessageBox.critical(self,tr("Assessment Area"),f"Could not start assessment area creation. The current page was preserved.\n\n{domain_message(str(exc))}"); return
        page.area_created.connect(lambda area_id:self._area_created(area_id,page)); page.cancelled.connect(lambda:self.select_domain(self.selected_domain_id,self.selected_domain_name,self.selected_site_id,self.selected_site_name))
        self._activate_page(page); self.assessment_page=page; self.assessment_domain_id=self.selected_domain_id
    def _area_created(self,area_id,creation_page):
        self.assessment_page=None; self.refresh_project_data(); self.open_area_from_tree(area_id,self.selected_domain_id,self.selected_site_id,self.selected_domain_name)
        if self.page_stack.indexOf(creation_page)>=0:self.page_stack.removeWidget(creation_page)
        creation_page.deleteLater()
    def _finish_area_boundary_edit(self,area_id,edit_page):
        """Leave an already-saved edit without running the unsaved-work guard again."""
        if self.assessment_page is edit_page:self.assessment_page=None
        self.assessment_domain_id=None; self.assessment_site_id=None
        domain_id=self.selected_domain_id; site_id=self.selected_site_id; domain_name=self.selected_domain_name
        self.refresh_project_data()
        self.open_area_from_tree(area_id,domain_id,site_id,domain_name)
        if self.page_stack.indexOf(edit_page)>=0:self.page_stack.removeWidget(edit_page)
        edit_page.deleteLater()
    def _cancel_area_boundary_edit(self,area_id,edit_page):
        """Back remains guarded while an edit workflow is active."""
        if not self.open_area_from_tree(area_id,self.selected_domain_id,self.selected_site_id,self.selected_domain_name):return
        if self.page_stack.indexOf(edit_page)>=0:self.page_stack.removeWidget(edit_page)
        edit_page.deleteLater();self.assessment_page=None;self.assessment_domain_id=None;self.assessment_site_id=None
    def _edit_area_boundaries(self,area_id):
        if not self._guard_leave():return
        from ui.pages.assessment_area_creation_page import AssessmentAreaCreationPage
        try: page=AssessmentAreaCreationPage(self.context,self.selected_domain_id,self.selected_domain_name,self.selected_site_id,edit_area_id=area_id)
        except Exception as exc:
            QMessageBox.critical(self,tr("Assessment Area"),f"Could not open boundary editing. The current page was preserved.\n\n{domain_message(str(exc))}");return
        page.area_created.connect(lambda saved_id:self._finish_area_boundary_edit(saved_id,page));page.cancelled.connect(lambda:self._cancel_area_boundary_edit(area_id,page))
        self._activate_page(page);self.assessment_page=page;self.assessment_domain_id=self.selected_domain_id;self.assessment_site_id=self.selected_site_id
    def _archive_selected(self):
        try:
            if self.selected_block_id is not None:
                from infrastructure.services.production_blast_service import ProductionBlastService
                ProductionBlastService(self.context.session_factory).set_archived(self.selected_block_id,True)
            elif self.selected_contour_event_id is not None:self.archive_action.archive_contour(self.selected_contour_event_id)
            elif self.selected_assessment_area_id is not None:self.archive_action.archive_area(self.selected_assessment_area_id)
            else:return
            self.refresh_project_data()
            if self.selected_domain_id:self.select_domain(self.selected_domain_id,self.selected_domain_name,self.selected_site_id,self.selected_site_name)
        except Exception as exc:QMessageBox.warning(self,tr("Archive error"),domain_message(str(exc)))
    def closeEvent(self,event):
        if self._guard_leave():event.accept()
        else:event.ignore()
