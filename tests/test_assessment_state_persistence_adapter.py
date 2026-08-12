from application.ports.assessment_state import AssessmentStateSnapshot
from application.state.assessment_domain_state import AssessmentDomainState
from infrastructure.db.assessment_state import SqlAlchemyAssessmentStatePersistence
from repositories.assessment_state_repository import LoadedAssessmentState


def test_sqlalchemy_adapter_maps_versioned_read_contract(monkeypatch):
    original = AssessmentDomainState()
    calls = []

    class Repository:
        def __init__(self, session_factory): calls.append(("init", session_factory))
        def load_for_domain(self, domain_id):
            calls.append(("load", domain_id))
            return LoadedAssessmentState(domain_id, 8, None, original, 6)

    monkeypatch.setattr("infrastructure.db.assessment_state.AssessmentStateRepository", Repository)
    factory = object()
    adapter = SqlAlchemyAssessmentStatePersistence(factory)
    assert adapter.load(4) == AssessmentStateSnapshot(4, 8, None, original, 6)
    assert not hasattr(adapter, "save")
    assert calls == [("init", factory), ("load", 4)]
