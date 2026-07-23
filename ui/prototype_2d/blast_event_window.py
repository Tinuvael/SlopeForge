from __future__ import annotations

from pathlib import Path
from PySide6.QtCore import Qt, Signal, QDate
from PySide6.QtGui import QColor, QBrush, QPainterPath, QPen
from PySide6.QtWidgets import (QDialog, QDialogButtonBox,QComboBox, QDateEdit, QFileDialog, QFormLayout, QFrame, QGraphicsEllipseItem,
    QGraphicsPathItem, QGraphicsScene, QGraphicsView, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMainWindow, QMessageBox, QPushButton, QSplitter, QDoubleSpinBox, QVBoxLayout, QWidget)

from app.qt import apply_window_icon
from prototype_2d.blast_event_service import BlastEventService, BlastEventValidationError
from prototype_2d.blast_event_storage import load_blast_event_state, save_blast_event_state
from prototype_2d.domain import BlastEvent, PlanMultiPoint, PlanPolygon


class BlastEventPlanView(QGraphicsView):
    def __init__(self, scene):
        super().__init__(scene); self.setRenderHint(self.renderHints()); self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15; self.scale(factor, factor)
    def fit_to_extent(self):
        rect = self.scene().itemsBoundingRect()
        if not rect.isNull(): self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)


class BlastEventWindow(QMainWindow):
    closed = Signal()
    def __init__(self, parent=None, storage_path=None):
        super().__init__(parent, Qt.WindowType.Window)
        self.storage_path = storage_path
        self.state = load_blast_event_state(storage_path)
        self.service = BlastEventService(self.state)
        self.selected_event: BlastEvent | None = None
        self.setWindowTitle("Blast Events Prototype"); self.resize(1300, 800); self.setMinimumSize(1000, 650); apply_window_icon(self)
        self._build_ui(); self.refresh_events()

    def _build_ui(self):
        root = QSplitter(); self.setCentralWidget(root)
        left = QWidget(); left_layout = QVBoxLayout(left)
        self.filter_combo = QComboBox(); self.filter_combo.addItems(["Активные", "Архив"]); self.filter_combo.currentIndexChanged.connect(self.refresh_events)
        self.event_list = QListWidget(); self.event_list.currentRowChanged.connect(self._select_event)
        create = QPushButton("+ Создать событие"); create.clicked.connect(self.create_event)
        left_layout.addWidget(self.filter_combo); left_layout.addWidget(self.event_list, 1); left_layout.addWidget(create)
        root.addWidget(left)
        centre = QWidget(); centre_layout = QVBoxLayout(centre)
        actions = QHBoxLayout(); fit = QPushButton("Вписать в экран"); fit.clicked.connect(lambda: self.plan_view.fit_to_extent())
        self.grid_button = QPushButton("Сетка"); self.grid_button.setCheckable(True); self.grid_button.setChecked(True); self.grid_button.toggled.connect(lambda _: self.draw_geometry())
        actions.addWidget(fit); actions.addWidget(self.grid_button); actions.addStretch(); centre_layout.addLayout(actions)
        self.scene = QGraphicsScene(self); self.plan_view = BlastEventPlanView(self.scene); centre_layout.addWidget(self.plan_view, 1); root.addWidget(centre)
        self.card = QWidget(); self.card_layout = QVBoxLayout(self.card); self.card_layout.addWidget(QLabel("Выберите событие")); self.card_layout.addStretch(); root.addWidget(self.card); root.setSizes([250, 700, 300])

    def _events(self): return [e for e in self.state.blast_events if e.is_archived == (self.filter_combo.currentIndex() == 1)]
    def refresh_events(self):
        prior = self.selected_event.id if self.selected_event else None; self.event_list.blockSignals(True); self.event_list.clear()
        for event in self._events(): self.event_list.addItem(f"{event.name} ({event.event_type})")
        self.event_list.blockSignals(False)
        row = next((i for i,e in enumerate(self._events()) if e.id == prior), -1); self.event_list.setCurrentRow(row)
        if row < 0: self.selected_event = None; self._render_card(); self.draw_geometry()
    def _select_event(self, row):
        events = self._events(); self.selected_event = events[row] if 0 <= row < len(events) else None; self._render_card(); self.draw_geometry()
    def _clear_card(self):
        while self.card_layout.count():
            item=self.card_layout.takeAt(0); widget=item.widget()
            if widget: widget.deleteLater()
    def _render_card(self):
        self._clear_card(); event = self.selected_event
        if not event: self.card_layout.addWidget(QLabel("Выберите событие")); self.card_layout.addStretch(); return
        revision=event.active_geometry_revision(); details=[("ID",event.id),("Название",event.name),("Тип",event.event_type),("Дата",event.event_date.isoformat() if event.event_date else "—"),("Горизонт",f"{event.elevation:g}"),("Активная ревизия",str(revision.revision_number) if revision else "—"),("CSV",revision.source_file_name if revision else "—"),("Дата импорта",revision.imported_at.isoformat(sep=' ', timespec='minutes') if revision else "—"),("Тип геометрии",revision.plan_geometry.to_dict()['type'] if revision else "—"),("Число ревизий",str(len(event.geometry_revisions))),("Статус","Архив" if event.is_archived else "Активно")]
        form=QFormLayout(); [form.addRow(a, QLabel(b)) for a,b in details]; self.card_layout.addLayout(form)
        reimport=QPushButton("Переимпортировать геометрию"); reimport.clicked.connect(self.reimport_geometry); self.card_layout.addWidget(reimport)
        archive=QPushButton("Восстановить" if event.is_archived else "Архивировать"); archive.clicked.connect(self.toggle_archive); self.card_layout.addWidget(archive); self.card_layout.addStretch()
    def draw_geometry(self):
        self.scene.clear(); event=self.selected_event
        if not event or not event.active_geometry_revision(): return
        geometry=event.active_geometry_revision().plan_geometry
        if isinstance(geometry, PlanPolygon):
            ring=geometry.ring; path=QPainterPath(); path.moveTo(ring[0].x,-ring[0].y)
            for point in ring[1:]: path.lineTo(point.x,-point.y)
            item=QGraphicsPathItem(path); item.setPen(QPen(QColor(210,70,20),2)); item.setBrush(QBrush(QColor(255,150,40,70))); self.scene.addItem(item)
        elif isinstance(geometry, PlanMultiPoint):
            for point in geometry.points:
                item=QGraphicsEllipseItem(-4,-4,8,8); item.setPos(point.x,-point.y); item.setBrush(QColor(30,100,220)); self.scene.addItem(item)
        if self.grid_button.isChecked(): self._add_grid()
        self.plan_view.fit_to_extent()
    def _add_grid(self):
        rect=self.scene.itemsBoundingRect()
        if rect.isNull(): return
        step=max(max(rect.width(),rect.height())/10, 1); pen=QPen(QColor(225,225,225), 0)
        x=rect.left()
        while x<=rect.right(): self.scene.addLine(x,rect.top(),x,rect.bottom(),pen); x+=step
        y=rect.top()
        while y<=rect.bottom(): self.scene.addLine(rect.left(),y,rect.right(),y,pen); y+=step
    def create_event(self):
        dialog=BlastEventDialog(self)
        if dialog.exec() != dialog.DialogCode.Accepted: return
        try:
            self.selected_event=self.service.create_event(**dialog.values()); self._save(); self.refresh_events()
        except Exception as exc: QMessageBox.warning(self,"Не удалось создать событие",str(exc))
    def reimport_geometry(self):
        if not self.selected_event: return
        path,_=QFileDialog.getOpenFileName(self,"Выберите CSV", "", "CSV (*.csv)")
        if not path: return
        try: self.service.reimport_geometry(self.selected_event,path); self._save(); self._render_card(); self.draw_geometry()
        except Exception as exc: QMessageBox.warning(self,"Ошибка переимпорта",str(exc))
    def toggle_archive(self):
        if not self.selected_event: return
        self.selected_event.restore() if self.selected_event.is_archived else self.selected_event.archive(); self._save(); self.refresh_events()
    def _save(self): save_blast_event_state(self.state,self.storage_path)
    def closeEvent(self,event): self._save(); self.closed.emit(); super().closeEvent(event)


class BlastEventDialog(QDialog):
    # QDialog-like small form without dependence on the old prototype workflow.
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle("Создать Blast Event")
        layout=QVBoxLayout(self); form=QFormLayout(); self.name=QLineEdit(); self.kind=QComboBox(); self.kind.addItem("production"); self.kind.addItem("contour"); self.date=QDateEdit(QDate.currentDate()); self.date.setCalendarPopup(True); self.elevation=QDoubleSpinBox(); self.elevation.setRange(-10000,10000); self.elevation.setDecimals(2); self.csv=QLineEdit(); browse=QPushButton("Выбрать CSV")
        def select(): self.csv.setText(QFileDialog.getOpenFileName(self,"Выберите CSV","","CSV (*.csv)")[0])
        browse.clicked.connect(select); row=QHBoxLayout(); row.addWidget(self.csv); row.addWidget(browse); form.addRow("Название *",self.name); form.addRow("Тип *",self.kind); form.addRow("Дата",self.date); form.addRow("Горизонт *",self.elevation); form.addRow("CSV Datamine *",row); layout.addLayout(form); buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel); buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); layout.addWidget(buttons)
    def values(self): return {"name":self.name.text(),"event_type":self.kind.currentText(),"event_date":self.date.date().toPython(),"elevation":self.elevation.value(),"csv_path":self.csv.text()}
