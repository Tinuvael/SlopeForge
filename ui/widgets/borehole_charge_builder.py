"""Reusable, persistence-free editor for a composable borehole charge draft."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal, ROUND_HALF_UP
import math
from uuid import uuid4

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QComboBox, QDoubleSpinBox, QFormLayout, QGraphicsScene, QGraphicsView,
    QHBoxLayout, QLabel, QMenu, QMessageBox, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from app.localization import tr
from domain.blasting.charge_design import (
    ChargeComponent, ChargeComponentKind, ChargeDesignValidationError,
    ExplosiveProduct, ExplosiveProductKind, available_air_intervals,
    cartridge_depths, validate_components,
)

AIR_COLOR = "#7EA9CC"
STEMMING_COLOR = "#30343B"
DEPTH_STEP = Decimal("0.1")


def snap_depth(value: float) -> float:
    """Snap a depth to the nearest decimetre without binary accumulation."""
    if not math.isfinite(value):
        raise ValueError("Depth must be finite")
    return float((Decimal(str(value)) / DEPTH_STEP).quantize(Decimal("1"),
                                                              rounding=ROUND_HALF_UP) * DEPTH_STEP)


def depth_to_scene_y(depth: float, hole_depth: float, top: float, height: float) -> float:
    return top + (depth / hole_depth) * height


def scene_y_to_depth(y: float, hole_depth: float, top: float, height: float) -> float:
    return ((y - top) / height) * hole_depth


class BoreholeView(QGraphicsView):
    """Graphics view that delegates selection and deterministic vertical drags."""
    def __init__(self, builder):
        super().__init__(builder)
        self.builder = builder
        self.setObjectName("boreholeView")
        self.setScene(QGraphicsScene(self))
        self.setMinimumSize(280, 330)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setStyleSheet("QGraphicsView { background: #FAFBFC; border: 1px solid #CCD3DB; }")
        self._drag = None
        self._drag_origin_depth = 0.0

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.builder._render()

    def mousePressEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        role = item.data(0) if item else None
        payload = item.data(1) if item else None
        if role == "air":
            self.builder.select_air(tuple(payload)); event.accept(); return
        if role in {"component", "start", "end"}:
            self.builder.select_component(str(payload))
            if not self.builder.read_only:
                self._drag = (role, str(payload))
                self._drag_origin_depth = self.builder._depth_at_view_y(event.position().y())
            event.accept(); return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag:
            role, component_id = self._drag
            depth = self.builder._depth_at_view_y(event.position().y())
            self.builder._drag_component(component_id, role, depth, self._drag_origin_depth)
            if role == "component":
                self._drag_origin_depth = depth
            event.accept(); return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag = None
        super().mouseReleaseEvent(event)


class BoreholeChargeBuilder(QWidget):
    """Own and edit a draft list of immutable :class:`ChargeComponent` values."""
    components_changed = Signal(list)

    def __init__(self, hole_depth_m, hole_diameter_mm, products, components,
                 read_only=False, parent=None):
        super().__init__(parent)
        self._hole_depth_m = float(hole_depth_m)
        self._hole_diameter_mm = hole_diameter_mm
        self._products = list(products)
        self._components = list(components)
        validate_components(self._components, self._hole_depth_m)
        self.read_only = bool(read_only)
        self._selected_component_id = None
        self._selected_air = None
        self._updating = False
        self._scene_top, self._scene_height = 28.0, 300.0
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(6, 6, 6, 6); root.setSpacing(6)
        self.add_button = QPushButton(tr("Add component")); self.add_button.setObjectName("addComponentButton")
        self.add_button.clicked.connect(self._show_add_menu); root.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignLeft)
        body = QHBoxLayout(); root.addLayout(body, 1)
        self.view = BoreholeView(self); body.addWidget(self.view, 1)
        panel = QWidget(); panel.setMaximumWidth(245); form = QFormLayout(panel)
        self.type_label = QLabel("—"); form.addRow(tr("Type"), self.type_label)
        self.start_spin = self._depth_spin("componentStartSpin"); form.addRow(tr("Start depth, m"), self.start_spin)
        self.end_spin = self._depth_spin("componentEndSpin"); form.addRow(tr("End depth, m"), self.end_spin)
        self.length_spin = self._depth_spin("componentLengthSpin"); form.addRow(tr("Length, m"), self.length_spin)
        self.product_label = QLabel(tr("Product")); self.product_combo = QComboBox(); self.product_combo.setObjectName("componentProductCombo")
        form.addRow(self.product_label, self.product_combo)
        self.pitch_label = QLabel(tr("Pitch, m")); self.pitch_spin = QDoubleSpinBox(); self.pitch_spin.setObjectName("cartridgePitchSpin")
        self.pitch_spin.setRange(0.001, 10000); self.pitch_spin.setDecimals(3); self.pitch_spin.setSingleStep(0.05)
        form.addRow(self.pitch_label, self.pitch_spin)
        self.count_title = QLabel(tr("Cartridge count")); self.count_label = QLabel("—"); self.count_label.setObjectName("cartridgeCountLabel")
        form.addRow(self.count_title, self.count_label)
        self.feedback = QLabel(); self.feedback.setStyleSheet("color: #A33;"); self.feedback.setWordWrap(True); form.addRow(self.feedback)
        self.delete_button = QPushButton(tr("Delete component")); self.delete_button.setObjectName("deleteComponentButton")
        self.delete_button.clicked.connect(self.delete_selected_component); form.addRow(self.delete_button)
        body.addWidget(panel)
        self.legend = QLabel(); self.legend.setObjectName("chargeLegend"); self.legend.setTextFormat(Qt.TextFormat.RichText)
        root.addWidget(self.legend)
        self.start_spin.editingFinished.connect(lambda: self._numeric_edit("start"))
        self.end_spin.editingFinished.connect(lambda: self._numeric_edit("end"))
        self.length_spin.editingFinished.connect(lambda: self._numeric_edit("length"))
        self.pitch_spin.editingFinished.connect(self._pitch_edit)
        self.product_combo.currentIndexChanged.connect(self._product_changed)

    def _depth_spin(self, name):
        spin = QDoubleSpinBox(); spin.setObjectName(name); spin.setRange(0, 100000)
        spin.setDecimals(1); spin.setSingleStep(0.1); return spin

    def components(self): return list(self._components)
    def hole_depth(self): return self._hole_depth_m
    def air_intervals(self): return available_air_intervals(self._hole_depth_m, self._components)

    def set_components(self, components):
        draft = list(components); validate_components(draft, self._hole_depth_m)
        self._components = draft; self._selected_component_id = None; self._selected_air = None; self._refresh()

    def set_products(self, products): self._products = list(products); self._refresh()

    def set_hole_depth(self, new_depth):
        try: validate_components(self._components, float(new_depth))
        except (ValueError, ChargeDesignValidationError) as exc:
            self._feedback(str(exc)); return False
        self._hole_depth_m = float(new_depth); self._selected_air = None; self._refresh(); return True

    def set_hole_diameter(self, diameter):
        if diameter is not None and (not math.isfinite(float(diameter)) or float(diameter) <= 0):
            raise ValueError("Hole diameter must be positive or None")
        self._hole_diameter_mm = None if diameter is None else float(diameter); self._render()

    def set_read_only(self, read_only): self.read_only = bool(read_only); self._refresh()

    def select_air(self, interval):
        if interval not in self.air_intervals(): return
        self._selected_air = interval; self._selected_component_id = None; self._refresh()

    def select_component(self, component_id):
        if not any(c.id == component_id for c in self._components): return
        self._selected_component_id = component_id; self._selected_air = None; self._refresh()

    def _selected(self):
        return next((c for c in self._components if c.id == self._selected_component_id), None)

    def _insertion_interval(self):
        gaps = self.air_intervals()
        if self._selected_air in gaps and self._selected_air[1] - self._selected_air[0] >= .1 - 1e-9:
            return self._selected_air
        return next((gap for gap in gaps if gap[1] - gap[0] >= .1 - 1e-9), None)

    def add_component(self, kind, product=None):
        if self.read_only: return False
        gap = self._insertion_interval()
        if gap is None:
            self._feedback(tr("No air interval has 0.1 m available.")); return False
        start, end = snap_depth(gap[0]), snap_depth(gap[0] + .1)
        snapshot = product.snapshot() if product is not None else None
        pitch = product.default_pitch_m if kind is ChargeComponentKind.CARTRIDGE_EXPLOSIVE else None
        if kind is ChargeComponentKind.CARTRIDGE_EXPLOSIVE and pitch is None: pitch = .1
        component = ChargeComponent(f"charge-{uuid4()}", kind, start, end, snapshot, pitch)
        self._components.append(component); self._components.sort(key=lambda c: c.start_depth_m)
        self._selected_component_id = component.id; self._selected_air = None
        self._changed(); return True

    def add_stemming(self): return self.add_component(ChargeComponentKind.STEMMING)

    def _show_add_menu(self):
        menu = QMenu(self); stem = menu.addAction(tr("Stemming")); stem.triggered.connect(self.add_stemming)
        enabled = [p for p in self._products if p.enabled]
        for title, product_kind, component_kind in (
            (tr("Bulk explosive"), ExplosiveProductKind.BULK, ChargeComponentKind.BULK_EXPLOSIVE),
            (tr("Cartridge explosive"), ExplosiveProductKind.CARTRIDGE, ChargeComponentKind.CARTRIDGE_EXPLOSIVE)):
            submenu = menu.addMenu(title); matches = [p for p in enabled if p.kind is product_kind]
            if not matches: submenu.addAction(tr("No explosive products configured")).setEnabled(False)
            for product in matches:
                action = submenu.addAction(product.name)
                action.triggered.connect(lambda _checked=False, k=component_kind, p=product: self.add_component(k, p))
        menu.exec(self.add_button.mapToGlobal(self.add_button.rect().bottomLeft()))

    def delete_selected_component(self):
        selected = self._selected()
        if self.read_only or selected is None: return False
        old_start = selected.start_depth_m
        self._components = [c for c in self._components if c.id != selected.id]
        self._selected_component_id = None
        self._selected_air = next((g for g in self.air_intervals() if g[0] <= old_start <= g[1]), None)
        self._changed(); return True

    def _replace_selected(self, replacement):
        trial = [replacement if c.id == replacement.id else c for c in self._components]
        try: validate_components(trial, self._hole_depth_m)
        except ChargeDesignValidationError as exc: self._feedback(str(exc)); self._refresh(); return False
        self._components = sorted(trial, key=lambda c: c.start_depth_m); self._changed(); return True

    def _numeric_edit(self, field):
        if self._updating or self.read_only: return
        component = self._selected()
        if not component: return
        if field == "start": start, end = snap_depth(self.start_spin.value()), component.end_depth_m
        elif field == "end": start, end = component.start_depth_m, snap_depth(self.end_spin.value())
        else: start, end = component.start_depth_m, snap_depth(component.start_depth_m + self.length_spin.value())
        try: replacement = replace(component, start_depth_m=start, end_depth_m=end)
        except ChargeDesignValidationError as exc: self._feedback(str(exc)); self._refresh(); return
        self._replace_selected(replacement)

    def _pitch_edit(self):
        if self._updating or self.read_only: return
        component = self._selected()
        if component and component.kind is ChargeComponentKind.CARTRIDGE_EXPLOSIVE:
            self._replace_selected(replace(component, cartridge_pitch_m=self.pitch_spin.value()))

    def _product_changed(self, index):
        if self._updating or self.read_only or index < 0: return
        component, product = self._selected(), self.product_combo.itemData(index)
        if component and isinstance(product, ExplosiveProduct):
            self._replace_selected(replace(component, product_snapshot=product.snapshot()))

    def _drag_component(self, component_id, role, depth, origin_depth):
        component = next((c for c in self._components if c.id == component_id), None)
        if not component: return
        target = snap_depth(depth)
        if role == "start": start, end = target, component.end_depth_m
        elif role == "end": start, end = component.start_depth_m, target
        else:
            delta = snap_depth(depth - origin_depth)
            if delta == 0: return
            start, end = snap_depth(component.start_depth_m + delta), snap_depth(component.end_depth_m + delta)
        try: replacement = replace(component, start_depth_m=start, end_depth_m=end)
        except ChargeDesignValidationError: return
        self._replace_selected(replacement)

    def _depth_at_view_y(self, y):
        scene_y = self.view.mapToScene(0, int(y)).y()
        return scene_y_to_depth(scene_y, self._hole_depth_m, self._scene_top, self._scene_height)

    def _changed(self):
        self.feedback.clear(); self._refresh(); self.components_changed.emit(self.components())

    def _feedback(self, text): self.feedback.setText(text)

    def _refresh(self):
        selected = self._selected(); self._updating = True
        editable = selected is not None and not self.read_only
        self.add_button.setEnabled(not self.read_only and self._insertion_interval() is not None)
        self.delete_button.setEnabled(editable)
        for spin in (self.start_spin, self.end_spin, self.length_spin): spin.setEnabled(editable)
        if selected:
            names = {ChargeComponentKind.STEMMING: tr("Stemming"), ChargeComponentKind.BULK_EXPLOSIVE: tr("Bulk explosive"), ChargeComponentKind.CARTRIDGE_EXPLOSIVE: tr("Cartridge explosive")}
            self.type_label.setText(names[selected.kind]); self.start_spin.setValue(selected.start_depth_m)
            self.end_spin.setValue(selected.end_depth_m); self.length_spin.setValue(selected.length_m)
        else: self.type_label.setText("—")
        explosive = selected is not None and selected.kind is not ChargeComponentKind.STEMMING
        cartridge = selected is not None and selected.kind is ChargeComponentKind.CARTRIDGE_EXPLOSIVE
        self.product_label.setVisible(explosive); self.product_combo.setVisible(explosive)
        self.pitch_label.setVisible(cartridge); self.pitch_spin.setVisible(cartridge)
        self.count_title.setVisible(cartridge); self.count_label.setVisible(cartridge)
        self.product_combo.clear()
        if explosive:
            snapshot = selected.product_snapshot
            self.product_combo.addItem(f"{snapshot.name} ({tr('current snapshot')})", None)
            target_kind = snapshot.kind
            for product in self._products:
                if product.enabled and product.kind is target_kind:
                    self.product_combo.addItem(product.name, product)
            self.product_combo.setEnabled(not self.read_only)
        if cartridge:
            self.pitch_spin.setValue(selected.cartridge_pitch_m)
            self.pitch_spin.setEnabled(not self.read_only)
            self.count_label.setText(str(len(cartridge_depths(selected))))
        self._updating = False; self._render(); self._render_legend()

    def _render(self):
        scene = self.view.scene(); scene.clear()
        width = max(260, self.view.viewport().width() - 8); height = max(300, self.view.viewport().height() - 12)
        self._scene_top, self._scene_height = 28.0, height - 56.0
        bore_x, bore_w = width * .46, max(48.0, min(90.0, width * .24))
        scene.setSceneRect(0, 0, width, height)
        scene.addText(tr("Collar")).setPos(bore_x + bore_w + 8, 4)
        toe = scene.addText(f"{tr('Toe')} · {self._hole_depth_m:.1f} m"); toe.setPos(bore_x + bore_w + 8, height - 27)
        tick_count = max(1, min(10, int(math.ceil(self._hole_depth_m))))
        for index in range(tick_count + 1):
            depth = self._hole_depth_m * index / tick_count; y = depth_to_scene_y(depth, self._hole_depth_m, self._scene_top, self._scene_height)
            scene.addLine(bore_x - 7, y, bore_x, y, QPen(QColor("#65717E")))
            label = scene.addText(f"{depth:.1f}"); label.setPos(bore_x - 45, y - 10)
        for gap in self.air_intervals():
            y1 = depth_to_scene_y(gap[0], self._hole_depth_m, self._scene_top, self._scene_height); y2 = depth_to_scene_y(gap[1], self._hole_depth_m, self._scene_top, self._scene_height)
            pen = QPen(QColor("#2F6FA5"), 2 if gap == self._selected_air else 1)
            item = scene.addRect(bore_x, y1, bore_w, y2-y1, pen, QBrush(QColor(AIR_COLOR)))
            item.setData(0, "air"); item.setData(1, list(gap)); item.setToolTip(f"{tr('Air')}: {gap[0]:.1f}–{gap[1]:.1f} m")
            if y2-y1 >= 18: text = scene.addText(tr("Air")); text.setDefaultTextColor(QColor("#163A58")); text.setPos(bore_x+5, (y1+y2)/2-10)
        for component in self._components: self._draw_component(scene, component, bore_x, bore_w)
        scene.addRect(bore_x, self._scene_top, bore_w, self._scene_height, QPen(QColor("#222A33"), 2), QBrush(Qt.BrushStyle.NoBrush))

    def _draw_component(self, scene, component, x, width):
        y1 = depth_to_scene_y(component.start_depth_m, self._hole_depth_m, self._scene_top, self._scene_height)
        y2 = depth_to_scene_y(component.end_depth_m, self._hole_depth_m, self._scene_top, self._scene_height)
        name = tr("Stemming") if component.kind is ChargeComponentKind.STEMMING else component.product_snapshot.name
        color = STEMMING_COLOR if component.kind is ChargeComponentKind.STEMMING else component.product_snapshot.display_color
        selected = component.id == self._selected_component_id
        pen = QPen(QColor("#1267A5") if selected else QColor("#343B44"), 3 if selected else 1)
        if component.kind is ChargeComponentKind.CARTRIDGE_EXPLOSIVE:
            body = scene.addRect(x, y1, width, y2-y1, pen, QBrush(QColor("#F7F8FA")))
            ratio = component.product_snapshot.cartridge_diameter_mm / self._hole_diameter_mm if self._hole_diameter_mm else .55
            marker_w = width * max(.25, min(.85, ratio)); marker_h = max(4.0, min(12.0, self._scene_height / self._hole_depth_m * .08))
            for depth in cartridge_depths(component):
                cy = depth_to_scene_y(depth, self._hole_depth_m, self._scene_top, self._scene_height)
                scene.addEllipse(x+(width-marker_w)/2, cy-marker_h/2, marker_w, marker_h, QPen(QColor(color)), QBrush(QColor(color)))
        else: body = scene.addRect(x, y1, width, y2-y1, pen, QBrush(QColor(color)))
        body.setData(0, "component"); body.setData(1, component.id); body.setToolTip(f"{name}: {component.start_depth_m:.1f}–{component.end_depth_m:.1f} m")
        if y2-y1 >= 18:
            label = scene.addText(name); label.setDefaultTextColor(QColor("white") if component.kind is ChargeComponentKind.STEMMING else QColor("#16202A")); label.setPos(x+4, (y1+y2)/2-10)
        if selected:
            for role, y in (("start", y1), ("end", y2)):
                handle = scene.addRect(x-6, y-4, width+12, 8, QPen(QColor("#1267A5")), QBrush(QColor("#D8EAF7")))
                handle.setData(0, role); handle.setData(1, component.id); handle.setToolTip(tr("Drag bound (0.1 m snap)"))

    def _render_legend(self):
        entries = [(tr("Air"), AIR_COLOR), (tr("Stemming"), STEMMING_COLOR)]
        seen = set()
        for component in self._components:
            if component.product_snapshot and (component.product_snapshot.name, component.product_snapshot.display_color) not in seen:
                pair = (component.product_snapshot.name, component.product_snapshot.display_color); entries.append(pair); seen.add(pair)
        self.legend.setText(" &nbsp; ".join(f'<span style="color:{color}">■</span> {name}' for name, color in entries))
