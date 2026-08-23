"""Physical file storage for revisioned Project design/actual surfaces."""
from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


class ProjectGeometryStorageError(OSError):
    pass


@dataclass(frozen=True)
class StoredProjectGeometryFile:
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


class ProjectGeometryFileStorage:
    def __init__(self, data_root: Path):
        self.data_root = Path(data_root)

    @staticmethod
    def _safe_filename(path: Path) -> str:
        name = Path(path.name).name.strip()
        if not name or name in {".", ".."}:
            raise ProjectGeometryStorageError("Invalid Project geometry source filename")
        return name

    def dataset_folder(self, site_id: int, kind: str, logical_id: str) -> Path:
        if kind not in {"design", "actual"}:
            raise ValueError(f"Unsupported Project surface kind: {kind!r}")
        safe_id = str(logical_id).strip()
        if not safe_id or Path(safe_id).name != safe_id:
            raise ValueError("Invalid Project surface dataset id")
        return (
            self.data_root
            / "files"
            / "project_geometry"
            / str(int(site_id))
            / kind
            / safe_id
        )

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with Path(path).open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def copy_dataset(
        self,
        site_id: int,
        kind: str,
        logical_id: str,
        source_paths: tuple[Path, ...],
    ) -> list[StoredProjectGeometryFile]:
        if not source_paths:
            raise ProjectGeometryStorageError("Project surface dataset has no source files")
        folder = self.dataset_folder(site_id, kind, logical_id)
        if folder.exists():
            raise ProjectGeometryStorageError(
                f"Project surface dataset storage already exists: {logical_id}"
            )
        folder.mkdir(parents=True, exist_ok=False)
        stored: list[StoredProjectGeometryFile] = []
        used_names: set[str] = set()
        try:
            for source in source_paths:
                source = Path(source)
                if not source.is_file():
                    raise ProjectGeometryStorageError(
                        f"Project geometry source file does not exist: {source}"
                    )
                filename = self._safe_filename(source)
                if filename.casefold() in used_names:
                    raise ProjectGeometryStorageError(
                        f"Duplicate Project geometry source filename: {filename}"
                    )
                used_names.add(filename.casefold())
                destination = folder / filename
                shutil.copy2(source, destination)
                if not destination.is_file():
                    raise ProjectGeometryStorageError(
                        f"Could not copy Project geometry file: {filename}"
                    )
                stored.append(
                    StoredProjectGeometryFile(
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
            raise ValueError("Project geometry file path escapes the data directory")
        return path

    def verify(
        self,
        relative_path: str,
        *,
        expected_size: int,
        expected_sha256: str,
    ) -> Path:
        path = self.resolve(relative_path)
        if not path.is_file():
            raise ProjectGeometryStorageError(
                f"Stored Project geometry file is missing: {relative_path}"
            )
        if path.stat().st_size != int(expected_size):
            raise ProjectGeometryStorageError(
                f"Stored Project geometry file size does not match metadata: {path.name}"
            )
        if self.sha256(path).lower() != str(expected_sha256).lower():
            raise ProjectGeometryStorageError(
                f"Stored Project geometry file hash does not match metadata: {path.name}"
            )
        return path

    def remove_dataset(self, site_id: int, kind: str, logical_id: str) -> None:
        folder = self.dataset_folder(site_id, kind, logical_id)
        if folder.exists():
            shutil.rmtree(folder)
