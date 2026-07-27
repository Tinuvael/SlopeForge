from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem,
    QGraphicsScene, QGraphicsTextItem, QGraphicsView, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPushButton, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QSizePolicy,
)

from app.qt import apply_window_icon
from prototype_2d.blast_event_service import BlastEventService
from prototype_2d.blast_event_storage import load_blast_event_state, save_blast_event_state
from prototype_2d.csv_importer import DatamineCsvError, detect_columns, missing_required, read_text, sniff_delimiter
from prototype_2d.domain import BlastEvent, PlanMultiPoint, PlanPolygon
from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService
from ui.prototype_2d.dialogs import ColumnMappingDialog

PROJECT_LINE_ROLE = 1001
BLAST_GEOMETRY_ROLE = 1002


class BlastEventPlanView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def fit_to_extent(self):
        # itemsBoundingRect учитывает только находящиеся в сцене видимые слои.
        rect = self.scene().itemsBoundingRect()
        if not rect.isNull() and rect.isValid():
            margin = max(min(max(rect.width(), rect.height()) * 0.03, 100.0), 1.0)
            self.fitInView(rect.adjusted(-margin, -margin, margin, margin), Qt.AspectRatioMode.KeepAspectRatio)


class DatasetHistoryDialog(QDialog):
    def __init__(self, datasets, parent=None):
        super().__init__(parent)
        self.setWindowTitle("История проектных линий")
        self.resize(760, 320)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(len(datasets), 5)
        self.table.setHorizontalHeaderLabels(["ID", "Название", "Исходный файл", "Дата импорта", "Статус"])
        for row, dataset in enumerate(datasets):
            values = [dataset.id, dataset.name, dataset.source_file_name,
                      dataset.imported_at.isoformat(sep=" ", timespec="minutes"),
                      "active" if dataset.is_active else "inactive"]
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(value))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, dataset.id)
            if dataset.is_active:
                self.table.selectRow(row)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Сделать активным")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_dataset_id(self):
        row = self.table.currentRow()
        return self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) if row >= 0 else None


class BlastEventWindow(QMainWindow):
    closed = Signal()

    def __init__(self, parent=None, storage_path=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.storage_path = storage_path
        self.state = load_blast_event_state(storage_path)
        self.service = BlastEventService(self.state)
        self.dataset_service = ProjectLinesDatasetService(self.state)
        self.selected_event: BlastEvent | None = None
        self.setWindowTitle("Blast Events Prototype")
        self.resize(1300, 800)
        self.setMinimumSize(1000, 650)
        apply_window_icon(self)
        self._build_ui()
        self.refresh_datasets()
        self.refresh_events()

    def _build_ui(self):
        root_widget = QWidget()
        outer = QVBoxLayout(root_widget)
        self.setCentralWidget(root_widget)

        dataset_bar = QHBoxLayout()
        self.dataset_label = QLabel()
        self.import_dataset_button = QPushButton("Загрузить проектные линии")
        self.import_dataset_button.clicked.connect(self.import_project_lines)
        history = QPushButton("История Dataset")
        history.clicked.connect(self.show_dataset_history)
        self.lines_checkbox = QCheckBox("Проектные линии")
        self.lines_checkbox.setChecked(True)
        self.lines_checkbox.toggled.connect(self.draw_geometry)
        self.elevation_combo = QComboBox()
        self.elevation_combo.currentIndexChanged.connect(self.draw_geometry)
        dataset_bar.addWidget(self.dataset_label, 1)
        dataset_bar.addWidget(self.import_dataset_button)
        dataset_bar.addWidget(history)
        dataset_bar.addWidget(self.lines_checkbox)
        dataset_bar.addWidget(self.elevation_combo)
        outer.addLayout(dataset_bar)

        root = QSplitter()
        outer.addWidget(root, 1)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Активные", "Архив"])
        self.filter_combo.currentIndexChanged.connect(self.refresh_events)
        self.event_list = QListWidget()
        self.event_list.currentRowChanged.connect(self._select_event)
        create = QPushButton("+ Создать событие")
        create.clicked.connect(self.create_event)
        left_layout.addWidget(self.filter_combo)
        left_layout.addWidget(self.event_list, 1)
        left_layout.addWidget(create)
        root.addWidget(left)

        centre = QWidget()
        centre_layout = QVBoxLayout(centre)
        actions = QHBoxLayout()
        fit = QPushButton("Вписать в экран")
        fit.clicked.connect(self.plan_view_fit)
        self.grid_button = QPushButton("Сетка")
        self.grid_button.setCheckable(True)
        self.grid_button.setChecked(True)
        self.grid_button.toggled.connect(self.draw_geometry)
        actions.addWidget(fit)
        actions.addWidget(self.grid_button)
        actions.addStretch()
        centre_layout.addLayout(actions)
        self.scene = QGraphicsScene(self)
        self.plan_view = BlastEventPlanView(self.scene)
        centre_layout.addWidget(self.plan_view, 1)
        root.addWidget(centre)

        self.card = QWidget()
        self.card.setMinimumWidth(330)
        self.card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.addWidget(QLabel("Выберите событие"))
        self.card_layout.addStretch()
        root.addWidget(self.card)
        root.setSizes([250, 700, 300])

    def plan_view_fit(self):
        self.plan_view.fit_to_extent()

    def _events(self):
        return [event for event in self.state.blast_events
                if event.is_archived == (self.filter_combo.currentIndex() == 1)]

    def refresh_events(self):
        prior = self.selected_event.id if self.selected_event else None
        self.event_list.blockSignals(True)
        self.event_list.clear()
        for event in self._events():
            self.event_list.addItem(f"{event.name} ({event.event_type})")
        self.event_list.blockSignals(False)
        row = next((i for i, event in enumerate(self._events()) if event.id == prior), -1)
        self.event_list.setCurrentRow(row)
        if row < 0:
            self.selected_event = None
            self._render_card()
            self.draw_geometry()

    def refresh_datasets(self):
        dataset = self.dataset_service.active_dataset()
        self.dataset_label.setText(f"Проектные линии: {dataset.name}" if dataset else "Проектные линии: не загружены")
        current = self.elevation_combo.currentData()
        self.elevation_combo.blockSignals(True)
        self.elevation_combo.clear()
        self.elevation_combo.addItem("Все отметки", None)
        for elevation in self.dataset_service.available_elevations():
            self.elevation_combo.addItem(f"{elevation:g}", elevation)
        index = self.elevation_combo.findData(current)
        self.elevation_combo.setCurrentIndex(max(index, 0))
        self.elevation_combo.blockSignals(False)

    def _select_event(self, row):
        events = self._events()
        self.selected_event = events[row] if 0 <= row < len(events) else None
        self._render_card()
        self.draw_geometry()

    def _clear_card(self):
        while self.card_layout.count():
            item = self.card_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _render_card(self):
        self._clear_card()
        event = self.selected_event
        if not event:
            self.card_layout.addWidget(QLabel("Выберите событие"))
            self.card_layout.addStretch()
            return
        revision = event.active_geometry_revision()
        details = [("ID", event.id), ("Название", event.name), ("Тип", event.event_type),
                   ("Дата", event.event_date.isoformat() if event.event_date else "—"),
                   ("Горизонт", f"{event.elevation:g}"),
                   ("Активная ревизия", str(revision.revision_number) if revision else "—"),
                   ("CSV", revision.source_file_name if revision else "—"),
                   ("Дата импорта", revision.imported_at.isoformat(sep=' ', timespec='minutes') if revision else "—"),
                   ("Тип геометрии", revision.plan_geometry.to_dict()['type'] if revision else "—"),
                   ("Число ревизий", str(len(event.geometry_revisions))),
                   ("Статус", "Архив" if event.is_archived else "Активно")]
        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        for caption, value in details:
            form.addRow(caption, self._detail_value_label(value))
        self.card_layout.addLayout(form)
        reimport = QPushButton("Переимпортировать геометрию")
        reimport.clicked.connect(self.reimport_geometry)
        self.card_layout.addWidget(reimport)
        archive = QPushButton("Восстановить" if event.is_archived else "Архивировать")
        archive.clicked.connect(self.toggle_archive)
        self.card_layout.addWidget(archive)
        self.card_layout.addStretch()

    @staticmethod
    def _detail_value_label(value: str) -> QLabel:
        """Readable form value which can grow/wrap and retains its full text."""
        label = QLabel(value)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        label.setMinimumWidth(0)
        label.setToolTip(value)
        label.setProperty("blastEventDetailValue", True)
        return label

    def draw_geometry(self):
        self.scene.clear()
        self._draw_project_lines()
        self._draw_blast_event()
        if self.grid_button.isChecked():
            self._add_grid()

    def _draw_project_lines(self):
        dataset = self.dataset_service.active_dataset()
        if not dataset or not self.lines_checkbox.isChecked():
            return
        selected_elevation = self.elevation_combo.currentData()
        pen = QPen(self.palette().color(self.palette().ColorRole.Mid), 0.8)
        for line in dataset.lines:
            if len(line.points) < 2:
                continue
            if selected_elevation is not None and (not line.is_horizontal or line.elevation != selected_elevation):
                continue
            path = QPainterPath()
            path.moveTo(line.points[0].x, -line.points[0].y)
            for point in line.points[1:]:
                path.lineTo(point.x, -point.y)
            item = QGraphicsPathItem(path)
            item.setPen(pen)
            item.setOpacity(0.55)
            item.setZValue(10)
            item.setData(PROJECT_LINE_ROLE, True)
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.scene.addItem(item)

    def _draw_blast_event(self):
        event = self.selected_event
        if not event or not event.active_geometry_revision():
            return
        geometry = event.active_geometry_revision().plan_geometry
        if isinstance(geometry, PlanPolygon):
            ring = geometry.ring
            path = QPainterPath()
            path.moveTo(ring[0].x, -ring[0].y)
            for point in ring[1:]:
                path.lineTo(point.x, -point.y)
            item = QGraphicsPathItem(path)
            item.setPen(QPen(QColor(210, 70, 20), 2))
            item.setBrush(QBrush(QColor(255, 150, 40, 70)))
            item.setZValue(20)
            item.setData(BLAST_GEOMETRY_ROLE, True)
            self.scene.addItem(item)
        elif isinstance(geometry, PlanMultiPoint):
            for point in geometry.points:
                item = QGraphicsEllipseItem(-4, -4, 8, 8)
                item.setPos(point.x, -point.y)
                item.setBrush(QColor(30, 100, 220))
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                item.setZValue(20)
                item.setData(BLAST_GEOMETRY_ROLE, True)
                self.scene.addItem(item)
        rect = self.scene.itemsBoundingRect()
        label = QGraphicsTextItem(event.name)
        label.setDefaultTextColor(self.palette().color(self.palette().ColorRole.Text))
        label.setPos(rect.left(), rect.top())
        label.setZValue(30)
        label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.scene.addItem(label)

    def _add_grid(self):
        rect = self.scene.itemsBoundingRect()
        if rect.isNull():
            return
        step = max(max(rect.width(), rect.height()) / 10, 1)
        pen = QPen(self.palette().color(self.palette().ColorRole.Midlight), 0)
        x = rect.left()
        while x <= rect.right():
            item = self.scene.addLine(x, rect.top(), x, rect.bottom(), pen)
            item.setZValue(0)
            x += step
        y = rect.top()
        while y <= rect.bottom():
            item = self.scene.addLine(rect.left(), y, rect.right(), y, pen)
            item.setZValue(0)
            y += step

    def import_project_lines(self):
        path, _ = QFileDialog.getOpenFileName(self, "CSV Datamine — проектные линии", "", "CSV (*.csv)")
        if not path:
            return
        first_import = not self.state.datasets
        try:
            QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            text, _ = read_text(Path(path))
            delimiter = sniff_delimiter(text)
            headers = csv.DictReader(text.splitlines(), delimiter=delimiter).fieldnames or []
            mapping = detect_columns(headers)
            if missing_required(mapping):
                QGuiApplication.restoreOverrideCursor()
                dialog = ColumnMappingDialog(headers, self)
                if not dialog.exec():
                    return
                mapping = dialog.mapping()
                QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            dataset, result = self.dataset_service.import_dataset(path, column_mapping=mapping)
            self._save()
            self.refresh_datasets()
            self.draw_geometry()
            if first_import:
                self.plan_view.fit_to_extent()
            QMessageBox.information(self, "Импорт проектных линий", result.summary.to_text() + f"\nDataset: {dataset.id}")
        except (DatamineCsvError, ValueError) as exc:
            QMessageBox.warning(self, "Ошибка импорта", str(exc))
        finally:
            QGuiApplication.restoreOverrideCursor()

    def show_dataset_history(self):
        if not self.state.datasets:
            QMessageBox.information(self, "История Dataset", "Проектные линии ещё не загружены")
            return
        dialog = DatasetHistoryDialog(self.state.datasets, self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.selected_dataset_id():
            return
        self.dataset_service.set_active(dialog.selected_dataset_id())
        self._save()
        self.refresh_datasets()
        self.draw_geometry()

    def create_event(self):
        dialog = BlastEventDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self.selected_event = self.service.create_event(**dialog.values())
            self._save()
            self.refresh_events()
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось создать событие", str(exc))

    def reimport_geometry(self):
        if not self.selected_event:
            return
        path, _ = QFileDialog.getOpenFileName(self, "Выберите CSV", "", "CSV (*.csv)")
        if not path:
            return
        try:
            self.service.reimport_geometry(self.selected_event, path)
            self._save()
            self._render_card()
            self.draw_geometry()
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка переимпорта", str(exc))

    def toggle_archive(self):
        if not self.selected_event:
            return
        self.selected_event.restore() if self.selected_event.is_archived else self.selected_event.archive()
        self._save()
        self.refresh_events()

    def _save(self):
        save_blast_event_state(self.state, self.storage_path)

    def closeEvent(self, event):
        self._save()
        self.closed.emit()
        super().closeEvent(event)


class BlastEventDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Создать Blast Event")
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit()
        self.kind = QComboBox()
        self.kind.addItems(["production", "contour"])
        self.date = QDateEdit(QDate.currentDate())
        self.date.setCalendarPopup(True)
        self.elevation = QDoubleSpinBox()
        self.elevation.setRange(-10000, 10000)
        self.elevation.setDecimals(2)
        self.csv = QLineEdit()
        browse = QPushButton("Выбрать CSV")
        browse.clicked.connect(lambda: self.csv.setText(QFileDialog.getOpenFileName(self, "Выберите CSV", "", "CSV (*.csv)")[0]))
        row = QHBoxLayout()
        row.addWidget(self.csv)
        row.addWidget(browse)
        form.addRow("Название *", self.name)
        form.addRow("Тип *", self.kind)
        form.addRow("Дата", self.date)
        form.addRow("Горизонт *", self.elevation)
        form.addRow("CSV Datamine *", row)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return {"name": self.name.text(), "event_type": self.kind.currentText(),
                "event_date": self.date.date().toPython(), "elevation": self.elevation.value(),
                "csv_path": self.csv.text()}
