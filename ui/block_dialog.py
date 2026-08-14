
from app.localization import tr
from PySide6.QtWidgets import QComboBox,QDialog,QFormLayout,QHBoxLayout,QLineEdit,QMessageBox,QPushButton,QTextEdit,QVBoxLayout
from infrastructure.services.blast_block_service import BlastBlockInput,PermissionDenied,ValidationError
class BlockDialog(QDialog):
    def __init__(self, service, domain_repo, user, domain_id=None, block=None,
                 read_only=False, expected_version=None):
        super().__init__(); self.service=service; self.domain_repo=domain_repo; self.user=user; self.block=block; self.saved_block_id=None; self.read_only=read_only or not user.can_edit
        self.setWindowTitle(tr("Block card") if block else "New block"); layout=QVBoxLayout(self); form=QFormLayout(); self.domain=QComboBox(); self.block_number=QLineEdit(); self.horizon=QLineEdit(); self.comment=QTextEdit()
        selected=block.domain_id if block else domain_id; domain=domain_repo.get(selected) if selected else None
        if domain:
            for item in domain_repo.list_for_site(domain.site_id): self.domain.addItem(item.name,item.id)
            self.domain.setCurrentIndex(max(0,self.domain.findData(selected)))
        form.addRow(tr("Domain *"),self.domain); form.addRow(tr("Block number *"),self.block_number); form.addRow(tr("Horizon, m"),self.horizon); form.addRow(tr("Comment"),self.comment); layout.addLayout(form)
        self.expected_version = expected_version
        if block:
            self.block_number.setText(block.block_number); self.horizon.setText("" if block.horizon_m is None else str(block.horizon_m)); self.comment.setPlainText(block.comment or "")
            self.domain.setEnabled(False); self.domain.setToolTip(tr("Moving a Block between Domains is not available yet"))
        buttons=QHBoxLayout(); buttons.addStretch(); cancel=QPushButton(tr("Cancel")); cancel.clicked.connect(self.reject); save=QPushButton(tr("Save")); save.clicked.connect(self._save); save.setVisible(not self.read_only); buttons.addWidget(cancel); buttons.addWidget(save); layout.addLayout(buttons)
    def _input(self):
        return BlastBlockInput(self.domain.currentData(),self.block_number.text(),self.horizon.text(),self.comment.toPlainText())
    def _save(self):
        try: self.saved_block_id=self.service.update_block(self.block.id,self._input(),self.user,expected_version=self.expected_version) if self.block else self.service.create_block(self._input(),self.user); self.accept()
        except (ValidationError,PermissionDenied,ValueError,RuntimeError) as exc: QMessageBox.warning(self,tr("Could not save block"),str(exc))
