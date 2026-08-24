"""Physical file storage for revisioned BlastEvent drillhole datasets."""
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


class DrillholeGeometryStorageError(OSError):
    pass


@dataclass(frozen=True)
class StoredDrillholeGeometryFile:
    original_filename: str
    stored_filename: str
    relative_path: str
    file_size_bytes: int
    sha256: str

    def to_dict(self) -> dict[str, object]:
        return {
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "relative_path": self.relative_path,
            "file_size_bytes": self.file_size_bytes,
            "sha256": self.sha256,
        }


class BlastEventDrillholeFileStorage:
    def __init__(self, data_root: Path):
        self.data_root = Path(data_root)

    @staticmethod
    def _safe_segment(value: str, label: str) -> str:
        segment = str(value).strip()
        if not segment or Path(segment).name != segment or segment in {".", ".."}:
            raise ValueError(f"Invalid {label}")
        return segment

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def dataset_folder(
        self,
        domain_id: int,
        event_logical_id: str,
        kind: str,
        logical_id: str,
    ) -> Path:
        if kind not in {"design", "actual"}:
            raise ValueError(f"Unsupported drillhole dataset kind: {kind!r}")
        domain_segment = self._safe_segment(str(int(domain_id)), "Domain id")
        event_id = self._safe_segment(event_logical_id, "BlastEvent id")
        dataset_id = self._safe_segment(logical_id, "drillhole dataset id")
        return (
            self.data_root
            / "files"
            / "domains"
            / domain_segment
            / "blast_events"
            / event_id
            / "drillholes"
            / kind
            / dataset_id
        )

    def copy_dataset(
        self,
        domain_id: int,
        event_logical_id: str,
        kind: str,
        logical_id: str,
        source_paths: tuple[Path, ...],
    ) -> list[StoredDrillholeGeometryFile]:
        if not source_paths:
            raise DrillholeGeometryStorageError("Drillhole dataset has no source files")
        folder = self.dataset_folder(domain_id, event_logical_id, kind, logical_id)
        if folder.exists():
            raise DrillholeGeometryStorageError(
                f"Drillhole dataset storage already exists: {logical_id}"
            )
        folder.mkdir(parents=True, exist_ok=False)
        stored: list[StoredDrillholeGeometryFile] = []
        used_names: set[str] = set()
        try:
            for source in source_paths:
                source = Path(source)
                if not source.is_file():
                    raise DrillholeGeometryStorageError(
                        f"Drillhole geometry source file does not exist: {source}"
                    )
                name = Path(source.name).name.strip()
                if not name or name.casefold() in used_names:
                    raise DrillholeGeometryStorageError(
                        f"Invalid or duplicate drillhole source filename: {name!r}"
                    )
                used_names.add(name.casefold())
                destination = folder / name
                shutil.copy2(source, destination)
                stored.append(
                    StoredDrillholeGeometryFile(
                        original_filename=source.name,
                        stored_filename=destination.name,
                        relative_path=destination.relative_to(self.data_root).as_posix(),
                        file_size_bytes=destination.stat().st_size,
                        sha256=self.sha256(destination),
                    )
                )
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        return stored

    def resolve(self, relative_path: str) -> Path:
        root = self.data_root.resolve()
        path = (self.data_root / relative_path).resolve()
        if path != root and root not in path.parents:
            raise ValueError("Drillhole file path escapes the data directory")
        return path

    def verify(self, metadata: dict[str, object]) -> Path:
        relative_path = str(metadata["relative_path"])
        path = self.resolve(relative_path)
        if not path.is_file():
            raise DrillholeGeometryStorageError(
                f"Stored drillhole geometry file is missing: {relative_path}"
            )
        if path.stat().st_size != int(metadata["file_size_bytes"]):
            raise DrillholeGeometryStorageError(
                f"Stored drillhole geometry file size does not match metadata: {path.name}"
            )
        if self.sha256(path).lower() != str(metadata["sha256"]).lower():
            raise DrillholeGeometryStorageError(
                f"Stored drillhole geometry file hash does not match metadata: {path.name}"
            )
        return path

    def remove_dataset(
        self,
        domain_id: int,
        event_logical_id: str,
        kind: str,
        logical_id: str,
    ) -> None:
        folder = self.dataset_folder(domain_id, event_logical_id, kind, logical_id)
        if folder.exists():
            shutil.rmtree(folder)
