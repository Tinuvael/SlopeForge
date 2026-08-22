import pytest

from tests.postgres_test_database import is_disposable_test_database


@pytest.mark.parametrize("database_name", (
    "slopeforge_test",
    "test_slopeforge",
    "slopeforge-test",
    "test-slopeforge",
))
def test_explicit_test_database_token_is_accepted(database_name):
    url = f"postgresql+psycopg://user:password@localhost:5432/{database_name}"
    assert is_disposable_test_database(url)


@pytest.mark.parametrize("database_name", (
    "slopeforge",
    "contest",
    "latest",
    "production_testing_backup",
    "productiontest",
    "testproduction",
))
def test_embedded_test_text_is_rejected(database_name):
    url = f"postgresql+psycopg://user:password@localhost:5432/{database_name}"
    assert not is_disposable_test_database(url)
