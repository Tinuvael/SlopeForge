from application.ports.assessment_state import AssessmentStateSnapshot
from application.state.assessment_domain_state import AssessmentDomainState
from infrastructure.db.assessment_state import SqlAlchemyAssessmentStatePersistence
from repositories.assessment_state_repository import LoadedAssessmentState


def test_sqlalchemy_adapter_maps_repository_load_and_replace_contract(monkeypatch):
    original = AssessmentDomainState()
    saved_state = AssessmentDomainState()
    calls = []

    class Repository:
        def __init__(self, session_factory):
            calls.append(("init", session_factory))

        def load_for_domain(self, domain_id):
            calls.append(("load", domain_id))
            return LoadedAssessmentState(domain_id, 8, None, original)

        def replace_for_domain(self, domain_id, state):
            calls.append(("replace", domain_id, state))
            return LoadedAssessmentState(domain_id, 8, 91, saved_state)

    monkeypatch.setattr("infrastructure.db.assessment_state.AssessmentStateRepository", Repository)
    factory = object()
    adapter = SqlAlchemyAssessmentStatePersistence(factory)
    loaded = adapter.load(4)
    saved = adapter.save(4, original)

    assert loaded == AssessmentStateSnapshot(4, 8, None, original)
    assert saved == AssessmentStateSnapshot(4, 8, 91, saved_state)
    assert calls == [("init", factory), ("load", 4), ("replace", 4, original)]
