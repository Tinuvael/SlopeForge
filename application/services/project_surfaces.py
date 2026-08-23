"""Application orchestration for revisioned Project design/actual surface datasets."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import uuid4

from sqlalchemy.orm import Session

from infrastructure.files.project_geometry import ProjectGeometryFileStorage
from infrastructure.geometry_import.surfaces import SurfaceImportResult, import_surface_geometry
from repositories.project_surface_repository import ProjectSurfaceDatasetRepository


class ProjectSurfaceDatasetService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        storage_root: Path,
    ):
        self.repository = ProjectSurfaceDatasetRepository(session_factory)
        self.storage = ProjectGeometryFileStorage(storage_root)

    @staticmethod
    def _logical_id() -> str:
        return f"PG-{uuid4().hex[:8].upper()}"

    def import_dataset(
        self,
        site_id: int,
        dataset_kind: str,
        source_path: str | Path,
        *,
        imported_by_user_id: int | None = None,
    ):
        if dataset_kind not in {"design", "actual"}:
            raise ValueError(f"Unsupported Project surface kind: {dataset_kind!r}")

        imported = import_surface_geometry(source_path)
        logical_id = self._logical_id()
        stored_files = self.storage.copy_dataset(
            site_id,
            dataset_kind,
            logical_id,
            imported.source_paths,
        )
        try:
            row = self.repository.add_dataset(
                site_id,
                logical_id=logical_id,
                dataset_kind=dataset_kind,
                imported_at=datetime.now(timezone.utc),
                imported_by_user_id=imported_by_user_id,
                source_format=imported.source_format,
                source_files=[item.to_dict() for item in stored_files],
                vertex_count=imported.vertex_count,
                triangle_count=imported.triangle_count,
            )
        except Exception:
            self.storage.remove_dataset(site_id, dataset_kind, logical_id)
            raise
        return row, imported

    def list_for_site(self, site_id: int):
        return self.repository.list_for_site(site_id)

    def current(self, site_id: int, dataset_kind: str):
        return self.repository.get_current(site_id, dataset_kind)

    def load_dataset(self, site_id: int, logical_id: str) -> tuple[object, SurfaceImportResult]:
        row = self.repository.get_by_logical_id(site_id, logical_id)
        paths = [
            self.storage.resolve(str(file_metadata["relative_path"]))
            for file_metadata in row.source_files_json
        ]
        if not paths:
            raise ValueError("Project surface dataset has no stored source files")
        result = import_surface_geometry(paths[0])
        return row, result

    def load_current(
        self, site_id: int, dataset_kind: str
    ) -> tuple[object, SurfaceImportResult] | None:
        row = self.repository.get_current(site_id, dataset_kind)
        if row is None:
            return None
        return self.load_dataset(site_id, row.logical_id)
