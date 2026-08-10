"""Destructive integration tests for a disposable PostgreSQL database only."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
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
from database.models import BlastBlock, Domain, Mine, Site
from repositories.assessment_state_mapper import (
    AssessmentPersistenceCorruptionError, AssessmentSiteNotFoundError,
)
from repositories.assessment_state_repository import AssessmentStateRepository
from repositories.project_lines_repository import ProjectLinesRepository
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


@dataclass(frozen=True)
class AssessmentContext:
    site_id: int
    domain_id: int
    mine_id: int


@pytest.fixture
def assessment_context(session_factory):
    with session_factory.begin() as session:
        mine = Mine(name="Assessment repository integration mine")
        session.add(mine); session.flush()
        site = Site(mine_id=mine.id, name="Assessment repository integration site")
        session.add(site); session.flush()
        domain = Domain(site_id=site.id, name="North")
        session.add(domain); session.flush()
        context = AssessmentContext(site.id, domain.id, mine.id)
    yield context
    with session_factory.begin() as session:
        workspace = session.scalar(select(orm.AssessmentWorkspace).where(
            orm.AssessmentWorkspace.domain_id == context.domain_id))
        if workspace: session.delete(workspace); session.flush()
        session.query(orm.ProjectLinesDataset).filter_by(site_id=context.site_id).delete()
        session.query(BlastBlock).filter_by(domain_id=context.domain_id).delete()
        session.query(Domain).filter_by(id=context.domain_id).delete()
        session.query(Site).filter_by(id=context.site_id).delete()
        session.query(Mine).filter_by(id=context.mine_id).delete()


def persist_project_lines(session_factory, site_id, state):
    repository = ProjectLinesRepository(session_factory)
    for dataset in state.datasets:
        repository.add_dataset(site_id, dataset)
    active = state.active_dataset()
    repository.set_active(site_id, active.id if active else None)


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


def test_missing_domain_and_empty_domain(session_factory, assessment_context):
    repository = AssessmentStateRepository(session_factory)
    with pytest.raises(AssessmentSiteNotFoundError): repository.load_for_domain(2_000_000_000)
    loaded = repository.load_for_domain(assessment_context.domain_id)
    assert loaded.workspace_id is None and semantic(loaded.state) == semantic(type(loaded.state)())


def test_rich_replace_round_trip_and_active_history(session_factory, assessment_context):
    repository = AssessmentStateRepository(session_factory); expected = build_rich_state()
    persist_project_lines(session_factory, assessment_context.site_id, expected)
    saved = repository.replace_for_domain(assessment_context.domain_id, expected)
    loaded = AssessmentStateRepository(session_factory).load_for_domain(assessment_context.domain_id)
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


def test_second_replace_recreates_rows_and_removes_omitted_state(session_factory, assessment_context):
    repository = AssessmentStateRepository(session_factory); state = build_rich_state()
    persist_project_lines(session_factory, assessment_context.site_id, state)
    first = repository.replace_for_domain(assessment_context.domain_id, state)
    with session_factory() as session:
        old_event_ids = set(session.scalars(select(orm.BlastEvent.id)).all())
    replacement = deepcopy(state); replacement.blast_events[1].is_archived = True
    second = repository.replace_for_domain(assessment_context.domain_id, replacement)
    with session_factory() as session:
        new_event_ids = set(session.scalars(select(orm.BlastEvent.id)).all())
        assert session.scalar(select(func.count()).select_from(orm.AssessmentWorkspace).where(
            orm.AssessmentWorkspace.domain_id == assessment_context.domain_id)) == 1
    assert first.workspace_id != second.workspace_id and old_event_ids.isdisjoint(new_event_ids)
    assert [x.id for x in second.state.blast_events] == [x.id for x in replacement.blast_events]


def test_real_cascade_graph_preserves_foundation_and_clears_block_link(session_factory, assessment_context):
    with session_factory.begin() as session:
        block = BlastBlock(domain_id=assessment_context.domain_id, block_number="B-1", status="planned")
        session.add(block); session.flush(); block_id = block.id
    repository = AssessmentStateRepository(session_factory)
    state = build_rich_state()
    persist_project_lines(session_factory, assessment_context.site_id, state)
    repository.replace_for_domain(assessment_context.domain_id, state)
    repository.replace_for_domain(assessment_context.domain_id, state)
    with session_factory() as session:
        assert session.get(Site, assessment_context.site_id) is not None and session.get(BlastBlock, block_id) is not None
        assert all(value is None for value in session.scalars(select(orm.BlastEvent.blast_block_id)))


def test_failed_replace_rolls_back_previous_workspace(session_factory, assessment_context, monkeypatch):
    repository = AssessmentStateRepository(session_factory); state = build_rich_state()
    persist_project_lines(session_factory, assessment_context.site_id, state)
    committed = repository.replace_for_domain(assessment_context.domain_id, state)
    def fail(*args): raise RuntimeError("injected insertion failure")
    monkeypatch.setattr(repository, "_insert", fail)
    with pytest.raises(RuntimeError): repository.replace_for_domain(assessment_context.domain_id, deepcopy(state))
    loaded = AssessmentStateRepository(session_factory).load_for_domain(assessment_context.domain_id)
    assert loaded.workspace_id == committed.workspace_id and semantic(loaded.state) == semantic(state)


def test_replace_performs_no_filesystem_operations(session_factory, assessment_context, monkeypatch):
    def forbidden(*args, **kwargs): raise AssertionError("filesystem operation")
    for name in ("unlink", "rename", "replace", "read_bytes", "write_bytes"):
        monkeypatch.setattr(Path, name, forbidden)
    state = build_rich_state()
    persist_project_lines(session_factory, assessment_context.site_id, state)
    AssessmentStateRepository(session_factory).replace_for_domain(assessment_context.domain_id, state)


def test_payload_mismatch_is_corruption(session_factory, assessment_context):
    state = build_rich_state()
    persist_project_lines(session_factory, assessment_context.site_id, state)
    AssessmentStateRepository(session_factory).replace_for_domain(assessment_context.domain_id, state)
    with session_factory.begin() as session:
        row = session.scalar(select(orm.BlastEventTechnicalCardRevision).order_by(orm.BlastEventTechnicalCardRevision.id))
        payload = dict(row.payload_json); payload["status"] = "completed"
        session.execute(update(orm.BlastEventTechnicalCardRevision).where(
            orm.BlastEventTechnicalCardRevision.id == row.id).values(payload_json=payload))
    with pytest.raises(AssessmentPersistenceCorruptionError, match="payload"):
        AssessmentStateRepository(session_factory).load_for_domain(assessment_context.domain_id)


def test_cross_event_card_geometry_corruption_is_detected(session_factory, assessment_context):
    state = build_rich_state()
    persist_project_lines(session_factory, assessment_context.site_id, state)
    AssessmentStateRepository(session_factory).replace_for_domain(assessment_context.domain_id, state)
    with session_factory.begin() as session:
        contour_geometry = session.scalar(select(orm.BlastEventGeometryRevision.id).join(orm.BlastEvent).where(
            orm.BlastEvent.domain_id == "BE-C"))
        card_revision = session.scalar(select(orm.BlastEventTechnicalCardRevision.id))
        session.execute(update(orm.BlastEventTechnicalCardRevision).where(
            orm.BlastEventTechnicalCardRevision.id == card_revision).values(
                blast_event_geometry_revision_id=contour_geometry))
    with pytest.raises(AssessmentPersistenceCorruptionError, match="another BlastEvent"):
        AssessmentStateRepository(session_factory).load_for_domain(assessment_context.domain_id)


def test_cross_area_evaluation_geometry_corruption_is_detected(session_factory, assessment_context):
    # A second area and its revision are produced through a valid replacement,
    # then the relational FK is deliberately pointed at that other area.
    state = build_rich_state(); other = deepcopy(state.assessment_areas[0])
    persist_project_lines(session_factory, assessment_context.site_id, state)
    other.id = "AA-OTHER"; other.event_links = []
    for revision in other.geometry_revisions:
        object.__setattr__(revision, "assessment_area_id", other.id)
        object.__setattr__(revision, "id", "OTHER-" + revision.id)
    other.active_geometry_revision_id = "OTHER-AA-R2"; state.assessment_areas.append(other)
    AssessmentStateRepository(session_factory).replace_for_domain(assessment_context.domain_id, state)
    with session_factory.begin() as session:
        other_geometry = session.scalar(select(orm.AssessmentAreaGeometryRevision.id).join(orm.AssessmentArea).where(
            orm.AssessmentArea.domain_id == "AA-OTHER"))
        evaluation_revision = session.scalar(select(orm.AssessmentAreaEvaluationRevision.id))
        session.execute(update(orm.AssessmentAreaEvaluationRevision).where(
            orm.AssessmentAreaEvaluationRevision.id == evaluation_revision).values(
                assessment_area_geometry_revision_id=other_geometry))
    with pytest.raises(AssessmentPersistenceCorruptionError, match="another Assessment Area"):
        AssessmentStateRepository(session_factory).load_for_domain(assessment_context.domain_id)


def test_optional_production_link_snapshot_persists_as_sql_null(session_factory, assessment_context):
    """Production suggestions intentionally have no frozen intersection snapshot."""
    repository=AssessmentStateRepository(session_factory); state=build_rich_state(); persist_project_lines(session_factory,assessment_context.site_id,state)
    active=next(link for link in state.assessment_areas[0].event_links if link.id=="LINK-ACTIVE")
    active.frozen_intersection_geometry=None
    saved=repository.replace_for_domain(assessment_context.domain_id,state)
    restored=next(link for link in saved.state.assessment_areas[0].event_links if link.id=="LINK-ACTIVE")
    contour_snapshot=next(link for link in saved.state.assessment_areas[0].event_links if link.id=="LINK-OLD")
    assert restored.frozen_intersection_geometry is None
    assert contour_snapshot.frozen_intersection_geometry is not None
    with session_factory() as session:
        row=session.scalar(select(orm.AssessmentEventLink).where(orm.AssessmentEventLink.domain_id=="LINK-ACTIVE"))
        assert row.frozen_intersection_geometry_json is None


def test_real_block_page_embeds_engineering_and_persists_ucs(session_factory, assessment_context, tmp_path):
    widgets=pytest.importorskip("PySide6.QtWidgets",exc_type=ImportError)
    from database.app_context import AppContext,CurrentUser
    from ui.pages.block_page import BlockPage
    app=widgets.QApplication.instance() or widgets.QApplication([])
    with session_factory.begin() as session:
        block=BlastBlock(domain_id=assessment_context.domain_id,block_number="QT-BLOCK",status="planned")
        session.add(block); session.flush(); block_id=block.id
    state=build_rich_state(); production=next(e for e in state.blast_events if e.event_type=="production"); production.blast_block_id=block_id
    persist_project_lines(session_factory,assessment_context.site_id,state); AssessmentStateRepository(session_factory).replace_for_domain(assessment_context.domain_id,state)
    context=AppContext(session_factory,CurrentUser(1,"qt-editor","Qt Editor","editor"),tmp_path)
    page=BlockPage(context); page.resize(1400,900); page.show(); page.open_block_id(block_id); app.processEvents()
    editor=page.technical_card_editor.editor
    page.tabs.setCurrentWidget(page.geomechanics_tab); app.processEvents()
    assert page.geomechanics_tab.isVisibleTo(page)
    for control in (editor.lithology,editor.geotechnical_domain,editor.strength_class,editor.ucs,editor.ucs_min,editor.ucs_max,editor.rqd,editor.rqd_min,editor.rqd_max,editor.rock_properties,editor.fracturing,editor.water,editor.geo_notes):
        assert page.geomechanics_tab.isAncestorOf(control) and control.isVisibleTo(page.geomechanics_tab)
    page.tabs.setCurrentWidget(page.design_tab); app.processEvents(); assert page.design_tab.isVisibleTo(page) and editor.group_cards_layout.count()>=1
    burden=page.design_tab.findChild(widgets.QDoubleSpinBox,"burden_m"); spacing=page.design_tab.findChild(widgets.QDoubleSpinBox,"spacing_m")
    assert burden is not None and burden.isVisibleTo(page.design_tab); assert spacing is not None and spacing.isVisibleTo(page.design_tab)
    page.tabs.setCurrentWidget(page.execution_tab); app.processEvents(); assert page.execution_tab.isVisibleTo(page)
    assert page.execution_tab.isAncestorOf(editor.completion_status) and editor.completion_status.isVisibleTo(page.execution_tab) and editor.actual_summary_widgets
    editor.ucs.setValue(147.0); page._save_technical_card_draft()
    reloaded=AssessmentStateRepository(session_factory).load_for_domain(assessment_context.domain_id).state
    card=next(c for c in reloaded.technical_cards if c.blast_event_id==production.id)
    assert card.active_revision().geomechanical_parameters.representative_ucs_mpa==147.0
    page.deleteLater(); app.processEvents()


def test_focused_area_edit_boundaries_round_trip_preserves_entity_graph(session_factory, assessment_context, tmp_path, monkeypatch):
    widgets=pytest.importorskip("PySide6.QtWidgets",exc_type=ImportError)
    from database.app_context import AppContext,CurrentUser
    from ui.main_window import MainWindow
    app=widgets.QApplication.instance() or widgets.QApplication([])
    state=build_rich_state(); persist_project_lines(session_factory,assessment_context.site_id,state); repository=AssessmentStateRepository(session_factory); repository.replace_for_domain(assessment_context.domain_id,state)
    original=repository.load_for_domain(assessment_context.domain_id).state; area=original.assessment_areas[0]; area_id=area.id; revision_ids=[r.id for r in area.geometry_revisions]; evaluation_ids=[e.id for e in original.evaluations]; attachment_ids=[a.id for a in original.attachments]
    context=AppContext(session_factory,CurrentUser(1,"area-editor","Area Editor","editor"),tmp_path)
    window=MainWindow(context); window.show(); window._set_context(assessment_context.site_id,"Project",assessment_context.domain_id,"North",area_id=area_id)
    assert window.open_area_from_tree(area_id,assessment_context.domain_id,assessment_context.site_id,"North")
    window._edit_area_boundaries(area_id); focused=window.assessment_page; app.processEvents(); assert focused.controller.workspace.workflow_state=="REFINING"
    warnings=[]
    monkeypatch.setattr(widgets.QMessageBox,"warning",lambda *args,**kwargs:(warnings.append(args),widgets.QMessageBox.StandardButton.Cancel)[1])
    focused._close_page(); app.processEvents()
    assert warnings and window.assessment_page is focused and window.page_stack.currentWidget() is focused
    focused._cancel_drawing(); assert focused.controller.workspace.workflow_state=="IDLE"
    focused._start_drawing(); assert focused.controller.workspace.workflow_state=="REFINING" and focused.controller.workspace.selected_area.id==area_id
    saved_signals=[]; focused.controller.state_saved.connect(lambda:saved_signals.append(True)); completed=[]; focused.area_created.connect(completed.append)
    focused.controller.workspace._save(); assert saved_signals==[True] and completed==[]
    save_now_calls=[]; monkeypatch.setattr(focused,"save_now",lambda:save_now_calls.append(True))
    def confirm_after_persistence():
        edited=focused.controller.workspace.selected_area; polygon=edited.selection_polygon_frozen; candidates=focused.controller.workspace.area_service.generate_candidates(polygon)
        focused.controller.workspace.area_service.revise_area(edited,selection_polygon=polygon,selected_fragments=candidates)
        focused.controller.workspace.link_service.refresh_suggestions(edited); focused.controller.workspace._save(); focused.controller.workspace.cancel_area_drawing()
    monkeypatch.setattr(focused.controller.workspace,"confirm_refined_polygon",confirm_after_persistence)
    warning_count=len(warnings); focused._confirm(); app.processEvents()
    assert completed==[area_id] and len(warnings)==warning_count and save_now_calls==[]
    assert window.assessment_page is None and window.area_page.area.id==area_id and window.page_stack.indexOf(focused)==-1
    reloaded=repository.load_for_domain(assessment_context.domain_id).state
    assert [a.id for a in reloaded.assessment_areas]==[area_id]
    saved_area=reloaded.assessment_areas[0]; assert len(saved_area.geometry_revisions)==len(revision_ids)+1
    assert set(revision_ids).issubset({r.id for r in saved_area.geometry_revisions})
    assert saved_area.active_geometry_revision().source_dataset_id in {d.id for d in reloaded.datasets}
    assert [e.id for e in reloaded.evaluations]==evaluation_ids and [a.id for a in reloaded.attachments]==attachment_ids
    window.close(); app.processEvents()


def test_zero_revision_evaluation_container_round_trips(session_factory, assessment_context):
    from domain.assessment.evaluation import AssessmentAreaEvaluationService

    state = build_rich_state()
    state.evaluations = []
    state.attachments = [item for item in state.attachments if item.owner_type != "assessment_evaluation"]
    area = state.assessment_areas[0]
    owner = AssessmentAreaEvaluationService(state).create_evaluation(area)
    state.evaluations.append(owner)
    repository = AssessmentStateRepository(session_factory)
    repository.replace_for_domain(assessment_context.domain_id, state)

    reloaded = repository.load_for_domain(assessment_context.domain_id).state
    owners = [item for item in reloaded.evaluations if item.assessment_area_id == area.id]
    assert len(owners) == 1
    assert owners[0].id == owner.id
    assert owners[0].revisions == []
    assert owners[0].active_revision_id is None
