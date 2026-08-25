from pathlib import Path

import pytest

from tools.validate_windows_payload import require_payload


REQUIRED = (
    "SlopeForge.exe",
    "SlopeForgeUpdater.exe",
    "_internal/translations/slopeforge_ru.ts",
    "_internal/alembic.ini",
    "_internal/alembic/env.py",
    "_internal/alembic/versions/0001_slopeforge_1.py",
    "_internal/alembic/schema_v1/core.py",
    "_internal/alembic/schema_v1/project_surfaces.py",
    "_internal/alembic/schema_v1/drillhole_datasets.py",
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


def test_missing_release_1_schema_component_is_rejected(tmp_path):
    make_payload(tmp_path)
    missing = tmp_path / "_internal/alembic/schema_v1/core.py"
    missing.unlink()

    with pytest.raises(SystemExit, match=r"schema_v1[\\/]core\.py"):
        require_payload(tmp_path)


def test_pre_1_0_baseline_is_not_required(tmp_path):
    make_payload(tmp_path)
    assert not (tmp_path / "_internal/alembic/versions/0001_mvp_baseline.py").exists()
    require_payload(tmp_path)


@pytest.mark.parametrize("forbidden", [".env", ".env.test", "tests/test_app.py"])
def test_development_files_are_rejected(tmp_path, forbidden):
    make_payload(tmp_path)
    path = tmp_path / forbidden
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("secret", encoding="utf-8")
    with pytest.raises(SystemExit, match="forbidden"):
        require_payload(tmp_path)
