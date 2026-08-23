from database.base import Base
from database import drillhole_models  # noqa: F401


def test_drillhole_dataset_belongs_directly_to_blast_event():
    table = Base.metadata.tables["blast_event_drillhole_datasets"]
    fk = next(iter(table.c.blast_event_id.foreign_keys))
    assert fk.target_fullname == "blast_events.id"
    assert "blast_block_id" not in table.c
