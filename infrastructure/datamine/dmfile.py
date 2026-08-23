"""Low-level, lazy access to Datamine DmFile tables.

This module intentionally does not map Datamine fields to SlopeForge geometry.
It only exposes enough schema and row data to inspect real .dm/.dmx files and
build verified adapters from observed file structures.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

DMFILE_PROG_ID = "DmFile.DmTable"
_SUPPORTED_EXTENSIONS = {".dm", ".dmx"}


class DatamineUnavailableError(RuntimeError):
    """Raised when the optional Datamine COM component cannot be created."""


class DatamineReadError(ValueError):
    """Raised when a Datamine file cannot be inspected through DmFile."""


@dataclass(frozen=True)
class DatamineTablePreview:
    file_name: str
    fields: tuple[str, ...]
    row_count: int
    rows: tuple[tuple[Any, ...], ...]
    default_datamine_format: str | None = None


DispatchFactory = Callable[[str], Any]


def _default_dispatch(prog_id: str) -> Any:
    try:
        import win32com.client
    except ImportError as exc:
        raise DatamineUnavailableError(
            "Datamine DM/DMX access requires pywin32 on Windows. "
            "Install the optional Datamine requirements and ensure Datamine/DmFile is installed."
        ) from exc

    try:
        return win32com.client.Dispatch(prog_id)
    except Exception as exc:  # pywintypes.com_error is optional with pywin32
        raise DatamineUnavailableError(
            f"Could not create Datamine COM component {prog_id!r}. "
            "Ensure a compatible Datamine Studio/DmFile installation is registered on this Windows machine."
        ) from exc


def _is_absent(value: Any, absent_value: Any) -> bool:
    if absent_value is None:
        return False
    try:
        return bool(value == absent_value)
    except Exception:
        return False


def read_datamine_table_preview(
    path: str | Path,
    *,
    row_limit: int = 5,
    dispatch_factory: DispatchFactory | None = None,
) -> DatamineTablePreview:
    """Read field names and a bounded row preview from a Datamine table.

    The Datamine DmFile API is accessed through the registered COM ProgID
    ``DmFile.DmTable``. The function deliberately performs no semantic field
    mapping: callers can inspect real files first and build geometry mappings
    from observed schemas rather than undocumented assumptions.
    """
    source_path = Path(path)
    if source_path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
        raise DatamineReadError(
            f"Unsupported Datamine file extension {source_path.suffix or '(none)'!r}. Use .dm or .dmx."
        )
    if not source_path.is_file():
        raise DatamineReadError(f"Datamine file does not exist: {source_path}")
    if row_limit < 0:
        raise DatamineReadError("row_limit must be zero or greater")

    dispatch = dispatch_factory or _default_dispatch
    try:
        table = dispatch(DMFILE_PROG_ID)
    except DatamineUnavailableError:
        raise
    except Exception as exc:
        raise DatamineUnavailableError(
            f"Could not create Datamine COM component {DMFILE_PROG_ID!r}: {exc}"
        ) from exc

    try:
        default_format = getattr(table, "DefaultDatamineFormat", None)
        table.Open(str(source_path.resolve()), 0)
        schema = table.Schema
        field_count = int(schema.FieldCount)
        fields = tuple(str(schema.GetFieldName(index)) for index in range(1, field_count + 1))
        row_count = int(table.GetRowCount())
        absent_value = getattr(schema, "SpecialValueAbsent", None)

        preview_count = min(row_count, row_limit)
        rows: list[tuple[Any, ...]] = []
        for row_index in range(preview_count):
            values = []
            for column_index in range(1, field_count + 1):
                value = table.GetColumn(column_index)
                values.append(None if _is_absent(value, absent_value) else value)
            rows.append(tuple(values))
            if row_index + 1 < preview_count:
                table.GetNextRow()
    except DatamineUnavailableError:
        raise
    except Exception as exc:
        raise DatamineReadError(f"Could not read Datamine file {source_path.name!r}: {exc}") from exc

    return DatamineTablePreview(
        file_name=source_path.name,
        fields=fields,
        row_count=row_count,
        rows=tuple(rows),
        default_datamine_format=str(default_format) if default_format is not None else None,
    )
