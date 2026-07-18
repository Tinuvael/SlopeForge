from __future__ import annotations

import csv

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QComboBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPushButton, QSplitter, QTextEdit, QVBoxLayout, QWidget)

from prototype_2d.csv_importer import DatamineCsvError, import_datamine_csv, missing_required, detect_columns
from prototype_2d.geometry import extract_segment, nearest_point_on_polyline
from prototype_2d.models import BenchSectionDraft, LineSegmentSelection, PrototypeState
from prototype_2d.storage import default_storage_path, load_state, save_state
from .dialogs import ColumnMappingDialog
from .plan_scene import PrototypePlanScene
from .plan_view import PrototypePlanView


class Prototype2DPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Прототип 2D-плана")
        self.resize(1200, 800)
        self.state = PrototypeState(); self.selected_line_id = None; self.segment_start = None; self.mode = "select"
        self.scene = PrototypePlanScene(); self.view = PrototypePlanView(self.scene)
        self.scene.line_clicked.connect(self.on_line_clicked); self.view.cursor_moved.connect(self.on_cursor)
        self.mode_label = QLabel("Режим: выбор линии"); self.coord_label = QLabel("X: — Y: —")
        self.elevation_filter = QComboBox(); self.elevation_filter.addItem("Все отметки")
        self.source_type_filter = QLineEdit(); self.assigned_type_filter = QLineEdit(); self.ptn_filter = QLineEdit()
        for widget in (self.elevation_filter, self.source_type_filter, self.assigned_type_filter, self.ptn_filter):
            if hasattr(widget, 'currentIndexChanged'): widget.currentIndexChanged.connect(self.refresh_scene)
            else: widget.textChanged.connect(self.refresh_scene)
        self.assigned_type_edit = QLineEdit(); self.assigned_type_edit.editingFinished.connect(self.update_assigned_type)
        self.role_combo = QComboBox(); self.role_combo.addItems(["upper_boundary", "lower_boundary", "intermediate_assessment"])
        self.segment_list = QListWidget(); self.segment_list.currentTextChanged.connect(self.highlight_selected_segment)
        self.draft_list = QListWidget(); self.draft_list.currentRowChanged.connect(self.show_draft_details)
        self.draft_details = QTextEdit(); self.draft_details.setMaximumHeight(140)
        root = QVBoxLayout(self); toolbar = QHBoxLayout(); root.addLayout(toolbar)
        for text, cb in [("Импортировать новый CSV", self.import_csv), ("Сохранить", self.save), ("Загрузить", self.load), ("Очистить прототип", self.clear), ("Fit to extent", self.view.fit_to_extent), ("Выбрать сегмент", self.start_segment_mode), ("Создать черновик уступа", self.create_draft), ("Добавить промежуточный", self.add_intermediate), ("Удалить сегмент", self.delete_segment)]:
            b = QPushButton(text); b.clicked.connect(cb); toolbar.addWidget(b)
        toolbar.addWidget(self.mode_label); toolbar.addWidget(self.coord_label)
        splitter = QSplitter(); root.addWidget(splitter, 1); splitter.addWidget(self.view)
        panel = QWidget(); form = QFormLayout(panel); splitter.addWidget(panel)
        form.addRow("Отметка", self.elevation_filter); form.addRow("Исходный TYPE", self.source_type_filter); form.addRow("Назначенный TYPE", self.assigned_type_filter); form.addRow("PTN", self.ptn_filter); form.addRow("TYPE выбранной", self.assigned_type_edit); form.addRow("Роль сегмента", self.role_combo); form.addRow("Сегменты", self.segment_list); form.addRow("Черновики уступов", self.draft_list); form.addRow("Детали", self.draft_details)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def visible_lines(self):
        lines = self.state.lines
        if self.elevation_filter.currentIndex() > 0:
            lines = [l for l in lines if str(l.elevation) == self.elevation_filter.currentText()]
        if self.source_type_filter.text(): lines = [l for l in lines if self.source_type_filter.text().lower() in (l.source_type or '').lower()]
        if self.assigned_type_filter.text(): lines = [l for l in lines if self.assigned_type_filter.text().lower() in (l.assigned_type or '').lower()]
        if self.ptn_filter.text(): lines = [l for l in lines if self.ptn_filter.text().lower() in l.source_id.lower()]
        return lines

    def refresh_scene(self):
        self.scene.set_lines(self.visible_lines()); self.scene.show_segments(self.state.segments); self.scene.set_selected_line(self.selected_line_id)

    def refresh_lists(self):
        self.elevation_filter.blockSignals(True); cur = self.elevation_filter.currentText(); self.elevation_filter.clear(); self.elevation_filter.addItem("Все отметки"); self.elevation_filter.addItems([str(e) for e in self.state.elevations()]); self.elevation_filter.setCurrentText(cur); self.elevation_filter.blockSignals(False)
        self.segment_list.clear(); self.segment_list.addItems([f"{s.id} · {s.role} · Z {s.elevation}" for s in self.state.segments])
        self.draft_list.clear(); self.draft_list.addItems([self.draft_caption(d) for d in self.state.drafts])

    def draft_caption(self, d):
        segs = {s.id: s for s in self.state.segments}; up = segs.get(d.upper_segment_id); low = segs.get(d.lower_segment_id)
        return f"{d.id} · верх {up.elevation if up else '—'} · низ {low.elevation if low else '—'}"

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "CSV Datamine", "", "CSV (*.csv)")
        if not path: return
        try:
            with open(path, newline='', encoding='utf-8-sig') as h: headers = csv.DictReader(h).fieldnames or []
            mapping = detect_columns(headers)
            if missing_required(mapping):
                dlg = ColumnMappingDialog(headers, self)
                if not dlg.exec(): return
                mapping = dlg.mapping()
            self.state.lines = import_datamine_csv(path, mapping); self.state.imported_csv = path; self.state.segments.clear(); self.state.drafts.clear(); self.refresh_lists(); self.refresh_scene(); self.view.fit_to_extent()
        except DatamineCsvError as exc: QMessageBox.warning(self, "Ошибка импорта", str(exc))
        except Exception as exc: QMessageBox.warning(self, "Ошибка импорта", f"Не удалось импортировать CSV: {exc}")

    def on_line_clicked(self, line_id, x, y):
        self.selected_line_id = line_id; line = next(l for l in self.state.lines if l.source_id == line_id); self.assigned_type_edit.setText(line.assigned_type or '')
        if self.mode == "segment":
            _, pos, _ = nearest_point_on_polyline(line, x, y)
            if self.segment_start is None: self.segment_start = (line_id, pos); self.mode_label.setText("Режим: укажите конец сегмента")
            elif self.segment_start[0] != line_id: QMessageBox.warning(self, "Сегмент", "Начало и конец должны быть на одной линии")
            else: self.save_segment(line, self.segment_start[1], pos); self.segment_start = None; self.mode_label.setText("Режим: сегмент сохранён")
        self.refresh_scene()

    def save_segment(self, line, start, end):
        s, e, pts = extract_segment(line, start, end)
        self.state.segments.append(LineSegmentSelection(self.state.next_segment_id(), line.source_id, s, e, pts, self.role_combo.currentText(), line.elevation))
        self.refresh_lists(); self.scene.show_segments(self.state.segments)

    def create_draft(self):
        upper = next((s for s in self.state.segments if s.role == "upper_boundary"), None); lower = next((s for s in self.state.segments if s.role == "lower_boundary"), None)
        if not upper or not lower: QMessageBox.warning(self, "Черновик уступа", "Нужны верхний и нижний сегменты"); return
        self.state.drafts.append(BenchSectionDraft(self.state.next_draft_id(), upper.id, lower.id, [upper.id], self.state.next_draft_id()))
        self.refresh_lists()

    def add_intermediate(self):
        if self.draft_list.currentRow() < 0 or self.segment_list.currentRow() < 0: return
        draft = self.state.drafts[self.draft_list.currentRow()]; segment = self.state.segments[self.segment_list.currentRow()]
        try: draft.add_intermediate(segment.id)
        except ValueError as exc: QMessageBox.warning(self, "Промежуточный сегмент", str(exc))
        self.show_draft_details(self.draft_list.currentRow())

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

    def start_segment_mode(self): self.mode = "segment"; self.segment_start = None; self.mode_label.setText("Режим: укажите начало сегмента")
    def on_cursor(self, x, y): self.coord_label.setText(f"X: {x:.3f} Y: {y:.3f}")
    def save(self): QMessageBox.information(self, "Сохранено", str(save_state(self.state)))
    def load(self): self.state = load_state(); self.refresh_lists(); self.refresh_scene(); self.view.fit_to_extent()
    def clear(self):
        if QMessageBox.question(self, "Очистить", "Очистить прототип?") == QMessageBox.StandardButton.Yes: self.state = PrototypeState(); self.refresh_lists(); self.refresh_scene()
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape: self.segment_start = None; self.mode = "select"; self.mode_label.setText("Режим: выбор линии")
        super().keyPressEvent(event)
