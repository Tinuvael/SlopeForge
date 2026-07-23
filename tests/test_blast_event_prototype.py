from datetime import date

import pytest

from prototype_2d.blast_event_service import BlastEventService, BlastEventValidationError
from prototype_2d.blast_event_storage import load_blast_event_state, save_blast_event_state
from prototype_2d.domain import AssessmentDomainState, PlanMultiPoint, PlanPolygon


def write_csv(path, rows):
    path.write_text("XP,YP,ZP,SID,PTN\n" + "\n".join(
        f"{x},{y},{z},{line},{order}" for x, y, z, line, order in rows
    ), encoding="utf-8")


def production_csv(path, z=620):
    write_csv(path, [(0,0,z,"top",1),(10,0,z,"top",2),(10,10,z,"top",3),(0,0,z,"top",4)])


def test_create_production_event(tmp_path):
    source=tmp_path/"block.csv"; production_csv(source); state=AssessmentDomainState()
    event=BlastEventService(state).create_event(name="Блок",event_type="production",event_date=date.today(),elevation=615,csv_path=source)
    assert len(state.blast_events)==1 and isinstance(event.active_geometry_revision().plan_geometry, PlanPolygon)
    assert event.active_geometry_revision().revision_number == 1


def test_create_contour_event_preserves_user_horizon(tmp_path):
    source=tmp_path/"holes.csv"; write_csv(source, [(0,0,650,"h1",1),(0,0,620,"h1",2),(10,0,655,"h2",1),(10,0,620,"h2",2)])
    event=BlastEventService(AssessmentDomainState()).create_event(name="Контур",event_type="contour",event_date=date.today(),elevation=640,csv_path=source)
    assert event.elevation == 640 and isinstance(event.active_geometry_revision().plan_geometry, PlanMultiPoint)


def test_cannot_save_without_geometry(tmp_path):
    with pytest.raises(BlastEventValidationError, match="CSV"):
        BlastEventService(AssessmentDomainState()).create_event(name="Блок",event_type="production",event_date=None,elevation=620,csv_path=tmp_path/"missing.csv")


def test_reimport_keeps_first_revision_and_makes_revision_two(tmp_path):
    one=tmp_path/"one.csv"; two=tmp_path/"two.csv"; production_csv(one,620); production_csv(two,621); service=BlastEventService(AssessmentDomainState())
    event=service.create_event(name="Блок",event_type="production",event_date=None,elevation=620,csv_path=one); first=event.geometry_revisions[0]
    second=service.reimport_geometry(event,two)
    assert second.revision_number == 2 and second.is_active and not first.is_active
    assert first.source_file_name == "one.csv" and event.active_geometry_revision_id == second.id


def test_archive_restore_and_json_round_trip(tmp_path):
    source=tmp_path/"block.csv"; production_csv(source); state=AssessmentDomainState(); event=BlastEventService(state).create_event(name="Блок",event_type="production",event_date=None,elevation=620,csv_path=source)
    event.archive("проверка"); target=save_blast_event_state(state,tmp_path/"events.json"); restored=load_blast_event_state(target)
    assert restored.blast_events[0].is_archived and restored.blast_events[0].active_geometry_revision_id == event.active_geometry_revision_id
    restored.blast_events[0].restore(); assert not restored.blast_events[0].is_archived


def test_main_window_declares_blast_events_entry_point():
    source = __import__('pathlib').Path('ui/main_window.py').read_text(encoding='utf-8')
    assert 'Blast Events Prototype' in source
    assert 'open_blast_events_prototype' in source
