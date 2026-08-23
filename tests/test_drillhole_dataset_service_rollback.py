from pathlib import Path
from types import SimpleNamespace

import pytest

from application.services.drillhole_datasets import BlastEventDrillholeDatasetService
from domain.geometry.types import DatamineLine, DataminePoint


class FailingRepository:
    def get_current(self, domain_id, event_id, dataset_kind):
        return None

    def add_dataset(self, domain_id, event_id, **values):
        raise RuntimeError("database write failed")


class TrackingStorage:
    def __init__(self):
        self.removed = []

    def copy_dataset(self, event_id, kind, logical_id, source_paths):
        return [
            SimpleNamespace(
                to_dict=lambda: {
                    "original_filename": Path(source_paths[0]).name,
                    "stored_filename": Path(source_paths[0]).name,
                    "relative_path": "files/source.dxf",
                    "file_size_bytes": 1,
                    "sha256": "a" * 64,
                }
            )
        ]

    def remove_dataset(self, event_id, kind, logical_id):
        self.removed.append((event_id, kind, logical_id))


def test_import_removes_copied_files_when_repository_write_fails(tmp_path: Path) -> None:
    source = tmp_path / "design.dxf"
    source.write_text("x")
    imported = SimpleNamespace(
        lines=[
            DatamineLine(
                "DXF-1",
                [
                    DataminePoint(0, 0, 630, 1),
                    DataminePoint(0, 0, 620, 2),
                ],
            )
        ]
    )
    storage = TrackingStorage()
    service = BlastEventDrillholeDatasetService(
        FailingRepository(),
        storage,
        lambda _path: imported,
    )

    with pytest.raises(RuntimeError, match="database write failed"):
        service.import_dataset(7, "BE-1", "design", source)

    assert len(storage.removed) == 1
    event_id, kind, logical_id = storage.removed[0]
    assert event_id == "BE-1"
    assert kind == "design"
    assert logical_id.startswith("DH-")
