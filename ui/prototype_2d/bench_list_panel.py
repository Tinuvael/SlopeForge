from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGroupBox, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget


class BenchListPanel(QWidget):
    bench_selected = Signal(int)
    add_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        project = QGroupBox("Проект")
        project_layout = QVBoxLayout(project)
        self.project_label = QLabel("Проект: —")
        self.dataset_label = QLabel("Dataset: —")
        project_layout.addWidget(self.project_label); project_layout.addWidget(self.dataset_label)
        layout.addWidget(project)
        layout.addWidget(QLabel("Уступы"))
        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self.bench_selected)
        layout.addWidget(self.list_widget, 1)
        self.add_button = QPushButton("+ Добавить уступ")
        self.add_button.clicked.connect(self.add_requested)
        layout.addWidget(self.add_button)

    def set_project(self, name: str, dataset_id: str | None) -> None:
        self.project_label.setText(f"Проект: {name or '—'}")
        self.dataset_label.setText(f"Dataset: {dataset_id or '—'}")
