"""File-format dispatch for user-facing line geometry sources."""
from pathlib import Path
from typing import TypeAlias

from infrastructure.datamine.strings import DatamineStringImportResult, import_datamine_strings
from infrastructure.geometry_import.dxf import DxfImportResult, import_dxf_polylines

LineGeometryImportResult: TypeAlias = DxfImportResult | DatamineStringImportResult


class LineGeometryImportError(ValueError):
    pass


def import_line_geometry(path) -> LineGeometryImportResult:
    source_path = Path(path)
    extension = source_path.suffix.lower()
    if extension == ".dxf":
        return import_dxf_polylines(source_path)
    if extension in {".dm", ".dmx"}:
        return import_datamine_strings(source_path)
    raise LineGeometryImportError(
        f"Unsupported geometry file extension {source_path.suffix or '(none)'!r}. Use .dxf, .dm or .dmx."
    )
