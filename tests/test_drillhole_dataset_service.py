from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from application.services.drillhole_datasets import BlastEventDrillholeDatasetService
from domain.geometry.types import DatamineLine, DataminePoint


def line(source_id, points):
    return DatamineLine(
        source_id,
        [DataminePoint(x, y, z, index + 1) for index, (x, y, z) in enumerate(points)],
    )


class Stored:
    def __init__(self, path):
        self.path = Path(path)

    def to_dict(self):
        return {
            "original_filename": self.path.name,
            "stored_filename": self.path.name,
            "relative_path": f"files/{self.path.name}",
            "file_size_bytes": 1,
            "sha256": "abc",
        }


class MemoryStorage:
    def __init__(self):
        self.copied = []
        self.removed = []

    def copy_dataset(self, event_id, kind, logical_id, source_paths):
        self.copied.append((event_id, kind, logical_id, source_paths))
        return [Stored(path) for path in source_paths]

    def remove_dataset(self, event_id, kind, logical_id):
        self.removed.append((event_id, kind, logical_id))


class MemoryRepository:
    def __init__(self):
        self.rows = []
        self.next_id = 1

    def add_dataset(self, domain_id, event_id, **values):
        revision = 1 + max(
            (
                row.revision_number
                for row in self.rows
                if row.dataset_kind == values["dataset_kind"]
            ),
            default=0,
        )
        row = SimpleNamespace(
            id=self.next_id,
            revision_number=revision,
            matched_design_dataset_id=values["matched_design_dataset_id"],
            holes_json=values["holes"],
            summary_json=values["summary"],
            matches_json=values["matches"],
            source_files_json=values["source_files"],
            source_format=values["source_format"],
            dataset_kind=values["dataset_kind"],
            logical_id=values["logical_id"],
        )
        self.next_id += 1
        self.rows.append(row)
        return row

    def get_current(self, domain_id, event_id, dataset_kind):
        rows = [row for row in self.rows if row.dataset_kind == dataset_kind]
        return max(rows, key=lambda row: row.revision_number) if rows else None

    def list_for_event(self, domain_id, event_id, *, dataset_kind=None):
        return [
            row for row in self.rows
            if dataset_kind is None or row.dataset_kind == dataset_kind
        ]

    def update_holes(self, row_id, holes):
        row = next(row for row in self.rows if row.id == row_id)
        row.holes_json = holes
        return row


def importer_for(mapping):
    def importer(path):
        return SimpleNamespace(lines=mapping[Path(path).name])
    return importer


def test_design_import_ignores_flat_marker_strings_and_reimport_increments_revision(tmp_path):
    mapping = {
        "design.dxf": [
            line("H1", [(0,0,630),(0,0,620)]),
            line("MARKER", [(0,5,625),(10,5,625)]),
            line("H2", [(10,0,632),(10,0,622)]),
        ]
    }
    repo = MemoryRepository(); storage = MemoryStorage()
    service = BlastEventDrillholeDatasetService(repo, storage, importer_for(mapping))
    source = tmp_path / "design.dxf"; source.write_text("x")

    first = service.import_dataset(7, "BE-1", "design", source)
    second = service.import_dataset(7, "BE-1", "design", source)

    assert first.revision_number == 1 and second.revision_number == 2
    assert first.matched_design_dataset_id is None
    assert second.matched_design_dataset_id is None
    assert first.summary_json["hole_count"] == 2
    assert [item["hole_id"] for item in first.holes_json] == ["H1", "H2"]
    assert len(storage.copied) == 2


def test_actual_import_matches_current_design_revision_and_persists_qa(tmp_path):
    mapping = {
        "design.dxf": [
            line("D1", [(0,0,630),(0,0,620)]),
            line("D2", [(10,0,630),(10,0,620)]),
        ],
        "actual.dxf": [
            line("A1", [(0.2,0,631),(0.4,0,619)]),
            line("A2", [(10.1,0,630),(11,0,618)]),
        ],
    }
    repo = MemoryRepository(); storage = MemoryStorage()
    service = BlastEventDrillholeDatasetService(repo, storage, importer_for(mapping))
    design = tmp_path / "design.dxf"; design.write_text("d")
    actual = tmp_path / "actual.dxf"; actual.write_text("a")

    service.import_dataset(7, "BE-1", "design", design)
    current_design = service.import_dataset(7, "BE-1", "design", design)
    row = service.import_dataset(7, "BE-1", "actual", actual)

    assert row.matched_design_dataset_id == current_design.id
    paired = [item for item in row.matches_json if item["actual_hole_id"]]
    assert len(paired) == 2
    assert {item["match_method"] for item in paired} == {"matched_geometry_high_confidence"}
    assert {item["design_hole_id"] for item in paired} == {"D1", "D2"}
    assert all(item["collar_distance_xy_m"] is not None for item in paired)
    assert all(item["toe_deviation_3d_m"] is not None for item in paired)
    assert all(item["length_deviation_percent"] is not None for item in paired)


def test_actual_import_requires_design_dataset(tmp_path):
    source = tmp_path / "actual.dxf"; source.write_text("a")
    service = BlastEventDrillholeDatasetService(
        MemoryRepository(),
        MemoryStorage(),
        importer_for({"actual.dxf": [line("A", [(0,0,630),(0,0,620)])]}),
    )

    with pytest.raises(ValueError, match="design drillholes"):
        service.import_dataset(7, "BE-1", "actual", source)


def test_group_assignment_is_exclusive_and_can_clear_previous_membership(tmp_path):
    source = tmp_path / "design.dxf"; source.write_text("d")
    repo = MemoryRepository(); storage = MemoryStorage()
    service = BlastEventDrillholeDatasetService(
        repo,
        storage,
        importer_for({
            "design.dxf": [
                line("H1", [(0,0,630),(0,0,620)]),
                line("H2", [(5,0,630),(5,0,620)]),
                line("H3", [(10,0,630),(10,0,620)]),
            ]
        }),
    )
    service.import_dataset(7, "BE-1", "design", source)

    service.assign_design_holes(7, "BE-1", "MAIN", {"H1", "H2"})
    service.assign_design_holes(7, "BE-1", "BUFFER", {"H2", "H3"})

    main_ids = {hole.hole_id for hole in service.assigned_holes(7, "BE-1", "MAIN")}
    buffer_ids = {hole.hole_id for hole in service.assigned_holes(7, "BE-1", "BUFFER")}
    assert main_ids == {"H1"}
    assert buffer_ids == {"H2", "H3"}

    service.assign_design_holes(7, "BE-1", "BUFFER", {"H3"})
    assert {hole.hole_id for hole in service.assigned_holes(7, "BE-1", "BUFFER")} == {"H3"}
