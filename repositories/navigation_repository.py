"""Small read model used by the structural project tree."""
from dataclasses import dataclass
from decimal import Decimal
from sqlalchemy import select
from database import assessment_models as orm

@dataclass(frozen=True)
class AreaNavigationRow:
    id: str
    domain_id: int
    name: str
    lower_elevation: Decimal
    upper_elevation: Decimal

class NavigationRepository:
    def __init__(self, session_factory): self.session_factory = session_factory
    def list_active_areas(self):
        active = orm.AssessmentAreaGeometryRevision.is_active.is_(True)
        with self.session_factory() as session:
            stmt = (select(orm.AssessmentArea.domain_id, orm.AssessmentWorkspace.domain_id, orm.AssessmentArea.name,
                     orm.AssessmentAreaGeometryRevision.lower_elevation_m, orm.AssessmentAreaGeometryRevision.upper_elevation_m)
                    .join(orm.AssessmentArea.workspace).join(orm.AssessmentArea.geometry_revisions)
                    .where(orm.AssessmentArea.is_archived.is_(False), active)
                    .order_by(orm.AssessmentWorkspace.domain_id, orm.AssessmentAreaGeometryRevision.lower_elevation_m,
                              orm.AssessmentAreaGeometryRevision.upper_elevation_m, orm.AssessmentArea.name))
            return [AreaNavigationRow(*row) for row in session.execute(stmt)]
