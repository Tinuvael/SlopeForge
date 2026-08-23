from __future__ import annotations

from statistics import mean

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
)

from app.localization import tr
from domain.blasting.contour_drilling import summarize_contour_drilling
from domain.blasting.drillholes import Drillhole
from ui.widgets.design_system import CardFrame, set_button_role, set_status_role


def _value(value, suffix="", digits=2):
    if value is None:
        return "—"
    if isinstance(value, int):
        return str(value)
    text = f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


class _ElidedLabel(QLabel):
    """Single-line metadata label that never pushes actions out of a card."""

    def __init__(self, text="", parent=None):
        super().__init__(parent)
        self._full_text = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.setText(text)

    def setText(self, text):
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self._refresh_text()

    def _refresh_text(self):
        if not self._full_text:
            super().setText("")
            return
        available = max(20, self.contentsRect().width())
        super().setText(
            self.fontMetrics().elidedText(
                self._full_text,
                Qt.TextElideMode.ElideMiddle,
                available,
            )
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._refresh_text()


class DrillholeDatasetCard(CardFrame):
    import_requested = Signal(str)

    def __init__(self, dataset_kind: str, *, contour=False, read_only=False, parent=None):
        super().__init__()
        if parent is not None:
            self.setParent(parent)
        self.dataset_kind = dataset_kind
        self.contour = bool(contour)
        self.read_only = bool(read_only)
        self._import_available = not self.read_only
        self.setObjectName("EngineeringCard")
        self.layout.setContentsMargins(12, 10, 12, 10)
        self.layout.setSpacing(7)

        header = QHBoxLayout()
        title = tr("Design drillholes") if dataset_kind == "design" else tr("As-drilled holes")
        self.title = QLabel(title)
        self.title.setObjectName("EngineeringSectionTitle")
        self.source = _ElidedLabel(tr("No dataset loaded"))
        self.source.setObjectName("MutedText")
        self.button = set_button_role(QPushButton(tr("Import")), "secondary")
        self.button.setEnabled(self._import_available)
        self.button.clicked.connect(lambda: self.import_requested.emit(self.dataset_kind))
        header.addWidget(self.title)
        header.addWidget(self.source, 1)
        header.addWidget(self.button)
        self.layout.addLayout(header)

        self.status_row = QHBoxLayout()
        self.status = QLabel()
        self.status.hide()
        self.status_row.addWidget(self.status)
        self.status_row.addStretch(1)
        self.layout.addLayout(self.status_row)

        self.helper = QLabel()
        self.helper.setObjectName("FormHelperText")
        self.helper.setWordWrap(True)
        self.layout.addWidget(self.helper)

        self.metrics = QGridLayout()
        self.metrics.setHorizontalSpacing(18)
        self.metrics.setVerticalSpacing(2)
        self._labels = {}
        self.layout.addLayout(self.metrics)

    def set_import_available(self, available: bool, reason: str | None = None):
        self._import_available = bool(available) and not self.read_only
        self.button.setEnabled(self._import_available)
        self.button.setToolTip("" if self._import_available else str(reason or ""))
        if not self._import_available and reason:
            self.show_helper(reason)

    def show_helper(self, text: str):
        self.helper.setText(tr(text) if text else "")
        self.helper.setVisible(bool(text))

    def show_status(self, text: str, role: str = "info"):
        set_status_role(self.status, role)
        self.status.setText(tr(text))
        self.status.show()

    def clear_status(self):
        self.status.hide()
        self.status.setText("")

    def _set_metrics(self, values):
        while self.metrics.count():
            item = self.metrics.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._labels = {}
        max_columns = 5
        for index, (caption, value) in enumerate(values):
            column = index % max_columns
            row = (index // max_columns) * 2
            label = QLabel(tr(caption))
            label.setObjectName("MutedText")
            label.setWordWrap(True)
            output = QLabel(str(value))
            output.setObjectName("SummaryValue")
            self.metrics.addWidget(label, row, column)
            self.metrics.addWidget(output, row + 1, column)
            self.metrics.setColumnStretch(column, 1)
            self._labels[caption] = output

    @staticmethod
    def _source_name(row):
        files = list(getattr(row, "source_files_json", ()) or ())
        if not files:
            return "—"
        first = files[0] if isinstance(files[0], dict) else {}
        return str(first.get("original_filename") or first.get("stored_filename") or "—")

    def set_dataset(
        self,
        row,
        holes: tuple[Drillhole, ...] = (),
        *,
        design_revision_current: bool | None = None,
    ):
        self.clear_status()
        self.show_helper("")
        if row is None:
            self.source.setText(tr("No dataset loaded"))
            self.button.setText(tr("Import"))
            self._set_metrics([])
            self.show_helper(
                "Import design drillholes to calculate drilling values automatically."
                if self.dataset_kind == "design"
                else "Optional. Import as-drilled holes to populate Execution fact automatically."
            )
            return
        if design_revision_current is None:
            design_revision_current = bool(getattr(row, "design_revision_current", True))
        self.button.setText(tr("Update"))
        source_text = (
            f"R{row.revision_number} · {str(row.source_format).upper()} · {self._source_name(row)}"
        )
        self.source.setText(source_text)
        summary = dict(row.summary_json or {})
        if self.dataset_kind == "design":
            values = [
                ("Holes", _value(summary.get("hole_count"))),
                ("Total drilling", _value(summary.get("total_drilling_length_m"), " m")),
                ("Average depth", _value(summary.get("mean_length_m"), " m")),
                ("Min / max depth", f"{_value(summary.get('min_length_m'))} / {_value(summary.get('max_length_m'))} m"),
                ("Mean inclination", _value(summary.get("mean_inclination_deg"), "°")),
                ("Mean hole azimuth", _value(summary.get("mean_azimuth_deg"), "°")),
            ]
            if self.contour and holes:
                contour = summarize_contour_drilling(holes)
                values.extend([
                    ("Contour length", _value(contour.line_length_m, " m")),
                    ("Mean spacing", _value(contour.mean_spacing_m, " m")),
                    ("Spacing min / max", f"{_value(contour.min_spacing_m)} / {_value(contour.max_spacing_m)} m"),
                    ("Alignment azimuth", _value(contour.alignment_azimuth_deg, "°")),
                ])
            elif holes:
                unassigned = sum(not hole.engineering_group_id for hole in holes)
                if unassigned:
                    self.show_status(
                        tr("%1 drillholes are not assigned to a drilling group. Use Assign holes in the group header.")
                        .replace("%1", str(unassigned)),
                        "warning",
                    )
            self._set_metrics(values)
            return

        matches = list(getattr(row, "matches_json", ()) or ())
        paired = [item for item in matches if item.get("design_hole_id") and item.get("actual_hole_id")]
        missing = sum(item.get("match_method") == "unmatched_design" for item in matches)
        additional = sum(item.get("match_method") == "unmatched_actual" for item in matches)
        low_confidence = sum(
            item.get("match_method") == "matched_geometry_low_confidence"
            for item in matches
        )
        collar = [float(item["collar_distance_xy_m"]) for item in paired if item.get("collar_distance_xy_m") is not None]
        toe = [float(item["toe_deviation_3d_m"]) for item in paired if item.get("toe_deviation_3d_m") is not None]
        if not design_revision_current:
            self.button.setText(tr("Re-import"))
            self.show_status(
                "Design drillholes changed after this fact was imported. Re-import the fact to refresh automatic comparison values.",
                "warning",
            )
        values = [
            ("Actual holes", _value(summary.get("hole_count"))),
            ("Matched", str(len(paired))),
            ("Low-confidence matches", str(low_confidence)),
            ("Missing design holes", str(missing)),
            ("Additional holes", str(additional)),
            ("Mean collar deviation", _value(mean(collar) if collar else None, " m")),
            ("Max collar deviation", _value(max(collar) if collar else None, " m")),
            ("Mean toe deviation", _value(mean(toe) if toe else None, " m")),
            ("Max toe deviation", _value(max(toe) if toe else None, " m")),
        ]
        self._set_metrics(values)
