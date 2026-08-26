from __future__ import annotations

from math import hypot

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
        self._half_width_m = 12.0
        self._selected_index = -1

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        bar = QHBoxLayout()
        title = QLabel(tr("Plan / transverse profiles"))
        title.setObjectName("EngineeringSectionTitle")
        bar.addWidget(title)
        self.legend = QLabel()
        self.legend.setObjectName("MutedText")
        bar.addWidget(self.legend)
        bar.addStretch()
        fit = QPushButton(tr("Fit"))
        fit.clicked.connect(self.view.fit_to_extent)
        bar.addWidget(fit)
        root.addLayout(bar)
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
        swatch = lambda key: f'<span style="color:{colors[key].name()}">&#9632;</span>'
        return (
            f"{swatch('area')} {tr('Assessment area')} &nbsp; "
            f"{swatch('crest')} {tr('Design crest')} &nbsp; "
            f"{swatch('toe')} {tr('Design toe')} &nbsp; "
            f"{swatch('profile')} {tr('Profiles')} &nbsp; "
            f"{swatch('selected')} {tr('Selected')}"
        )

    def _apply_theme(self):
        colors = self._colors()
        self.legend.setText(self._legend_html())
        self.scene.setBackgroundBrush(QBrush(colors["background"]))
        if not self._profile_items:
            return
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
        self._profiles = diagnostic_result.profile_set.profiles
        self._half_width_m = diagnostic_result.settings.half_width_m
        self._selected_index = -1
        colors = self._colors()
        self.scene.setBackgroundBrush(QBrush(colors["background"]))

        area_path = self._polygon_path(assessment_polygon)
        self.scene.addPath(
            area_path,
            self._cosmetic_pen(colors["area"], 2.0),
            QBrush(colors["area_fill"]),
        )
        crest = diagnostic_result.profile_set.crest_line
        self.scene.addPath(
            self._line_path(crest.points),
            self._cosmetic_pen(colors["crest"], 3.0),
        )
        toe_pen = self._cosmetic_pen(colors["toe"], 2.0, Qt.PenStyle.DashLine)
        for toe in diagnostic_result.profile_set.toe_lines:
            self.scene.addPath(self._line_path(toe.points), toe_pen)

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
        }

    def set_profile(self, profile) -> None:
        self.profile = profile
        self.update()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.StyleChange):
            self.update()

    def _points(self):
        if self.profile is None:
            return ()
        return tuple(
            point
            for segment in (*self.profile.design_segments, *self.profile.actual_segments)
            for point in (segment.start, segment.end)
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

        left, top, right, bottom = 62, 58, 22, 46
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
        painter.drawText(QRectF(plot.left(), plot.bottom() + 8, plot.width(), 24), Qt.AlignmentFlag.AlignCenter, "U (m)")
        painter.save()
        painter.translate(16, plot.center().y())
        painter.rotate(-90)
        painter.drawText(QRectF(-plot.height() / 2, -12, plot.height(), 24), Qt.AlignmentFlag.AlignCenter, "Z (m)")
        painter.restore()

        title = tr("Transverse section")
        chainage = getattr(getattr(self.profile, "alignment", None), "chainage_m", 0.0)
        painter.drawText(QRectF(plot.left(), 5, plot.width(), 20), Qt.AlignmentFlag.AlignLeft, title)
        painter.drawText(
            QRectF(plot.left(), 5, plot.width(), 20),
            Qt.AlignmentFlag.AlignRight,
            tr("Chainage %1 m").replace("%1", f"{chainage:.1f}"),
        )
        painter.drawText(QRectF(plot.left(), 29, 70, 20), Qt.AlignmentFlag.AlignLeft, tr("Design"))
        painter.setPen(QPen(colors["design"], 3))
        painter.drawLine(QPointF(plot.left() + 45, 39), QPointF(plot.left() + 70, 39))
        painter.setPen(colors["text"])
        painter.drawText(QRectF(plot.left() + 84, 29, 70, 20), Qt.AlignmentFlag.AlignLeft, tr("Actual"))
        painter.setPen(QPen(colors["actual"], 3))
        painter.drawLine(QPointF(plot.left() + 127, 39), QPointF(plot.left() + 152, 39))
        painter.setPen(colors["text"])
        semantic_x = plot.left() + 174
        for role in ("face", "berm", "road"):
            painter.setPen(QPen(colors[role], 3))
            painter.drawLine(QPointF(semantic_x, 39), QPointF(semantic_x + 18, 39))
            painter.setPen(colors["text"])
            painter.drawText(QRectF(semantic_x + 22, 29, 48, 20), Qt.AlignmentFlag.AlignLeft, tr(role.title()))
            semantic_x += 72

        def draw_segments(segments, color, base_width, semantic=False):
            for segment in segments:
                width = base_width
                role = str(getattr(segment, "semantic_role", "") or "").lower()
                segment_color = colors.get(role, color) if semantic else color
                painter.setPen(QPen(segment_color, width))
                painter.drawLine(map_point(segment.start), map_point(segment.end))

        draw_segments(self.profile.design_segments, colors["design"], 2.3, True)
        draw_segments(self.profile.actual_segments, colors["actual"], 2.2)


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
        controls.addWidget(QLabel(tr("Strike window")))
        self.tangent_window = QDoubleSpinBox()
        self.tangent_window.setRange(1.0, 100.0)
        self.tangent_window.setDecimals(1)
        self.tangent_window.setSingleStep(1.0)
        self.tangent_window.setValue(6.0)
        self.tangent_window.setSuffix(" m")
        self.tangent_window.setToolTip(
            tr("Distance along the crest used to estimate the local strike direction.")
        )
        controls.addWidget(self.tangent_window)
        controls.addSpacing(10)
        controls.addWidget(QLabel(tr("Profile half-width")))
        self.half_width = QDoubleSpinBox()
        self.half_width.setRange(2.0, 100.0)
        self.half_width.setDecimals(1)
        self.half_width.setSingleStep(1.0)
        self.half_width.setValue(12.0)
        self.half_width.setSuffix(" m")
        self.half_width.setToolTip(
            tr("Distance sampled on each side of the profile origin, normal to the wall.")
        )
        controls.addWidget(self.half_width)
        controls.addStretch()
        setup_layout.addLayout(controls)

        self.semantic_mapping = QLabel(
            tr("Design semantics: COLOUR 2 = Face · COLOUR 5 = Berm · COLOUR 3 = Road")
        )
        self.semantic_mapping.setObjectName("MutedText")
        self.semantic_mapping.setToolTip(
            tr("Diagnostic mapping read from the active Design surface attributes.")
        )
        setup_layout.addWidget(self.semantic_mapping)

        self.status = QLabel(tr("Ready to calculate."))
        self.status.setWordWrap(True)
        set_status_role(self.status, "info")
        setup_layout.addWidget(self.status)
        root.addWidget(setup)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self.plan = WallConformancePlanWidget()
        self.plan.profile_selected.connect(self._select_profile)
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
        for index, profile in enumerate(self.result.profile_set.profiles, start=1):
            self.profile_selector.addItem(
                tr("Profile %1 · Ch. %2 m")
                .replace("%1", str(index))
                .replace("%2", f"{profile.alignment.chainage_m:.1f}")
            )
        self.profile_selector.blockSignals(False)
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
        if self.result is None or not 0 <= index < len(self.result.profile_set.profiles):
            self.plan.set_selected_profile(-1)
            self.profile_plot.set_profile(None)
            self.profile_summary.setText("—")
            self.profile_vectors.setText("")
            return
        if self.profile_selector.currentIndex() != index:
            self.profile_selector.blockSignals(True)
            self.profile_selector.setCurrentIndex(index)
            self.profile_selector.blockSignals(False)
        profile = self.result.profile_set.profiles[index]
        self.plan.set_selected_profile(index)
        self.profile_plot.set_profile(profile)
        tx, ty = profile.alignment.tangent_xy
        nx, ny = profile.alignment.normal_xy
        self.profile_summary.setText(
            tr("Profile %1 · Chainage %2 m")
            .replace("%1", str(index + 1))
            .replace("%2", f"{profile.alignment.chainage_m:.1f}")
        )
        self.profile_vectors.setText(tr("Direction details"))
        self.profile_vectors.setToolTip(
            f"T ({tx:.3f}, {ty:.3f}) · N ({nx:.3f}, {ny:.3f})"
        )
