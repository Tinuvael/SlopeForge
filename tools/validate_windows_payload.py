from __future__ import annotations

import argparse
from pathlib import Path


def require_payload(payload: Path) -> None:
    required = (
        Path("SlopeForge.exe"),
        Path("_internal/translations/slopeforge_ru.ts"),
        Path("_internal/alembic.ini"),
        Path("_internal/alembic/env.py"),
        Path("_internal/alembic/versions/0001_mvp_baseline.py"),
        Path("_internal/app/icons/slopeforge_icon.ico"),
    )
    missing = [str(item) for item in required if not (payload / item).is_file()]
    forbidden = [
        path.relative_to(payload)
        for path in payload.rglob("*")
        if path.name in {".env", ".env.test"} or "tests" in path.parts
    ]
    if missing or forbidden:
        details = []
        if missing:
            details.append("missing: " + ", ".join(missing))
        if forbidden:
            details.append("forbidden: " + ", ".join(map(str, forbidden)))
        raise SystemExit("Invalid Windows payload (" + "; ".join(details) + ")")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("payload", type=Path)
    args = parser.parse_args()
    require_payload(args.payload)


if __name__ == "__main__":
    main()
