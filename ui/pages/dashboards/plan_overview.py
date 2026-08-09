from PySide6.QtWidgets import QCheckBox,QHBoxLayout,QLabel,QPushButton,QVBoxLayout,QWidget
from app.icons.ui.ui_icons import ui_icon
class DashboardPlanOverviewWidget(QWidget):
    """Isolated read-only overview; deliberately exposes no geometry tools."""
    def __init__(self,snapshot):
        super().__init__(); box=QVBoxLayout(self); controls=QHBoxLayout(); fit=QPushButton("Fit"); fit.setIcon(ui_icon("fit-view")); controls.addWidget(fit); lines=QCheckBox("Project Lines"); lines.setChecked(True); controls.addWidget(lines); controls.addStretch(); box.addLayout(controls)
        label=QLabel(f"Read-only plan overview  •  {snapshot.domain.production} production  •  {snapshot.domain.contour} contour  •  {snapshot.domain.areas} areas")
        label.setMinimumHeight(150); label.setStyleSheet("background:#F8FAFC;border:1px solid #E2E8F0;color:#64748B;qproperty-alignment:AlignCenter"); box.addWidget(label)
