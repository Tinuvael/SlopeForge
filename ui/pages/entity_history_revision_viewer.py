from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from app.localization import tr
from ui.editors.assessment_evaluation_editor import AssessmentAreaEvaluationDialog
from ui.pages.plan_geometry_widget import PlanGeometryWidget
from ui.pages.technical_card_widgets import TechnicalCardEditorWidget


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
    """Open one immutable Technical Card revision without exposing save actions."""
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
    layout.addWidget(editor, 1)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.exec()


def open_assessment_revision(parent, *, area, evaluation, revision, attachment_service=None):
    """Reuse the proven Assessment revision-safe read-only dialog."""
    dialog = AssessmentAreaEvaluationDialog(
        area,
        evaluation,
        revision,
        None,
        parent,
        read_only=True,
        attachment_service=attachment_service,
    )
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
