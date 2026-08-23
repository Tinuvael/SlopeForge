"""Versioned Project Lines datasets shared by a Project's Domains."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from infrastructure.geometry_import.lines import LineGeometryImportResult, import_line_geometry
from domain.blasting.entities import utc_now
from domain.project.project_lines import ProjectLinesDataset
from application.state.assessment_domain_state import AssessmentDomainState
from domain.geometry.types import DatamineLine


class ProjectLinesImportError(ValueError):
    """The source file cannot produce a usable Project Lines Dataset."""


class ProjectLinesDatasetService:
    """Create datasets, retain their history, and select the active version."""

    def __init__(self, state: AssessmentDomainState):
        self.state = state

    def import_dataset(
        self,
        source_path: str | Path,
        *,
        name: str | None = None,
        imported_at: datetime | None = None,
    ) -> tuple[ProjectLinesDataset, LineGeometryImportResult]:
        path = Path(source_path)
        result = import_line_geometry(path)
        usable_lines = [line for line in result.lines if len(line.points) >= 2]
        if not usable_lines:
            raise ProjectLinesImportError("Geometry file contains no suitable lines")
        dataset = self.create_dataset(
            name=name or path.stem,
            source_file_name=path.name,
            lines=usable_lines,
            imported_at=imported_at,
        )
        return dataset, result

    def create_dataset(
        self,
        *,
        name: str,
        source_file_name: str,
        lines: list[DatamineLine],
        imported_at: datetime | None = None,
    ) -> ProjectLinesDataset:
        dataset = ProjectLinesDataset(
            id=self._next_id(),
            name=name.strip() or source_file_name,
            imported_at=imported_at or utc_now(),
            source_file_name=source_file_name,
            is_active=False,
            lines=[DatamineLine.from_dict(line.to_dict()) for line in lines],
        )
        self.state.add_dataset(dataset)
        return dataset

    def set_active(self, dataset_id: str) -> ProjectLinesDataset:
        selected = next((item for item in self.state.datasets if item.id == dataset_id), None)
        if selected is None:
            raise ValueError(f"Dataset {dataset_id!r} was not found")
        for dataset in self.state.datasets:
            dataset.is_active = dataset is selected
        return selected

    def active_dataset(self) -> ProjectLinesDataset | None:
        return self.state.active_dataset()

    def available_elevations(self) -> list[float]:
        dataset = self.active_dataset()
        if dataset is None:
            return []
        return sorted({float(line.elevation) for line in dataset.lines if line.is_horizontal and line.elevation is not None})

    def _next_id(self) -> str:
        used = {dataset.id for dataset in self.state.datasets}
        number = 1
        while f"D-{number:03d}" in used:
            number += 1
        return f"D-{number:03d}"
