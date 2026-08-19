from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.icons.ui.ui_icons import ui_icon
from app.localization import tr
from ui.assessment_result_presentation import (
    AssessmentResultPresentation,
    assessment_result_presentation,
)
from ui.pages.block_card_widgets import CardFrame
from ui.pages.entity_overview_widgets import OverviewLinkButton


DASHBOARD_CARD_STYLE = (
    "QFrame#DashboardCard{background:#ffffff;border:1px solid #d7dde6;"
    "border-radius:7px;}"
)
DASHBOARD_METRIC_STYLE = (
    "QFrame#DashboardMetricCard{background:#ffffff;border:1px solid #d7dde6;"
    "border-radius:7px;}"
)

QuadrantPresentation = AssessmentResultPresentation


def quadrant_presentation(value):
    return assessment_result_presentation(value)


def metric(value):
    return "—" if value is None else f"{value:.2f}"


def format_dashboard_datetime(value) -> str:
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return "—"


class MetricCard(CardFrame):
    def __init__(self, title, value, detail="", icon="analytics"):
        super().__init__()
        self.setObjectName("DashboardMetricCard")
        self.setStyleSheet(DASHBOARD_METRIC_STYLE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(74)
        self.setMaximumHeight(84)
        self.layout.setContentsMargins(12, 10, 12, 10)
        row = QHBoxLayout()
        row.setSpacing(10)
        image = QLabel()
        image.setPixmap(ui_icon(icon, "blue").pixmap(22, 22))
        image.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(image)
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(1)
        title_label = QLabel(tr(str(title)))
        title_label.setObjectName("MutedText")
        self.value_label = QLabel(str(value))
        self.value_label.setObjectName("DashboardMetricValue")
        self.value_label.setStyleSheet("font-size:18px;font-weight:700;color:#0f172a;")
        detail_label = QLabel(str(detail))
        detail_label.setObjectName("MutedText")
        detail_label.setWordWrap(False)
        box.addWidget(title_label)
        box.addWidget(self.value_label)
        box.addWidget(detail_label)
        row.addLayout(box, 1)
        self.layout.addLayout(row)


class EmptyStateWidget(QWidget):
    def __init__(self, text, icon="info"):
        super().__init__()
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        image = QLabel()
        image.setPixmap(ui_icon(icon).pixmap(20, 20))
        row.addWidget(image)
        label = QLabel(tr(str(text)))
        label.setObjectName("MutedText")
        row.addWidget(label)
        row.addStretch()


class DashboardCard(CardFrame):
    def __init__(self, title: str, parent=None):
        super().__init__()
        if parent is not None:
            self.setParent(parent)
        self.setObjectName("DashboardCard")
        self.setStyleSheet(DASHBOARD_CARD_STYLE)
        self.layout.setContentsMargins(12, 10, 12, 10)
        self.layout.setSpacing(7)
        self.header = QHBoxLayout()
        self.header.setSpacing(6)
        self.heading = QLabel(tr(title))
        self.heading.setObjectName("CardTitle")
        self.heading.setStyleSheet("font-weight:600;color:#1f2937;")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("MutedText")
        self.subtitle.setMinimumWidth(0)
        self.header.addWidget(self.heading)
        self.header.addSpacing(6)
        self.header.addWidget(self.subtitle)
        self.header.addStretch()
        self.layout.addLayout(self.header)

    def set_subtitle(self, text: str | None):
        value = str(text or "")
        self.subtitle.setText(value)
        self.subtitle.setVisible(bool(value))

    def add_header_action(self, text: str) -> OverviewLinkButton:
        button = OverviewLinkButton(text)
        self.header.addWidget(button)
        return button


@dataclass(frozen=True)
class SummaryRow:
    key: str
    title: str
    detail: str = ""
    trailing: str = ""
    accent: str | None = None


class SummaryRowWidget(QWidget):
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class CompactSummaryList(DashboardCard):
    """Bounded dashboard rows: row click filters, optional Go to navigates."""

    activated = Signal(str)
    go_to_requested = Signal(str)
    ROW_HEIGHT = 46

    def __init__(
        self,
        title: str,
        parent=None,
        *,
        visible_rows: int = 3,
        show_go_to: bool = False,
        fill_available: bool = False,
    ):
        super().__init__(title, parent)
        self.visible_rows = max(1, int(visible_rows))
        self.show_go_to = bool(show_go_to)
        self.fill_available = bool(fill_available)
        self.list = QListWidget()
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setSpacing(4)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list.setStyleSheet(
            "QListWidget{background:transparent;border:0;}"
            "QListWidget::item{background:transparent;border:0;}"
            "QListWidget::item:selected{background:transparent;}"
        )
        if self.fill_available:
            self.list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.layout.addWidget(self.list, 1)
        else:
            self.layout.addWidget(self.list, 0, Qt.AlignmentFlag.AlignTop)
            self.layout.addStretch(1)
        self.set_rows([])

    def clear_selection(self):
        self.list.clearSelection()
        self.list.setCurrentItem(None)

    def set_rows(self, rows: list[SummaryRow], *, empty_text="No data yet"):
        self.list.clear()
        rows = list(rows)
        if self.fill_available:
            self.list.setMinimumHeight(self.ROW_HEIGHT + 4)
            self.list.setMaximumHeight(16777215)
        else:
            visible_height = self.ROW_HEIGHT * min(max(1, len(rows)), self.visible_rows) + 4
            self.list.setMinimumHeight(visible_height)
            self.list.setMaximumHeight(self.ROW_HEIGHT * self.visible_rows + 4)
        if not rows:
            item = QListWidgetItem(tr(empty_text))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setSizeHint(QSize(0, self.ROW_HEIGHT))
            self.list.addItem(item)
            return
        for row in rows:
            key = str(row.key)
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setSizeHint(QSize(0, self.ROW_HEIGHT))
            holder = SummaryRowWidget()
            holder.setObjectName("DashboardSummaryRow")
            holder.setFixedHeight(self.ROW_HEIGHT - 2)
            holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            holder.setCursor(Qt.CursorShape.PointingHandCursor)
            holder.setStyleSheet(
                "QWidget#DashboardSummaryRow{background:#fbfcfd;"
                "border:1px solid #e2e6ec;border-radius:5px;}"
            )
            holder.clicked.connect(lambda current_key=key: self.activated.emit(current_key))
            layout = QHBoxLayout(holder)
            layout.setContentsMargins(7, 4, 8, 4)
            layout.setSpacing(7)
            if row.accent:
                accent = QFrame()
                accent.setFixedWidth(4)
                accent.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                accent.setStyleSheet(
                    f"background:{row.accent};border:0;border-radius:2px;"
                )
                layout.addWidget(accent)
            text = QVBoxLayout()
            text.setContentsMargins(0, 0, 0, 0)
            text.setSpacing(0)
            title = QLabel(row.title)
            title.setObjectName("RelatedEntityTitle")
            title.setMinimumWidth(0)
            title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            detail = QLabel(row.detail)
            detail.setObjectName("MutedText")
            detail.setMinimumWidth(0)
            detail.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            text.addWidget(title)
            text.addWidget(detail)
            layout.addLayout(text, 1)
            if row.trailing:
                trailing = QLabel(row.trailing)
                trailing.setObjectName("SummaryValue")
                trailing.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                trailing.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
                layout.addWidget(trailing)
            if self.show_go_to:
                go_to = OverviewLinkButton("Go to ›")
                go_to.setToolTip(tr("Open"))
                go_to.clicked.connect(
                    lambda _checked=False, current_key=key: self.go_to_requested.emit(current_key)
                )
                layout.addWidget(go_to)
            self.list.addItem(item)
            self.list.setItemWidget(item, holder)


class AssessmentProgressCard(DashboardCard):
    def __init__(self, parent=None):
        super().__init__("Assessment progress", parent)
        self.setMinimumHeight(118)
        summary = QHBoxLayout()
        summary.setContentsMargins(0, 2, 0, 3)
        self.counts = QLabel()
        self.counts.setStyleSheet("font-weight:600;color:#334155;")
        self.percent = QLabel("0%")
        self.percent.setStyleSheet("font-size:18px;font-weight:700;color:#1f4f7a;")
        self.percent.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        summary.addWidget(self.counts, 1)
        summary.addWidget(self.percent)
        self.layout.addLayout(summary)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setFixedHeight(17)
        self.progress.setStyleSheet(
            "QProgressBar{border:1px solid #ccd5e1;border-radius:8px;background:#eef2f6;}"
            "QProgressBar::chunk{background:#4f78a8;border-radius:7px;}"
        )
        self.layout.addWidget(self.progress)
        self.layout.addStretch()

    def set_counts(self, total: int, completed: int, drafts: int):
        total = max(0, int(total))
        completed = max(0, int(completed))
        drafts = max(0, int(drafts))
        pending = max(0, total - completed - drafts)
        percentage = round(100 * completed / total) if total else 0
        self.counts.setText(
            tr("Completed: %1  ·  Draft: %2  ·  Not evaluated: %3")
            .replace("%1", str(completed))
            .replace("%2", str(drafts))
            .replace("%3", str(pending))
        )
        self.percent.setText(f"{percentage}%")
        self.progress.setValue(percentage)


class BlastActivityCard(DashboardCard):
    def __init__(self, parent=None):
        super().__init__("Blast activity", parent)
        self.setMinimumHeight(118)
        self.counts = QLabel()
        self.counts.setStyleSheet("font-weight:600;color:#334155;")
        self.latest = QLabel()
        self.latest.setObjectName("MutedText")
        self.layout.addWidget(self.counts)
        self.layout.addWidget(self.latest)
        self.layout.addStretch()

    def set_data(self, production: int, contour: int, blasts):
        self.counts.setText(
            tr("Production: %1  ·  Contour: %2")
            .replace("%1", str(production))
            .replace("%2", str(contour))
        )
        dated = [item for item in blasts if getattr(item, "event_date", None) is not None]
        latest = max(dated, key=lambda item: item.event_date) if dated else None
        if latest is None:
            self.latest.setText(tr("No dated Blast Events yet"))
        else:
            self.latest.setText(
                f"{tr('Latest blast')}: {latest.name}  ·  "
                f"{format_dashboard_datetime(latest.event_date)}"
            )


class ProjectLinesCard(DashboardCard):
    VISIBLE_ROWS = 3
    ROW_HEIGHT = 42

    def __init__(self, parent=None):
        super().__init__("Project Lines", parent)
        self.setMinimumHeight(118)
        self.list = QListWidget()
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setSpacing(3)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list.setStyleSheet("QListWidget{background:transparent;border:0;}")
        self.list.setMinimumHeight(self.ROW_HEIGHT + 4)
        self.list.setMaximumHeight(self.ROW_HEIGHT * self.VISIBLE_ROWS + 5)
        self.layout.addWidget(self.list, 1)

    def set_datasets(self, datasets):
        self.list.clear()
        datasets = list(datasets)
        if not datasets:
            item = QListWidgetItem(tr("No Project Lines loaded"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setSizeHint(QSize(0, self.ROW_HEIGHT))
            self.list.addItem(item)
            return
        for dataset in datasets:
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, self.ROW_HEIGHT))
            holder = QWidget()
            holder.setObjectName("ProjectLinesDatasetRow")
            holder.setFixedHeight(self.ROW_HEIGHT - 2)
            holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            holder.setStyleSheet(
                "QWidget#ProjectLinesDatasetRow{background:#fbfcfd;"
                "border:1px solid #e2e6ec;border-radius:5px;}"
            )
            layout = QHBoxLayout(holder)
            layout.setContentsMargins(8, 4, 9, 4)
            layout.setSpacing(8)
            text = QVBoxLayout()
            text.setContentsMargins(0, 0, 0, 0)
            text.setSpacing(0)
            title = QLabel(str(dataset.name))
            title.setObjectName("RelatedEntityTitle")
            title.setMinimumWidth(0)
            stamp = getattr(dataset, "imported_at", None)
            detail = QLabel(
                f"{format_dashboard_datetime(stamp)}  ·  {getattr(dataset, 'source_file_name', '') or '—'}"
            )
            detail.setObjectName("MutedText")
            detail.setMinimumWidth(0)
            text.addWidget(title)
            text.addWidget(detail)
            layout.addLayout(text, 1)
            state = QLabel(tr("Active") if getattr(dataset, "is_active", False) else tr("Inactive"))
            state.setObjectName("StatusBadge")
            if getattr(dataset, "is_active", False):
                state.setStyleSheet(
                    "background:#edf8f0;color:#2f6f3e;border:1px solid #9bcaa6;"
                    "border-radius:5px;padding:3px 7px;font-weight:600;"
                )
            else:
                state.setStyleSheet(
                    "background:#f3f4f6;color:#4b5563;border:1px solid #d1d5db;"
                    "border-radius:5px;padding:3px 7px;font-weight:600;"
                )
            layout.addWidget(state)
            self.list.addItem(item)
            self.list.setItemWidget(item, holder)


class DashboardRecentActivityCard(DashboardCard):
    ROW_HEIGHT = 30

    def __init__(self, parent=None):
        super().__init__("Recent activity", parent)
        self.setMinimumHeight(142)
        self.list = QListWidget()
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setSpacing(0)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list.setStyleSheet(
            "QListWidget{background:transparent;border:0;}"
            "QListWidget::item{background:transparent;border:0;}"
        )
        self.layout.addWidget(self.list, 1)

    @staticmethod
    def _entry_parts(entry):
        if hasattr(entry, "changed_at"):
            entity_type = tr(str(getattr(entry, "entity_type", "")))
            entity_name = str(getattr(entry, "entity_name", "") or "")
            action = tr(str(getattr(entry, "action", "") or ""))
            title = " ".join(part for part in (entity_type, entity_name) if part)
            if action:
                title = f"{title}  ·  {action}" if title else action
            return title, getattr(entry, "changed_at", None), str(getattr(entry, "actor", "") or "")
        name, changed = entry[:2]
        author = str(entry[2] or "") if len(entry) > 2 else ""
        return str(name), changed, author

    def set_entries(self, entries):
        self.list.clear()
        visible = list(entries[:10])
        if not visible:
            item = QListWidgetItem(tr("No recent activity"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setSizeHint(QSize(0, self.ROW_HEIGHT))
            self.list.addItem(item)
            return
        for entry in visible:
            title_text, changed, author = self._entry_parts(entry)
            item = QListWidgetItem()
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setSizeHint(QSize(0, self.ROW_HEIGHT))
            holder = QWidget()
            holder.setObjectName("DashboardActivityRow")
            holder.setFixedHeight(self.ROW_HEIGHT - 1)
            holder.setStyleSheet(
                "QWidget#DashboardActivityRow{border-bottom:1px solid #eef1f5;}"
            )
            layout = QHBoxLayout(holder)
            layout.setContentsMargins(2, 0, 2, 0)
            layout.setSpacing(10)
            title = QLabel(title_text)
            title.setObjectName("ActivityTitle")
            title.setStyleSheet("font-weight:500;color:#334155;")
            title.setMinimumWidth(0)
            title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            title.setToolTip(title_text)
            stamp_text = format_dashboard_datetime(changed)
            meta_text = f"{author}  ·  {stamp_text}" if author else stamp_text
            meta = QLabel(meta_text)
            meta.setObjectName("MutedText")
            meta.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(title, 1)
            layout.addWidget(meta)
            self.list.addItem(item)
            self.list.setItemWidget(item, holder)


def section(title, child):
    card = DashboardCard(title)
    card.layout.addWidget(child)
    return card
