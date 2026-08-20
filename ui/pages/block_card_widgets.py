from __future__ import annotations

from decimal import Decimal

from app.localization import tr

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from repositories.audit_log_repository import AuditLogEntryRow
from repositories.production_blast_repository import ProductionBlastRow
from infrastructure.services.production_blast_service import AUDIT_FIELD_LABELS
from domain.blasting.workflow import WORKFLOW_LABELS, BlastWorkflowState
from ui.pages.plan_geometry_widget import PlanGeometryWidget
from ui.widgets.design_system import CardFrame, set_status_role

ACTION_LABELS = {"create": "Create", "update": "Update", "delete": "Delete", "attach": "Attach", "detach": "Detach"}
def apply_workflow_badge_style(label: QLabel) -> None:
    set_status_role(label, "warning")


def _dash(value) -> str:
    return str(value) if value not in (None, "") else "—"


def _number(value, unit="") -> str:
    if value is None:
        return "—"
    try:
        text=f"{float(value):g}"
    except (TypeError,ValueError):
        text=str(value)
    return f"{text}{unit}"


def _pattern(burden, spacing) -> str:
    if burden is None and spacing is None:
        return "—"
    return f"{_number(burden)} × {_number(spacing)} m"


def format_datetime(value) -> str:
    return value.strftime("%d.%m.%Y %H:%M") if value else "—"


def format_date(value) -> str:
    return value.strftime("%d.%m.%Y") if value else "—"


def format_decimal(value) -> str:
    if value is None:
        return "—"
    decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
    text = format(decimal_value.normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


class EmptySection(QWidget):
    def __init__(self, text: str = "This section will be implemented in the next stage"):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addStretch()
        label = QLabel(tr(text))
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setObjectName("MutedText")
        layout.addWidget(label)
        layout.addStretch()


class BlockHeaderWidget(CardFrame):
    def __init__(self):
        super().__init__()
        top = QHBoxLayout()
        self.title = QLabel(tr("Select a block"))
        self.title.setObjectName("BlockTitle")
        self.status = QLabel(tr("—"))
        apply_workflow_badge_style(self.status)
        self.edit_button = QPushButton(tr("Edit"))
        top.addWidget(self.title)
        top.addWidget(self.status)
        top.addStretch()
        top.addWidget(self.edit_button)
        self.layout.addLayout(top)
        self.meta = QHBoxLayout()
        self.layout.addLayout(self.meta)

    def set_block(self, block: ProductionBlastRow | None, can_edit: bool) -> None:
        while self.meta.count():
            item = self.meta.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self.edit_button.setEnabled(bool(block and can_edit))
        if block is None:
            self.title.setText(tr("Select a block")); self.status.setText(tr("—")); return
        self.title.setText(f"{tr('Block')} {block.block_number}")
        self.status.setText(tr(WORKFLOW_LABELS[BlastWorkflowState(block.status)]))
        if block.is_archived: self.status.setText(self.status.text() + " · " + tr("Archived"))
        values = [
            f"{tr('ID')}: {block.id}",
            f"{tr('Horizon')}: {format_decimal(block.horizon_m)}",
            f"{tr('Project / Quarry')}: {block.site_name}",
            f"{tr('Domain')}: {block.domain_name}",
            f"{tr('Created')}: {format_datetime(block.created_at)}",
            f"{tr('Updated')}: {format_datetime(block.updated_at)}",
        ]
        for value in values:
            badge = QLabel(value); badge.setObjectName("MetaBadge"); self.meta.addWidget(badge)
        self.meta.addStretch()


class BlockOverviewWidget(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.info = CardFrame(tr("General information")); self.grid = QGridLayout(); self.info.layout.addLayout(self.grid)
        self.scheme = PlanGeometryWidget(); layout.addWidget(self.info, 3); layout.addWidget(self.scheme, 2)

    def set_block(self, block: ProductionBlastRow | None) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        rows = []
        if block:
            rows = [
                ("Block number", block.block_number), ("ID", block.id),
                ("Created", format_datetime(block.created_at)), ("Author", block.author_name),
                ("Horizon", format_decimal(block.horizon_m)), ("Project / Quarry", block.site_name),
                ("Domain", block.domain_name), ("Status", tr(WORKFLOW_LABELS[BlastWorkflowState(block.status)])),
                ("Planned blast date", format_date(block.planned_blast_date)), ("Comment", block.comment),
            ]
        else: rows = [("Block", "—")]
        for row, (name, value) in enumerate(rows):
            left = QLabel(tr(name)); left.setObjectName("MutedText")
            right = QLabel(_dash(value)); right.setWordWrap(True)
            self.grid.addWidget(left, row, 0); self.grid.addWidget(right, row, 1)
        if block is None: self.scheme.set_geometry(None, context="Geometry is not loaded")


class BlockSchemePlaceholder(CardFrame):
    def __init__(self):
        super().__init__("Block scheme")
        self.box = QLabel(tr("Block scheme is not loaded yet")); self.box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.box.setMinimumHeight(220); self.box.setObjectName("SchemePlaceholder"); self.layout.addWidget(self.box)

    def set_block(self, block: ProductionBlastRow | None) -> None:
        number = block.block_number if block else "—"
        self.box.setText(f"{number}\nBlock scheme is not loaded yet")


class CompactInfoCards(QWidget):
    """Read-only Block summaries sourced from one current Technical Card revision."""

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0)
        self.labels=[]; self.open_buttons=[]
        for title in ("Geomechanical parameters", "Blast design parameters", "Execution fact"):
            card = CardFrame(title)
            label = QLabel(tr("No data yet")); label.setObjectName("MutedText"); label.setWordWrap(True)
            button=QPushButton(tr("Open section"))
            card.layout.addWidget(label); card.layout.addStretch(); card.layout.addWidget(button)
            self.labels.append(label); self.open_buttons.append(button); layout.addWidget(card)

    def set_block(self, block: ProductionBlastRow | None) -> None:
        if block is None:self.set_revision(None)

    def set_revision(self, revision) -> None:
        if revision is None:
            for label in self.labels:label.setText(tr("No data yet"))
            return

        geo=revision.geomechanical_parameters
        if geo is None:
            geo_text=tr("No geomechanics data yet")
        else:
            joint_sets=len(geo.joint_sets or [])
            rows=(
                ("Lithology",geo.lithology or "—"),
                ("UCS",_number(geo.ucs_mpa," MPa")),
                ("RQD",_number(geo.rqd_percent," %")),
                ("GSI",_number(geo.gsi)),
                ("FF",_number(geo.ff)),
                ("Joint sets",joint_sets if joint_sets else "—"),
            )
            geo_text="\n".join(f"{tr(name)}: {value}" for name,value in rows)

        main=next((g for g in revision.drilling_groups if g.included and g.group_type=="main_pattern"),None)
        if main is None:
            main=next((g for g in revision.drilling_groups if g.included),None)
        if main is None:
            design_text=tr("No blast-design data yet")
        else:
            explosive=main.explosive_names() or main.explosive_type or "—"
            rows=(
                ("Hole diameter",_number(main.diameter_mm," mm")),
                ("Drilling pattern",_pattern(main.burden_m,main.spacing_m)),
                ("Average depth",_number(main.average_depth_m," m")),
                ("Inclination",_number(main.inclination_deg,"°")),
                ("Hole count",_number(main.hole_count)),
                ("Explosive",explosive),
                ("Charge per hole",_number(main.explosive_mass_per_hole_kg()," kg")),
            )
            design_text="\n".join(f"{tr(name)}: {value}" for name,value in rows)

        actual=revision.actual_execution
        actual_main=next((g for g in actual.actual_drilling_groups if g.included and g.group_type=="main_pattern"),None)
        if actual_main is None:
            actual_main=next((g for g in actual.actual_drilling_groups if g.included),None)
        has_fact=bool(actual.actual_drilling_groups or actual.actual_blast_date or actual.completion_status=="completed")
        if not has_fact:
            execution_text=tr("No execution data yet")
        else:
            rows=(
                ("Actual blast date",actual.actual_blast_date or "—"),
                ("Actual drilling pattern",_pattern(actual_main.burden_m,actual_main.spacing_m) if actual_main else "—"),
                ("Actual average depth",_number(actual.actual_average_depth_m," m")),
                ("Actual hole count",_number(actual.actual_total_hole_count)),
                ("Actual drilling length",_number(actual.actual_total_drilling_length_m," m")),
                ("Actual explosive mass",_number(actual.actual_total_explosive_mass_kg," kg")),
                ("Completion status",tr((actual.completion_status or "planned").replace("_"," ").title())),
            )
            execution_text="\n".join(f"{tr(name)}: {value}" for name,value in rows)

        for label,text in zip(self.labels,(geo_text,design_text,execution_text)):label.setText(text)


class BlockSummaryWidget(CardFrame):
    def __init__(self):
        super().__init__("Summary"); self.grid = QGridLayout(); self.layout.addLayout(self.grid)

    def set_data(self, block: ProductionBlastRow | None, photo_count: int, document_count: int, audit_count: int) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        rows = [
            ("Status", WORKFLOW_LABELS[BlastWorkflowState(block.status)] if block else "—"),
            ("Planned blast date", format_date(block.planned_blast_date) if block else "—"),
            ("Photos", photo_count), ("Documents", document_count), ("History records", audit_count),
        ]
        for row, (name, value) in enumerate(rows):
            self.grid.addWidget(QLabel(tr(name)), row, 0); self.grid.addWidget(QLabel(_dash(value)), row, 1)


class AttachmentPreviewWidget(CardFrame):
    def __init__(self, title: str):
        super().__init__(title); header = QHBoxLayout(); self.add_button = QPushButton(tr("Manage")); self.add_button.setEnabled(False)
        header.addStretch(); header.addWidget(self.add_button); self.layout.addLayout(header); self.content = QVBoxLayout(); self.layout.addLayout(self.content)

    def set_items(self, items: list, empty_text: str) -> None:
        while self.content.count():
            item = self.content.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        if not items:
            label = QLabel(empty_text); label.setObjectName("MutedText"); self.content.addWidget(label); return
        for attachment in items[:5]:
            label = QLabel(attachment.original_filename); label.setWordWrap(True); self.content.addWidget(label)


class AuditPreviewWidget(CardFrame):
    def __init__(self, title: str = "Change history"):
        super().__init__(title); self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([tr("Date"), tr("User"), tr("Action"), tr("Field"), tr("Old"), tr("New")])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.layout.addWidget(self.table)

    def set_entries(self, entries: list[AuditLogEntryRow], limit: int = 5) -> None:
        visible = entries[:limit]; self.table.setRowCount(len(visible))
        for row, entry in enumerate(visible):
            values = [format_datetime(entry.created_at), entry.user_display_name,
                      tr(ACTION_LABELS.get(entry.action, entry.action)),
                      AUDIT_FIELD_LABELS.get(entry.field_name or "", entry.field_name or ""),
                      entry.old_value or "", entry.new_value or ""]
            for col, value in enumerate(values): self.table.setItem(row, col, QTableWidgetItem(value))


class CommentsWidget(CardFrame):
    def __init__(self):
        super().__init__(); header=QHBoxLayout(); header.addWidget(QLabel(tr("Comments"))); header.addStretch(); self.edit_button=QPushButton(tr("Edit")); header.addWidget(self.edit_button); self.layout.addLayout(header)
        self.text = QTextEdit(); self.text.setReadOnly(True); self.layout.addWidget(self.text)

    def set_block(self, block: ProductionBlastRow | None) -> None:
        self.text.setPlainText(block.comment if block and block.comment else "—")
