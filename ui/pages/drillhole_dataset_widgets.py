from __future__ import annotations

from statistics import mean

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton

from app.localization import tr
from domain.blasting.contour_drilling import summarize_contour_drilling
from domain.blasting.drillholes import Drillhole
from ui.widgets.design_system import CardFrame, set_button_role


def _value(value, suffix="", digits=2):
    if value is None:
        return "—"
    if isinstance(value, int):
        return str(value)
    text = f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    return f"{text}{suffix}"


class DrillholeDatasetCard(CardFrame):
    import_requested = Signal(str)

    def __init__(self, dataset_kind: str, *, contour=False, read_only=False, parent=None):
        super().__init__()
        if parent is not None:
            self.setParent(parent)
        self.dataset_kind = dataset_kind
        self.contour = bool(contour)
        self.read_only = bool(read_only)
        self.setObjectName("EngineeringCard")
        self.layout.setContentsMargins(12, 10, 12, 10)
        self.layout.setSpacing(7)

        header = QHBoxLayout()
        title = tr("Design drillholes") if dataset_kind == "design" else tr("As-drilled holes")
        self.title = QLabel(title)
        self.title.setObjectName("EngineeringSectionTitle")
        self.source = QLabel(tr("No dataset loaded"))
        self.source.setObjectName("MutedText")
        self.button = set_button_role(QPushButton(tr("Import")), "secondary")
        self.button.setEnabled(not self.read_only)
        self.button.clicked.connect(lambda: self.import_requested.emit(self.dataset_kind))
        header.addWidget(self.title)
        header.addWidget(self.source, 1)
        header.addWidget(self.button)
        self.layout.addLayout(header)

        self.metrics = QGridLayout()
        self.metrics.setHorizontalSpacing(18)
        self.metrics.setVerticalSpacing(2)
        self._labels = {}
        self.layout.addLayout(self.metrics)

    def _set_metrics(self, values):
        while self.metrics.count():
            item = self.metrics.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._labels = {}
        for index, (caption, value) in enumerate(values):
            column = index % 6
            row = (index // 6) * 2
            label = QLabel(tr(caption))
            label.setObjectName("MutedText")
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
        if row is None:
            self.source.setText(tr("No dataset loaded"))
            self.button.setText(tr("Import"))
            self._set_metrics([])
            return
        if design_revision_current is None:
            design_revision_current = bool(getattr(row, "design_revision_current", True))
        self.button.setText(tr("Update"))
        source_text = (
            f"R{row.revision_number} · {str(row.source_format).upper()} · {self._source_name(row)}"
        )
        if self.dataset_kind == "actual" and not design_revision_current:
            source_text += f" · {tr('Design changed')}"
            self.button.setText(tr("Re-import"))
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
        values = [
            ("Design comparison", tr("Current") if design_revision_current else tr("Outdated — re-import fact")),
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
