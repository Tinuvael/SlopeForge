"""Read-only collection of detached data for the first Project report."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.models import BlastBlock, Domain, Site
from database import assessment_models as orm


@dataclass(frozen=True)
class BlastReportRow:
    report_date: date; event_date: date | None; actual_blast_date: date | None
    domain: str; event_type: str; name: str; block_number: str | None
    horizon: float; archived: bool; technical_card_status: str | None
    actual_volume_m3: float | None; actual_explosive_mass_kg: float | None
    actual_drilling_length_m: float | None


@dataclass(frozen=True)
class AssessmentReportRow:
    name: str; domain: str; assessment_date: date; elevation_interval: str
    geometry_revision: int; evaluation_status: str | None; dai: float | None
    fci: float | None; quadrant: str | None; production_blocks: tuple[str, ...]
    contour_blasts: tuple[str, ...]


@dataclass(frozen=True)
class ProjectReport:
    project: str; from_date: date; to_date: date
    blasts: tuple[BlastReportRow, ...]; assessments: tuple[AssessmentReportRow, ...]

    @property
    def completed_assessments(self): return sum(x.evaluation_status == "completed" for x in self.assessments)
    @property
    def average_dai(self):
        values=[x.dai for x in self.assessments if x.evaluation_status == "completed" and x.dai is not None]
        return sum(values)/len(values) if values else None
    @property
    def average_fci(self):
        values=[x.fci for x in self.assessments if x.evaluation_status == "completed" and x.fci is not None]
        return sum(values)/len(values) if values else None


def _date(value: Any) -> date | None:
    if isinstance(value, date): return value
    if isinstance(value, str):
        try: return date.fromisoformat(value[:10])
        except ValueError: return None
    return None


class ProjectReportService:
    def __init__(self, session_factory): self.session_factory=session_factory

    def collect(self, site_id: int, from_date: date, to_date: date) -> ProjectReport:
        if from_date > to_date: raise ValueError("From date must not be after To date")
        with self.session_factory() as session:
            site=session.get(Site,site_id)
            if site is None: raise ValueError("Project does not exist")
            domains=session.scalars(select(Domain).where(Domain.site_id==site_id)).all()
            names={d.id:d.name for d in domains}; domain_ids=set(names)
            workspaces=session.scalars(select(orm.AssessmentWorkspace).where(orm.AssessmentWorkspace.domain_id.in_(domain_ids)).options(
                selectinload(orm.AssessmentWorkspace.events).selectinload(orm.BlastEvent.technical_card).selectinload(orm.BlastEventTechnicalCard.revisions),
                selectinload(orm.AssessmentWorkspace.events).selectinload(orm.BlastEvent.geometry_revisions),
                selectinload(orm.AssessmentWorkspace.areas).selectinload(orm.AssessmentArea.geometry_revisions).selectinload(orm.AssessmentAreaGeometryRevision.event_links).selectinload(orm.AssessmentEventLink.blast_event_geometry_revision).selectinload(orm.BlastEventGeometryRevision.blast_event),
                selectinload(orm.AssessmentWorkspace.areas).selectinload(orm.AssessmentArea.evaluation).selectinload(orm.AssessmentAreaEvaluation.revisions),
            )).all() if domain_ids else []
            block_ids={e.blast_block_id for w in workspaces for e in w.events if e.blast_block_id}
            blocks={b.id:b.block_number for b in session.scalars(select(BlastBlock).where(BlastBlock.id.in_(block_ids))).all()} if block_ids else {}
            blasts=[]; assessments=[]
            for workspace in workspaces:
                domain_name=names.get(workspace.domain_id,"")
                for event in workspace.events:
                    active=next((r for r in event.technical_card.revisions if r.is_active),None) if event.technical_card else None
                    payload=active.payload_json if active else {}; actual=payload.get("actual_execution") or {}
                    actual_date=_date(actual.get("actual_blast_date")); report_date=actual_date or event.event_date
                    if report_date is None or not from_date <= report_date <= to_date: continue
                    def number(key):
                        value=actual.get(key); return float(value) if value is not None else None
                    blasts.append(BlastReportRow(report_date,event.event_date,actual_date,domain_name,event.event_type,event.name,
                        blocks.get(event.blast_block_id),float(event.elevation_m),event.is_archived,active.status if active else None,
                        number("actual_block_volume_m3"),number("actual_total_explosive_mass_kg"),number("actual_total_drilling_length_m")))
                for area in workspace.areas:
                    if not from_date <= area.assessment_date <= to_date: continue
                    geometry=next((r for r in area.geometry_revisions if r.is_active),None)
                    evaluation=area.evaluation
                    result=next((r for r in evaluation.revisions if r.is_active and r.status=="completed"),None) if evaluation else None
                    active_eval=next((r for r in evaluation.revisions if r.is_active),None) if evaluation else None
                    prod=set(); contour=set()
                    if geometry:
                        for link in geometry.event_links:
                            if link.status != "confirmed": continue
                            event=link.blast_event_geometry_revision.blast_event
                            if event.event_type=="production" and event.blast_block_id in blocks: prod.add(blocks[event.blast_block_id])
                            elif event.event_type=="contour": contour.add(event.name)
                    assessments.append(AssessmentReportRow(area.name,domain_name,area.assessment_date,
                        f"{float(geometry.lower_elevation_m):g}–{float(geometry.upper_elevation_m):g}" if geometry else "",
                        geometry.revision_number if geometry else 0,active_eval.status if active_eval else None,
                        float(result.design_achievement_index) if result and result.design_achievement_index is not None else None,
                        float(result.face_condition_index) if result and result.face_condition_index is not None else None,
                        result.result_quadrant if result else None,tuple(sorted(prod)),tuple(sorted(contour))))
            return ProjectReport(site.name,from_date,to_date,tuple(sorted(blasts,key=lambda x:x.report_date)),tuple(sorted(assessments,key=lambda x:x.assessment_date)))
