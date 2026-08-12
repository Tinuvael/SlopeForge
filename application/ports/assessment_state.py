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
    expected_version: int = 0


class AssessmentStatePersistence(Protocol):
    def load(self, domain_id: int) -> AssessmentStateSnapshot: ...
