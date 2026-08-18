from copy import deepcopy
from datetime import date

import pytest

from application.state.assessment_domain_state import AssessmentDomainState
from application.ports.assessment_state import AssessmentStateSnapshot
from application.use_cases.create_blast_event import (
    BlastEventCreationPermissionError, CreateBlastEvent, CreateBlastEventCommand,
)


class MemoryPersistence:
    def __init__(self, *, fail=False):
        self.persisted = AssessmentDomainState()
        self.calls = []
        self.fail = fail

    def load_state(self, domain_id):
        return AssessmentStateSnapshot(domain_id, 1, deepcopy(self.persisted), 0)

    def persist_event(self, domain_id, expected_version, event, actor_id):
        if self.fail:
            raise RuntimeError("injected persistence failure")
        self.calls.append((domain_id, expected_version, actor_id))
        self.persisted.blast_events.append(deepcopy(event))
        return expected_version + 1


def geometry_file(tmp_path):
    path = tmp_path / "blast.csv"
    path.write_text("SID,PTN,X,Y,Z\nA,1,0,0,100\nA,2,10,0,100\nA,3,10,10,100\nA,4,0,10,100\nA,5,0,0,100\n")
    return str(path)


def command(path, event_type="production", can_edit=True):
    return CreateBlastEventCommand(7, "B-17", event_type, date(2026, 8, 10), 100, path, 42, can_edit)


def contour_geometry_file(tmp_path):
    path = tmp_path / "contour.csv"
    path.write_text("SID,PTN,X,Y,Z\nA,1,0,0,100\nA,2,0,0,90\nB,1,10,0,102\nB,2,10,0,90\n")
    return str(path)


def test_contour_success_creates_exactly_one_contour_event(tmp_path):
    persistence = MemoryPersistence()
    result = CreateBlastEvent(persistence).execute(command(contour_geometry_file(tmp_path), "contour"))
    assert result.event_type == "contour"
    assert len(persistence.persisted.blast_events) == 1
    event = persistence.persisted.blast_events[0]
    assert event.id == result.event_id
    assert event.event_type == "contour"
    assert event.created_by_user_id == 42
    assert persistence.calls == [(7, 0, 42)]


def test_production_success_creates_exactly_one_production_event_without_secondary_block_identity(tmp_path):
    persistence = MemoryPersistence()
    result = CreateBlastEvent(persistence).execute(command(geometry_file(tmp_path)))
    assert result.event_type == "production"
    assert len(persistence.persisted.blast_events) == 1
    event = persistence.persisted.blast_events[0]
    assert event.id == result.event_id
    assert event.name == "B-17"
    assert event.elevation == 100.0
    assert event.event_date == date(2026, 8, 10)
    assert event.created_by_user_id == 42
    assert not hasattr(event, "blast_block_id")
    assert not hasattr(result, "blast_block_id")
    assert persistence.calls == [(7, 0, 42)]


def test_permission_rejection_does_not_load_or_persist(tmp_path):
    persistence = MemoryPersistence()
    with pytest.raises(BlastEventCreationPermissionError):
        CreateBlastEvent(persistence).execute(command(geometry_file(tmp_path), can_edit=False))
    assert persistence.persisted.blast_events == [] and persistence.calls == []


def test_geometry_failure_does_not_persist(tmp_path):
    persistence = MemoryPersistence()
    with pytest.raises(ValueError):
        CreateBlastEvent(persistence).execute(command(str(tmp_path / "missing.csv")))
    assert persistence.persisted.blast_events == [] and persistence.calls == []


def test_persistence_failure_leaves_fake_store_unchanged(tmp_path):
    persistence = MemoryPersistence(fail=True)
    with pytest.raises(RuntimeError, match="injected"):
        CreateBlastEvent(persistence).execute(command(geometry_file(tmp_path)))
    assert persistence.persisted.blast_events == [] and persistence.calls == []
