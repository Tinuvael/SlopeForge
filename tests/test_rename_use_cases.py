import pytest

from application.use_cases.rename_domain import RenameDomain, RenameDomainCommand
from application.use_cases.rename_project import RenameProject, RenameProjectCommand


class Projects:
    def __init__(self): self.calls=[]
    def rename_project(self,site_id,name): self.calls.append((site_id,name)); return name


class Domains:
    def __init__(self): self.calls=[]
    def rename_domain(self,domain_id,name,version):
        self.calls.append((domain_id,name,version)); return 4,name,version+1


def test_project_rename_trims_and_enforces_permission_and_name():
    persistence=Projects(); use_case=RenameProject(persistence)
    result=use_case.execute(RenameProjectCommand(3,"  Central Pit  ",8,True))
    assert result.site_id==3 and result.project_name=="Central Pit"
    assert persistence.calls==[(3,"Central Pit")]
    with pytest.raises(PermissionError): use_case.execute(RenameProjectCommand(3,"X",8,False))
    with pytest.raises(ValueError): use_case.execute(RenameProjectCommand(3,"  ",8,True))


def test_domain_rename_passes_expected_version_and_returns_increment():
    persistence=Domains(); use_case=RenameDomain(persistence)
    result=use_case.execute(RenameDomainCommand(9," East Wall ",12,8,True))
    assert (result.domain_id,result.site_id,result.domain_name,result.new_version)==(9,4,"East Wall",13)
    assert persistence.calls==[(9,"East Wall",12)]
    with pytest.raises(PermissionError): use_case.execute(RenameDomainCommand(9,"X",12,8,False))
    with pytest.raises(ValueError): use_case.execute(RenameDomainCommand(9,"",12,8,True))
