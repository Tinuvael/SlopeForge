
from app.localization import tr
from PySide6.QtWidgets import QComboBox,QDialog,QFormLayout,QHBoxLayout,QLineEdit,QMessageBox,QPushButton,QTextEdit,QVBoxLayout
from infrastructure.services.blast_block_service import BlastBlockInput,PermissionDenied,ValidationError
class BlockDialog(QDialog):
    def __init__(self, service, domain_repo, user, domain_id=None, block=None,
                 read_only=False, expected_version=None):
        super().__init__(); self.service=service; self.domain_repo=domain_repo; self.user=user; self.block=block; self.saved_block_id=None; self.read_only=read_only or not user.can_edit
        self.setWindowTitle(tr("Edit block") if block else "New block"); layout=QVBoxLayout(self); form=QFormLayout(); self.domain=QComboBox(); self.block_number=QLineEdit(); self.horizon=QLineEdit(); self.comment=QTextEdit() if not block else None
        selected=block.domain_id if block else domain_id; domain=domain_repo.get(selected) if selected else None
        if domain:
            for item in domain_repo.selectable_for_site(domain.site_id): self.domain.addItem(item.domain_name,(item.domain_id,item.version))
            self.domain.setCurrentIndex(max(0,self.domain.findData(selected)))
            self.domain.setCurrentIndex(next((i for i in range(self.domain.count()) if self.domain.itemData(i)[0]==selected),0))
            self.domain.setEnabled(self.domain.count()>1 and not self.read_only)
        form.addRow(tr("Block number"),self.block_number); form.addRow(tr("Domain"),self.domain); form.addRow(tr("Horizon, m"),self.horizon)
        if self.comment is not None: form.addRow(tr("Comment"),self.comment)
        layout.addLayout(form)
        self.expected_version = expected_version
        if block:
            self.block_number.setText(block.block_number); self.horizon.setText("" if block.horizon_m is None else str(block.horizon_m))
        buttons=QHBoxLayout(); buttons.addStretch(); cancel=QPushButton(tr("Cancel")); cancel.clicked.connect(self.reject); save=QPushButton(tr("Save")); save.clicked.connect(self._save); save.setVisible(not self.read_only); buttons.addWidget(cancel); buttons.addWidget(save); layout.addLayout(buttons)
    def _input(self):
        data=self.domain.currentData(); domain_id=data[0] if isinstance(data,tuple) else data
        return BlastBlockInput(domain_id,self.block_number.text(),self.horizon.text(),self.comment.toPlainText() if self.comment else None)
    def _save(self):
        try:
            if self.block:
                data=self._input(); selected=self.domain.currentData(); target_version=selected[1]
                frozen=self.service.active_geometry_elevation(self.block.id)
                try:new_horizon=float(data.horizon_text.replace(",","."))
                except ValueError:new_horizon=None
                if frozen is not None and new_horizon is not None and abs(new_horizon-float(frozen))>0.01:
                    warning=tr("The new Horizon differs from the active imported geometry elevation. Existing geometry revisions will remain unchanged.\n\nContinue?")
                    if QMessageBox.question(self,tr("Frozen geometry"),warning)!=QMessageBox.Yes:return
                self.saved_block_id=self.service.update_metadata(self.block.id,domain_id=data.domain_id,block_number=data.block_number,horizon_text=data.horizon_text,user=self.user,expected_version=self.expected_version,target_expected_version=target_version)
            else:self.saved_block_id=self.service.create_block(self._input(),self.user)
            self.accept()
        except (ValidationError,PermissionDenied,ValueError,RuntimeError) as exc: QMessageBox.warning(self,tr("Could not save block"),str(exc))
