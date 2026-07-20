from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton,
    QSplitter, QTextEdit, QToolButton, QVBoxLayout, QWidget, QAbstractSpinBox, QMenu,
)

from prototype_2d.bench_analysis import conflicting_bench_ids
from prototype_2d.occupancy import interval_conflicts, occupied_intervals, position_conflict
from prototype_2d.csv_importer import DatamineCsvError, detect_columns, import_datamine_csv, missing_required, read_text, sniff_delimiter
from prototype_2d.geometry import line_length, nearest_point_on_polyline
from prototype_2d.models import DatamineLine, LineSegmentSelection, PrototypeDataset, PrototypeState
from prototype_2d.storage import load_state, save_state
from .bench_creation_controller import BenchCreationController, BenchWorkflowState, segment_length
from .dialogs import ColumnMappingDialog
from .plan_scene import PrototypePlanScene
from .plan_view import PrototypePlanView


LINE_SELECTION_STATES = {
    BenchWorkflowState.SELECT_LOWER_LINE,
    BenchWorkflowState.SELECT_UPPER_LINE,
    BenchWorkflowState.ADD_INTERMEDIATE_SELECT_LINE,
}
CONFIRM_SEGMENT_STATES = {
    BenchWorkflowState.CONFIRM_LOWER,
    BenchWorkflowState.CONFIRM_UPPER,
    BenchWorkflowState.ADD_INTERMEDIATE_CONFIRM,
}


class Prototype2DPage(QWidget):
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = PrototypeState()
        self.controller = BenchCreationController()
        self.edit_snapshot: tuple[list[LineSegmentSelection], list] | None = None
        self.workflow_notice = ""
        self.highlighted_bench_id: str | None = None
        self.scene = PrototypePlanScene()
        self.view = PrototypePlanView(self.scene)
        self.scene.line_clicked.connect(self.on_line_clicked)
        self.scene.line_hovered.connect(self.on_line_hovered)
        self.scene.marker_moved.connect(self.on_marker_moved)
        self.view.cursor_moved.connect(self.on_cursor)
        self.view.escape_requested.connect(self.handle_escape)
        self.view.workflow_key_requested.connect(self.handle_workflow_key)
        self.scene.marker_dragged.connect(self.on_marker_dragged)
        self.scene.line_context_requested.connect(self.show_line_context_menu)
        self._create_controls()
        self.build_layout()
        self.update_workflow_panel()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _create_controls(self) -> None:
        self.coord_label = QLabel("X: —  Y: —")
        self.delimiter_combo = QComboBox(); self.delimiter_combo.addItems(["Auto", "comma", "semicolon", "tab"])
        self.horizon_combo = QComboBox(); self.horizon_combo.addItem("Все отметки"); self.horizon_combo.currentIndexChanged.connect(self.refresh_scene)
        self.only_horizon_check = QCheckBox("Только рабочий горизонт"); self.only_horizon_check.toggled.connect(self.refresh_scene)
        self.grid_check = QCheckBox("Сетка"); self.grid_check.setChecked(True); self.grid_check.toggled.connect(self.toggle_grid)
        self.create_bench_button = QPushButton("Создать сегмент уступа"); self.create_bench_button.clicked.connect(self.start_bench_workflow)
        self.workflow_step = QLabel("Готово к работе")
        self.workflow_instruction = QLabel("Выберите уступ или начните создание нового."); self.workflow_instruction.setWordWrap(True)
        self.workflow_selected = QTextEdit(); self.workflow_selected.setReadOnly(True); self.workflow_selected.setMaximumHeight(130)
        self.primary_button = QPushButton("Создать сегмент уступа"); self.primary_button.clicked.connect(self.primary_action)
        self.retry_button = QPushButton("Выбрать заново"); self.retry_button.clicked.connect(self.retry_current_segment)
        self.back_button = QPushButton("Назад"); self.back_button.clicked.connect(self.go_back)
        self.cancel_button = QPushButton("Отмена"); self.cancel_button.clicked.connect(self.cancel_workflow)
        self.line_info = QTextEdit(); self.line_info.setReadOnly(True); self.line_info.setMaximumHeight(120)
        self.draft_list = QListWidget(); self.draft_list.currentRowChanged.connect(self.on_draft_selected)
        self.draft_details = QTextEdit(); self.draft_details.setReadOnly(True); self.draft_details.setMaximumHeight(110)
        self.add_intermediate_button = QPushButton("Добавить промежуточный сегмент"); self.add_intermediate_button.clicked.connect(self.start_intermediate_workflow)
        self.edit_button = QPushButton("Редактировать границы"); self.edit_button.clicked.connect(self.start_editing)
        self.edit_lower_button = QPushButton("Изменить нижнюю границу"); self.edit_lower_button.clicked.connect(lambda: self.edit_boundary("lower"))
        self.edit_upper_button = QPushButton("Изменить верхнюю границу"); self.edit_upper_button.clicked.connect(lambda: self.edit_boundary("upper"))
        self.delete_bench_button = QPushButton("Удалить"); self.delete_bench_button.clicked.connect(self.delete_selected_bench)
        self.intermediate_list = QListWidget(); self.intermediate_list.currentRowChanged.connect(self.on_intermediate_selected)
        self.upper_assessment_check = QCheckBox("Использовать верхнюю границу как первую промежуточную оценку"); self.upper_assessment_check.toggled.connect(self.toggle_upper_assessment)
        self.delete_intermediate_button = QPushButton("Удалить промежуточный"); self.delete_intermediate_button.clicked.connect(self.delete_selected_intermediate)
        self.edit_intermediate_button = QPushButton("Изменить промежуточный"); self.edit_intermediate_button.clicked.connect(self.edit_selected_intermediate)
        self.finish_button = QPushButton("Готово"); self.finish_button.clicked.connect(self.finish_editing)
        self.cancel_edit_button = QPushButton("Отменить изменения"); self.cancel_edit_button.clicked.connect(self.cancel_editing)
        self.clear_selection_button = QPushButton("Снять выделение"); self.clear_selection_button.clicked.connect(self.clear_selection)
        self.pit_boundary_button = QPushButton("Назначить границей карьера"); self.pit_boundary_button.clicked.connect(self.toggle_pit_boundary)
        self.show_pit_boundary_check = QCheckBox("Показывать границу карьера"); self.show_pit_boundary_check.setChecked(True); self.show_pit_boundary_check.toggled.connect(self.refresh_scene)
        self.advanced_toggle = QToolButton(); self.advanced_toggle.setText("Дополнительно"); self.advanced_toggle.setCheckable(True); self.advanced_toggle.toggled.connect(self.toggle_advanced)
        self.advanced_box = QGroupBox("Дополнительно"); self.advanced_box.setVisible(False)
        self.assigned_type_edit = QLineEdit(); self.assigned_type_edit.editingFinished.connect(self.update_assigned_type)
        self.sid_filter_edit = QLineEdit(); self.sid_filter_edit.setPlaceholderText("Фильтр SID")


    def build_layout(self) -> None:
        root = QVBoxLayout(self)
        top = QHBoxLayout(); root.addLayout(top)
        file_group = QGroupBox("Файл"); file_layout = QHBoxLayout(file_group)
        for text, callback in [("Импорт", self.import_csv), ("Сохранить", self.save), ("Загрузить", self.load), ("Очистить", self.clear), ("Закрыть", self.close_requested.emit)]:
            button = QPushButton(text); button.clicked.connect(callback); file_layout.addWidget(button)
        view_group = QGroupBox("Вид"); view_layout = QHBoxLayout(view_group)
        fit = QPushButton("Fit to extent"); fit.clicked.connect(self.view.fit_to_extent)
        view_layout.addWidget(fit); view_layout.addWidget(QLabel("Рабочий горизонт")); view_layout.addWidget(self.horizon_combo); view_layout.addWidget(self.only_horizon_check); view_layout.addWidget(self.grid_check)
        top.addWidget(file_group); top.addWidget(view_group, 1); top.addWidget(self.create_bench_button); top.addWidget(self.coord_label)
        self.splitter = QSplitter(Qt.Orientation.Horizontal); root.addWidget(self.splitter, 1)
        self.splitter.addWidget(self.view)
        panel = QWidget(); panel.setMinimumWidth(300); panel_layout = QVBoxLayout(panel); self.splitter.addWidget(panel)
        self.splitter.setStretchFactor(0, 3); self.splitter.setStretchFactor(1, 1); self.splitter.setSizes([975, 325])
        workflow = QGroupBox("Workflow"); layout = QVBoxLayout(workflow)
        for widget in (self.workflow_step, self.workflow_instruction, self.workflow_selected, self.primary_button, self.retry_button): layout.addWidget(widget)
        navigation = QHBoxLayout(); navigation.addWidget(self.back_button); navigation.addWidget(self.cancel_button); layout.addLayout(navigation); panel_layout.addWidget(workflow)
        benches = QGroupBox("Черновики уступов"); bench_layout = QVBoxLayout(benches)
        bench_layout.addWidget(self.draft_list); bench_layout.addWidget(self.draft_details)
        bench_layout.addWidget(self.edit_lower_button); bench_layout.addWidget(self.edit_upper_button)
        bench_layout.addWidget(QLabel("Промежуточные оценки")); bench_layout.addWidget(self.upper_assessment_check); bench_layout.addWidget(self.intermediate_list); bench_layout.addWidget(self.edit_intermediate_button); bench_layout.addWidget(self.delete_intermediate_button)
        bench_layout.addWidget(self.add_intermediate_button)
        actions = QHBoxLayout(); actions.addWidget(self.edit_button); actions.addWidget(self.delete_bench_button); bench_layout.addLayout(actions)
        bench_layout.addWidget(self.finish_button); bench_layout.addWidget(self.cancel_edit_button); bench_layout.addWidget(self.clear_selection_button)
        panel_layout.addWidget(benches)
        panel_layout.addWidget(self.advanced_toggle)
        advanced = QFormLayout(self.advanced_box)
        advanced.addRow("Назначенный TYPE", self.assigned_type_edit); advanced.addRow("Фильтр SID", self.sid_filter_edit); advanced.addRow("", self.show_pit_boundary_check)
        panel_layout.addWidget(self.advanced_box); panel_layout.addStretch(1)

    def find_line(self, line_id: str | None) -> DatamineLine | None:
        return next((line for line in self.state.lines if line.source_id == line_id), None)

    def active_elevation(self) -> float | None:
        if self.horizon_combo.currentIndex() <= 0 or self.horizon_combo.currentText() == "Переменные линии": return None
        return float(self.horizon_combo.currentText())

    def step_horizon(self, direction: int) -> None:
        if self.horizon_combo.count() > 1:
            index = max(0, min(self.horizon_combo.count() - 1, self.horizon_combo.currentIndex() + direction))
            self.horizon_combo.setCurrentIndex(index)

    def handle_escape(self) -> None:
        if self.controller.state == BenchWorkflowState.IDLE:
            self.clear_selection()
        else:
            self.controller.escape(); self.update_workflow_panel(); self.refresh_scene()

    def handle_workflow_key(self, key: str) -> None:
        if key == "enter": self.confirm_from_controller()
        elif key == "back": self.go_back(); self.update_workflow_panel(); self.refresh_scene()
        elif key == "delete": self.delete_from_keyboard()
        elif key == "candidate_previous": self.cycle_candidate(-1)
        elif key == "candidate_next": self.cycle_candidate(1)

    def cycle_candidate(self, direction: int) -> None:
        if self.controller.state not in LINE_SELECTION_STATES: return
        line_id = self.controller.next_candidate() if direction > 0 else self.controller.previous_candidate()
        if line_id:
            self.workflow_notice = self.candidate_summary()
            self.update_workflow_panel(); self.refresh_scene()

    def candidate_summary(self) -> str:
        line = self.find_line(self.controller.current_candidate())
        if not line: return ""
        return f"Выбрана линия {self.controller.candidate_index + 1} из {len(self.controller.candidate_line_ids)}\nSID: {line.source_id}\nTYPE: {line.source_type or '—'}\n{line.display_elevation()}"

    def confirm_from_controller(self) -> None:
        action = self.controller.confirm_current_step()
        if action is None:
            if self.selected_intermediate():
                self.edit_selected_intermediate(); return
            self.workflow_notice = "Сначала завершите текущий шаг."; self.update_workflow_panel(); return
        if action == "finish": self.finish_editing(); return
        if action == "save_segment_edit": self.save_segment_edit(); return
        self.execute_confirmation(action)

    def delete_from_keyboard(self) -> None:
        if self.intermediate_list.currentRow() >= 0:
            self.delete_selected_intermediate(); return
        if self.draft_list.currentRow() >= 0:
            if QMessageBox.question(self, "Удалить уступ", "Удалить выбранный уступ?") == QMessageBox.StandardButton.Yes: self.delete_selected_bench()

    def keyPressEvent(self, event):
        if isinstance(self.focusWidget(), (QLineEdit, QAbstractSpinBox)):
            super().keyPressEvent(event); return
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.confirm_from_controller(); event.accept(); return
        if event.key() == Qt.Key.Key_Backspace:
            self.go_back(); event.accept(); return
        if event.key() == Qt.Key.Key_Delete:
            self.delete_from_keyboard(); event.accept(); return
        if event.key() == Qt.Key.Key_Escape:
            self.handle_escape()
            event.accept(); return
        if event.key() in {Qt.Key.Key_Up, Qt.Key.Key_Left}:
            self.cycle_candidate(-1); event.accept(); return
        if event.key() in {Qt.Key.Key_Down, Qt.Key.Key_Right}:
            self.cycle_candidate(1); event.accept(); return
        super().keyPressEvent(event)

    def clear_selection(self) -> None:
        self.horizon_combo.setCurrentIndex(0)
        self.draft_list.blockSignals(True); self.draft_list.clearSelection(); self.draft_list.setCurrentRow(-1); self.draft_list.blockSignals(False)
        self.highlighted_bench_id = None; self.controller.selected_bench_id = None; self.controller.selected_line_id = None; self.controller.active_line_id = None
        self.line_info.setText("Выберите уступ или начните создание нового."); self.draft_details.clear(); self.refresh_scene()

    def bench_segments(self, bench_id: str | None) -> list[LineSegmentSelection]:
        bench = next((item for item in self.state.drafts if item.id == bench_id), None)
        if not bench: return []
        by_id = {segment.id: segment for segment in self.state.segments}
        return [by_id[item] for item in [bench.lower_segment_id, bench.upper_segment_id, *bench.intermediate_segment_ids] if item in by_id]

    def _highlighted_segments(self) -> list[LineSegmentSelection]:
        # В IDLE рисуется только один явно выбранный уступ.
        selected = self.controller.selected_bench_id
        visible = self.bench_segments(selected)
        if self.controller.state == BenchWorkflowState.IDLE:
            return visible
        pending = [segment for segment in (self.controller.lower.segment, self.controller.upper.segment, self.controller.intermediate.segment) if segment]
        seen = {item.id for item in visible}
        return visible + [item for item in pending if item.id not in seen]

    def visible_lines(self) -> list[DatamineLine]:
        lines = self.state.lines
        if not self.show_pit_boundary_check.isChecked():
            lines = [line for line in lines if line.semantic_role != "pit_boundary"]
        filter_text = self.sid_filter_edit.text().strip()
        return [line for line in lines if not filter_text or filter_text.lower() in line.source_id.lower()]

    def current_occupied_intervals(self):
        line = self.find_line(self.controller.active_line_id or self.controller.selected_line_id)
        return occupied_intervals(self.state, self.state.active_dataset_id, line.source_id, self.controller.edited_segment_id) if line else []

    def refresh_scene(self) -> None:
        self.scene.set_lines(self.visible_lines(), self.active_elevation(), self.only_horizon_check.isChecked())
        self.scene.set_active_line(self.controller.active_line_id)
        self.scene.set_selected_line(self.controller.selected_line_id)
        self.scene.show_segments(self._highlighted_segments())
        current = self.controller.current_draft(); line = self.find_line(self.controller.active_line_id)
        if current and line: self.scene.show_segment_preview(line, current.start_position, current.end_position)
        active_or_selected = self.find_line(self.controller.active_line_id or self.controller.selected_line_id)
        self.scene.show_occupied_intervals(active_or_selected, self.current_occupied_intervals())

    def refresh_lists(self) -> None:
        self.horizon_combo.blockSignals(True); current = self.horizon_combo.currentText(); self.horizon_combo.clear(); self.horizon_combo.addItem("Все отметки"); self.horizon_combo.addItems([str(value) for value in self.state.elevations()])
        if any(not line.is_horizontal for line in self.state.lines): self.horizon_combo.addItem("Переменные линии")
        self.horizon_combo.setCurrentText(current if self.horizon_combo.findText(current) >= 0 else "Все отметки"); self.horizon_combo.blockSignals(False)
        self.draft_list.clear(); self.draft_list.addItems([self.draft_caption(draft) for draft in self.state.drafts])

    def draft_caption(self, draft) -> str:
        by_id = {segment.id: segment for segment in self.state.segments}; upper = by_id.get(draft.upper_segment_id); lower = by_id.get(draft.lower_segment_id)
        return f"{draft.id} · верх {upper.elevation if upper else '—'} · низ {lower.elevation if lower else '—'}"

    def import_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "CSV Datamine", "", "CSV (*.csv)")
        if not path: return
        try:
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            text, _encoding = read_text(Path(path)); choice = self.delimiter_combo.currentText(); delimiter = sniff_delimiter(text, choice)
            headers = csv.DictReader(text.splitlines(), delimiter=delimiter).fieldnames or []; mapping = detect_columns(headers)
            if missing_required(mapping):
                QGuiApplication.restoreOverrideCursor(); dialog = ColumnMappingDialog(headers, self)
                if not dialog.exec(): return
                mapping = dialog.mapping(); QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            result = import_datamine_csv(path, mapping, choice)
            dataset = PrototypeDataset(self.state.next_dataset_id(), path, Path(path).name)
            self.state.datasets.append(dataset); self.state.active_dataset_id = dataset.id; self.state.imported_csv = path; self.state.lines = result.lines
            self.controller.reset(); self.highlighted_bench_id = None
            self.refresh_lists(); self.refresh_scene(); self.view.fit_to_extent(); self.update_workflow_panel()
            QMessageBox.information(self, "Импорт Datamine", result.summary.to_text() + f"\nDataset: {dataset.id}")
        except DatamineCsvError as exc:
            QMessageBox.warning(self, "Ошибка импорта", str(exc))
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка импорта", f"Не удалось импортировать CSV: {exc}")
        finally:
            QGuiApplication.restoreOverrideCursor()

    def on_line_clicked(self, line_id: str, x: float, y: float) -> None:
        try:
            if self.controller.state in LINE_SELECTION_STATES:
                candidates = [line_id for line_id, distance in self.scene.nearest_line_candidates(x, y) if distance <= 15]
                if candidates:
                    self.controller.set_line_candidates(candidates, x, y)
                    self.workflow_notice = self.candidate_summary()
                else:
                    self.controller.clear_candidates(); self.workflow_notice = "Нет линии рядом с курсором."
                self.update_line_info()
            elif self.controller.active_line_id:
                line = self.find_line(self.controller.active_line_id)
                if line:
                    _point, position, _distance = nearest_point_on_polyline(line, x, y)
                    intervals = self.current_occupied_intervals()
                    draft = self.controller.current_draft()
                    conflict = position_conflict(intervals, position) if draft and draft.start_position is None else None
                    if conflict:
                        self.workflow_notice = conflict.description()
                    elif draft and draft.start_position is not None and interval_conflicts(intervals, draft.start_position, position):
                        self.workflow_notice = interval_conflicts(intervals, draft.start_position, position)[0].description()
                    else:
                        self.workflow_notice = ""; self.controller.add_marker(self.controller.active_line_id, position)
            else:
                if not self.controller.selected_bench_id:
                    self.controller.selected_line_id = line_id
                    self.pit_boundary_button.setVisible(True)
                    self.update_line_info()
            self.update_workflow_panel(); self.refresh_scene()
        except ValueError as exc:
            QMessageBox.warning(self, "Выбор сегмента", str(exc))

    def on_line_hovered(self, x: float, y: float) -> None:
        draft = self.controller.current_draft(); line = self.find_line(self.controller.active_line_id)
        if draft and line and draft.start_position is not None and draft.end_position is None:
            _point, position, _distance = nearest_point_on_polyline(line, x, y)
            conflicts = interval_conflicts(self.current_occupied_intervals(), draft.start_position, position)
            self.workflow_notice = conflicts[0].description() if conflicts else ""
            self.scene.show_segment_preview(line, draft.start_position, position, invalid=bool(conflicts))
            self.update_workflow_panel()

    def on_marker_dragged(self, marker: str, x: float, y: float) -> None:
        line = self.find_line(self.controller.active_line_id)
        draft = self.controller.current_draft()
        if not line or not draft: return
        _point, position, _distance = nearest_point_on_polyline(line, x, y)
        other = draft.end_position if marker == "start" else draft.start_position
        if other is not None and interval_conflicts(self.current_occupied_intervals(), position, other):
            self.workflow_notice = "Новая позиция пересекает занятый участок"; return
        self.controller.update_marker(marker, line.source_id, position)
        self.scene.update_drag_preview(line, draft.start_position, draft.end_position)
        self.update_workflow_panel()

    def on_marker_moved(self, marker: str, x: float, y: float) -> None:
        line = self.find_line(self.controller.active_line_id)
        draft = self.controller.current_draft()
        if not line or not draft: return
        _point, position, _distance = nearest_point_on_polyline(line, x, y)
        other = draft.end_position if marker == "start" else draft.start_position
        if other is not None and interval_conflicts(self.current_occupied_intervals(), position, other):
            self.workflow_notice = "Новая позиция пересекает занятый участок"; self.refresh_scene(); self.update_workflow_panel(); return
        self.controller.update_marker(marker, line.source_id, position); self.update_workflow_panel(); self.refresh_scene()

    def primary_action(self) -> None:
        action = self.controller.confirm_current_step()
        if action is None:
            if self.controller.state == BenchWorkflowState.IDLE: self.start_bench_workflow()
            else: self.workflow_notice = "Сначала завершите текущий шаг."; self.update_workflow_panel()
            return
        if action == "finish": self.finish_editing(); return
        if action == "save_segment_edit": self.save_segment_edit(); return
        self.execute_confirmation(action)

    def execute_confirmation(self, action: str) -> None:
        try:
            if action == "use_line": self.controller.use_selected_line()
            elif action == "confirm_segment": self.confirm_segment()
            elif action == "create_bench": self.create_bench_with_checks()
            self.workflow_notice = ""; self.update_workflow_panel(); self.refresh_scene()
        except ValueError as exc:
            self.workflow_notice = str(exc); self.update_workflow_panel()

    def create_bench_with_checks(self) -> None:
        lower, upper = self.controller.lower.segment, self.controller.upper.segment
        if not lower or not upper: raise ValueError("Нужны нижний и верхний сегменты")
        conflicts = conflicting_bench_ids(self.state, lower, upper)
        if conflicts:
            QMessageBox.warning(self, "Пересечение уступов", f"Новый уступ пересекается с {', '.join(conflicts)}. Создание запрещено.")
            return
        bench = self.controller.create_bench(self.state)
        self.highlighted_bench_id = None
        self.refresh_lists()

    def confirm_segment(self) -> None:
        line = self.find_line(self.controller.active_line_id)
        if not line: raise ValueError("Активная линия не найдена")
        segment = self.controller.confirm_current_segment(self.state, line)
        if segment.role == "intermediate_assessment": self.controller.add_intermediate_to_bench(self.state); self.refresh_lists()

    def start_bench_workflow(self) -> None:
        if not self.state.lines: QMessageBox.information(self, "Создание уступа", "Сначала импортируйте CSV."); return
        self.highlighted_bench_id = None; self.controller.start_bench(); self.update_workflow_panel(); self.refresh_scene()

    def start_intermediate_workflow(self) -> None:
        row = self.draft_list.currentRow(); bench_id = self.state.drafts[row].id if row >= 0 else self.controller.selected_bench_id
        try:
            self.controller.start_intermediate(bench_id)
            bench = next((item for item in self.state.drafts if item.id == bench_id), None)
            if bench: bench.status = "editing"
            self.update_workflow_panel(); self.refresh_scene()
        except ValueError as exc: QMessageBox.warning(self, "Промежуточный сегмент", str(exc))

    def retry_current_segment(self) -> None:
        draft = self.controller.current_draft()
        if draft: draft.reset_points(); self.update_workflow_panel(); self.refresh_scene()

    def go_back(self) -> None: self.controller.back(); self.update_workflow_panel(); self.refresh_scene()

    def cancel_workflow(self) -> None:
        if self.controller.has_work_in_progress() and QMessageBox.question(self, "Отмена", "Отменить текущий workflow?") != QMessageBox.StandardButton.Yes: return
        self.controller.reset(); self.update_workflow_panel(); self.refresh_scene()

    def update_workflow_panel(self) -> None:
        state = self.controller.state
        labels = {
            BenchWorkflowState.IDLE: ("Готово", "Выберите уступ или начните создание нового.", "Создать сегмент уступа"),
            BenchWorkflowState.SELECT_LOWER_LINE: ("Шаг 1 из 5", "Выберите нижнюю линию уступа.", "Использовать эту линию"),
            BenchWorkflowState.SELECT_LOWER_START: ("Шаг 2 из 5", "Укажите начало нижнего сегмента. Активна только выбранная линия.", "Ожидается маркер"),
            BenchWorkflowState.SELECT_LOWER_END: ("Шаг 2 из 5", "Укажите конец нижнего сегмента.", "Ожидается маркер"),
            BenchWorkflowState.CONFIRM_LOWER: ("Шаг 3 из 5", "Проверьте нижний сегмент.", "Подтвердить нижний сегмент"),
            BenchWorkflowState.SELECT_UPPER_LINE: ("Шаг 4 из 5", "Выберите верхнюю линию уступа.", "Использовать эту линию"),
            BenchWorkflowState.SELECT_UPPER_START: ("Шаг 4 из 5", "Укажите начало верхнего сегмента. Активна только выбранная линия.", "Ожидается маркер"),
            BenchWorkflowState.SELECT_UPPER_END: ("Шаг 4 из 5", "Укажите конец верхнего сегмента.", "Ожидается маркер"),
            BenchWorkflowState.CONFIRM_UPPER: ("Шаг 4 из 5", "Проверьте верхний сегмент.", "Подтвердить верхний сегмент"),
            BenchWorkflowState.CONFIRM_BENCH: ("Шаг 5 из 5", f"Проверьте итог. Будет создан {self.state.next_draft_id()}.", "Создать уступ"),
            BenchWorkflowState.BENCH_CREATED: ("Уступ редактируется", "Добавляйте промежуточные сегменты вручную либо нажмите «Готово».", "Добавить промежуточный сегмент"),
            BenchWorkflowState.ADD_INTERMEDIATE_SELECT_LINE: ("Промежуточный 1 из 4", "Выберите линию промежуточного сегмента.", "Использовать эту линию"),
            BenchWorkflowState.ADD_INTERMEDIATE_START: ("Промежуточный 2 из 4", "Укажите начало промежуточного сегмента.", "Ожидается маркер"),
            BenchWorkflowState.ADD_INTERMEDIATE_END: ("Промежуточный 3 из 4", "Укажите конец промежуточного сегмента.", "Ожидается маркер"),
            BenchWorkflowState.ADD_INTERMEDIATE_CONFIRM: ("Промежуточный 4 из 4", "Подтвердите промежуточный сегмент.", "Добавить в уступ"),
        }
        step, instruction, primary = labels[state]; self.workflow_step.setText(step); self.workflow_instruction.setText(instruction); self.primary_button.setText(primary); self.primary_button.setEnabled(primary != "Ожидается маркер")
        self.retry_button.setVisible(state in CONFIRM_SEGMENT_STATES); self.back_button.setEnabled(state != BenchWorkflowState.IDLE); self.cancel_button.setEnabled(state != BenchWorkflowState.IDLE)
        self.finish_button.setVisible(state == BenchWorkflowState.BENCH_CREATED or self.edit_snapshot is not None)
        self.cancel_edit_button.setVisible(self.edit_snapshot is not None)
        self.pit_boundary_button.setVisible(state == BenchWorkflowState.IDLE and not self.highlighted_bench_id and self.controller.selected_line_id is not None)
        self.workflow_selected.setText((self.workflow_notice + "\n" if self.workflow_notice else "") + self.workflow_summary())

    def workflow_summary(self) -> str:
        lines = []
        for label, draft in (("Нижний", self.controller.lower), ("Верхний", self.controller.upper), ("Промежуточный", self.controller.intermediate)):
            if draft.segment: lines.append(f"{label}: SID {draft.segment.source_line_id}, Z {draft.segment.elevation if draft.segment.elevation is not None else 'var'}, длина {segment_length(draft.segment):.1f} м")
            elif draft.line_id: lines.append(f"{label}: активная линия {draft.line_id}")
        if self.controller.state == BenchWorkflowState.CONFIRM_BENCH: lines.insert(0, f"Название: {self.state.next_draft_id()}")
        return "\n".join(lines) if lines else "Пока ничего не выбрано."

    def toggle_upper_assessment(self, checked: bool) -> None:
        bench = next((item for item in self.state.drafts if item.id == self.controller.selected_bench_id), None)
        if bench:
            bench.upper_boundary_is_assessment = checked
            self.on_draft_selected(self.draft_list.currentRow())

    def show_line_context_menu(self, line_id: str, global_position) -> None:
        line = self.find_line(line_id)
        if not line: return
        menu = QMenu(self)
        action = menu.addAction("Снять признак границы карьера" if line.semantic_role == "pit_boundary" else "Назначить границей карьера")
        chosen = menu.exec(global_position)
        if chosen == action:
            line.semantic_role = "normal" if line.semantic_role == "pit_boundary" else "pit_boundary"
            self.refresh_scene()

    def update_line_info(self) -> None:
        line = self.find_line(self.controller.selected_line_id or self.controller.active_line_id)
        if not line: self.line_info.setText("Выберите уступ или начните создание нового."); return
        self.line_info.setText(f"SID: {line.source_id}\nsource TYPE: {line.source_type or '—'}\nassigned TYPE: {line.assigned_type or '—'}\nZ: {line.display_elevation()}\nДлина: {line_length(line):.1f} м")
        self.assigned_type_edit.setText(line.assigned_type or "")
        self.pit_boundary_button.setText("Снять признак границы карьера" if line.semantic_role == "pit_boundary" else "Назначить границей карьера")

    def on_draft_selected(self, row: int) -> None:
        if row < 0: return
        draft = self.state.drafts[row]
        self.controller.selected_bench_id = draft.id; self.highlighted_bench_id = None; self.controller.lower.reset_points(); self.controller.upper.reset_points(); self.controller.intermediate.reset_points(); self.pit_boundary_button.setVisible(False)
        segments = {segment.id: segment for segment in self.state.segments}
        lower, upper = segments.get(draft.lower_segment_id), segments.get(draft.upper_segment_id)
        status = "Редактируется" if draft.status == "editing" else "Готов"
        dataset = (lower or upper).dataset_id if lower or upper else "—"
        self.draft_details.setText(
            f"{draft.id}\nСтатус: {status}\nDataset: {dataset or '—'}\n"
            f"Нижняя граница: {self.segment_description(lower, 'низ не задан')}\n"
            f"Верхняя граница: {self.segment_description(upper, 'верх не задан')}"
        )
        self.upper_assessment_check.blockSignals(True); self.upper_assessment_check.setChecked(draft.upper_boundary_is_assessment); self.upper_assessment_check.blockSignals(False)
        self.intermediate_list.blockSignals(True); self.intermediate_list.clear()
        if draft.upper_boundary_is_assessment:
            self.intermediate_list.addItem("Верхняя граница — первая оценка")
        for segment_id in draft.intermediate_segment_ids:
            segment = segments.get(segment_id)
            if segment:
                self.intermediate_list.addItem(f"{segment.id} · Z {segment.elevation if segment.elevation is not None else 'переменная'} · SID {segment.source_line_id} · {segment_length(segment):.1f} м")
            else:
                self.intermediate_list.addItem(f"{segment_id} · сегмент отсутствует")
        self.intermediate_list.blockSignals(False)
        self.edit_intermediate_button.setEnabled(False); self.delete_intermediate_button.setEnabled(False)
        self.refresh_scene()

    def segment_description(self, segment: LineSegmentSelection | None, missing: str) -> str:
        if not segment: return missing
        return f"SID {segment.source_line_id}, Z {segment.elevation if segment.elevation is not None else 'переменная'}, {segment_length(segment):.1f} м"

    def edit_boundary(self, boundary: str) -> None:
        bench = next((item for item in self.state.drafts if item.id == self.controller.selected_bench_id), None)
        if not bench: return
        segment_id = bench.lower_segment_id if boundary == "lower" else bench.upper_segment_id
        segment = next((item for item in self.state.segments if item.id == segment_id), None)
        if segment: self.start_segment_edit(segment)

    def delete_selected_bench(self) -> None:
        row = self.draft_list.currentRow()
        if row >= 0:
            self.state.drafts.pop(row)
            self.highlighted_bench_id = None; self.intermediate_list.clear(); self.refresh_lists(); self.refresh_scene()

    def selected_intermediate(self) -> LineSegmentSelection | None:
        bench = next((item for item in self.state.drafts if item.id == self.controller.selected_bench_id), None)
        row = self.intermediate_list.currentRow()
        if not bench or row < 0: return None
        if bench.upper_boundary_is_assessment:
            if row == 0: return None
            row -= 1
        if row >= len(bench.intermediate_segment_ids): return None
        return next((item for item in self.state.segments if item.id == bench.intermediate_segment_ids[row]), None)

    def on_intermediate_selected(self, _row: int) -> None:
        segment = self.selected_intermediate()
        if segment:
            self.scene.show_segments(self._highlighted_segments(), selected_segment_id=segment.id)
            self.edit_intermediate_button.setEnabled(True); self.delete_intermediate_button.setEnabled(True)
            self.workflow_notice = f"Выбран промежуточный сегмент {segment.id}. Enter — изменить, Delete — удалить."
            self.update_workflow_panel()

    def delete_selected_intermediate(self) -> None:
        bench = next((item for item in self.state.drafts if item.id == self.controller.selected_bench_id), None)
        row = self.intermediate_list.currentRow()
        if not bench or row < 0 or row >= len(bench.intermediate_segment_ids): return
        segment_id = bench.intermediate_segment_ids.pop(row)
        self.state.segments = [segment for segment in self.state.segments if segment.id != segment_id]
        bench.status = "editing"
        self.on_draft_selected(self.draft_list.currentRow())

    def edit_selected_intermediate(self) -> None:
        segment = self.selected_intermediate()
        if segment: self.start_segment_edit(segment)

    def start_segment_edit(self, segment: LineSegmentSelection) -> None:
        line = self.find_line(segment.source_line_id)
        if not line or segment.dataset_id != self.state.active_dataset_id:
            self.workflow_notice = "Исходная линия сегмента недоступна. Геометрию можно просмотреть, но нельзя редактировать без перепривязки."
            self.update_workflow_panel(); return
        self.edit_snapshot = PrototypeState.from_dict(self.state.to_dict()).segments, PrototypeState.from_dict(self.state.to_dict()).drafts
        self.controller.start_segment_edit(segment)
        self.workflow_notice = f"Редактирование {segment.id}. Перетащите A или B. Enter — сохранить."
        self.update_workflow_panel(); self.refresh_scene()

    def save_segment_edit(self) -> None:
        line = self.find_line(self.controller.active_line_id)
        if not line: self.workflow_notice = "Исходная линия недоступна."; self.update_workflow_panel(); return
        updated = self.controller.build_current_segment(self.state, line)
        intervals = self.current_occupied_intervals()
        if interval_conflicts(intervals, updated.start_position, updated.end_position):
            self.workflow_notice = "Изменённый сегмент пересекает занятый участок."; self.update_workflow_panel(); return
        self.state.segments = [updated if item.id == updated.id else item for item in self.state.segments]
        self.controller.reset(); self.edit_snapshot = None; self.workflow_notice = "Изменения сегмента сохранены."; self.refresh_lists(); self.refresh_scene(); self.update_workflow_panel()

    def toggle_advanced(self, checked: bool) -> None: self.advanced_box.setVisible(checked)
    def update_assigned_type(self) -> None:
        line = self.find_line(self.controller.selected_line_id or self.controller.active_line_id)
        if line: line.assigned_type = self.assigned_type_edit.text() or None
    def toggle_pit_boundary(self) -> None:
        line = self.find_line(self.controller.selected_line_id)
        if not line: return
        line.semantic_role = "normal" if line.semantic_role == "pit_boundary" else "pit_boundary"
        self.update_line_info(); self.refresh_scene()
    def finish_editing(self) -> None:
        bench_id = self.controller.selected_bench_id
        bench = next((draft for draft in self.state.drafts if draft.id == bench_id), None)
        if not bench: return
        bench.status = "ready"; self.controller.reset(); self.highlighted_bench_id = None; self.edit_snapshot = None
        self.refresh_scene(); self.refresh_lists(); self.workflow_instruction.setText(f"Сегмент уступа {bench.id} сохранён")
    def cancel_editing(self) -> None:
        if self.edit_snapshot is not None:
            self.state.segments, self.state.drafts = self.edit_snapshot
        self.edit_snapshot = None; self.controller.reset(); self.highlighted_bench_id = None; self.refresh_lists(); self.refresh_scene(); self.update_workflow_panel()
    def start_editing(self) -> None:
        row = self.draft_list.currentRow()
        if row < 0: return
        self.edit_snapshot = PrototypeState.from_dict(self.state.to_dict()).segments, PrototypeState.from_dict(self.state.to_dict()).drafts
        bench = self.state.drafts[row]; bench.status = "editing"; self.controller.selected_bench_id = bench.id; self.highlighted_bench_id = bench.id
        self.refresh_scene(); self.refresh_lists()
    def toggle_grid(self, checked: bool) -> None: self.scene.show_grid = checked; self.refresh_scene()
    def on_cursor(self, x: float, y: float) -> None: self.coord_label.setText(f"X: {x:.3f}  Y: {y:.3f}")
    def save(self) -> None: QMessageBox.information(self, "Сохранено", str(save_state(self.state)))
    def load(self) -> None: self.state = load_state(); self.controller.reset(); self.highlighted_bench_id = None; self.refresh_lists(); self.refresh_scene(); self.view.fit_to_extent(); self.update_workflow_panel()
    def clear(self) -> None:
        if QMessageBox.question(self, "Очистить", "Очистить прототип?") == QMessageBox.StandardButton.Yes:
            self.state = PrototypeState(); self.controller.reset(); self.highlighted_bench_id = None; self.refresh_lists(); self.refresh_scene(); self.update_workflow_panel()
