from repositories.assessment_area_context_repository import AssessmentAreaContextRepository


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, statement):
        self.statement = statement
        return self.rows


def polygon(offset):
    return {"type": "Polygon", "coordinates": [[
        [offset, 0], [offset + 1, 0], [offset, 1], [offset, 0],
    ]]}


def test_project_context_query_is_site_scoped_current_and_non_archived():
    session = FakeSession([
        ("same-domain", 10, polygon(0)),
        ("other-domain", 11, polygon(5)),
        ("bad", 11, {}),
    ])
    result = AssessmentAreaContextRepository(lambda: session).list_current_boundaries(7)

    assert [(item.assessment_area_id, item.domain_id) for item in result] == [
        ("same-domain", 10), ("other-domain", 11),
    ]
    sql = str(session.statement)
    params = session.statement.compile().params
    assert "domains.site_id" in sql and 7 in params.values()
    assert "assessment_areas.is_archived IS false" in sql
    assert "assessment_area_geometry_revisions.is_active IS true" in sql

