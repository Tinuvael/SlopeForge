"""Destructive Domain Geometry tests run only against an explicit disposable DB."""
import os
from datetime import datetime,timezone
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine,func,select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

URL=os.environ.get("SLOPEFORGE_TEST_DATABASE_URL")
if not URL: pytest.skip("SLOPEFORGE_TEST_DATABASE_URL is not set; Domain Geometry DB tests skipped",allow_module_level=True)
if "test" not in (make_url(URL).database or "").lower(): pytest.fail("Refusing destructive tests: database name must contain 'test'",pytrace=False)
from database.models import Domain,DomainGeometry,Mine,Site
from prototype_2d.domain import PlanPoint,PlanPolygon
from repositories.domain_geometry_repository import DomainGeometryRepository
from repositories.dashboard_repository import DashboardRepository
from database.assessment_models import ProjectLinesDataset


def polygon(offset=0):
    p=(PlanPoint(offset,0),PlanPoint(offset+2,0),PlanPoint(offset,2)); return PlanPolygon(p+(p[0],))

@pytest.fixture(scope="module")
def repository_context(tmp_path_factory):
    old_db,old_storage=os.getenv("DATABASE_URL"),os.getenv("STORAGE_ROOT")
    os.environ["DATABASE_URL"]=URL; os.environ["STORAGE_ROOT"]=str(tmp_path_factory.mktemp("domain-geometry-storage"))
    try: command.upgrade(Config("alembic.ini"),"head")
    finally:
        if old_db is None:os.environ.pop("DATABASE_URL",None)
        else:os.environ["DATABASE_URL"]=old_db
        if old_storage is None:os.environ.pop("STORAGE_ROOT",None)
        else:os.environ["STORAGE_ROOT"]=old_storage
    engine=create_engine(URL); factory=sessionmaker(engine,expire_on_commit=False)
    with factory.begin() as session:
        mine=Mine(name="Domain Geometry test mine"); session.add(mine); session.flush()
        site=Site(mine_id=mine.id,name="Domain Geometry test site"); session.add(site); session.flush()
        a=Domain(site_id=site.id,name="A"); b=Domain(site_id=site.id,name="B"); session.add_all((a,b)); session.flush(); ids=(mine.id,site.id,a.id,b.id)
    yield DomainGeometryRepository(factory),factory,ids
    with factory.begin() as session:
        session.query(DomainGeometry).filter(DomainGeometry.domain_id.in_(ids[2:])).delete(synchronize_session=False)
        session.query(ProjectLinesDataset).filter_by(site_id=ids[1]).delete()
        session.query(Domain).filter(Domain.id.in_(ids[2:])).delete(synchronize_session=False); session.query(Site).filter_by(id=ids[1]).delete(); session.query(Mine).filter_by(id=ids[0]).delete()
    engine.dispose()


def test_current_geometry_lifecycle_and_domain_isolation(repository_context):
    repo,factory,(_,_,a,b)=repository_context
    assert repo.get_for_domain(a) is None and repo.get_for_domain(b) is None
    first=repo.replace_imported(a,[polygon(),polygon(10)],"domains.dxf")
    assert first.polygons==(polygon(),polygon(10)) and first.source_kind=="imported" and first.source_file_name=="domains.dxf"
    assert repo.get_for_domain(a)==first and repo.get_for_domain(b) is None
    second=repo.replace_imported(a,[polygon(20)],"new.csv")
    assert second.polygons==(polygon(20),)
    drawn=repo.replace_drawn(a,[polygon(30)])
    assert drawn.source_kind=="drawn" and drawn.source_file_name is None
    with factory() as session: assert session.scalar(select(func.count()).select_from(DomainGeometry).where(DomainGeometry.domain_id==a))==1
    repo.clear(a); assert repo.get_for_domain(a) is None


def test_dashboard_domain_context_palette_and_project_lines(repository_context):
    repo,factory,(_,site,a,b)=repository_context
    repo.replace_drawn(a,[polygon()]); repo.replace_drawn(b,[polygon(10)])
    with factory.begin() as session:
        session.add(ProjectLinesDataset(site_id=site,domain_id="LINES",name="Lines",imported_at=datetime.now(timezone.utc),source_file_name="lines.csv",is_active=True,is_archived=False,lines_json=[{"source_id":"L","points":[{"x":0,"y":0,"z":0,"source_row_number":1},{"x":2,"y":3,"z":0,"source_row_number":2}]}]))
    dashboard=DashboardRepository(factory); domain=dashboard.domain_snapshot(a)
    assert [(g.domain_name,g.palette_index,g.is_current) for g in domain.domain_geometries]==[("A",0,True),("B",1,False)]
    site_snapshot=dashboard.site_snapshot(site)
    assert len(site_snapshot.domain_geometries)==2 and len(site_snapshot.project_lines)==1
    assert site_snapshot.production==0 and site_snapshot.contour==0 and site_snapshot.areas==0


def test_site_project_lines_exist_without_domains(repository_context):
    _,factory,(mine,_,_,_)=repository_context
    with factory.begin() as session:
        site=Site(mine_id=mine,name="Lines without domains"); session.add(site); session.flush(); site_id=site.id
        session.add(ProjectLinesDataset(site_id=site_id,domain_id="ONLY",name="Only",imported_at=datetime.now(timezone.utc),source_file_name="only.csv",is_active=True,is_archived=False,lines_json=[{"source_id":"L","points":[{"x":1,"y":1},{"x":2,"y":2}]}]))
    snapshot=DashboardRepository(factory).site_snapshot(site_id)
    assert snapshot.domains==[] and len(snapshot.project_lines)==1
    with factory.begin() as session:
        session.query(ProjectLinesDataset).filter_by(site_id=site_id).delete(); session.query(Site).filter_by(id=site_id).delete()
