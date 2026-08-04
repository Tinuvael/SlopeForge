"""Transactional, replace-based PostgreSQL repository for Assessment state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database.models import Site
from database import assessment_models as orm
from prototype_2d.domain import AssessmentDomainState
from repositories.assessment_state_mapper import (
    AssessmentPersistenceCorruptionError, AssessmentSiteNotFoundError,
    validate_assessment_state,
)


@dataclass(frozen=True)
class LoadedAssessmentState:
    site_id: int
    workspace_id: int | None
    state: AssessmentDomainState


def _workspace_query(site_id: int):
    return (select(orm.AssessmentWorkspace).where(orm.AssessmentWorkspace.site_id == site_id)
            .options(
                selectinload(orm.AssessmentWorkspace.datasets),
                selectinload(orm.AssessmentWorkspace.events).selectinload(orm.BlastEvent.geometry_revisions),
                selectinload(orm.AssessmentWorkspace.events).selectinload(orm.BlastEvent.technical_card).selectinload(orm.BlastEventTechnicalCard.revisions),
                selectinload(orm.AssessmentWorkspace.events).selectinload(orm.BlastEvent.attachments),
                selectinload(orm.AssessmentWorkspace.areas).selectinload(orm.AssessmentArea.geometry_revisions).selectinload(orm.AssessmentAreaGeometryRevision.event_links).selectinload(orm.AssessmentEventLink.blast_event_geometry_revision),
                selectinload(orm.AssessmentWorkspace.areas).selectinload(orm.AssessmentArea.evaluation).selectinload(orm.AssessmentAreaEvaluation.revisions),
                selectinload(orm.AssessmentWorkspace.areas).selectinload(orm.AssessmentArea.evaluation).selectinload(orm.AssessmentAreaEvaluation.attachments),
            ))


def _assert_payload(payload, expected, kind: str) -> None:
    for key, value in expected.items():
        if payload.get(key) != value:
            raise AssessmentPersistenceCorruptionError(
                f"{kind} payload field {key!r} disagrees with relational data")


def _state_from_workspace(workspace: orm.AssessmentWorkspace) -> AssessmentDomainState:
    events, areas, cards, evaluations, attachments = [], [], [], [], []
    geometry_owner = {}
    for row in sorted(workspace.events, key=lambda x: x.id):
        revisions = []
        for revision in sorted(row.geometry_revisions, key=lambda x: x.revision_number):
            geometry_owner[revision.id] = (row.domain_id, revision.domain_id)
            revisions.append({"id": revision.domain_id, "blast_event_id": row.domain_id,
                "revision_number": revision.revision_number, "imported_at": revision.imported_at.isoformat(),
                "source_file_name": revision.source_file_name, "source_geometry": revision.source_geometry_json,
                "plan_geometry": revision.plan_geometry_json, "elevation": float(revision.elevation_m),
                "is_active": revision.is_active})
        events.append({"id": row.domain_id, "name": row.name, "event_type": row.event_type,
            "event_date": row.event_date.isoformat() if row.event_date else None, "elevation": float(row.elevation_m),
            "geometry_revisions": revisions,
            "active_geometry_revision_id": next((x.domain_id for x in row.geometry_revisions if x.is_active), None),
            "is_archived": row.is_archived, "archived_at": row.archived_at.isoformat() if row.archived_at else None,
            "archive_reason": row.archive_reason})
        if row.technical_card:
            card = row.technical_card
            revision_payloads = []
            for revision in sorted(card.revisions, key=lambda x: x.revision_number):
                payload = revision.payload_json
                geometry_domain = geometry_owner[revision.blast_event_geometry_revision_id][1]
                _assert_payload(payload, {"id": revision.domain_id, "revision_number": revision.revision_number,
                    "geometry_revision_id": geometry_domain, "event_type": revision.event_type,
                    "status": revision.status}, "technical-card revision")
                revision_payloads.append(payload)
            cards.append({"id": card.domain_id, "blast_event_id": row.domain_id,
                "revisions": revision_payloads,
                "active_revision_id": next((x.domain_id for x in card.revisions if x.is_active), None),
                "is_archived": card.is_archived})
        for item in sorted(row.attachments, key=lambda x: (x.created_at, x.id)):
            attachments.append(_attachment_dict(item, row.domain_id))
    datasets = [{"id": x.domain_id, "name": x.name, "imported_at": x.imported_at.isoformat(),
        "source_file_name": x.source_file_name, "is_active": x.is_active, "lines": x.lines_json}
        for x in sorted(workspace.datasets, key=lambda x: x.id)]
    dataset_domains = {x.id: x.domain_id for x in workspace.datasets}
    for row in sorted(workspace.areas, key=lambda x: x.id):
        revisions, links = [], []
        revision_domains = {x.id: x.domain_id for x in row.geometry_revisions}
        for revision in sorted(row.geometry_revisions, key=lambda x: x.revision_number):
            revisions.append({"id": revision.domain_id, "assessment_area_id": row.domain_id,
                "revision_number": revision.revision_number, "created_at": revision.created_at.isoformat(),
                "source_dataset_id": dataset_domains[revision.source_dataset_id],
                "selection_polygon_frozen": revision.selection_polygon_json,
                "final_geometry_frozen": revision.final_geometry_json,
                "lower_elevation": float(revision.lower_elevation_m), "upper_elevation": float(revision.upper_elevation_m),
                "horizon_slices": revision.horizon_slices_json, "change_reason": revision.change_reason})
            for link in sorted(revision.event_links, key=lambda x: (x.created_at, x.id)):
                event_domain, geometry_domain = geometry_owner[link.blast_event_geometry_revision_id]
                links.append({"id": link.domain_id, "assessment_area_geometry_revision_id": revision.domain_id,
                    "blast_event_id": event_domain, "geometry_revision_id": geometry_domain,
                    "status": link.status, "source": link.source, "created_at": link.created_at.isoformat(),
                    "frozen_intersection_geometry": link.frozen_intersection_geometry_json})
        areas.append({"id": row.domain_id, "name": row.name, "assessment_date": row.assessment_date.isoformat(),
            "geometry_revisions": revisions,
            "active_geometry_revision_id": next((x.domain_id for x in row.geometry_revisions if x.is_active), None),
            "event_links": links, "is_archived": row.is_archived,
            "archived_at": row.archived_at.isoformat() if row.archived_at else None,
            "archive_reason": row.archive_reason})
        if row.evaluation:
            evaluation = row.evaluation
            payloads = []
            for revision in sorted(evaluation.revisions, key=lambda x: x.revision_number):
                payload = revision.payload_json
                area_geometry_domain = revision_domains[revision.assessment_area_geometry_revision_id]
                _assert_payload(payload, {"id": revision.domain_id, "revision_number": revision.revision_number,
                    "assessment_area_geometry_revision_id": area_geometry_domain, "status": revision.status,
                    "matrix_template_id": revision.matrix_template_id,
                    "matrix_template_version": revision.matrix_template_version}, "evaluation revision")
                payloads.append(payload)
            evaluations.append({"id": evaluation.domain_id, "assessment_area_id": row.domain_id,
                "revisions": payloads,
                "active_revision_id": next((x.domain_id for x in evaluation.revisions if x.is_active), None),
                "is_archived": evaluation.is_archived,
                "archived_at": evaluation.archived_at.isoformat() if evaluation.archived_at else None})
            for item in sorted(evaluation.attachments, key=lambda x: (x.created_at, x.id)):
                attachments.append(_attachment_dict(item, evaluation.domain_id))
    return AssessmentDomainState.from_dict({"datasets": datasets, "blast_events": events,
        "assessment_areas": areas, "technical_cards": cards, "evaluations": evaluations,
        "attachments": sorted(attachments, key=lambda x: (x["created_at"], x["id"]))})


def _attachment_dict(row, owner_id):
    return {"id": row.domain_id, "owner_type": row.owner_type, "owner_id": owner_id,
        "attachment_kind": row.attachment_kind, "subtype": row.subtype, "custom_subtype": row.custom_subtype,
        "title": row.title, "original_filename": row.original_filename, "stored_filename": row.stored_filename,
        "relative_path": row.relative_path, "file_date": row.file_date.isoformat(), "description": row.description,
        "mime_type": row.mime_type, "file_size_bytes": row.file_size_bytes, "created_at": row.created_at.isoformat()}


class AssessmentStateRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def load_for_site(self, site_id: int) -> LoadedAssessmentState:
        with self._session_factory() as session:
            if session.get(Site, site_id) is None:
                raise AssessmentSiteNotFoundError(f"Site {site_id} does not exist")
            workspace = session.scalars(_workspace_query(site_id)).one_or_none()
            return LoadedAssessmentState(site_id, workspace.id if workspace else None,
                _state_from_workspace(workspace) if workspace else AssessmentDomainState())

    def replace_for_site(self, site_id: int, state: AssessmentDomainState) -> LoadedAssessmentState:
        validate_assessment_state(state)
        with self._session_factory() as session:
            with session.begin():
                if session.get(Site, site_id) is None:
                    raise AssessmentSiteNotFoundError(f"Site {site_id} does not exist")
                previous = session.scalars(_workspace_query(site_id)).one_or_none()
                if previous:
                    session.delete(previous)
                    session.flush()
                workspace = orm.AssessmentWorkspace(site_id=site_id)
                session.add(workspace)
                session.flush()
                self._insert(session, workspace, state)
                session.flush()
                saved = _state_from_workspace(session.scalars(_workspace_query(site_id)).one())
                result = LoadedAssessmentState(site_id, workspace.id, saved)
            return result

    @staticmethod
    def _insert(session, workspace, state):
        datasets = {}
        for item in state.datasets:
            row = orm.ProjectLinesDataset(workspace=workspace, domain_id=item.id, name=item.name,
                imported_at=item.imported_at, source_file_name=item.source_file_name,
                is_active=item.is_active, lines_json=[x.to_dict() for x in item.lines])
            session.add(row); datasets[item.id] = row
        events, geometries = {}, {}
        for item in state.blast_events:
            row = orm.BlastEvent(workspace=workspace, domain_id=item.id, name=item.name,
                event_type=item.event_type, event_date=item.event_date, elevation_m=item.elevation,
                blast_block_id=None, is_archived=item.is_archived, archived_at=item.archived_at,
                archive_reason=item.archive_reason)
            session.add(row); events[item.id] = row
            for revision in item.geometry_revisions:
                child = orm.BlastEventGeometryRevision(blast_event=row, domain_id=revision.id,
                    revision_number=revision.revision_number, imported_at=revision.imported_at,
                    source_file_name=revision.source_file_name,
                    source_geometry_json=[x.to_dict() for x in revision.source_geometry],
                    plan_geometry_json=revision.plan_geometry.to_dict(), elevation_m=revision.elevation,
                    is_active=revision.id == item.active_geometry_revision_id)
                session.add(child); geometries[revision.id] = child
        areas, area_geometries = {}, {}
        for item in state.assessment_areas:
            row = orm.AssessmentArea(workspace=workspace, domain_id=item.id, name=item.name,
                assessment_date=item.assessment_date, is_archived=item.is_archived,
                archived_at=item.archived_at, archive_reason=item.archive_reason)
            session.add(row); areas[item.id] = row
            for revision in item.geometry_revisions:
                child = orm.AssessmentAreaGeometryRevision(assessment_area=row, domain_id=revision.id,
                    revision_number=revision.revision_number, created_at=revision.created_at,
                    source_dataset=datasets[revision.source_dataset_id],
                    selection_polygon_json=revision.selection_polygon_frozen.to_dict(),
                    final_geometry_json=revision.final_geometry_frozen.to_dict(),
                    lower_elevation_m=revision.lower_elevation, upper_elevation_m=revision.upper_elevation,
                    horizon_slices_json=[x.to_dict() for x in revision.horizon_slices],
                    change_reason=revision.change_reason, is_active=revision.id == item.active_geometry_revision_id)
                session.add(child); area_geometries[revision.id] = child
        session.flush()
        for area in state.assessment_areas:
            for link in area.event_links:
                session.add(orm.AssessmentEventLink(
                    assessment_area_geometry_revision=area_geometries[link.assessment_area_geometry_revision_id],
                    blast_event_geometry_revision=geometries[link.geometry_revision_id], domain_id=link.id,
                    status=link.status, source=link.source,
                    frozen_intersection_geometry_json=link.frozen_intersection_geometry.to_dict() if link.frozen_intersection_geometry else None,
                    created_at=link.created_at))
        for card in state.technical_cards:
            row = orm.BlastEventTechnicalCard(blast_event=events[card.blast_event_id], domain_id=card.id,
                is_archived=card.is_archived)
            session.add(row)
            serialized_revisions = {item["id"]: item for item in card.to_dict()["revisions"]}
            for revision in card.revisions:
                session.add(orm.BlastEventTechnicalCardRevision(technical_card=row, domain_id=revision.id,
                    revision_number=revision.revision_number, created_at=revision.created_at,
                    geometry_revision=geometries[revision.geometry_revision_id], event_type=revision.event_type,
                    status=revision.status, author=revision.author, change_reason=revision.change_reason,
                    payload_json=serialized_revisions[revision.id], is_active=revision.id == card.active_revision_id))
        evaluations = {}
        for evaluation in state.evaluations:
            row = orm.AssessmentAreaEvaluation(assessment_area=areas[evaluation.assessment_area_id],
                domain_id=evaluation.id, is_archived=evaluation.is_archived, archived_at=evaluation.archived_at)
            session.add(row); evaluations[evaluation.id] = row
            for revision in evaluation.revisions:
                session.add(orm.AssessmentAreaEvaluationRevision(evaluation=row, domain_id=revision.id,
                    revision_number=revision.revision_number, created_at=revision.created_at,
                    geometry_revision=area_geometries[revision.assessment_area_geometry_revision_id],
                    assessment_date=revision.assessment_date, inspector=revision.inspector, status=revision.status,
                    matrix_template_id=revision.matrix_template_id, matrix_template_version=revision.matrix_template_version,
                    design_achievement_index=revision.design_achievement_index,
                    face_condition_index=revision.face_condition_index, result_quadrant=revision.result_quadrant,
                    payload_json=revision.to_dict(), is_active=revision.id == evaluation.active_revision_id))
        session.flush()
        for item in state.attachments:
            values = item.to_dict()
            for key in ("id", "owner_id", "file_date", "created_at"):
                values.pop(key)
            session.add(orm.AssessmentEntityAttachment(domain_id=item.id,
                blast_event=events[item.owner_id] if item.owner_type == "blast_event" else None,
                assessment_area_evaluation=evaluations[item.owner_id] if item.owner_type == "assessment_evaluation" else None,
                file_date=item.file_date, created_at=item.created_at, **values))
