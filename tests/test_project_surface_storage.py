from pathlib import Path

import pytest

from infrastructure.files.project_geometry import (
    ProjectGeometryFileStorage,
    ProjectGeometryStorageError,
)


def test_project_surface_files_are_copied_outside_postgres_with_hashes(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    triangle = source_dir / "walltr.dmx"
    points = source_dir / "wallpt.dmx"
    triangle.write_bytes(b"triangle topology")
    points.write_bytes(b"point coordinates")

    data_root = tmp_path / "data"
    storage = ProjectGeometryFileStorage(data_root)
    stored = storage.copy_dataset(
        42,
        "design",
        "PG-ABCDEF12",
        (triangle, points),
    )

    assert [item.original_filename for item in stored] == ["walltr.dmx", "wallpt.dmx"]
    assert all(len(item.sha256) == 64 for item in stored)
    assert all(
        item.relative_path.startswith(
            "files/project_geometry/42/design/PG-ABCDEF12/"
        )
        for item in stored
    )
    assert [storage.resolve(item.relative_path).read_bytes() for item in stored] == [
        b"triangle topology",
        b"point coordinates",
    ]
    assert [
        storage.verify(
            item.relative_path,
            expected_size=item.file_size_bytes,
            expected_sha256=item.sha256,
        )
        for item in stored
    ] == [storage.resolve(item.relative_path) for item in stored]

    storage.remove_dataset(42, "design", "PG-ABCDEF12")
    assert not storage.dataset_folder(42, "design", "PG-ABCDEF12").exists()


def test_project_surface_integrity_check_rejects_modified_stored_file(
    tmp_path: Path,
) -> None:
    source = tmp_path / "surface.dxf"
    source.write_bytes(b"original")
    storage = ProjectGeometryFileStorage(tmp_path / "data")
    stored = storage.copy_dataset(1, "actual", "PG-12345678", (source,))[0]
    destination = storage.resolve(stored.relative_path)
    destination.write_bytes(b"tampered")

    with pytest.raises(ProjectGeometryStorageError, match="does not match metadata"):
        storage.verify(
            stored.relative_path,
            expected_size=stored.file_size_bytes,
            expected_sha256=stored.sha256,
        )
