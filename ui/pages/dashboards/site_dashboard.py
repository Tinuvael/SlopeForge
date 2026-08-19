from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.icons.ui.ui_icons import ui_icon
from app.localization import tr
from app.use_case_factory import create_rename_project_use_case
from application.services.project_lines import ProjectLinesDatasetService
from application.state.assessment_domain_state import AssessmentDomainState
from application.use_cases.rename_project import RenameProjectCommand
from repositories.dashboard_repository import DashboardRepository
from repositories.project_lines_repository import ProjectLinesRepository
from ui.assessment_result_presentation import assessment_result_presentation
from ui.dialogs.rename_entity_dialog import RenameEntityDialog
from ui.presentation_labels import domain_message

from .charts import CompactChart
from .plan_overview import DashboardPlanCard
from .widgets import (
    AssessmentProgressCard,
    CompactSummaryList,
    DashboardCard,
    DashboardRecentActivityCard,
    MetricCard,
    ProjectLinesCard,
    SummaryRow,
    metric,
)


class SiteDashboardPage(QWidget):
    """Single-screen Project operational overview; no dashboard tabs or page scroll."""

    domain_requested = Signal(int)
    assessment_area_requested = Signal(str, int)
    project_renamed = Signal(int, str)

    def __init__(self, context, site_id, name):
        super().__init__()
        self.setObjectName("DashboardPage")
        self.setStyleSheet("QWidget#DashboardPage{background:#f4f6f9;}")
        self.context = context
        self.site_id = site_id
        self.repo = DashboardRepository(context.session_factory)
        self.lines_repo = ProjectLinesRepository(context.session_factory)
        self.rename_project = create_rename_project_use_case(context)
        self.snapshot = self.repo.site_snapshot(site_id)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(9)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.title_label = QLabel(name)
        self.title_label.setObjectName("EntityTitle")
        self.title_label.setStyleSheet("font-size:22px;font-weight:700;color:#0f172a;")
        self.edit_button = QPushButton(tr("Edit"))
        self.edit_button.setProperty("role", "secondary")
        self.edit_button.setIcon(ui_icon("edit", "blue"))
        self.edit_button.setEnabled(self._can_edit())
        self.edit_button.clicked.connect(self.edit_project)
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.edit_button)
        root.addLayout(header)

        subtitle = QLabel(tr("Project overview"))
        subtitle.setObjectName("MutedText")
        root.addWidget(subtitle)

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
        self.result_card.setMinimumHeight(245)
        self.result_chart = CompactChart({}, "donut")
        self.result_card.layout.addWidget(self.result_chart, 1)
        right_layout.addWidget(self.result_card, 1)

        self.attention_card = CompactSummaryList(
            "Attention required", visible_rows=2, show_go_to=True
        )
        self.attention_card.activated.connect(self._filter_attention_area)
        self.attention_card.go_to_requested.connect(self._open_attention_area)
        right_layout.addWidget(self.attention_card)
        workspace.addWidget(right_top, 0, 1)

        self.domain_summary = CompactSummaryList(
            "Domain summary", visible_rows=3, show_go_to=True
        )
        self.domain_summary.activated.connect(self._filter_domain)
        self.domain_summary.go_to_requested.connect(
            lambda value: self.domain_requested.emit(int(value))
        )
        workspace.addWidget(self.domain_summary, 1, 0)

        self.lines_card = ProjectLinesCard()
        self.lines_add_button = self.lines_card.add_header_action("Add")
        self.lines_add_button.clicked.connect(self.import_lines)
        workspace.addWidget(self.lines_card, 1, 1)

        self.progress_card = AssessmentProgressCard()
        workspace.addWidget(self.progress_card, 2, 0)

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
            self.plan_card.set_subtitle(tr("No Project Lines loaded"))
            action_label = tr("Import Project Lines")
        else:
            imported = active.imported_at.strftime("%d.%m.%Y") if active.imported_at else "—"
            self.plan_card.set_subtitle(f"{active.name} · {imported}")
            action_label = tr("Update Project Lines")
        if self.plan_card.primary_action is not None:
            self.plan_card.primary_action.setText(action_label)
        editable = self._can_edit()
        self.plan_card.set_actions_enabled(editable)
        self.lines_add_button.setEnabled(editable)
        self.result_chart.set_data(self.snapshot.quadrants)
        self.attention_card.set_rows(
            self._attention_rows(), empty_text="No areas require attention"
        )
        self.domain_summary.set_rows(
            self._domain_rows(), empty_text="No Domains yet"
        )
        self.lines_card.set_datasets(self.snapshot.datasets)
        self.progress_card.set_counts(
            self.snapshot.areas, self.snapshot.completed, self.snapshot.drafts
        )
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
                "Project Lines (*.csv *.dxf);;Datamine CSV (*.csv);;AutoCAD DXF (*.dxf)"
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
