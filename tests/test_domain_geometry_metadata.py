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


def test_domain_geometry_is_part_of_immutable_mvp_baseline():
    path = Path("alembic/versions/0001_mvp_baseline.py")
    spec = spec_from_file_location("mvp_baseline", path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.revision == "0001_mvp_baseline"
    assert module.down_revision is None
    assert sorted(item.name for item in Path("alembic/versions").glob("*.py")) == [
        "0001_mvp_baseline.py", "0002_workflow_status.py", "0003_explosive_catalog.py", "0004_charge_presets.py"]


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
    assert "if dialog.exec():" in source and "replace_drawn" in source


def test_domain_geometry_edit_and_clear_present_persistence_errors():
    """Qt callbacks must not leak optimistic-concurrency conflicts."""
    import ast
    tree=ast.parse(Path("ui/pages/dashboards/domain_dashboard.py").read_text())
    methods={node.name:node for node in ast.walk(tree) if isinstance(node,ast.FunctionDef)}
    for name,persistence_method in (("edit_geometry","replace_drawn"),("clear_geometry","clear")):
        method=methods[name]
        handlers=[node for node in ast.walk(method) if isinstance(node,ast.Try)]
        assert any(any(isinstance(call,ast.Attribute) and call.attr==persistence_method
                       for call in ast.walk(handler)) and handler.handlers
                   for handler in handlers)
        assert any(isinstance(node,ast.Attribute) and node.attr=="warning"
                   for node in ast.walk(method))
