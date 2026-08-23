"""Map verified Datamine Studio wireframe pairs to canonical triangle surfaces."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from math import isfinite
from pathlib import Path
from typing import Any

from domain.geometry.surfaces import SurfaceTriangle, SurfaceVertex, TriangleSurface
from infrastructure.datamine.dmfile import DispatchFactory, read_datamine_table


class DatamineWireframeImportError(ValueError):
    pass


@dataclass(frozen=True)
class DatamineWireframeImportResult:
    surface: TriangleSurface
    triangle_path: Path
    point_path: Path


_REQUIRED_TRIANGLE_FIELDS = ("PID1", "PID2", "PID3")
_REQUIRED_POINT_FIELDS = ("PID", "XP", "YP", "ZP")


def _normalized_id(value: Any) -> str:
    if value is None:
        return ""
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


def _finite_coordinate(value: Any, field: str, row_number: int) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise DatamineWireframeImportError(
            f"Invalid {field} coordinate at point row {row_number}: {value!r}."
        ) from exc
    if not isfinite(number):
        raise DatamineWireframeImportError(
            f"Non-finite {field} coordinate at point row {row_number}."
        )
    return number


def _field_map(fields: tuple[str, ...], required: tuple[str, ...], description: str) -> dict[str, str]:
    by_upper = {field.upper(): field for field in fields}
    missing = [name for name in required if name not in by_upper]
    if missing:
        raise DatamineWireframeImportError(
            f"Datamine {description} file is missing required fields: {', '.join(missing)}."
        )
    return {name: by_upper[name] for name in required}


def _pair_candidates(selected: Path, partner_suffix: str) -> list[Path]:
    stem = selected.stem
    prefix = stem[:-2]
    candidates = []
    for extension in (selected.suffix.lower(), ".dmx", ".dm"):
        candidate = selected.with_name(f"{prefix}{partner_suffix}{extension}")
        if candidate not in candidates and candidate.is_file():
            candidates.append(candidate)
    return candidates


def resolve_wireframe_pair(path: str | Path) -> tuple[Path, Path]:
    """Resolve a normal ``*tr.dm[x]`` + ``*pt.dm[x]`` Datamine wireframe pair."""
    selected = Path(path)
    if selected.suffix.lower() not in {".dm", ".dmx"}:
        raise DatamineWireframeImportError("Datamine wireframe files must use .dm or .dmx")
    lower_stem = selected.stem.lower()
    if lower_stem.endswith("tr"):
        triangle_path = selected
        candidates = _pair_candidates(selected, "pt")
        if len(candidates) != 1:
            raise DatamineWireframeImportError(
                "Could not resolve one matching Datamine *pt.dm[x] point file for the selected *tr.dm[x] file."
            )
        point_path = candidates[0]
    elif lower_stem.endswith("pt"):
        point_path = selected
        candidates = _pair_candidates(selected, "tr")
        if len(candidates) != 1:
            raise DatamineWireframeImportError(
                "Could not resolve one matching Datamine *tr.dm[x] triangle file for the selected *pt.dm[x] file."
            )
        triangle_path = candidates[0]
    else:
        raise DatamineWireframeImportError(
            "Select a Datamine wireframe file named *tr.dm[x] or *pt.dm[x]."
        )
    if not triangle_path.is_file() or not point_path.is_file():
        raise DatamineWireframeImportError("Datamine wireframe pair is incomplete")
    return triangle_path, point_path


def import_datamine_wireframe(
    path: str | Path,
    *,
    dispatch_factory: DispatchFactory | None = None,
) -> DatamineWireframeImportResult:
    triangle_path, point_path = resolve_wireframe_pair(path)
    point_table = read_datamine_table(point_path, dispatch_factory=dispatch_factory)
    triangle_table = read_datamine_table(triangle_path, dispatch_factory=dispatch_factory)

    point_fields = _field_map(point_table.fields, _REQUIRED_POINT_FIELDS, "point")
    triangle_fields = _field_map(triangle_table.fields, _REQUIRED_TRIANGLE_FIELDS, "triangle")

    vertices: list[SurfaceVertex] = []
    point_index: dict[str, int] = {}
    for row_number, values in enumerate(point_table.rows, start=1):
        row = dict(zip(point_table.fields, values))
        pid = _normalized_id(row.get(point_fields["PID"]))
        if not pid:
            raise DatamineWireframeImportError(f"Empty PID at point row {row_number}.")
        if pid in point_index:
            raise DatamineWireframeImportError(f"Duplicate PID {pid!r} in Datamine point file.")
        point_index[pid] = len(vertices)
        vertices.append(
            SurfaceVertex(
                _finite_coordinate(row.get(point_fields["XP"]), point_fields["XP"], row_number),
                _finite_coordinate(row.get(point_fields["YP"]), point_fields["YP"], row_number),
                _finite_coordinate(row.get(point_fields["ZP"]), point_fields["ZP"], row_number),
            )
        )

    triangles: list[SurfaceTriangle] = []
    for row_number, values in enumerate(triangle_table.rows, start=1):
        row = dict(zip(triangle_table.fields, values))
        pids = tuple(_normalized_id(row.get(triangle_fields[name])) for name in _REQUIRED_TRIANGLE_FIELDS)
        if not all(pids):
            raise DatamineWireframeImportError(f"Empty triangle point reference at triangle row {row_number}.")
        missing = [pid for pid in pids if pid not in point_index]
        if missing:
            raise DatamineWireframeImportError(
                f"Triangle row {row_number} references missing PID(s): {', '.join(missing)}."
            )
        source_id = _normalized_id(row.get("TRIANGLE")) if "TRIANGLE" in row else str(row_number)
        source_attributes = {
            field_name: value
            for field_name, value in row.items()
            if field_name.upper() not in _REQUIRED_TRIANGLE_FIELDS and value is not None
        }
        try:
            triangle = SurfaceTriangle(
                tuple(point_index[pid] for pid in pids),
                source_id=source_id or str(row_number),
                source_attributes=source_attributes,
            )
        except ValueError as exc:
            raise DatamineWireframeImportError(
                f"Invalid Datamine triangle at row {row_number}: {exc}"
            ) from exc
        triangles.append(triangle)

    try:
        surface = TriangleSurface(
            vertices=tuple(vertices),
            triangles=tuple(triangles),
            source_files=(triangle_path.name, point_path.name),
            source_attributes={
                "format": triangle_path.suffix.lstrip(".").upper(),
                "triangle_fields": triangle_table.fields,
                "point_fields": point_table.fields,
            },
        )
    except ValueError as exc:
        raise DatamineWireframeImportError(f"Invalid Datamine wireframe: {exc}") from exc

    return DatamineWireframeImportResult(surface, triangle_path, point_path)
