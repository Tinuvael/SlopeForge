"""Narrow persistence boundary for a Domain's Assessment editing state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from application.state.assessment_domain_state import AssessmentDomainState


@dataclass(frozen=True)
class AssessmentStateSnapshot:
    domain_id: int
    site_id: int
    workspace_id: int | None
    state: AssessmentDomainState


class AssessmentStatePersistence(Protocol):
    def load(self, domain_id: int) -> AssessmentStateSnapshot: ...

    def save(self, domain_id: int, state: AssessmentDomainState) -> AssessmentStateSnapshot:
        """Compatibility-only whole-state write; remove in Phase 5C."""
        ...
