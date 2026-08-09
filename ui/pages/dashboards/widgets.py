from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame,QHBoxLayout,QLabel,QVBoxLayout,QWidget
from app.icons.ui.ui_icons import ui_icon

QUADRANTS={
    "good_design_good_face": ("Good design / good face", "#16A34A"),
    "good_design_poor_face": ("Good design / poor face", "#EA580C"),
    "poor_design_good_face": ("Poor design / good face", "#EA580C"),
    "poor_design_poor_face": ("Poor design / poor face", "#DC2626"),
}
def quadrant_presentation(value): return QUADRANTS.get(value,(value.replace("_"," ").title() if value else "—","#64748B"))
def metric(value): return "—" if value is None else f"{value:.2f}"

class MetricCard(QFrame):
    def __init__(self,title,value,detail="",icon="analytics"):
        super().__init__(); self.setObjectName("metricCard"); self.setStyleSheet("#metricCard{background:#fff;border:1px solid #E2E8F0;border-radius:9px;padding:10px}")
        row=QHBoxLayout(self); image=QLabel(); image.setPixmap(ui_icon(icon,"blue").pixmap(24,24)); row.addWidget(image)
        box=QVBoxLayout(); box.addWidget(QLabel(title)); self.value_label=QLabel(str(value)); self.value_label.setStyleSheet("font-size:20px;font-weight:700;color:#0F172A"); box.addWidget(self.value_label)
        d=QLabel(detail); d.setStyleSheet("color:#64748B"); box.addWidget(d); row.addLayout(box); row.addStretch()

class EmptyStateWidget(QWidget):
    def __init__(self,text,icon="info"):
        super().__init__(); row=QHBoxLayout(self); image=QLabel(); image.setPixmap(ui_icon(icon).pixmap(24,24)); row.addWidget(image); label=QLabel(text); label.setStyleSheet("color:#64748B"); row.addWidget(label); row.addStretch()

def section(title, child):
    w=QWidget(); box=QVBoxLayout(w); h=QLabel(title.upper()); h.setStyleSheet("font-weight:700;color:#334155;margin-top:8px"); box.addWidget(h); box.addWidget(child); return w
