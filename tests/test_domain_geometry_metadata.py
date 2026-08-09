from importlib.util import module_from_spec,spec_from_file_location
from pathlib import Path
from sqlalchemy import CheckConstraint,UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from database.base import Base
from database.models import DomainGeometry
from repositories.dashboard_repository import MapGeometry,SiteDashboardSnapshot,_project_line_geometries


def test_domain_geometry_metadata_contract():
    table=Base.metadata.tables[DomainGeometry.__tablename__]
    assert table.name=="domain_geometries"
    assert isinstance(table.c.polygons_json.type,JSONB)
    assert any(isinstance(c,UniqueConstraint) and {x.name for x in c.columns}=={"domain_id"} for c in table.constraints)
    foreign_key=next(iter(table.c.domain_id.foreign_keys))
    assert foreign_key.target_fullname=="domains.id" and foreign_key.ondelete=="CASCADE"
    checks={c.name:str(c.sqltext) for c in table.constraints if isinstance(c,CheckConstraint)}
    assert "source_kind" in checks["ck_domain_geometries_source_kind"]
    assert "jsonb_typeof" in checks["ck_domain_geometries_polygons_array"]


def test_domain_geometry_migration_parent_and_single_head():
    path=Path("alembic/versions/20260809_0008_add_domain_geometry.py")
    spec=spec_from_file_location("domain_geometry_migration",path); module=module_from_spec(spec); spec.loader.exec_module(module)
    assert module.revision=="20260809_0008" and module.down_revision=="20260807_0007"
    revisions={}
    for migration in Path("alembic/versions").glob("*.py"):
        text=migration.read_text()
        import re
        revision=re.search(r'^revision\s*=\s*["\']([^"\']+)',text,re.M)
        down=re.search(r'^down_revision\s*=\s*["\']([^"\']+)',text,re.M)
        if revision: revisions[revision.group(1)]=down.group(1) if down else None
    assert set(revisions)-{parent for parent in revisions.values() if parent}=={"20260809_0008"}


def test_project_lines_are_project_owned_and_independent_of_domains():
    dataset=type("Dataset",(),{"lines_json":[{"source_id":"L1","points":[{"x":0,"y":0},{"x":2,"y":3}]}]})()
    lines=_project_line_geometries(dataset)
    snapshot=SiteDashboardSnapshot(1,[],dataset,[dataset],project_lines=lines)
    assert snapshot.domains==[] and snapshot.project_lines==(MapGeometry("L1",((0.0,0.0),(2.0,3.0))),)
    source=Path("ui/pages/dashboards/site_dashboard.py").read_text()
    assert "project_lines=self.snapshot.project_lines" in source
    assert "domains[0].project_lines" not in source


def test_domain_dashboard_permissions_and_import_filter_are_explicit():
    source=Path("ui/pages/dashboards/domain_dashboard.py").read_text()
    assert 'tr("Import geometry")' in source and 'tr("Draw geometry")' in source
    assert 'tr("Edit boundaries")' in source and 'tr("Clear geometry")' in source
    assert 'can_edit=getattr(getattr(self.context,"current_user",None),"can_edit",False)' in source
    assert 'bool(current) and can_edit' in source
    assert "*.csv *.dxf" in source
    # Persistence is deliberately guarded by modal acceptance.
    assert "if dialog.exec(): self.geometry_repo.replace_drawn" in source
