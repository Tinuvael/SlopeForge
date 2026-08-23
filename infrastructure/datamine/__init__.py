"""Lazy Datamine interoperability adapters.

Datamine integration is optional. Importing this package must not require
Datamine components or pywin32 to be installed.
"""

from infrastructure.datamine.dmfile import (
    DMFILE_PROG_ID,
    DatamineReadError,
    DatamineTablePreview,
    DatamineUnavailableError,
    read_datamine_table_preview,
)

__all__ = [
    "DMFILE_PROG_ID",
    "DatamineReadError",
    "DatamineTablePreview",
    "DatamineUnavailableError",
    "read_datamine_table_preview",
]
