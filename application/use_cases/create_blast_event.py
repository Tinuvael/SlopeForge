"""Application workflow for creating one Blast Event header."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from application.services.blast_events import BlastEventService
from application.ports.assessment_state import AssessmentStateSnapshot
from domain.blasting.entities import BlastEvent


class BlastEventCreationPermissionError(ValueError):
    """The actor is not allowed to create Blast Events."""


@dataclass(frozen=True)
class CreateBlastEventCommand:
    domain_id: int
    name: str
    event_type: str
    event_date: date | None
    elevation: float | None
    geometry_file_path: str
    actor_id: int | None
    can_edit: bool
    design_drillhole_file_path: str | None = None


@dataclass(frozen=True)
class CreateBlastEventResult:
    event_id: str
    event_type: str
    warning_text: str | None = None


class BlastEventCreationPersistence(Protocol):
    """Narrow port required by the Blast Event creation workflow."""

    def load_state(self, domain_id: int) -> AssessmentStateSnapshot: ...

    def persist_event(
        self, domain_id: int, expected_version: int, event: BlastEvent, actor_id: int | None,
    ) -> int: ...


class DrillholeDatasetWriter(Protocol):
    def import_dataset(
        self,
        domain_id: int,
        event_logical_id: str,
        dataset_kind: str,
        source_path: str,
        *,
        imported_by_user_id: int | None = None,
    ): ...


class CreateBlastEvent:
    def __init__(
        self,
        persistence: BlastEventCreationPersistence,
        drillhole_datasets: DrillholeDatasetWriter | None = None,
    ):
        self._persistence = persistence
        self._drillhole_datasets = drillhole_datasets

    @staticmethod
    def _combine_warnings(*values: str | None) -> str | None:
        usable = [str(value).strip() for value in values if value and str(value).strip()]
        return "\n".join(usable) if usable else None

    def execute(self, command: CreateBlastEventCommand) -> CreateBlastEventResult:
        if not command.can_edit:
            raise BlastEventCreationPermissionError(
                "Your role is not allowed to create or edit blast events")
        snapshot = self._persistence.load_state(command.domain_id)
        service = BlastEventService(snapshot.state)
        event = service.create_event(
            name=command.name,
            event_type=command.event_type,
            event_date=command.event_date,
            elevation=command.elevation,
            csv_path=command.geometry_file_path,
        )
        event.created_by_user_id = command.actor_id
        self._persistence.persist_event(
            command.domain_id, snapshot.expected_version, event, command.actor_id)

        drillhole_warning = None
        if self._drillhole_datasets is not None:
            # A contour BlastEvent's existing geometry source already consists of
            # drillhole strings, so that same file is its initial design dataset.
            # Production keeps the block outline and drillholes as separate files.
            design_drillholes = (
                command.geometry_file_path
                if command.event_type == "contour"
                else command.design_drillhole_file_path
            )
            if design_drillholes:
                try:
                    self._drillhole_datasets.import_dataset(
                        command.domain_id,
                        event.id,
                        "design",
                        design_drillholes,
                        imported_by_user_id=command.actor_id,
                    )
                except Exception as exc:
                    # The BlastEvent itself is already valid and persisted. Keep
                    # creation successful and surface a retryable secondary warning.
                    drillhole_warning = f"Design drillholes were not saved: {exc}"

        return CreateBlastEventResult(
            event.id,
            event.event_type,
            self._combine_warnings(service.last_import_warning, drillhole_warning),
        )
