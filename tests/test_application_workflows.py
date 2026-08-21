from datetime import date
from types import SimpleNamespace

import pytest

from application.use_cases.create_project import CreateProject, CreateProjectCommand
from application.use_cases.create_domain import CreateDomain, CreateDomainCommand
from application.use_cases.generate_project_report import GenerateProjectReport, GenerateProjectReportCommand


def project_command(**changes):
    values=dict(name=" Quarry ",description="face",optional_project_lines_path=None,actor_id=1,can_edit=True)
    values.update(changes); return CreateProjectCommand(**values)


class Projects:
    def __init__(self): self.created=[]
    def create_project(self,name,description): self.created.append((name,description)); return 17


class Lines:
    def __init__(self,prepare_error=None,save_error=None): self.prepare_error=prepare_error; self.save_error=save_error; self.saved=[]
    def prepare(self,path):
        if self.prepare_error: raise self.prepare_error
        return SimpleNamespace(id="D-001")
    def save_active(self,site_id,dataset):
        if self.save_error: raise self.save_error
        self.saved.append((site_id,dataset))


def test_create_project_permissions_prepare_order_and_partial_save_failure():
    projects=Projects(); lines=Lines()
    with pytest.raises(PermissionError): CreateProject(projects,lines).execute(project_command(can_edit=False))
    assert projects.created == []
    result=CreateProject(projects,lines).execute(project_command())
    assert result.site_id==17 and result.project_name=="Quarry" and not result.project_lines_requested
    projects=Projects(); lines=Lines(prepare_error=ValueError("bad geometry"))
    with pytest.raises(ValueError): CreateProject(projects,lines).execute(project_command(optional_project_lines_path="bad.csv"))
    assert projects.created == []
    projects=Projects(); lines=Lines(save_error=RuntimeError("database unavailable"))
    result=CreateProject(projects,lines).execute(project_command(optional_project_lines_path="lines.csv"))
    assert projects.created and result.project_created and not result.project_lines_saved
    assert result.site_id==17 and "database unavailable" in result.project_lines_warning


def test_create_domain_permission_and_contract():
    persistence=SimpleNamespace(create_domain=lambda site_id,name,description: 9)
    use_case=CreateDomain(persistence)
    with pytest.raises(PermissionError):
        use_case.execute(CreateDomainCommand(3,"D","text",1,False))
    result=use_case.execute(CreateDomainCommand(3," Domain ","text",1,True))
    assert (result.domain_id,result.site_id,result.domain_name)==(9,3,"Domain")


def test_generate_report_validates_then_collects_and_writes(tmp_path):
    calls=[]; report=object()
    query=SimpleNamespace(collect=lambda *args: calls.append(("collect",args)) or report)
    writer=SimpleNamespace(write=lambda *args: calls.append(("write",args)))
    use_case=GenerateProjectReport(query,writer); output=tmp_path/"report.xlsx"
    result=use_case.execute(GenerateProjectReportCommand(2,date(2026,1,1),date(2026,1,31),output))
    assert [item[0] for item in calls]==["collect","write"] and result.output_path==output.resolve()
    with pytest.raises(ValueError): use_case.execute(GenerateProjectReportCommand(2,date(2026,2,1),date(2026,1,1),output))


def test_navigation_query_returns_detached_context_and_active_lines():
    from infrastructure.db.project_navigation import SqlAlchemyProjectNavigationQueries
    query = SqlAlchemyProjectNavigationQueries.__new__(SqlAlchemyProjectNavigationQueries)
    site = SimpleNamespace(id=5, name="Project")
    query._domains = SimpleNamespace(get=lambda domain_id: SimpleNamespace(id=domain_id, name="North", site_id=5, site=site))
    query._lines = SimpleNamespace(get_active=lambda site_id: object() if site_id == 5 else None)
    context = query.get_domain_context(8)
    assert (context.domain_id, context.domain_name, context.site_id, context.site_name) == (8, "North", 5, "Project")
    assert query.project_has_active_lines(5) and not query.project_has_active_lines(6)
