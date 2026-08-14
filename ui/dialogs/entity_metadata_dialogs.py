"""Compact identity/location editors; engineering facts live elsewhere."""
from app.localization import tr
from PySide6.QtWidgets import QComboBox,QDialog,QDoubleSpinBox,QFormLayout,QHBoxLayout,QLineEdit,QPushButton,QVBoxLayout

class EntityMetadataDialog(QDialog):
    def __init__(self, domains, current_domain_id, *, name, horizon=None, block=False, parent=None):
        super().__init__(parent); self.setWindowTitle(tr("Edit")); root=QVBoxLayout(self); form=QFormLayout()
        self.name=QLineEdit(name); self.name.setObjectName("block_number" if block else "name")
        self.domain=QComboBox(); self.domain.setObjectName("domain")
        for item in domains:self.domain.addItem(item.domain_name,(item.domain_id,item.version))
        self.domain.setCurrentIndex(next((i for i in range(self.domain.count()) if self.domain.itemData(i)[0]==current_domain_id),0)); self.domain.setEnabled(self.domain.count()>1)
        form.addRow(tr("Block number") if block else tr("Name"),self.name); form.addRow(tr("Domain"),self.domain)
        self.horizon=None
        if horizon is not None:
            self.horizon=QDoubleSpinBox(); self.horizon.setObjectName("horizon"); self.horizon.setDecimals(3); self.horizon.setRange(-100000,100000); self.horizon.setValue(float(horizon)); form.addRow(tr("Horizon, m"),self.horizon)
        root.addLayout(form); buttons=QHBoxLayout(); buttons.addStretch(); cancel=QPushButton(tr("Cancel")); save=QPushButton(tr("Save")); cancel.clicked.connect(self.reject); save.clicked.connect(self.accept); buttons.addWidget(cancel); buttons.addWidget(save); root.addLayout(buttons)
    @property
    def selected_domain(self): return self.domain.currentData()

class ContourMetadataDialog(EntityMetadataDialog):
    def __init__(self,domains,current_domain_id,name,horizon,parent=None):super().__init__(domains,current_domain_id,name=name,horizon=horizon,parent=parent)
class AssessmentAreaMetadataDialog(EntityMetadataDialog):
    def __init__(self,domains,current_domain_id,name,parent=None):super().__init__(domains,current_domain_id,name=name,parent=parent)
