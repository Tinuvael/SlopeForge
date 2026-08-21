"""Small project-wide read model for Assessment boundary context."""
from dataclasses import dataclass
from math import isfinite

from sqlalchemy import select

from database import assessment_models as orm
from database.models import Domain
from domain.geometry.types import PlanPoint, PlanPolygon


@dataclass(frozen=True)
class AssessmentAreaBoundaryContext:
    assessment_area_id: str
    domain_id: int
    ring: tuple[PlanPoint, ...]


class AssessmentAreaContextRepository:
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def list_current_boundaries(self, site_id: int) -> tuple[AssessmentAreaBoundaryContext, ...]:
        """Return usable active Area polygons for every Domain in one Project."""
        stmt = (
            select(
                orm.AssessmentArea.logical_id,
                orm.AssessmentArea.domain_id,
                orm.AssessmentAreaGeometryRevision.final_geometry_json,
            )
            .join(orm.AssessmentArea.domain)
            .join(orm.AssessmentArea.geometry_revisions)
            .where(
                Domain.site_id == site_id,
                orm.AssessmentArea.is_archived.is_(False),
                orm.AssessmentAreaGeometryRevision.is_active.is_(True),
            )
            .order_by(orm.AssessmentArea.domain_id, orm.AssessmentArea.logical_id)
        )
        with self._session_factory() as session:
            rows = session.execute(stmt)

            result = []
            for area_id, domain_id, geometry in rows:
                try:
                    polygon = PlanPolygon.from_dict(geometry)
                except (KeyError, TypeError, ValueError, IndexError):
                    continue
                if not all(isfinite(point.x) and isfinite(point.y) for point in polygon.ring):
                    continue
                result.append(AssessmentAreaBoundaryContext(area_id, domain_id, polygon.ring))
            return tuple(result)
