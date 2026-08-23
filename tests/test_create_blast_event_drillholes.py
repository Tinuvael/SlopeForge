from copy import deepcopy
from datetime import date
from types import SimpleNamespace

import pytest

from application.ports.assessment_state import AssessmentStateSnapshot
from application.state.assessment_domain_state import AssessmentDomainState
from application.use_cases.create_blast_event import CreateBlastEvent, CreateBlastEventCommand


class MemoryPersistence:
    def __init__(self):
        self.persisted = AssessmentDomainState()

    def load_state(self, domain_id):
        return AssessmentStateSnapshot(domain_id, 1, deepcopy(self.persisted), 0)

    def persist_event(self, domain_id, expected_version, event, actor_id):
        self.persisted.blast_events.append(deepcopy(event))
        return expected_version + 1


class DrillholeWriter:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def import_dataset(self, domain_id, event_id, kind, path, *, imported_by_user_id=None):
        self.calls.append((domain_id, event_id, kind, path, imported_by_user_id))
        if self.fail:
            raise RuntimeError("drillhole import failed")
        return SimpleNamespace(id=1)


def write_dxf(path, lines):
    ezdxf = pytest.importorskip("ezdxf")
    doc = ezdxf.new(); modelspace = doc.modelspace()
    for points in lines:
        modelspace.add_polyline3d(points)
    doc.saveas(path)
    return str(path)


def production_geometry(tmp_path):
    return write_dxf(
        tmp_path / "block.dxf",
        [[(0,0,100),(10,0,100),(10,10,100),(0,10,100),(0,0,100)]],
    )


def contour_geometry(tmp_path):
    return write_dxf(
        tmp_path / "contour.dxf",
        [[(0,0,100),(0,0,90)],[(10,0,101),(10,0,90)]],
    )


def command(path, event_type, design_path=None):
    return CreateBlastEventCommand(
        domain_id=7,
        name="Event",
        event_type=event_type,
        event_date=date(2026, 8, 23),
        elevation=100,
        geometry_file_path=path,
        actor_id=42,
        can_edit=True,
        design_drillhole_file_path=design_path,
    )


def test_contour_creation_reuses_event_geometry_as_design_drillholes(tmp_path):
    persistence = MemoryPersistence(); writer = DrillholeWriter()
    geometry = contour_geometry(tmp_path)

    result = CreateBlastEvent(persistence, writer).execute(command(geometry, "contour"))

    assert result.warning_text is None
    assert writer.calls == [(7, result.event_id, "design", geometry, 42)]


def test_production_creation_uses_separate_optional_drillhole_source(tmp_path):
    persistence = MemoryPersistence(); writer = DrillholeWriter()
    geometry = production_geometry(tmp_path)
    drillholes = write_dxf(
        tmp_path / "design-holes.dxf",
        [[(2,2,100),(2,2,90)],[(8,8,100),(8,8,90)]],
    )

    result = CreateBlastEvent(persistence, writer).execute(
        command(geometry, "production", drillholes)
    )

    assert result.warning_text is None
    assert writer.calls == [(7, result.event_id, "design", drillholes, 42)]


def test_production_creation_without_drillholes_remains_valid(tmp_path):
    writer = DrillholeWriter()
    result = CreateBlastEvent(MemoryPersistence(), writer).execute(
        command(production_geometry(tmp_path), "production")
    )
    assert result.event_type == "production"
    assert writer.calls == []


def test_secondary_drillhole_failure_does_not_roll_back_created_event(tmp_path):
    persistence = MemoryPersistence(); writer = DrillholeWriter(fail=True)
    result = CreateBlastEvent(persistence, writer).execute(
        command(contour_geometry(tmp_path), "contour")
    )
    assert len(persistence.persisted.blast_events) == 1
    assert "Design drillholes were not saved" in result.warning_text
