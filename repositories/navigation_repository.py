"""Small read model used by the structural project tree."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from sqlalchemy import select
from database import assessment_models as orm
from infrastructure.db.workflow_status_queries import blast_workflow_states

@dataclass(frozen=True)
class AreaNavigationRow:
    id: str
    domain_id: int
    name: str
    min_elevation: Decimal | None
    max_elevation: Decimal | None
    is_archived: bool
    assessment_date: date

@dataclass(frozen=True)
class ContourEventNavigationRow:
    id: str
    domain_id: int
    name: str
    elevation: Decimal
    is_archived: bool
    event_date: date | None
    status: str

class NavigationRepository:
    def __init__(self, session_factory): self.session_factory = session_factory
    def list_areas(self, show_archived=False):
        active = orm.AssessmentAreaGeometryRevision.is_active.is_(True)
        with self.session_factory() as session:
            stmt = (select(orm.AssessmentArea.logical_id, orm.AssessmentArea.domain_id, orm.AssessmentArea.name,
                     orm.AssessmentAreaGeometryRevision.min_elevation_m, orm.AssessmentAreaGeometryRevision.max_elevation_m,
                     orm.AssessmentArea.is_archived, orm.AssessmentArea.assessment_date)
                    .join(orm.AssessmentArea.geometry_revisions)
                    .where(active)
                    .order_by(orm.AssessmentArea.domain_id, orm.AssessmentAreaGeometryRevision.min_elevation_m,
                              orm.AssessmentAreaGeometryRevision.max_elevation_m, orm.AssessmentArea.name))
            if not show_archived: stmt = stmt.where(orm.AssessmentArea.is_archived.is_(False))
            return [AreaNavigationRow(*row) for row in session.execute(stmt)]

    def list_active_areas(self):
        """Compatibility name for callers that only need current areas."""
        return self.list_areas(False)
    def list_contour_events(self, show_archived=False):
        with self.session_factory() as session:
            stmt=(select(orm.BlastEvent)
                  .where(orm.BlastEvent.event_type=="contour")
                  .order_by(orm.BlastEvent.domain_id,orm.BlastEvent.elevation_m.desc(),orm.BlastEvent.name))
            if not show_archived: stmt=stmt.where(orm.BlastEvent.is_archived.is_(False))
            events = list(session.scalars(stmt))
            states = blast_workflow_states(session, events)
            return [ContourEventNavigationRow(
                row.logical_id, row.domain_id, row.name, row.elevation_m,
                row.is_archived, row.event_date, str(states[row.id]))
                for row in events]
