from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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


# Compatibility name retained for the existing dashboard repository/tests.
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
    """Small KPI card using the same card shell/margins as entity overviews."""

    def __init__(self, title, value, detail="", icon="analytics"):
        super().__init__()
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(78)
        self.setMaximumHeight(92)
        row = QHBoxLayout()
        row.setSpacing(10)
        image = QLabel()
        image.setPixmap(ui_icon(icon, "blue").pixmap(22, 22))
        image.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(image)
        box = QVBoxLayout()
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(2)
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
    """Card header used by dashboard panels; actions match entity Overview links."""

    def __init__(self, title: str, parent=None):
        super().__init__()
        if parent is not None:
            self.setParent(parent)
        self.header = QHBoxLayout()
        self.header.setSpacing(6)
        self.heading = QLabel(tr(title))
        self.heading.setObjectName("CardTitle")
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


class CompactSummaryList(DashboardCard):
    """Card-like rows for Domain/Interval summaries; only the inner list may scroll."""

    activated = Signal(str)
    VISIBLE_ROWS = 4
    ROW_HEIGHT = 46

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        self.list = QListWidget()
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setSpacing(4)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list.setStyleSheet("QListWidget{background:transparent;border:0;}")
        self.list.itemClicked.connect(self._emit_item)
        self.layout.addWidget(self.list, 1)
        self.set_rows([])

    def set_rows(self, rows: list[SummaryRow], *, empty_text="No data yet"):
        self.list.clear()
        rows = list(rows)
        visible_height = self.ROW_HEIGHT * min(max(1, len(rows)), self.VISIBLE_ROWS) + 6
        self.list.setMinimumHeight(visible_height)
        self.list.setMaximumHeight(self.ROW_HEIGHT * self.VISIBLE_ROWS + 6)
        if not rows:
            item = QListWidgetItem(tr(empty_text))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setSizeHint(QSize(0, self.ROW_HEIGHT))
            self.list.addItem(item)
            return
        for row in rows:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, row.key)
            item.setSizeHint(QSize(0, self.ROW_HEIGHT))
            holder = QWidget()
            holder.setObjectName("DashboardSummaryRow")
            holder.setFixedHeight(self.ROW_HEIGHT - 2)
            holder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            holder.setStyleSheet(
                "QWidget#DashboardSummaryRow{background:#ffffff;"
                "border:1px solid #d9dee7;border-radius:5px;}"
            )
            layout = QHBoxLayout(holder)
            layout.setContentsMargins(9, 5, 10, 5)
            layout.setSpacing(8)
            text = QVBoxLayout()
            text.setContentsMargins(0, 0, 0, 0)
            text.setSpacing(0)
            title = QLabel(row.title)
            title.setObjectName("RelatedEntityTitle")
            title.setMinimumWidth(0)
            detail = QLabel(row.detail)
            detail.setObjectName("MutedText")
            detail.setMinimumWidth(0)
            text.addWidget(title)
            text.addWidget(detail)
            layout.addLayout(text, 1)
            if row.trailing:
                trailing = QLabel(row.trailing)
                trailing.setObjectName("SummaryValue")
                trailing.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                layout.addWidget(trailing)
            self.list.addItem(item)
            self.list.setItemWidget(item, holder)

    def _emit_item(self, item):
        key = item.data(Qt.ItemDataRole.UserRole)
        if key not in (None, ""):
            self.activated.emit(str(key))


class ProjectLinesCard(DashboardCard):
    """Compact history of Site-wide Project Lines datasets."""

    VISIBLE_ROWS = 3
    ROW_HEIGHT = 42

    def __init__(self, parent=None):
        super().__init__("Project Lines", parent)
        self.list = QListWidget()
        self.list.setFrameShape(QFrame.Shape.NoFrame)
        self.list.setSpacing(3)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list.setStyleSheet("QListWidget{background:transparent;border:0;}")
        self.list.setMinimumHeight(self.ROW_HEIGHT + 4)
        self.list.setMaximumHeight(self.ROW_HEIGHT * self.VISIBLE_ROWS + 6)
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
                "QWidget#ProjectLinesDatasetRow{background:#ffffff;"
                "border:1px solid #d9dee7;border-radius:5px;}"
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
    """Four stable one-line activity slots, matching operational entity cards."""

    SLOT_COUNT = 4
    SLOT_HEIGHT = 30

    def __init__(self, parent=None):
        super().__init__("Recent activity", parent)
        self.rows = QVBoxLayout()
        self.rows.setSpacing(3)
        self.layout.addLayout(self.rows)

    def set_entries(self, entries):
        while self.rows.count():
            item = self.rows.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        visible = list(entries[: self.SLOT_COUNT])
        for index in range(self.SLOT_COUNT):
            slot = QWidget()
            slot.setFixedHeight(self.SLOT_HEIGHT)
            layout = QHBoxLayout(slot)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            if index < len(visible):
                name, changed = visible[index]
                title = QLabel(f"●  {name}")
                title.setObjectName("ActivityTitle")
                title.setMinimumWidth(0)
                title.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
                stamp = QLabel(format_dashboard_datetime(changed))
                stamp.setObjectName("MutedText")
                stamp.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                layout.addWidget(title, 1)
                layout.addWidget(stamp)
            elif index == 0 and not visible:
                empty = QLabel(tr("No recent activity"))
                empty.setObjectName("MutedText")
                layout.addWidget(empty)
                layout.addStretch()
            self.rows.addWidget(slot)


def section(title, child):
    """Legacy helper kept for callers outside #69; new dashboards use DashboardCard."""
    card = DashboardCard(title)
    card.layout.addWidget(child)
    return card
