from pathlib import Path

import pytest

from tools.validate_windows_payload import require_payload


REQUIRED = (
    "SlopeForge.exe",
    "_internal/translations/slopeforge_ru.ts",
    "_internal/alembic.ini",
    "_internal/alembic/env.py",
    "_internal/alembic/versions/0001_mvp_baseline.py",
    "_internal/app/icons/slopeforge_icon.ico",
)


def make_payload(root: Path) -> None:
    for relative in REQUIRED:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"payload")


def test_complete_payload_is_accepted(tmp_path):
    make_payload(tmp_path)
    require_payload(tmp_path)


@pytest.mark.parametrize("forbidden", [".env", ".env.test", "tests/test_app.py"])
def test_development_files_are_rejected(tmp_path, forbidden):
    make_payload(tmp_path)
    path = tmp_path / forbidden
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("secret", encoding="utf-8")
    with pytest.raises(SystemExit, match="forbidden"):
        require_payload(tmp_path)
