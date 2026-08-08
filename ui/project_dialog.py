from PySide6.QtWidgets import QFileDialog,QHBoxLayout,QLabel,QLineEdit,QPushButton,QTextEdit,QVBoxLayout,QDialog
class ProjectDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle("Add mine / quarry"); layout=QVBoxLayout(self); layout.addWidget(QLabel("Name")); self.name=QLineEdit(); layout.addWidget(self.name); layout.addWidget(QLabel("Description")); self.description=QTextEdit(); layout.addWidget(self.description); self.csv_path=QLineEdit(); self.csv_path.setReadOnly(True); browse=QPushButton("Import Project Lines (optional)"); browse.clicked.connect(self._browse); row=QHBoxLayout(); row.addWidget(self.csv_path); row.addWidget(browse); layout.addLayout(row); buttons=QHBoxLayout(); cancel=QPushButton("Cancel"); create=QPushButton("Create"); cancel.clicked.connect(self.reject); create.clicked.connect(self.accept); buttons.addStretch(); buttons.addWidget(cancel); buttons.addWidget(create); layout.addLayout(buttons)
    def _browse(self):
        path,_=QFileDialog.getOpenFileName(self,"CSV Datamine — проектные линии","","CSV (*.csv)")
        if path:self.csv_path.setText(path)
