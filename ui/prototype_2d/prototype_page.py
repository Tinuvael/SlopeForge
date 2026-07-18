from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QDoubleSpinBox, QSplitter, QTextEdit, QToolButton, QVBoxLayout, QWidget)

from prototype_2d.connectivity import LineConnection, build_endpoint_connections
from prototype_2d.csv_importer import DatamineCsvError, detect_columns, import_datamine_csv, missing_required, read_text, sniff_delimiter
from prototype_2d.geometry import line_length, nearest_point_on_polyline
from prototype_2d.models import DatamineLine, LineSegmentSelection, PrototypeState
from prototype_2d.storage import load_state, save_state
from .bench_creation_controller import BenchCreationController, BenchWorkflowState, segment_length
from .dialogs import ColumnMappingDialog
from .plan_scene import PrototypePlanScene
from .plan_view import PrototypePlanView


class Prototype2DPage(QWidget):
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = PrototypeState()
        self.controller = BenchCreationController()
        self.connections: list[LineConnection] = []
        self.scene = PrototypePlanScene(); self.view = PrototypePlanView(self.scene)
        self.scene.line_clicked.connect(self.on_line_clicked); self.scene.line_hovered.connect(self.on_line_hovered); self.scene.marker_moved.connect(self.on_marker_moved); self.view.cursor_moved.connect(self.on_cursor)
        self.coord_label = QLabel("X: — Y: —")
        self.delimiter_combo = QComboBox(); self.delimiter_combo.addItems(["Auto", "comma", "semicolon", "tab"])
        self.horizon_combo = QComboBox(); self.horizon_combo.addItem("Все отметки"); self.horizon_combo.currentIndexChanged.connect(self.refresh_scene)
        self.only_horizon_check = QCheckBox("Только рабочий горизонт"); self.only_horizon_check.toggled.connect(self.refresh_scene)
        self.grid_check = QCheckBox("Сетка"); self.grid_check.setChecked(True); self.grid_check.toggled.connect(self.toggle_grid)
        self.create_bench_button = QPushButton("Создать сегмент уступа"); self.create_bench_button.clicked.connect(self.start_bench_workflow)
        self.workflow_title = QLabel("Создание сегмента уступа"); self.workflow_step = QLabel("Готово к работе"); self.workflow_instruction = QLabel("Импортируйте CSV и нажмите «Создать сегмент уступа»."); self.workflow_instruction.setWordWrap(True)
        self.workflow_selected = QTextEdit(); self.workflow_selected.setReadOnly(True); self.workflow_selected.setMaximumHeight(150)
        self.primary_button = QPushButton("Создать сегмент уступа"); self.primary_button.clicked.connect(self.primary_action)
        self.retry_button = QPushButton("Выбрать заново"); self.retry_button.clicked.connect(self.retry_current_segment)
        self.back_button = QPushButton("Назад"); self.back_button.clicked.connect(self.go_back)
        self.cancel_button = QPushButton("Отмена"); self.cancel_button.clicked.connect(self.cancel_workflow)
        self.line_info = QTextEdit(); self.line_info.setReadOnly(True); self.line_info.setMaximumHeight(110)
        self.draft_list = QListWidget(); self.draft_list.currentRowChanged.connect(self.on_draft_selected)
        self.draft_details = QTextEdit(); self.draft_details.setReadOnly(True); self.draft_details.setMaximumHeight(140)
        self.add_intermediate_button = QPushButton("Добавить промежуточный сегмент"); self.add_intermediate_button.clicked.connect(self.start_intermediate_workflow)
        self.edit_button = QPushButton("Редактировать"); self.edit_button.setEnabled(False)
        self.delete_bench_button = QPushButton("Удалить"); self.delete_bench_button.clicked.connect(self.delete_selected_bench)
        self.advanced_toggle = QToolButton(); self.advanced_toggle.setText("Дополнительно"); self.advanced_toggle.setCheckable(True); self.advanced_toggle.setChecked(False); self.advanced_toggle.toggled.connect(self.toggle_advanced)
        self.advanced_box = QGroupBox("Дополнительно"); self.advanced_box.setVisible(False)
        self.assigned_type_edit = QLineEdit(); self.assigned_type_edit.editingFinished.connect(self.update_assigned_type)
        self.auto_connect_check = QCheckBox("Автосвязь концов"); self.auto_connect_check.toggled.connect(self.toggle_auto_connect)
        self.connection_tolerance = QDoubleSpinBox(); self.connection_tolerance.setRange(0.01, 1000); self.connection_tolerance.setValue(1.0); self.connection_tolerance.setSuffix(" м"); self.connection_tolerance.setEnabled(False); self.connection_tolerance.setToolTip("Максимальное расстояние между концами двух линий, при котором они считаются связанными. Не используется при обычном выборе сегмента внутри одной линии")
        self.show_connections_check = QCheckBox("Показать связи"); self.show_connections_check.toggled.connect(self.refresh_scene)
        self.connection_list = QListWidget()
        self.build_layout(); self.update_workflow_panel()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def build_layout(self):
        root = QVBoxLayout(self)
        top = QHBoxLayout(); root.addLayout(top)
        file_group = QGroupBox("Файл"); file_layout = QHBoxLayout(file_group)
        for text, cb in [("Импорт", self.import_csv), ("Сохранить", self.save), ("Загрузить", self.load), ("Очистить", self.clear), ("Закрыть", self.close_requested.emit)]:
            button = QPushButton(text); button.clicked.connect(cb); file_layout.addWidget(button)
        view_group = QGroupBox("Вид"); view_layout = QHBoxLayout(view_group)
        fit = QPushButton("Fit to extent"); fit.clicked.connect(self.view.fit_to_extent); view_layout.addWidget(fit); view_layout.addWidget(QLabel("Рабочий горизонт")); view_layout.addWidget(self.horizon_combo); view_layout.addWidget(self.only_horizon_check); view_layout.addWidget(self.grid_check)
        action_group = QGroupBox("Основное действие"); action_layout = QHBoxLayout(action_group); action_layout.addWidget(self.create_bench_button)
        top.addWidget(file_group); top.addWidget(view_group); top.addWidget(action_group); top.addWidget(self.coord_label)
        splitter = QSplitter(); root.addWidget(splitter, 1); splitter.addWidget(self.view)
        panel = QWidget(); panel_layout = QVBoxLayout(panel); splitter.addWidget(panel)
        workflow = QGroupBox("Создание сегмента уступа"); wf = QVBoxLayout(workflow); wf.addWidget(self.workflow_step); wf.addWidget(self.workflow_instruction); wf.addWidget(self.workflow_selected); wf.addWidget(self.primary_button); wf.addWidget(self.retry_button); nav = QHBoxLayout(); nav.addWidget(self.back_button); nav.addWidget(self.cancel_button); wf.addLayout(nav); panel_layout.addWidget(workflow)
        info = QGroupBox("Информация о выбранной линии"); info_layout = QVBoxLayout(info); info_layout.addWidget(self.line_info); panel_layout.addWidget(info)
        benches = QGroupBox("Черновики уступов"); b = QVBoxLayout(benches); b.addWidget(self.draft_list); b.addWidget(self.draft_details); b.addWidget(self.add_intermediate_button); row = QHBoxLayout(); row.addWidget(self.edit_button); row.addWidget(self.delete_bench_button); b.addLayout(row); panel_layout.addWidget(benches)
        panel_layout.addWidget(self.advanced_toggle); adv = QFormLayout(self.advanced_box); adv.addRow("Разделитель CSV", self.delimiter_combo); adv.addRow("Назначенный TYPE", self.assigned_type_edit); adv.addRow("", self.auto_connect_check); adv.addRow("Допуск автосвязи концов, м", self.connection_tolerance); adv.addRow("", self.show_connections_check); rebuild = QPushButton("Перестроить связи"); rebuild.clicked.connect(self.rebuild_connections); adv.addRow(rebuild); adv.addRow("Связи", self.connection_list); panel_layout.addWidget(self.advanced_box); panel_layout.addStretch(1)

    def find_line(self, line_id: str | None) -> DatamineLine | None:
        return next((line for line in self.state.lines if line.source_id == line_id), None)

    def active_elevation(self) -> float | None:
        if self.horizon_combo.currentIndex() <= 0 or self.horizon_combo.currentText() == "Переменные линии": return None
        return float(self.horizon_combo.currentText())

    def visible_lines(self):
        return self.state.lines

    def refresh_scene(self):
        self.scene.set_lines(self.visible_lines(), self.active_elevation(), self.only_horizon_check.isChecked())
        self.scene.set_active_line(self.controller.active_line_id)
        self.scene.show_segments(self.state.segments + [s for s in [self.controller.lower.segment, self.controller.upper.segment, self.controller.intermediate.segment] if s])
        self.scene.set_selected_line(self.controller.selected_line_id)
        draft = self.controller.current_draft(); line = self.find_line(self.controller.active_line_id)
        if draft and line: self.scene.show_segment_preview(line, draft.start_position, draft.end_position)
        if self.show_connections_check.isChecked(): self.scene.show_connections(self.connections)

    def refresh_lists(self):
        self.horizon_combo.blockSignals(True); cur = self.horizon_combo.currentText(); self.horizon_combo.clear(); self.horizon_combo.addItem("Все отметки"); self.horizon_combo.addItems([str(e) for e in self.state.elevations()])
        if any(not line.is_horizontal for line in self.state.lines): self.horizon_combo.addItem("Переменные линии")
        values = [self.horizon_combo.itemText(i) for i in range(self.horizon_combo.count())]; self.horizon_combo.setCurrentText(cur if cur in values else "Все отметки"); self.horizon_combo.blockSignals(False)
        self.draft_list.clear(); self.draft_list.addItems([self.draft_caption(d) for d in self.state.drafts]); self.refresh_connections_list()

    def draft_caption(self, d):
        segs = {s.id: s for s in self.state.segments}; up = segs.get(d.upper_segment_id); low = segs.get(d.lower_segment_id)
        return f"{d.id} · верх {up.elevation if up else '—'} · низ {low.elevation if low else '—'}"

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "CSV Datamine", "", "CSV (*.csv)")
        if not path: return
        try:
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            text, _encoding = read_text(Path(path)); delimiter_choice = self.delimiter_combo.currentText(); delimiter = sniff_delimiter(text, delimiter_choice)
            headers = csv.DictReader(text.splitlines(), delimiter=delimiter).fieldnames or []; mapping = detect_columns(headers)
            if missing_required(mapping):
                QGuiApplication.restoreOverrideCursor(); dlg = ColumnMappingDialog(headers, self)
                if not dlg.exec(): return
                mapping = dlg.mapping(); QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            result = import_datamine_csv(path, mapping, delimiter_choice)
            self.state = PrototypeState(path, result.lines, [], []); self.controller.reset(); self.connections.clear()
            if self.auto_connect_check.isChecked(): self.rebuild_connections(show_message=False)
            self.refresh_lists(); self.refresh_scene(); self.view.fit_to_extent(); self.update_workflow_panel()
            QGuiApplication.restoreOverrideCursor(); QMessageBox.information(self, "Импорт Datamine", result.summary.to_text())
        except DatamineCsvError as exc:
            QGuiApplication.restoreOverrideCursor(); QMessageBox.warning(self, "Ошибка импорта", str(exc))
        except Exception as exc:
            QGuiApplication.restoreOverrideCursor(); QMessageBox.warning(self, "Ошибка импорта", f"Не удалось импортировать CSV: {exc}")

    def on_line_clicked(self, line_id, x, y):
        try:
            if self.controller.state in {BenchWorkflowState.SELECT_LOWER_LINE, BenchWorkflowState.SELECT_UPPER_LINE, BenchWorkflowState.ADD_INTERMEDIATE_SELECT_LINE}:
                candidates = self.scene.nearest_line_candidates(x, y)
                if len(candidates) > 1 and candidates[1][1] - candidates[0][1] < 3:
                    # Минимально: берём ближайшую; список кандидатов показываем в информационной карточке.
                    self.show_candidate_list(candidates)
                self.controller.choose_line(candidates[0][0] if candidates else line_id)
            elif self.controller.active_line_id:
                line = self.find_line(self.controller.active_line_id); _p, pos, _d = nearest_point_on_polyline(line, x, y); self.controller.add_marker(self.controller.active_line_id, pos)
            self.update_line_info(); self.update_workflow_panel(); self.refresh_scene()
        except ValueError as exc:
            QMessageBox.warning(self, "Workflow", str(exc))

    def on_line_hovered(self, x, y):
        draft = self.controller.current_draft(); line = self.find_line(self.controller.active_line_id)
        if draft and line and draft.start_position is not None and draft.end_position is None:
            _p, pos, _d = nearest_point_on_polyline(line, x, y); self.scene.show_segment_preview(line, draft.start_position, pos)

    def on_marker_moved(self, marker, x, y):
        line = self.find_line(self.controller.active_line_id)
        if not line: return
        _p, pos, _d = nearest_point_on_polyline(line, x, y); self.controller.update_marker(marker, line.source_id, pos); self.update_workflow_panel(); self.refresh_scene()

    def primary_action(self):
        try:
            st = self.controller.state
            if st == BenchWorkflowState.IDLE: self.start_bench_workflow(); return
            if st in {BenchWorkflowState.SELECT_LOWER_LINE, BenchWorkflowState.SELECT_UPPER_LINE, BenchWorkflowState.ADD_INTERMEDIATE_SELECT_LINE}: self.controller.use_selected_line()
            elif st in {BenchWorkflowState.CONFIRM_LOWER, BenchWorkflowState.CONFIRM_UPPER, BenchWorkflowState.ADD_INTERMEDIATE_CONFIRM}: self.confirm_segment()
            elif st == BenchWorkflowState.CONFIRM_BENCH: self.controller.create_bench(self.state); self.refresh_lists()
            elif st == BenchWorkflowState.BENCH_CREATED: self.start_intermediate_workflow(); return
            self.update_workflow_panel(); self.refresh_scene()
        except ValueError as exc:
            QMessageBox.warning(self, "Workflow", str(exc))

    def confirm_segment(self):
        line = self.find_line(self.controller.active_line_id)
        if not line: raise ValueError("Активная линия не найдена")
        segment = self.controller.confirm_current_segment(self.state, line)
        if segment.role == "intermediate_assessment": self.controller.add_intermediate_to_bench(self.state); self.refresh_lists()

    def start_bench_workflow(self): self.controller.start_bench(); self.update_workflow_panel(); self.refresh_scene()
    def start_intermediate_workflow(self):
        row = self.draft_list.currentRow(); bench_id = self.state.drafts[row].id if row >= 0 else self.controller.selected_bench_id
        try: self.controller.start_intermediate(bench_id); self.update_workflow_panel(); self.refresh_scene()
        except ValueError as exc: QMessageBox.warning(self, "Промежуточный сегмент", str(exc))

    def retry_current_segment(self):
        draft = self.controller.current_draft()
        if draft: draft.reset_points(); self.update_workflow_panel(); self.refresh_scene()
    def go_back(self): self.controller.back(); self.update_workflow_panel(); self.refresh_scene()
    def cancel_workflow(self):
        if self.controller.has_work_in_progress() and QMessageBox.question(self, "Отмена", "Отменить текущий workflow?") != QMessageBox.StandardButton.Yes: return
        self.controller.reset(); self.update_workflow_panel(); self.refresh_scene()

    def update_workflow_panel(self):
        st = self.controller.state; labels = {
            BenchWorkflowState.IDLE: ("Готово", "Импортируйте CSV и нажмите «Создать сегмент уступа».", "Создать сегмент уступа"),
            BenchWorkflowState.SELECT_LOWER_LINE: ("Шаг 1 из 5", "Выберите нижнюю линию уступа кликом на плане.", "Использовать эту линию"),
            BenchWorkflowState.SELECT_LOWER_START: ("Шаг 2 из 5", "Поставьте круглый маркер A — начало нижнего сегмента. Работа идёт только по активной линии.", "Ожидается маркер"),
            BenchWorkflowState.SELECT_LOWER_END: ("Шаг 2 из 5", "Поставьте маркер B — конец нижнего сегмента.", "Ожидается маркер"),
            BenchWorkflowState.CONFIRM_LOWER: ("Шаг 3 из 5", "Проверьте нижний сегмент и подтвердите.", "Подтвердить нижний сегмент"),
            BenchWorkflowState.SELECT_UPPER_LINE: ("Шаг 4 из 5", "Выберите верхнюю линию уступа.", "Использовать эту линию"),
            BenchWorkflowState.SELECT_UPPER_START: ("Шаг 4 из 5", "Поставьте маркер A — начало верхнего сегмента. Работа идёт только по активной линии.", "Ожидается маркер"),
            BenchWorkflowState.SELECT_UPPER_END: ("Шаг 4 из 5", "Поставьте маркер B — конец верхнего сегмента.", "Ожидается маркер"),
            BenchWorkflowState.CONFIRM_UPPER: ("Шаг 4 из 5", "Проверьте верхний сегмент и подтвердите.", "Подтвердить верхний сегмент"),
            BenchWorkflowState.CONFIRM_BENCH: ("Шаг 5 из 5", f"Проверьте итог. Будет создан {self.state.next_draft_id()}.", "Создать уступ"),
            BenchWorkflowState.BENCH_CREATED: ("U создан", "Уступ создан. Можно добавить промежуточный сегмент.", "Добавить промежуточный сегмент"),
            BenchWorkflowState.ADD_INTERMEDIATE_SELECT_LINE: ("Промежуточный 1 из 4", "Выберите линию промежуточного сегмента.", "Использовать эту линию"),
            BenchWorkflowState.ADD_INTERMEDIATE_START: ("Промежуточный 2 из 4", "Поставьте начало промежуточного сегмента.", "Ожидается маркер"),
            BenchWorkflowState.ADD_INTERMEDIATE_END: ("Промежуточный 3 из 4", "Поставьте конец промежуточного сегмента.", "Ожидается маркер"),
            BenchWorkflowState.ADD_INTERMEDIATE_CONFIRM: ("Промежуточный 4 из 4", "Подтвердите промежуточный сегмент для выбранного уступа.", "Добавить в уступ"),
        }
        step, instruction, primary = labels[st]; self.workflow_step.setText(step); self.workflow_instruction.setText(instruction); self.primary_button.setText(primary); self.primary_button.setEnabled(primary != "Ожидается маркер")
        self.retry_button.setVisible(st in {BenchWorkflowState.CONFIRM_LOWER, BenchWorkflowState.CONFIRM_UPPER, BenchWorkflowState.ADD_INTERMEDIATE_CONFIRM})
        self.workflow_selected.setText(self.workflow_summary())

    def workflow_summary(self) -> str:
        lines = []
        for label, draft in [("Нижний", self.controller.lower), ("Верхний", self.controller.upper), ("Промежуточный", self.controller.intermediate)]:
            if draft.segment: lines.append(f"{label}: SID {draft.segment.source_line_id}, Z {draft.segment.elevation if draft.segment.elevation is not None else 'var'}, длина {segment_length(draft.segment):.1f} м")
            elif draft.line_id: lines.append(f"{label}: активная линия {draft.line_id}")
        if self.controller.state == BenchWorkflowState.CONFIRM_BENCH: lines.insert(0, f"Название: {self.state.next_draft_id()}")
        return "\n".join(lines) if lines else "Пока ничего не выбрано."

    def update_line_info(self):
        line = self.find_line(self.controller.selected_line_id or self.controller.active_line_id)
        if not line: self.line_info.setText("Линия не выбрана."); return
        self.line_info.setText(f"SID: {line.source_id}\nsource TYPE: {line.source_type or '—'}\nassigned TYPE: {line.assigned_type or '—'}\nZ: {line.display_elevation()}\nДлина: {line_length(line):.1f} м")
        self.assigned_type_edit.setText(line.assigned_type or "")

    def show_candidate_list(self, candidates):
        text = []
        for line_id, distance in candidates:
            line = self.find_line(line_id); text.append(f"{line_id} · {line.source_type or '—'} · {line.display_elevation()} · {distance:.2f} м")
        self.line_info.setText("Близкие линии:\n" + "\n".join(text))

    def on_draft_selected(self, row):
        if row < 0: self.draft_details.clear(); return
        draft = self.state.drafts[row]; self.controller.selected_bench_id = draft.id; segs = {s.id: s for s in self.state.segments}
        self.draft_details.setText(f"{draft.id}\nНиз: {draft.lower_segment_id}\nВерх: {draft.upper_segment_id}\nПромежуточные: {', '.join(draft.intermediate_segment_ids)}\nКоличество: {2 + len(draft.intermediate_segment_ids)}")
        self.scene.show_segments([s for sid in [draft.lower_segment_id, draft.upper_segment_id, *draft.intermediate_segment_ids] if (s := segs.get(sid))])

    def delete_selected_bench(self):
        row = self.draft_list.currentRow()
        if row >= 0: del self.state.drafts[row]; self.refresh_lists(); self.refresh_scene()

    def update_assigned_type(self):
        line = self.find_line(self.controller.selected_line_id or self.controller.active_line_id)
        if line: line.assigned_type = self.assigned_type_edit.text() or None
    def toggle_advanced(self, checked): self.advanced_box.setVisible(checked)
    def toggle_auto_connect(self, checked): self.connection_tolerance.setEnabled(checked)
    def rebuild_connections(self, show_message=True):
        self.connections = build_endpoint_connections(self.state.lines, self.connection_tolerance.value()); self.refresh_connections_list(); self.refresh_scene()
        if show_message: QMessageBox.information(self, "Автосвязь концов", f"Найдено связей: {len(self.connections)}")
    def refresh_connections_list(self): self.connection_list.clear(); self.connection_list.addItems([f"{c.from_line_id}:{c.from_endpoint} ↔ {c.to_line_id}:{c.to_endpoint} · {c.distance:.3f} м" for c in self.connections])
    def toggle_grid(self, checked): self.scene.show_grid = checked; self.refresh_scene()
    def on_cursor(self, x, y): self.coord_label.setText(f"X: {x:.3f} Y: {y:.3f}")
    def save(self): QMessageBox.information(self, "Сохранено", str(save_state(self.state)))
    def load(self): self.state = load_state(); self.controller.reset(); self.refresh_lists(); self.refresh_scene(); self.view.fit_to_extent(); self.update_workflow_panel()
    def clear(self):
        if QMessageBox.question(self, "Очистить", "Очистить прототип?") == QMessageBox.StandardButton.Yes: self.state = PrototypeState(); self.controller.reset(); self.connections.clear(); self.refresh_lists(); self.refresh_scene(); self.update_workflow_panel()
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.controller.escape(); self.update_workflow_panel(); self.refresh_scene(); return
        super().keyPressEvent(event)
