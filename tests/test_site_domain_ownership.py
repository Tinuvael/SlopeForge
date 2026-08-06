from sqlalchemy.orm import configure_mappers

from database import assessment_models
from database.models import BlastBlock, Domain, Mine, Site


def test_mine_site_domain_orm_relationships_and_ownership_columns():
    configure_mappers()
    assert Mine.sites.property.back_populates == "mine"
    assert Site.domains.property.back_populates == "site"
    assert Domain.site.property.back_populates == "domains"
    assert Domain.blast_blocks.property.back_populates == "domain"
    assert Domain.assessment_workspace.property.uselist is False
    assert BlastBlock.domain.property.back_populates == "blast_blocks"
    assert "domain_id" in BlastBlock.__table__.c and "site_id" not in BlastBlock.__table__.c
    assert "domain_id" in assessment_models.AssessmentWorkspace.__table__.c
    assert "site_id" not in assessment_models.AssessmentWorkspace.__table__.c
    assert "site_id" in assessment_models.ProjectLinesDataset.__table__.c
    assert "workspace_id" not in assessment_models.ProjectLinesDataset.__table__.c


def test_domain_name_and_site_dataset_constraints_are_site_scoped():
    domain_unique = {tuple(column.name for column in constraint.columns)
                     for constraint in Domain.__table__.constraints
                     if constraint.__class__.__name__ == "UniqueConstraint"}
    dataset_unique = {tuple(column.name for column in constraint.columns)
                      for constraint in assessment_models.ProjectLinesDataset.__table__.constraints
                      if constraint.__class__.__name__ == "UniqueConstraint"}
    assert ("site_id", "name") in domain_unique
    assert ("site_id", "domain_id") in dataset_unique
    active = [index for index in assessment_models.ProjectLinesDataset.__table__.indexes
              if index.unique]
    assert len(active) == 1
    assert tuple(column.name for column in active[0].columns) == ("site_id",)


def test_domain_snapshot_dataset_sync_never_changes_site_activation():
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from prototype_2d.domain import ProjectLinesDataset
    from repositories.assessment_state_repository import AssessmentStateRepository

    active = SimpleNamespace(domain_id="Y", name="Y", imported_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
                             source_file_name="y.csv", lines_json=[], is_active=True)
    stale = ProjectLinesDataset("Y", "Y", active.imported_at, "y.csv", False, [])

    class Session:
        def scalars(self, statement): return [active]
        def add(self, row): raise AssertionError("existing immutable version must not be recreated")
        def flush(self): pass

    rows = AssessmentStateRepository._sync_site_datasets(Session(), 10, [stale])
    assert rows["Y"] is active
    assert active.is_active is True
