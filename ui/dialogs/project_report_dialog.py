from datetime import date
from pathlib import Path
from PySide6.QtCore import QDate,QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDateEdit,QDialog,QDialogButtonBox,QFileDialog,QFormLayout,QLabel,QMessageBox,QPushButton
from app.localization import tr
from application.use_cases.generate_project_report import GenerateProjectReportCommand

class ProjectReportDialog(QDialog):
    def __init__(self,generate_report,site_id,site_name,parent=None):
        super().__init__(parent); self.generate_report=generate_report; self.site_id=site_id; self.site_name=site_name
        self.setWindowTitle(tr("Project report")); form=QFormLayout(self); form.addRow(tr("Project"),QLabel(site_name))
        today=date.today(); first=today.replace(day=1); self.from_date=QDateEdit(QDate(first.year,first.month,first.day)); self.to_date=QDateEdit(QDate(today.year,today.month,today.day))
        for editor in (self.from_date,self.to_date):editor.setCalendarPopup(True)
        form.addRow(tr("From"),self.from_date); form.addRow(tr("To"),self.to_date)
        buttons=QDialogButtonBox(); cancel=buttons.addButton(tr("Cancel"),QDialogButtonBox.ButtonRole.RejectRole); generate=buttons.addButton(tr("Generate Excel"),QDialogButtonBox.ButtonRole.AcceptRole); cancel.clicked.connect(self.reject); generate.clicked.connect(self.generate); form.addRow(buttons)
    def dates(self):return self.from_date.date().toPython(),self.to_date.date().toPython()
    def validate_dates(self):
        start,end=self.dates(); return start<=end
    def generate(self):
        if not self.validate_dates():QMessageBox.warning(self,tr("Project report"),tr("From date must not be after To date")); return
        start,end=self.dates(); safe="".join(c if c.isalnum() or c in "-_" else "_" for c in self.site_name).strip("_") or "Project"
        path,_=QFileDialog.getSaveFileName(self,tr("Project report"),f"{safe}_report_{start}_{end}.xlsx",tr("Excel workbook (*.xlsx)"))
        if not path:return
        if Path(path).suffix.lower()!=".xlsx":path += ".xlsx"
        try:
            result=self.generate_report.execute(GenerateProjectReportCommand(self.site_id,start,end,path))
        except Exception as exc:QMessageBox.critical(self,tr("Project report"),f"{tr('Could not generate report')}: {exc}")
        else:
            absolute=result.output_path
            try:opened=QDesktopServices.openUrl(QUrl.fromLocalFile(str(absolute)))
            except Exception:opened=False
            self.accept()
            if not opened:QMessageBox.warning(self.parent() or self,tr("Project report"),tr("The report was saved, but could not be opened automatically."))
