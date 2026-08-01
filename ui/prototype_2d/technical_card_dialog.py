"""Scrollable editor for versioned BlastEvent technical cards."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTabWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from prototype_2d.technical_card import (CONTOUR_GROUP_TYPES, CONTROLLED_BLASTING_METHODS,
    PRODUCTION_GROUP_TYPES, BlastDrillingGroup)


def _number(value, suffix=""):
    widget = QDoubleSpinBox(); widget.setRange(-1_000_000_000, 1_000_000_000); widget.setDecimals(3)
    widget.setSpecialValueText("—"); widget.setValue(value if value is not None else widget.minimum())
    if suffix: widget.setSuffix(f" {suffix}")
    return widget


class TechnicalCardDialog(QDialog):
    def __init__(self, event, card, revision, save_callback, parent=None, read_only=False):
        super().__init__(parent); self.event, self.card, self.revision = event, card, revision
        self.save_callback, self.read_only = save_callback, read_only
        self.setWindowTitle(f"Техническая карточка — {event.name}"); self.setMinimumSize(760, 560); self.resize(940, 720)
        root = QVBoxLayout(self); meta = QLabel(f"BlastEvent ID: {event.id}   |   Ревизия геометрии: {revision.geometry_revision_id}")
        meta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse); root.addWidget(meta)
        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)
        self._common_tab()
        if event.event_type == "production": self._geomechanics_tab(); drilling_title = "Бурение и заряды"
        else: drilling_title = "Контурное бурение"
        self._drilling_tab(drilling_title); self._actual_tab(); self._history_tab()
        buttons = QHBoxLayout(); buttons.addStretch()
        self.draft_button = QPushButton("Сохранить черновик"); self.complete_button = QPushButton("Завершить"); cancel = QPushButton("Отмена")
        self.draft_button.clicked.connect(lambda: self._save("draft")); self.complete_button.clicked.connect(lambda: self._save("completed")); cancel.clicked.connect(self.reject)
        for button in (self.draft_button, self.complete_button): button.setEnabled(not read_only)
        buttons.addWidget(self.draft_button); buttons.addWidget(self.complete_button); buttons.addWidget(cancel); root.addLayout(buttons)

    def _scroll_tab(self, title):
        scroll = QScrollArea(); scroll.setWidgetResizable(True); page = QWidget(); layout = QVBoxLayout(page); layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(page); self.tabs.addTab(scroll, title); return layout

    def _common_tab(self):
        layout = self._scroll_tab("Общие"); common = self.revision.common_parameters
        identity = QGroupBox("Событие и источник"); form = QFormLayout(identity)
        form.addRow("BlastEvent ID", QLabel(self.event.id)); form.addRow("Geometry revision ID", QLabel(self.revision.geometry_revision_id))
        form.addRow("Исходный CSV", QLabel(common.source_csv or "—")); layout.addWidget(identity)
        block = QGroupBox("Параметры блока"); form = QFormLayout(block)
        self.block_name = QLineEdit(common.block_name); self.horizon = _number(common.working_horizon, "м"); self.comments = QLineEdit(common.comments)
        form.addRow("Название блока", self.block_name); form.addRow("Рабочий горизонт", self.horizon); form.addRow("Комментарии", self.comments); layout.addWidget(block)
        if self.revision.production_parameters:
            p = self.revision.production_parameters; calc = QGroupBox("Расчётные показатели"); f = QFormLayout(calc)
            f.addRow("Площадь бурения", QLabel(f"{p.drilling_area_m2.accepted_value:g} м²" if p.drilling_area_m2.accepted_value is not None else "— м²"))
            self.bench_height = _number(p.design_bench_height_m, "м"); self.explosive = _number(p.total_explosive_mass_kg, "кг")
            f.addRow("Проектная высота уступа", self.bench_height); f.addRow("Масса ВВ", self.explosive); layout.addWidget(calc)
        else:
            contour = self.revision.contour_parameters; method = QGroupBox("Метод контролируемого взрывания"); f = QFormLayout(method)
            self.method = QComboBox(); self.method.addItem("— выберите —", "")
            for key, name in CONTROLLED_BLASTING_METHODS.items(): self.method.addItem(name, key)
            self.method.setCurrentIndex(max(0, self.method.findData(contour.controlled_blasting_method)))
            self.method.currentIndexChanged.connect(self._method_changed); f.addRow("Метод", self.method); layout.addWidget(method)

    def _geomechanics_tab(self):
        layout = self._scroll_tab("Геомеханика"); geo = self.revision.geomechanical_parameters
        strength = QGroupBox("Прочность массива"); form = QFormLayout(strength)
        self.strength_class = QLineEdit(geo.rock_strength_class_text); self.ucs = _number(geo.representative_ucs_mpa, "МПа")
        form.addRow("Локальный класс прочности", self.strength_class); form.addRow("Представительный UCS", self.ucs); layout.addWidget(strength)
        quality = QGroupBox("Качество массива"); form = QFormLayout(quality)
        self.rqd = _number(geo.rqd_representative_percent, "%"); self.rock_properties = QLineEdit(geo.rock_mass_properties_text)
        form.addRow("Представительный RQD", self.rqd); form.addRow("Описание свойств массива", self.rock_properties); layout.addWidget(quality)

    def _drilling_tab(self, title):
        self.drilling_layout = self._scroll_tab(title); self.group_cards = QWidget(); self.group_cards_layout = QVBoxLayout(self.group_cards)
        self.drilling_layout.addWidget(self.group_cards); self._render_groups()
        self.add_group_combo = QComboBox(); catalogue = PRODUCTION_GROUP_TYPES if self.event.event_type == "production" else CONTOUR_GROUP_TYPES
        self.add_group_combo.addItem("+ Добавить тип бурения", "")
        for key, name in catalogue.items(): self.add_group_combo.addItem(name, key)
        self.add_group_combo.activated.connect(self._add_group); self.drilling_layout.addWidget(self.add_group_combo)

    def _render_groups(self):
        while self.group_cards_layout.count():
            item = self.group_cards_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for group in self.revision.drilling_groups:
            box = QGroupBox(f"{group.name} — {group.group_type}"); form = QFormLayout(box)
            name = QLineEdit(group.name); holes = _number(group.hole_count); depth = _number(group.average_depth_m, "м")
            burden = _number(group.burden_m, "м"); spacing = _number(group.spacing_m, "м"); diameter = _number(group.diameter_mm, "мм")
            for label, widget in (("Название", name), ("Скважин", holes), ("Глубина", depth), ("ЛНС", burden), ("Расстояние", spacing), ("Диаметр", diameter)): form.addRow(label, widget)
            name.textChanged.connect(lambda value, g=group: setattr(g, "name", value))
            for widget, attr, integer in ((holes,"hole_count",True),(depth,"average_depth_m",False),(burden,"burden_m",False),(spacing,"spacing_m",False),(diameter,"diameter_mm",False)):
                widget.valueChanged.connect(lambda value, g=group, a=attr, i=integer, w=widget: setattr(g, a, None if value == w.minimum() else (int(value) if i else value)))
            actions = QHBoxLayout(); duplicate = QPushButton("Дублировать"); remove = QPushButton("Удалить")
            duplicate.clicked.connect(lambda _=False, g=group: self._duplicate(g)); remove.clicked.connect(lambda _=False, g=group: self._remove(g))
            actions.addWidget(duplicate); actions.addWidget(remove); form.addRow(actions); self.group_cards_layout.addWidget(box)

    def _add_group(self, index):
        kind = self.add_group_combo.itemData(index)
        if not kind: return
        catalogue = PRODUCTION_GROUP_TYPES if self.event.event_type == "production" else CONTOUR_GROUP_TYPES
        group = BlastDrillingGroup(group_type=kind, name=catalogue[kind], sequence_order=len(self.revision.drilling_groups)+1)
        if kind == "other": group.custom_type_name = "Другой тип"
        self.revision.drilling_groups.append(group); self.add_group_combo.setCurrentIndex(0); self._render_groups()

    def _duplicate(self, group):
        from copy import deepcopy
        from uuid import uuid4
        copy = deepcopy(group); copy.id = f"DG-{uuid4().hex}"; copy.name += " (копия)"; copy.sequence_order = len(self.revision.drilling_groups)+1
        self.revision.drilling_groups.append(copy); self._render_groups()

    def _remove(self, group):
        try: self.card.remove_group(self.revision, group.id)
        except ValueError as exc: QMessageBox.warning(self, "Удаление", str(exc)); return
        self._render_groups()

    def _method_changed(self):
        if self.method.currentData(): self.revision.contour_parameters.set_method(self.method.currentData())

    def _actual_tab(self):
        layout = self._scroll_tab("Факт"); execution = QGroupBox("Фактическое исполнение"); form = QFormLayout(execution)
        self.completion_status = QComboBox()
        for key, name in (("planned","Запланировано"),("drilling","Бурение"),("charged","Заряжено"),("blasted","Взорвано"),("completed","Завершено"),("rejected","Отклонено")): self.completion_status.addItem(name,key)
        self.completion_status.setCurrentIndex(self.completion_status.findData(self.revision.actual_execution.completion_status)); form.addRow("Статус", self.completion_status); layout.addWidget(execution)

    def _history_tab(self):
        layout = self._scroll_tab("История ревизий"); table = QTableWidget(len(self.card.revisions), 5); table.setHorizontalHeaderLabels(["№", "Дата", "Статус", "Ревизия геометрии", "Причина"])
        for row, revision in enumerate(self.card.revisions):
            for col, value in enumerate((revision.revision_number, revision.created_at.isoformat(sep=" ", timespec="minutes"), revision.status, revision.geometry_revision_id, revision.change_reason)): table.setItem(row,col,QTableWidgetItem(str(value)))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.horizontalHeader().setStretchLastSection(True); layout.addWidget(table)

    def _save(self, status):
        self.revision.common_parameters.block_name = self.block_name.text(); self.revision.common_parameters.comments = self.comments.text()
        if self.revision.production_parameters:
            p=self.revision.production_parameters; p.design_bench_height_m=None if self.bench_height.value()==self.bench_height.minimum() else self.bench_height.value(); p.total_explosive_mass_kg=None if self.explosive.value()==self.explosive.minimum() else self.explosive.value()
            g=self.revision.geomechanical_parameters; g.rock_strength_class_text=self.strength_class.text(); g.representative_ucs_mpa=None if self.ucs.value()==self.ucs.minimum() else self.ucs.value(); g.rqd_representative_percent=None if self.rqd.value()==self.rqd.minimum() else self.rqd.value(); g.rock_mass_properties_text=self.rock_properties.text()
        self.revision.actual_execution.completion_status=self.completion_status.currentData()
        try: self.save_callback(self.card, self.revision, status)
        except ValueError as exc: QMessageBox.warning(self, "Проверка карточки", str(exc)); return
        self.accept()
