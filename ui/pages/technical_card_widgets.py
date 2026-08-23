"""Reusable embedded views backed by the existing TechnicalCardDialog editor."""
from __future__ import annotations

from statistics import mean

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.localization import tr
from app.use_case_factory import create_drillhole_dataset_service
from domain.blasting.contour_drilling import summarize_contour_drilling
from domain.blasting.drillholes import summarize_drillholes
from domain.blasting.technical_card import ActualDrillingGroup, BlastDrillingGroup, polygon_area_m2
from domain.geometry.types import PlanPolygon
from ui.dialogs.drillhole_group_assignment_dialog import DrillholeGroupAssignmentDialog
from ui.editors.technical_card_editor import TechnicalCardDialog
from ui.pages.drillhole_dataset_widgets import DrillholeDatasetCard
from ui.presentation_labels import domain_message
from ui.widgets.design_system import set_button_role


DRILLHOLE_FILE_FILTER = (
    "Drillhole files (*.dxf *.dm *.dmx);;AutoCAD DXF (*.dxf);;Datamine files (*.dm *.dmx)"
)


class _DrillholeTechnicalCardDialog(TechnicalCardDialog):
    """The proven Technical Card editor with one non-invasive group action hook."""

    group_assign_callback = None

    def _render_groups(self):
        super()._render_groups()
        callback = getattr(self, "group_assign_callback", None)
        if not callable(callback):
            return
        for index, group in enumerate(self.revision.drilling_groups):
            item = self.group_cards_layout.itemAt(index)
            box = item.widget() if item is not None else None
            if box is None or box.layout() is None:
                continue
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addStretch()
            assign = set_button_role(QPushButton(tr("Assign holes")), "secondary")
            assign.setObjectName("assignDrillholesButton")
            assign.setEnabled(not self.read_only)
            assign.clicked.connect(lambda _checked=False, current=group: callback(current))
            row.addWidget(assign)
            box.layout().addLayout(row)


class _DrillholeEngineeringPage(QWidget):
    """One persisted drillhole dataset card above an existing Technical Card page."""

    def __init__(self, owner: "TechnicalCardEditorWidget", page: QWidget, dataset_kind: str):
        super().__init__()
        self.owner = owner
        self.dataset_kind = dataset_kind
        self.setProperty("blastEventType", owner.editor.blast_event.event_type)
        self.setMinimumHeight(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.dataset_card = DrillholeDatasetCard(
            dataset_kind,
            contour=owner.editor.blast_event.event_type == "contour",
            read_only=owner.editor.read_only,
        )
        self.dataset_card.import_requested.connect(owner.import_drillholes)
        layout.addWidget(self.dataset_card)

        page.setParent(self)
        page.setMinimumHeight(0)
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(page, 1)
        page.setVisible(True)
        self.page = page
        owner._drillhole_pages[dataset_kind] = self
        owner.refresh_drillhole_page(dataset_kind, apply_to_draft=True)


class TechnicalCardEditorWidget(QWidget):
    """Permanently hidden adapter that lends pages from the proven editor."""

    def __init__(
        self,
        event,
        card,
        revision,
        save_callback,
        parent=None,
        read_only=False,
        domain_name="",
        explosive_products=None,
        charge_presets=None,
    ):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Ignored)
        self.setFixedSize(0, 0)
        self.hide()
        self.editor = _DrillholeTechnicalCardDialog(
            event,
            card,
            revision,
            save_callback,
            None,
            read_only,
            domain_name=domain_name,
            explosive_products=explosive_products,
            charge_presets=charge_presets,
        )
        self.tabs = self.editor.tabs
        self._controller = getattr(save_callback, "__self__", None)
        context = getattr(self._controller, "context", None)
        self._drillhole_service = (
            create_drillhole_dataset_service(context)
            if context is not None and hasattr(self._controller, "domain_id")
            else None
        )
        self._drillhole_pages: dict[str, _DrillholeEngineeringPage] = {}
        if self._drillhole_service is not None:
            self.editor.group_assign_callback = self.assign_holes_to_group
            self.editor._render_groups()

    def take_tab(self, title):
        for index in range(self.tabs.count()):
            if self.tabs.tabText(index) == title:
                page = self.tabs.widget(index)
                self.tabs.removeTab(index)
                page.setProperty("blastEventType", self.editor.blast_event.event_type)
                page.setVisible(True)
                if self._drillhole_service is None:
                    return page
                if title in {tr("Drilling and charging"), tr("Contour drilling")}:
                    return _DrillholeEngineeringPage(self, page, "design")
                if title == tr("Execution fact"):
                    return _DrillholeEngineeringPage(self, page, "actual")
                return page
        return QWidget()

    def save_draft(self):
        return False if self.editor.read_only else self.editor._save("draft")

    def _current_row(self, dataset_kind: str):
        if self._drillhole_service is None or self._controller is None:
            return None
        return self._drillhole_service.current(
            self._controller.domain_id,
            self.editor.blast_event.id,
            dataset_kind,
        )

    def _current_holes(self, dataset_kind: str):
        if self._drillhole_service is None or self._controller is None:
            return ()
        return self._drillhole_service.current_holes(
            self._controller.domain_id,
            self.editor.blast_event.id,
            dataset_kind,
        )

    def refresh_drillhole_page(self, dataset_kind: str, *, apply_to_draft: bool = False):
        page = self._drillhole_pages.get(dataset_kind)
        if page is None:
            return
        row = self._current_row(dataset_kind)
        holes = self._current_holes(dataset_kind) if row is not None else ()
        page.dataset_card.set_dataset(row, holes)
        if not apply_to_draft or row is None:
            return
        if dataset_kind == "design" and self.editor.blast_event.event_type == "contour":
            self._apply_contour_design(row, holes)
        elif dataset_kind == "actual":
            if self.editor.blast_event.event_type == "contour":
                self._apply_contour_actual(row)
            else:
                self._apply_actual_group_matches(row)

    def import_drillholes(self, dataset_kind: str):
        if self.editor.read_only or self._drillhole_service is None or self._controller is None:
            return
        title = tr("Import design drillholes") if dataset_kind == "design" else tr("Import as-drilled holes")
        path, _ = QFileDialog.getOpenFileName(self, title, "", tr(DRILLHOLE_FILE_FILTER))
        if not path:
            return
        try:
            user = self._controller.context.current_user
            row = self._drillhole_service.import_dataset(
                self._controller.domain_id,
                self.editor.blast_event.id,
                dataset_kind,
                path,
                imported_by_user_id=user.id,
            )
            holes = self._current_holes(dataset_kind)
            if dataset_kind == "design" and self.editor.blast_event.event_type == "contour":
                self._apply_contour_design(row, holes)
            elif dataset_kind == "actual":
                if self.editor.blast_event.event_type == "contour":
                    self._apply_contour_actual(row)
                else:
                    self._apply_actual_group_matches(row)
            self.refresh_drillhole_page(dataset_kind)
            QMessageBox.information(
                self,
                tr("Drillhole import"),
                tr("Drillholes were imported and derived values were updated in the current Technical Card draft. Save the Technical Card to keep those values."),
            )
        except Exception as exc:
            QMessageBox.warning(self, tr("Drillhole import"), domain_message(str(exc)))

    def assign_holes_to_group(self, group: BlastDrillingGroup):
        if self.editor.read_only or self._drillhole_service is None or self._controller is None:
            return
        holes = self._current_holes("design")
        if not holes:
            QMessageBox.information(
                self,
                tr("Design drillholes"),
                tr("Import design drillholes before assigning holes to drilling groups."),
            )
            return
        selected = {hole.hole_id for hole in holes if hole.engineering_group_id == group.id}
        if (
            self.editor.blast_event.event_type == "contour"
            and not selected
            and not any(hole.engineering_group_id for hole in holes)
        ):
            selected = {hole.hole_id for hole in holes}
        geometry = self.editor.blast_event.active_geometry_revision()
        dialog = DrillholeGroupAssignmentDialog(
            group.name or group.group_type,
            holes,
            selected_ids=selected,
            plan_geometry=geometry.plan_geometry if geometry else None,
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        try:
            self._drillhole_service.assign_design_holes(
                self._controller.domain_id,
                self.editor.blast_event.id,
                group.id,
                dialog.selected_hole_ids,
            )
            assigned = self._drillhole_service.assigned_holes(
                self._controller.domain_id,
                self.editor.blast_event.id,
                group.id,
            )
            self._apply_design_group_metrics(group, assigned)
            self.editor._render_groups()
            self.refresh_drillhole_page("design")
            actual_row = self._current_row("actual")
            if actual_row is not None:
                self._apply_actual_group_matches(actual_row)
                self.refresh_drillhole_page("actual")
        except Exception as exc:
            QMessageBox.warning(self, tr("Assign drillholes"), domain_message(str(exc)))

    def _apply_design_group_metrics(self, group: BlastDrillingGroup, holes) -> None:
        if not holes:
            group.hole_count = 0
            group.planned_drilling_length_m = 0.0
            return
        summary = summarize_drillholes(holes)
        group.hole_count = summary.hole_count
        group.average_depth_m = summary.mean_length_m
        group.planned_drilling_length_m = summary.total_drilling_length_m
        group.inclination_deg = summary.mean_inclination_deg
        group.azimuth_deg = summary.mean_azimuth_deg
        if self.editor.blast_event.event_type == "contour":
            contour = summarize_contour_drilling(holes)
            group.spacing_m = contour.mean_spacing_m
            parameters = self.editor.revision.contour_parameters
            if parameters is not None:
                parameters.hole_count = summary.hole_count
                parameters.average_depth_m = summary.mean_length_m
                parameters.average_spacing_m = contour.mean_spacing_m
                parameters.inclination_deg = summary.mean_inclination_deg
                parameters.line_length_m = contour.line_length_m
        elif self.editor.revision.production_parameters is not None:
            self.editor.revision.production_parameters.recalculate(
                self.editor.revision.drilling_groups
            )

    def _primary_contour_group(self):
        preferred = {
            "contour_line",
            "presplit_line",
            "midsplit_line",
            "postsplit_line",
            "line_drilling",
        }
        included = [group for group in self.editor.revision.drilling_groups if group.included]
        group = next((item for item in included if item.group_type in preferred), None)
        if group is None and included:
            group = included[0]
        if group is None:
            group = BlastDrillingGroup(
                group_type="contour_line",
                name=tr("Contour line"),
                sequence_order=len(self.editor.revision.drilling_groups) + 1,
            )
            self.editor.revision.drilling_groups.append(group)
        return group

    def _apply_contour_design(self, row, holes) -> None:
        if not holes:
            return
        group = self._primary_contour_group()
        assigned = tuple(hole for hole in holes if hole.engineering_group_id == group.id)
        effective_holes = assigned or tuple(holes)
        self._apply_design_group_metrics(group, effective_holes)
        self.editor._render_groups()

    @staticmethod
    def _deviation_values(matches, key: str):
        return [
            float(item[key])
            for item in matches
            if item.get(key) is not None
        ]

    def _set_actual_group_geometry(self, actual, holes, matches) -> None:
        summary = summarize_drillholes(holes)
        actual.hole_count = summary.hole_count
        actual.average_depth_m = summary.mean_length_m
        actual.drilling_length_m = summary.total_drilling_length_m
        actual.inclination_deg = summary.mean_inclination_deg
        actual.azimuth_deg = summary.mean_azimuth_deg
        collar = self._deviation_values(matches, "collar_deviation_3d_m")
        toe = self._deviation_values(matches, "toe_deviation_3d_m")
        actual.mean_collar_deviation_m = mean(collar) if collar else None
        actual.max_collar_deviation_m = max(collar) if collar else None
        actual.mean_toe_deviation_m = mean(toe) if toe else None
        actual.max_toe_deviation_m = max(toe) if toe else None

    def _ensure_actual_group(self, design: BlastDrillingGroup):
        execution = self.editor.revision.actual_execution
        actual = next(
            (item for item in execution.actual_drilling_groups if item.design_group_id == design.id),
            None,
        )
        if actual is None:
            actual = ActualDrillingGroup.from_design(design, self.editor.revision.id)
            execution.actual_drilling_groups.append(actual)
        return actual

    def _recalculate_actual(self):
        execution = self.editor.revision.actual_execution
        geometry = self.editor.blast_event.active_geometry_revision()
        plan = geometry.plan_geometry if geometry else None
        area = polygon_area_m2(plan) if isinstance(plan, PlanPolygon) else None
        execution.recalculate(
            geometry_area_m2=area,
            production=self.editor.blast_event.event_type == "production",
        )
        self.editor._render_actual_groups()
        self.editor._refresh_actual_summary()

    def _apply_contour_actual(self, row) -> None:
        holes = self._current_holes("actual")
        if not holes:
            return
        design = self._primary_contour_group()
        actual = self._ensure_actual_group(design)
        paired = [
            item for item in list(row.matches_json or [])
            if item.get("design_hole_id") and item.get("actual_hole_id")
        ]
        self._set_actual_group_geometry(actual, holes, paired)
        self._recalculate_actual()

    def _apply_actual_group_matches(self, row) -> None:
        design_holes = self._current_holes("design")
        actual_holes = self._current_holes("actual")
        if not design_holes or not actual_holes:
            return
        actual_by_id = {hole.hole_id: hole for hole in actual_holes}
        matches = list(row.matches_json or [])
        matches_by_design = {
            str(item["design_hole_id"]): item
            for item in matches
            if item.get("design_hole_id") and item.get("actual_hole_id")
        }
        changed = False
        for design_group in self.editor.revision.drilling_groups:
            assigned_design_ids = {
                hole.hole_id
                for hole in design_holes
                if hole.engineering_group_id == design_group.id
            }
            if not assigned_design_ids:
                continue
            group_matches = [
                matches_by_design[hole_id]
                for hole_id in assigned_design_ids
                if hole_id in matches_by_design
            ]
            actual_subset = tuple(
                actual_by_id[str(item["actual_hole_id"])]
                for item in group_matches
                if str(item["actual_hole_id"]) in actual_by_id
            )
            if not actual_subset:
                continue
            actual_group = self._ensure_actual_group(design_group)
            self._set_actual_group_geometry(actual_group, actual_subset, group_matches)
            changed = True
        if changed:
            self._recalculate_actual()


class _SectionWidget(QWidget):
    def __init__(self, page, parent=None):
        super().__init__(parent)
        self.page = page
        self.setMinimumHeight(0)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        page.setParent(self)
        page.setMinimumHeight(0)
        page.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(page, 1)
        page.setVisible(True)


class GeomechanicsEditorWidget(_SectionWidget):
    pass


class BlastDesignEditorWidget(_SectionWidget):
    pass


class ActualExecutionEditorWidget(_SectionWidget):
    def __init__(self, page, parent=None):
        super().__init__(page, parent)
        # BoreholeChargeBuilder contains a 330 px minimum graphics viewport plus
        # its add-component row, legend, margins and spacing. The editor-level
        # 350 px minimum is therefore too small: with several factual groups Qt
        # can compress the builder until the toe label and legend visually
        # collide. Reserve the real content height for production Actual and let
        # the outer Execution fact scroll area grow instead of squeezing it.
        if page.property("blastEventType") == "production":
            self.setStyleSheet("""
                QWidget#actualBoreholeChargeBuilder {
                    min-height: 400px;
                }
            """)