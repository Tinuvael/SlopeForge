"""Application orchestration for revisioned BlastEvent drillhole datasets."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from domain.blasting.drillholes import (
    Drillhole,
    drillholes_from_lines,
    match_actual_to_design,
    summarize_drillholes,
)
from infrastructure.geometry_import.lines import import_line_geometry


class DrillholeRepositoryPort(Protocol):
    def add_dataset(self, domain_id: int, event_logical_id: str, **values: Any) -> Any: ...
    def get_current(self, domain_id: int, event_logical_id: str, dataset_kind: str) -> Any | None: ...
    def list_for_event(self, domain_id: int, event_logical_id: str, *, dataset_kind: str | None = None) -> list[Any]: ...


class DrillholeStoragePort(Protocol):
    def copy_dataset(
        self,
        event_logical_id: str,
        kind: str,
        logical_id: str,
        source_paths: tuple[Path, ...],
    ) -> list[Any]: ...
    def remove_dataset(self, event_logical_id: str, kind: str, logical_id: str) -> None: ...


class BlastEventDrillholeDatasetService:
    def __init__(self, repository: DrillholeRepositoryPort, storage: DrillholeStoragePort):
        self.repository = repository
        self.storage = storage

    @staticmethod
    def _logical_id() -> str:
        return f"DH-{uuid4().hex[:8].upper()}"

    @staticmethod
    def _source_format(path: Path) -> str:
        return "dxf" if path.suffix.lower() == ".dxf" else "datamine"

    @staticmethod
    def _holes_from_row(row) -> tuple[Drillhole, ...]:
        return tuple(Drillhole.from_dict(item) for item in row.holes_json)

    def import_dataset(
        self,
        domain_id: int,
        event_logical_id: str,
        dataset_kind: str,
        source_path: str | Path,
        *,
        imported_by_user_id: int | None = None,
    ):
        if dataset_kind not in {"design", "actual"}:
            raise ValueError(f"Unsupported drillhole dataset kind: {dataset_kind!r}")
        path = Path(source_path)
        imported = import_line_geometry(path)
        # Geometry sources used in Studio can contain flat marker/reference
        # strings alongside real hole traces. Existing contour import already
        # excludes those rows; keep the same product semantics here.
        candidate_lines = [line for line in imported.lines if not line.is_horizontal]
        holes = drillholes_from_lines(candidate_lines)
        summary = summarize_drillholes(holes)

        matches = []
        if dataset_kind == "actual":
            design_row = self.repository.get_current(domain_id, event_logical_id, "design")
            if design_row is None:
                raise ValueError("Import design drillholes before importing as-drilled holes")
            design_holes = self._holes_from_row(design_row)
            matches = [item.to_dict() for item in match_actual_to_design(design_holes, holes)]

        logical_id = self._logical_id()
        stored_files = self.storage.copy_dataset(
            event_logical_id,
            dataset_kind,
            logical_id,
            (path,),
        )
        try:
            row = self.repository.add_dataset(
                domain_id,
                event_logical_id,
                logical_id=logical_id,
                dataset_kind=dataset_kind,
                imported_at=datetime.now(timezone.utc),
                imported_by_user_id=imported_by_user_id,
                source_format=self._source_format(path),
                source_files=[item.to_dict() for item in stored_files],
                holes=[hole.to_dict() for hole in holes],
                summary=summary.to_dict(),
                matches=matches,
                hole_count=summary.hole_count,
                total_drilling_length_m=summary.total_drilling_length_m,
            )
        except Exception:
            self.storage.remove_dataset(event_logical_id, dataset_kind, logical_id)
            raise
        return row

    def current(self, domain_id: int, event_logical_id: str, dataset_kind: str):
        return self.repository.get_current(domain_id, event_logical_id, dataset_kind)

    def current_holes(
        self,
        domain_id: int,
        event_logical_id: str,
        dataset_kind: str,
    ) -> tuple[Drillhole, ...]:
        row = self.current(domain_id, event_logical_id, dataset_kind)
        return () if row is None else self._holes_from_row(row)

    def history(self, domain_id: int, event_logical_id: str):
        return self.repository.list_for_event(domain_id, event_logical_id)
