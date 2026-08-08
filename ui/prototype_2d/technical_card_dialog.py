"""Scrollable editor for versioned BlastEvent technical cards."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QDialog, QDoubleSpinBox, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QTabWidget,
    QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QInputDialog)

from prototype_2d.technical_card import (CONTOUR_GROUP_TYPES, CONTROLLED_BLASTING_METHODS,
    PRODUCTION_GROUP_TYPES, ActualDrillingGroup, BlastDrillingGroup)

BURDEN_LABEL = "ЛНС / расстояние между рядами, м"
BURDEN_TOOLTIP = "Линия наименьшего сопротивления. Для сетки рядов обычно соответствует расстоянию между рядами или расстоянию первого ряда до свободной поверхности."
SPACING_LABEL = "Шаг скважин в ряду, м"
SPACING_TOOLTIP = "Расстояние между соседними скважинами в одном ряду."
TOE_LABEL = "Расстояние последнего ряда до проектного контура, м"


def _number(value, suffix=""):
    widget = QDoubleSpinBox(); widget.setRange(-1_000_000_000, 1_000_000_000); widget.setDecimals(3)
    widget.setSpecialValueText("—"); widget.setValue(value if value is not None else widget.minimum())
    if suffix: widget.setSuffix(f" {suffix}")
    return widget


class TechnicalCardDialog(QDialog):
    def __init__(self, event, card, revision, save_callback, parent=None, read_only=False):
        # QDialog already has an event() method used internally by Qt.  Do not
        # shadow it with the BlastEvent model, otherwise showing the dialog
        # fails with: "BlastEvent object is not callable".
        super().__init__(parent); self.blast_event, self.card, self.revision = event, card, revision
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
        form.addRow("BlastEvent ID", QLabel(self.blast_event.id)); form.addRow("Geometry revision ID", QLabel(self.revision.geometry_revision_id))
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
        identity = QGroupBox("Порода и геотехнический контекст"); form = QFormLayout(identity)
        self.lithology = QLineEdit(geo.lithology); self.geotechnical_domain = QLineEdit(geo.geotechnical_domain)
        form.addRow("Литология", self.lithology); form.addRow("Геотехнический домен", self.geotechnical_domain); layout.addWidget(identity)
        strength = QGroupBox("Прочность массива"); form = QFormLayout(strength)
        self.strength_class = QLineEdit(geo.rock_strength_class_text); self.ucs = _number(geo.representative_ucs_mpa, "МПа"); self.ucs_min = _number(geo.ucs_min_mpa,"МПа"); self.ucs_max = _number(geo.ucs_max_mpa,"МПа")
        form.addRow("Локальный класс прочности", self.strength_class); form.addRow("Представительный UCS", self.ucs); form.addRow("Минимальный UCS",self.ucs_min); form.addRow("Максимальный UCS",self.ucs_max); layout.addWidget(strength)
        quality = QGroupBox("Качество массива"); form = QFormLayout(quality)
        self.rqd = _number(geo.rqd_representative_percent, "%"); self.rqd_min=_number(geo.rqd_min_percent,"%"); self.rqd_max=_number(geo.rqd_max_percent,"%"); self.rock_properties = QLineEdit(geo.rock_mass_properties_text); self.fracturing=QLineEdit(geo.fracturing_description); self.water=QLineEdit(geo.water_condition); self.geo_notes=QTextEdit(geo.geomechanical_notes)
        form.addRow("Представительный RQD", self.rqd); form.addRow("Минимальный RQD",self.rqd_min); form.addRow("Максимальный RQD",self.rqd_max); form.addRow("Описание свойств массива", self.rock_properties); form.addRow("Трещиноватость",self.fracturing); form.addRow("Водные условия",self.water); form.addRow("Геомеханические примечания",self.geo_notes); layout.addWidget(quality)

    def _drilling_tab(self, title):
        self.drilling_layout = self._scroll_tab(title); self.group_cards = QWidget(); self.group_cards_layout = QVBoxLayout(self.group_cards)
        self.drilling_layout.addWidget(self.group_cards); self._render_groups()
        self.add_group_combo = QComboBox(); catalogue = PRODUCTION_GROUP_TYPES if self.blast_event.event_type == "production" else CONTOUR_GROUP_TYPES
        self.add_group_combo.addItem("+ Добавить тип бурения", "")
        for key, name in catalogue.items(): self.add_group_combo.addItem(name, key)
        self.add_group_combo.activated.connect(self._add_group); self.drilling_layout.addWidget(self.add_group_combo)

    def _render_groups(self):
        while self.group_cards_layout.count():
            item = self.group_cards_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        for group in self.revision.drilling_groups:
            box = QGroupBox(f"{group.name} — {group.group_type}"); box.setCheckable(True); box.setChecked(True)
            outer = QVBoxLayout(box); identity = QFormLayout(); outer.addLayout(identity)
            name = QLineEdit(group.name); identity.addRow("Название", name); name.textChanged.connect(lambda value, g=group: setattr(g, "name", value))
            pattern = QGroupBox("Сетка бурения"); pattern.setCheckable(True); pattern.setChecked(True); form = QFormLayout(pattern)
            fields = (("Скважин, шт", "hole_count", "", True), ("Диаметр, мм", "diameter_mm", "", False),
                ("Средняя глубина, м", "average_depth_m", "", False), ("Перебур, м", "subdrill_m", "", False),
                (BURDEN_LABEL, "burden_m", "", False), (SPACING_LABEL, "spacing_m", "", False),
                ("Число рядов", "row_count", "", True), ("Наклон, °", "inclination_deg", "", False),
                ("Азимут, °", "azimuth_deg", "", False), ("Смещение линии, м", "line_offset_m", "", False),
                (TOE_LABEL, "toe_standoff_m", "", False), ("Проектный метраж бурения (переопределение), м", "planned_drilling_length_m", "", False))
            for label, attr, suffix, integer in fields: self._add_number(form, label, group, attr, suffix, integer)
            outer.addWidget(pattern)
            charging = QGroupBox("Заряжание"); charging.setCheckable(True); charging.setChecked(False); charge_form = QFormLayout(charging)
            for label, attr, suffix, integer in (("Масса заряда на скважину, кг","charge_mass_per_hole_kg","",False),
                ("Концентрация заряда, кг/м","charge_concentration_kg_per_m","",False),("Общая масса заряда, кг","total_charge_mass_kg","",False),
                ("Длина забойки, м","stemming_length_m","",False),("Замедление, мс","delay_ms","",False),("Воздушные промежутки","air_deck_count","",True)):
                self._add_number(charge_form,label,group,attr,suffix,integer)
            for label, attr in (("Тип ВВ","explosive_type"),("Конструкция заряда","charge_construction_text"),("Схема инициирования","initiation_sequence"),("Примечания по дэкам","deck_notes")):
                edit=QLineEdit(getattr(group,attr)); edit.textChanged.connect(lambda v,g=group,a=attr:setattr(g,a,v)); charge_form.addRow(label,edit)
            outer.addWidget(charging)
            actions = QHBoxLayout(); duplicate = QPushButton("Дублировать"); remove = QPushButton("Удалить")
            duplicate.clicked.connect(lambda _=False, g=group: self._duplicate(g)); remove.clicked.connect(lambda _=False, g=group: self._remove(g))
            actions.addWidget(duplicate); actions.addWidget(remove); outer.addLayout(actions); self.group_cards_layout.addWidget(box)

    def _add_number(self, form, label, model, attr, suffix="", integer=False):
        widget = _number(getattr(model, attr), suffix); widget.setObjectName(attr)
        if attr == "burden_m": widget.setToolTip(BURDEN_TOOLTIP)
        if attr == "spacing_m": widget.setToolTip(SPACING_TOOLTIP)
        widget.valueChanged.connect(lambda value, m=model, a=attr, i=integer, w=widget:
            setattr(m, a, None if value == w.minimum() else (int(value) if i else value)))
        form.addRow(label, widget); return widget

    def _add_group(self, index):
        kind = self.add_group_combo.itemData(index)
        if not kind: return
        catalogue = PRODUCTION_GROUP_TYPES if self.blast_event.event_type == "production" else CONTOUR_GROUP_TYPES
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
        layout = self._scroll_tab("Факт"); execution = QGroupBox("A. Статус выполнения"); form = QFormLayout(execution)
        self.completion_status = QComboBox()
        for key, name in (("planned","Запланировано"),("drilling","Бурение"),("charged","Заряжено"),("blasted","Взорвано"),("completed","Завершено"),("rejected","Отклонено")): self.completion_status.addItem(name,key)
        actual=self.revision.actual_execution; self.completion_status.setCurrentIndex(self.completion_status.findData(actual.completion_status)); form.addRow("Статус", self.completion_status)
        self.actual_date=QLineEdit(actual.actual_blast_date or ""); self.execution_notes=QTextEdit(actual.execution_notes); self.execution_notes.setMaximumHeight(70)
        form.addRow("Фактическая дата взрыва (ГГГГ-ММ-ДД)",self.actual_date); form.addRow("Общие примечания",self.execution_notes); layout.addWidget(execution)
        summary=QGroupBox("B. Общие фактические показатели"); grid=QFormLayout(summary); self.actual_summary_widgets={}
        for label,attr in (("Фактическая площадь, м²","actual_drilling_area_m2"),("Принятый объём блока, м³","actual_block_volume_m3"),
            ("Всего скважин, шт","actual_total_hole_count"),("Общий метраж бурения, м","actual_total_drilling_length_m"),
            ("Общая масса ВВ, кг","actual_total_explosive_mass_kg"),("Средняя глубина, м","actual_average_depth_m"),
            ("Выход горной массы, м³/м","actual_rock_yield_m3_per_drilling_m"),("Удельное бурение, м/м³","actual_specific_drilling_m_per_m3"),
            ("Удельный расход ВВ, кг/м³","actual_powder_factor_kg_per_m3"),("Забраковано, шт","rejected_hole_count"),
            ("Перебурено, шт","redrilled_hole_count"),("Обводнено, шт","wet_hole_count"),("Не заряжено, шт","uncharged_hole_count")):
            self.actual_summary_widgets[attr]=self._add_number(grid,label,actual,attr)
        layout.addWidget(summary)
        controls=QHBoxLayout(); copy_all=QPushButton("Заполнить факт по проекту"); copy_all.setObjectName("copyProjectToActualButton")
        add=QPushButton("+ Добавить фактическую группу"); copy_all.clicked.connect(self._copy_all_actual); add.clicked.connect(self._add_actual_group)
        controls.addWidget(copy_all); controls.addWidget(add); controls.addStretch(); layout.addLayout(controls)
        section=QGroupBox("C. Фактические группы бурения и зарядки"); self.actual_cards_layout=QVBoxLayout(section); layout.addWidget(section)
        comparison=QGroupBox("D. Сравнение проект / факт"); comparison_layout=QVBoxLayout(comparison)
        self.comparison_table=QTableWidget(); self.comparison_table.setObjectName("projectActualComparisonTable"); comparison_layout.addWidget(self.comparison_table); layout.addWidget(comparison)
        self._render_actual_groups(); self._refresh_actual_summary()

    def _render_actual_groups(self):
        while self.actual_cards_layout.count():
            item=self.actual_cards_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        designs={g.id:g for g in self.revision.drilling_groups}
        for group in self.revision.actual_execution.actual_drilling_groups:
            design=designs.get(group.design_group_id); flags=[]
            if group.copied_from_design: flags.append("Скопировано из проекта")
            if group.design_group_id is None: flags.append("Не предусмотрено проектом")
            box=QGroupBox(f"{group.name} — {group.group_type}" + (f"  [{'; '.join(flags)}]" if flags else "")); box.setCheckable(True); box.setChecked(True)
            outer=QVBoxLayout(box); outer.addWidget(QLabel(f"Связанная проектная группа: {design.name if design else '—'}"))
            drilling=QGroupBox("Бурение"); f=QFormLayout(drilling)
            for label,attr,integer in (("Скважин, шт","hole_count",True),("Диаметр, мм","diameter_mm",False),("Средняя глубина, м","average_depth_m",False),
                ("Перебур, м","subdrill_m",False),(BURDEN_LABEL,"burden_m",False),(SPACING_LABEL,"spacing_m",False),("Число рядов","row_count",True),
                ("Наклон, °","inclination_deg",False),("Азимут, °","azimuth_deg",False),("Метраж бурения, м","drilling_length_m",False),
                (TOE_LABEL,"toe_standoff_m",False),("Забраковано, шт","rejected_hole_count",True),("Перебурено, шт","redrilled_hole_count",True),("Обводнено, шт","wet_hole_count",True)):
                self._add_number(f,label,group,attr,integer=integer)
            outer.addWidget(drilling); charging=QGroupBox("Заряжание"); cf=QFormLayout(charging)
            for label,attr,integer in (("Масса на скважину, кг","charge_mass_per_hole_kg",False),("Концентрация, кг/м","charge_concentration_kg_per_m",False),
                ("Общая масса, кг","total_charge_mass_kg",False),("Забойка, м","stemming_length_m",False),("Замедление, мс","delay_ms",False),
                ("Воздушные промежутки","air_deck_count",True),("Не заряжено, шт","uncharged_hole_count",True)):
                self._add_number(cf,label,group,attr,integer=integer)
            for label,attr in (("Тип ВВ","explosive_type"),("Конструкция заряда","charge_construction_text"),("Инициирование","initiation_sequence"),("Примечания по дэкам","deck_notes")):
                edit=QLineEdit(getattr(group,attr)); edit.textChanged.connect(lambda v,g=group,a=attr:setattr(g,a,v)); cf.addRow(label,edit)
            outer.addWidget(charging); deviation=QGroupBox("Отклонения"); df=QFormLayout(deviation)
            for label,attr in (("Описание отклонений","deviations_text"),("Примечания","notes")):
                edit=QLineEdit(getattr(group,attr)); edit.textChanged.connect(lambda v,g=group,a=attr:setattr(g,a,v)); df.addRow(label,edit)
            outer.addWidget(deviation); actions=QHBoxLayout(); copy=QPushButton("Скопировать из проекта"); duplicate=QPushButton("Дублировать"); remove=QPushButton("Удалить")
            copy.setEnabled(design is not None); copy.clicked.connect(lambda _=False,d=design,a=group:self._copy_one_actual(d,a)); duplicate.clicked.connect(lambda _=False,g=group:self._duplicate_actual(g)); remove.clicked.connect(lambda _=False,g=group:self._remove_actual(g))
            for button in (copy,duplicate,remove): actions.addWidget(button)
            outer.addLayout(actions); self.actual_cards_layout.addWidget(box)
        self._render_comparison()

    def _copy_all_actual(self):
        actual=self.revision.actual_execution
        if not actual.actual_drilling_groups:
            if QMessageBox.question(self,"Копирование проекта","Создать независимый снимок проектных групп в факте?") != QMessageBox.StandardButton.Yes: return
            mode="replace"
        else:
            labels=["Заполнить только пустые поля","Добавить отсутствующие группы","Полностью заменить факт по проекту","Отмена"]
            choice,ok=QInputDialog.getItem(self,"Копирование проекта","Выберите безопасный режим копирования:",labels,0,False)
            if not ok or choice=="Отмена": return
            mode={labels[0]:"fill_empty",labels[1]:"add_missing",labels[2]:"replace"}[choice]
            if mode=="replace" and QMessageBox.warning(self,"Замена факта","Все введённые фактические параметры будут заменены проектными значениями.",QMessageBox.StandardButton.Ok|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)!=QMessageBox.StandardButton.Ok: return
        actual.copy_from_design(self.revision.drilling_groups,self.revision.id or None,mode); self._render_actual_groups(); self._refresh_actual_summary()

    def _copy_one_actual(self, design, actual):
        if design is None: return
        labels=["Заполнить только пустые поля","Заменить группу","Отмена"]
        choice,ok=QInputDialog.getItem(self,"Скопировать из проекта","Фактические значения уже могут быть заполнены:",labels,0,False)
        if not ok or choice==labels[2]: return
        mode="fill_empty" if choice==labels[0] else "replace"
        self.revision.actual_execution.copy_one(design,actual,self.revision.id or None,mode)
        self.revision.actual_execution.recalculate(); self._render_actual_groups(); self._refresh_actual_summary()

    def _add_actual_group(self):
        catalogue=PRODUCTION_GROUP_TYPES if self.blast_event.event_type=="production" else CONTOUR_GROUP_TYPES
        names=list(catalogue.values()); choice,ok=QInputDialog.getItem(self,"Фактическая группа","Тип группы:",names,0,False)
        if not ok:return
        kind=next(k for k,v in catalogue.items() if v==choice)
        self.revision.actual_execution.actual_drilling_groups.append(ActualDrillingGroup(design_group_id=None,group_type=kind,name=choice,sequence_order=len(self.revision.actual_execution.actual_drilling_groups)+1))
        self._render_actual_groups(); self._refresh_actual_summary()

    def _duplicate_actual(self, group):
        from copy import deepcopy
        from uuid import uuid4
        copied=deepcopy(group); copied.id=f"AG-{uuid4().hex}"; copied.design_group_id=None; copied.copied_from_design=False; copied.copied_from_technical_revision_id=None; copied.copied_at=None; copied.name += " (копия)"
        self.revision.actual_execution.actual_drilling_groups.append(copied); self._render_actual_groups()

    def _remove_actual(self, group):
        self.revision.actual_execution.actual_drilling_groups.remove(group); self._render_actual_groups(); self._refresh_actual_summary()

    def _refresh_actual_summary(self):
        actual=self.revision.actual_execution; actual.recalculate()
        for attr,widget in self.actual_summary_widgets.items():
            value=getattr(actual,attr); widget.blockSignals(True); widget.setValue(value if value is not None else widget.minimum()); widget.blockSignals(False)
        self._render_comparison()

    def _render_comparison(self):
        if not hasattr(self,"comparison_table"): return
        rows=self.revision.comparison_rows(); table=self.comparison_table; table.setRowCount(len(rows)); table.setColumnCount(6)
        table.setHorizontalHeaderLabels(["Группа","Параметр","Проект","Факт","Абсолютное отклонение","Относительное отклонение, %"])
        def display(value,unit=""): return "—" if value is None else f"{value:g} {unit}".strip()
        for row,data in enumerate(rows):
            values=(data["group"],data["parameter"],display(data["project"],data["unit"]),display(data["actual"],data["unit"]),display(data["absolute_deviation"],data["unit"]),display(data["relative_deviation_percent"],"%"))
            for column,value in enumerate(values): table.setItem(row,column,QTableWidgetItem(value))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.resizeColumnsToContents()

    def _history_tab(self):
        layout = self._scroll_tab("История ревизий"); table = QTableWidget(len(self.card.revisions), 5); table.setHorizontalHeaderLabels(["№", "Дата", "Статус", "Ревизия геометрии", "Причина"])
        for row, revision in enumerate(self.card.revisions):
            for col, value in enumerate((revision.revision_number, revision.created_at.isoformat(sep=" ", timespec="minutes"), revision.status, revision.geometry_revision_id, revision.change_reason)): table.setItem(row,col,QTableWidgetItem(str(value)))
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.horizontalHeader().setStretchLastSection(True); layout.addWidget(table)

    def _save(self, status):
        if self.read_only:
            QMessageBox.warning(self, "Read only", "Archived entities and Viewer accounts cannot change the Technical Card.")
            return False
        self.revision.common_parameters.block_name = self.block_name.text(); self.revision.common_parameters.comments = self.comments.text()
        if self.revision.production_parameters:
            p=self.revision.production_parameters; p.design_bench_height_m=None if self.bench_height.value()==self.bench_height.minimum() else self.bench_height.value(); p.total_explosive_mass_kg=None if self.explosive.value()==self.explosive.minimum() else self.explosive.value()
            g=self.revision.geomechanical_parameters; g.lithology=self.lithology.text(); g.geotechnical_domain=self.geotechnical_domain.text(); g.rock_strength_class_text=self.strength_class.text(); g.representative_ucs_mpa=None if self.ucs.value()==self.ucs.minimum() else self.ucs.value(); g.ucs_min_mpa=None if self.ucs_min.value()==self.ucs_min.minimum() else self.ucs_min.value(); g.ucs_max_mpa=None if self.ucs_max.value()==self.ucs_max.minimum() else self.ucs_max.value(); g.rqd_representative_percent=None if self.rqd.value()==self.rqd.minimum() else self.rqd.value(); g.rqd_min_percent=None if self.rqd_min.value()==self.rqd_min.minimum() else self.rqd_min.value(); g.rqd_max_percent=None if self.rqd_max.value()==self.rqd_max.minimum() else self.rqd_max.value(); g.rock_mass_properties_text=self.rock_properties.text(); g.fracturing_description=self.fracturing.text(); g.water_condition=self.water.text(); g.geomechanical_notes=self.geo_notes.toPlainText()
        actual=self.revision.actual_execution; actual.completion_status=self.completion_status.currentData(); actual.actual_blast_date=self.actual_date.text().strip() or None; actual.execution_notes=self.execution_notes.toPlainText(); actual.recalculate()
        warnings=actual.completion_warnings()
        if warnings: QMessageBox.warning(self,"Фактическое исполнение","Карточка будет сохранена. Предупреждения:\n• " + "\n• ".join(warnings))
        try: self.save_callback(self.card, self.revision, status)
        except ValueError as exc: QMessageBox.warning(self, "Проверка карточки", str(exc)); return False
        except Exception as exc:
            QMessageBox.critical(self, "Техническая карточка", f"Не удалось сохранить изменения. Данные остаются в форме.\n\n{exc}")
            return False
        self.accept(); return True
