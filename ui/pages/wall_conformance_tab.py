from __future__ import annotations

from math import hypot
from types import SimpleNamespace

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QGraphicsScene,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.localization import tr
from app.use_case_factory import create_project_surface_dataset_service
from application.services.wall_conformance import (
    WallConformanceDiagnosticService,
    WallConformanceDiagnosticSettings,
)
from domain.geometry.types import PlanPolygon
from domain.wall_conformance.models import SectionPoint
from ui.widgets.design_system import set_status_role
from ui.widgets.plan_view import PlanView


class WallConformancePlanWidget(QWidget):
    profile_selected = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.scene = QGraphicsScene(self)
        self.view = PlanView(self.scene)
        self.view.scene_clicked.connect(self._select_nearest_profile)
        # Read-only section selection uses the PlanView's existing left-click
        # domain-coordinate signal. Middle-drag remains available for panning.
        self.view.set_polygon_drawing_mode(True)
        self._profiles = ()
        self._profile_items = []
        self._area_item = None
        self._crest_item = None
        self._toe_items = []
        self._half_width_m = 12.0
        self._selected_index = -1

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        title = QLabel(tr("Plan / transverse profiles"))
        title.setObjectName("EngineeringSectionTitle")
        bar.addWidget(title)
        bar.addStretch()
        fit = QPushButton(tr("Fit"))
        fit.clicked.connect(self.view.fit_to_extent)
        bar.addWidget(fit)
        root.addLayout(bar)
        self.legend = QLabel()
        self.legend.setObjectName("MutedText")
        self.legend.setWordWrap(True)
        self.legend.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        root.addWidget(self.legend)
        root.addWidget(self.view, 1)
        self._apply_theme()

    @staticmethod
    def _dark_theme() -> bool:
        app = QApplication.instance()
        return bool(app is not None and app.property("slopeforgeTheme") == "dark")

    @classmethod
    def _colors(cls):
        if cls._dark_theme():
            return {
                "background": QColor("#252c36"),
                "area": QColor("#5aa7e8"),
                "area_fill": QColor(90, 167, 232, 26),
                "crest": QColor("#8bd39a"),
                "toe": QColor("#79b9ee"),
                "profile": QColor("#718096"),
                "selected": QColor("#f0c66e"),
            }
        return {
            "background": QColor("#f8fafc"),
            "area": QColor("#1261a0"),
            "area_fill": QColor(18, 97, 160, 22),
            "crest": QColor("#2f855a"),
            "toe": QColor("#4f78a8"),
            "profile": QColor("#94a3b8"),
            "selected": QColor("#d97706"),
        }

    def _legend_html(self) -> str:
        colors = self._colors()
        def swatch(key):
            return f'<span style="color:{colors[key].name()}">&#9632;</span>'
        return (
            f"{swatch('area')} {tr('Assessment area')} · "
            f"{swatch('crest')} {tr('Design crest')} · "
            f"{swatch('toe')} {tr('Design toe')} · "
            f"{swatch('profile')} {tr('Profiles')} · "
            f"{swatch('selected')} {tr('Selected profile')}"
        )

    def _apply_theme(self):
        colors = self._colors()
        self.legend.setText(self._legend_html())
        self.scene.setBackgroundBrush(QBrush(colors["background"]))
        if self._area_item is not None:
            self._area_item.setPen(self._cosmetic_pen(colors["area"], 2.0))
            self._area_item.setBrush(QBrush(colors["area_fill"]))
        if self._crest_item is not None:
            self._crest_item.setPen(self._cosmetic_pen(colors["crest"], 3.0))
        toe_pen = self._cosmetic_pen(colors["toe"], 2.0, Qt.PenStyle.DashLine)
        for item in self._toe_items:
            item.setPen(toe_pen)
        for index, item in enumerate(self._profile_items):
            item.setPen(self._profile_pen(index == self._selected_index))
        self.view.viewport().update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self._apply_theme()

    @classmethod
    def _profile_pen(cls, selected: bool) -> QPen:
        colors = cls._colors()
        pen = QPen(
            colors["selected"] if selected else colors["profile"],
            3.0 if selected else 1.0,
        )
        pen.setCosmetic(True)
        return pen

    @staticmethod
    def _cosmetic_pen(color: QColor, width: float, style=Qt.PenStyle.SolidLine) -> QPen:
        pen = QPen(color, width, style)
        pen.setCosmetic(True)
        return pen

    @staticmethod
    def _polygon_path(polygon: PlanPolygon) -> QPainterPath:
        path = QPainterPath()
        if not polygon.ring:
            return path
        path.moveTo(QPointF(polygon.ring[0].x, -polygon.ring[0].y))
        for point in polygon.ring[1:]:
            path.lineTo(QPointF(point.x, -point.y))
        path.closeSubpath()
        return path

    @staticmethod
    def _line_path(points) -> QPainterPath:
        path = QPainterPath()
        if not points:
            return path
        path.moveTo(QPointF(points[0].x, -points[0].y))
        for point in points[1:]:
            path.lineTo(QPointF(point.x, -point.y))
        return path

    def set_result(self, assessment_polygon: PlanPolygon, diagnostic_result) -> None:
        self.scene.clear()
        self._profile_items = []
        self._area_item = None
        self._crest_item = None
        self._toe_items = []
        self._profiles = diagnostic_result.profile_set.profiles
        self._half_width_m = diagnostic_result.settings.half_width_m
        self._selected_index = -1
        colors = self._colors()
        self.scene.setBackgroundBrush(QBrush(colors["background"]))

        area_path = self._polygon_path(assessment_polygon)
        self._area_item = self.scene.addPath(
            area_path,
            self._cosmetic_pen(colors["area"], 2.0),
            QBrush(colors["area_fill"]),
        )
        crest = diagnostic_result.profile_set.crest_line
        self._crest_item = self.scene.addPath(
            self._line_path(crest.points),
            self._cosmetic_pen(colors["crest"], 3.0),
        )
        toe_pen = self._cosmetic_pen(colors["toe"], 2.0, Qt.PenStyle.DashLine)
        for toe in diagnostic_result.profile_set.toe_lines:
            self._toe_items.append(
                self.scene.addPath(self._line_path(toe.points), toe_pen)
            )

        for profile in self._profiles:
            origin = profile.alignment.origin
            nx, ny = profile.alignment.normal_xy
            first = QPointF(
                origin.x - nx * self._half_width_m,
                -(origin.y - ny * self._half_width_m),
            )
            second = QPointF(
                origin.x + nx * self._half_width_m,
                -(origin.y + ny * self._half_width_m),
            )
            self._profile_items.append(
                self.scene.addLine(
                    first.x(), first.y(), second.x(), second.y(), self._profile_pen(False)
                )
            )
        self.view.fit_to_extent()

    def clear_result(self) -> None:
        self.scene.clear()
        self._profiles = ()
        self._profile_items = []
        self._area_item = None
        self._crest_item = None
        self._toe_items = []
        self._selected_index = -1
        self._apply_theme()

    def set_selected_profile(self, index: int) -> None:
        if not 0 <= index < len(self._profile_items):
            self._selected_index = -1
        else:
            self._selected_index = index
        for item_index, item in enumerate(self._profile_items):
            item.setPen(self._profile_pen(item_index == self._selected_index))

    @staticmethod
    def _distance_to_segment(px, py, ax, ay, bx, by) -> float:
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        if length_sq <= 1e-18:
            return hypot(px - ax, py - ay)
        fraction = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_sq))
        x = ax + dx * fraction
        y = ay + dy * fraction
        return hypot(px - x, py - y)

    def _scene_tolerance(self) -> float:
        left = self.view.mapToScene(QPoint(0, 0))
        right = self.view.mapToScene(QPoint(8, 0))
        return max(abs(right.x() - left.x()), 0.5)

    def _select_nearest_profile(self, x: float, y: float) -> None:
        if not self._profiles:
            return
        candidates = []
        for index, profile in enumerate(self._profiles):
            origin = profile.alignment.origin
            nx, ny = profile.alignment.normal_xy
            ax = origin.x - nx * self._half_width_m
            ay = origin.y - ny * self._half_width_m
            bx = origin.x + nx * self._half_width_m
            by = origin.y + ny * self._half_width_m
            candidates.append((self._distance_to_segment(x, y, ax, ay, bx, by), index))
        distance, index = min(candidates)
        if distance <= self._scene_tolerance():
            self.profile_selected.emit(index)


class WallProfilePlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.profile = None
        self.profile_set = None
        self.variant_index = 0
        self.mode = "empty"
        self.setMinimumSize(340, 280)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @staticmethod
    def _dark_theme() -> bool:
        app = QApplication.instance()
        return bool(app is not None and app.property("slopeforgeTheme") == "dark")

    @classmethod
    def _colors(cls):
        if cls._dark_theme():
            return {
                "background": QColor("#252c36"),
                "border": QColor("#4a5665"),
                "grid": QColor("#3b4654"),
                "text": QColor("#d5dbe3"),
                "design": QColor("#5aa7e8"),
                "actual": QColor("#f0c66e"),
                "face": QColor("#67c587"),
                "berm": QColor("#5aa7e8"),
                "road": QColor("#b9a4ef"),
                "unknown": QColor("#9aa6b2"),
                "ignore": QColor("#718096"),
            }
        return {
            "background": QColor("#f8fafc"),
            "border": QColor("#d7dde6"),
            "grid": QColor("#e2e8f0"),
            "text": QColor("#475467"),
            "design": QColor("#1261a0"),
            "actual": QColor("#d97706"),
            "face": QColor("#27864f"),
            "berm": QColor("#1261a0"),
            "road": QColor("#7657a8"),
            "unknown": QColor("#7a8696"),
            "ignore": QColor("#94a3b8"),
        }

    def set_profile(self, profile) -> None:
        self.profile = profile
        self.profile_set = None
        self.mode = "selected" if profile is not None else "empty"
        self.update()

    def set_overview(self, profile_set, variant_index: int = 0) -> None:
        self.profile = None
        self.profile_set = profile_set
        self.variant_index = variant_index
        self.mode = "overview"
        self.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self.update()

    def _points(self):
        design, actual = self._geometry()
        return tuple(
            point
            for segment in (*design, *actual)
            for point in (segment.start, segment.end)
        )

    def _geometry(self):
        if self.mode == "selected" and self.profile is not None:
            design = tuple(s for s in self.profile.design_segments if s.semantic_role != "ignore")
            return design, self.profile.actual_segments
        if self.mode != "overview" or not self.profile_set.design_variants:
            return (), ()
        variant = self.profile_set.design_variants[self.variant_index]
        design = tuple(
            SimpleNamespace(
                start=SectionPoint(e.start_u, e.start_dz, e.start_u, 0),
                end=SectionPoint(e.end_u, e.end_dz, e.end_u, 0),
                semantic_role=e.role,
            ) for e in variant.elements if e.role != "ignore"
        )
        actual = []
        for index in variant.profile_indices:
            profile = self.profile_set.profiles[index]
            origin_z = profile.alignment.origin.z
            actual.extend(
                SimpleNamespace(
                    start=SectionPoint(s.start.u, s.start.z-origin_z, s.start.x, s.start.y),
                    end=SectionPoint(s.end.u, s.end.z-origin_z, s.end.x, s.end.y),
                    semantic_role=None,
                ) for s in profile.actual_segments
            )
        return design, tuple(actual)

    @staticmethod
    def _legend_rows(profile):
        design = [(tr("Face"), "face"), (tr("Berm"), "berm"), (tr("Road"), "road")]
        if any(
            getattr(segment, "semantic_role", None) == "unknown"
            for segment in profile.design_segments
        ):
            design.append((tr("Unknown"), "unknown"))
        return tuple(design), ((tr("Survey"), "actual"),)

    @staticmethod
    def _draw_legend_row(painter, rect: QRectF, entries, colors) -> None:
        """Distribute legend entries across the available width without clipping."""
        if not entries:
            return
        slot_width = rect.width() / len(entries)
        metrics = painter.fontMetrics()
        for index, (label, color_key) in enumerate(entries):
            slot = QRectF(
                rect.left() + index * slot_width,
                rect.top(),
                slot_width,
                rect.height(),
            )
            line_width = min(24.0, max(12.0, slot.width() * 0.28))
            text_width = max(1, slot.width() - line_width - 8)
            text = metrics.elidedText(label, Qt.TextElideMode.ElideRight, int(text_width))
            line_left = slot.left() + 4
            line_y = slot.center().y()
            painter.setPen(QPen(colors[color_key], 3))
            painter.drawLine(
                QPointF(line_left, line_y), QPointF(line_left + line_width, line_y)
            )
            painter.setPen(colors["text"])
            painter.drawText(
                QRectF(
                    line_left + line_width + 4,
                    slot.top(),
                    text_width,
                    slot.height(),
                ),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                text,
            )

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = self._colors()
        painter.fillRect(self.rect(), colors["background"])
        painter.setPen(QPen(colors["border"], 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

        points = self._points()
        if not points:
            painter.setPen(colors["text"])
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("No profile selected"))
            return

        left, top, right, bottom = 62, 104, 22, 46
        plot = QRectF(
            left,
            top,
            max(1, self.width() - left - right),
            max(1, self.height() - top - bottom),
        )
        u_values = [point.u for point in points]
        z_values = [point.z for point in points]
        u_min, u_max = min(u_values), max(u_values)
        z_min, z_max = min(z_values), max(z_values)
        if abs(u_max - u_min) < 1e-9:
            u_min -= 1.0
            u_max += 1.0
        if abs(z_max - z_min) < 1e-9:
            z_min -= 1.0
            z_max += 1.0
        u_pad = (u_max - u_min) * 0.06
        z_pad = (z_max - z_min) * 0.08
        u_min, u_max = u_min - u_pad, u_max + u_pad
        z_min, z_max = z_min - z_pad, z_max + z_pad

        def map_point(point):
            x = plot.left() + (point.u - u_min) / (u_max - u_min) * plot.width()
            y = plot.bottom() - (point.z - z_min) / (z_max - z_min) * plot.height()
            return QPointF(x, y)

        painter.setPen(QPen(colors["grid"], 1))
        metrics = QFontMetrics(painter.font())
        for step in range(6):
            fraction = step / 5
            x = plot.left() + plot.width() * fraction
            y = plot.top() + plot.height() * fraction
            painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(colors["text"])
            u_value = u_min + fraction * (u_max - u_min)
            z_value = z_max - fraction * (z_max - z_min)
            painter.drawText(
                QRectF(x - 36, plot.bottom() + 5, 72, metrics.height() + 2),
                Qt.AlignmentFlag.AlignHCenter,
                f"{u_value:.1f}",
            )
            painter.drawText(
                QRectF(2, y - metrics.height() / 2, left - 10, metrics.height() + 2),
                Qt.AlignmentFlag.AlignRight,
                f"{z_value:.1f}",
            )
            painter.setPen(QPen(colors["grid"], 1))

        painter.setPen(QPen(colors["border"], 1))
        painter.drawRect(plot)

        painter.setPen(colors["text"])
        painter.drawText(QRectF(plot.left(), plot.bottom() + 8, plot.width(), 24), Qt.AlignmentFlag.AlignCenter, tr("U (m, + toward wall/toe)"))
        painter.save()
        painter.translate(16, plot.center().y())
        painter.rotate(-90)
        vertical_axis = tr("dZ (m, local Design crest = 0)") if self.mode == "overview" else "Z (m)"
        painter.drawText(QRectF(-plot.height() / 2, -12, plot.height(), 24), Qt.AlignmentFlag.AlignCenter, vertical_axis)
        painter.restore()

        title = tr("Representative Design Profile") if self.mode == "overview" else tr("Transverse section")
        painter.drawText(QRectF(plot.left(), 5, plot.width(), 20), Qt.AlignmentFlag.AlignLeft, title)
        if self.mode == "selected":
            chainage = self.profile.alignment.chainage_m
            painter.drawText(QRectF(plot.left(), 5, plot.width(), 20), Qt.AlignmentFlag.AlignRight, tr("Chainage %1 m").replace("%1", f"{chainage:.1f}"))
        design, actual = self._geometry()
        group_title = tr("REPRESENTATIVE DESIGN") if self.mode == "overview" else tr("DESIGN")
        painter.drawText(QRectF(plot.left(), 27, plot.width(), 18), Qt.AlignmentFlag.AlignLeft, group_title)
        design_entries = [(tr(role.title()), role) for role in ("face", "berm", "road") if any(s.semantic_role == role for s in design)]
        if any(s.semantic_role == "unknown" for s in design):
            design_entries.append((tr("Unknown"), "unknown"))
        actual_label = tr("All profiles") if self.mode == "overview" else tr("Selected profile")
        actual_entries = ((actual_label, "actual"),)
        self._draw_legend_row(
            painter,
            QRectF(plot.left(), 44, plot.width(), 20),
            design_entries,
            colors,
        )
        painter.drawText(QRectF(plot.left(), 65, plot.width(), 18), Qt.AlignmentFlag.AlignLeft, tr("ACTUAL SURVEY"))
        self._draw_legend_row(
            painter,
            QRectF(plot.left(), 81, plot.width(), 20),
            actual_entries,
            colors,
        )

        def draw_segments(segments, color, base_width, semantic=False):
            for segment in segments:
                width = base_width
                role = str(getattr(segment, "semantic_role", "") or "").lower()
                segment_color = colors.get(role, color) if semantic else color
                painter.setPen(QPen(segment_color, width))
                painter.drawLine(map_point(segment.start), map_point(segment.end))

        draw_segments(design, colors["design"], 3.0 if self.mode == "overview" else 2.3, True)
        actual_color = QColor(colors["actual"])
        if self.mode == "overview":
            actual_color.setAlpha(90)
        draw_segments(actual, actual_color, 1.0 if self.mode == "overview" else 2.2)


class WallConformanceTab(QWidget):
    """Read-only diagnostic view for current Project design vs actual surfaces."""

    def __init__(self, context, site_id: int, assessment_polygon: PlanPolygon, parent=None):
        super().__init__(parent)
        self.context = context
        self.site_id = site_id
        self.assessment_polygon = assessment_polygon
        self.service = WallConformanceDiagnosticService(
            create_project_surface_dataset_service(context)
        )
        self.result = None

        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 4)
        root.setSpacing(8)

        setup = QFrame()
        setup.setObjectName("CriterionCard")
        setup_layout = QVBoxLayout(setup)
        setup_layout.setContentsMargins(10, 8, 10, 8)
        setup_layout.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel(tr("Wall conformance diagnostic"))
        title.setObjectName("EngineeringSectionTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        self.calculate_button = QPushButton(tr("Calculate profiles"))
        self.calculate_button.setProperty("role", "primary")
        self.calculate_button.clicked.connect(self.calculate)
        title_row.addWidget(self.calculate_button)
        setup_layout.addLayout(title_row)

        datasets = QGridLayout()
        datasets.setHorizontalSpacing(18)
        datasets.setVerticalSpacing(2)
        self.design_title = QLabel(tr("DESIGN"))
        self.actual_title = QLabel(tr("ACTUAL"))
        self.design_title.setObjectName("EngineeringSectionTitle")
        self.actual_title.setObjectName("EngineeringSectionTitle")
        self.design_metadata = QLabel()
        self.actual_metadata = QLabel()
        for label in (self.design_metadata, self.actual_metadata):
            label.setObjectName("MutedText")
            label.setWordWrap(True)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        datasets.addWidget(self.design_title, 0, 0)
        datasets.addWidget(self.actual_title, 0, 1)
        datasets.addWidget(self.design_metadata, 1, 0)
        datasets.addWidget(self.actual_metadata, 1, 1)
        datasets.setColumnStretch(0, 1)
        datasets.setColumnStretch(1, 1)
        setup_layout.addLayout(datasets)

        controls = QHBoxLayout()
        controls.addWidget(QLabel(tr("Profile spacing")))
        self.spacing = QDoubleSpinBox()
        self.spacing.setRange(0.5, 50.0)
        self.spacing.setDecimals(1)
        self.spacing.setSingleStep(0.5)
        self.spacing.setValue(3.0)
        self.spacing.setSuffix(" m")
        controls.addWidget(self.spacing)
        controls.addSpacing(10)
        controls.addWidget(QLabel(tr("Strike smoothing radius")))
        self.tangent_window = QDoubleSpinBox()
        self.tangent_window.setRange(1.0, 100.0)
        self.tangent_window.setDecimals(1)
        self.tangent_window.setSingleStep(1.0)
        self.tangent_window.setValue(6.0)
        self.tangent_window.setSuffix(" m")
        self.tangent_window.setToolTip(
            tr("Distance along the design crest on each side of the profile used to estimate the local wall strike. Larger values smooth local curvature.")
        )
        controls.addWidget(self.tangent_window)
        controls.addSpacing(10)
        controls.addWidget(QLabel(tr("Section extent")))
        self.half_width = QDoubleSpinBox()
        self.half_width.setRange(2.0, 100.0)
        self.half_width.setDecimals(1)
        self.half_width.setSingleStep(1.0)
        self.half_width.setValue(12.0)
        self.half_width.setPrefix("±")
        self.half_width.setSuffix(" m")
        self.half_width.setToolTip(
            tr("Maximum displayed and intersected distance from the profile origin in local U. The section covers -U to +U; this is not an averaging width.")
        )
        controls.addWidget(self.half_width)
        controls.addStretch()
        setup_layout.addLayout(controls)

        mapping_row = QHBoxLayout()
        self.semantic_mapping = QLabel()
        self.semantic_mapping.setObjectName("MutedText")
        self.semantic_mapping.setToolTip(
            tr("Diagnostic mapping read from the active Design surface attributes.")
        )
        mapping_row.addWidget(self.semantic_mapping, 1)
        self.edit_semantics = QPushButton(tr("Edit design semantics…"))
        self.edit_semantics.clicked.connect(self._edit_design_semantics)
        mapping_row.addWidget(self.edit_semantics)
        setup_layout.addLayout(mapping_row)

        self.status = QLabel(tr("Ready to calculate."))
        self.status.setWordWrap(True)
        set_status_role(self.status, "info")
        setup_layout.addWidget(self.status)
        root.addWidget(setup)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.plan = WallConformancePlanWidget()
        self.plan.profile_selected.connect(lambda index: self._select_profile(index + 1))
        splitter.addWidget(self.plan)

        profile_host = QWidget()
        profile_layout = QVBoxLayout(profile_host)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(6)
        selector_row = QHBoxLayout()
        selector_row.addWidget(QLabel(tr("Profile")))
        self.profile_selector = QComboBox()
        self.profile_selector.setMinimumWidth(180)
        self.profile_selector.currentIndexChanged.connect(self._select_profile)
        selector_row.addWidget(self.profile_selector)
        self.variant_selector = QComboBox()
        self.variant_selector.currentIndexChanged.connect(self._select_variant)
        self.variant_selector.setVisible(False)
        selector_row.addWidget(self.variant_selector)
        self.profile_summary = QLabel("—")
        self.profile_summary.setObjectName("SummaryValue")
        selector_row.addWidget(self.profile_summary)
        self.profile_vectors = QLabel("")
        self.profile_vectors.setObjectName("MutedText")
        self.profile_vectors.setToolTip(
            tr("Diagnostic local tangent (T) and wall-normal (N) unit vectors.")
        )
        selector_row.addWidget(self.profile_vectors)
        selector_row.addStretch()
        profile_layout.addLayout(selector_row)
        self.profile_plot = WallProfilePlot()
        profile_layout.addWidget(self.profile_plot, 1)
        for escape_source in (
            self,
            self.plan.view,
            self.profile_selector,
            self.profile_plot,
        ):
            escape_source.installEventFilter(self)
        self.representative_summary = QLabel()
        self.representative_summary.setObjectName("MutedText")
        self.representative_summary.setWordWrap(True)
        profile_layout.addWidget(self.representative_summary)
        splitter.addWidget(profile_host)
        splitter.setStretchFactor(0, 45)
        splitter.setStretchFactor(1, 55)
        splitter.setSizes([480, 520])
        self.splitter = splitter
        root.addWidget(splitter, 1)
        self._refresh_dataset_metadata()

    @staticmethod
    def _dataset_text(dataset) -> str:
        if dataset is None:
            return tr("No active dataset")
        revision = int(getattr(dataset, "revision_number", 0) or 0)
        source_format = str(getattr(dataset, "source_format", "") or tr("Unknown")).upper()
        triangles = int(getattr(dataset, "triangle_count", 0) or 0)
        return (
            tr("Active revision R%1 · %2 · %3 triangles")
            .replace("%1", str(revision))
            .replace("%2", source_format)
            .replace("%3", f"{triangles:,}")
        )

    def _refresh_dataset_metadata(self) -> None:
        try:
            design, actual = self.service.current_datasets(self.site_id)
        except Exception as exc:
            self.design_metadata.setText(str(exc))
            self.actual_metadata.setText(str(exc))
            return
        self.design_metadata.setText(self._dataset_text(design))
        self.actual_metadata.setText(self._dataset_text(actual))
        if design is None:
            self.semantic_mapping.setText(tr("Design semantics: unavailable"))
            self.edit_semantics.setEnabled(False)
            return
        mapping, fallback = self.service.mapping_for_dataset(design)
        assignments = {
            role: sorted(
                (str(value) for value, assigned in mapping.assignments if assigned == role),
                key=str.casefold,
            )
            for role in ("face", "berm", "road")
        }
        detail = " · ".join(
            f"{tr(role.title())}={','.join(assignments[role])}"
            for role in ("face", "berm", "road")
            if assignments[role]
        )
        prefix = tr("Design semantics: default mapping") if fallback else tr("Design semantics: %1").replace("%1", mapping.attribute_name)
        self.semantic_mapping.setText(f"{prefix} · {detail}")
        self.edit_semantics.setEnabled(bool(getattr(self.service.surface_service, "storage_available", True)))

    def _edit_design_semantics(self) -> None:
        from ui.dialogs.design_surface_semantics_dialog import DesignSurfaceSemanticsDialog

        try:
            dialog = DesignSurfaceSemanticsDialog(self.service, self.site_id, self)
            if dialog.exec():
                self.result = None
                self.profile_selector.clear()
                self.variant_selector.clear()
                self.variant_selector.setVisible(False)
                self.profile_plot.set_profile(None)
                self.plan.clear_result()
                self.profile_summary.setText("—")
                self.profile_vectors.setText("")
                self.representative_summary.clear()
                self._refresh_dataset_metadata()
                self.status.setText(tr("Design surface semantics saved. Calculate profiles again."))
                set_status_role(self.status, "success")
        except Exception as exc:
            self.status.setText(str(exc))
            set_status_role(self.status, "error")

    def _settings(self) -> WallConformanceDiagnosticSettings:
        return WallConformanceDiagnosticSettings(
            spacing_m=self.spacing.value(),
            tangent_window_m=self.tangent_window.value(),
            half_width_m=self.half_width.value(),
        )

    def calculate(self) -> None:
        self.calculate_button.setEnabled(False)
        self.status.setText(tr("Calculating transverse profiles…"))
        set_status_role(self.status, "info")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            self.result = self.service.calculate_current(
                self.site_id,
                self.assessment_polygon,
                self._settings(),
            )
        except Exception as exc:
            self.result = None
            self.profile_selector.clear()
            self.profile_summary.setText("—")
            self.profile_vectors.setText("")
            self.profile_plot.set_profile(None)
            self.status.setText(str(exc))
            set_status_role(self.status, "error")
            self._refresh_dataset_metadata()
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.calculate_button.setEnabled(True)

        self._refresh_dataset_metadata()
        self.plan.set_result(self.assessment_polygon, self.result)
        self.profile_selector.blockSignals(True)
        self.profile_selector.clear()
        self.profile_selector.addItem(tr("Overview · All actual profiles"))
        for index, profile in enumerate(self.result.profile_set.profiles, start=1):
            self.profile_selector.addItem(
                tr("Profile %1 · Ch. %2 m")
                .replace("%1", str(index))
                .replace("%2", f"{profile.alignment.chainage_m:.1f}")
            )
        self.profile_selector.blockSignals(False)
        self.variant_selector.blockSignals(True)
        self.variant_selector.clear()
        for index, variant in enumerate(self.result.profile_set.design_variants, start=1):
            self.variant_selector.addItem(
                tr("Variant %1 · %2 · %3 profiles")
                .replace("%1", str(index))
                .replace("%2", variant.signature)
                .replace("%3", str(len(variant.profile_indices)))
            )
        self.variant_selector.blockSignals(False)
        self.variant_selector.setVisible(self.variant_selector.count() > 1)
        count = len(self.result.profile_set.profiles)
        self.status.setText(
            tr("Calculated %1 transverse profiles from the active Project surfaces.")
            .replace("%1", str(count))
        )
        set_status_role(self.status, "success")
        if count:
            self.profile_selector.setCurrentIndex(0)
            self._select_profile(0)
        else:
            self.profile_summary.setText(tr("No profiles"))
            self.profile_vectors.setText("")
            self.profile_plot.set_profile(None)
            self.plan.set_selected_profile(-1)

    def _select_profile(self, index: int) -> None:
        if self.result is None:
            self.plan.set_selected_profile(-1)
            self.profile_plot.set_profile(None)
            self.profile_summary.setText("—")
            self.profile_vectors.setText("")
            return
        if index == 0:
            self.profile_selector.blockSignals(True)
            self.profile_selector.setCurrentIndex(0)
            self.profile_selector.blockSignals(False)
            self.plan.set_selected_profile(-1)
            self.profile_plot.set_overview(
                self.result.profile_set, max(0, self.variant_selector.currentIndex())
            )
            self.profile_summary.setText(tr("All actual profiles · Select a profile to inspect"))
            self.profile_vectors.setText("")
            self._update_representative_summary()
            return
        profile_index = index - 1
        if not 0 <= profile_index < len(self.result.profile_set.profiles):
            return
        if self.profile_selector.currentIndex() != index:
            self.profile_selector.blockSignals(True)
            self.profile_selector.setCurrentIndex(index)
            self.profile_selector.blockSignals(False)
        profile = self.result.profile_set.profiles[profile_index]
        self.plan.set_selected_profile(profile_index)
        self.profile_plot.set_profile(profile)
        self.representative_summary.clear()
        tx, ty = profile.alignment.tangent_xy
        nx, ny = profile.alignment.normal_xy
        self.profile_summary.setText(
            tr("Profile %1 · Chainage %2 m")
            .replace("%1", str(profile_index + 1))
            .replace("%2", f"{profile.alignment.chainage_m:.1f}")
        )
        self.profile_vectors.setText(tr("Direction details"))
        self.profile_vectors.setToolTip(
            f"T ({tx:.3f}, {ty:.3f}) · N ({nx:.3f}, {ny:.3f})"
        )

    def _select_variant(self, index: int) -> None:
        if self.result is not None and self.profile_selector.currentIndex() == 0:
            self.profile_plot.set_overview(self.result.profile_set, max(0, index))
            self._update_representative_summary()

    def _update_representative_summary(self) -> None:
        variants = self.result.profile_set.design_variants if self.result else ()
        if not variants:
            self.representative_summary.clear()
            return
        variant = variants[max(0, self.variant_selector.currentIndex())]
        lines = [
            tr("REPRESENTATIVE DESIGN"),
            tr("Profiles used: %1").replace("%1", str(len(variant.profile_indices))),
        ]
        counters = {}
        for element in variant.elements:
            counters[element.role] = counters.get(element.role, 0) + 1
            name = f"{tr(element.role.title())} {counters[element.role]}"
            if element.role == "face" and element.angle_median is not None:
                lines.append(
                    tr("%1 · Height %2 m · Angle %3° · range %4–%5°")
                    .replace("%1", name).replace("%2", f"{element.height_median:.1f}")
                    .replace("%3", f"{element.angle_median:.1f}")
                    .replace("%4", f"{element.angle_range[0]:.1f}")
                    .replace("%5", f"{element.angle_range[1]:.1f}")
                )
            else:
                lines.append(
                    tr("%1 · Width %2 m · range %3–%4 m")
                    .replace("%1", name).replace("%2", f"{element.width_median:.1f}")
                    .replace("%3", f"{element.width_range[0]:.1f}")
                    .replace("%4", f"{element.width_range[1]:.1f}")
                )
        self.representative_summary.setText("\n".join(lines))

    def _return_to_overview(self) -> None:
        if self.result is not None and self.profile_selector.currentIndex() > 0:
            self._select_profile(0)

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Escape
            and self.result is not None
            and self.profile_selector.currentIndex() > 0
        ):
            self._return_to_overview()
            event.accept()
            return True
        return super().eventFilter(watched, event)
