from PySide6.QtWidgets import QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from repositories.project_lines_repository import ProjectLinesRepository

class _Dashboard(QWidget):
    def __init__(self, title, subtitle):
        super().__init__(); layout=QVBoxLayout(self); heading=QLabel(title); heading.setStyleSheet("font-size: 26px; font-weight: 700"); layout.addWidget(heading); layout.addWidget(QLabel(subtitle)); layout.addStretch()
class SiteDashboardPage(_Dashboard):
    def __init__(self, name): super().__init__(name, "Overall mine / quarry dashboard")
class DomainDashboardPage(_Dashboard):
    def __init__(self, name): super().__init__(name, "Domain dashboard")
class ProjectLinesPage(QWidget):
    def __init__(self, context, site_id, site_name):
        super().__init__(); self.repo=ProjectLinesRepository(context.session_factory); self.site_id=site_id
        layout=QVBoxLayout(self); layout.addWidget(QLabel(f"Project Lines — {site_name}")); self.table=QTableWidget(0,4); self.table.setHorizontalHeaderLabels(["Dataset", "Imported", "Source filename", "State"]); layout.addWidget(self.table); self.refresh()
    def refresh(self):
        rows=self.repo.list_for_site(self.site_id); self.table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            values=(row.name, row.imported_at.strftime("%Y-%m-%d %H:%M"), row.source_file_name, "Active" if row.is_active else "Inactive")
            for c,value in enumerate(values): self.table.setItem(r,c,QTableWidgetItem(value))
