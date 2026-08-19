"""Read-only, non-persisted dashboard projections over the current schema."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from database import assessment_models as a
from database.models import AuditLogEntry, Domain, DomainGeometry
from domain.blasting.workflow import derive_assessment_progress_state
from infrastructure.db.workflow_status_queries import blast_workflow_states


@dataclass(frozen=True)
class AreaRow:
    id: str
    name: str
    interval: str
    assessment_date: date | None
    status: str | None
    dai: float | None
    fci: float | None
    quadrant: str | None


@dataclass(frozen=True)
class BlastRow:
    id: int | str
    entity_type: str
    name: str
    horizon: str
    event_date: date | None
    status: str


@dataclass(frozen=True)
class ActivityRow:
    entity_type: str
    entity_name: str
    action: str
    changed_at: datetime | date | None
    actor: str = ""


@dataclass(frozen=True)
class TrendRow:
    """One stored completed assessment revision for an all-time trend."""

    assessment_date: date
    dai: float | None
    fci: float | None


@dataclass(frozen=True)
class MapGeometry:
    entity_id: int | str
    points: tuple[tuple[float, float], ...]
    quadrant: str | None = None
    name: str = ""
    domain_name: str = ""
    interval: str = ""
    dai: float | None = None
    fci: float | None = None


@dataclass(frozen=True)
class DomainMapGeometry:
    domain_id: int
    domain_name: str
    points: tuple[tuple[float, float], ...]
    palette_index: int
    is_current: bool = False


@dataclass(frozen=True)
class _SiteDomainGeometryProjection:
    geometries: tuple[DomainMapGeometry, ...]
    metadata: tuple[tuple[int, str, str | None], ...]

    def for_domain(self, domain_id: int):
        geometries = tuple(
            DomainMapGeometry(
                item.domain_id,
                item.domain_name,
                item.points,
                item.palette_index,
                item.domain_id == domain_id,
            )
            for item in self.geometries
        )
        source = next(
            (
                (kind, filename)
                for current_id, kind, filename in self.metadata
                if current_id == domain_id
            ),
            (None, None),
        )
        return geometries, source[0], source[1]


@dataclass(frozen=True)
class DomainSummary:
    id: int
    name: str
    production: int = 0
    contour: int = 0
    areas: int = 0
    completed: int = 0
    drafts: int = 0
    average_dai: float | None = None
    average_fci: float | None = None

    @property
    def blast_events(self):
        return self.production + self.contour


@dataclass(frozen=True)
class DomainDashboardSnapshot:
    domain: DomainSummary
    areas: list[AreaRow] = field(default_factory=list)
    blasts: list[BlastRow] = field(default_factory=list)
    intervals: dict[str, int] = field(default_factory=dict)
    quadrants: dict[str, int] = field(default_factory=dict)
    recent: list[ActivityRow] = field(default_factory=list)
    project_lines: tuple[MapGeometry, ...] = ()
    production_geometries: tuple[MapGeometry, ...] = ()
    contour_geometries: tuple[MapGeometry, ...] = ()
    assessment_geometries: tuple[MapGeometry, ...] = ()
    domain_geometries: tuple[DomainMapGeometry, ...] = ()
    geometry_source_kind: str | None = None
    geometry_source_file_name: str | None = None
    trend_history: list[TrendRow] = field(default_factory=list)

    @property
    def trend_rows(self):
        if self.trend_history:
            return self.trend_history
        # Keeps lightweight/in-memory snapshots useful in tests and previews.
        return [
            row
            for row in self.areas
            if row.status == "completed"
            and row.assessment_date is not None
            and (row.dai is not None or row.fci is not None)
        ]


@dataclass(frozen=True)
class SiteDashboardSnapshot:
    site_id: int
    domains: list[DomainDashboardSnapshot]
    active_dataset: object | None
    datasets: list[object]
    recent: list[ActivityRow] = field(default_factory=list)
    project_lines: tuple[MapGeometry, ...] = ()

    @property
    def production(self):
        return sum(x.domain.production for x in self.domains)

    @property
    def contour(self):
        return sum(x.domain.contour for x in self.domains)

    @property
    def areas(self):
        return sum(x.domain.areas for x in self.domains)

    @property
    def completed(self):
        return sum(x.domain.completed for x in self.domains)

    @property
    def drafts(self):
        return sum(x.domain.drafts for x in self.domains)

    def _average(self, attr):
        values = [
            getattr(row, attr)
            for domain in self.domains
            for row in domain.areas
            if row.status == "completed" and getattr(row, attr) is not None
        ]
        return sum(values) / len(values) if values else None

    @property
    def average_dai(self):
        return self._average("dai")

    @property
    def average_fci(self):
        return self._average("fci")

    @property
    def trend_rows(self):
        return [row for domain in self.domains for row in domain.trend_rows]

    @property
    def domain_geometries(self):
        if not self.domains:
            return ()
        return tuple(
            DomainMapGeometry(
                geometry.domain_id,
                geometry.domain_name,
                geometry.points,
                geometry.palette_index,
                False,
            )
            for geometry in self.domains[0].domain_geometries
        )

    @property
    def assessment_geometries(self):
        return tuple(
            geometry
            for domain in self.domains
            for geometry in domain.assessment_geometries
        )

    @property
    def quadrants(self):
        result: dict[str, int] = {}
        for domain in self.domains:
            for key, value in domain.quadrants.items():
                result[key] = result.get(key, 0) + value
        return result


def _number(value):
    if value is None:
        return "—"
    text = format(Decimal(value).normalize(), "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _actor(user) -> str:
    if user is None:
        return ""
    return user.full_name or user.username or ""


def _audit_actor_maps(session, entity_type: str, entity_ids) -> tuple[dict, dict, dict]:
    ids = [str(value) for value in entity_ids]
    if not ids:
        return {}, {}, {}
    audits = list(
        session.scalars(
            select(AuditLogEntry)
            .options(joinedload(AuditLogEntry.user))
            .where(
                AuditLogEntry.entity_type == entity_type,
                AuditLogEntry.entity_id.in_(ids),
            )
            .order_by(AuditLogEntry.created_at.desc(), AuditLogEntry.id.desc())
        )
    )
    latest: dict[str, str] = {}
    created: dict[str, str] = {}
    revision: dict[str, str] = {}
    revision_markers = {"geometry_revision", "assessment_revision", "technical_revision"}
    for entry in audits:
        actor = _actor(entry.user)
        if actor:
            latest.setdefault(entry.entity_id, actor)
            if entry.action == "create":
                created[entry.entity_id] = actor
            if entry.field_name in revision_markers and entry.new_value:
                revision[entry.new_value] = actor
    return latest, created, revision


def _activity_sort_key(item: ActivityRow):
    changed = item.changed_at
    if isinstance(changed, datetime):
        return changed.timestamp()
    if isinstance(changed, date):
        return datetime.combine(changed, datetime.min.time()).timestamp()
    return 0


class DashboardRepository:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    def domain_snapshot(self, domain_id: int) -> DomainDashboardSnapshot:
        return self._domain_snapshot(domain_id)

    def _domain_snapshot(
        self,
        domain_id: int,
        site_geometry: _SiteDomainGeometryProjection | None = None,
    ) -> DomainDashboardSnapshot:
        with self.session_factory() as session:
            domain = session.get(Domain, domain_id)
            if domain is None:
                raise LookupError(f"Domain {domain_id} not found")

            production = list(
                session.scalars(
                    select(a.BlastEvent).where(
                        a.BlastEvent.domain_id == domain_id,
                        a.BlastEvent.event_type == "production",
                        a.BlastEvent.is_archived.is_(False),
                    )
                )
            )
            contours = list(
                session.scalars(
                    select(a.BlastEvent).where(
                        a.BlastEvent.domain_id == domain_id,
                        a.BlastEvent.event_type == "contour",
                        a.BlastEvent.is_archived.is_(False),
                    )
                )
            )
            rows = session.execute(
                select(
                    a.AssessmentArea,
                    a.AssessmentAreaGeometryRevision,
                    a.AssessmentAreaEvaluationRevision,
                )
                .join(a.AssessmentArea.geometry_revisions)
                .outerjoin(
                    a.AssessmentAreaEvaluation,
                    (a.AssessmentAreaEvaluation.assessment_area_id == a.AssessmentArea.id)
                    & a.AssessmentAreaEvaluation.is_archived.is_(False),
                )
                .outerjoin(
                    a.AssessmentAreaEvaluationRevision,
                    (a.AssessmentAreaEvaluationRevision.evaluation_id == a.AssessmentAreaEvaluation.id)
                    & a.AssessmentAreaEvaluationRevision.is_active.is_(True),
                )
                .where(
                    a.AssessmentArea.domain_id == domain_id,
                    a.AssessmentArea.is_archived.is_(False),
                    a.AssessmentAreaGeometryRevision.is_active.is_(True),
                )
            ).all()

            areas: list[AreaRow] = []
            intervals: dict[str, int] = {}
            quadrants: dict[str, int] = {}
            for area, geometry, evaluation in rows:
                interval = (
                    f"{_number(geometry.min_elevation_m)}–{_number(geometry.max_elevation_m)}"
                    if geometry.min_elevation_m is not None
                    and geometry.max_elevation_m is not None
                    else "—"
                )
                intervals[interval] = intervals.get(interval, 0) + 1
                status = str(
                    derive_assessment_progress_state(
                        geometry.logical_id,
                        evaluation.status if evaluation else None,
                        evaluation.geometry_revision.logical_id if evaluation else None,
                    )
                )
                current_completed = status == "completed"
                quadrant = (
                    evaluation.result_quadrant
                    if evaluation and current_completed
                    else None
                )
                if quadrant:
                    quadrants[quadrant] = quadrants.get(quadrant, 0) + 1
                areas.append(
                    AreaRow(
                        area.logical_id,
                        area.name,
                        interval,
                        evaluation.assessment_date if evaluation else area.assessment_date,
                        status,
                        float(evaluation.design_achievement_index)
                        if evaluation
                        and current_completed
                        and evaluation.design_achievement_index is not None
                        else None,
                        float(evaluation.face_condition_index)
                        if evaluation
                        and current_completed
                        and evaluation.face_condition_index is not None
                        else None,
                        quadrant,
                    )
                )

            completed = [item for item in areas if item.status == "completed"]

            def average(key):
                values = [
                    getattr(item, key)
                    for item in completed
                    if getattr(item, key) is not None
                ]
                return sum(values) / len(values) if values else None

            summary = DomainSummary(
                domain.id,
                domain.name,
                len(production),
                len(contours),
                len(areas),
                len(completed),
                sum(item.status == "draft" for item in areas),
                average("dai"),
                average("fci"),
            )

            historical_revisions = list(
                session.scalars(
                    select(a.AssessmentAreaEvaluationRevision)
                    .join(
                        a.AssessmentAreaEvaluation,
                        a.AssessmentAreaEvaluationRevision.evaluation_id
                        == a.AssessmentAreaEvaluation.id,
                    )
                    .join(
                        a.AssessmentArea,
                        a.AssessmentAreaEvaluation.assessment_area_id
                        == a.AssessmentArea.id,
                    )
                    .where(
                        a.AssessmentArea.domain_id == domain_id,
                        a.AssessmentArea.is_archived.is_(False),
                        a.AssessmentAreaEvaluation.is_archived.is_(False),
                        a.AssessmentAreaEvaluationRevision.status == "completed",
                        a.AssessmentAreaEvaluationRevision.assessment_date.is_not(None),
                    )
                    .order_by(
                        a.AssessmentAreaEvaluationRevision.assessment_date,
                        a.AssessmentAreaEvaluationRevision.created_at,
                        a.AssessmentAreaEvaluationRevision.id,
                    )
                )
            )
            trend_history = [
                TrendRow(
                    revision.assessment_date,
                    float(revision.design_achievement_index)
                    if revision.design_achievement_index is not None
                    else None,
                    float(revision.face_condition_index)
                    if revision.face_condition_index is not None
                    else None,
                )
                for revision in historical_revisions
                if revision.design_achievement_index is not None
                or revision.face_condition_index is not None
            ]

            all_events = production + contours
            states = blast_workflow_states(session, all_events)
            blasts = [
                BlastRow(
                    item.logical_id,
                    "Production",
                    item.name,
                    _number(item.elevation_m),
                    item.event_date,
                    str(states[item.id]),
                )
                for item in production
            ]
            blasts += [
                BlastRow(
                    item.logical_id,
                    "Contour",
                    item.name,
                    _number(item.elevation_m),
                    item.event_date,
                    str(states[item.id]),
                )
                for item in contours
            ]

            area_ids = [area.logical_id for area, _, _ in rows]
            event_ids = [item.logical_id for item in all_events]
            area_latest_actor, area_created_actor, revision_actor = _audit_actor_maps(
                session, "assessment_area", area_ids
            )
            event_latest_actor, _event_created_actor, _ = _audit_actor_maps(
                session, "blast_event", event_ids
            )

            activity: list[ActivityRow] = []
            for area, _, evaluation in rows:
                area_id = str(area.logical_id)
                created = area.created_at == area.updated_at
                activity.append(
                    ActivityRow(
                        "Assessment Area",
                        area.name,
                        "Created" if created else "Updated",
                        area.updated_at,
                        area_latest_actor.get(area_id)
                        or area_created_actor.get(area_id, ""),
                    )
                )
                if evaluation is not None:
                    activity.append(
                        ActivityRow(
                            "Assessment Area",
                            area.name,
                            "Assessment completed"
                            if evaluation.status == "completed"
                            else "Assessment draft saved",
                            evaluation.created_at,
                            revision_actor.get(evaluation.logical_id, ""),
                        )
                    )
            for item in production:
                activity.append(
                    ActivityRow(
                        "Block",
                        item.name,
                        "Created" if item.created_at == item.updated_at else "Updated",
                        item.updated_at,
                        event_latest_actor.get(str(item.logical_id))
                        or _actor(item.created_by_user),
                    )
                )
            for item in contours:
                activity.append(
                    ActivityRow(
                        "Contour blast",
                        item.name,
                        "Created" if item.created_at == item.updated_at else "Updated",
                        item.updated_at,
                        event_latest_actor.get(str(item.logical_id))
                        or _actor(item.created_by_user),
                    )
                )
            recent = sorted(activity, key=_activity_sort_key, reverse=True)[:10]

            dataset = session.scalar(
                select(a.ProjectLinesDataset).where(
                    a.ProjectLinesDataset.site_id == domain.site_id,
                    a.ProjectLinesDataset.is_active.is_(True),
                )
            )
            project_lines = _project_line_geometries(dataset)

            geometry_rows = session.execute(
                select(a.BlastEvent, a.BlastEventGeometryRevision)
                .join(a.BlastEvent.geometry_revisions)
                .where(
                    a.BlastEvent.domain_id == domain_id,
                    a.BlastEvent.is_archived.is_(False),
                    a.BlastEventGeometryRevision.is_active.is_(True),
                )
            ).all()
            production_geometries = []
            contour_geometries = []
            for event, revision in geometry_rows:
                points = _geometry_points(revision.plan_geometry_json)
                if not points:
                    continue
                target = (
                    production_geometries
                    if event.event_type == "production"
                    else contour_geometries
                    if event.event_type == "contour"
                    else None
                )
                if target is not None:
                    target.append(MapGeometry(event.logical_id, points, name=event.name))

            area_rows = {item.id: item for item in areas}
            assessment_geometries = []
            for area, geometry, _evaluation in rows:
                points = _geometry_points(geometry.final_geometry_json)
                if not points:
                    continue
                row = area_rows.get(area.logical_id)
                assessment_geometries.append(
                    MapGeometry(
                        area.logical_id,
                        points,
                        quadrant=row.quadrant if row else None,
                        name=area.name,
                        domain_name=domain.name,
                        interval=row.interval if row else "—",
                        dai=row.dai if row else None,
                        fci=row.fci if row else None,
                    )
                )

            if site_geometry is None:
                site_geometry = _load_site_domain_geometry(session, domain.site_id)
            domain_geometries, source_kind, source_file_name = site_geometry.for_domain(
                domain_id
            )
            return DomainDashboardSnapshot(
                domain=summary,
                areas=areas,
                blasts=blasts,
                intervals=intervals,
                quadrants=quadrants,
                recent=recent,
                project_lines=project_lines,
                production_geometries=tuple(production_geometries),
                contour_geometries=tuple(contour_geometries),
                assessment_geometries=tuple(assessment_geometries),
                domain_geometries=domain_geometries,
                geometry_source_kind=source_kind,
                geometry_source_file_name=source_file_name,
                trend_history=trend_history,
            )

    def site_snapshot(self, site_id: int) -> SiteDashboardSnapshot:
        with self.session_factory() as session:
            ids = list(
                session.scalars(
                    select(Domain.id)
                    .where(Domain.site_id == site_id)
                    .order_by(Domain.name)
                )
            )
            datasets = list(
                session.scalars(
                    select(a.ProjectLinesDataset)
                    .where(a.ProjectLinesDataset.site_id == site_id)
                    .order_by(a.ProjectLinesDataset.imported_at.desc())
                )
            )
            active = next((item for item in datasets if item.is_active), None)
            project_lines = _project_line_geometries(active)
            site_geometry = _load_site_domain_geometry(session, site_id)
            for row in datasets:
                session.expunge(row)
        domains = [self._domain_snapshot(item, site_geometry) for item in ids]
        activity = [
            ActivityRow("Project Lines", item.name, "Imported", item.imported_at)
            for item in datasets
        ]
        activity += [item for domain in domains for item in domain.recent]
        activity.sort(key=_activity_sort_key, reverse=True)
        return SiteDashboardSnapshot(
            site_id,
            domains,
            active,
            datasets,
            activity[:10],
            project_lines,
        )


def _load_site_domain_geometry(session, site_id: int) -> _SiteDomainGeometryProjection:
    rows = session.execute(
        select(Domain, DomainGeometry)
        .outerjoin(DomainGeometry)
        .where(Domain.site_id == site_id)
        .order_by(Domain.name, Domain.id)
    ).all()
    geometries = []
    metadata = []
    for palette_index, (domain, geometry) in enumerate(rows):
        if geometry is not None:
            metadata.append(
                (domain.id, geometry.source_kind, geometry.source_file_name)
            )
            for polygon in geometry.polygons_json:
                points = _geometry_points(polygon)
                if points:
                    geometries.append(
                        DomainMapGeometry(
                            domain.id,
                            domain.name,
                            points,
                            palette_index,
                        )
                    )
    return _SiteDomainGeometryProjection(tuple(geometries), tuple(metadata))


def _project_line_geometries(dataset) -> tuple[MapGeometry, ...]:
    return tuple(
        MapGeometry(
            str(line.get("source_id", index)),
            tuple(
                (float(point["x"]), float(point["y"]))
                for point in line.get("points", [])
            ),
        )
        for index, line in enumerate(dataset.lines_json if dataset else [])
        if len(line.get("points", [])) >= 2
    )


def _geometry_points(value) -> tuple[tuple[float, float], ...]:
    """Decode the persisted GeoJSON-like plan types into detached XY tuples."""
    if not isinstance(value, dict):
        return ()
    coordinates = value.get("coordinates", [])
    if value.get("type") == "Polygon":
        coordinates = coordinates[0] if coordinates else []
    if value.get("type") in {"Polygon", "LineString", "MultiPoint"}:
        return tuple((float(x), float(y)) for x, y in coordinates)
    if value.get("type") == "Point" and len(coordinates) == 2:
        return ((float(coordinates[0]), float(coordinates[1])),)
    return ()