"""Focused visual progress indicator for the Assessment workflow."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.localization import tr


class AssessmentWizardStepper(QWidget):
    """Three visible user steps; SAVE remains a compatible completion state."""

    labels = ("Details", "Boundary", "Review")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.step_nodes = []
        self.connectors = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setSpacing(6)
        for index, text in enumerate(self.labels):
            node = QWidget(); box = QVBoxLayout(node)
            box.setContentsMargins(0, 0, 0, 0); box.setSpacing(2)
            circle = QLabel(str(index + 1)); circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
            circle.setFixedSize(20, 20); circle.setObjectName("assessmentStepCircle")
            label = QLabel(tr(text)); label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setObjectName("assessmentStepLabel")
            box.addWidget(circle, 0, Qt.AlignmentFlag.AlignHCenter); box.addWidget(label)
            self.step_nodes.append((circle, label)); layout.addWidget(node)
            if index < len(self.labels) - 1:
                line = QFrame(); line.setObjectName("assessmentStepConnector"); line.setFixedHeight(1)
                self.connectors.append(line); layout.addWidget(line, 1)
        self.set_step(0)

    def set_step(self, active):
        visible_active = min(active, len(self.step_nodes))
        for index, (circle, label) in enumerate(self.step_nodes):
            state = "complete" if index < visible_active else "active" if index == visible_active else "future"
            circle.setText("✓" if state == "complete" else str(index + 1))
            for widget in (circle, label):
                widget.setProperty("stepState", state)
                widget.style().unpolish(widget); widget.style().polish(widget)
        for index, line in enumerate(self.connectors):
            line.setProperty("complete", index < visible_active)
            line.style().unpolish(line); line.style().polish(line)
