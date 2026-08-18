from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractSpinBox, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QGroupBox,
    QLabel, QLineEdit, QSplitter, QTextEdit, QVBoxLayout, QWidget,
)

from app.localization import tr
from ui.editors.assessment_evaluation_editor import AssessmentAreaEvaluationDialog
from ui.pages.plan_geometry_widget import PlanGeometryWidget
from ui.pages.technical_card_widgets import TechnicalCardEditorWidget


def _lock_technical_revision(editor: TechnicalCardEditorWidget) -> None:
    """Make every value control visibly read-only without disabling navigation/help."""
    host = editor.editor
    for control in host.findChildren(QLineEdit):
        control.setReadOnly(True)
    for control in host.findChildren(QTextEdit):
        control.setReadOnly(True)
    for control in host.findChildren(QAbstractSpinBox):
        control.setReadOnly(True)
    for control in host.findChildren(QComboBox):
        control.setEnabled(False)
    for control in host.findChildren(QCheckBox):
        control.setEnabled(False)


def _take_optional_tab(dialog: AssessmentAreaEvaluationDialog, title: str, parent=None):
    for index in range(dialog.tabs.count()):
        if dialog.tabs.tabText(index) == title:
            page = dialog.tabs.widget(index)
            dialog.tabs.removeTab(index)
            page.setParent(parent)
            return page
    return None


def open_technical_card_revision(
    parent,
    *,
    event,
    card,
    revision,
    domain_name="",
    explosive_products=None,
    charge_presets=None,
):
    """Open one immutable Technical Card revision without edit/history controls."""
    dialog = QDialog(parent)
    dialog.setWindowTitle(f"{tr('Technical Card')} R{revision.revision_number} — {tr('Read only')}")
    dialog.resize(1180, 820)
    layout = QVBoxLayout(dialog)
    editor = TechnicalCardEditorWidget(
        event,
        card,
        revision,
        lambda *_args, **_kwargs: None,
        dialog,
        True,
        domain_name=domain_name,
        explosive_products=explosive_products,
        charge_presets=charge_presets,
    )
    editor.draft.hide()
    editor.complete.hide()
    history_page = editor.take_tab(tr("Revision history"))
    history_page.deleteLater()
    _lock_technical_revision(editor)
    layout.addWidget(editor, 1)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()


def open_assessment_revision(parent, *, area, evaluation, revision, attachment_service=None):
    """Open one saved Assessment revision with only revision-relevant content."""
    dialog = AssessmentAreaEvaluationDialog(
        area,
        evaluation,
        revision,
        None,
        parent,
        read_only=True,
        attachment_service=attachment_service,
    )

    geometry = _take_optional_tab(dialog, tr("Geometry"))
    condition = _take_optional_tab(dialog, tr("Face condition"))
    attachments = _take_optional_tab(dialog, tr("Photos and documents"))
    history = _take_optional_tab(dialog, tr("History"))
    for obsolete in (attachments, history):
        if obsolete is not None:
            obsolete.deleteLater()

    if geometry is not None or condition is not None:
        combined = QWidget(dialog)
        combined_layout = QVBoxLayout(combined)
        combined_layout.setContentsMargins(8, 8, 8, 8)
        splitter = QSplitter(Qt.Orientation.Vertical, combined)
        splitter.setChildrenCollapsible(False)
        for title, page in ((tr("Geometry"), geometry), (tr("Face condition"), condition)):
            if page is None:
                continue
            section = QGroupBox(title, splitter)
            section_layout = QVBoxLayout(section)
            page.setParent(section)
            section_layout.addWidget(page)
            splitter.addWidget(section)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        combined_layout.addWidget(splitter)
        dialog.tabs.insertTab(1, combined, tr("Geometry & face condition"))

    dialog.exec()


def open_geometry_revision(parent, *, revision, project_lines=None, assessment=False):
    """Open the exact frozen historical geometry in a focused read-only plan dialog."""
    dialog = QDialog(parent)
    number = revision.revision_number
    title = tr("Assessment geometry") if assessment else tr("Blast geometry")
    dialog.setWindowTitle(f"{title} R{number} — {tr('Read only')}")
    dialog.resize(1000, 760)
    layout = QVBoxLayout(dialog)
    if assessment:
        geometry = revision.final_geometry_frozen
        context = f"{tr('Geometry')} R{number}"
        if revision.change_reason:
            context += f" · {revision.change_reason}"
    else:
        geometry = revision.plan_geometry
        context = f"{tr('Geometry')} R{number} · {revision.source_file_name}"
    plan = PlanGeometryWidget()
    plan.reimport_button.hide()
    plan.use_center_control()
    plan.set_geometry(geometry, project_lines or [], context, focus_geometry=geometry)
    layout.addWidget(plan, 1)
    hint = QLabel(tr("Historical revision is read-only."))
    hint.setStyleSheet("color:#6b7280;")
    layout.addWidget(hint)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()
