from datetime import date
from PySide6.QtCore import QDate
from PySide6.QtWidgets import QComboBox,QDateEdit,QDialog,QFormLayout,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QTextEdit,QVBoxLayout
from services.blast_block_service import BlastBlockInput,PermissionDenied,STATUS_LABELS,ValidationError
class BlockDialog(QDialog):
    def __init__(self, service, domain_repo, user, domain_id=None, block=None, read_only=False):
        super().__init__(); self.service=service; self.domain_repo=domain_repo; self.user=user; self.block=block; self.saved_block_id=None; self.read_only=read_only or not user.can_edit
        self.setWindowTitle("Block card" if block else "New block"); layout=QVBoxLayout(self); form=QFormLayout(); self.domain=QComboBox(); self.block_number=QLineEdit(); self.horizon=QLineEdit(); self.planned_date=QDateEdit(); self.planned_date.setCalendarPopup(True); self.planned_date.setMinimumDate(QDate(1900,1,1)); self.status=QComboBox(); self.comment=QTextEdit()
        for value,label in STATUS_LABELS.items(): self.status.addItem(label,value)
        selected=block.domain_id if block else domain_id; domain=domain_repo.get(selected) if selected else None
        if domain:
            for item in domain_repo.list_for_site(domain.site_id): self.domain.addItem(item.name,item.id)
            self.domain.setCurrentIndex(max(0,self.domain.findData(selected)))
        form.addRow("Domain *",self.domain); form.addRow("Block number *",self.block_number); form.addRow("Horizon, m",self.horizon); form.addRow("Planned blast date",self.planned_date); form.addRow("Status",self.status); form.addRow("Comment",self.comment); layout.addLayout(form)
        if block:
            self.block_number.setText(block.block_number); self.horizon.setText(str(block.horizon_m or "")); self.status.setCurrentIndex(max(0,self.status.findData(block.status))); self.comment.setPlainText(block.comment or "")
            if block.planned_blast_date: d=block.planned_blast_date; self.planned_date.setDate(QDate(d.year,d.month,d.day))
        buttons=QHBoxLayout(); buttons.addStretch(); cancel=QPushButton("Cancel"); cancel.clicked.connect(self.reject); save=QPushButton("Save"); save.clicked.connect(self._save); save.setVisible(not self.read_only); buttons.addWidget(cancel); buttons.addWidget(save); layout.addLayout(buttons)
    def _input(self):
        q=self.planned_date.date(); planned=None if q==self.planned_date.minimumDate() else date(q.year(),q.month(),q.day())
        return BlastBlockInput(self.domain.currentData(),self.block_number.text(),self.horizon.text(),planned,self.status.currentData(),self.comment.toPlainText())
    def _save(self):
        try: self.saved_block_id=self.service.update_block(self.block.id,self._input(),self.user) if self.block else self.service.create_block(self._input(),self.user); self.accept()
        except (ValidationError,PermissionDenied,ValueError) as exc: QMessageBox.warning(self,"Could not save block",str(exc))
