
from app.localization import tr
from PySide6.QtWidgets import QFileDialog,QHBoxLayout,QLabel,QLineEdit,QPushButton,QTextEdit,QVBoxLayout,QDialog
class ProjectDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle(tr("Add project")); layout=QVBoxLayout(self); layout.addWidget(QLabel(tr("Name"))); self.name=QLineEdit(); layout.addWidget(self.name); layout.addWidget(QLabel(tr("Description"))); self.description=QTextEdit(); layout.addWidget(self.description); self.csv_path=QLineEdit(); self.csv_path.setReadOnly(True); browse=QPushButton(tr("Import Project Lines (optional)")); browse.clicked.connect(self._browse); row=QHBoxLayout(); row.addWidget(self.csv_path); row.addWidget(browse); layout.addLayout(row); buttons=QHBoxLayout(); cancel=QPushButton(tr("Cancel")); create=QPushButton(tr("Create")); cancel.clicked.connect(self.reject); create.clicked.connect(self.accept); buttons.addStretch(); buttons.addWidget(cancel); buttons.addWidget(create); layout.addLayout(buttons)
    def _browse(self):
        path,_=QFileDialog.getOpenFileName(self,tr("Select Project Lines file"),"",tr("Project Lines (*.csv *.dxf);;Datamine CSV (*.csv);;AutoCAD DXF (*.dxf)"))
        if path:self.csv_path.setText(path)
