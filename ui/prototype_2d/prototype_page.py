from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFileDialog, QFormLayout, QGroupBox,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton,
    QSplitter, QTextEdit, QToolButton, QVBoxLayout, QWidget,
)

from prototype_2d.bench_analysis import conflicting_bench_ids, suggest_intermediate_segments
from prototype_2d.connectivity import LineConnection, build_endpoint_connections
from prototype_2d.csv_importer import DatamineCsvError, detect_columns, import_datamine_csv, missing_required, read_text, sniff_delimiter
from prototype_2d.geometry import line_length, nearest_point_on_polyline
from prototype_2d.models import CandidateIntermediateSegment, DatamineLine, LineSegmentSelection, PrototypeDataset, PrototypeState
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
        self.connections: list[LineConnection] = []
        self.highlighted_bench_id: str | None = None
        self.scene = PrototypePlanScene()
        self.view = PrototypePlanView(self.scene)
        self.scene.line_clicked.connect(self.on_line_clicked)
        self.scene.line_hovered.connect(self.on_line_hovered)
        self.scene.marker_moved.connect(self.on_marker_moved)
        self.view.cursor_moved.connect(self.on_cursor)
        self.view.horizon_step_requested.connect(self.step_horizon)
        self.view.escape_requested.connect(self.handle_escape)
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
        self.edit_button = QPushButton("Редактировать"); self.edit_button.setEnabled(False)
        self.delete_bench_button = QPushButton("Удалить"); self.delete_bench_button.clicked.connect(self.delete_selected_bench)
        self.candidate_list = QListWidget(); self.candidate_list.currentRowChanged.connect(self.on_candidate_selected)
        self.accept_candidate_button = QPushButton("Принять предложенный"); self.accept_candidate_button.clicked.connect(self.accept_candidate)
        self.reject_candidate_button = QPushButton("Отклонить"); self.reject_candidate_button.clicked.connect(self.reject_candidate)
        self.edit_candidate_button = QPushButton("Изменить границы"); self.edit_candidate_button.clicked.connect(self.edit_candidate)
        self.advanced_toggle = QToolButton(); self.advanced_toggle.setText("Дополнительно"); self.advanced_toggle.setCheckable(True); self.advanced_toggle.toggled.connect(self.toggle_advanced)
        self.advanced_box = QGroupBox("Дополнительно"); self.advanced_box.setVisible(False)
        self.assigned_type_edit = QLineEdit(); self.assigned_type_edit.editingFinished.connect(self.update_assigned_type)
        self.auto_connect_check = QCheckBox("Автосвязь концов"); self.auto_connect_check.toggled.connect(self.toggle_auto_connect)
        self.connection_tolerance = QDoubleSpinBox(); self.connection_tolerance.setRange(0.01, 1000); self.connection_tolerance.setValue(1.0); self.connection_tolerance.setSuffix(" м"); self.connection_tolerance.setEnabled(False)
        self.connection_tolerance.setToolTip("Максимальное расстояние между концами двух линий, при котором они считаются связанными. Не используется при обычном выборе сегмента внутри одной линии")
        self.show_connections_check = QCheckBox("Показать связи"); self.show_connections_check.toggled.connect(self.refresh_scene)
        self.connection_list = QListWidget()

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
        info = QGroupBox("Информация"); info_layout = QVBoxLayout(info); info_layout.addWidget(self.line_info); panel_layout.addWidget(info)
        benches = QGroupBox("Черновики уступов"); bench_layout = QVBoxLayout(benches)
        bench_layout.addWidget(self.draft_list); bench_layout.addWidget(self.draft_details); bench_layout.addWidget(self.add_intermediate_button)
        actions = QHBoxLayout(); actions.addWidget(self.edit_button); actions.addWidget(self.delete_bench_button); bench_layout.addLayout(actions)
        bench_layout.addWidget(QLabel("Автоматически найденные промежуточные")); bench_layout.addWidget(self.candidate_list)
        candidate_actions = QHBoxLayout(); candidate_actions.addWidget(self.accept_candidate_button); candidate_actions.addWidget(self.reject_candidate_button); bench_layout.addLayout(candidate_actions)
        bench_layout.addWidget(self.edit_candidate_button)
        panel_layout.addWidget(benches)
        panel_layout.addWidget(self.advanced_toggle)
        advanced = QFormLayout(self.advanced_box)
        advanced.addRow("Разделитель CSV", self.delimiter_combo); advanced.addRow("Назначенный TYPE", self.assigned_type_edit); advanced.addRow("", self.auto_connect_check); advanced.addRow("Допуск автосвязи концов, м", self.connection_tolerance); advanced.addRow("", self.show_connections_check)
        rebuild = QPushButton("Перестроить связи"); rebuild.clicked.connect(self.rebuild_connections); advanced.addRow(rebuild); advanced.addRow("Связи", self.connection_list)
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

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.handle_escape()
            event.accept(); return
        if event.key() in {Qt.Key.Key_Up, Qt.Key.Key_Down} and not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.step_horizon(1 if event.key() == Qt.Key.Key_Up else -1); event.accept(); return
        super().keyPressEvent(event)

    def clear_selection(self) -> None:
        self.horizon_combo.setCurrentIndex(0)
        self.draft_list.blockSignals(True); self.draft_list.clearSelection(); self.draft_list.setCurrentRow(-1); self.draft_list.blockSignals(False)
        self.highlighted_bench_id = None; self.controller.selected_bench_id = None; self.controller.selected_line_id = None; self.controller.active_line_id = None
        self.line_info.setText("Выберите уступ или начните создание нового."); self.draft_details.clear(); self.refresh_scene()

    def _highlighted_segments(self) -> list[LineSegmentSelection]:
        if self.controller.state != BenchWorkflowState.IDLE:
            return [segment for segment in (self.controller.lower.segment, self.controller.upper.segment, self.controller.intermediate.segment) if segment]
        if not self.highlighted_bench_id: return []
        bench = next((item for item in self.state.drafts if item.id == self.highlighted_bench_id), None)
        if not bench: return []
        segment_by_id = {segment.id: segment for segment in self.state.segments}
        return [segment_by_id[item] for item in [bench.lower_segment_id, bench.upper_segment_id, *bench.intermediate_segment_ids] if item in segment_by_id]

    def refresh_scene(self) -> None:
        self.scene.set_lines(self.state.lines, self.active_elevation(), self.only_horizon_check.isChecked())
        self.scene.set_active_line(self.controller.active_line_id)
        self.scene.set_selected_line(self.controller.selected_line_id)
        self.scene.show_segments(self._highlighted_segments())
        current = self.controller.current_draft(); line = self.find_line(self.controller.active_line_id)
        if current and line: self.scene.show_segment_preview(line, current.start_position, current.end_position)
        if self.show_connections_check.isChecked(): self.scene.show_connections(self.connections)

    def refresh_lists(self) -> None:
        self.horizon_combo.blockSignals(True); current = self.horizon_combo.currentText(); self.horizon_combo.clear(); self.horizon_combo.addItem("Все отметки"); self.horizon_combo.addItems([str(value) for value in self.state.elevations()])
        if any(not line.is_horizontal for line in self.state.lines): self.horizon_combo.addItem("Переменные линии")
        self.horizon_combo.setCurrentText(current if self.horizon_combo.findText(current) >= 0 else "Все отметки"); self.horizon_combo.blockSignals(False)
        self.draft_list.clear(); self.draft_list.addItems([self.draft_caption(draft) for draft in self.state.drafts]); self.refresh_candidates(); self.refresh_connections_list()

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
            self.controller.reset(); self.highlighted_bench_id = None; self.connections.clear()
            if self.auto_connect_check.isChecked(): self.rebuild_connections(show_message=False)
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
                candidates = self.scene.nearest_line_candidates(x, y)
                if candidates: self.controller.choose_line(candidates[0][0])
                self.update_line_info()
            elif self.controller.active_line_id:
                line = self.find_line(self.controller.active_line_id)
                if line:
                    _point, position, _distance = nearest_point_on_polyline(line, x, y)
                    self.controller.add_marker(self.controller.active_line_id, position)
            self.update_workflow_panel(); self.refresh_scene()
        except ValueError as exc:
            QMessageBox.warning(self, "Выбор сегмента", str(exc))

    def on_line_hovered(self, x: float, y: float) -> None:
        draft = self.controller.current_draft(); line = self.find_line(self.controller.active_line_id)
        if draft and line and draft.start_position is not None and draft.end_position is None:
            _point, position, _distance = nearest_point_on_polyline(line, x, y); self.scene.show_segment_preview(line, draft.start_position, position)

    def on_marker_moved(self, marker: str, x: float, y: float) -> None:
        line = self.find_line(self.controller.active_line_id)
        if not line: return
        _point, position, _distance = nearest_point_on_polyline(line, x, y)
        self.controller.update_marker(marker, line.source_id, position); self.update_workflow_panel(); self.refresh_scene()

    def primary_action(self) -> None:
        try:
            current = self.controller.state
            if current == BenchWorkflowState.IDLE: self.start_bench_workflow(); return
            if current in LINE_SELECTION_STATES: self.controller.use_selected_line()
            elif current in CONFIRM_SEGMENT_STATES: self.confirm_segment()
            elif current == BenchWorkflowState.CONFIRM_BENCH: self.create_bench_with_checks()
            elif current == BenchWorkflowState.BENCH_CREATED: self.start_intermediate_workflow(); return
            self.update_workflow_panel(); self.refresh_scene()
        except ValueError as exc:
            QMessageBox.warning(self, "Workflow", str(exc))

    def create_bench_with_checks(self) -> None:
        lower, upper = self.controller.lower.segment, self.controller.upper.segment
        if not lower or not upper: raise ValueError("Нужны нижний и верхний сегменты")
        conflicts = conflicting_bench_ids(self.state, lower, upper)
        if conflicts:
            QMessageBox.warning(self, "Пересечение уступов", f"Новый уступ пересекается с {', '.join(conflicts)}. Создание запрещено.")
            return
        bench = self.controller.create_bench(self.state)
        self.state.candidate_segments.extend(suggest_intermediate_segments(self.state, bench.id, lower, upper))
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
        try: self.controller.start_intermediate(bench_id); self.update_workflow_panel(); self.refresh_scene()
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
            BenchWorkflowState.BENCH_CREATED: ("Уступ создан", "Найдены промежуточные линии: примите или отклоните их ниже.", "Добавить промежуточный сегмент"),
            BenchWorkflowState.ADD_INTERMEDIATE_SELECT_LINE: ("Промежуточный 1 из 4", "Выберите линию промежуточного сегмента.", "Использовать эту линию"),
            BenchWorkflowState.ADD_INTERMEDIATE_START: ("Промежуточный 2 из 4", "Укажите начало промежуточного сегмента.", "Ожидается маркер"),
            BenchWorkflowState.ADD_INTERMEDIATE_END: ("Промежуточный 3 из 4", "Укажите конец промежуточного сегмента.", "Ожидается маркер"),
            BenchWorkflowState.ADD_INTERMEDIATE_CONFIRM: ("Промежуточный 4 из 4", "Подтвердите промежуточный сегмент.", "Добавить в уступ"),
        }
        step, instruction, primary = labels[state]; self.workflow_step.setText(step); self.workflow_instruction.setText(instruction); self.primary_button.setText(primary); self.primary_button.setEnabled(primary != "Ожидается маркер")
        self.retry_button.setVisible(state in CONFIRM_SEGMENT_STATES); self.back_button.setEnabled(state != BenchWorkflowState.IDLE); self.cancel_button.setEnabled(state != BenchWorkflowState.IDLE)
        self.workflow_selected.setText(self.workflow_summary())

    def workflow_summary(self) -> str:
        lines = []
        for label, draft in (("Нижний", self.controller.lower), ("Верхний", self.controller.upper), ("Промежуточный", self.controller.intermediate)):
            if draft.segment: lines.append(f"{label}: SID {draft.segment.source_line_id}, Z {draft.segment.elevation if draft.segment.elevation is not None else 'var'}, длина {segment_length(draft.segment):.1f} м")
            elif draft.line_id: lines.append(f"{label}: активная линия {draft.line_id}")
        if self.controller.state == BenchWorkflowState.CONFIRM_BENCH: lines.insert(0, f"Название: {self.state.next_draft_id()}")
        return "\n".join(lines) if lines else "Пока ничего не выбрано."

    def update_line_info(self) -> None:
        line = self.find_line(self.controller.selected_line_id or self.controller.active_line_id)
        if not line: self.line_info.setText("Выберите уступ или начните создание нового."); return
        self.line_info.setText(f"SID: {line.source_id}\nsource TYPE: {line.source_type or '—'}\nassigned TYPE: {line.assigned_type or '—'}\nZ: {line.display_elevation()}\nДлина: {line_length(line):.1f} м")
        self.assigned_type_edit.setText(line.assigned_type or "")

    def on_draft_selected(self, row: int) -> None:
        if row < 0: return
        draft = self.state.drafts[row]; self.controller.selected_bench_id = draft.id; self.highlighted_bench_id = draft.id
        self.draft_details.setText(f"{draft.id}\nНиз: {draft.lower_segment_id}\nВерх: {draft.upper_segment_id}\nПромежуточные: {len(draft.intermediate_segment_ids)}\nКоличество: {2 + len(draft.intermediate_segment_ids)}")
        self.refresh_candidates(); self.refresh_scene()

    def refresh_candidates(self) -> None:
        selected = self.highlighted_bench_id or self.controller.selected_bench_id
        self.candidate_list.clear()
        if not selected: return
        for candidate in self.state.candidate_segments:
            if candidate.bench_id == selected:
                self.candidate_list.addItem(f"{candidate.id} · SID {candidate.segment.source_line_id} · Z {candidate.segment.elevation} · {candidate.status}")

    def _selected_candidate(self) -> CandidateIntermediateSegment | None:
        selected = self.highlighted_bench_id or self.controller.selected_bench_id; row = self.candidate_list.currentRow()
        items = [candidate for candidate in self.state.candidate_segments if candidate.bench_id == selected]
        return items[row] if 0 <= row < len(items) else None

    def on_candidate_selected(self, _row: int) -> None:
        candidate = self._selected_candidate()
        if candidate:
            self.highlighted_bench_id = None; self.scene.show_segments([candidate.segment])

    def accept_candidate(self) -> None:
        candidate = self._selected_candidate()
        if not candidate or candidate.status == "accepted": return
        bench = next((item for item in self.state.drafts if item.id == candidate.bench_id), None)
        if not bench: return
        candidate.segment.id = self.state.next_segment_id(); self.state.segments.append(candidate.segment); bench.add_intermediate(candidate.segment.id); candidate.status = "accepted"
        self.refresh_lists(); self.refresh_scene()

    def reject_candidate(self) -> None:
        candidate = self._selected_candidate()
        if candidate: candidate.status = "rejected"; self.refresh_candidates()

    def edit_candidate(self) -> None:
        """Переводит предложение в ручной workflow, сохраняя исходное предложение для аудита."""
        candidate = self._selected_candidate()
        if not candidate or candidate.status == "accepted": return
        candidate.status = "edited"
        self.controller.start_intermediate(candidate.bench_id)
        self.controller.choose_line(candidate.segment.source_line_id)
        self.controller.use_selected_line()
        self.controller.add_marker(candidate.segment.source_line_id, candidate.segment.start_position)
        self.controller.add_marker(candidate.segment.source_line_id, candidate.segment.end_position)
        self.update_workflow_panel(); self.refresh_candidates(); self.refresh_scene()

    def delete_selected_bench(self) -> None:
        row = self.draft_list.currentRow()
        if row >= 0:
            draft = self.state.drafts.pop(row); self.state.candidate_segments = [candidate for candidate in self.state.candidate_segments if candidate.bench_id != draft.id]
            self.highlighted_bench_id = None; self.refresh_lists(); self.refresh_scene()

    def update_assigned_type(self) -> None:
        line = self.find_line(self.controller.selected_line_id or self.controller.active_line_id)
        if line: line.assigned_type = self.assigned_type_edit.text() or None
    def toggle_advanced(self, checked: bool) -> None: self.advanced_box.setVisible(checked)
    def toggle_auto_connect(self, checked: bool) -> None: self.connection_tolerance.setEnabled(checked)
    def rebuild_connections(self, show_message: bool = True) -> None:
        self.connections = build_endpoint_connections(self.state.lines, self.connection_tolerance.value()); self.refresh_connections_list(); self.refresh_scene()
        if show_message: QMessageBox.information(self, "Автосвязь концов", f"Найдено связей: {len(self.connections)}")
    def refresh_connections_list(self) -> None: self.connection_list.clear(); self.connection_list.addItems([f"{item.from_line_id}:{item.from_endpoint} ↔ {item.to_line_id}:{item.to_endpoint} · {item.distance:.3f} м" for item in self.connections])
    def toggle_grid(self, checked: bool) -> None: self.scene.show_grid = checked; self.refresh_scene()
    def on_cursor(self, x: float, y: float) -> None: self.coord_label.setText(f"X: {x:.3f}  Y: {y:.3f}")
    def save(self) -> None: QMessageBox.information(self, "Сохранено", str(save_state(self.state)))
    def load(self) -> None: self.state = load_state(); self.controller.reset(); self.highlighted_bench_id = None; self.refresh_lists(); self.refresh_scene(); self.view.fit_to_extent(); self.update_workflow_panel()
    def clear(self) -> None:
        if QMessageBox.question(self, "Очистить", "Очистить прототип?") == QMessageBox.StandardButton.Yes:
            self.state = PrototypeState(); self.controller.reset(); self.connections.clear(); self.highlighted_bench_id = None; self.refresh_lists(); self.refresh_scene(); self.update_workflow_panel()
