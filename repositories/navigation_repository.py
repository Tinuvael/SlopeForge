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
    is_archived: bool

@dataclass(frozen=True)
class ContourEventNavigationRow:
    id: str
    domain_id: int
    name: str
    elevation: Decimal
    is_archived: bool

class NavigationRepository:
    def __init__(self, session_factory): self.session_factory = session_factory
    def list_areas(self, show_archived=False):
        active = orm.AssessmentAreaGeometryRevision.is_active.is_(True)
        with self.session_factory() as session:
            stmt = (select(orm.AssessmentArea.logical_id, orm.AssessmentArea.domain_id, orm.AssessmentArea.name,
                     orm.AssessmentAreaGeometryRevision.lower_elevation_m, orm.AssessmentAreaGeometryRevision.upper_elevation_m,
                     orm.AssessmentArea.is_archived)
                    .join(orm.AssessmentArea.geometry_revisions)
                    .where(active)
                    .order_by(orm.AssessmentArea.domain_id, orm.AssessmentAreaGeometryRevision.lower_elevation_m,
                              orm.AssessmentAreaGeometryRevision.upper_elevation_m, orm.AssessmentArea.name))
            if not show_archived: stmt = stmt.where(orm.AssessmentArea.is_archived.is_(False))
            return [AreaNavigationRow(*row) for row in session.execute(stmt)]

    def list_active_areas(self):
        """Compatibility name for callers that only need current areas."""
        return self.list_areas(False)
    def list_contour_events(self, show_archived=False):
        with self.session_factory() as session:
            stmt=(select(orm.BlastEvent.logical_id,orm.BlastEvent.domain_id,
                         orm.BlastEvent.name,orm.BlastEvent.elevation_m,orm.BlastEvent.is_archived)
                  .where(orm.BlastEvent.event_type=="contour")
                  .order_by(orm.BlastEvent.domain_id,orm.BlastEvent.elevation_m.desc(),orm.BlastEvent.name))
            if not show_archived: stmt=stmt.where(orm.BlastEvent.is_archived.is_(False))
            return [ContourEventNavigationRow(*row) for row in session.execute(stmt)]
