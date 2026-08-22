"""Focused integration checks for shared Site Project Lines (safe test DB only)."""
from __future__ import annotations

from datetime import datetime, timezone
import os

import pytest

pytestmark = pytest.mark.postgres
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

URL = os.environ.get("TEST_DATABASE_URL")
if not URL:
    pytest.skip("TEST_DATABASE_URL is not set", allow_module_level=True)
if "test" not in (make_url(URL).database or "").lower():
    pytest.fail("Refusing destructive Project Lines tests outside a test database", pytrace=False)

from database.models import Domain, Site
from domain.project.project_lines import ProjectLinesDataset
from application.state.assessment_domain_state import AssessmentDomainState
from application.services.project_lines import (
    ProjectLinesDatasetService,
    ProjectLinesImportError,
)
from repositories.assessment_state_repository import AssessmentStateRepository
from repositories.project_lines_repository import ProjectLinesRepository
import ezdxf


@pytest.fixture
def context():
    engine = create_engine(URL)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory.begin() as session:
        north_site = Site(name="Site A")
        other_site = Site(name="Site B")
        session.add_all([north_site, other_site]); session.flush()
        north = Domain(site_id=north_site.id, name="North")
        south = Domain(site_id=north_site.id, name="South")
        other = Domain(site_id=other_site.id, name="Other")
        session.add_all([north, south, other]); session.flush()
        ids = north_site.id, other_site.id, north.id, south.id, other.id
    try:
        yield factory, ids
    finally:
        engine.dispose()


def dataset(dataset_id: str) -> ProjectLinesDataset:
    return ProjectLinesDataset(dataset_id, dataset_id, datetime.now(timezone.utc),
                               f"{dataset_id}.csv", True, [])


def test_add_list_activate_archive_restore_and_stable_pk(context):
    factory, ids = context
    repo = ProjectLinesRepository(factory)
    first = repo.add_dataset(ids[0], dataset("D-X"))
    second = repo.add_dataset(ids[0], dataset("D-Y"))
    assert [row.logical_id for row in repo.list_for_site(ids[0])] == ["D-X", "D-Y"]
    assert repo.get_active(ids[0]) is None
    repo.set_active(ids[0], "D-X")
    assert repo.get_active(ids[0]).id == first.id
    repo.archive(ids[0], "D-X")
    assert repo.get_active(ids[0]) is None
    with pytest.raises(ValueError, match="Archived"):
        repo.set_active(ids[0], "D-X")
    repo.restore(ids[0], "D-X")
    repo.set_active(ids[0], "D-X")
    assert repo.get_active(ids[0]).id == first.id
    assert second.id != first.id


def test_atomic_import_rolls_back_row_when_activation_fails(context, monkeypatch):
    factory, ids = context
    repo = ProjectLinesRepository(factory)
    repo.import_dataset(ids[0], dataset("D-X"), make_active=True)

    def fail_activation(session, site_id, row):
        raise RuntimeError("injected activation failure")

    monkeypatch.setattr(ProjectLinesRepository, "_activate_imported_dataset",
                        staticmethod(fail_activation))
    with pytest.raises(RuntimeError, match="activation failure"):
        repo.import_dataset(ids[0], dataset("D-FAILED"), make_active=True)

    assert [row.logical_id for row in repo.list_for_site(ids[0])] == ["D-X"]
    assert repo.get_active(ids[0]).logical_id == "D-X"


def test_repeated_dashboard_style_import_allocates_new_site_dataset_id(context):
    factory, ids = context
    repo = ProjectLinesRepository(factory)
    first = dataset("D-001")
    second = dataset("D-001")

    repo.import_dataset(ids[0], first, make_active=True)
    repo.import_dataset(ids[0], second, make_active=True)

    rows = repo.list_for_site(ids[0])
    assert [row.logical_id for row in rows] == ["D-001", "D-002"]
    assert first.id == "D-001" and second.id == "D-002"
    assert [row.source_file_name for row in rows] == ["D-001.csv", "D-001.csv"]
    assert sum(row.is_active for row in rows) == 1
    assert not rows[0].is_active and rows[1].is_active


def test_empty_import_does_not_change_persisted_active_dataset(context, monkeypatch):
    factory, ids = context
    repo = ProjectLinesRepository(factory)
    repo.import_dataset(ids[0], dataset("D-001"), make_active=True)
    monkeypatch.setattr(
        "application.services.project_lines.import_line_geometry",
        lambda *args, **kwargs: type("EmptyResult", (), {"lines": []})(),
    )

    with pytest.raises(ProjectLinesImportError, match="no suitable lines"):
        ProjectLinesDatasetService(AssessmentDomainState()).import_dataset("empty.dxf")

    rows = repo.list_for_site(ids[0])
    assert len(rows) == 1 and rows[0].logical_id == "D-001" and rows[0].is_active


def test_degenerate_dxf_does_not_change_persisted_active_dataset(context, tmp_path):
    factory, ids = context
    repo = ProjectLinesRepository(factory)
    repo.import_dataset(ids[0], dataset("D-001"), make_active=True)
    document = ezdxf.new()
    document.modelspace().add_lwpolyline(
        [(0, 0)], dxfattribs={"elevation": 610}
    )
    source = tmp_path / "one-vertex.dxf"
    document.saveas(source)

    with pytest.raises(ProjectLinesImportError, match="no suitable lines"):
        ProjectLinesDatasetService(AssessmentDomainState()).import_dataset(source)

    rows = repo.list_for_site(ids[0])
    assert len(rows) == 1 and rows[0].logical_id == "D-001" and rows[0].is_active


def test_csv_to_dxf_and_same_file_reimports_create_history(context, tmp_path):
    factory, ids = context
    repo = ProjectLinesRepository(factory)
    csv_path = tmp_path / "project.csv"
    csv_path.write_text("X,Y,Z,SID\n0,0,600,L1\n1,0,600,L1\n", encoding="utf-8")
    document = ezdxf.new()
    document.modelspace().add_lwpolyline(
        [(0, 0), (2, 0)], dxfattribs={"elevation": 610}
    )
    dxf_path = tmp_path / "project.dxf"
    document.saveas(dxf_path)

    sources = (csv_path, dxf_path, dxf_path)
    datasets = []
    for source in sources:
        imported, _ = ProjectLinesDatasetService(
            AssessmentDomainState()
        ).import_dataset(source)
        repo.import_dataset(ids[0], imported, make_active=True)
        datasets.append(imported)

    rows = repo.list_for_site(ids[0])
    assert [row.logical_id for row in rows] == ["D-001", "D-002", "D-003"]
    assert [item.id for item in datasets] == ["D-001", "D-002", "D-003"]
    assert [row.source_file_name for row in rows] == [
        "project.csv", "project.dxf", "project.dxf"
    ]
    assert [row.is_active for row in rows] == [False, False, True]


def test_domains_share_one_site_history_but_sites_are_isolated(context):
    factory, ids = context
    lines = ProjectLinesRepository(factory)
    lines.add_dataset(ids[0], dataset("D-X")); lines.set_active(ids[0], "D-X")
    lines.add_dataset(ids[1], dataset("D-OTHER")); lines.set_active(ids[1], "D-OTHER")
    assessments = AssessmentStateRepository(factory)
    north = assessments.load_for_domain(ids[2])
    south = assessments.load_for_domain(ids[3])
    other = assessments.load_for_domain(ids[4])
    assert [item.id for item in north.state.datasets] == ["D-X"]
    assert [item.id for item in south.state.datasets] == ["D-X"]
    assert north.state.active_dataset().id == south.state.active_dataset().id == "D-X"
    assert [item.id for item in other.state.datasets] == ["D-OTHER"]
