from pathlib import Path


def test_drillhole_reimport_appends_revision_instead_of_overwriting_source():
    repository = Path("repositories/drillhole_dataset_repository.py").read_text(encoding="utf-8")
    service = Path("application/services/drillhole_datasets.py").read_text(encoding="utf-8")
    assert "func.max(BlastEventDrillholeDataset.revision_number)" in repository
    assert "+ 1" in repository
    assert "copy_dataset(" in service
    assert "add_dataset(" in service
