from copy import deepcopy
from datetime import date

import pytest

from application.state.assessment_domain_state import AssessmentDomainState
from application.use_cases.create_blast_event import (
    BlastEventCreationPermissionError, CreateBlastEvent, CreateBlastEventCommand,
)


class MemoryPersistence:
    def __init__(self, *, fail=False):
        self.persisted = AssessmentDomainState()
        self.blocks = []
        self.fail = fail

    def load_state(self, domain_id):
        return deepcopy(self.persisted)

    def persist_contour(self, domain_id, state):
        if self.fail: raise RuntimeError("injected persistence failure")
        self.persisted = deepcopy(state)

    def persist_production(self, domain_id, state, event_id, actor_id):
        if self.fail: raise RuntimeError("injected persistence failure")
        block_id = len(self.blocks) + 1
        event = next(item for item in state.blast_events if item.id == event_id)
        event.blast_block_id = block_id
        self.blocks.append({"id": block_id, "domain_id": domain_id, "block_number": event.name,
                            "horizon": event.elevation, "date": event.event_date,
                            "status": "planned", "comment": None, "actor_id": actor_id})
        self.persisted = deepcopy(state)
        return block_id


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


def test_contour_success_creates_event_without_block(tmp_path):
    persistence = MemoryPersistence()
    result = CreateBlastEvent(persistence).execute(command(contour_geometry_file(tmp_path), "contour"))
    assert result.event_type == "contour" and result.blast_block_id is None
    assert len(persistence.persisted.blast_events) == 1
    assert persistence.persisted.blast_events[0].blast_block_id is None
    assert persistence.blocks == []


def test_production_success_creates_exactly_one_linked_block(tmp_path):
    persistence = MemoryPersistence()
    result = CreateBlastEvent(persistence).execute(command(geometry_file(tmp_path)))
    event = persistence.persisted.blast_events[0]
    assert result.blast_block_id == event.blast_block_id == persistence.blocks[0]["id"]
    assert len(persistence.blocks) == 1
    assert persistence.blocks[0] == {"id": 1, "domain_id": 7, "block_number": "B-17", "horizon": 100.0,
                                     "date": date(2026, 8, 10), "status": "planned", "comment": None, "actor_id": 42}


def test_permission_rejection_does_not_load_or_persist(tmp_path):
    persistence = MemoryPersistence()
    with pytest.raises(BlastEventCreationPermissionError):
        CreateBlastEvent(persistence).execute(command(geometry_file(tmp_path), can_edit=False))
    assert persistence.persisted.blast_events == [] and persistence.blocks == []


def test_geometry_failure_does_not_persist(tmp_path):
    persistence = MemoryPersistence()
    with pytest.raises(ValueError):
        CreateBlastEvent(persistence).execute(command(str(tmp_path / "missing.csv")))
    assert persistence.persisted.blast_events == [] and persistence.blocks == []


def test_persistence_failure_leaves_fake_store_unchanged(tmp_path):
    persistence = MemoryPersistence(fail=True)
    with pytest.raises(RuntimeError, match="injected"):
        CreateBlastEvent(persistence).execute(command(geometry_file(tmp_path)))
    assert persistence.persisted.blast_events == [] and persistence.blocks == []
