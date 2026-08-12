"""Explicit optimistic compare-and-swap inside a caller-owned transaction."""
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from application.errors import DomainConcurrencyConflict
from database.models import Domain


def guard_domain_versions(
    session: Session, expected_versions: Mapping[int, int]
) -> dict[int, int]:
    """Lock, validate and increment Domains once; transaction remains caller-owned."""
    if not expected_versions:
        raise ValueError("At least one Domain version is required")
    normalized: dict[int, int] = {}
    for domain_id, expected in expected_versions.items():
        if isinstance(domain_id, bool) or not isinstance(domain_id, int) or domain_id <= 0:
            raise ValueError("Domain IDs must be positive integers")
        if isinstance(expected, bool) or not isinstance(expected, int) or expected < 0:
            raise ValueError("Expected Domain versions must be non-negative integers")
        normalized[domain_id] = expected
    ids = sorted(normalized)
    rows = list(session.scalars(
        select(Domain).where(Domain.id.in_(ids)).order_by(Domain.id).with_for_update()
    ))
    if len(rows) != len(ids):
        raise ValueError("One or more Domains do not exist")
    if any(row.version != normalized[row.id] for row in rows):
        raise DomainConcurrencyConflict()
    result = {}
    for row in rows:
        row.version += 1
        result[row.id] = row.version
    session.flush()
    return result
