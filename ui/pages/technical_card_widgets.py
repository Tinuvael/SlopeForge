"""Reusable embedded views backed by the existing TechnicalCardDialog editor."""
from __future__ import annotations

from statistics import mean

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox, QSizePolicy, QVBoxLayout, QWidget

from app.localization import tr
from app.use_case_factory import create_drillhole_dataset_service
from domain.blasting.contour_drilling import summarize_contour_drilling
from domain.blasting.technical_card import ActualDrillingGroup, BlastDrillingGroup
from ui.editors.technical_card_editor import TechnicalCardDialog
from ui.pages.drillhole_dataset_widgets import DrillholeDatasetCard
from ui.presentation_labels import domain_message


DRILLHOLE_FILE_FILTER = (
    "Drillhole files (*.dxf *.dm *.dmx);;AutoCAD DXF (*.dxf);;Datamine files (*.dm *.dmx)"
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
        self.editor = TechnicalCardDialog(
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
        if apply_to_draft and row is not None and self.editor.blast_event.event_type == "contour":
            if dataset_kind == "design":
                self._apply_contour_design(row, holes)
            else:
                self._apply_contour_actual(row)

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
            if self.editor.blast_event.event_type == "contour":
                if dataset_kind == "design":
                    self._apply_contour_design(row, holes)
                else:
                    self._apply_contour_actual(row)
            self.refresh_drillhole_page(dataset_kind)
            QMessageBox.information(
                self,
                tr("Drillhole import"),
                tr("Drillholes were imported and derived values were updated in the current Technical Card draft. Save the Technical Card to keep those values."),
            )
        except Exception as exc:
            QMessageBox.warning(self, tr("Drillhole import"), domain_message(str(exc)))

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
        summary = dict(row.summary_json or {})
        contour = summarize_contour_drilling(holes)
        group = self._primary_contour_group()
        group.hole_count = int(summary["hole_count"])
        group.average_depth_m = float(summary["mean_length_m"])
        group.planned_drilling_length_m = float(summary["total_drilling_length_m"])
        group.inclination_deg = summary.get("mean_inclination_deg")
        group.azimuth_deg = summary.get("mean_azimuth_deg")
        group.spacing_m = contour.mean_spacing_m
        parameters = self.editor.revision.contour_parameters
        if parameters is not None:
            parameters.hole_count = group.hole_count
            parameters.average_depth_m = group.average_depth_m
            parameters.average_spacing_m = group.spacing_m
            parameters.inclination_deg = group.inclination_deg
            parameters.line_length_m = contour.line_length_m
        self.editor._render_groups()

    def _apply_contour_actual(self, row) -> None:
        summary = dict(row.summary_json or {})
        design = self._primary_contour_group()
        execution = self.editor.revision.actual_execution
        actual = next(
            (item for item in execution.actual_drilling_groups if item.design_group_id == design.id),
            None,
        )
        if actual is None:
            actual = ActualDrillingGroup.from_design(design, self.editor.revision.id)
            execution.actual_drilling_groups.append(actual)
        actual.hole_count = int(summary["hole_count"])
        actual.average_depth_m = float(summary["mean_length_m"])
        actual.drilling_length_m = float(summary["total_drilling_length_m"])
        actual.inclination_deg = summary.get("mean_inclination_deg")
        actual.azimuth_deg = summary.get("mean_azimuth_deg")

        matches = list(row.matches_json or [])
        paired = [
            item for item in matches
            if item.get("design_hole_id") and item.get("actual_hole_id")
        ]
        collar = [
            float(item["collar_deviation_3d_m"])
            for item in paired
            if item.get("collar_deviation_3d_m") is not None
        ]
        toe = [
            float(item["toe_deviation_3d_m"])
            for item in paired
            if item.get("toe_deviation_3d_m") is not None
        ]
        actual.mean_collar_deviation_m = mean(collar) if collar else None
        actual.max_collar_deviation_m = max(collar) if collar else None
        actual.mean_toe_deviation_m = mean(toe) if toe else None
        actual.max_toe_deviation_m = max(toe) if toe else None
        execution.recalculate(production=False)
        self.editor._render_actual_groups()
        self.editor._refresh_actual_summary()


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
