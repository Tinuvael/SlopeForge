from pathlib import Path
import os
import runpy

import pytest


CONFTEST = Path(__file__).with_name("conftest.py")


def _run_conftest_env_loading(monkeypatch, tmp_path, *, real_url=None, legacy_url=None):
    pytest.importorskip("dotenv", reason="python-dotenv is not installed")
    file_url = "postgresql+psycopg://local:file@localhost:5432/slopeforge_test"
    (tmp_path / ".env.test").write_text(
        f"TEST_DATABASE_URL={file_url}\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("SLOPEFORGE_TEST_DATABASE_URL", raising=False)
    if legacy_url is not None:
        monkeypatch.setenv("SLOPEFORGE_TEST_DATABASE_URL", legacy_url)
    if real_url is not None:
        monkeypatch.setenv("TEST_DATABASE_URL", real_url)
    runpy.run_path(str(CONFTEST))
    return file_url


def test_conftest_loads_test_database_url_from_dot_env_test(monkeypatch, tmp_path):
    file_url = _run_conftest_env_loading(monkeypatch, tmp_path)

    assert os.environ["TEST_DATABASE_URL"] == file_url
    assert "SLOPEFORGE_TEST_DATABASE_URL" not in os.environ


def test_real_test_database_url_takes_precedence_over_dot_env_test(monkeypatch, tmp_path):
    real_url = "postgresql+psycopg://real:env@localhost:5432/real_test"
    _run_conftest_env_loading(monkeypatch, tmp_path, real_url=real_url)

    assert os.environ["TEST_DATABASE_URL"] == real_url
    assert "SLOPEFORGE_TEST_DATABASE_URL" not in os.environ


def test_legacy_database_url_is_ignored(monkeypatch, tmp_path):
    legacy_url = "postgresql+psycopg://legacy:env@localhost:5432/legacy_test"
    file_url = _run_conftest_env_loading(
        monkeypatch, tmp_path, legacy_url=legacy_url,
    )

    assert os.environ["TEST_DATABASE_URL"] == file_url
    assert os.environ["SLOPEFORGE_TEST_DATABASE_URL"] == legacy_url
