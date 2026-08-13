from types import SimpleNamespace

from repositories.assessment_state_repository import AssessmentStateRepository


class _Session:
    def __init__(self):
        self.scalar_calls = 0

    def __enter__(self): return self
    def __exit__(self, *_args): return None

    def get(self, _model, domain_id):
        return SimpleNamespace(id=domain_id, site_id=17, version=0)

    def scalars(self, _query):
        self.scalar_calls += 1
        return iter(())


def test_real_repository_loads_valid_empty_domain_state_without_name_error():
    """Exercise load_for_domain through mapping and the real state validator."""
    session = _Session()
    loaded = AssessmentStateRepository(lambda: session).load_for_domain(23)

    assert (loaded.domain_id, loaded.site_id, loaded.expected_version) == (23, 17, 0)
    assert loaded.state.to_dict() == {
        "datasets": [], "blast_events": [], "assessment_areas": [],
        "technical_cards": [], "evaluations": [], "attachments": [],
    }
    assert session.scalar_calls == 3
