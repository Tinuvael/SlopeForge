"""SQLAlchemy adapter for the application Assessment-state port."""
from application.ports.assessment_state import AssessmentStateSnapshot
from repositories.assessment_state_repository import AssessmentStateRepository


class SqlAlchemyAssessmentStatePersistence:
    def __init__(self, session_factory):
        self._repository = AssessmentStateRepository(session_factory)

    @staticmethod
    def _snapshot(loaded) -> AssessmentStateSnapshot:
        return AssessmentStateSnapshot(
            domain_id=loaded.domain_id,
            site_id=loaded.site_id,
            workspace_id=loaded.workspace_id,
            expected_version=loaded.expected_version,
            state=loaded.state,
        )

    def load(self, domain_id: int) -> AssessmentStateSnapshot:
        return self._snapshot(self._repository.load_for_domain(domain_id))
