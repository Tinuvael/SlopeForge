"""Low-level, lazy access to Datamine DmFile tables.

This module deliberately does not assign engineering meaning to Datamine
fields. It exposes schema/row data so format-specific infrastructure adapters
can map verified source fields into SlopeForge canonical geometry.
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
    """Raised when a Datamine file cannot be read through DmFile."""


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


def _validate_source_path(path: str | Path) -> Path:
    source_path = Path(path)
    if source_path.suffix.lower() not in _SUPPORTED_EXTENSIONS:
        raise DatamineReadError(
            f"Unsupported Datamine file extension {source_path.suffix or '(none)'!r}. Use .dm or .dmx."
        )
    if not source_path.is_file():
        raise DatamineReadError(f"Datamine file does not exist: {source_path}")
    return source_path


def read_datamine_table(
    path: str | Path,
    *,
    row_limit: int | None = None,
    dispatch_factory: DispatchFactory | None = None,
) -> DatamineTablePreview:
    """Read schema and rows from a Datamine table through ``DmFile.DmTable``.

    ``row_limit=None`` reads the complete table. A non-negative limit is useful
    for diagnostics/probes. No semantic field mapping is performed here.
    """
    source_path = _validate_source_path(path)
    if row_limit is not None and row_limit < 0:
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

        read_count = row_count if row_limit is None else min(row_count, row_limit)
        rows: list[tuple[Any, ...]] = []
        for row_index in range(read_count):
            values = []
            for column_index in range(1, field_count + 1):
                value = table.GetColumn(column_index)
                values.append(None if _is_absent(value, absent_value) else value)
            rows.append(tuple(values))
            if row_index + 1 < read_count:
                table.GetNextRow()
    except DatamineUnavailableError:
        raise
    except Exception as exc:
        raise DatamineReadError(f"Could not read Datamine file {source_path.name!r}: {exc}") from exc
    finally:
        close = getattr(table, "Close", None)
        if callable(close):
            try:
                close()
            except Exception:
                # Closing is best-effort; a successfully read table should not
                # be reported as unreadable because a COM implementation has a
                # different/unsupported Close contract.
                pass

    return DatamineTablePreview(
        file_name=source_path.name,
        fields=fields,
        row_count=row_count,
        rows=tuple(rows),
        default_datamine_format=str(default_format) if default_format is not None else None,
    )


def read_datamine_table_preview(
    path: str | Path,
    *,
    row_limit: int = 5,
    dispatch_factory: DispatchFactory | None = None,
) -> DatamineTablePreview:
    """Read a bounded schema/row preview from a Datamine table."""
    return read_datamine_table(
        path,
        row_limit=row_limit,
        dispatch_factory=dispatch_factory,
    )
