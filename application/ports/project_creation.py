"""Narrow boundaries used while creating a user-facing Project."""
from __future__ import annotations

from typing import Protocol

from domain.project.project_lines import ProjectLinesDataset


class ProjectCreation(Protocol):
    def create_project(self, name: str, description: str | None = None) -> int: ...


class ProjectLinesCreationSupport(Protocol):
    def prepare(self, source_path: str) -> ProjectLinesDataset: ...
    def save_active(self, site_id: int, dataset: ProjectLinesDataset) -> None: ...
