from __future__ import annotations

import re

from sqlalchemy.engine import make_url


_TEST_DATABASE_TOKEN = re.compile(r"(?:^|[_-])test(?:$|[_-])", re.IGNORECASE)


def is_disposable_test_database(url: str) -> bool:
    """Return whether the URL names an explicitly marked disposable test DB."""
    database_name = make_url(url).database or ""
    return _TEST_DATABASE_TOKEN.search(database_name) is not None
