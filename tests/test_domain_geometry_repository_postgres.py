"""Destructive Domain Geometry tests run only against an explicit disposable DB."""
import os
from datetime import datetime,timezone
import pytest

pytestmark = pytest.mark.postgres
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine,event,func,select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

URL=os.environ.get("TEST_DATABASE_URL")
if not URL: pytest.skip("TEST_DATABASE_URL is not set; Domain Geometry DB tests skipped",allow_module_level=True)
if "test" not in (make_url(URL).database or "").lower(): pytest.fail("Refusing destructive tests: database name must contain 'test'",pytrace=False)
from database.models import Domain,DomainGeometry,Site
from domain.geometry.types import PlanPoint, PlanPolygon
from repositories.domain_geometry_repository import DomainGeometryRepository
from repositories.dashboard_repository import DashboardRepository
from database.assessment_models import ProjectLinesDataset


def polygon(offset=0):
    p=(PlanPoint(offset,0),PlanPoint(offset+2,0),PlanPoint(offset,2)); return PlanPolygon(p+(p[0],))

@pytest.fixture
def repository_context(tmp_path):
    old_db,old_storage=os.getenv("DATABASE_URL"),os.getenv("STORAGE_ROOT")
    os.environ["DATABASE_URL"]=URL; os.environ["STORAGE_ROOT"]=str(tmp_path/"domain-geometry-storage")
    try: command.upgrade(Config("alembic.ini"),"head")
    finally:
        if old_db is None:os.environ.pop("DATABASE_URL",None)
        else:os.environ["DATABASE_URL"]=old_db
        if old_storage is None:os.environ.pop("STORAGE_ROOT",None)
        else:os.environ["STORAGE_ROOT"]=old_storage
    engine=create_engine(URL); factory=sessionmaker(engine,expire_on_commit=False)
    with factory.begin() as session:
        site=Site(name="Domain Geometry test site"); session.add(site); session.flush()
        a=Domain(site_id=site.id,name="A"); b=Domain(site_id=site.id,name="B"); session.add_all((a,b)); session.flush(); ids=(site.id,a.id,b.id)
    try:
        yield DomainGeometryRepository(factory),factory,ids
    finally:
        engine.dispose()


def test_current_geometry_lifecycle_and_domain_isolation(repository_context):
    repo,factory,(_,a,b)=repository_context
    assert repo.get_for_domain(a) is None and repo.get_for_domain(b) is None
    first=repo.replace_imported(a,0,[polygon(),polygon(10)],"domains.dxf")
    assert first.polygons==(polygon(),polygon(10)) and first.source_kind=="imported" and first.source_file_name=="domains.dxf"
    assert repo.get_for_domain(a)==first and repo.get_for_domain(b) is None
    second=repo.replace_imported(a,1,[polygon(20)],"new.csv")
    assert second.polygons==(polygon(20),)
    drawn=repo.replace_drawn(a,2,[polygon(30)])
    assert drawn.source_kind=="drawn" and drawn.source_file_name is None
    with factory() as session: assert session.scalar(select(func.count()).select_from(DomainGeometry).where(DomainGeometry.domain_id==a))==1
    repo.clear(a,3); assert repo.get_for_domain(a) is None


@pytest.mark.parametrize("invalid",[
    PlanPolygon((PlanPoint(0,0),PlanPoint(4,4),PlanPoint(0,4),PlanPoint(4,0),PlanPoint(0,0))),
    PlanPolygon((PlanPoint(0,0),PlanPoint(1,0),PlanPoint(2,0),PlanPoint(0,0))),
    PlanPolygon((PlanPoint(0,0),PlanPoint(2,0),PlanPoint(2,0),PlanPoint(0,2),PlanPoint(0,0))),
    PlanPolygon((PlanPoint(0,0),PlanPoint(float("nan"),0),PlanPoint(0,2),PlanPoint(0,0))),
    PlanPolygon((PlanPoint(0,0),PlanPoint(float("inf"),0),PlanPoint(0,2),PlanPoint(0,0))),
    PlanPolygon((PlanPoint(0,0),PlanPoint(2,float("-inf")),PlanPoint(0,2),PlanPoint(0,0))),
])
def test_invalid_replacement_is_rejected_without_changing_existing_geometry(repository_context,invalid):
    repo,_,(_,domain_id,_)=repository_context
    existing=repo.replace_drawn(domain_id,0,[polygon(100)])
    with pytest.raises(ValueError): repo.replace_drawn(domain_id,1,[invalid])
    assert repo.get_for_domain(domain_id)==existing


def test_dashboard_domain_context_palette_and_project_lines(repository_context):
    repo,factory,(site,a,b)=repository_context
    repo.replace_drawn(a,0,[polygon()]); repo.replace_drawn(b,0,[polygon(10)])
    with factory.begin() as session:
        session.add(ProjectLinesDataset(site_id=site,logical_id="LINES",name="Lines",imported_at=datetime.now(timezone.utc),source_file_name="lines.csv",is_active=True,is_archived=False,lines_json=[{"source_id":"L","points":[{"x":0,"y":0,"z":0,"source_row_number":1},{"x":2,"y":3,"z":0,"source_row_number":2}]}]))
    dashboard=DashboardRepository(factory); domain=dashboard.domain_snapshot(a)
    assert [(g.domain_name,g.palette_index,g.is_current) for g in domain.domain_geometries]==[("A",0,True),("B",1,False)]
    site_snapshot=dashboard.site_snapshot(site)
    assert len(site_snapshot.domain_geometries)==2 and len(site_snapshot.project_lines)==1
    assert site_snapshot.production==0 and site_snapshot.contour==0 and site_snapshot.areas==0


def test_site_snapshot_loads_site_domain_geometry_once(repository_context):
    repo,factory,(site,a,b)=repository_context
    repo.replace_drawn(a,0,[polygon()]); repo.replace_imported(b,0,[polygon(10)],"domains.csv")
    statements=[]
    engine=factory.kw["bind"]
    def capture(_connection,_cursor,statement,_parameters,_context,_executemany):
        if "domain_geometries" in statement.lower(): statements.append(statement)
    event.listen(engine,"before_cursor_execute",capture)
    try: snapshot=DashboardRepository(factory).site_snapshot(site)
    finally: event.remove(engine,"before_cursor_execute",capture)
    assert len(statements)==1
    assert len(snapshot.domains)==2
    assert [g.is_current for g in snapshot.domains[0].domain_geometries]==[True,False]
    assert [g.is_current for g in snapshot.domains[1].domain_geometries]==[False,True]
    assert snapshot.domains[1].geometry_source_file_name=="domains.csv"


def test_site_project_lines_exist_without_domains(repository_context):
    _,factory,(_,_,_)=repository_context
    with factory.begin() as session:
        site=Site(name="Lines without domains"); session.add(site); session.flush(); site_id=site.id
        session.add(ProjectLinesDataset(site_id=site_id,logical_id="ONLY",name="Only",imported_at=datetime.now(timezone.utc),source_file_name="only.csv",is_active=True,is_archived=False,lines_json=[{"source_id":"L","points":[{"x":1,"y":1},{"x":2,"y":2}]}]))
    snapshot=DashboardRepository(factory).site_snapshot(site_id)
    assert snapshot.domains==[] and len(snapshot.project_lines)==1
