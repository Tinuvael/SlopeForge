from __future__ import annotations

from copy import deepcopy

import csv
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal, QPointF
from PySide6.QtGui import QBrush, QColor, QGuiApplication, QPainterPath, QPen
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFileDialog, QFormLayout, QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem,
    QGraphicsScene, QGraphicsTextItem, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMainWindow, QMessageBox, QPushButton, QScrollArea, QSplitter, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QSizePolicy, QTabWidget,
)

from app.qt import apply_window_icon
from prototype_2d.blast_event_service import BlastEventService, BlastEventValidationError
from prototype_2d.blast_event_storage import load_blast_event_state, save_blast_event_state
from prototype_2d.csv_importer import DatamineCsvError, detect_columns, missing_required, read_text, sniff_delimiter
from prototype_2d.domain import AssessmentDomainState, BlastEvent, PlanMultiPoint, PlanPoint, PlanPolygon
from prototype_2d.assessment_area_service import AssessmentAreaService
from prototype_2d.assessment_event_link_service import AssessmentEventLinkService
from prototype_2d.geometry import validate_simple_polygon
from prototype_2d.project_lines_dataset_service import ProjectLinesDatasetService
from ui.prototype_2d.dialogs import ColumnMappingDialog
from ui.prototype_2d.plan_view import PrototypePlanView
from prototype_2d.technical_card import TechnicalCardService
from prototype_2d.wall_assessment import AssessmentAreaEvaluationService
from ui.prototype_2d.wall_assessment_dialog import AssessmentAreaEvaluationDialog
from ui.prototype_2d.technical_card_dialog import TechnicalCardDialog

PROJECT_LINE_ROLE = 1001
BLAST_GEOMETRY_ROLE = 1002
ASSESSMENT_SELECTION_ROLE = 1003
ASSESSMENT_HANDLE_ROLE = 1004
BLAST_CONTEXT_ROLE = 1005


BlastEventPlanView = PrototypePlanView  # совместимость для прежних импортов и тестов


class PolygonVertexHandle(QGraphicsEllipseItem):
    def __init__(self, index, point, moved, released):
        super().__init__(-6, -6, 12, 12); self.index = index; self._moved = moved; self._released = released
        self.setPos(point.x, -point.y); self.setBrush(QColor(255, 210, 0)); self.setPen(QPen(QColor(20, 80, 130), 2))
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
                      QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges |
                      QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations)
        self.setData(ASSESSMENT_HANDLE_ROLE, True); self.setZValue(90)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._moved(self.index, value.x(), -value.y())
        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        super().mouseReleaseEvent(event); self._released(self.index)


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
        self.area_service = AssessmentAreaService(self.state)
        self.link_service = AssessmentEventLinkService(self.state)
        self.technical_card_service = TechnicalCardService(self.state)
        self.evaluation_service = AssessmentAreaEvaluationService(self.state)
        self.selected_event: BlastEvent | None = None
        self.selected_area = None
        self._drawing_vertices: list[PlanPoint] = []
        self._drawing_cursor: PlanPoint | None = None
        self._candidate_preview = []
        self.workflow_state = "IDLE"
        self._editing_area = None
        self._previous_selected_area = None
        self._refinement_path_item = None
        self._highlighted_link = None
        self._vertex_handles = []
        self.setWindowTitle("SlopeForge — 2D Assessment Workspace")
        self.resize(1300, 800)
        self.setMinimumSize(1000, 650)
        apply_window_icon(self)
        self._build_ui()
        self.refresh_datasets()
        self.refresh_events()
        self.refresh_areas()

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
        self.mode_tabs = QTabWidget()
        events_page = QWidget(); events_layout = QVBoxLayout(events_page)
        areas_page = QWidget(); areas_layout = QVBoxLayout(areas_page)
        self.mode_tabs.addTab(events_page, "Blast Events")
        self.mode_tabs.addTab(areas_page, "Assessment Areas")
        self.mode_tabs.currentChanged.connect(self._mode_changed)
        left_layout.addWidget(self.mode_tabs, 1)
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Активные", "Архив"])
        self.filter_combo.currentIndexChanged.connect(self.refresh_events)
        self.event_list = QListWidget()
        self.event_list.currentRowChanged.connect(self._select_event)
        create = QPushButton("+ Создать событие")
        create.clicked.connect(self.create_event)
        events_layout.addWidget(self.filter_combo)
        events_layout.addWidget(self.event_list, 1)
        events_layout.addWidget(create)
        self.area_filter_combo = QComboBox(); self.area_filter_combo.addItems(["Активные", "Архив"])
        self.area_filter_combo.currentIndexChanged.connect(self._area_filter_changed)
        self.area_list = QListWidget(); self.area_list.currentRowChanged.connect(self._select_area)
        create_area = QPushButton("+ Создать Assessment Area"); create_area.clicked.connect(self.start_area_drawing)
        areas_layout.addWidget(self.area_filter_combo); areas_layout.addWidget(self.area_list, 1); areas_layout.addWidget(create_area)
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
        self.confirm_boundaries_button = QPushButton("Подтвердить границы")
        self.confirm_boundaries_button.clicked.connect(self.confirm_refined_polygon)
        self.cancel_workflow_button = QPushButton("Отменить создание")
        self.cancel_workflow_button.clicked.connect(self.cancel_area_drawing)
        actions.addWidget(self.confirm_boundaries_button); actions.addWidget(self.cancel_workflow_button)
        self.confirm_boundaries_button.hide(); self.cancel_workflow_button.hide()
        actions.addStretch()
        centre_layout.addLayout(actions)
        self.scene = QGraphicsScene(self)
        self.plan_view = BlastEventPlanView(self.scene)
        self.plan_view.scene_clicked.connect(self._drawing_click)
        self.plan_view.scene_double_clicked.connect(lambda _x, _y: self.finish_area_drawing())
        self.plan_view.cursor_moved.connect(self._drawing_move)
        self.plan_view.escape_requested.connect(self.cancel_area_drawing)
        self.plan_view.workflow_key_requested.connect(self._drawing_key)
        centre_layout.addWidget(self.plan_view, 1)
        root.addWidget(centre)

        self.card = QWidget()
        self.card.setMinimumWidth(400)
        self.card.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.card_layout = QVBoxLayout(self.card)
        self.details_scroll = QScrollArea(); self.details_scroll.setWidgetResizable(True)
        self.details_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.details_content = QWidget(); self.details_layout = QVBoxLayout(self.details_content)
        self.details_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.details_scroll.setWidget(self.details_content); self.card_layout.addWidget(self.details_scroll, 1)
        self.card_actions = QWidget(); self.card_actions_layout = QVBoxLayout(self.card_actions)
        self.card_actions_layout.setContentsMargins(0, 0, 0, 0); self.card_layout.addWidget(self.card_actions)
        root.addWidget(self.card)
        root.setSizes([230, 670, 400])

    def plan_view_fit(self):
        self.plan_view.fit_to_extent()

    def _events(self):
        return [event for event in self.state.blast_events
                if event.is_archived == (self.filter_combo.currentIndex() == 1)]

    def _areas(self):
        return [area for area in self.state.assessment_areas
                if area.is_archived == (self.area_filter_combo.currentIndex() == 1)]

    def _area_filter_changed(self):
        self.clear_highlighted_link(redraw=False); self.refresh_areas()

    def refresh_areas(self):
        prior = self.selected_area.id if self.selected_area else None
        self.area_list.blockSignals(True); self.area_list.clear()
        for area in self._areas(): self.area_list.addItem(f"{area.name} ({area.lower_elevation:g}–{area.upper_elevation:g})")
        self.area_list.blockSignals(False)
        row = next((i for i, area in enumerate(self._areas()) if area.id == prior), -1)
        self.area_list.setCurrentRow(row)
        if row < 0: self.selected_area = None
        if self.mode_tabs.currentIndex() == 1: self._render_card(); self.draw_geometry()

    def _select_area(self, row):
        self.clear_highlighted_link(redraw=False)
        areas = self._areas(); self.selected_area = areas[row] if 0 <= row < len(areas) else None
        self._render_card(); self.draw_geometry()

    def _mode_changed(self):
        self.clear_highlighted_link(redraw=False)
        self._render_card(); self.draw_geometry()

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

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_card(self):
        self._clear_layout(self.details_layout); self._clear_layout(self.card_actions_layout)

    def _set_card(self, details, actions):
        for caption, value in details:
            block = QWidget(); block_layout = QVBoxLayout(block); block_layout.setContentsMargins(0, 2, 0, 6)
            caption_label = QLabel(caption); caption_label.setStyleSheet("font-weight: 600;")
            block_layout.addWidget(caption_label); block_layout.addWidget(self._detail_value_label(str(value)))
            self.details_layout.addWidget(block)
        self.details_layout.addStretch()
        for text, callback, enabled in actions:
            button = QPushButton(text); button.clicked.connect(callback); button.setEnabled(enabled)
            self.card_actions_layout.addWidget(button)

    def _render_card(self):
        self._clear_card()
        if self.mode_tabs.currentIndex() == 1:
            area = self.selected_area
            if not area:
                self.details_layout.addWidget(QLabel("Выберите Assessment Area")); return
            revision = area.active_geometry_revision()
            dataset = next((item for item in self.state.datasets if item.id == revision.source_dataset_id), None)
            links = area.links_for_revision()
            details = [("ID", area.id), ("Название", area.name), ("Дата оценки", area.assessment_date.isoformat()),
                       ("Статус", "Архив" if area.is_archived else "Активно"),
                       ("Активная ревизия", str(revision.revision_number)),
                       ("Всего ревизий", str(len(area.geometry_revisions))),
                       ("Дата ревизии", revision.created_at.isoformat(sep=" ", timespec="minutes")),
                       ("Dataset", f"{revision.source_dataset_id} — {dataset.name}" if dataset else revision.source_dataset_id),
                       ("Нижняя отметка", f"{area.lower_elevation:g}"), ("Верхняя отметка", f"{area.upper_elevation:g}"),
                       ("Горизонтов", str(len(area.horizon_slices))),
                       ("Связи", str(len(links))),
                ("Предложено", str(sum(x.status == "suggested" for x in links))),
                ("Подтверждено", str(sum(x.status == "confirmed" for x in links))),
                ("Исключено", str(sum(x.status == "excluded" for x in links))),
                ("Устаревшие ревизии", str(sum(self.link_service.is_stale(x) for x in links)))]
            actions = [("Оценка борта", self.show_wall_assessment, not area.is_archived), ("Связанные Blast Events", self.show_area_links, True)]
            if self._highlighted_link: actions.append(("Скрыть BlastEvent", self.clear_highlighted_link, True))
            actions += [("Найти / пересчитать связи", self.refresh_area_links, not area.is_archived),
                        ("Редактировать границы", self.edit_area_boundaries, not area.is_archived),
                        ("Восстановить" if area.is_archived else "Архивировать", self.toggle_area_archive, True)]
            self._set_card(details, actions); return
        event = self.selected_event
        if not event:
            self.details_layout.addWidget(QLabel("Выберите событие"))
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
        self._set_card(details, [("Техническая карточка", self.show_technical_card, True),
            ("Переимпортировать геометрию", self.reimport_geometry, True),
            ("Восстановить" if event.is_archived else "Архивировать", self.toggle_archive, True)])

    def show_wall_assessment(self):
        if not self.selected_area: return
        existing = [e for e in self.state.evaluations if e.assessment_area_id == self.selected_area.id]
        if existing:
            evaluation = existing[-1]
            current = evaluation.active_revision()
            draft = deepcopy(current)
        else:
            evaluation, draft = self.evaluation_service.new_evaluation(self.selected_area)
        AssessmentAreaEvaluationDialog(self.selected_area, evaluation, draft, self._save_wall_assessment, self).exec()

    def _save_wall_assessment(self, evaluation, revision, status):
        evaluation.save_revision(revision, status)
        save_blast_event_state(self.state, self.storage_path)
        self._render_card()

    def show_technical_card(self):
        if not self.selected_event: return
        card, revision = self.technical_card_service.edit_or_create(self.selected_event)
        TechnicalCardDialog(self.selected_event, card, revision, self._save_technical_card, self).exec()

    def _save_technical_card(self, card, revision, status):
        card.save_revision(revision, status=status)
        save_blast_event_state(self.state, self.storage_path)

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
        self._vertex_handles = []; self._refinement_path_item = None
        self.scene.clear()
        self._draw_project_lines()
        if self.mode_tabs.currentIndex() == 0: self._draw_blast_event()
        else:
            self._draw_blast_event_context()
            self._draw_assessment_area()
        self._draw_polygon_preview()
        for candidate in self._candidate_preview:
            self._path_item(candidate.geometry, QPen(QColor(255, 120, 0), 4), z=75)
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

    def _path_item(self, geometry, pen, brush=None, z=20):
        points = geometry.ring if isinstance(geometry, PlanPolygon) else geometry.points
        path = QPainterPath(QPointF(points[0].x, -points[0].y))
        for point in points[1:]: path.lineTo(point.x, -point.y)
        item = QGraphicsPathItem(path); item.setPen(pen)
        if brush is not None: item.setBrush(brush)
        item.setZValue(z); self.scene.addItem(item); return item

    def _draw_assessment_area(self):
        area = self.selected_area
        if not area: return
        editing_reference = self.workflow_state == "REFINING" and self._editing_area is area
        self._path_item(area.final_geometry_frozen,
                        QPen(QColor(90, 120, 140), 1.5) if editing_reference else QPen(QColor(20, 120, 200), 3),
                        QBrush(QColor(70, 100, 120, 20)) if editing_reference else QBrush(QColor(30, 140, 220, 55)), 22)
        colors = {"lower_boundary": QColor(20, 160, 80), "upper_boundary": QColor(190, 70, 220), "internal_horizon": QColor(245, 150, 20)}
        for horizon in area.horizon_slices:
            color = QColor(110, 125, 135, 120) if editing_reference else colors[horizon.role]
            width = 1.2 if editing_reference else (2 if horizon.role == "internal_horizon" else 3)
            self._path_item(horizon.frozen_geometry, QPen(color, width), z=25)

    def _draw_blast_event_context(self):
        link, area = self._highlighted_link, self.selected_area
        if (link is None or area is None
                or link.assessment_area_geometry_revision_id != area.active_geometry_revision_id
                or link not in area.links_for_revision()):
            self._highlighted_link = None; return
        event = next((item for item in self.state.blast_events if item.id == link.blast_event_id), None)
        if event is None:
            self._highlighted_link = None; return
        revision = self.link_service.linked_revision(event, link)
        if revision is None: return
        geometry = revision.plan_geometry; color = QColor(20, 170, 90)
        if isinstance(geometry, PlanPolygon):
            item = self._path_item(geometry, QPen(color, 3), QBrush(QColor(20, 170, 90, 45)), 30)
            item.setData(BLAST_CONTEXT_ROLE, event.id)
        elif isinstance(geometry, PlanMultiPoint):
            for point in geometry.points:
                item = QGraphicsEllipseItem(-4, -4, 8, 8); item.setPos(point.x, -point.y)
                item.setBrush(color); item.setPen(QPen(Qt.PenStyle.NoPen))
                item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
                item.setData(BLAST_CONTEXT_ROLE, event.id); item.setZValue(30); self.scene.addItem(item)

    def _draw_polygon_preview(self):
        if not self._drawing_vertices: return
        points = self._drawing_vertices + ([self._drawing_cursor] if self._drawing_cursor else [])
        path = QPainterPath(QPointF(points[0].x, -points[0].y))
        for point in points[1:]: path.lineTo(point.x, -point.y)
        if len(self._drawing_vertices) >= 3: path.lineTo(points[0].x, -points[0].y)
        item = QGraphicsPathItem(path); item.setPen(QPen(QColor(0, 130, 230), 2, Qt.PenStyle.DashLine)); item.setBrush(QColor(0, 130, 230, 35)); item.setZValue(80); item.setData(ASSESSMENT_SELECTION_ROLE, True); self.scene.addItem(item)
        self._refinement_path_item = item
        if self.workflow_state == "REFINING":
            for index, point in enumerate(self._drawing_vertices):
                handle = PolygonVertexHandle(index, point, self._handle_moved, self._handle_released)
                self.scene.addItem(handle); self._vertex_handles.append(handle)
        else:
            for point in self._drawing_vertices:
                marker = QGraphicsEllipseItem(-4, -4, 8, 8); marker.setPos(point.x, -point.y); marker.setBrush(QColor(0, 130, 230)); marker.setZValue(81); self.scene.addItem(marker)

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
            self.clear_highlighted_link(redraw=False)
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
        self.clear_highlighted_link(redraw=False)
        self._save()
        self.refresh_datasets()
        self.draw_geometry()

    def create_event(self):
        dialog = BlastEventDialog(self, self.service)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self.selected_event = self.service.create_event(**dialog.values())
            self._save()
            self.refresh_events()
            if self.service.last_import_warning:
                QMessageBox.warning(self, "Production CSV", self.service.last_import_warning)
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
            if self.service.last_import_warning:
                QMessageBox.warning(self, "Production CSV", self.service.last_import_warning)
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка переимпорта", str(exc))

    def toggle_archive(self):
        if not self.selected_event:
            return
        self.selected_event.restore() if self.selected_event.is_archived else self.selected_event.archive()
        self._save()
        self.refresh_events()

    def toggle_area_archive(self):
        if not self.selected_area: return
        self.clear_highlighted_link(redraw=False)
        self.selected_area.restore() if self.selected_area.is_archived else self.selected_area.archive()
        self._save(); self.refresh_areas()

    def refresh_area_links(self):
        if not self.selected_area: return
        try:
            result = self.link_service.refresh_suggestions(self.selected_area)
            self._save(); self._render_card(); self.draw_geometry()
            QMessageBox.information(self, "Связи Assessment Area",
                f"Просканировано активных событий: {result.active_events_scanned}\n"
                f"Без активной геометрии: {result.events_without_active_geometry}\n"
                f"Отклонено по отметке: {result.events_rejected_by_elevation}\n"
                f"Подошло по отметке: {result.elevation_matches}\n"
                f"Отклонено пространственно: {result.events_rejected_by_spatial_match}\n"
                f"Пространственно совпало: {result.spatial_matches}\n"
                f"Production совпадений: {result.production_matches}\nContour совпадений: {result.contour_matches}\n"
                f"Новых предложений: {result.suggestions_added}\n"
                f"Сохранённых решений: {result.protected_existing_links}\n"
                f"Всего связей активной ревизии: {result.total_links_for_active_area_revision}")
        except ValueError as exc:
            QMessageBox.warning(self, "Связи Assessment Area", str(exc))

    def show_area_links(self):
        if not self.selected_area: return
        dialog = AssessmentEventLinksDialog(self.selected_area, self.state, self.link_service, self)
        dialog.highlight_requested.connect(self.highlight_area_link)
        dialog.exec(); self._save(); self._render_card(); self.draw_geometry()

    def highlight_area_link(self, link):
        if (not self.selected_area or
                link.assessment_area_geometry_revision_id != self.selected_area.active_geometry_revision_id or
                link not in self.selected_area.links_for_revision()):
            return
        self._highlighted_link = link
        self._render_card(); self.draw_geometry(); self.statusBar().showMessage(
            "Показана точная ревизия связи. Нажмите «Скрыть BlastEvent» для обычного режима.")

    def clear_highlighted_link(self, _checked=False, *, redraw=True):
        self._highlighted_link = None
        self.statusBar().clearMessage()
        if redraw:
            self._render_card(); self.draw_geometry()

    def start_area_drawing(self):
        if self.state.active_dataset() is None:
            QMessageBox.warning(self, "Assessment Area", "Сначала загрузите или выберите активный Dataset")
            return
        self.clear_highlighted_link(redraw=False)
        self._previous_selected_area = self.selected_area; self._editing_area = None
        self.workflow_state = "DRAWING"; self._drawing_vertices = []; self._drawing_cursor = None
        self.plan_view.set_polygon_drawing_mode(True)
        self.cancel_workflow_button.setText("Отменить создание"); self.cancel_workflow_button.show()
        self.confirm_boundaries_button.hide()
        self.statusBar().showMessage("ЛКМ — вершина; Enter/двойной клик — завершить; Backspace — назад; Esc — отмена")

    def _drawing_click(self, x, y):
        if self.workflow_state != "DRAWING": return
        point = PlanPoint(x, y)
        if self._drawing_vertices and len(self._drawing_vertices) >= 3:
            first = self._drawing_vertices[0]
            if ((point.x-first.x) ** 2 + (point.y-first.y) ** 2) ** .5 <= 8 / max(self.plan_view.transform().m11(), 1e-9):
                self.enter_refinement(); return
        self._drawing_vertices.append(point); self.draw_geometry()

    def _drawing_move(self, x, y):
        if self.workflow_state == "DRAWING" and self._drawing_vertices:
            self._drawing_cursor = PlanPoint(x, y); self.draw_geometry()

    def _drawing_key(self, key):
        if self.workflow_state == "DRAWING" and key == "back":
            if self._drawing_vertices: self._drawing_vertices.pop()
            self.draw_geometry()
        elif self.workflow_state == "DRAWING" and key == "enter": self.enter_refinement()
        elif self.workflow_state == "REFINING" and key == "enter": self.confirm_refined_polygon()

    def cancel_area_drawing(self):
        if self.workflow_state == "IDLE": return
        self.plan_view.set_polygon_drawing_mode(False); self._drawing_vertices = []; self._drawing_cursor = None
        self._candidate_preview = []
        self.workflow_state = "IDLE"; self._editing_area = None
        self.selected_area = self._previous_selected_area; self._previous_selected_area = None
        self.confirm_boundaries_button.hide(); self.cancel_workflow_button.hide()
        self.statusBar().clearMessage(); self.draw_geometry()

    def enter_refinement(self):
        if self.workflow_state != "DRAWING": return
        try:
            polygon = PlanPolygon(tuple(self._drawing_vertices + [self._drawing_vertices[0]]))
            validate_simple_polygon(polygon)
            self.workflow_state = "REFINING"; self._drawing_cursor = None
            self.plan_view.set_polygon_refinement_mode()
            self.confirm_boundaries_button.show(); self.cancel_workflow_button.show()
            self._refresh_refinement_candidates(); self.draw_geometry()
            self.statusBar().showMessage("Перетащите вершины. Enter или «Подтвердить границы» — продолжить; Esc — отменить")
        except (ValueError, IndexError) as exc:
            QMessageBox.warning(self, "Некорректная Assessment Area", str(exc))

    def _current_draft_polygon(self):
        return PlanPolygon(tuple(self._drawing_vertices + [self._drawing_vertices[0]]))

    def _refresh_refinement_candidates(self):
        try:
            polygon = self._current_draft_polygon(); validate_simple_polygon(polygon)
            self._candidate_preview = self.area_service.generate_candidates(polygon)
            self.confirm_boundaries_button.setEnabled(bool(self._candidate_preview))
        except (ValueError, IndexError):
            self._candidate_preview = []; self.confirm_boundaries_button.setEnabled(False)

    def _update_refinement_path(self, valid=True):
        if self._refinement_path_item is None or not self._drawing_vertices: return
        path = QPainterPath(QPointF(self._drawing_vertices[0].x, -self._drawing_vertices[0].y))
        for point in self._drawing_vertices[1:]: path.lineTo(point.x, -point.y)
        path.closeSubpath(); self._refinement_path_item.setPath(path)
        self._refinement_path_item.setPen(QPen(QColor(0, 130, 230) if valid else QColor(210, 40, 40), 2, Qt.PenStyle.DashLine))

    def _handle_moved(self, index, x, y):
        if self.workflow_state != "REFINING" or index >= len(self._drawing_vertices): return
        self._drawing_vertices[index] = PlanPoint(x, y)
        try: validate_simple_polygon(self._current_draft_polygon()); valid = True
        except ValueError: valid = False
        self.confirm_boundaries_button.setEnabled(valid); self._update_refinement_path(valid)

    def _handle_released(self, _index):
        self._refresh_refinement_candidates(); self.draw_geometry()

    def confirm_refined_polygon(self):
        if self.workflow_state != "REFINING": return
        try:
            polygon = self._current_draft_polygon(); validate_simple_polygon(polygon)
            candidates = self.area_service.generate_candidates(polygon)
            if not candidates: raise ValueError("Внутри полигона нет подходящих горизонтальных линий")
            self.workflow_state = "CANDIDATE_CONFIRMATION"
            dialog = AssessmentCandidateDialog(candidates, self)
            if dialog.exec() != QDialog.DialogCode.Accepted:
                self.workflow_state = "REFINING"; self._candidate_preview = []
                self._refresh_refinement_candidates(); self.draw_geometry(); return
            if self._editing_area:
                area = self._editing_area
                self.area_service.revise_area(area, selection_polygon=polygon,
                                              selected_fragments=dialog.selected_candidates())
            else:
                area = self.area_service.create_area(name=dialog.area_name.text(), assessment_date=dialog.area_date.date().toPython(),
                                                     selection_polygon=polygon, selected_fragments=dialog.selected_candidates())
            try:
                scan = self.link_service.refresh_suggestions(area)
                scan_text = (f"Production: {scan.production_candidates}; Contour: {scan.contour_candidates}; "
                             f"предложений: {scan.suggestions_added}")
            except Exception as exc:
                scan_text = f"Ревизия сохранена, но поиск связей не выполнен: {exc}"
            self.selected_area = area; self._previous_selected_area = area
            self._save(); self.cancel_area_drawing(); self.refresh_areas()
            QMessageBox.information(self, "Поиск связей", scan_text)
        except (ValueError, IndexError) as exc:
            self.workflow_state = "REFINING"
            QMessageBox.warning(self, "Некорректная Assessment Area", str(exc))

    finish_area_drawing = enter_refinement  # compatibility for older tests

    def edit_area_boundaries(self):
        area = self.selected_area
        if area is None or area.is_archived: return
        self.clear_highlighted_link(redraw=False)
        self._previous_selected_area = area; self._editing_area = area; self.workflow_state = "REFINING"
        self._drawing_vertices = list(area.selection_polygon_frozen.ring[:-1]); self._drawing_cursor = None
        self.cancel_workflow_button.setText("Отменить редактирование")
        self.confirm_boundaries_button.show(); self.cancel_workflow_button.show()
        self.plan_view.set_polygon_refinement_mode()
        self._refresh_refinement_candidates(); self.draw_geometry()

    def _save(self):
        save_blast_event_state(self.state, self.storage_path)

    def closeEvent(self, event):
        self._save()
        self.closed.emit()
        super().closeEvent(event)


class AssessmentEventLinksDialog(QDialog):
    """Focused, revision-aware link manager; archived areas are read-only."""
    highlight_requested = Signal(object)
    FILTERS = {"Все": None, "Предложено": "suggested", "Подтверждено": "confirmed", "Исключено": "excluded"}

    def __init__(self, area, state, service, parent=None):
        super().__init__(parent); self.area = area; self.state = state; self.service = service
        self.setWindowTitle(f"Связанные Blast Events — {area.name}"); self.resize(1050, 520)
        layout = QVBoxLayout(self); self.filter = QComboBox(); self.filter.addItems(self.FILTERS)
        self.filter.currentIndexChanged.connect(self.refresh); layout.addWidget(self.filter)
        self.row_count_label = QLabel(); layout.addWidget(self.row_count_label)
        self.table = QTableWidget(0, 8); self.table.setHorizontalHeaderLabels([
            "Статус", "Источник", "BlastEvent", "Тип", "Отметка", "Ревизия", "Состояние", "Пространственное совпадение"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        for column, width in enumerate((105, 105, 180, 90, 85, 170, 145)):
            self.table.setColumnWidth(column, width)
        self.table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        for text, slot in (("Подтвердить", self.confirm), ("Исключить", self.exclude),
                           ("Вернуть в предложенные", self.restore), ("Добавить вручную", self.manual),
                           ("Показать на плане", self.highlight)):
            button = QPushButton(text); button.clicked.connect(slot); row.addWidget(button)
            if area.is_archived and text != "Показать на плане": button.setEnabled(False)
        close = QPushButton("Закрыть"); close.clicked.connect(self.accept); row.addWidget(close)
        layout.addLayout(row); self.refresh()

    def refresh(self):
        status = self.FILTERS[self.filter.currentText()]
        self.links = [x for x in self.area.links_for_revision() if status is None or x.status == status]
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.links))
        self.row_count_label.setText(f"Показано: {len(self.links)}")
        labels = {"suggested": "Предложено", "confirmed": "Подтверждено", "excluded": "Исключено",
                  "automatic": "Автоматически", "manual": "Вручную"}
        for row, link in enumerate(self.links):
            event = next((e for e in self.state.blast_events if e.id == link.blast_event_id), None)
            revision = self.service.linked_revision(event, link) if event else None
            state = "событие не найдено" if not event else "событие в архиве" if event.is_archived else "устаревшая ревизия" if self.service.is_stale(link) else "текущая"
            spatial = "совпавшие устья: " + str(len(link.frozen_intersection_geometry.points)) if isinstance(link.frozen_intersection_geometry, PlanMultiPoint) else "пересечение полигонов" if event and event.event_type == "production" else "—"
            values = (labels[link.status], labels[link.source], event.name if event else link.blast_event_id,
                      event.event_type if event else "—", f"{event.elevation:g}" if event else "—",
                      f"{revision.revision_number} ({link.geometry_revision_id})" if revision else link.geometry_revision_id,
                      state, spatial)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value); item.setToolTip(value); self.table.setItem(row, column, item)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, link.id)
                    item.setData(Qt.ItemDataRole.UserRole + 1, link.blast_event_id)
        self.table.setSortingEnabled(True)

    def selected_link(self):
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        link_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        return next((link for link in self.area.links_for_revision() if link.id == link_id), None)

    def _change(self, action):
        link = self.selected_link()
        if link:
            try: action(self.area, link.id); self.refresh()
            except ValueError as exc: QMessageBox.warning(self, "Связи", str(exc))
    def confirm(self): self._change(self.service.confirm_link)
    def exclude(self): self._change(self.service.exclude_link)
    def restore(self): self._change(self.service.restore_suggestion)

    def manual(self):
        dialog = ManualAssessmentEventLinkDialog(self.area, self.state, self.service, self)
        if dialog.exec() == QDialog.DialogCode.Accepted: self.refresh()

    def highlight(self):
        link = self.selected_link()
        if link: self.highlight_requested.emit(link); self.accept()


class ManualAssessmentEventLinkDialog(QDialog):
    def __init__(self, area, state, service, parent=None):
        super().__init__(parent); self.area = area; self.service = service
        linked = {x.blast_event_id for x in area.links_for_revision()}
        self.events = [e for e in state.blast_events if not e.is_archived and e.id not in linked
                       and e.active_geometry_revision() is not None]
        self.setWindowTitle("Добавить BlastEvent вручную"); self.resize(820, 420)
        layout = QVBoxLayout(self); self.table = QTableWidget(len(self.events), 6)
        self.table.setHorizontalHeaderLabels(["BlastEvent", "Тип", "Отметка", "Ревизия", "Отметка подходит", "Геометрия подходит"])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        for row, event in enumerate(self.events):
            candidate = service.evaluate_event(area, event)
            values = (event.name, event.event_type, f"{event.elevation:g}", event.active_geometry_revision_id,
                      "Да" if candidate.elevation_matches else "Нет", "Да" if candidate.spatial_matches else "Нет")
            for column, value in enumerate(values): self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.add); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def add(self):
        row = self.table.currentRow()
        if row < 0: return
        event = self.events[row]; candidate = self.service.evaluate_event(self.area, event)
        failures = []
        if not candidate.elevation_matches: failures.append("отметка вне диапазона")
        if not candidate.spatial_matches: failures.append("нет пространственного совпадения")
        if failures and QMessageBox.warning(self, "Ручная связь",
                "Автоматические условия не выполнены: " + ", ".join(failures) + ". Добавить всё равно?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        try: self.service.add_manual_link(self.area, event.id); self.accept()
        except ValueError as exc: QMessageBox.warning(self, "Ручная связь", str(exc))


class AssessmentCandidateDialog(QDialog):
    def __init__(self, candidates, parent=None):
        super().__init__(parent); self.candidates = candidates
        self.setWindowTitle("Подтвердите горизонты Assessment Area"); self.resize(760, 480)
        layout = QVBoxLayout(self); form = QFormLayout()
        self.area_name = QLineEdit(); self.area_name.setPlaceholderText("Например: Участок 600–620")
        self.area_date = QDateEdit(QDate.currentDate()); self.area_date.setCalendarPopup(True)
        form.addRow("Название", self.area_name); form.addRow("Дата оценки", self.area_date); layout.addLayout(form)
        layout.addWidget(QLabel("Выберите не более одного фрагмента на отметке и минимум две отметки:"))
        self.table = QTableWidget(len(candidates), 6)
        self.table.setHorizontalHeaderLabels(["Включить", "Отметка", "SID", "Фрагмент", "Длина", "Точек"])
        counts = {}; [counts.__setitem__(item.elevation, counts.get(item.elevation, 0) + 1) for item in candidates]
        for row, candidate in enumerate(candidates):
            check = QCheckBox(); check.setChecked(counts[candidate.elevation] == 1)
            self.table.setCellWidget(row, 0, check)
            for column, value in enumerate((f"{candidate.elevation:g}", candidate.source_line_id,
                                            str(candidate.fragment_number), f"{candidate.length:.2f}",
                                            str(len(candidate.geometry.points))), 1):
                self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.horizontalHeader().setStretchLastSection(True); layout.addWidget(self.table)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept_checked); buttons.rejected.connect(self.reject); layout.addWidget(buttons)

    def selected_candidates(self):
        return [candidate for row, candidate in enumerate(self.candidates) if self.table.cellWidget(row, 0).isChecked()]

    def _accept_checked(self):
        try: AssessmentAreaService.validate_selection(self.selected_candidates())
        except ValueError as exc: QMessageBox.warning(self, "Выбор горизонтов", str(exc)); return
        self.accept()


class BlastEventDialog(QDialog):
    def __init__(self, parent=None, service=None):
        super().__init__(parent)
        self.service = service or BlastEventService(AssessmentDomainState())
        self._applying_suggestion = False
        self.elevation_is_manual = False
        self.preview = None
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
        self.elevation.valueChanged.connect(self._elevation_changed)
        self.csv = QLineEdit()
        browse = QPushButton("Выбрать CSV")
        browse.clicked.connect(self._choose_csv)
        row = QHBoxLayout()
        row.addWidget(self.csv)
        row.addWidget(browse)
        auto = QPushButton("Определить автоматически"); auto.clicked.connect(self._auto_detect)
        elevation_row = QHBoxLayout(); elevation_row.addWidget(self.elevation); elevation_row.addWidget(auto)
        self.auto_status = QLabel("Выберите CSV для автоопределения горизонта")
        self.auto_status.setWordWrap(True)
        form.addRow("Название *", self.name)
        form.addRow("Тип *", self.kind)
        form.addRow("Дата", self.date)
        form.addRow("Горизонт *", elevation_row)
        form.addRow("CSV Datamine *", row)
        form.addRow("", self.auto_status)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.kind.currentTextChanged.connect(self._event_type_changed)

    def _choose_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите CSV", "", "CSV (*.csv)")
        if not path: return
        self.csv.setText(path)
        self._inspect(force_override=True)

    def _event_type_changed(self, _event_type):
        if self.csv.text().strip(): self._inspect(force_override=True)

    def _auto_detect(self):
        self._inspect(force_override=True)

    def _inspect(self, *, force_override: bool) -> bool:
        path = self.csv.text().strip()
        if not path:
            self.auto_status.setText("Сначала выберите CSV")
            return False
        try:
            preview = self.service.inspect_event_geometry(self.kind.currentText(), path)
        except BlastEventValidationError as exc:
            self.preview = None
            self.auto_status.setText(f"Автоопределение не выполнено: {exc}")
            QMessageBox.warning(self, "Автоопределение горизонта", str(exc))
            return False
        self.preview = preview
        if force_override or not self.elevation_is_manual:
            self._applying_suggestion = True
            self.elevation.setValue(preview.suggested_elevation)
            self._applying_suggestion = False
            self.elevation_is_manual = False
        if preview.geometry_type == "Polygon":
            text = (f"Автоопределение: горизонт {preview.suggested_elevation:.2f} "
                    f"по верхней линии SID {preview.selected_source_line_id}")
        else:
            text = (f"Автоопределение: горизонт {preview.suggested_elevation:.2f} по медиане "
                    f"{preview.accepted_contour_drillhole_count} устьев")
            if preview.ignored_flat_contour_line_count:
                text += f"; плоских строк исключено: {preview.ignored_flat_contour_line_count}"
        if preview.warning_text: text += f"\n{preview.warning_text}"
        self.auto_status.setText(text)
        return True

    def _elevation_changed(self, _value):
        if self._applying_suggestion: return
        self.elevation_is_manual = True
        if self.csv.text().strip(): self.auto_status.setText("Горизонт изменён вручную")

    def _validate_and_accept(self):
        manual = self.elevation_is_manual
        if not self._inspect(force_override=not manual): return
        if manual:
            self.elevation_is_manual = True
            self.auto_status.setText("Горизонт изменён вручную")
        self.accept()

    def values(self):
        return {"name": self.name.text(), "event_type": self.kind.currentText(),
                "event_date": self.date.date().toPython(), "elevation": self.elevation.value(),
                "csv_path": self.csv.text()}
