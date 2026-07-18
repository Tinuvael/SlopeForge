from __future__ import annotations

import csv

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QDoubleSpinBox, QSplitter, QTextEdit, QVBoxLayout, QWidget)

from prototype_2d.connectivity import LineConnection, build_endpoint_connections
from prototype_2d.csv_importer import DatamineCsvError, detect_columns, import_datamine_csv, missing_required
from prototype_2d.geometry import extract_segment, nearest_point_on_polyline
from prototype_2d.models import BenchSectionDraft, LineSegmentSelection, PrototypeState
from prototype_2d.storage import load_state, save_state
from .dialogs import ColumnMappingDialog
from .plan_scene import PrototypePlanScene
from .plan_view import PrototypePlanView


class Prototype2DPage(QWidget):
    close_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.state = PrototypeState(); self.selected_line_id = None; self.segment_start = None; self.mode = "select"
        self.connections: list[LineConnection] = []
        self.scene = PrototypePlanScene(); self.view = PrototypePlanView(self.scene)
        self.scene.line_clicked.connect(self.on_line_clicked); self.view.cursor_moved.connect(self.on_cursor)
        self.mode_label = QLabel("Режим: выбор линии"); self.coord_label = QLabel("X: — Y: —")
        self.delimiter_combo = QComboBox(); self.delimiter_combo.addItems(["Auto", "comma", "semicolon", "tab"])
        self.horizon_combo = QComboBox(); self.horizon_combo.addItem("Все отметки"); self.horizon_combo.currentIndexChanged.connect(self.refresh_scene)
        self.only_horizon_check = QCheckBox("Показывать только рабочий горизонт"); self.only_horizon_check.toggled.connect(self.refresh_scene)
        self.grid_check = QCheckBox("Показывать сетку"); self.grid_check.setChecked(True); self.grid_check.toggled.connect(self.toggle_grid)
        self.source_type_filter = QLineEdit(); self.assigned_type_filter = QLineEdit(); self.ptn_filter = QLineEdit()
        for widget in (self.source_type_filter, self.assigned_type_filter, self.ptn_filter):
            widget.textChanged.connect(self.refresh_scene)
        self.assigned_type_edit = QLineEdit(); self.assigned_type_edit.editingFinished.connect(self.update_assigned_type)
        self.role_combo = QComboBox(); self.role_combo.addItems(["upper_boundary", "lower_boundary", "intermediate_assessment"])
        self.segment_list = QListWidget(); self.segment_list.currentTextChanged.connect(self.highlight_selected_segment)
        self.draft_list = QListWidget(); self.draft_list.currentRowChanged.connect(self.show_draft_details)
        self.draft_details = QTextEdit(); self.draft_details.setMaximumHeight(120)
        self.auto_connect_check = QCheckBox("Автосвязь концов")
        self.connection_tolerance = QDoubleSpinBox(); self.connection_tolerance.setRange(0.01, 1000); self.connection_tolerance.setValue(1.0); self.connection_tolerance.setSuffix(" м")
        self.show_connections_check = QCheckBox("Показать связи"); self.show_connections_check.toggled.connect(self.refresh_scene)
        self.connection_list = QListWidget()
        self.build_layout()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def build_layout(self):
        root = QVBoxLayout(self)
        top = QHBoxLayout(); root.addLayout(top)
        for title, rows in [
            ("Файл", [("Импорт", self.import_csv), ("Сохранить", self.save), ("Загрузить", self.load), ("Очистить", self.clear), ("Закрыть", self.close_requested.emit)]),
            ("Вид", [("Fit to extent", self.view.fit_to_extent)]),
            ("Выбор", [("Выбрать линию", self.select_line_mode), ("Выбрать сегмент", self.start_segment_mode), ("Отменить выбор", self.cancel_current), ("Удалить сегмент", self.delete_segment)]),
            ("Уступ", [("Создать черновик", self.create_draft), ("Добавить промежуточный", self.add_intermediate), ("Удалить промежуточный", self.remove_intermediate)]),
            ("Связность", [("Перестроить связи", self.rebuild_connections)]),
        ]:
            group = QGroupBox(title); layout = QVBoxLayout(group)
            for text, cb in rows:
                button = QPushButton(text); button.clicked.connect(cb); layout.addWidget(button)
            top.addWidget(group)
        top.addWidget(self.mode_label); top.addWidget(self.coord_label)
        splitter = QSplitter(); root.addWidget(splitter, 1); splitter.addWidget(self.view)
        panel = QWidget(); form = QFormLayout(panel); splitter.addWidget(panel)
        form.addRow("Разделитель CSV", self.delimiter_combo)
        form.addRow("Рабочий горизонт", self.horizon_combo); form.addRow("", self.only_horizon_check); form.addRow("", self.grid_check)
        form.addRow("Исходный TYPE", self.source_type_filter); form.addRow("Назначенный TYPE", self.assigned_type_filter); form.addRow("SID / Line ID", self.ptn_filter)
        form.addRow("TYPE выбранной", self.assigned_type_edit); form.addRow("Роль сегмента", self.role_combo)
        form.addRow("", self.auto_connect_check); form.addRow("Допуск", self.connection_tolerance); form.addRow("", self.show_connections_check); form.addRow("Связи", self.connection_list)
        form.addRow("Сегменты", self.segment_list); form.addRow("Черновики уступов", self.draft_list); form.addRow("Детали", self.draft_details)

    def active_elevation(self) -> float | None:
        if self.horizon_combo.currentIndex() <= 0 or self.horizon_combo.currentText() == "Переменные линии":
            return None
        return float(self.horizon_combo.currentText())

    def visible_lines(self):
        lines = self.state.lines
        if self.source_type_filter.text(): lines = [l for l in lines if self.source_type_filter.text().lower() in (l.source_type or '').lower()]
        if self.assigned_type_filter.text(): lines = [l for l in lines if self.assigned_type_filter.text().lower() in (l.assigned_type or '').lower()]
        if self.ptn_filter.text(): lines = [l for l in lines if self.ptn_filter.text().lower() in l.source_id.lower()]
        return lines

    def refresh_scene(self):
        active = self.active_elevation()
        self.scene.set_lines(self.visible_lines(), active, self.only_horizon_check.isChecked())
        self.scene.show_segments(self.state.segments); self.scene.set_selected_line(self.selected_line_id)
        if self.show_connections_check.isChecked():
            self.scene.show_connections(self.connections)

    def refresh_lists(self):
        self.horizon_combo.blockSignals(True); cur = self.horizon_combo.currentText(); self.horizon_combo.clear(); self.horizon_combo.addItem("Все отметки"); self.horizon_combo.addItems([str(e) for e in self.state.elevations()])
        if any(not line.is_horizontal for line in self.state.lines): self.horizon_combo.addItem("Переменные линии")
        self.horizon_combo.setCurrentText(cur if cur in [self.horizon_combo.itemText(i) for i in range(self.horizon_combo.count())] else "Все отметки"); self.horizon_combo.blockSignals(False)
        self.segment_list.clear(); self.segment_list.addItems([f"{s.id} · {s.role} · Z {s.elevation if s.elevation is not None else 'var'}" for s in self.state.segments])
        self.draft_list.clear(); self.draft_list.addItems([self.draft_caption(d) for d in self.state.drafts])
        self.refresh_connections_list()

    def draft_caption(self, d):
        segs = {s.id: s for s in self.state.segments}; up = segs.get(d.upper_segment_id); low = segs.get(d.lower_segment_id)
        return f"{d.id} · верх {up.elevation if up else '—'} · низ {low.elevation if low else '—'}"

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "CSV Datamine", "", "CSV (*.csv)")
        if not path: return
        try:
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            text, encoding = self._read_headers(path)
            delimiter_choice = self.delimiter_combo.currentText()
            from prototype_2d.csv_importer import sniff_delimiter
            delimiter = sniff_delimiter(text, delimiter_choice)
            headers = csv.DictReader(text.splitlines(), delimiter=delimiter).fieldnames or []
            mapping = detect_columns(headers)
            if missing_required(mapping):
                QGuiApplication.restoreOverrideCursor()
                dlg = ColumnMappingDialog(headers, self)
                if not dlg.exec(): return
                mapping = dlg.mapping(); QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            result = import_datamine_csv(path, mapping, delimiter_choice)
            self.state.lines = result.lines; self.state.imported_csv = path; self.state.segments.clear(); self.state.drafts.clear(); self.connections.clear()
            if self.auto_connect_check.isChecked(): self.rebuild_connections(show_message=False)
            self.refresh_lists(); self.refresh_scene(); self.view.fit_to_extent()
            QGuiApplication.restoreOverrideCursor(); QMessageBox.information(self, "Импорт Datamine", result.summary.to_text())
        except DatamineCsvError as exc:
            QGuiApplication.restoreOverrideCursor(); QMessageBox.warning(self, "Ошибка импорта", str(exc))
        except Exception as exc:
            QGuiApplication.restoreOverrideCursor(); QMessageBox.warning(self, "Ошибка импорта", f"Не удалось импортировать CSV: {exc}")

    def _read_headers(self, path):
        from prototype_2d.csv_importer import read_text
        return read_text(__import__('pathlib').Path(path))

    def on_line_clicked(self, line_id, x, y):
        self.selected_line_id = line_id; line = next(l for l in self.state.lines if l.source_id == line_id); self.assigned_type_edit.setText(line.assigned_type or '')
        if self.mode == "segment":
            _, pos, _ = nearest_point_on_polyline(line, x, y)
            if self.segment_start is None: self.segment_start = (line_id, pos); self.mode_label.setText("Режим: укажите конец сегмента")
            elif self.segment_start[0] != line_id: QMessageBox.warning(self, "Сегмент", "В этой версии сегмент сохраняется только в пределах одной SID. Связность уже диагностируется, multi-line selection подготовлен, но не включён.")
            else: self.save_segment(line, self.segment_start[1], pos); self.segment_start = None; self.mode_label.setText("Режим: сегмент сохранён")
        self.refresh_scene()

    def save_segment(self, line, start, end):
        s, e, pts = extract_segment(line, start, end)
        self.state.segments.append(LineSegmentSelection(self.state.next_segment_id(), line.source_id, s, e, pts, self.role_combo.currentText(), line.elevation))
        self.refresh_lists(); self.scene.show_segments(self.state.segments)

    def create_draft(self):
        upper = next((s for s in self.state.segments if s.role == "upper_boundary"), None); lower = next((s for s in self.state.segments if s.role == "lower_boundary"), None)
        if not upper or not lower: QMessageBox.warning(self, "Черновик уступа", "Нужны верхний и нижний сегменты"); return
        draft_id = self.state.next_draft_id(); self.state.drafts.append(BenchSectionDraft(draft_id, upper.id, lower.id, [upper.id], draft_id)); self.refresh_lists()

    def add_intermediate(self):
        if self.draft_list.currentRow() < 0 or self.segment_list.currentRow() < 0: return
        draft = self.state.drafts[self.draft_list.currentRow()]; segment = self.state.segments[self.segment_list.currentRow()]
        try: draft.add_intermediate(segment.id)
        except ValueError as exc: QMessageBox.warning(self, "Промежуточный сегмент", str(exc))
        self.show_draft_details(self.draft_list.currentRow())

    def remove_intermediate(self):
        if self.draft_list.currentRow() < 0 or self.segment_list.currentRow() < 0: return
        self.state.drafts[self.draft_list.currentRow()].remove_intermediate(self.state.segments[self.segment_list.currentRow()].id); self.show_draft_details(self.draft_list.currentRow())

    def rebuild_connections(self, show_message=True):
        self.connections = build_endpoint_connections(self.state.lines, self.connection_tolerance.value())
        self.refresh_connections_list(); self.refresh_scene()
        if show_message: QMessageBox.information(self, "Автосвязь концов", f"Найдено связей: {len(self.connections)}")

    def refresh_connections_list(self):
        self.connection_list.clear(); self.connection_list.addItems([f"{c.from_line_id}:{c.from_endpoint} ↔ {c.to_line_id}:{c.to_endpoint} · {c.distance:.3f} м" for c in self.connections])

    def delete_segment(self):
        row = self.segment_list.currentRow()
        if row >= 0: del self.state.segments[row]; self.refresh_lists(); self.refresh_scene()

    def highlight_selected_segment(self):
        row = self.segment_list.currentRow(); self.scene.show_segments([self.state.segments[row]] if row >= 0 else self.state.segments)

    def show_draft_details(self, row):
        if row < 0: self.draft_details.clear(); return
        d = self.state.drafts[row]; self.draft_details.setText(f"Верх: {d.upper_segment_id}\nНиз: {d.lower_segment_id}\nПромежуточные: {', '.join(d.intermediate_segment_ids)}\nКоличество сегментов: {2 + len(d.intermediate_segment_ids)}\nКомментарий: {d.comment}")

    def update_assigned_type(self):
        if self.selected_line_id:
            for line in self.state.lines:
                if line.source_id == self.selected_line_id: line.assigned_type = self.assigned_type_edit.text() or None

    def toggle_grid(self, checked): self.scene.show_grid = checked; self.refresh_scene()
    def select_line_mode(self): self.mode = "select"; self.segment_start = None; self.mode_label.setText("Режим: выбор линии")
    def start_segment_mode(self): self.mode = "segment"; self.segment_start = None; self.mode_label.setText("Режим: укажите начало сегмента")
    def cancel_current(self): self.segment_start = None; self.mode = "select"; self.mode_label.setText("Режим: выбор линии")
    def on_cursor(self, x, y): self.coord_label.setText(f"X: {x:.3f} Y: {y:.3f}")
    def save(self): QMessageBox.information(self, "Сохранено", str(save_state(self.state)))
    def load(self): self.state = load_state(); self.refresh_lists(); self.refresh_scene(); self.view.fit_to_extent()
    def clear(self):
        if QMessageBox.question(self, "Очистить", "Очистить прототип?") == QMessageBox.StandardButton.Yes: self.state = PrototypeState(); self.connections.clear(); self.refresh_lists(); self.refresh_scene()
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.cancel_current(); return
        super().keyPressEvent(event)
