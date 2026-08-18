from __future__ import annotations

from datetime import datetime

from app.localization import tr
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMessageBox, QPushButton, QVBoxLayout, QWidget

from repositories.domain_repository import DomainRepository
from repositories.entity_history_repository import EntityHistoryRepository
from ui.pages.entity_history_widget import EntityHistoryWidget
from ui.pages.entity_history_revision_viewer import open_geometry_revision, open_technical_card_revision
from ui.pages.entity_overview_widgets import (
    EngineeringSummaryCard,
    EntityHeaderWidget,
    GeneralInfoCard,
    OverviewKeyValueCard,
    QuickAttachmentPreview,
    RecentActivityCard,
    SquareGeometryCard,
)
from ui.pages.entity_page_controller import EntityPageController
from ui.pages.entity_tabs import create_attachment_tab_page, create_entity_tabs
from ui.pages.technical_card_widgets import ActualExecutionEditorWidget, BlastDesignEditorWidget, TechnicalCardEditorWidget
from ui.presentation_labels import domain_message
from domain.blasting.workflow import WORKFLOW_LABELS, blast_workflow_for


def _show(value, unit=""):
    if value in (None, ""):
        return "—"
    if isinstance(value, (int, float)):
        return f"{value:g}{unit}"
    return str(value)


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
        self._header(root)
        body = QHBoxLayout()
        left = QVBoxLayout()
        self.tabs = create_entity_tabs()
        left.addWidget(self.tabs)

        self.engineering_actions_widget = QWidget()
        actions = QHBoxLayout(self.engineering_actions_widget)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.addStretch()
        self.draft_button = QPushButton(tr("Save draft"))
        self.complete_button = QPushButton(tr("Complete"))
        self.draft_button.setEnabled(not self.read_only)
        self.complete_button.setEnabled(not self.read_only)
        self.draft_button.clicked.connect(self.save_draft)
        self.complete_button.clicked.connect(self.complete)
        actions.addWidget(self.draft_button)
        actions.addWidget(self.complete_button)
        left.addWidget(self.engineering_actions_widget)
        body.addLayout(left, 4)
        self._sidebar(body)
        root.addLayout(body)

        self._general()
        self.design_tab = BlastDesignEditorWidget(self.editor.take_tab(tr("Contour drilling")))
        self.execution_tab = ActualExecutionEditorWidget(self.editor.take_tab(tr("Execution fact")))
        self.tabs.addTab(self.design_tab, tr("Blast design"))
        self.tabs.addTab(self.execution_tab, tr("Execution fact"))
        general_page = self.editor.take_tab(tr("General"))
        general_page.deleteLater()
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
            "#CardTitle,#EngineeringSectionTitle{font-weight:600;color:#111827}"
            "#EntityTitle{font-size:24px;font-weight:700}#EntityContextLine{color:#667085}"
            "#MutedText{color:#6b7280}#SummaryValue{color:#111827;font-weight:600}"
            "#EngineeringSummaryText{color:#374151}#OverviewDivider{color:#e5e7eb;background:#e5e7eb;max-height:1px;border:0}"
        )

    def _sync_engineering_actions_visibility(self, *_args):
        self.engineering_actions_widget.setVisible(self.tabs.currentIndex() in (1, 2))

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
        self.summary = OverviewKeyValueCard("Summary")
        self.photo_preview = QuickAttachmentPreview("Photos", "photo")
        self.document_preview = QuickAttachmentPreview("Documents", "document")
        for widget in (self.summary, self.photo_preview, self.document_preview):
            widget.setMinimumWidth(250)
            widget.setMaximumWidth(290)
        right.addWidget(self.summary)
        right.addWidget(self.photo_preview)
        right.addWidget(self.document_preview)
        right.addStretch()
        body.addLayout(right, 1)

    def _general(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(8)
        top = QHBoxLayout()
        top.setSpacing(8)
        self.general_info = GeneralInfoCard()
        self.general_info.edit_notes_button.setText(tr("Open ›"))
        self.general_info.edit_notes_requested.connect(lambda: self._open_tab("blast_design"))
        self.geometry_card = SquareGeometryCard("Plan / geometry")
        self.geometry_card.reimport_requested.connect(self.reimport_geometry)
        top.addWidget(self.general_info, 1)
        top.addWidget(self.geometry_card, 0)
        layout.addLayout(top)

        self.engineering_summary = EngineeringSummaryCard()
        self.engineering_summary.section_open_requested.connect(self._open_tab)
        layout.addWidget(self.engineering_summary)

        bottom = QHBoxLayout()
        self.engineering_notes = EngineeringSummaryCard("Engineering notes")
        self.engineering_notes.section_open_requested.connect(self._open_tab)
        self.recent_activity = RecentActivityCard()
        self.recent_activity.open_history_requested.connect(lambda: self.tabs.setCurrentWidget(self.history))
        bottom.addWidget(self.engineering_notes, 3)
        bottom.addWidget(self.recent_activity, 2)
        layout.addLayout(bottom)
        self.tabs.addTab(page, tr("General information"))

    def _refresh_header(self, history_entries):
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
                f"{tr('Horizon')}: {self.blast_event.elevation:g} m",
                f"{tr('Geometry rev.')}: {self.rev.revision_number if self.rev else '—'}",
            ),
        )
        author = history_entries[-1].actor if history_entries else "—"
        revision = self.card.active_revision() or self.draft
        self.general_info.set_data(
            (
                ("Author", author),
                ("Created", _dateish(self.blast_event.created_at)),
                ("Source geometry", self.rev.source_file_name if self.rev else "—"),
                ("Imported", _dateish(self.rev.imported_at) if self.rev else "—"),
            ),
            revision.notes or "",
            can_edit=not self.read_only,
        )

    def _refresh_engineering_summary(self):
        revision = self.card.active_revision() or self.draft
        contour = revision.contour_parameters
        actual = revision.actual_execution
        group = _primary_contour_group(revision)
        if contour:
            spacing = contour.average_spacing_m if contour.average_spacing_m is not None else (group.spacing_m if group else None)
            depth = contour.average_depth_m if contour.average_depth_m is not None else (group.average_depth_m if group else None)
            inclination = group.inclination_deg if group and group.inclination_deg is not None else contour.inclination_deg
            diameter = contour.diameter_mm if contour.diameter_mm is not None else (group.diameter_mm if group else None)
            holes = contour.hole_count if contour.hole_count is not None else (group.hole_count if group else None)
            explosive = contour.explosive_type or (group.explosive_names() if group else "") or "—"
            design_lines = [
                f"{tr('Method')}: {_method_label(contour.controlled_blasting_method)}",
                f"{tr('Line length')} {_show(contour.line_length_m, ' m')}",
                f"{tr('Average depth')} {_show(depth, ' m')}",
                f"{tr('Azimuth')} {_show(group.azimuth_deg if group else None, '°')}",
                f"{tr('Inclination')} {_show(inclination, '°')}",
                f"{tr('Spacing')} {_show(spacing, ' m')}",
                f"Ø {_show(diameter, ' mm')}",
                f"{tr('Holes')} {_show(holes)}",
                f"{tr('Explosive')}: {explosive}",
            ]
        else:
            design_lines = [tr("No design data")]

        actual_group = next(
            (
                item for item in actual.actual_drilling_groups
                if item.included and item.group_type in {"contour_line", "presplit_line", "midsplit_line", "postsplit_line", "line_drilling"}
            ),
            next((item for item in actual.actual_drilling_groups if item.included), None),
        )
        has_fact = bool(actual.actual_drilling_groups or actual.actual_blast_date or actual.completion_status == "completed")
        execution_lines = [
            f"{tr('Blast date')} {_dateish(actual.actual_blast_date)}" if has_fact else tr("No execution data yet"),
            f"{tr('Average depth')} {_show(actual.actual_average_depth_m, ' m')}" if has_fact else "",
            f"{tr('Spacing')} {_show(actual_group.spacing_m if actual_group else None, ' m')}" if has_fact else "",
            f"{tr('Holes')} {_show(actual.actual_total_hole_count)}" if has_fact else "",
            f"{tr('Explosive')} {_show(actual.actual_total_explosive_mass_kg, ' kg')}" if has_fact else "",
        ]
        self.engineering_summary.set_sections(
            (
                ("blast_design", "Blast design", design_lines),
                ("execution", "Execution fact", execution_lines),
            )
        )
        self.engineering_notes.set_sections(
            (
                ("blast_design", "Blast design", [contour.notes if contour and contour.notes else revision.notes or tr("No notes")]),
                ("execution", "Execution fact", [actual.execution_notes or tr("No notes")]),
            )
        )
        self.summary.set_rows(
            (
                ("Blast date", _dateish(actual.actual_blast_date or self.blast_event.event_date), tr("Actual") if actual.actual_blast_date else tr("Planned")),
                ("Line length", _show(contour.line_length_m if contour else None, " m")),
                ("Average depth", _show((contour.average_depth_m if contour else None) or (group.average_depth_m if group else None), " m")),
                ("Spacing", _show((contour.average_spacing_m if contour else None) or (group.spacing_m if group else None), " m")),
                ("Method", _method_label(contour.controlled_blasting_method) if contour else "—"),
                ("Technical Card", f"{tr('Rev.')} {revision.revision_number}"),
            )
        )

    def _refresh_all(self):
        self.rev = self.blast_event.active_geometry_revision()
        history_entries = self.history_repo.for_blast_event(self.blast_event.id)
        self._refresh_header(history_entries)
        dataset = self.controller.state.active_dataset()
        self.geometry_card.set_geometry(
            self.rev.plan_geometry if self.rev else None,
            dataset.lines if dataset else [],
            revision=self.rev.revision_number if self.rev else None,
            source=self.rev.source_file_name if self.rev else "",
            focus_geometry=self.rev.plan_geometry if self.rev else None,
        )
        self.geometry_card.set_reimport_enabled(not self.read_only)
        self._refresh_engineering_summary()
        self.recent_activity.set_entries(history_entries)
        self.history.set_entries(history_entries)
        self._refresh_sidebar()

    def _attachments(self, title):
        kind = "photo" if title == "Photos" else "document"
        page, manager = create_attachment_tab_page(
            self.controller.attachments, "blast_event", self.blast_event.id, kind, read_only=self.read_only
        )
        manager.changed.connect(self._after_attachment_change)
        if kind == "photo":
            self.photo_manager = manager
        else:
            self.document_manager = manager
        return page

    def _after_attachment_change(self):
        self._refresh_sidebar()
        history_entries = self.history_repo.for_blast_event(self.blast_event.id)
        self.history.set_entries(history_entries)
        self.recent_activity.set_entries(history_entries)

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

    def _refresh_sidebar(self):
        photos = self.controller.attachments.list_for_owner("blast_event", self.blast_event.id, "photo")
        documents = self.controller.attachments.list_for_owner("blast_event", self.blast_event.id, "document")
        self.photo_preview.set_items(self.controller.attachments, photos, "No photos yet", can_add=not self.read_only)
        self.document_preview.set_items(self.controller.attachments, documents, "No documents yet", can_add=not self.read_only)

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
