from __future__ import annotations

import os

import pytest
from sqlalchemy.engine import make_url


# Older focused PostgreSQL modules used a second environment-variable name.
# Keep one documented test database sufficient for the complete suite.
_test_database_url = os.getenv("TEST_DATABASE_URL") or os.getenv("SLOPEFORGE_TEST_DATABASE_URL")
if _test_database_url:
    os.environ.setdefault("TEST_DATABASE_URL", _test_database_url)
    os.environ.setdefault("SLOPEFORGE_TEST_DATABASE_URL", _test_database_url)


def _remove_installed_slopeforge_translator() -> None:
    """Do not let a Russian-localization test leak into later UI tests."""
    try:
        from PySide6.QtCore import QCoreApplication
        import app.localization as localization
    except ImportError:
        return
    app = QCoreApplication.instance()
    if app is not None and localization._translator is not None:
        app.removeTranslator(localization._translator)
    localization._translator = None


@pytest.fixture(autouse=True)
def isolate_installed_translator():
    """Every test starts and ends with canonical English presentation state."""
    _remove_installed_slopeforge_translator()
    yield
    _remove_installed_slopeforge_translator()


@pytest.fixture(scope="session", autouse=True)
def reset_disposable_postgresql_test_database(tmp_path_factory):
    """Start integration tests from a clean Alembic head on the dedicated test DB.

    The suite is intentionally destructive only when an explicitly configured
    database name contains ``test``.  This prevents leftovers from a previous
    pytest run from changing row counts or violating globally unique logical IDs.
    """
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        yield
        return
    database_name = (make_url(url).database or "").lower()
    if "test" not in database_name:
        pytest.fail(
            "Refusing destructive PostgreSQL test reset outside a database whose name contains 'test'",
            pytrace=False,
        )

    from alembic import command
    from alembic.config import Config

    old_database = os.environ.get("DATABASE_URL")
    old_storage = os.environ.get("STORAGE_ROOT")
    os.environ["DATABASE_URL"] = url
    os.environ["STORAGE_ROOT"] = str(tmp_path_factory.mktemp("suite-storage"))
    config = Config("alembic.ini")
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
    finally:
        if old_database is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_database
        if old_storage is None:
            os.environ.pop("STORAGE_ROOT", None)
        else:
            os.environ["STORAGE_ROOT"] = old_storage

    yield
