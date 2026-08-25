from pathlib import Path

import pytest

from tools.validate_windows_payload import require_payload


REQUIRED_RELEASE_1_FILES = (
    "SlopeForge.exe",
    "_internal/translations/slopeforge_ru.ts",
    "_internal/alembic.ini",
    "_internal/alembic/env.py",
    "_internal/alembic/versions/0001_slopeforge_1.py",
    "_internal/alembic/schema_v1/core.py",
    "_internal/alembic/schema_v1/project_surfaces.py",
    "_internal/alembic/schema_v1/drillhole_datasets.py",
    "_internal/app/icons/slopeforge_icon.ico",
)


def _write_payload(root: Path) -> None:
    for relative in REQUIRED_RELEASE_1_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"payload")


def test_release_1_payload_accepts_current_alembic_baseline(tmp_path: Path) -> None:
    _write_payload(tmp_path)
    require_payload(tmp_path)


def test_release_1_payload_rejects_missing_schema_component(tmp_path: Path) -> None:
    _write_payload(tmp_path)
    missing = tmp_path / "_internal/alembic/schema_v1/core.py"
    missing.unlink()

    with pytest.raises(SystemExit, match=r"schema_v1[\\/]core\.py"):
        require_payload(tmp_path)


def test_payload_validator_no_longer_requires_pre_1_0_baseline(tmp_path: Path) -> None:
    _write_payload(tmp_path)
    assert not (tmp_path / "_internal/alembic/versions/0001_mvp_baseline.py").exists()
    require_payload(tmp_path)
