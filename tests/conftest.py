from __future__ import annotations

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import make_url
from database.env import load_local_env


# Older focused PostgreSQL modules used a second environment-variable name.
# Keep one documented test database sufficient for the complete suite.
load_local_env(".env.test")
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


def _assert_disposable_database(url: str) -> None:
    database_name = (make_url(url).database or "").lower()
    if "test" not in database_name:
        pytest.fail(
            "Refusing destructive PostgreSQL test reset outside a database whose name contains 'test'",
            pytrace=False,
        )


def _truncate_test_data(url: str) -> None:
    """Remove all application rows while keeping the migrated schema intact."""
    _assert_disposable_database(url)
    engine = create_engine(url)
    try:
        with engine.begin() as connection:
            tables = [name for name in inspect(connection).get_table_names()
                      if name != "alembic_version"]
            if not tables:
                return
            quoted = ", ".join(connection.dialect.identifier_preparer.quote(name)
                               for name in tables)
            connection.exec_driver_sql(
                f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"
            )
    finally:
        engine.dispose()


def _is_postgresql_integration_item(item) -> bool:
    filename = Path(str(item.fspath)).name
    return ("postgres" in filename.lower()
            and filename != "test_alembic_postgresql_integration.py")


@pytest.fixture(scope="session", autouse=True)
def reset_disposable_postgresql_test_database(tmp_path_factory):
    """Start integration tests from a clean Alembic head on the dedicated test DB."""
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        yield
        return
    _assert_disposable_database(url)

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


@pytest.fixture(autouse=True)
def isolate_postgresql_integration_test_data(request):
    """Give each PostgreSQL integration test an empty data set before setup."""
    url = os.getenv("TEST_DATABASE_URL")
    if not url or not _is_postgresql_integration_item(request.node):
        yield
        return
    _truncate_test_data(url)
    yield


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_teardown(item, nextitem):  # noqa: ARG001
    """Clear data before legacy fixture finalizers start deleting parent rows.

    Several older integration fixtures manually delete Domain/Site rows but do not
    know about newer revision/link foreign keys.  The suite owns a disposable DB,
    so truncating application rows first is both safer and more representative than
    teaching every historical finalizer the current dependency graph.
    """
    url = os.getenv("TEST_DATABASE_URL")
    if url and _is_postgresql_integration_item(item):
        _truncate_test_data(url)
    yield
