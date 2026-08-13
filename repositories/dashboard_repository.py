"""Read-only, non-persisted dashboard projections over the current schema."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import select
from database.models import BlastBlock, Domain, DomainGeometry
from database import assessment_models as a

@dataclass(frozen=True)
class AreaRow:
    id: str; name: str; interval: str; assessment_date: date | None
    status: str | None; dai: float | None; fci: float | None; quadrant: str | None

@dataclass(frozen=True)
class BlastRow:
    id: int | str; entity_type: str; name: str; horizon: str; event_date: date | None; status: str

@dataclass(frozen=True)
class MapGeometry:
    entity_id: int | str
    points: tuple[tuple[float, float], ...]
    quadrant: str | None = None

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
        geometries=tuple(DomainMapGeometry(
            item.domain_id,item.domain_name,item.points,item.palette_index,item.domain_id==domain_id
        ) for item in self.geometries)
        source=next(((kind,filename) for current_id,kind,filename in self.metadata if current_id==domain_id),(None,None))
        return geometries,source[0],source[1]

@dataclass(frozen=True)
class DomainSummary:
    id: int; name: str; production: int = 0; contour: int = 0; areas: int = 0
    completed: int = 0; drafts: int = 0; average_dai: float | None = None; average_fci: float | None = None
    @property
    def blast_events(self): return self.production + self.contour

@dataclass(frozen=True)
class DomainDashboardSnapshot:
    domain: DomainSummary; areas: list[AreaRow] = field(default_factory=list)
    blasts: list[BlastRow] = field(default_factory=list); intervals: dict[str, int] = field(default_factory=dict)
    quadrants: dict[str, int] = field(default_factory=dict); recent: list[tuple[str, datetime | date | None]] = field(default_factory=list)
    project_lines: tuple[MapGeometry, ...] = ()
    production_geometries: tuple[MapGeometry, ...] = ()
    contour_geometries: tuple[MapGeometry, ...] = ()
    assessment_geometries: tuple[MapGeometry, ...] = ()
    domain_geometries: tuple[DomainMapGeometry, ...] = ()
    geometry_source_kind: str | None = None
    geometry_source_file_name: str | None = None

@dataclass(frozen=True)
class SiteDashboardSnapshot:
    site_id: int; domains: list[DomainDashboardSnapshot]; active_dataset: object | None; datasets: list[object]
    recent: list[tuple[str, datetime | date | None]] = field(default_factory=list)
    project_lines: tuple[MapGeometry, ...] = ()
    @property
    def production(self): return sum(x.domain.production for x in self.domains)
    @property
    def contour(self): return sum(x.domain.contour for x in self.domains)
    @property
    def areas(self): return sum(x.domain.areas for x in self.domains)
    @property
    def completed(self): return sum(x.domain.completed for x in self.domains)
    @property
    def drafts(self): return sum(x.domain.drafts for x in self.domains)
    def _average(self, attr):
        values=[getattr(r,attr) for d in self.domains for r in d.areas if r.status=="completed" and getattr(r,attr) is not None]
        return sum(values)/len(values) if values else None
    @property
    def average_dai(self): return self._average("dai")
    @property
    def average_fci(self): return self._average("fci")
    @property
    def domain_geometries(self):
        if not self.domains: return ()
        # Every Domain snapshot contains the same set-based Project context.
        return tuple(DomainMapGeometry(g.domain_id,g.domain_name,g.points,g.palette_index,False) for g in self.domains[0].domain_geometries)

def _number(v):
    if v is None: return "—"
    s=format(Decimal(v).normalize(), "f"); return s.rstrip("0").rstrip(".") if "." in s else s

class DashboardRepository:
    def __init__(self, session_factory): self.session_factory=session_factory
    def domain_snapshot(self, domain_id: int) -> DomainDashboardSnapshot:
        return self._domain_snapshot(domain_id)
    def _domain_snapshot(self, domain_id: int, site_geometry: _SiteDomainGeometryProjection | None = None) -> DomainDashboardSnapshot:
        with self.session_factory() as s:
            domain=s.get(Domain,domain_id)
            if domain is None: raise LookupError(f"Domain {domain_id} not found")
            blocks=list(s.scalars(select(BlastBlock).where(BlastBlock.domain_id==domain_id,BlastBlock.is_archived.is_(False))))
            contours=list(s.scalars(select(a.BlastEvent).where(a.BlastEvent.domain_id==domain_id,a.BlastEvent.event_type=="contour",a.BlastEvent.is_archived.is_(False))))
            rows=s.execute(select(a.AssessmentArea,a.AssessmentAreaGeometryRevision,a.AssessmentAreaEvaluationRevision)
                .join(a.AssessmentArea.geometry_revisions)
                .outerjoin(a.AssessmentAreaEvaluation,(a.AssessmentAreaEvaluation.assessment_area_id==a.AssessmentArea.id)&a.AssessmentAreaEvaluation.is_archived.is_(False))
                .outerjoin(a.AssessmentAreaEvaluationRevision,(a.AssessmentAreaEvaluationRevision.evaluation_id==a.AssessmentAreaEvaluation.id)&a.AssessmentAreaEvaluationRevision.is_active.is_(True))
                .where(a.AssessmentArea.domain_id==domain_id,a.AssessmentArea.is_archived.is_(False),a.AssessmentAreaGeometryRevision.is_active.is_(True))).all()
            areas=[]; intervals={}; quadrants={}
            for area,geo,ev in rows:
                interval=(f"{_number(geo.min_elevation_m)}–{_number(geo.max_elevation_m)}"
                          if geo.min_elevation_m is not None and geo.max_elevation_m is not None else "—")
                intervals[interval]=intervals.get(interval,0)+1
                status=ev.status if ev else None; q=ev.result_quadrant if ev and status=="completed" else None
                if q: quadrants[q]=quadrants.get(q,0)+1
                areas.append(AreaRow(area.logical_id,area.name,interval,(ev.assessment_date if ev else area.assessment_date),status,float(ev.design_achievement_index) if ev and ev.design_achievement_index is not None else None,float(ev.face_condition_index) if ev and ev.face_condition_index is not None else None,q))
            completed=[x for x in areas if x.status=="completed"]
            avg=lambda key: (sum(v)/len(v) if (v:=[getattr(x,key) for x in completed if getattr(x,key) is not None]) else None)
            summary=DomainSummary(domain.id,domain.name,len(blocks),len(contours),len(areas),len(completed),sum(x.status=="draft" for x in areas),avg("dai"),avg("fci"))
            blasts=[BlastRow(x.id,"Production",x.block_number,_number(x.horizon_m),x.planned_blast_date,x.status) for x in blocks]
            blasts += [BlastRow(x.logical_id,"Contour",x.name,_number(x.elevation_m),x.event_date,"—") for x in contours]
            activity=[(f"Assessment Area: {area.name}",area.updated_at) for area,_,_ in rows]
            activity += [(f"Evaluation: {area.name}",ev.created_at) for area,_,ev in rows if ev is not None]
            activity += [(f"Block {x.block_number}",x.updated_at) for x in blocks]+[(x.name,x.updated_at) for x in contours]
            recent=sorted(activity,key=lambda x:x[1].timestamp() if isinstance(x[1],datetime) else 0,reverse=True)[:10]

            dataset=s.scalar(select(a.ProjectLinesDataset).where(a.ProjectLinesDataset.site_id==domain.site_id,a.ProjectLinesDataset.is_active.is_(True)))
            project_lines=_project_line_geometries(dataset)
            active_block_ids={x.id for x in blocks}
            geometry_rows=s.execute(select(a.BlastEvent,a.BlastEventGeometryRevision).join(a.BlastEvent.geometry_revisions).where(a.BlastEvent.domain_id==domain_id,a.BlastEvent.is_archived.is_(False),a.BlastEventGeometryRevision.is_active.is_(True))).all()
            production_geometries=[]; contour_geometries=[]
            for event,revision in geometry_rows:
                points=_geometry_points(revision.plan_geometry_json)
                if not points: continue
                target=production_geometries if event.event_type=="production" and event.blast_block_id in active_block_ids else contour_geometries if event.event_type=="contour" else None
                if target is not None: target.append(MapGeometry(event.blast_block_id if event.blast_block_id else event.logical_id,points))
            assessment_geometries=tuple(MapGeometry(area.logical_id,_geometry_points(geo.final_geometry_json),ev.result_quadrant if ev and ev.status=="completed" else None) for area,geo,ev in rows if _geometry_points(geo.final_geometry_json))
            if site_geometry is None: site_geometry=_load_site_domain_geometry(s,domain.site_id)
            domain_geometries,source_kind,source_file_name=site_geometry.for_domain(domain_id)
            return DomainDashboardSnapshot(summary,areas,blasts,intervals,quadrants,recent,project_lines,tuple(production_geometries),tuple(contour_geometries),assessment_geometries,domain_geometries,source_kind,source_file_name)
    def site_snapshot(self, site_id: int) -> SiteDashboardSnapshot:
        with self.session_factory() as s:
            ids=list(s.scalars(select(Domain.id).where(Domain.site_id==site_id).order_by(Domain.name)))
            datasets=list(s.scalars(select(a.ProjectLinesDataset).where(a.ProjectLinesDataset.site_id==site_id).order_by(a.ProjectLinesDataset.imported_at.desc())))
            active=next((x for x in datasets if x.is_active),None)
            project_lines=_project_line_geometries(active)
            site_geometry=_load_site_domain_geometry(s,site_id)
            for row in datasets: s.expunge(row)
        domains=[self._domain_snapshot(i,site_geometry) for i in ids]
        activity=[(f"Project Lines: {x.name}",x.imported_at) for x in datasets]
        activity += [item for domain in domains for item in domain.recent]
        activity.sort(key=lambda x:x[1].timestamp() if isinstance(x[1],datetime) else 0,reverse=True)
        return SiteDashboardSnapshot(site_id,domains,active,datasets,activity[:10],project_lines)

def _load_site_domain_geometry(session,site_id: int) -> _SiteDomainGeometryProjection:
    rows=session.execute(select(Domain,DomainGeometry).outerjoin(DomainGeometry).where(
        Domain.site_id==site_id
    ).order_by(Domain.name,Domain.id)).all()
    geometries=[]; metadata=[]
    for palette_index,(domain,geometry) in enumerate(rows):
        if geometry is not None:
            metadata.append((domain.id,geometry.source_kind,geometry.source_file_name))
            for polygon in geometry.polygons_json:
                points=_geometry_points(polygon)
                if points: geometries.append(DomainMapGeometry(domain.id,domain.name,points,palette_index))
    return _SiteDomainGeometryProjection(tuple(geometries),tuple(metadata))

def _project_line_geometries(dataset) -> tuple[MapGeometry,...]:
    return tuple(MapGeometry(str(line.get("source_id",index)),tuple(
        (float(point["x"]),float(point["y"])) for point in line.get("points",[])
    )) for index,line in enumerate(dataset.lines_json if dataset else []) if len(line.get("points",[]))>=2)

def _geometry_points(value) -> tuple[tuple[float,float],...]:
    """Decode the persisted GeoJSON-like plan types into detached XY tuples."""
    if not isinstance(value,dict): return ()
    coordinates=value.get("coordinates",[])
    if value.get("type")=="Polygon": coordinates=coordinates[0] if coordinates else []
    if value.get("type") in {"Polygon","LineString","MultiPoint"}:
        return tuple((float(x),float(y)) for x,y in coordinates)
    if value.get("type")=="Point" and len(coordinates)==2:
        return ((float(coordinates[0]),float(coordinates[1])),)
    return ()
