"""Destructive integration tests for a disposable PostgreSQL database only."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

URL = os.environ.get("SLOPEFORGE_TEST_DATABASE_URL")
if not URL:
    pytest.skip("SLOPEFORGE_TEST_DATABASE_URL is not set; PostgreSQL integration tests skipped", allow_module_level=True)
DATABASE_NAME = make_url(URL).database or ""
if "test" not in DATABASE_NAME.lower():
    pytest.fail("Refusing destructive tests: PostgreSQL database name must contain 'test'", pytrace=False)

from database import assessment_models as orm
from database.models import BlastBlock, Mine, Site
from repositories.assessment_state_mapper import (
    AssessmentPersistenceCorruptionError, AssessmentSiteNotFoundError,
)
from repositories.assessment_state_repository import AssessmentStateRepository
from tests.test_assessment_state_mapper import build_rich_state


@pytest.fixture(scope="session")
def session_factory(tmp_path_factory):
    # Alembic itself reads DATABASE_URL/STORAGE_ROOT; both values originate here,
    # never from the application's DATABASE_URL environment setting.
    old_database = os.environ.get("DATABASE_URL")
    old_storage = os.environ.get("STORAGE_ROOT")
    os.environ["DATABASE_URL"] = URL
    os.environ["STORAGE_ROOT"] = str(tmp_path_factory.mktemp("storage"))
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if old_database is None: os.environ.pop("DATABASE_URL", None)
        else: os.environ["DATABASE_URL"] = old_database
        if old_storage is None: os.environ.pop("STORAGE_ROOT", None)
        else: os.environ["STORAGE_ROOT"] = old_storage
    engine = create_engine(URL)
    yield sessionmaker(engine, expire_on_commit=False)
    engine.dispose()


@pytest.fixture
def site(session_factory):
    with session_factory.begin() as session:
        mine = Mine(name="Assessment repository integration mine")
        session.add(mine); session.flush()
        value = Site(mine_id=mine.id, name="Assessment repository integration site")
        session.add(value); session.flush()
        ids = value.id, mine.id
    yield ids[0]
    with session_factory.begin() as session:
        workspace = session.scalar(select(orm.AssessmentWorkspace).where(orm.AssessmentWorkspace.site_id == ids[0]))
        if workspace: session.delete(workspace); session.flush()
        session.query(BlastBlock).filter_by(site_id=ids[0]).delete()
        session.query(Site).filter_by(id=ids[0]).delete()
        session.query(Mine).filter_by(id=ids[1]).delete()


def semantic(state):
    """Canonical public payload; datetime offsets compare as the same instant."""
    def normalize(value):
        if isinstance(value, dict):
            return {key: normalize(item) for key, item in value.items()}
        if isinstance(value, list):
            return [normalize(item) for item in value]
        if isinstance(value, str) and "T" in value:
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return value
            if parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).isoformat()
        return value
    # to_dict is the complete domain contract (IDs, parents, geometry, archive
    # fields, revision order, links, card/evaluation payloads and attachments).
    return normalize(state.to_dict())


def test_missing_site_and_empty_site(session_factory, site):
    repository = AssessmentStateRepository(session_factory)
    with pytest.raises(AssessmentSiteNotFoundError): repository.load_for_site(2_000_000_000)
    loaded = repository.load_for_site(site)
    assert loaded.workspace_id is None and semantic(loaded.state) == semantic(type(loaded.state)())


def test_rich_replace_round_trip_and_active_history(session_factory, site):
    repository = AssessmentStateRepository(session_factory); expected = build_rich_state()
    saved = repository.replace_for_site(site, expected)
    loaded = AssessmentStateRepository(session_factory).load_for_site(site)
    assert loaded.workspace_id == saved.workspace_id
    assert semantic(loaded.state) == semantic(expected)
    assert loaded.state.active_dataset().id == "D2"
    assert loaded.state.blast_events[0].active_geometry_revision_id == "BE-P-R2"
    assert loaded.state.assessment_areas[0].active_geometry_revision_id == "AA-R2"
    assert loaded.state.technical_cards[0].active_revision_id.endswith("R002")
    assert loaded.state.evaluations[0].active_revision_id.endswith("R002")
    assert [item.id for item in loaded.state.assessment_areas[0].event_links] == ["LINK-OLD", "LINK-ACTIVE"]
    assert {item.owner_type for item in loaded.state.attachments} == {"blast_event", "assessment_evaluation"}
    assert loaded.state.assessment_areas[0].geometry_revisions[-1].change_reason is None


def test_second_replace_recreates_rows_and_removes_omitted_state(session_factory, site):
    repository = AssessmentStateRepository(session_factory); state = build_rich_state()
    first = repository.replace_for_site(site, state)
    with session_factory() as session:
        old_event_ids = set(session.scalars(select(orm.BlastEvent.id)).all())
    replacement = deepcopy(state); replacement.blast_events[1].is_archived = True
    second = repository.replace_for_site(site, replacement)
    with session_factory() as session:
        new_event_ids = set(session.scalars(select(orm.BlastEvent.id)).all())
        assert session.scalar(select(func.count()).select_from(orm.AssessmentWorkspace).where(
            orm.AssessmentWorkspace.site_id == site)) == 1
    assert first.workspace_id != second.workspace_id and old_event_ids.isdisjoint(new_event_ids)
    assert [x.id for x in second.state.blast_events] == [x.id for x in replacement.blast_events]


def test_real_cascade_graph_preserves_foundation_and_clears_block_link(session_factory, site):
    with session_factory.begin() as session:
        block = BlastBlock(site_id=site, block_number="B-1", status="planned")
        session.add(block); session.flush(); block_id = block.id
    repository = AssessmentStateRepository(session_factory)
    repository.replace_for_site(site, build_rich_state())
    repository.replace_for_site(site, build_rich_state())
    with session_factory() as session:
        assert session.get(Site, site) is not None and session.get(BlastBlock, block_id) is not None
        assert all(value is None for value in session.scalars(select(orm.BlastEvent.blast_block_id)))


def test_failed_replace_rolls_back_previous_workspace(session_factory, site, monkeypatch):
    repository = AssessmentStateRepository(session_factory); state = build_rich_state()
    committed = repository.replace_for_site(site, state)
    def fail(*args): raise RuntimeError("injected insertion failure")
    monkeypatch.setattr(repository, "_insert", fail)
    with pytest.raises(RuntimeError): repository.replace_for_site(site, deepcopy(state))
    loaded = AssessmentStateRepository(session_factory).load_for_site(site)
    assert loaded.workspace_id == committed.workspace_id and semantic(loaded.state) == semantic(state)


def test_replace_performs_no_filesystem_operations(session_factory, site, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("filesystem operation")
    for name in ("unlink", "rename", "replace", "read_bytes", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    AssessmentStateRepository(session_factory).replace_for_site(site, build_rich_state())


def test_payload_mismatch_is_corruption(session_factory, site):
    AssessmentStateRepository(session_factory).replace_for_site(site, build_rich_state())
    with session_factory.begin() as session:
        row = session.scalar(select(orm.BlastEventTechnicalCardRevision).order_by(orm.BlastEventTechnicalCardRevision.id))
        payload = dict(row.payload_json); payload["status"] = "completed"
        session.execute(update(orm.BlastEventTechnicalCardRevision).where(
            orm.BlastEventTechnicalCardRevision.id == row.id).values(payload_json=payload))
    with pytest.raises(AssessmentPersistenceCorruptionError, match="payload"):
        AssessmentStateRepository(session_factory).load_for_site(site)


def test_cross_event_card_geometry_corruption_is_detected(session_factory, site):
    AssessmentStateRepository(session_factory).replace_for_site(site, build_rich_state())
    with session_factory.begin() as session:
        contour_geometry = session.scalar(select(orm.BlastEventGeometryRevision.id).join(orm.BlastEvent).where(
            orm.BlastEvent.domain_id == "BE-C"))
        card_revision = session.scalar(select(orm.BlastEventTechnicalCardRevision.id))
        session.execute(update(orm.BlastEventTechnicalCardRevision).where(
            orm.BlastEventTechnicalCardRevision.id == card_revision).values(
                blast_event_geometry_revision_id=contour_geometry))
    with pytest.raises(AssessmentPersistenceCorruptionError, match="another BlastEvent"):
        AssessmentStateRepository(session_factory).load_for_site(site)


def test_cross_area_evaluation_geometry_corruption_is_detected(session_factory, site):
    # A second area and its revision are produced through a valid replacement,
    # then the relational FK is deliberately pointed at that other area.
    state = build_rich_state(); other = deepcopy(state.assessment_areas[0])
    other.id = "AA-OTHER"; other.event_links = []
    for revision in other.geometry_revisions:
        object.__setattr__(revision, "assessment_area_id", other.id)
        object.__setattr__(revision, "id", "OTHER-" + revision.id)
    other.active_geometry_revision_id = "OTHER-AA-R2"; state.assessment_areas.append(other)
    AssessmentStateRepository(session_factory).replace_for_site(site, state)
    with session_factory.begin() as session:
        other_geometry = session.scalar(select(orm.AssessmentAreaGeometryRevision.id).join(orm.AssessmentArea).where(
            orm.AssessmentArea.domain_id == "AA-OTHER"))
        evaluation_revision = session.scalar(select(orm.AssessmentAreaEvaluationRevision.id))
        session.execute(update(orm.AssessmentAreaEvaluationRevision).where(
            orm.AssessmentAreaEvaluationRevision.id == evaluation_revision).values(
                assessment_area_geometry_revision_id=other_geometry))
    with pytest.raises(AssessmentPersistenceCorruptionError, match="another Assessment Area"):
        AssessmentStateRepository(session_factory).load_for_site(site)
