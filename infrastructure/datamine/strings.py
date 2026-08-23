"""Map verified Datamine string tables to canonical SlopeForge lines."""
from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from math import isfinite
from pathlib import Path
from typing import Any

from domain.geometry.types import DatamineLine, DataminePoint
from infrastructure.datamine.dmfile import DispatchFactory, read_datamine_table


class DatamineStringImportError(ValueError):
    pass


@dataclass(frozen=True)
class DatamineStringImportSummary:
    file_name: str
    format: str
    total_rows: int
    line_count: int
    fields: tuple[str, ...]
    line_id_field: str
    point_order_field: str
    colours: tuple[Any, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DatamineStringImportResult:
    lines: list[DatamineLine]
    summary: DatamineStringImportSummary


_FIELD_CANDIDATES = {
    "X": ("XP", "X"),
    "Y": ("YP", "Y"),
    "Z": ("ZP", "Z"),
    # SID is an explicit string id when present. Studio RM string files from
    # the verified sample use PVALUE instead, with PTN resetting per PVALUE.
    "LINE_ID": ("SID", "PVALUE"),
    "POINT_ORDER": ("PTN", "PID"),
    "COLOUR": ("COLOUR", "COLOR"),
}


def _normalized_id(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    try:
        number = Decimal(text)
    except InvalidOperation:
        return text
    if not number.is_finite():
        return text
    normalized = format(number.normalize(), "f")
    return "0" if normalized in {"-0", ""} else normalized


def _find_field(fields: tuple[str, ...], logical_name: str, *, required: bool = True) -> str | None:
    by_upper = {field.upper(): field for field in fields}
    for candidate in _FIELD_CANDIDATES[logical_name]:
        if candidate in by_upper:
            return by_upper[candidate]
    if required:
        expected = "/".join(_FIELD_CANDIDATES[logical_name])
        raise DatamineStringImportError(
            f"Datamine string file is missing required field for {logical_name}: expected {expected}."
        )
    return None


def _numeric_order(value: Any, *, line_id: str, row_number: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DatamineStringImportError(
            f"Invalid point order for line {line_id!r} at source row {row_number}: {value!r}."
        ) from exc
    if not isfinite(number):
        raise DatamineStringImportError(
            f"Non-finite point order for line {line_id!r} at source row {row_number}."
        )
    return number


def _finite_coordinate(value: Any, field: str, row_number: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DatamineStringImportError(
            f"Invalid {field} coordinate at source row {row_number}: {value!r}."
        ) from exc
    if not isfinite(number):
        raise DatamineStringImportError(
            f"Non-finite {field} coordinate at source row {row_number}."
        )
    return number


def _collapse_attribute(rows: list[dict[str, Any]], field: str) -> Any:
    values: list[Any] = []
    for row in rows:
        value = row.get(field)
        if value is None or value in values:
            continue
        values.append(value)
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    return tuple(values)


def import_datamine_strings(
    path: str | Path,
    *,
    dispatch_factory: DispatchFactory | None = None,
) -> DatamineStringImportResult:
    """Import a Datamine string `.dm`/`.dmx` file as canonical lines.

    Verified Studio RM schema uses `PVALUE` as the line grouping field and
    `PTN` as point order. `SID` remains preferred when a source file exposes an
    explicit SID. Raw source attributes are preserved without assigning them
    engineering meaning.
    """
    source_path = Path(path)
    table = read_datamine_table(source_path, dispatch_factory=dispatch_factory)
    fields = table.fields

    x_field = _find_field(fields, "X")
    y_field = _find_field(fields, "Y")
    z_field = _find_field(fields, "Z")
    line_id_field = _find_field(fields, "LINE_ID")
    point_order_field = _find_field(fields, "POINT_ORDER")
    colour_field = _find_field(fields, "COLOUR", required=False)

    groups: OrderedDict[str, list[tuple[float, int, DataminePoint, dict[str, Any]]]] = OrderedDict()
    for row_number, values in enumerate(table.rows, start=1):
        row = dict(zip(fields, values))
        line_id = _normalized_id(row.get(line_id_field))
        if not line_id:
            raise DatamineStringImportError(f"Empty {line_id_field} at source row {row_number}.")
        point_order = _numeric_order(row.get(point_order_field), line_id=line_id, row_number=row_number)
        point = DataminePoint(
            x=_finite_coordinate(row.get(x_field), x_field, row_number),
            y=_finite_coordinate(row.get(y_field), y_field, row_number),
            z=_finite_coordinate(row.get(z_field), z_field, row_number),
            source_row_number=row_number,
            pvalue=_normalized_id(row.get("PVALUE")) if "PVALUE" in row and row.get("PVALUE") is not None else None,
            extra_values={
                field_name: value
                for field_name, value in row.items()
                if field_name not in {x_field, y_field, z_field}
            },
        )
        groups.setdefault(line_id, []).append((point_order, row_number, point, row))

    lines: list[DatamineLine] = []
    all_colours: list[Any] = []
    for import_order, (line_id, items) in enumerate(groups.items(), start=1):
        point_orders = [order for order, _row_number, _point, _row in items]
        if len(point_orders) != len(set(point_orders)):
            raise DatamineStringImportError(
                f"Duplicate {point_order_field} values in Datamine line {line_id!r}; point order is ambiguous."
            )
        ordered = sorted(items, key=lambda item: (item[0], item[1]))
        line_rows = [row for _order, _row_number, _point, row in ordered]
        source_attributes: dict[str, Any] = {
            "datamine_line_id_field": line_id_field,
            "datamine_point_order_field": point_order_field,
        }
        for attribute_field in ("PVALUE", "COLOUR", "COLOR", "LSTYLE", "SYMBOL"):
            if attribute_field in fields:
                collapsed = _collapse_attribute(line_rows, attribute_field)
                if collapsed is not None:
                    source_attributes[attribute_field] = collapsed
        if colour_field is not None:
            colour = source_attributes.get(colour_field)
            if colour is not None:
                values_to_add = colour if isinstance(colour, tuple) else (colour,)
                for value in values_to_add:
                    if value not in all_colours:
                        all_colours.append(value)

        lines.append(
            DatamineLine(
                source_id=line_id,
                points=[point for _order, _row_number, point, _row in ordered],
                source_file=str(source_path),
                import_order=import_order,
                source_attributes=source_attributes,
            )
        )

    return DatamineStringImportResult(
        lines=lines,
        summary=DatamineStringImportSummary(
            file_name=source_path.name,
            format=source_path.suffix.lstrip(".").upper(),
            total_rows=table.row_count,
            line_count=len(lines),
            fields=fields,
            line_id_field=line_id_field,
            point_order_field=point_order_field,
            colours=tuple(all_colours),
        ),
    )
