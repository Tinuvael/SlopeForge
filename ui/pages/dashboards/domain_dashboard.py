from __future__ import annotations

from datetime import date
from pathlib import Path

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
from app.use_case_factory import create_rename_domain_use_case
from application.use_cases.rename_domain import RenameDomainCommand
from domain.project.domain_geometry import build_domain_polygons
from infrastructure.geometry_import.lines import import_line_geometry
from repositories.dashboard_repository import DashboardRepository
from repositories.domain_geometry_repository import DomainGeometryRepository
from ui.assessment_result_presentation import assessment_result_presentation
from ui.dialogs.domain_geometry_editor import DomainGeometryEditorDialog
from ui.dialogs.rename_entity_dialog import RenameEntityDialog
from ui.presentation_labels import domain_message

from .charts import CompactChart
from .plan_overview import DashboardPlanCard
from .widgets import (
    BlastActivityCard,
    CompactSummaryList,
    DashboardCard,
    DashboardRecentActivityCard,
    MetricCard,
    SummaryRow,
    metric,
)


class DomainDashboardPage(QWidget):
    """Single-screen Domain operational overview; no dashboard tabs or page scroll."""

    block_requested = Signal(int)
    contour_requested = Signal(str)
    assessment_area_requested = Signal(str)
    domain_renamed = Signal(int, str, int)

    def __init__(self, context, domain_id, name=None):
        super().__init__()
        self.setObjectName("DashboardPage")
        self.setStyleSheet("QWidget#DashboardPage{background:#f4f6f9;}")
        self.context = context
        self.domain_id = domain_id
        self.repo = DashboardRepository(context.session_factory)
        self.geometry_repo = DomainGeometryRepository(context.session_factory)
        self.rename_domain = create_rename_domain_use_case(context)
        self.expected_version = self.geometry_repo.get_domain_version(domain_id)
        self.snapshot = self.repo.domain_snapshot(domain_id)
        domain = self.snapshot.domain

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(9)

        header = QHBoxLayout()
        header.setSpacing(8)
        self.title_label = QLabel(name or domain.name)
        self.title_label.setObjectName("EntityTitle")
        self.title_label.setStyleSheet("font-size:22px;font-weight:700;color:#0f172a;")
        self.edit_button = QPushButton(tr("Edit"))
        self.edit_button.setProperty("role", "secondary")
        self.edit_button.setIcon(ui_icon("edit", "blue"))
        self.edit_button.setEnabled(self._can_edit())
        self.edit_button.clicked.connect(self.edit_domain)
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.edit_button)
        root.addLayout(header)

        subtitle = QLabel(tr("Domain overview"))
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
            primary_action_label="Import geometry",
            secondary_action_label="Draw geometry",
        )
        self.plan_card.primary_action_requested.connect(self.import_geometry)
        self.plan_card.secondary_action_requested.connect(self.edit_geometry)
        self.plan_card.filter_cleared.connect(self._clear_filter_selections)
        self.clear_geometry_button = self.plan_card.add_header_action("Clear")
        self.clear_geometry_button.clicked.connect(self.clear_geometry)
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
        self.attention_card.activated.connect(
            lambda value: self._filter_area(value, self.attention_card)
        )
        self.attention_card.go_to_requested.connect(self.assessment_area_requested)
        right_layout.addWidget(self.attention_card)
        workspace.addWidget(right_top, 0, 1)

        self.interval_summary = CompactSummaryList("Elevation intervals", visible_rows=3)
        self.interval_summary.activated.connect(self._filter_interval)
        workspace.addWidget(self.interval_summary, 1, 0)

        self.latest_assessments = CompactSummaryList(
            "Latest assessments", visible_rows=3, show_go_to=True
        )
        self.latest_assessments.activated.connect(
            lambda value: self._filter_area(value, self.latest_assessments)
        )
        self.latest_assessments.go_to_requested.connect(self.assessment_area_requested)
        workspace.addWidget(self.latest_assessments, 1, 1)

        self.blast_activity = BlastActivityCard()
        workspace.addWidget(self.blast_activity, 2, 0)

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
        self.interval_summary.clear_selection()
        self.attention_card.clear_selection()
        self.latest_assessments.clear_selection()

    def _filter_interval(self, interval: str):
        self.attention_card.clear_selection()
        self.latest_assessments.clear_selection()
        self.plan_card.set_filter("interval", interval)

    def _filter_area(self, area_id: str, source):
        for card in (self.interval_summary, self.attention_card, self.latest_assessments):
            if card is not source:
                card.clear_selection()
        self.plan_card.set_filter("area", area_id)

    def _render_metrics(self):
        self._clear_layout(self.metrics_layout)
        domain = self.snapshot.domain
        percentage = round(100 * domain.completed / domain.areas) if domain.areas else 0
        event_detail = tr("Production: %1 • Contour: %2").replace(
            "%1", str(domain.production)
        ).replace("%2", str(domain.contour))
        evaluation_detail = tr("%1% • Drafts: %2").replace(
            "%1", str(percentage)
        ).replace("%2", str(domain.drafts))
        cards = (
            MetricCard("Blast events", domain.blast_events, event_detail, "blast-blocks"),
            MetricCard("Assessment areas", domain.areas, tr("Active areas"), "assessment-area"),
            MetricCard(
                "Evaluated",
                f"{domain.completed} / {domain.areas}",
                evaluation_detail,
                "check",
            ),
            MetricCard("Average DAI", metric(domain.average_dai), tr("Completed"), "analytics"),
            MetricCard("Average FCI", metric(domain.average_fci), tr("Completed"), "analytics"),
        )
        for index, card in enumerate(cards):
            self.metrics_layout.addWidget(card, 0, index)
            self.metrics_layout.setColumnStretch(index, 1)

    def _interval_rows(self):
        grouped: dict[str, list] = {}
        for area in self.snapshot.areas:
            grouped.setdefault(area.interval, []).append(area)
        rows = []
        for interval, areas in grouped.items():
            completed = [area for area in areas if area.status == "completed"]
            dai_values = [area.dai for area in completed if area.dai is not None]
            fci_values = [area.fci for area in completed if area.fci is not None]
            average_dai = sum(dai_values) / len(dai_values) if dai_values else None
            average_fci = sum(fci_values) / len(fci_values) if fci_values else None
            detail = tr("Assessment areas: %1 • Evaluated: %2").replace(
                "%1", str(len(areas))
            ).replace("%2", f"{len(completed)}/{len(areas)}")
            trailing = f"DAI {metric(average_dai)}  ·  FCI {metric(average_fci)}"
            rows.append(SummaryRow(interval, f"{interval} m", detail, trailing))
        return rows

    def _attention_rows(self):
        rows = []
        for area in self.snapshot.areas:
            presentation = assessment_result_presentation(area.quadrant)
            if area.status != "completed" or not presentation.requires_attention:
                continue
            rows.append(
                (
                    presentation.severity,
                    SummaryRow(
                        area.id,
                        area.name,
                        f"{area.interval} m  ·  {presentation.label}",
                        f"DAI {metric(area.dai)}  ·  FCI {metric(area.fci)}",
                        presentation.color,
                    ),
                )
            )
        rows.sort(key=lambda item: (-item[0], item[1].title.lower()))
        return [row for _, row in rows]

    def _latest_rows(self):
        completed = [area for area in self.snapshot.areas if area.status == "completed"]
        completed.sort(
            key=lambda area: area.assessment_date or date.min,
            reverse=True,
        )
        rows = []
        for area in completed:
            presentation = assessment_result_presentation(area.quadrant)
            rows.append(
                SummaryRow(
                    area.id,
                    area.name,
                    f"{area.interval} m  ·  {presentation.label}",
                    f"DAI {metric(area.dai)}  ·  FCI {metric(area.fci)}",
                    presentation.color,
                )
            )
        return rows

    def _render_snapshot(self):
        self._clear_filter_selections()
        self._render_metrics()
        self.plan_card.set_snapshot(self.snapshot)
        current = [
            geometry
            for geometry in self.snapshot.domain_geometries
            if geometry.is_current
        ]
        source = self.snapshot.geometry_source_file_name or (
            tr("Drawn") if current else ""
        )
        if current:
            polygon_text = tr("%1 polygons").replace("%1", str(len(current)))
            self.plan_card.set_subtitle(
                f"{polygon_text} · {source}" if source else polygon_text
            )
        else:
            self.plan_card.set_subtitle(tr("No Domain geometry defined"))

        editable = self._can_edit()
        self.plan_card.set_actions_enabled(editable)
        if self.plan_card.primary_action is not None:
            self.plan_card.primary_action.setText(
                tr("Replace / Import") if current else tr("Import geometry")
            )
        if self.plan_card.secondary_action is not None:
            self.plan_card.secondary_action.setText(
                tr("Edit boundaries") if current else tr("Draw geometry")
            )
        self.clear_geometry_button.setVisible(bool(current) and editable)
        self.clear_geometry_button.setEnabled(bool(current) and editable)

        self.result_chart.set_data(self.snapshot.quadrants)
        self.attention_card.set_rows(
            self._attention_rows(), empty_text="No areas require attention"
        )
        self.interval_summary.set_rows(
            self._interval_rows(), empty_text="No Assessment Areas yet"
        )
        self.latest_assessments.set_rows(
            self._latest_rows(), empty_text="No completed assessments yet"
        )
        self.blast_activity.set_data(
            self.snapshot.domain.production,
            self.snapshot.domain.contour,
            self.snapshot.blasts,
        )
        self.recent_card.set_entries(self.snapshot.recent)

    def _refresh(self):
        self.snapshot = self.repo.domain_snapshot(self.domain_id)
        self._render_snapshot()

    def edit_domain(self):
        if not self._can_edit():
            return
        dialog = RenameEntityDialog("Domain", self.title_label.text(), self)
        while dialog.exec():
            try:
                user = self.context.current_user
                result = self.rename_domain.execute(
                    RenameDomainCommand(
                        self.domain_id,
                        dialog.name.text(),
                        self.expected_version,
                        user.id,
                        user.can_edit,
                    )
                )
            except Exception as exc:
                dialog.show_error(domain_message(str(exc)))
                continue
            self.snapshot = self.repo.domain_snapshot(self.domain_id)
            self.apply_rename_result(
                result.domain_id, result.domain_name, result.new_version
            )
            self._render_snapshot()
            return

    def apply_rename_result(self, domain_id, new_name, new_version):
        self.expected_version = new_version
        self.title_label.setText(new_name)
        self.domain_renamed.emit(domain_id, new_name, new_version)

    def import_geometry(self):
        if not self._can_edit():
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Select Domain geometry file"),
            "",
            tr(
                "Geometry files (*.csv *.dxf);;Datamine CSV (*.csv);;AutoCAD DXF (*.dxf)"
            ),
        )
        if not path:
            return
        try:
            imported = import_line_geometry(path)
            result = build_domain_polygons(imported.lines)
            stored = self.geometry_repo.replace_imported(
                self.domain_id,
                self.expected_version,
                result.polygons,
                Path(path).name,
            )
            self.expected_version = stored.domain_version
            self._refresh()
            text = "\n".join(
                (
                    tr("File: %1").replace("%1", Path(path).name),
                    tr("Imported polygons: %1").replace(
                        "%1", str(len(result.polygons))
                    ),
                    tr("Skipped open lines: %1").replace(
                        "%1", str(result.skipped_open_lines)
                    ),
                    tr("Skipped degenerate lines: %1").replace(
                        "%1", str(result.skipped_degenerate_lines)
                    ),
                )
            )
            QMessageBox.information(self, tr("Domain geometry"), text)
        except Exception as exc:
            QMessageBox.warning(self, tr("Import error"), domain_message(str(exc)))

    def edit_geometry(self):
        if not self._can_edit():
            return
        stored = self.geometry_repo.get_for_domain(self.domain_id)
        dialog = DomainGeometryEditorDialog(
            stored.polygons if stored else (),
            self.snapshot.project_lines,
            self,
        )
        if dialog.exec():
            try:
                stored = self.geometry_repo.replace_drawn(
                    self.domain_id,
                    self.expected_version,
                    dialog.polygons,
                )
                self.expected_version = stored.domain_version
                self._refresh()
            except Exception as exc:
                QMessageBox.warning(
                    self, tr("Domain geometry"), domain_message(str(exc))
                )

    def clear_geometry(self):
        if not self._can_edit():
            return
        if (
            QMessageBox.question(
                self,
                tr("Clear geometry"),
                tr("Clear the current Domain geometry?"),
            )
            != QMessageBox.StandardButton.Yes
        ):
            return
        try:
            self.expected_version = self.geometry_repo.clear(
                self.domain_id, self.expected_version
            )
            self._refresh()
        except Exception as exc:
            QMessageBox.warning(
                self, tr("Domain geometry"), domain_message(str(exc))
            )
