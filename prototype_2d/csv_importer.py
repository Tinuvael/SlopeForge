from __future__ import annotations

import csv
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import DatamineLine, DataminePoint

LOGICAL_FIELDS = ("X", "Y", "Z", "LINE_ID", "POINT_ORDER", "SOURCE_TYPE", "PVALUE")
REQUIRED_FIELDS = ("X", "Y", "Z", "LINE_ID")
FIELD_LABELS = {
    "X": "X coordinate",
    "Y": "Y coordinate",
    "Z": "Z coordinate",
    "LINE_ID": "Line ID",
    "POINT_ORDER": "Point order",
    "SOURCE_TYPE": "Source type",
    "PVALUE": "PValue",
}
COLUMN_CANDIDATES = {
    "X": ("XP", "X"),
    "Y": ("YP", "Y"),
    "Z": ("ZP", "Z"),
    "LINE_ID": ("SID", "LINE_ID", "STRING", "STRING_ID", "POLYLINE_ID", "PTN"),
    "POINT_ORDER": ("PTN", "PID", "POINT_ORDER", "POINT_ID"),
    "SOURCE_TYPE": ("TYPE",),
    "PVALUE": ("PVALUE",),
}
DELIMITERS = {"Auto": None, "comma": ",", "semicolon": ";", "tab": "\t"}


class DatamineCsvError(ValueError):
    pass


@dataclass
class ImportSummary:
    file_name: str
    delimiter: str
    encoding: str
    total_rows: int = 0
    valid_points: int = 0
    skipped_rows: int = 0
    failed_rows: int = 0
    line_count: int = 0
    column_mapping: dict[str, str] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        mapping = ", ".join(f"{key}={value}" for key, value in self.column_mapping.items())
        delimiter_name = {",": "comma", ";": "semicolon", "\t": "tab"}.get(self.delimiter, self.delimiter)
        lines = [
            f"Файл: {self.file_name}",
            f"Разделитель: {delimiter_name}",
            f"Кодировка: {self.encoding}",
            f"Строк всего: {self.total_rows}",
            f"Валидных точек: {self.valid_points}",
            f"Линий: {self.line_count}",
            f"Пропущено строк: {self.skipped_rows}",
            f"Строк с ошибками: {self.failed_rows}",
            f"Колонки: {mapping}",
        ]
        if self.errors:
            lines.append("Первые ошибки:")
            lines.extend(self.errors[:10])
        return "\n".join(lines)


@dataclass
class ImportResult:
    lines: list[DatamineLine]
    summary: ImportSummary


def read_text(path: Path) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return path.read_text(encoding=encoding), encoding
        except UnicodeDecodeError:
            continue
    raise DatamineCsvError("Не удалось прочитать файл как UTF-8. Сохраните CSV в UTF-8 или UTF-8 BOM.")


def sniff_delimiter(sample: str, delimiter_choice: str = "Auto") -> str:
    if delimiter_choice != "Auto":
        return DELIMITERS.get(delimiter_choice, delimiter_choice) or ","
    try:
        return csv.Sniffer().sniff(sample[:8192], delimiters=",;\t").delimiter
    except csv.Error:
        counts = {delimiter: sample.count(delimiter) for delimiter in (",", ";", "\t")}
        return max(counts, key=counts.get) if any(counts.values()) else ","


def detect_columns(headers: list[str]) -> dict[str, str]:
    by_upper = {header.strip().upper(): header for header in headers}
    mapping: dict[str, str] = {}
    for field, candidates in COLUMN_CANDIDATES.items():
        for candidate in candidates:
            if candidate in by_upper:
                mapping[field] = by_upper[candidate]
                break
    return mapping


def missing_required(mapping: dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if not mapping.get(field)]


def _sort_key(item: tuple[int, DataminePoint, Any]) -> tuple[float, int]:
    row_order, _point, point_order = item
    if point_order is None or point_order == "":
        return float(row_order), row_order
    try:
        return float(point_order), row_order
    except (TypeError, ValueError):
        return float(row_order), row_order


def import_datamine_csv(
    path: str | Path,
    column_mapping: dict[str, str] | None = None,
    delimiter_choice: str = "Auto",
) -> ImportResult:
    csv_path = Path(path)
    try:
        text, encoding = read_text(csv_path)
    except OSError as exc:
        raise DatamineCsvError(f"Не удалось прочитать CSV: {exc}") from exc
    delimiter = sniff_delimiter(text, delimiter_choice)
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    headers = reader.fieldnames or []
    mapping = column_mapping or detect_columns(headers)
    missing = missing_required(mapping)
    if missing:
        labels = [FIELD_LABELS[field] for field in missing]
        raise DatamineCsvError("Не сопоставлены обязательные колонки: " + ", ".join(labels))

    summary = ImportSummary(csv_path.name, delimiter, encoding, column_mapping=dict(mapping))
    groups: OrderedDict[str, list[tuple[int, DataminePoint, Any]]] = OrderedDict()
    types: dict[str, str | None] = {}
    for source_row_number, row in enumerate(reader, start=2):
        summary.total_rows += 1
        if not any((value or "").strip() for value in row.values() if value is not None):
            summary.skipped_rows += 1
            continue
        try:
            line_id = str(row[mapping["LINE_ID"]]).strip()
            if not line_id:
                raise ValueError("empty line id")
            point = DataminePoint(
                x=float(row[mapping["X"]]),
                y=float(row[mapping["Y"]]),
                z=float(row[mapping["Z"]]),
                source_row_number=source_row_number,
                pvalue=row.get(mapping.get("PVALUE", "")) or None,
                extra_values={key: value for key, value in row.items() if key not in mapping.values()},
            )
        except (KeyError, TypeError, ValueError) as exc:
            summary.failed_rows += 1
            if len(summary.errors) < 10:
                summary.errors.append(f"Строка {source_row_number}: проверьте X, Y, Z и Line ID ({exc})")
            continue
        point_order = row.get(mapping["POINT_ORDER"]) if mapping.get("POINT_ORDER") else None
        groups.setdefault(line_id, []).append((source_row_number, point, point_order))
        if line_id not in types:
            type_column = mapping.get("SOURCE_TYPE")
            types[line_id] = row.get(type_column) if type_column else None
        summary.valid_points += 1

    lines: list[DatamineLine] = []
    for order, (source_id, items) in enumerate(groups.items(), start=1):
        points = [point for _row, point, _point_order in sorted(items, key=_sort_key)]
        source_type = types.get(source_id) or None
        lines.append(DatamineLine(source_id, points, None, source_type, source_type, str(csv_path), order))
    summary.line_count = len(lines)
    return ImportResult(lines, summary)
