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


class CreateBlastEvent:
    def __init__(self, persistence: BlastEventCreationPersistence):
        self._persistence = persistence

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
        return CreateBlastEventResult(event.id, event.event_type, service.last_import_warning)
