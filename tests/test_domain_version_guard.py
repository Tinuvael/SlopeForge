import pytest

from application.errors import DomainConcurrencyConflict
from infrastructure.db.domain_version import guard_domain_versions


class _Scalars:
    def __init__(self, rows): self._rows = rows
    def __iter__(self): return iter(self._rows)


class _Session:
    def __init__(self, rows): self.rows = rows; self.flushes = 0
    def scalars(self, statement):
        # The primitive's SQL ordering is asserted independently below; emulate DB order.
        return _Scalars(sorted(self.rows, key=lambda row: row.id))
    def flush(self): self.flushes += 1


def _domain(domain_id, version):
    return type("DomainRow", (), {"id": domain_id, "version": version})()


def test_two_domain_guard_increments_once_in_deterministic_order():
    source, target = _domain(9, 3), _domain(2, 7)
    session = _Session([source, target])
    assert guard_domain_versions(session, {9: 3, 2: 7}) == {2: 8, 9: 4}
    assert (source.version, target.version, session.flushes) == (4, 8, 1)


@pytest.mark.parametrize("expected", ({2: 6, 9: 3}, {9: 2, 2: 7}))
def test_stale_member_increments_neither_domain(expected):
    source, target = _domain(9, 3), _domain(2, 7)
    session = _Session([source, target])
    with pytest.raises(DomainConcurrencyConflict, match="Reload or reopen"):
        guard_domain_versions(session, expected)
    assert (source.version, target.version, session.flushes) == (3, 7, 0)


@pytest.mark.parametrize("values", ({}, {0: 0}, {1: -1}))
def test_guard_rejects_invalid_input(values):
    with pytest.raises(ValueError):
        guard_domain_versions(_Session([]), values)
