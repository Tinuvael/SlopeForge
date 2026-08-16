from __future__ import annotations

from decimal import Decimal

from app.localization import tr
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)


_STATUS_LABELS = {
    "in_preparation": "In preparation",
    "planned": "Planned",
    "blasted": "Blasted",
    "assessed": "Assessed",
}


def workflow_status_label(value: str | None) -> str:
    return tr(_STATUS_LABELS.get(value or "", value or "—"))


def apply_workflow_badge_style(label: QLabel) -> None:
    label.setObjectName("StatusBadge")
    label.setStyleSheet(
        "background:#fff4d6;color:#8a5a00;border:1px solid #f4c76b;"
        "border-radius:5px;padding:4px 8px;"
    )


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


class CardFrame(QFrame):
    def __init__(self, title: str | None = None):
        super().__init__()
        self.setObjectName("CardFrame")
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 12, 14, 12)
        self.layout.setSpacing(8)
        if title:
            label = QLabel(tr(title))
            label.setObjectName("CardTitle")
            self.layout.addWidget(label)


class EmptySection(QWidget):
    def __init__(self, text=""):
        super().__init__(); layout=QVBoxLayout(self); label=QLabel(text); label.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(label)


class BlockHeaderWidget(CardFrame):
    def __init__(self):
        super().__init__(); top=QHBoxLayout(); self.title=QLabel(); self.title.setObjectName("BlockTitle"); self.status=QLabel(); apply_workflow_badge_style(self.status); self.edit_button=QPushButton(tr("Edit")); top.addWidget(self.title); top.addWidget(self.status); top.addStretch(); top.addWidget(self.edit_button); self.layout.addLayout(top); self.meta=QHBoxLayout(); self.layout.addLayout(self.meta)
    def set_block(self,block,editable=False):
        while self.meta.count():
            item=self.meta.takeAt(0); widget=item.widget()
            if widget: widget.deleteLater()
        if block is None:
            self.title.setText(tr("Block")); self.status.setText("—"); self.edit_button.setEnabled(False); return
        self.title.setText(f"{tr('Block')} {block.block_number}"); self.status.setText(workflow_status_label(block.status)); self.edit_button.setEnabled(editable)
        values=(f"{tr('ID')}: {block.id}",f"{tr('Horizon')}: {format_decimal(block.horizon_m)}",f"{tr('Domain')}: {block.domain_name}",f"{tr('Planned blast date')}: {format_date(block.planned_blast_date)}")
        for text in values:
            label=QLabel(text); label.setObjectName("MetaBadge"); self.meta.addWidget(label)
        self.meta.addStretch()


class BlockOverviewWidget(CardFrame):
    def __init__(self):
        super().__init__(); self.scheme=SimpleSchemeWidget(); self.layout.addWidget(self.scheme)
    def set_block(self,block): self.scheme.set_context(block.block_number if block else None)


class SimpleSchemeWidget(QWidget):
    reimport_requested = __import__('PySide6.QtCore',fromlist=['Signal']).Signal()
    def __init__(self):
        super().__init__(); root=QVBoxLayout(self); self.context=QLabel(); self.context.setObjectName("MutedText"); self.placeholder=QLabel(tr("Block scheme is not loaded yet")); self.placeholder.setObjectName("SchemePlaceholder"); self.placeholder.setMinimumHeight(180); self.placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter); self.reimport_button=QPushButton(tr("Reimport geometry")); self.reimport_button.clicked.connect(self.reimport_requested); root.addWidget(self.context); root.addWidget(self.placeholder); root.addWidget(self.reimport_button,alignment=Qt.AlignmentFlag.AlignRight)
    def set_context(self,text): self.context.setText(text or "")
    def set_geometry(self,_geometry,_lines=None,context=""):self.context.setText(context); self.placeholder.setText(tr("Geometry loaded") if _geometry else tr("Block scheme is not loaded yet"))
    def set_reimport_enabled(self,enabled):self.reimport_button.setEnabled(enabled)


class CompactInfoCards(QWidget):
    def __init__(self):
        super().__init__(); self.layout=QGridLayout(self); self.labels=[]
    def set_block(self,block):
        for label in self.labels:label.deleteLater()
        self.labels=[]
        values=[(tr("Author"),getattr(block,"author_name",None) or "—"),(tr("Created"),format_datetime(getattr(block,"created_at",None))),(tr("Updated"),format_datetime(getattr(block,"updated_at",None)))] if block else []
        for index,(name,value) in enumerate(values):
            label=QLabel(f"{name}\n{value}"); label.setObjectName("CardFrame"); self.layout.addWidget(label,0,index); self.labels.append(label)


class CommentsWidget(CardFrame):
    def __init__(self):
        super().__init__(tr("Comments")); self.text=QLabel(); self.text.setWordWrap(True); self.edit_button=QPushButton(tr("Edit")); self.layout.addWidget(self.text); self.layout.addWidget(self.edit_button,alignment=Qt.AlignmentFlag.AlignRight)
    def set_block(self,block): self.text.setText(getattr(block,"comment",None) or tr("No comments"))


class AuditPreviewWidget(CardFrame):
    def __init__(self,title="Recent activity"):
        super().__init__(tr(title)); self.body=QLabel(); self.body.setWordWrap(True); self.layout.addWidget(self.body)
    def set_entries(self,entries,limit=5):
        values=list(entries or [])[:limit]; self.body.setText("\n".join(getattr(item,"message",str(item)) for item in values) if values else tr("No activity"))


class BlockSummaryWidget(CardFrame):
    def __init__(self):
        super().__init__(tr("Summary")); self.body=QLabel(); self.body.setWordWrap(True); self.layout.addWidget(self.body)
    def set_data(self,block,photo_count,document_count,history_count):
        if not block:self.body.setText("—");return
        self.body.setText(f"{tr('Photos')}: {photo_count}\n{tr('Documents')}: {document_count}\n{tr('History')}: {history_count}")


class AttachmentPreviewWidget(CardFrame):
    def __init__(self,title):
        super().__init__(tr(title)); self.body=QLabel(); self.body.setWordWrap(True); self.add_button=QPushButton(tr("Manage")); self.layout.addWidget(self.body); self.layout.addWidget(self.add_button,alignment=Qt.AlignmentFlag.AlignRight)
    def set_items(self,items,empty_text):
        values=list(items or [])
        if not values:self.body.setText(tr(empty_text));return
        self.body.setText("\n".join(getattr(item,"title",str(item)) for item in values[:5]))