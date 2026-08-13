"""Read-only collection of detached data for the first Project report."""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.models import BlastBlock, Domain, Site
from database import assessment_models as orm


from application.dto.project_report import AssessmentReportRow, BlastReportRow, ProjectReport

def _date(value: Any) -> date | None:
    if isinstance(value, date): return value
    if isinstance(value, str):
        try: return date.fromisoformat(value[:10])
        except ValueError: return None
    return None


class SqlAlchemyProjectReportQuery:
    def __init__(self, session_factory): self.session_factory=session_factory

    def collect(self, site_id: int, from_date: date, to_date: date) -> ProjectReport:
        if from_date > to_date: raise ValueError("From date must not be after To date")
        with self.session_factory() as session:
            site=session.get(Site,site_id)
            if site is None: raise ValueError("Project does not exist")
            domains=session.scalars(select(Domain).where(Domain.site_id==site_id)).all()
            names={d.id:d.name for d in domains}; domain_ids=set(names)
            events=list(session.scalars(select(orm.BlastEvent).where(orm.BlastEvent.domain_id.in_(domain_ids)).options(
                selectinload(orm.BlastEvent.technical_card).selectinload(orm.BlastEventTechnicalCard.revisions),
                selectinload(orm.BlastEvent.geometry_revisions),
            ))) if domain_ids else []
            areas=list(session.scalars(select(orm.AssessmentArea).where(orm.AssessmentArea.domain_id.in_(domain_ids)).options(
                selectinload(orm.AssessmentArea.geometry_revisions).selectinload(orm.AssessmentAreaGeometryRevision.event_links).selectinload(orm.AssessmentEventLink.blast_event_geometry_revision).selectinload(orm.BlastEventGeometryRevision.blast_event),
                selectinload(orm.AssessmentArea.evaluation).selectinload(orm.AssessmentAreaEvaluation.revisions),
            ))) if domain_ids else []
            block_ids={e.blast_block_id for e in events if e.blast_block_id}
            blocks={b.id:b.block_number for b in session.scalars(select(BlastBlock).where(BlastBlock.id.in_(block_ids))).all()} if block_ids else {}
            blasts=[]; assessments=[]
            for event in events:
                domain_name=names.get(event.domain_id,"")
                active=next((r for r in event.technical_card.revisions if r.is_active),None) if event.technical_card else None
                payload=active.payload_json if active else {}; actual=payload.get("actual_execution") or {}
                actual_date=_date(actual.get("actual_blast_date")); report_date=actual_date or event.event_date
                if report_date is None or not from_date <= report_date <= to_date: continue
                def number(key):
                    value=actual.get(key); return float(value) if value is not None else None
                blasts.append(BlastReportRow(report_date,event.event_date,actual_date,domain_name,event.event_type,event.name,
                    blocks.get(event.blast_block_id),float(event.elevation_m),event.is_archived,active.status if active else None,
                    number("actual_block_volume_m3"),number("actual_total_explosive_mass_kg"),number("actual_total_drilling_length_m")))
            for area in areas:
                domain_name=names.get(area.domain_id,"")
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
                    f"{float(geometry.min_elevation_m):g}–{float(geometry.max_elevation_m):g}" if geometry else "",
                    geometry.revision_number if geometry else 0,active_eval.status if active_eval else None,
                    float(result.design_achievement_index) if result and result.design_achievement_index is not None else None,
                    float(result.face_condition_index) if result and result.face_condition_index is not None else None,
                    result.result_quadrant if result else None,tuple(sorted(prod)),tuple(sorted(contour))))
            return ProjectReport(site.name,from_date,to_date,tuple(sorted(blasts,key=lambda x:x.report_date)),tuple(sorted(assessments,key=lambda x:x.assessment_date)))
