from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infrastructure.datamine.dmfile import (  # noqa: E402
    DatamineReadError,
    DatamineUnavailableError,
    read_datamine_table_preview,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect the schema and a few rows from a Datamine .dm/.dmx file via DmFile COM."
    )
    parser.add_argument("path", type=Path, help="Datamine .dm or .dmx file")
    parser.add_argument("--rows", type=int, default=5, help="Maximum rows to preview (default: 5)")
    args = parser.parse_args()

    try:
        preview = read_datamine_table_preview(args.path, row_limit=args.rows)
    except (DatamineUnavailableError, DatamineReadError) as exc:
        raise SystemExit(f"Datamine probe failed: {exc}") from exc

    payload = {
        "file_name": preview.file_name,
        "default_datamine_format": preview.default_datamine_format,
        "row_count": preview.row_count,
        "fields": list(preview.fields),
        "rows": [list(row) for row in preview.rows],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
