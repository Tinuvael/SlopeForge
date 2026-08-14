"""Focused visual progress indicator for the Assessment workflow."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class AssessmentWizardStepper(QWidget):
    labels = ("General information", "Boundary", "Review & linked events", "Save")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.step_nodes = []
        self.connectors = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 2, 12, 4)
        layout.setSpacing(5)
        for index, text in enumerate(self.labels):
            node = QWidget(); box = QVBoxLayout(node)
            box.setContentsMargins(0, 0, 0, 0); box.setSpacing(2)
            circle = QLabel(str(index + 1)); circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            circle.setFixedSize(24, 24); circle.setObjectName("assessmentStepCircle")
            label = QLabel(text); label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setObjectName("assessmentStepLabel")
            box.addWidget(circle, 0, Qt.AlignmentFlag.AlignHCenter); box.addWidget(label)
            self.step_nodes.append((circle, label)); layout.addWidget(node)
            if index < len(self.labels) - 1:
                line = QFrame(); line.setFrameShape(QFrame.Shape.HLine); line.setFixedHeight(2)
                self.connectors.append(line); layout.addWidget(line, 1)
        self.set_step(0)

    def set_step(self, active):
        for index, (circle, label) in enumerate(self.step_nodes):
            if index < active:
                circle.setStyleSheet("background:#397DB7;color:white;border-radius:12px;font-weight:600;")
                label.setStyleSheet("color:#397DB7;")
            elif index == active:
                circle.setStyleSheet("background:#1769AA;color:white;border-radius:12px;font-weight:700;")
                label.setStyleSheet("color:#23313F;font-weight:700;")
            else:
                circle.setStyleSheet("background:#E4E9EE;color:#687481;border-radius:12px;")
                label.setStyleSheet("color:#687481;")
        for index, line in enumerate(self.connectors):
            line.setStyleSheet("background:#397DB7;border:0;" if index < active else
                               "background:#D9E0E7;border:0;")
