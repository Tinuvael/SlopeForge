"""Application workflow for creating one Blast Event header."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from application.services.blast_events import BlastEventService
from application.state.assessment_domain_state import AssessmentDomainState
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
    blast_block_id: int | None
    warning_text: str | None = None


class BlastEventCreationPersistence(Protocol):
    """Narrow port required by the Blast Event creation workflow."""

    def load_state(self, domain_id: int) -> AssessmentDomainState: ...

    def persist_contour(self, domain_id: int, event: BlastEvent) -> None: ...

    def persist_production(
        self, domain_id: int, event: BlastEvent, actor_id: int | None,
    ) -> int: ...


class CreateBlastEvent:
    def __init__(self, persistence: BlastEventCreationPersistence):
        self._persistence = persistence

    def execute(self, command: CreateBlastEventCommand) -> CreateBlastEventResult:
        if not command.can_edit:
            raise BlastEventCreationPermissionError(
                "Your role is not allowed to create or edit blast events")
        state = self._persistence.load_state(command.domain_id)
        service = BlastEventService(state)
        event = service.create_event(
            name=command.name,
            event_type=command.event_type,
            event_date=command.event_date,
            elevation=command.elevation,
            csv_path=command.geometry_file_path,
        )
        if event.event_type == "contour":
            self._persistence.persist_contour(command.domain_id, event)
            block_id = None
        else:
            block_id = self._persistence.persist_production(
                command.domain_id, event, command.actor_id)
            if block_id is None:  # defensive guarantee of the application contract
                raise RuntimeError("Production Blast Event persistence did not create a BlastBlock")
        return CreateBlastEventResult(event.id, event.event_type, block_id, service.last_import_warning)
