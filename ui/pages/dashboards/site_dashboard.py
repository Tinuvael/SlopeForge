from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QMessageBox,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.localization import tr
from app.use_case_factory import create_rename_project_use_case
from application.services.project_lines import ProjectLinesDatasetService
from application.services.project_surfaces import ProjectSurfaceDatasetService
from application.state.assessment_domain_state import AssessmentDomainState
from application.use_cases.rename_project import RenameProjectCommand
from repositories.dashboard_repository import DashboardRepository
from repositories.project_lines_repository import ProjectLinesRepository
from ui.assessment_result_presentation import assessment_result_presentation
from ui.dialogs.rename_entity_dialog import RenameEntityDialog
from ui.presentation_labels import domain_message

from .charts import AssessmentTrendCard, CompactChart
from .plan_overview import DashboardPlanCard
from .project_geometry_card import ProjectGeometryCard
from .widgets import (
    CompactSummaryList,
    DashboardCard,
    DashboardEntityHeader,
    DashboardRecentActivityCard,
    MetricCard,
    ProjectLinesCard,
    SummaryRow,
    metric,
)


SURFACE_FILE_FILTER = (
    "Surface files (*.dxf *.dm *.dmx);;"
    "AutoCAD DXF (*.dxf);;"
    "Datamine wireframe files (*.dm *.dmx)"
)


class SiteDashboardPage(QWidget):
    """Single-screen Project operational overview; no dashboard tabs or page scroll."""

    domain_requested = Signal(int)
    assessment_area_requested = Signal(str, int)
    project_renamed = Signal(int, str)

    def __init__(self, context, site_id, name):
        super().__init__()
        self.setObjectName("DashboardPage")
        self.context = context
        self.site_id = site_id
        self.repo = DashboardRepository(context.session_factory)
        self.lines_repo = ProjectLinesRepository(context.session_factory)
        self.surface_service = ProjectSurfaceDatasetService(
            context.session_factory, context.storage_root
        )
        self.rename_project = create_rename_project_use_case(context)
        self.snapshot = self.repo.site_snapshot(site_id)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(9)

        self.dashboard_header = DashboardEntityHeader(name, "Project overview")
        self.title_label = self.dashboard_header.title_label
        self.edit_button = self.dashboard_header.edit_button
        self.edit_button.setEnabled(self._can_edit())
        self.edit_button.clicked.connect(self.edit_project)
        root.addWidget(self.dashboard_header)

        self.metrics_host = QWidget()
        self.metrics_layout = QGridLayout(self.metrics_host)
        self.metrics_layout.setContentsMargins(0, 0, 0, 0)
        self.metrics_layout.setHorizontalSpacing(8)
        root.addWidget(self.metrics_host)

        workspace = QGridLayout()
        workspace.setContentsMargins(0, 0, 0, 0)
        workspace.setHorizontalSpacing(9)
        workspace.setVerticalSpacing(9)
        workspace.setColumnStretch(0, 1)
        workspace.setColumnStretch(1, 1)
        workspace.setRowMinimumHeight(0, 405)
        workspace.setRowStretch(0, 1)
        root.addLayout(workspace, 1)

        self.plan_card = DashboardPlanCard(
            self.snapshot,
            primary_action_label="Project Lines",
        )
        self.plan_card.primary_action_requested.connect(self.import_lines)
        self.plan_card.filter_cleared.connect(self._clear_filter_selections)
        self.plan_card.set_actions_enabled(self._can_edit())
        workspace.addWidget(self.plan_card, 0, 0)

        right_top = QWidget()
        right_top.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        right_top.setMinimumHeight(405)
        right_top.setMaximumHeight(455)
        right_layout = QVBoxLayout(right_top)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(9)

        self.result_card = DashboardCard("Assessment result distribution")
        self.result_card.setMinimumHeight(210)
        self.result_card.setMaximumHeight(225)
        self.result_chart = CompactChart({}, "donut")
        self.result_card.layout.addWidget(self.result_chart, 1)
        right_layout.addWidget(self.result_card)

        self.attention_card = CompactSummaryList(
            "Attention required",
            visible_rows=4,
            show_go_to=True,
            fill_available=True,
        )
        self.attention_card.setMinimumHeight(160)
        self.attention_card.activated.connect(self._filter_attention_area)
        self.attention_card.go_to_requested.connect(self._open_attention_area)
        right_layout.addWidget(self.attention_card, 1)
        workspace.addWidget(right_top, 0, 1)

        data_row = QWidget()
        data_layout = QGridLayout(data_row)
        data_layout.setContentsMargins(0, 0, 0, 0)
        data_layout.setHorizontalSpacing(9)
        for column in range(3):
            data_layout.setColumnStretch(column, 1)

        self.domain_summary = CompactSummaryList(
            "Domain summary", visible_rows=3, show_go_to=True
        )
        self.domain_summary.activated.connect(self._filter_domain)
        self.domain_summary.go_to_requested.connect(
            lambda value: self.domain_requested.emit(int(value))
        )
        data_layout.addWidget(self.domain_summary, 0, 0)

        self.lines_card = ProjectLinesCard()
        self.lines_add_button = self.lines_card.add_header_action("Add")
        self.lines_add_button.clicked.connect(self.import_lines)
        data_layout.addWidget(self.lines_card, 0, 1)

        self.geometry_card = ProjectGeometryCard()
        self.geometry_card.upload_requested.connect(self.import_surface)
        data_layout.addWidget(self.geometry_card, 0, 2)

        workspace.addWidget(data_row, 1, 0, 1, 2)

        self.trend_card = AssessmentTrendCard()
        workspace.addWidget(self.trend_card, 2, 0)

        self.recent_card = DashboardRecentActivityCard()
        workspace.addWidget(self.recent_card, 2, 1)

        self._render_snapshot()

    def _can_edit(self) -> bool:
        return bool(getattr(getattr(self.context, "current_user", None), "can_edit", False))

    @staticmethod
    def _clear_layout(layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _clear_filter_selections(self):
        self.domain_summary.clear_selection()
        self.attention_card.clear_selection()

    def _filter_domain(self, value: str):
        self.attention_card.clear_selection()
        domain_id = int(value)
        domain = next(
            (item.domain for item in self.snapshot.domains if item.domain.id == domain_id),
            None,
        )
        if domain is not None:
            self.plan_card.set_filter("domain", domain.name)

    def _filter_attention_area(self, value: str):
        self.domain_summary.clear_selection()
        _domain_id, area_id = value.split("|", 1)
        self.plan_card.set_filter("area", area_id)

    def _render_metrics(self):
        self._clear_layout(self.metrics_layout)
        snapshot = self.snapshot
        percentage = round(100 * snapshot.completed / snapshot.areas) if snapshot.areas else 0
        event_detail = tr("Production: %1 • Contour: %2").replace(
            "%1", str(snapshot.production)
        ).replace("%2", str(snapshot.contour))
        evaluation_detail = tr("%1% • Drafts: %2").replace(
            "%1", str(percentage)
        ).replace("%2", str(snapshot.drafts))
        cards = (
            MetricCard(
                "Blast events",
                snapshot.production + snapshot.contour,
                event_detail,
                "blast-blocks",
            ),
            MetricCard("Assessment areas", snapshot.areas, tr("Active areas"), "assessment-area"),
            MetricCard(
                "Evaluated",
                f"{snapshot.completed} / {snapshot.areas}",
                evaluation_detail,
                "check",
            ),
            MetricCard("Average DAI", metric(snapshot.average_dai), tr("Completed evaluations"), "analytics"),
            MetricCard("Average FCI", metric(snapshot.average_fci), tr("Completed evaluations"), "analytics"),
        )
        for index, card in enumerate(cards):
            self.metrics_layout.addWidget(card, 0, index)
            self.metrics_layout.setColumnStretch(index, 1)

    def _domain_rows(self):
        rows = []
        for item in self.snapshot.domains:
            domain = item.domain
            detail = tr("Blast events: %1 • Production: %2 • Contour: %3").replace(
                "%1", str(domain.blast_events)
            ).replace("%2", str(domain.production)).replace("%3", str(domain.contour))
            trailing = (
                f"{tr('Assessment areas')}: {domain.completed}/{domain.areas}  ·  "
                f"DAI {metric(domain.average_dai)}  ·  FCI {metric(domain.average_fci)}"
            )
            rows.append(SummaryRow(str(domain.id), domain.name, detail, trailing))
        return rows

    def _attention_rows(self):
        rows = []
        for domain_snapshot in self.snapshot.domains:
            for area in domain_snapshot.areas:
                presentation = assessment_result_presentation(area.quadrant)
                if area.status != "completed" or not presentation.requires_attention:
                    continue
                detail = f"{domain_snapshot.domain.name}  ·  {area.interval} m  ·  {presentation.label}"
                trailing = f"DAI {metric(area.dai)}  ·  FCI {metric(area.fci)}"
                rows.append(
                    (
                        presentation.severity,
                        SummaryRow(
                            f"{domain_snapshot.domain.id}|{area.id}",
                            area.name,
                            detail,
                            trailing,
                            presentation.color,
                        ),
                    )
                )
        rows.sort(key=lambda item: (-item[0], item[1].title.lower()))
        return [row for _, row in rows]

    def _open_attention_area(self, value: str):
        domain_id, area_id = value.split("|", 1)
        self.assessment_area_requested.emit(area_id, int(domain_id))

    def _render_snapshot(self):
        self._clear_filter_selections()
        self._render_metrics()
        self.plan_card.set_snapshot(self.snapshot)
        active = self.snapshot.active_dataset
        if active is None:
            self.plan_card.set_subtitle(tr("No Project Lines"))
            action_label = tr("Import lines")
        else:
            self.plan_card.set_subtitle(str(active.name))
            action_label = tr("Update lines")
        if self.plan_card.primary_action is not None:
            self.plan_card.primary_action.setText(action_label)
        editable = self._can_edit()
        self.plan_card.set_actions_enabled(editable)
        self.lines_add_button.setEnabled(editable)
        self.geometry_card.set_actions_enabled(editable)
        self.result_chart.set_data(self.snapshot.quadrants)
        self.attention_card.set_rows(
            self._attention_rows(), empty_text="No areas require attention"
        )
        self.domain_summary.set_rows(
            self._domain_rows(), empty_text="No Domains yet"
        )
        self.lines_card.set_datasets(self.snapshot.datasets)
        self.geometry_card.set_datasets(
            self.surface_service.current(self.site_id, "design"),
            self.surface_service.current(self.site_id, "actual"),
        )
        self.trend_card.set_rows(self.snapshot.trend_rows)
        self.recent_card.set_entries(self.snapshot.recent)

    def refresh(self):
        self.snapshot = self.repo.site_snapshot(self.site_id)
        self._render_snapshot()

    def edit_project(self):
        if not self._can_edit():
            return
        dialog = RenameEntityDialog("Project", self.title_label.text(), self)
        while dialog.exec():
            try:
                user = self.context.current_user
                result = self.rename_project.execute(
                    RenameProjectCommand(
                        self.site_id,
                        dialog.name.text(),
                        user.id,
                        user.can_edit,
                    )
                )
            except Exception as exc:
                dialog.show_error(domain_message(str(exc)))
                continue
            self.apply_rename_result(result.site_id, result.project_name)
            return

    def apply_rename_result(self, site_id, new_name):
        self.title_label.setText(new_name)
        self.project_renamed.emit(site_id, new_name)

    def import_lines(self):
        if not self._can_edit():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Select Project Lines file"),
            "",
            tr(
                "Project Lines (*.dxf *.dm *.dmx);;AutoCAD DXF (*.dxf);;Datamine files (*.dm *.dmx)"
            ),
        )
        if not path:
            return
        try:
            dataset, _ = ProjectLinesDatasetService(
                AssessmentDomainState()
            ).import_dataset(path)
            self.lines_repo.import_dataset(
                self.site_id, dataset, make_active=True
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, tr("Import error"), domain_message(str(exc)))

    def import_surface(self, dataset_kind: str):
        if not self._can_edit():
            return
        if dataset_kind == "design":
            title = tr("Design surface")
        elif dataset_kind == "actual":
            title = tr("Actual survey")
        else:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            title,
            "",
            SURFACE_FILE_FILTER,
        )
        if not path:
            return
        try:
            user = self.context.current_user
            self.surface_service.import_dataset(
                self.site_id,
                dataset_kind,
                path,
                imported_by_user_id=user.id,
            )
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, tr("Import error"), domain_message(str(exc)))
