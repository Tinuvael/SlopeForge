from sqlalchemy import CheckConstraint

from database.base import Base
from database import drillhole_models  # noqa: F401


def test_drillhole_dataset_belongs_directly_to_blast_event():
    table = Base.metadata.tables["blast_event_drillhole_datasets"]
    fk = next(iter(table.c.blast_event_id.foreign_keys))
    assert fk.target_fullname == "blast_events.id"
    assert fk.ondelete == "CASCADE"
    assert "blast_block_id" not in table.c


def test_actual_dataset_references_exact_design_dataset_revision():
    table = Base.metadata.tables["blast_event_drillhole_datasets"]
    provenance_fk = next(iter(table.c.matched_design_dataset_id.foreign_keys))
    assert provenance_fk.target_fullname == "blast_event_drillhole_datasets.id"
    assert provenance_fk.ondelete == "CASCADE"
    checks = " ".join(
        str(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    )
    assert "dataset_kind = 'design' AND matched_design_dataset_id IS NULL" in checks
    assert "dataset_kind = 'actual' AND matched_design_dataset_id IS NOT NULL" in checks
