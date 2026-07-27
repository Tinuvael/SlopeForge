from PySide6.QtWidgets import QGroupBox, QLabel, QListWidget, QPushButton, QVBoxLayout, QWidget


class BenchInspector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        self.empty_label = QLabel("Выберите уступ в списке слева или создайте новый.")
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)
        self.card = QWidget(); card_layout = QVBoxLayout(self.card)
        self.title = QLabel(); self.details = QLabel(); self.details.setWordWrap(True)
        card_layout.addWidget(self.title); card_layout.addWidget(self.details)
        boundaries = QGroupBox("Границы"); boundary_layout = QVBoxLayout(boundaries)
        self.upper_label = QLabel(); self.edit_upper_button = QPushButton("Изменить верхнюю границу")
        self.lower_label = QLabel(); self.edit_lower_button = QPushButton("Изменить нижнюю границу")
        for item in (self.upper_label, self.edit_upper_button, self.lower_label, self.edit_lower_button): boundary_layout.addWidget(item)
        card_layout.addWidget(boundaries)
        card_layout.addWidget(QLabel("Промежуточные сегменты"))
        self.upper_assessment_label = QLabel("Верхняя граница — первая промежуточная оценка")
        self.intermediate_list = QListWidget(); self.edit_intermediate_button = QPushButton("Изменить"); self.delete_intermediate_button = QPushButton("Удалить")
        self.add_intermediate_button = QPushButton("+ Добавить промежуточный сегмент")
        for item in (self.upper_assessment_label, self.intermediate_list, self.edit_intermediate_button, self.delete_intermediate_button, self.add_intermediate_button): card_layout.addWidget(item)
        self.delete_bench_button = QPushButton("Удалить уступ"); self.clear_selection_button = QPushButton("Снять выделение")
        card_layout.addWidget(self.delete_bench_button); card_layout.addWidget(self.clear_selection_button); card_layout.addStretch(1)
        layout.addWidget(self.card, 1)
        self.set_selected(False)

    def set_selected(self, selected: bool) -> None:
        self.empty_label.setVisible(not selected); self.card.setVisible(selected)
