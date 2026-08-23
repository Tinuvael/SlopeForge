"""Reusable embedded views backed by the existing TechnicalCardDialog editor."""
from __future__ import annotations

from statistics import mean

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
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
from ui.presentation_labels import domain_message, technical_group_label
from ui.widgets.design_system import set_button_role, set_status_role


DRILLHOLE_FILE_FILTER = (
    "Drillhole files (*.dxf *.dm *.dmx);;AutoCAD DXF (*.dxf);;Datamine files (*.dm *.dmx)"
)


class _DrillholeTechnicalCardDialog(TechnicalCardDialog):
    """The proven Technical Card editor with drillhole-specific presentation hooks."""

    group_assign_callback = None
    group_assign_available_callback = None
    design_auto_fields_callback = None
    actual_auto_fields_callback = None

    @staticmethod
    def _header_layout(box):
        layout = box.layout()
        if layout is None or not layout.count():
            return None
        item = layout.itemAt(0)
        return item.layout() if item is not None else None

    def _decorate_auto_fields(self, box, group, callback, badge_text):
        if not callable(callback):
            return
        fields = set(callback(group) or ())
        if not fields:
            return
        header = self._header_layout(box)
        if header is not None:
            badge = set_status_role(QLabel(tr(badge_text)), "info")
            badge.setToolTip(
                tr("These values are calculated from the imported drillhole geometry.")
            )
            header.insertWidget(max(0, header.count() - 1), badge)
        for field_name in fields:
            widget = box.findChild(QWidget, field_name)
            if widget is None:
                continue
            if hasattr(widget, "setReadOnly"):
                widget.setReadOnly(True)
            else:
                widget.setEnabled(False)
            widget.setToolTip(
                tr("Calculated automatically from imported drillhole geometry.")
            )

    def _render_groups(self):
        super()._render_groups()
        callback = getattr(self, "group_assign_callback", None)
        available_callback = getattr(self, "group_assign_available_callback", None)
        for index, group in enumerate(self.revision.drilling_groups):
            item = self.group_cards_layout.itemAt(index)
            box = item.widget() if item is not None else None
            if box is None or box.layout() is None:
                continue
            self._decorate_auto_fields(
                box,
                group,
                getattr(self, "design_auto_fields_callback", None),
                "Auto from design holes",
            )
            if not callable(callback):
                continue
            header = self._header_layout(box)
            if header is None:
                continue
            assign = set_button_role(QPushButton(tr("Assign holes")), "secondary")
            assign.setObjectName("assignDrillholesButton")
            available = not self.read_only and (
                not callable(available_callback) or bool(available_callback())
            )
            assign.setEnabled(available)
            if not available and not self.read_only:
                assign.setToolTip(tr("Import design drillholes first."))
            assign.clicked.connect(lambda _checked=False, current=group: callback(current))
            header.insertWidget(max(0, header.count() - 1), assign)

    def _render_actual_groups(self):
        super()._render_actual_groups()
        callback = getattr(self, "actual_auto_fields_callback", None)
        if not callable(callback):
            return
        for index, group in enumerate(self.revision.actual_execution.actual_drilling_groups):
            item = self.actual_cards_layout.itemAt(index)
            box = item.widget() if item is not None else None
            if box is None or box.layout() is None:
                continue
            self._decorate_auto_fields(
                box,
                group,
                callback,
                "Auto from as-drilled",
            )


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

    _DESIGN_AUTO_FIELDS = {
        "hole_count",
        "average_depth_m",
        "inclination_deg",
        "azimuth_deg",
    }
    _ACTUAL_AUTO_FIELDS = {
        "hole_count",
        "average_depth_m",
        "inclination_deg",
        "azimuth_deg",
        "mean_collar_deviation_m",
        "max_collar_deviation_m",
        "mean_toe_deviation_m",
        "max_toe_deviation_m",
    }
    _CONTOUR_PRIMARY_TYPES = {
        "contour_line",
        "presplit_line",
        "midsplit_line",
        "postsplit_line",
        "line_drilling",
    }

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
            self.editor.group_assign_available_callback = self._can_assign_design_holes
            self.editor.design_auto_fields_callback = self._design_auto_fields
            self.editor.actual_auto_fields_callback = self._actual_auto_fields
            self.editor._render_groups()
            if hasattr(self.editor, "actual_cards_layout"):
                self.editor._render_actual_groups()

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

    def _can_assign_design_holes(self):
        return bool(self._current_row("design"))

    def _primary_contour_group_candidate(self):
        included = [group for group in self.editor.revision.drilling_groups if group.included]
        return next(
            (group for group in included if group.group_type in self._CONTOUR_PRIMARY_TYPES),
            included[0] if included else None,
        )

    def _is_primary_contour_group(self, group: BlastDrillingGroup) -> bool:
        return self._primary_contour_group_candidate() is group

    def _design_auto_fields(self, group: BlastDrillingGroup):
        holes = self._current_holes("design")
        if not holes:
            return set()
        assigned = any(hole.engineering_group_id == group.id for hole in holes)
        if self.editor.blast_event.event_type == "production":
            return set(self._DESIGN_AUTO_FIELDS) if assigned else set()
        any_assigned = any(hole.engineering_group_id for hole in holes)
        active = assigned or self._is_primary_contour_group(group)
        if not active:
            return set()
        if any_assigned and not assigned and not self._is_primary_contour_group(group):
            return set()
        return set(self._DESIGN_AUTO_FIELDS) | {"spacing_m"}

    def _actual_auto_fields(self, group: ActualDrillingGroup):
        row = self._current_row("actual")
        if row is None or not bool(getattr(row, "design_revision_current", True)):
            return set()
        if not group.design_group_id:
            return set()
        if self.editor.blast_event.event_type == "contour":
            primary = self._primary_contour_group_candidate()
            return (
                set(self._ACTUAL_AUTO_FIELDS)
                if primary is not None and group.design_group_id == primary.id
                else set()
            )
        design_holes = self._current_holes("design")
        return (
            set(self._ACTUAL_AUTO_FIELDS)
            if any(
                hole.engineering_group_id == group.design_group_id
                for hole in design_holes
            )
            else set()
        )

    def refresh_drillhole_page(self, dataset_kind: str, *, apply_to_draft: bool = False):
        page = self._drillhole_pages.get(dataset_kind)
        if page is None:
            return
        row = self._current_row(dataset_kind)
        holes = self._current_holes(dataset_kind) if row is not None else ()
        page.dataset_card.set_dataset(row, holes)
        if dataset_kind == "actual":
            design_exists = self._current_row("design") is not None
            page.dataset_card.set_import_available(
                design_exists,
                tr("Import design drillholes before adding as-drilled holes."),
            )
        else:
            page.dataset_card.set_import_available(True)
        if not apply_to_draft or row is None:
            return
        if dataset_kind == "design":
            if self.editor.blast_event.event_type == "contour":
                self._apply_contour_design(row, holes)
            else:
                self._apply_production_design_assignments(holes)
        elif dataset_kind == "actual":
            if not bool(getattr(row, "design_revision_current", True)):
                return
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
            if dataset_kind == "design":
                if self.editor.blast_event.event_type == "contour":
                    self._apply_contour_design(row, holes)
                else:
                    self._apply_production_design_assignments(holes)
            elif dataset_kind == "actual":
                if self.editor.blast_event.event_type == "contour":
                    self._apply_contour_actual(row)
                else:
                    self._apply_actual_group_matches(row)
            self.refresh_drillhole_page(dataset_kind)
            if dataset_kind == "design":
                self.refresh_drillhole_page("actual")
            page = self._drillhole_pages.get(dataset_kind)
            if page is not None:
                page.dataset_card.show_helper(
                    tr("Imported successfully. Automatic values were updated in this Technical Card draft. Save the page to keep them.")
                )
        except Exception as exc:
            QMessageBox.warning(self, tr("Drillhole import"), domain_message(str(exc)))

    def assign_holes_to_group(self, group: BlastDrillingGroup):
        if self.editor.read_only or self._drillhole_service is None or self._controller is None:
            return
        holes = self._current_holes("design")
        if not holes:
            return
        selected = {hole.hole_id for hole in holes if hole.engineering_group_id == group.id}
        if (
            self.editor.blast_event.event_type == "contour"
            and not selected
            and not any(hole.engineering_group_id for hole in holes)
            and self._is_primary_contour_group(group)
        ):
            selected = {hole.hole_id for hole in holes}
        geometry = self.editor.blast_event.active_geometry_revision()
        group_labels = {
            item.id: technical_group_label(item.group_type, item.name)
            for item in self.editor.revision.drilling_groups
        }
        dialog = DrillholeGroupAssignmentDialog(
            technical_group_label(group.group_type, group.name),
            holes,
            selected_ids=selected,
            plan_geometry=geometry.plan_geometry if geometry else None,
            group_labels=group_labels,
            parent=self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        previous_groups = {
            hole.engineering_group_id
            for hole in holes
            if hole.hole_id in dialog.selected_hole_ids
            and hole.engineering_group_id
            and hole.engineering_group_id != group.id
        }
        affected_group_ids = {group.id, *previous_groups}
        try:
            self._drillhole_service.assign_design_holes(
                self._controller.domain_id,
                self.editor.blast_event.id,
                group.id,
                dialog.selected_hole_ids,
            )
            current_holes = self._current_holes("design")
            if self.editor.blast_event.event_type == "production":
                self._apply_production_design_assignments(
                    current_holes,
                    changed_group_ids=affected_group_ids,
                )
            else:
                self._apply_contour_design(
                    self._current_row("design"),
                    current_holes,
                    changed_group_ids=affected_group_ids,
                )
            self.refresh_drillhole_page("design")
            design_page = self._drillhole_pages.get("design")
            if design_page is not None:
                design_page.dataset_card.show_helper(
                    tr("Assignment updated. Geometry-derived group values were recalculated automatically. Save the page to keep them.")
                )
            actual_row = self._current_row("actual")
            if actual_row is not None and bool(getattr(actual_row, "design_revision_current", True)):
                if self.editor.blast_event.event_type == "contour":
                    self._apply_contour_actual(actual_row)
                else:
                    self._apply_actual_group_matches(
                        actual_row,
                        changed_group_ids=affected_group_ids,
                    )
                self.refresh_drillhole_page("actual")
        except Exception as exc:
            QMessageBox.warning(self, tr("Assign drillholes"), domain_message(str(exc)))

    def _apply_design_group_metrics(self, group: BlastDrillingGroup, holes) -> None:
        holes = tuple(holes)
        if not holes:
            group.hole_count = 0
            group.average_depth_m = None
            group.planned_drilling_length_m = 0.0
            group.inclination_deg = None
            group.azimuth_deg = None
            if self.editor.blast_event.event_type == "contour":
                group.spacing_m = None
                if self._is_primary_contour_group(group):
                    parameters = self.editor.revision.contour_parameters
                    if parameters is not None:
                        parameters.hole_count = 0
                        parameters.average_depth_m = None
                        parameters.average_spacing_m = None
                        parameters.inclination_deg = None
                        parameters.line_length_m = 0.0
            if self.editor.revision.production_parameters is not None:
                self.editor.revision.production_parameters.recalculate(
                    self.editor.revision.drilling_groups
                )
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
            if self._is_primary_contour_group(group):
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

    def _apply_production_design_assignments(self, holes, *, changed_group_ids=()) -> None:
        holes = tuple(holes)
        if not holes:
            return
        changed_group_ids = set(changed_group_ids)
        for group in self.editor.revision.drilling_groups:
            assigned = tuple(
                hole for hole in holes if hole.engineering_group_id == group.id
            )
            if assigned or group.id in changed_group_ids:
                self._apply_design_group_metrics(group, assigned)
        self.editor._render_groups()

    def _primary_contour_group(self):
        group = self._primary_contour_group_candidate()
        if group is None:
            group = BlastDrillingGroup(
                group_type="contour_line",
                name=tr("Contour line"),
                sequence_order=len(self.editor.revision.drilling_groups) + 1,
            )
            self.editor.revision.drilling_groups.append(group)
        return group

    def _apply_contour_design(self, row, holes, *, changed_group_ids=()) -> None:
        holes = tuple(holes)
        if not holes:
            return
        primary = self._primary_contour_group()
        changed_group_ids = set(changed_group_ids)
        any_assigned = any(hole.engineering_group_id for hole in holes)
        if not any_assigned:
            self._apply_design_group_metrics(primary, holes)
        else:
            for group in self.editor.revision.drilling_groups:
                assigned = tuple(
                    hole for hole in holes if hole.engineering_group_id == group.id
                )
                if assigned or group is primary or group.id in changed_group_ids:
                    self._apply_design_group_metrics(group, assigned)
        self.editor._render_groups()

    @staticmethod
    def _deviation_values(matches, key: str):
        return [
            float(item[key])
            for item in matches
            if item.get(key) is not None
        ]

    @staticmethod
    def _clear_actual_group_geometry(actual: ActualDrillingGroup) -> None:
        actual.hole_count = 0
        actual.average_depth_m = None
        actual.drilling_length_m = None
        actual.inclination_deg = None
        actual.azimuth_deg = None
        actual.mean_collar_deviation_m = None
        actual.max_collar_deviation_m = None
        actual.mean_toe_deviation_m = None
        actual.max_toe_deviation_m = None

    def _set_actual_group_geometry(self, actual, holes, matches) -> None:
        holes = tuple(holes)
        if not holes:
            self._clear_actual_group_geometry(actual)
            return
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

    def _apply_actual_group_matches(self, row, *, changed_group_ids=()) -> None:
        design_holes = self._current_holes("design")
        actual_holes = self._current_holes("actual")
        if not design_holes or not actual_holes:
            return
        changed_group_ids = set(changed_group_ids)
        actual_by_id = {hole.hole_id: hole for hole in actual_holes}
        matches = list(row.matches_json or [])
        matches_by_design = {
            str(item["design_hole_id"]): item
            for item in matches
            if item.get("design_hole_id") and item.get("actual_hole_id")
        }
        actual_by_design_group = {
            item.design_group_id: item
            for item in self.editor.revision.actual_execution.actual_drilling_groups
            if item.design_group_id
        }
        changed = False
        for design_group in self.editor.revision.drilling_groups:
            assigned_design_ids = {
                hole.hole_id
                for hole in design_holes
                if hole.engineering_group_id == design_group.id
            }
            if not assigned_design_ids:
                if design_group.id in changed_group_ids:
                    existing = actual_by_design_group.get(design_group.id)
                    if existing is not None:
                        self._clear_actual_group_geometry(existing)
                        changed = True
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
