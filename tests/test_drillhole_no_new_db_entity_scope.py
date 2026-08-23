from database.base import Base
from database import drillhole_models  # noqa: F401


def test_feature_adds_only_revisioned_event_drillhole_dataset_table():
    drillhole_tables = [name for name in Base.metadata.tables if "drillhole" in name]
    assert drillhole_tables == ["blast_event_drillhole_datasets"]
