from PySide6.QtWidgets import (QFileDialog, QLabel, QMessageBox, QPushButton,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)
from prototype_2d.domain import AssessmentDomainState
from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService
from repositories.project_lines_repository import ProjectLinesRepository

class _Dashboard(QWidget):
    def __init__(self, title, subtitle):
        super().__init__(); self.layout=QVBoxLayout(self); heading=QLabel(title); heading.setStyleSheet("font-size: 26px; font-weight: 700"); self.layout.addWidget(heading); self.layout.addWidget(QLabel(subtitle))
class SiteDashboardPage(_Dashboard):
    def __init__(self, context, site_id, name):
        super().__init__(name, "Overall mine / quarry dashboard"); self.context=context; self.site_id=site_id; self.repo=ProjectLinesRepository(context.session_factory)
        self.active_label=QLabel(); self.layout.addWidget(QLabel("Project Lines")); self.layout.addWidget(self.active_label)
        self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(["Dataset", "Imported", "Source filename", "State"]); self.layout.addWidget(self.table)
        self.import_button=QPushButton("Import / Update Project Lines"); self.import_button.setEnabled(context.current_user.can_edit); self.import_button.clicked.connect(self.import_lines); self.layout.addWidget(self.import_button); self.layout.addStretch(); self.refresh()
    def refresh(self):
        rows=self.repo.list_for_site(self.site_id); active=next((x for x in rows if x.is_active),None)
        self.active_label.setText(f"Active: {active.name} ({active.domain_id})" if active else "Active Dataset: not loaded")
        self.table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            for c,value in enumerate((f"{row.name} ({row.domain_id})",row.imported_at.strftime("%Y-%m-%d %H:%M"),row.source_file_name,"Active" if row.is_active else "Inactive")): self.table.setItem(r,c,QTableWidgetItem(value))
    def import_path(self, path):
        state=AssessmentDomainState(); dataset,_=ProjectLinesDatasetService(state).import_dataset(path); self.repo.import_dataset(self.site_id,dataset,make_active=True); self.refresh(); return dataset
    def import_lines(self):
        path,_=QFileDialog.getOpenFileName(self,"CSV Datamine — проектные линии","","CSV (*.csv)")
        if not path:return
        try:self.import_path(path)
        except Exception as exc: QMessageBox.warning(self,"Ошибка импорта",str(exc))
class DomainDashboardPage(_Dashboard):
    def __init__(self, name): super().__init__(name, "Domain dashboard"); self.layout.addStretch()

# Stable compatibility imports while dashboard code lives in focused modules.
from ui.pages.dashboards import SiteDashboardPage, DomainDashboardPage
