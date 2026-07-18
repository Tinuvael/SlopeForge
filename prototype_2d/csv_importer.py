from __future__ import annotations

import csv
from collections import OrderedDict
from pathlib import Path

from .models import DatamineLine, DataminePoint

REQUIRED_FIELDS = ("XP", "YP", "ZP", "PTN")
OPTIONAL_FIELDS = ("PVALUE", "TYPE")


class DatamineCsvError(ValueError):
    pass


def detect_columns(headers: list[str]) -> dict[str, str]:
    by_upper = {header.upper(): header for header in headers}
    return {field: by_upper[field] for field in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS) if field in by_upper}


def missing_required(mapping: dict[str, str]) -> list[str]:
    return [field for field in REQUIRED_FIELDS if not mapping.get(field)]


def import_datamine_csv(path: str | Path, column_mapping: dict[str, str] | None = None) -> list[DatamineLine]:
    csv_path = Path(path)
    try:
        with csv_path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = reader.fieldnames or []
            mapping = column_mapping or detect_columns(headers)
            missing = missing_required(mapping)
            if missing:
                raise DatamineCsvError("Не сопоставлены обязательные колонки: " + ", ".join(missing))
            groups: OrderedDict[str, list[DataminePoint]] = OrderedDict()
            types: dict[str, str | None] = {}
            for source_row_number, row in enumerate(reader, start=2):
                try:
                    ptn = str(row[mapping["PTN"]])
                    point = DataminePoint(
                        x=float(row[mapping["XP"]]),
                        y=float(row[mapping["YP"]]),
                        z=float(row[mapping["ZP"]]),
                        source_row_number=source_row_number,
                        pvalue=row.get(mapping.get("PVALUE", "")) or None,
                        extra_values={key: value for key, value in row.items() if key not in mapping.values()},
                    )
                except (KeyError, TypeError, ValueError) as exc:
                    raise DatamineCsvError(f"Ошибка в строке {source_row_number}: проверьте XP, YP, ZP и PTN") from exc
                groups.setdefault(ptn, []).append(point)
                if ptn not in types:
                    type_column = mapping.get("TYPE")
                    types[ptn] = row.get(type_column) if type_column else None
    except OSError as exc:
        raise DatamineCsvError(f"Не удалось прочитать CSV: {exc}") from exc

    lines: list[DatamineLine] = []
    for order, (source_id, points) in enumerate(groups.items(), start=1):
        source_type = types.get(source_id) or None
        lines.append(DatamineLine(source_id, points, points[0].z, source_type, source_type, str(csv_path), order))
    return lines
