from app.localization import tr
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class AnalysisPlaceholderPage(QWidget):
    """Stable placeholder for the post-MVP analysis workspace."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("analysisPlaceholderPage")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.addStretch(2)

        title = QLabel(tr("Analysis"))
        title.setObjectName("analysisPlaceholderTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: 600; color: #1f2937;")
        layout.addWidget(title)

        message = QLabel(tr("Analysis section is under development."))
        message.setObjectName("analysisPlaceholderMessage")
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setStyleSheet("color: #6b7280;")
        layout.addWidget(message)

        layout.addStretch(3)
