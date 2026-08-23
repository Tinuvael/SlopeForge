from pathlib import Path

import pytest

from infrastructure.files.drillhole_geometry import (
    BlastEventDrillholeFileStorage,
    DrillholeGeometryStorageError,
)


def test_drillhole_source_is_copied_with_hash_and_verified(tmp_path: Path) -> None:
    source = tmp_path / "design.dmx"
    source.write_bytes(b"drillhole strings")
    storage = BlastEventDrillholeFileStorage(tmp_path / "data")

    stored = storage.copy_dataset(
        17,
        "BE-ABC123",
        "design",
        "DH-12345678",
        (source,),
    )[0]

    assert stored.original_filename == "design.dmx"
    assert stored.relative_path == (
        "files/domains/17/blast_events/BE-ABC123/drillholes/design/DH-12345678/design.dmx"
    )
    assert stored.file_size_bytes == len(b"drillhole strings")
    assert len(stored.sha256) == 64
    resolved = storage.verify(stored.to_dict())
    assert resolved.read_bytes() == b"drillhole strings"

    storage.remove_dataset(17, "BE-ABC123", "design", "DH-12345678")
    assert not storage.dataset_folder(
        17, "BE-ABC123", "design", "DH-12345678"
    ).exists()


def test_same_event_logical_id_in_different_domains_has_separate_storage(tmp_path: Path) -> None:
    source = tmp_path / "design.dxf"
    source.write_bytes(b"same event id")
    storage = BlastEventDrillholeFileStorage(tmp_path / "data")

    first = storage.copy_dataset(10, "BE-1", "design", "DH-1", (source,))[0]
    second = storage.copy_dataset(11, "BE-1", "design", "DH-1", (source,))[0]

    assert first.relative_path != second.relative_path
    assert "/domains/10/" in f"/{first.relative_path}"
    assert "/domains/11/" in f"/{second.relative_path}"
    assert storage.verify(first.to_dict()).is_file()
    assert storage.verify(second.to_dict()).is_file()


def test_drillhole_integrity_check_rejects_modified_file(tmp_path: Path) -> None:
    source = tmp_path / "actual.dxf"
    source.write_bytes(b"original")
    storage = BlastEventDrillholeFileStorage(tmp_path / "data")
    stored = storage.copy_dataset(
        7, "BE-1", "actual", "DH-87654321", (source,)
    )[0]
    destination = storage.resolve(stored.relative_path)
    destination.write_bytes(b"tampered")

    with pytest.raises(DrillholeGeometryStorageError, match="does not match metadata"):
        storage.verify(stored.to_dict())


def test_drillhole_storage_rejects_path_escape_and_bad_segments(tmp_path: Path) -> None:
    storage = BlastEventDrillholeFileStorage(tmp_path / "data")

    with pytest.raises(ValueError, match="escapes the data directory"):
        storage.resolve("../outside.dxf")
    with pytest.raises(ValueError, match="Invalid BlastEvent id"):
        storage.dataset_folder(7, "../BE-1", "design", "DH-1")
    with pytest.raises(ValueError, match="Unsupported drillhole dataset kind"):
        storage.dataset_folder(7, "BE-1", "other", "DH-1")


def test_failed_copy_removes_partial_dataset_folder(tmp_path: Path) -> None:
    source = tmp_path / "design.dxf"
    source.write_bytes(b"ok")
    missing = tmp_path / "missing.dxf"
    storage = BlastEventDrillholeFileStorage(tmp_path / "data")

    with pytest.raises(DrillholeGeometryStorageError, match="does not exist"):
        storage.copy_dataset(
            7,
            "BE-1",
            "design",
            "DH-FAIL",
            (source, missing),
        )

    assert not storage.dataset_folder(7, "BE-1", "design", "DH-FAIL").exists()
