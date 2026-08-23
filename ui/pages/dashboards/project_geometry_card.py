from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from app.localization import tr
from ui.pages.entity_overview_widgets import OverviewLinkButton

from .widgets import DashboardCard, format_dashboard_datetime


class ProjectGeometryCard(DashboardCard):
    """Compact Project-level current design/actual surface summary."""

    upload_requested = Signal(str)
    ROW_HEIGHT = 44

    def __init__(self, parent=None):
        super().__init__("Geometry", parent)
        self.setMinimumHeight(140)
        self.setMinimumWidth(0)
        self.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )
        self._rows: dict[str, tuple[QLabel, QLabel, OverviewLinkButton]] = {}

        # Three visual row slots: design at the top, one intentionally empty
        # slot in the middle, actual survey at the bottom. This keeps the two
        # independent working surfaces visually separated and uses the full
        # height of the Project data card instead of bunching both rows at top.
        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        self.layout.addLayout(self.body, 1)
        self._add_dataset_row("design", tr("Design surface"))
        self.body.addStretch(1)
        self._add_dataset_row("actual", tr("Actual survey"))

    def _add_dataset_row(self, kind: str, label: str) -> None:
        host = QWidget()
        host.setMinimumWidth(0)
        host.setFixedHeight(self.ROW_HEIGHT)
        host.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Fixed,
        )
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(8)

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(0)
        title = QLabel(label)
        title.setObjectName("RelatedEntityTitle")
        title.setMinimumWidth(0)
        title.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        title.setToolTip(label)
        detail = QLabel("—")
        detail.setObjectName("MutedText")
        detail.setMinimumWidth(0)
        detail.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        detail.setToolTip("")
        text.addWidget(title)
        text.addWidget(detail)
        row.addLayout(text, 1)

        action = OverviewLinkButton(tr("Import"))
        action.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        action.clicked.connect(
            lambda _checked=False, dataset_kind=kind: self.upload_requested.emit(
                dataset_kind
            )
        )
        row.addWidget(action)
        self.body.addWidget(host)
        self._rows[kind] = (title, detail, action)

    @staticmethod
    def _source_names(dataset) -> str:
        files = list(getattr(dataset, "source_files_json", ()) or ())
        names = [
            str(item.get("original_filename") or item.get("stored_filename") or "")
            for item in files
            if isinstance(item, dict)
        ]
        return " + ".join(name for name in names if name)

    def set_dataset(self, kind: str, dataset) -> None:
        _title, detail, _action = self._rows[kind]
        if dataset is None:
            detail.setText("—")
            detail.setToolTip("")
            return
        names = self._source_names(dataset)
        stamp = format_dashboard_datetime(getattr(dataset, "imported_at", None))
        revision = int(getattr(dataset, "revision_number", 0) or 0)
        source_format = str(
            getattr(dataset, "source_format", "") or ""
        ).upper()
        vertices = int(getattr(dataset, "vertex_count", 0) or 0)
        triangles = int(getattr(dataset, "triangle_count", 0) or 0)
        summary = f"R{revision} · {source_format} · V {vertices} · T {triangles}"
        if stamp != "—":
            summary = f"{summary} · {stamp}"
        detail.setText(summary)
        detail.setToolTip(names or summary)

    def set_datasets(self, design, actual) -> None:
        self.set_dataset("design", design)
        self.set_dataset("actual", actual)

    def set_actions_enabled(self, enabled: bool) -> None:
        for _title, _detail, action in self._rows.values():
            action.setEnabled(bool(enabled))
