"""Application orchestration for revisioned BlastEvent drillhole datasets."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Protocol
from uuid import uuid4

from domain.blasting.drillholes import (
    Drillhole,
    drillholes_from_lines,
    match_actual_to_design,
    summarize_drillholes,
)


class DrillholeRepositoryPort(Protocol):
    def add_dataset(self, domain_id: int, event_logical_id: str, **values: Any) -> Any: ...
    def update_holes(self, row_id: int, holes: list[dict[str, object]]) -> Any: ...
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
    def __init__(
        self,
        repository: DrillholeRepositoryPort,
        storage: DrillholeStoragePort,
        line_importer: Callable[[Path], Any],
    ):
        self.repository = repository
        self.storage = storage
        self.line_importer = line_importer

    @staticmethod
    def _logical_id() -> str:
        return f"DH-{uuid4().hex[:8].upper()}"

    @staticmethod
    def _source_format(path: Path) -> str:
        return "dxf" if path.suffix.lower() == ".dxf" else "datamine"

    @staticmethod
    def _holes_from_row(row) -> tuple[Drillhole, ...]:
        return tuple(Drillhole.from_dict(item) for item in row.holes_json)

    @classmethod
    def _carry_design_assignments(cls, previous_row, holes: tuple[Drillhole, ...]) -> None:
        """Preserve explicit group classification only across stable hole identities."""
        if previous_row is None:
            return
        previous = {
            hole.hole_id: hole.engineering_group_id
            for hole in cls._holes_from_row(previous_row)
            if hole.engineering_group_id
        }
        for hole in holes:
            group_id = previous.get(hole.hole_id)
            if group_id:
                hole.engineering_group_id = group_id

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
        imported = self.line_importer(path)
        # Geometry sources used in Studio can contain flat marker/reference
        # strings alongside real hole traces. Existing contour import already
        # excludes those rows; keep the same product semantics here.
        candidate_lines = [line for line in imported.lines if not line.is_horizontal]
        holes = drillholes_from_lines(candidate_lines)
        previous_design = None
        if dataset_kind == "design":
            previous_design = self.repository.get_current(domain_id, event_logical_id, "design")
            self._carry_design_assignments(previous_design, holes)
        summary = summarize_drillholes(holes)

        matches = []
        matched_design_dataset_id = None
        if dataset_kind == "actual":
            design_row = self.repository.get_current(domain_id, event_logical_id, "design")
            if design_row is None:
                raise ValueError("Import design drillholes before importing as-drilled holes")
            design_holes = self._holes_from_row(design_row)
            matches = [item.to_dict() for item in match_actual_to_design(design_holes, holes)]
            matched_design_dataset_id = int(design_row.id)

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
                matched_design_dataset_id=matched_design_dataset_id,
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
        row = self.repository.get_current(domain_id, event_logical_id, dataset_kind)
        if row is not None and dataset_kind == "actual":
            design = self.repository.get_current(domain_id, event_logical_id, "design")
            row.design_revision_current = (
                design is not None
                and row.matched_design_dataset_id is not None
                and int(row.matched_design_dataset_id) == int(design.id)
            )
        return row

    def actual_uses_current_design(self, domain_id: int, event_logical_id: str) -> bool:
        """True when current as-drilled QA was calculated against current design evidence."""
        actual = self.current(domain_id, event_logical_id, "actual")
        return actual is None or bool(getattr(actual, "design_revision_current", False))

    def current_holes(
        self,
        domain_id: int,
        event_logical_id: str,
        dataset_kind: str,
    ) -> tuple[Drillhole, ...]:
        row = self.current(domain_id, event_logical_id, dataset_kind)
        if row is None:
            return ()
        if dataset_kind == "actual" and not bool(getattr(row, "design_revision_current", False)):
            # Historical as-drilled geometry remains stored and reviewable in the
            # dataset row, but its QA must not be projected onto a newer design.
            return ()
        return self._holes_from_row(row)

    def assigned_holes(
        self,
        domain_id: int,
        event_logical_id: str,
        group_id: str,
    ) -> tuple[Drillhole, ...]:
        return tuple(
            hole
            for hole in self.current_holes(domain_id, event_logical_id, "design")
            if hole.engineering_group_id == group_id
        )

    def assign_design_holes(
        self,
        domain_id: int,
        event_logical_id: str,
        group_id: str,
        hole_ids: set[str] | list[str] | tuple[str, ...],
    ):
        row = self.current(domain_id, event_logical_id, "design")
        if row is None:
            raise ValueError("Import design drillholes before assigning engineering groups")
        group_id = str(group_id).strip()
        if not group_id:
            raise ValueError("Engineering group ID is required")
        selected = {str(value) for value in hole_ids}
        holes = list(self._holes_from_row(row))
        known = {hole.hole_id for hole in holes}
        unknown = sorted(selected - known)
        if unknown:
            raise ValueError(f"Unknown design drillhole ID(s): {', '.join(unknown)}")
        for hole in holes:
            if hole.hole_id in selected:
                hole.engineering_group_id = group_id
            elif hole.engineering_group_id == group_id:
                hole.engineering_group_id = None
        return self.repository.update_holes(row.id, [hole.to_dict() for hole in holes])

    def history(self, domain_id: int, event_logical_id: str):
        return self.repository.list_for_event(domain_id, event_logical_id)
