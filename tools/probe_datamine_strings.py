from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from infrastructure.datamine.dmfile import DatamineReadError, DatamineUnavailableError  # noqa: E402
from infrastructure.datamine.strings import (  # noqa: E402
    DatamineStringImportError,
    import_datamine_strings,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import a Datamine string file into SlopeForge canonical lines and print a compact JSON preview."
    )
    parser.add_argument("path", type=Path, help="Datamine .dm or .dmx string file")
    parser.add_argument("--lines", type=int, default=10, help="Maximum canonical lines to print")
    args = parser.parse_args()

    try:
        result = import_datamine_strings(args.path)
    except (DatamineUnavailableError, DatamineReadError, DatamineStringImportError) as exc:
        raise SystemExit(f"Datamine string probe failed: {exc}") from exc

    payload = {
        "summary": {
            "file_name": result.summary.file_name,
            "format": result.summary.format,
            "total_rows": result.summary.total_rows,
            "line_count": result.summary.line_count,
            "line_id_field": result.summary.line_id_field,
            "point_order_field": result.summary.point_order_field,
            "colours": list(result.summary.colours),
        },
        "lines": [
            {
                "source_id": line.source_id,
                "point_count": len(line.points),
                "first_point": line.points[0].to_dict() if line.points else None,
                "last_point": line.points[-1].to_dict() if line.points else None,
                "source_attributes": line.source_attributes,
                "z_min": line.z_min,
                "z_max": line.z_max,
                "is_horizontal": line.is_horizontal,
            }
            for line in result.lines[: max(args.lines, 0)]
        ],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
