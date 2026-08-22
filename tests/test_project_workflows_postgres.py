"""Current Project workflow adapters against a disposable PostgreSQL database."""
from __future__ import annotations

from datetime import date
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, delete, event, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

URL = os.environ.get("TEST_DATABASE_URL")
if not URL:
    pytest.skip("TEST_DATABASE_URL is not set; Project workflow PostgreSQL tests skipped", allow_module_level=True)
if "test" not in (make_url(URL).database or "").lower():
    pytest.fail("Refusing destructive Project workflow tests outside a test database", pytrace=False)

from application.use_cases.create_project import CreateProject, CreateProjectCommand
from database import assessment_models as orm
from database.models import Domain, Site
from infrastructure.db.domain_creation import SqlAlchemyDomainCreation
from infrastructure.db.project_creation import SqlAlchemyProjectCreation
from infrastructure.db.project_lines_creation import SqlAlchemyProjectLinesCreationSupport
from infrastructure.db.project_navigation import SqlAlchemyProjectNavigationQueries
from infrastructure.db.project_report import SqlAlchemyProjectReportQuery
from tests.assessment_graph_seeder import AssessmentGraphSeeder
from repositories.project_lines_repository import ProjectLinesRepository
from tests.test_assessment_state_mapper import build_rich_state


@pytest.fixture(scope="module")
def factory(tmp_path_factory):
    old_database = os.environ.get("DATABASE_URL")
    old_storage = os.environ.get("STORAGE_ROOT")
    os.environ["DATABASE_URL"] = URL
    os.environ["STORAGE_ROOT"] = str(tmp_path_factory.mktemp("phase4c-storage"))
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


def command_for(path=None):
    return CreateProjectCommand("  Phase 4C Project  ", "", str(path) if path else None, 1, True)


def cleanup_project(factory, site_id):
    with factory.begin() as session:
        site = session.get(Site, site_id)
        if site is None: return
        domain_ids = select(Domain.id).where(Domain.site_id == site_id)
        event_ids = select(orm.BlastEvent.id).where(orm.BlastEvent.domain_id.in_(domain_ids))
        card_ids = select(orm.BlastEventTechnicalCard.id).where(
            orm.BlastEventTechnicalCard.blast_event_id.in_(event_ids)
        )

        # Area geometry owns AssessmentEventLink rows. Remove it before the
        # referenced BlastEvent geometry.
        session.execute(delete(orm.AssessmentArea).where(
            orm.AssessmentArea.domain_id.in_(domain_ids)))

        # Technical-card revisions also reference BlastEvent geometry with
        # RESTRICT. Delete that branch explicitly instead of relying on two
        # simultaneous CASCADE paths from BlastEvent.
        session.execute(delete(orm.BlastEventTechnicalCardRevision).where(
            orm.BlastEventTechnicalCardRevision.technical_card_id.in_(card_ids)))
        session.execute(delete(orm.BlastEventTechnicalCard).where(
            orm.BlastEventTechnicalCard.blast_event_id.in_(event_ids)))
        session.execute(delete(orm.BlastEvent).where(
            orm.BlastEvent.domain_id.in_(domain_ids)))

        session.execute(delete(orm.ProjectLinesDataset).where(
            orm.ProjectLinesDataset.site_id == site_id))
        session.execute(delete(Domain).where(Domain.site_id == site_id))
        session.delete(site)


def test_concrete_project_creation_is_direct_site_transaction(factory):
    adapter = SqlAlchemyProjectCreation(factory)
    with pytest.raises(ValueError, match="required"):
        adapter.create_project("   ", "ignored")

    site_id = adapter.create_project("  Concrete Project  ", "")
    try:
        with factory() as session:
            site = session.get(Site, site_id)
            assert site.name == "Concrete Project"
            assert site.description is None
            assert not hasattr(site, "mine_id")
            assert session.scalar(select(func.count()).select_from(Site).where(Site.id == site_id)) == 1
    finally:
        cleanup_project(factory, site_id)

    marker = "Phase 4C forced rollback"
    def fail_site_flush(session, _context, _instances):
        if any(isinstance(row, Site) and row.name == marker for row in session.new):
            raise RuntimeError("forced Site failure")
    event.listen(Session, "before_flush", fail_site_flush)
    try:
        with pytest.raises(RuntimeError, match="forced Site failure"):
            adapter.create_project(marker, "description")
    finally:
        event.remove(Session, "before_flush", fail_site_flush)
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Site).where(Site.name == marker)) == 0


def test_concrete_project_lines_prepare_partial_success_and_site_scope(factory, tmp_path, monkeypatch):
    persistence = SqlAlchemyProjectCreation(factory)
    support = SqlAlchemyProjectLinesCreationSupport(factory)
    use_case = CreateProject(persistence, support)
    bad = tmp_path / "bad.csv"; bad.write_text("X,Y\n0,0\n", encoding="utf-8")
    with factory() as session:
        before = session.scalar(select(func.count()).select_from(Site))
    with pytest.raises(Exception): use_case.execute(command_for(bad))
    with factory() as session:
        assert before == session.scalar(select(func.count()).select_from(Site))

    good = tmp_path / "lines.csv"
    good.write_text("X,Y,Z,SID\n0,0,600,L1\n10,0,600,L1\n", encoding="utf-8")
    original = support._repository.import_dataset
    monkeypatch.setattr(support._repository, "import_dataset", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("lines DB failed")))
    result = use_case.execute(command_for(good))
    assert result.project_created and result.project_lines_requested and not result.project_lines_saved
    assert "lines DB failed" in result.project_lines_warning
    with factory() as session:
        assert session.get(Site, result.site_id) is not None
    cleanup_project(factory, result.site_id)

    monkeypatch.setattr(support._repository, "import_dataset", original)
    result = use_case.execute(command_for(good))
    try:
        row = ProjectLinesRepository(factory).get_active(result.site_id)
        assert row is not None and row.site_id == result.site_id and row.is_active
    finally:
        cleanup_project(factory, result.site_id)


def test_domain_adapter_and_navigation_are_site_scoped(factory):
    site_id = SqlAlchemyProjectCreation(factory).create_project("Domain adapter project", None)
    adapter = SqlAlchemyDomainCreation(factory)
    try:
        with pytest.raises(ValueError, match="does not exist"):
            adapter.create_domain(2_000_000_000, "Missing", None)
        domain_id = adapter.create_domain(site_id, "  North  ", "")
        empty_id = adapter.create_domain(site_id, "   ", "description")
        with factory() as session:
            domain = session.get(Domain, domain_id); empty = session.get(Domain, empty_id)
            assert domain.site_id == site_id and domain.name == "North" and domain.description is None
            assert empty.name == "" and empty.description == "description"
        queries = SqlAlchemyProjectNavigationQueries(factory)
        context = queries.get_domain_context(domain_id)
        assert (context.domain_id, context.domain_name, context.site_id, context.site_name) == (domain_id, "North", site_id, "Domain adapter project")
        assert not queries.project_has_active_lines(site_id)
        with pytest.raises(ValueError, match="does not exist"):
            queries.get_domain_context(2_000_000_000)
    finally:
        cleanup_project(factory, site_id)


def test_concrete_report_query_preserves_actual_date_stored_scores_and_links(factory):
    site_id = SqlAlchemyProjectCreation(factory).create_project("Report integration project", None)
    domain_id = SqlAlchemyDomainCreation(factory).create_domain(site_id, "North", None)
    state = build_rich_state()
    production, contour = state.blast_events
    try:
        production.name = "PB-7"
        production.event_date = date(2026, 7, 1)
        contour.event_date = date(2026, 8, 7)
        actual = state.technical_cards[0].active_revision().actual_execution
        actual.actual_blast_date = date(2026, 8, 6).isoformat()
        actual.actual_block_volume_m3 = 1234
        actual.actual_total_explosive_mass_kg = 87
        actual.actual_total_drilling_length_m = 456
        area = state.assessment_areas[0]
        area.event_links[0].assessment_area_geometry_revision_id = area.active_geometry_revision_id
        area.event_links[0].geometry_revision_id = production.active_geometry_revision_id
        evaluation = state.evaluations[0].active_revision()
        evaluation.status = "completed"
        evaluation.design_achievement_index = .23
        evaluation.face_condition_index = .87
        evaluation.result_quadrant = "stored-quadrant"
        for dataset in state.datasets:
            ProjectLinesRepository(factory).add_dataset(site_id, dataset)
        ProjectLinesRepository(factory).set_active(site_id, state.active_dataset().id)
        AssessmentGraphSeeder(factory).seed_for_domain(domain_id, state)

        report = SqlAlchemyProjectReportQuery(factory).collect(site_id, date(2026, 8, 1), date(2026, 8, 31))
        assert [(row.event_type, row.report_date) for row in report.blasts] == [
            ("production", date(2026, 8, 6)), ("contour", date(2026, 8, 7))]
        production_row = report.blasts[0]
        assert (production_row.block_number, production_row.actual_volume_m3,
                production_row.actual_explosive_mass_kg, production_row.actual_drilling_length_m) == ("PB-7", 1234, 87, 456)
        assessment = report.assessments[0]
        assert assessment.dai == pytest.approx(.23) and assessment.fci == pytest.approx(.87)
        assert report.average_dai == pytest.approx(.23) and report.average_fci == pytest.approx(.87)
        assert assessment.production_blocks == ("PB-7",) and assessment.contour_blasts == ("BE-C",)
        assert SqlAlchemyProjectReportQuery(factory).collect(site_id, date(2026, 9, 1), date(2026, 9, 30)).blasts == ()
    finally:
        cleanup_project(factory, site_id)
