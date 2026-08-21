from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEvent, Qt, Signal
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
from domain.blasting.workflow import (
    ASSESSMENT_PROGRESS_LABELS,
    WORKFLOW_LABELS,
    assessment_progress_for,
    blast_workflow_for,
)
from repositories.domain_repository import DomainRepository
from repositories.entity_history_repository import EntityHistoryRepository
from ui.pages.contour_overview_widgets import (
    ContourAttachmentPreview,
    ContourEngineeringNotesCard,
    ContourGeometryCard,
    ContourNotesCard,
    ContourRecentActivityCard,
    ContourRelatedEntityList,
)
from ui.pages.entity_history_revision_viewer import open_geometry_revision, open_technical_card_revision
from ui.pages.entity_history_widget import EntityHistoryWidget
from ui.pages.entity_overview_widgets import (
    EngineeringSummaryCard,
    EntityHeaderWidget,
    OverviewKeyValueCard,
    RelatedEntityRow,
)
from ui.pages.entity_page_controller import EntityPageController
from ui.pages.entity_tabs import create_attachment_tab_page, create_entity_tabs
from ui.pages.technical_card_widgets import ActualExecutionEditorWidget, BlastDesignEditorWidget, TechnicalCardEditorWidget, TechnicalCardSaveButton
from ui.presentation_labels import domain_message, format_assessment_elevation_interval


def _show(value, unit="", digits=2):
    if value in (None, ""):
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    text = f"{number:.{digits}f}".rstrip("0").rstrip(".")
    return f"{text}{unit}"


def _dateish(value):
    if value in (None, ""):
        return "—"
    if hasattr(value, "strftime"):
        return value.strftime("%d.%m.%Y")
    text = str(value)
    try:
        return datetime.fromisoformat(text).strftime("%d.%m.%Y")
    except ValueError:
        return text


def _datetime_text(value):
    return value.strftime("%d.%m.%Y %H:%M") if value else "—"


def _history_bounds(entries):
    timed = [entry for entry in entries if entry.timestamp]
    if not timed:
        return None, None, None
    created = min(timed, key=lambda item: item.timestamp)
    updated = max(timed, key=lambda item: item.timestamp)
    return created.actor or "—", created.timestamp, updated.timestamp


def _method_label(code):
    labels = {
        "buffer_cushion": "Buffer / cushion blasting",
        "trim": "Trim blasting",
        "presplit": "Presplit",
        "midsplit": "Midsplit",
        "postsplit": "Postsplit",
        "line_drilling": "Line drilling",
        "other": "Other",
    }
    return tr(labels.get(code, code.replace("_", " ").title())) if code else "—"


def _primary_contour_group(revision):
    preferred = {"contour_line", "presplit_line", "midsplit_line", "postsplit_line", "line_drilling"}
    included = [group for group in revision.drilling_groups if group.included]
    return next((group for group in included if group.group_type in preferred), included[0] if included else None)


class ContourEventPage(QWidget):
    metadata_saved = Signal(str, int)
    related_assessment_requested = Signal(str, int)

    def __init__(self, context, domain_id, domain_name, event_id, parent=None):
        super().__init__(parent)
        self.context = context
        self.domain_name = domain_name
        self.controller = EntityPageController(context, domain_id)
        domain_row = DomainRepository(context.session_factory).get(domain_id)
        self.project_name = domain_row.site.name if domain_row is not None and domain_row.site is not None else "—"
        self.history_repo = EntityHistoryRepository(context.session_factory)
        self.blast_event = next(
            e for e in self.controller.state.blast_events if e.id == event_id and e.event_type == "contour"
        )
        self.read_only = not context.current_user.can_edit or self.blast_event.is_archived
        self.rev = self.blast_event.active_geometry_revision()
        self._related_area_preview_id = None

        from app.use_case_factory import create_charge_presets, create_explosive_catalogue
        card, draft = self.controller.technical_card_draft(self.blast_event)
        self.card, self.draft = card, draft
        self.editor = TechnicalCardEditorWidget(
            self.blast_event,
            card,
            draft,
            self.controller.save_technical_card,
            self,
            self.read_only,
            explosive_products=create_explosive_catalogue(context).list_enabled_products(),
            charge_presets=create_charge_presets(context, self.controller.site_id),
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        self._header(root)

        body = QHBoxLayout()
        left = QVBoxLayout()
        self.tabs = create_entity_tabs()
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        left.addWidget(self.tabs)

        self.engineering_actions_widget = QWidget()
        actions = QHBoxLayout(self.engineering_actions_widget)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addStretch()
        self.engineering_save = TechnicalCardSaveButton(self.save_draft, self.complete)
        self.engineering_save.setEnabled(not self.read_only)
        actions.addWidget(self.engineering_save)
        left.addWidget(self.engineering_actions_widget)
        body.addLayout(left, 1)
        self._sidebar(body)
        root.addLayout(body)

        self._general()
        self.design_tab = BlastDesignEditorWidget(self.editor.take_tab(tr("Contour drilling")))
        self.execution_tab = ActualExecutionEditorWidget(self.editor.take_tab(tr("Execution fact")))
        self.tabs.addTab(self.design_tab, tr("Blast design"))
        self.tabs.addTab(self.execution_tab, tr("Execution fact"))
        # The Technical Card General page remains hidden inside self.editor.
        # Its widgets are still canonical inputs used by TechnicalCardDialog._save;
        # deleting that page makes Design/Execution saves fail before persistence.
        self.photos_tab = self._attachments("Photos")
        self.documents_tab = self._attachments("Documents")
        self.tabs.addTab(self.photos_tab, tr("Photos"))
        self.tabs.addTab(self.documents_tab, tr("Documents"))
        self.history = EntityHistoryWidget()
        self.history.entryActivated.connect(self._open_history_entry)
        self.tabs.addTab(self.history, tr("History"))
        self.tabs.currentChanged.connect(self._sync_engineering_actions_visibility)
        self._sync_engineering_actions_visibility()
        self._wire_sidebar_actions()
        self._refresh_all()

        self.setStyleSheet(
            "#CardFrame{background:white;border:1px solid #dfe3ea;border-radius:8px}"
            "#CardTitle,#EngineeringSectionTitle,#RelatedEntityTitle{font-weight:600;color:#111827}"
            "#EntityTitle{font-size:24px;font-weight:700}#EntityContextLine{color:#667085}"
            "#MutedText{color:#6b7280}#SummaryValue{color:#111827;font-weight:600}"
            "#ActivityTitle{color:#111827}"
            "#EngineeringSummaryText{color:#374151}"
            "#OverviewDivider{color:#e5e7eb;background:#e5e7eb;max-height:1px;border:0}"
            "#StaleBadge{background:#fff1c2;color:#8a5a00;border:1px solid #e5b94d;border-radius:4px;padding:2px 5px}"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._sync_sidebar_density()

    def showEvent(self, event):
        super().showEvent(event)
        if self._related_area_preview_id is not None:
            self._clear_related_area_preview()
        self._sync_sidebar_density()
        if self._related_area_preview_id is None:
            self.geometry_card.plan.center_on_focus()

    def eventFilter(self, watched, event):
        if (
            watched is getattr(self, "_geometry_viewport", None)
            and self._related_area_preview_id is not None
            and event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._clear_related_area_preview()
        return super().eventFilter(watched, event)

    def _sync_engineering_actions_visibility(self, *_args):
        self.engineering_actions_widget.setVisible(self.tabs.currentIndex() in (1, 2))

    def _sync_sidebar_density(self) -> None:
        if not hasattr(self, "photo_preview") or not hasattr(self, "document_preview"):
            return
        if not hasattr(self, "tabs") or not self.isVisible() or self.tabs.height() < 100:
            self.photo_preview.set_visible_item_limit(4)
            self.document_preview.set_visible_item_limit(4)
            return

        available = max(0, self.tabs.height() - 4)
        photo_limit = min(6, self.photo_preview._max_items)
        document_limit = min(7, self.document_preview._max_items)
        self.photo_preview.set_visible_item_limit(photo_limit)
        self.document_preview.set_visible_item_limit(document_limit)

        def required_height():
            spacing = self._sidebar_layout.spacing()
            return (
                self.summary.sizeHint().height()
                + self.photo_preview.sizeHint().height()
                + self.document_preview.sizeHint().height()
                + max(0, spacing) * 2
            )

        while required_height() > available and (document_limit > 4 or photo_limit > 4):
            if document_limit > 4:
                document_limit -= 1
                self.document_preview.set_visible_item_limit(document_limit)
            elif photo_limit > 4:
                photo_limit -= 2
                self.photo_preview.set_visible_item_limit(photo_limit)

    def _open_tab(self, key):
        target = {"blast_design": self.design_tab, "execution": self.execution_tab}.get(key)
        if target is not None:
            self.tabs.setCurrentWidget(target)

    def _header(self, root):
        self.header = EntityHeaderWidget()
        self.header.edit_button.clicked.connect(self.edit_metadata)
        root.addWidget(self.header)

    def _wire_sidebar_actions(self):
        self.photo_preview.add_requested.connect(lambda: self.photo_manager.add())
        self.document_preview.add_requested.connect(lambda: self.document_manager.add())
        self.photo_preview.open_page_requested.connect(lambda: self.tabs.setCurrentWidget(self.photos_tab))
        self.document_preview.open_page_requested.connect(lambda: self.tabs.setCurrentWidget(self.documents_tab))

    def edit_metadata(self):
        from ui.dialogs.entity_metadata_dialogs import ContourMetadataDialog
        repo = DomainRepository(self.context.session_factory)
        domains = repo.selectable_for_site(self.controller.site_id)
        dialog = ContourMetadataDialog(
            domains, self.controller.domain_id, self.blast_event.name, self.blast_event.elevation, self
        )
        if not dialog.exec():
            return
        name = dialog.name.text().strip()
        target_id, target_version = dialog.selected_domain
        if not name:
            QMessageBox.warning(self, tr("Could not save"), tr("Name is required"))
            return
        if self.rev and abs(dialog.horizon.value() - float(self.rev.elevation)) > 0.01:
            text = tr(
                "The new Horizon differs from the active imported geometry elevation. Existing geometry revisions will remain unchanged.\n\nContinue?"
            )
            if QMessageBox.question(self, tr("Frozen geometry"), text) != QMessageBox.Yes:
                return
        try:
            self.controller.update_contour_metadata(
                self.blast_event,
                name=name,
                elevation=dialog.horizon.value(),
                target_domain_id=target_id,
                target_expected_version=target_version,
            )
        except Exception as exc:
            QMessageBox.warning(self, tr("Could not save"), domain_message(str(exc)))
            return
        self.metadata_saved.emit(self.blast_event.id, target_id)

    def _sidebar(self, body):
        right = QVBoxLayout()
        right.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.summary = OverviewKeyValueCard("Summary")
        self.photo_preview = ContourAttachmentPreview("Photos", "photo", max_items=6)
        self.document_preview = ContourAttachmentPreview("Documents", "document", max_items=7)
        for widget in (self.summary, self.photo_preview, self.document_preview):
            widget.setMinimumWidth(250)
            widget.setMaximumWidth(300)
        right.addWidget(self.summary)
        right.addWidget(self.photo_preview)
        right.addWidget(self.document_preview)
        right.addStretch()
        self._sidebar_layout = right
        body.addLayout(right, 0)

    def _general(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        top = QHBoxLayout()
        top.setSpacing(8)
        self.overview_stack_widget = QWidget()
        self.overview_stack_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        overview_stack = QVBoxLayout(self.overview_stack_widget)
        overview_stack.setContentsMargins(0, 0, 0, 0)
        overview_stack.setSpacing(8)
        overview_stack.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.general_info = OverviewKeyValueCard("General information")
        self.related_areas = ContourRelatedEntityList("Related assessment areas")
        self.related_areas.entity_activated.connect(self._preview_related_area)
        self.related_areas.entity_action_requested.connect(self._open_related_area)
        self.notes = ContourNotesCard("Notes")
        self.notes.save_requested.connect(self._autosave_note)
        overview_stack.addWidget(self.general_info)
        overview_stack.addWidget(self.related_areas)
        overview_stack.addWidget(self.notes)

        self.geometry_card = ContourGeometryCard("Plan / geometry", action_label="Reimport")
        self.geometry_card.action_requested.connect(self.reimport_geometry)
        self.geometry_card.plan.view.escape_requested.connect(self._clear_related_area_preview)
        self._geometry_viewport = self.geometry_card.plan.view.viewport()
        self._geometry_viewport.installEventFilter(self)
        top.addWidget(self.overview_stack_widget, 1)
        top.addWidget(self.geometry_card, 0)
        layout.addLayout(top)

        self.engineering_summary = EngineeringSummaryCard()
        self.engineering_summary.section_open_requested.connect(self._open_tab)
        layout.addWidget(self.engineering_summary)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        bottom.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.engineering_notes = ContourEngineeringNotesCard("Engineering notes")
        self.engineering_notes.section_open_requested.connect(self._open_tab)
        self.recent_activity = ContourRecentActivityCard()
        self.recent_activity.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        self.recent_activity.open_history_requested.connect(lambda: self.tabs.setCurrentWidget(self.history))
        bottom.addWidget(self.engineering_notes, 3)
        bottom.addWidget(self.recent_activity, 2)
        layout.addLayout(bottom)
        self.tabs.addTab(page, tr("General information"))

    def _open_related_area(self, area_id):
        self.related_assessment_requested.emit(area_id, self.controller.domain_id)

    def _preview_related_area(self, area_id):
        area = next(
            (item for item in self.controller.state.assessment_areas if item.id == area_id),
            None,
        )
        area_revision = area.active_geometry_revision() if area is not None else None
        if self.rev is None or area_revision is None:
            return
        area_geometry = area_revision.final_geometry_frozen
        if area_geometry is None:
            return

        dataset = self.controller.state.active_dataset()
        lines = dataset.lines if dataset else []
        plan = self.geometry_card.plan
        plan.set_comparison_geometry(
            self.rev.plan_geometry,
            area_geometry,
            lines,
            focus_geometry=self.rev.plan_geometry,
            recenter=False,
        )
        plan._toggle_lines(self.geometry_card.lines.isChecked())
        contour_rect = plan._geometry_path(self.rev.plan_geometry).boundingRect()
        area_rect = plan._geometry_path(area_geometry).boundingRect()
        combined = contour_rect.united(area_rect)
        if not combined.isNull():
            margin = max(max(combined.width(), combined.height()) * 0.12, 1.0)
            plan.view.fit_to_rect(combined.adjusted(-margin, -margin, margin, margin))
        self._related_area_preview_id = area_id
        plan.view.setFocus(Qt.FocusReason.OtherFocusReason)

    def _clear_related_area_preview(self):
        if self._related_area_preview_id is None:
            return
        self._related_area_preview_id = None
        self.related_areas.list.clearSelection()
        if self.rev is None:
            return
        dataset = self.controller.state.active_dataset()
        lines = dataset.lines if dataset else []
        plan = self.geometry_card.plan
        self.geometry_card.set_geometry(
            self.rev.plan_geometry,
            lines,
            focus_geometry=self.rev.plan_geometry,
        )
        plan._toggle_lines(self.geometry_card.lines.isChecked())
        plan.center_on_focus()

    def _autosave_note(self, text):
        if self.read_only:
            self.notes.restore_saved()
            return
        try:
            self.controller.update_contour_comment(self.blast_event, text)
        except Exception as exc:
            self.notes.restore_saved()
            QMessageBox.warning(self, tr("Could not save"), domain_message(str(exc)))
            return
        self.notes.mark_saved(text)
        self._refresh_all()

    def _refresh_header_and_summary(self, history_entries, photos, documents):
        state = blast_workflow_for(self.controller.state, self.blast_event)
        self.header.set_content(
            title=f"{tr('Contour blast')} {self.blast_event.name}",
            status_text=tr(WORKFLOW_LABELS[state]),
            status_state=state,
            archived=self.blast_event.is_archived,
            can_edit=not self.read_only,
            meta_values=(
                f"{tr('ID')}: {self.blast_event.id}",
                f"{tr('Project / Domain')}: {self.project_name} / {self.domain_name}",
                f"{tr('Horizon')}: {_show(self.blast_event.elevation)} m",
                f"{tr('Geometry rev.')}: {self.rev.revision_number if self.rev else '—'}",
            ),
        )
        created_actor, created_at, updated_at = _history_bounds(history_entries)
        if created_at is None and self.rev is not None:
            created_at = self.rev.imported_at
        if updated_at is None and self.rev is not None:
            updated_at = self.rev.imported_at
        revision = self.card.active_revision() or self.draft
        tc_number = revision.revision_number if revision.revision_number else None
        self.summary.set_rows((
            ("Created by", created_actor or "—"),
            ("Created", _datetime_text(created_at)),
            ("Last updated", _datetime_text(updated_at)),
            ("Geometry file", self.rev.source_file_name if self.rev else "—"),
            ("Geometry revision", f"{tr('Rev.')} {self.rev.revision_number}" if self.rev else "—"),
            ("Technical Card", f"{tr('Rev.')} {tc_number}" if tc_number else "—"),
            ("Photos", len(photos)),
            ("Documents", len(documents)),
        ))
        self.notes.set_value(self.blast_event.comment or "", editable=not self.read_only)

    def _refresh_engineering_summary(self):
        revision = self.card.active_revision() or self.draft
        contour = revision.contour_parameters
        actual = revision.actual_execution
        group = _primary_contour_group(revision)
        spacing = contour.average_spacing_m if contour else None
        if spacing is None and group is not None:
            spacing = group.spacing_m
        depth = contour.average_depth_m if contour else None
        if depth is None and group is not None:
            depth = group.average_depth_m
        inclination = group.inclination_deg if group and group.inclination_deg is not None else (contour.inclination_deg if contour else None)
        diameter = contour.diameter_mm if contour and contour.diameter_mm is not None else (group.diameter_mm if group else None)
        holes = contour.hole_count if contour and contour.hole_count is not None else (group.hole_count if group else None)
        explosive = (contour.explosive_type if contour else None) or (group.explosive_names() if group else "") or "—"
        actual_date = actual.actual_blast_date
        canonical_date = actual_date or self.blast_event.event_date
        self.general_info.set_rows((
            ("Blast date", _dateish(canonical_date), tr("Actual") if actual_date else tr("Planned")),
            ("Method", _method_label(contour.controlled_blasting_method) if contour else "—"),
            ("Line length", _show(contour.line_length_m if contour else None, " m")),
            ("Average depth", _show(depth, " m")),
            ("Azimuth", _show(group.azimuth_deg if group else None, "°")),
            ("Inclination", _show(inclination, "°")),
            ("Spacing", _show(spacing, " m")),
            ("Diameter", _show(diameter, " mm")),
        ))

        design_lines = [
            f"{tr('Holes')} {_show(holes)}",
            f"{tr('Explosive')}: {explosive}",
            f"{tr('Drilling length')} {_show(group.drilling_length() if group else None, ' m')}",
        ] if contour else [tr("No design data")]

        actual_group = next(
            (
                item for item in actual.actual_drilling_groups
                if item.included and item.group_type in {"contour_line", "presplit_line", "midsplit_line", "postsplit_line", "line_drilling"}
            ),
            next((item for item in actual.actual_drilling_groups if item.included), None),
        )
        has_fact = bool(actual.actual_drilling_groups or actual.actual_blast_date or actual.completion_status == "completed")
        execution_lines = [
            f"{tr('Average depth')} {_show(actual.actual_average_depth_m, ' m')}" if has_fact else tr("No execution data yet"),
            f"{tr('Spacing')} {_show(actual_group.spacing_m if actual_group else None, ' m')}" if has_fact else "",
            f"{tr('Holes')} {_show(actual.actual_total_hole_count)}" if has_fact else "",
            f"{tr('Explosive')} {_show(actual.actual_total_explosive_mass_kg, ' kg')}" if has_fact else "",
            (
                f"{tr('Rejected')}: {actual.rejected_hole_count or 0} · "
                f"{tr('Wet')}: {actual.wet_hole_count or 0} · "
                f"{tr('Redrilled')}: {actual.redrilled_hole_count or 0} · "
                f"{tr('Uncharged')}: {actual.uncharged_hole_count or 0}"
            ) if has_fact else "",
        ]
        self.engineering_summary.set_sections((
            ("blast_design", "Blast design", design_lines),
            ("execution", "Execution fact", execution_lines),
        ))
        self.engineering_notes.set_sections((
            ("blast_design", "Blast design", [contour.notes if contour and contour.notes else revision.notes or tr("No notes")]),
            ("execution", "Execution fact", [actual.execution_notes or tr("No notes")]),
        ))

    def _refresh_related_areas(self):
        rows = []
        for area in self.controller.state.assessment_areas:
            if not any(
                link.status == "confirmed" and link.blast_event_id == self.blast_event.id
                for link in area.links_for_revision()
            ):
                continue
            evaluation = next(
                (item for item in self.controller.state.evaluations if item.assessment_area_id == area.id),
                None,
            )
            progress = assessment_progress_for(area, evaluation)
            rev = area.active_geometry_revision()
            rows.append(RelatedEntityRow(
                area.id,
                area.name,
                f"{area.id} · {format_assessment_elevation_interval(rev.min_elevation, rev.max_elevation)}",
                tr(ASSESSMENT_PROGRESS_LABELS[progress]),
                getattr(progress, "value", progress),
                action_text=tr("Go to ›"),
            ))
        self.related_areas.set_rows(rows, empty_text="No linked assessment areas")

    def _refresh_all(self):
        self._related_area_preview_id = None
        self.rev = self.blast_event.active_geometry_revision()
        history_entries = self.history_repo.for_blast_event(self.blast_event.id)
        photos = self.controller.attachments.list_for_owner("blast_event", self.blast_event.id, "photo")
        documents = self.controller.attachments.list_for_owner("blast_event", self.blast_event.id, "document")
        self._refresh_header_and_summary(history_entries, photos, documents)
        dataset = self.controller.state.active_dataset()
        self.geometry_card.set_geometry(
            self.rev.plan_geometry if self.rev else None,
            dataset.lines if dataset else [],
            focus_geometry=self.rev.plan_geometry if self.rev else None,
        )
        self.geometry_card.set_action_enabled(not self.read_only)
        self._refresh_engineering_summary()
        self._refresh_related_areas()
        self.recent_activity.set_entries(history_entries)
        self.history.set_entries(history_entries)
        self.photo_preview.set_items(
            self.controller.attachments,
            photos,
            "No photos yet",
            can_add=not self.read_only,
        )
        self.document_preview.set_items(
            self.controller.attachments,
            documents,
            "No documents yet",
            can_add=not self.read_only,
        )
        self._sync_sidebar_density()

    def _attachments(self, title):
        kind = "photo" if title == "Photos" else "document"
        page, manager = create_attachment_tab_page(
            self.controller.attachments,
            "blast_event",
            self.blast_event.id,
            kind,
            read_only=self.read_only,
        )
        manager.changed.connect(self._after_attachment_change)
        if kind == "photo":
            self.photo_manager = manager
        else:
            self.document_manager = manager
        return page

    def _after_attachment_change(self):
        self._refresh_all()

    def _open_history_entry(self, entry):
        if entry.source_type == "blast_geometry":
            revision = next((item for item in self.blast_event.geometry_revisions if item.id == entry.source_id), None)
            if revision is not None:
                dataset = self.controller.state.active_dataset()
                open_geometry_revision(self, revision=revision, project_lines=dataset.lines if dataset else [])
            return
        if entry.source_type == "technical_card":
            revision = next((item for item in self.card.revisions if item.id == entry.source_id), None)
            if revision is not None:
                from app.use_case_factory import create_charge_presets, create_explosive_catalogue
                open_technical_card_revision(
                    self,
                    event=self.blast_event,
                    card=self.card,
                    revision=revision,
                    domain_name=self.domain_name,
                    explosive_products=create_explosive_catalogue(self.context).list_enabled_products(),
                    charge_presets=create_charge_presets(self.context, self.controller.site_id),
                )

    def reimport_geometry(self):
        if self.read_only:
            QMessageBox.warning(self, tr("Read only"), tr("Archived contour events and Viewer accounts are read-only."))
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Reimport contour geometry"),
            "",
            tr("Geometry files (*.csv *.dxf);;Datamine CSV (*.csv);;AutoCAD DXF (*.dxf)"),
        )
        if not path:
            return
        try:
            self.controller.reimport_blast_event_geometry(self.blast_event, path)
        except Exception as exc:
            QMessageBox.warning(self, tr("Contour geometry"), domain_message(str(exc)))
            return
        self._refresh_all()

    def save_draft(self):
        if self.read_only:
            QMessageBox.warning(self, tr("Read only"), tr("This contour event is read-only."))
            return False
        saved = self.editor.save_draft()
        if saved:
            self._refresh_all()
        return saved

    def complete(self):
        if self.read_only:
            QMessageBox.warning(self, tr("Read only"), tr("This contour event is read-only."))
            return False
        saved = self.editor.complete()
        if saved:
            self._refresh_all()
        return saved
