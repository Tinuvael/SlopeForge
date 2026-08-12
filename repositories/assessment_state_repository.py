"""Transactional, in-place synchronization of PostgreSQL Assessment state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from database.models import Domain
from database import assessment_models as orm
from application.state.assessment_domain_state import AssessmentDomainState
from repositories.assessment_state_mapper import (
    AssessmentPersistenceCorruptionError, AssessmentSiteNotFoundError,
)


@dataclass(frozen=True)
class LoadedAssessmentState:
    domain_id: int
    site_id: int
    workspace_id: int | None
    state: AssessmentDomainState
    expected_version: int


def _workspace_query(domain_id: int):
    return (select(orm.AssessmentWorkspace).where(orm.AssessmentWorkspace.domain_id == domain_id)
            .options(
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


def _state_from_workspace(workspace: orm.AssessmentWorkspace | None,
                          dataset_rows: list[orm.ProjectLinesDataset]) -> AssessmentDomainState:
    events, areas, cards, evaluations, attachments = [], [], [], [], []
    geometry_owner = {}
    if workspace is None:
        return AssessmentDomainState.from_dict({"datasets": _dataset_dicts(dataset_rows)})
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
            "blast_block_id": row.blast_block_id,
            "geometry_revisions": revisions,
            "active_geometry_revision_id": next((x.domain_id for x in row.geometry_revisions if x.is_active), None),
            "is_archived": row.is_archived, "archived_at": row.archived_at.isoformat() if row.archived_at else None,
            "archive_reason": row.archive_reason})
        if row.technical_card:
            card = row.technical_card
            revision_payloads = []
            for revision in sorted(card.revisions, key=lambda x: x.revision_number):
                payload = revision.payload_json
                owner = geometry_owner.get(revision.blast_event_geometry_revision_id)
                if owner is None or owner[0] != row.domain_id:
                    raise AssessmentPersistenceCorruptionError(
                        "technical-card geometry revision belongs to another BlastEvent or workspace")
                geometry_domain = owner[1]
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
    datasets = _dataset_dicts(dataset_rows)
    dataset_domains = {x.id: x.domain_id for x in dataset_rows}
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
                target = link.blast_event_geometry_revision
                if target.blast_event.workspace_id != workspace.id:
                    raise AssessmentPersistenceCorruptionError(
                        "AssessmentEventLink connects revisions from different workspaces")
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
                area_geometry_domain = revision_domains.get(revision.assessment_area_geometry_revision_id)
                if area_geometry_domain is None:
                    raise AssessmentPersistenceCorruptionError(
                        "evaluation geometry revision belongs to another Assessment Area")
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
    state = AssessmentDomainState.from_dict({"datasets": datasets, "blast_events": events,
        "assessment_areas": areas, "technical_cards": cards, "evaluations": evaluations,
        "attachments": sorted(attachments, key=lambda x: (x["created_at"], x["id"]))})
    try:
        validate_assessment_state(state)
    except AssessmentStateValidationError as exc:
        raise AssessmentPersistenceCorruptionError(
            f"persisted Assessment state is invalid: {exc}") from exc
    return state


def _dataset_dicts(rows):
    return [{"id": x.domain_id, "name": x.name, "imported_at": x.imported_at.isoformat(),
        "source_file_name": x.source_file_name, "is_active": x.is_active, "lines": x.lines_json}
        for x in sorted(rows, key=lambda x: x.id)]


def _attachment_dict(row, owner_id):
    return {"id": row.domain_id, "owner_type": row.owner_type, "owner_id": owner_id,
        "attachment_kind": row.attachment_kind, "subtype": row.subtype, "custom_subtype": row.custom_subtype,
        "title": row.title, "original_filename": row.original_filename, "stored_filename": row.stored_filename,
        "relative_path": row.relative_path, "file_date": row.file_date.isoformat(), "description": row.description,
        "mime_type": row.mime_type, "file_size_bytes": row.file_size_bytes, "created_at": row.created_at.isoformat()}


class AssessmentStateRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def load_for_domain(self, domain_id: int) -> LoadedAssessmentState:
        with self._session_factory() as session:
            domain = session.get(Domain, domain_id)
            if domain is None:
                raise AssessmentSiteNotFoundError(f"Domain {domain_id} does not exist")
            workspace = session.scalars(_workspace_query(domain_id)).one_or_none()
            datasets = list(session.scalars(select(orm.ProjectLinesDataset).where(
                orm.ProjectLinesDataset.site_id == domain.site_id)))
            return LoadedAssessmentState(domain.id, domain.site_id,
                workspace.id if workspace else None,
                _state_from_workspace(workspace, datasets), domain.version)
