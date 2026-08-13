"""TEST-ONLY realistic Assessment ORM graph seeding; never import from production."""
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
    AssessmentStateValidationError, validate_assessment_state,
)


@dataclass(frozen=True)
class LoadedAssessmentState:
    domain_id: int
    site_id: int
    state: AssessmentDomainState
    expected_version: int


def _domain_graph(domain_id: int):
    events = select(orm.BlastEvent).where(orm.BlastEvent.domain_id == domain_id).options(
        selectinload(orm.BlastEvent.geometry_revisions), selectinload(orm.BlastEvent.technical_card).selectinload(orm.BlastEventTechnicalCard.revisions), selectinload(orm.BlastEvent.attachments))
    areas = select(orm.AssessmentArea).where(orm.AssessmentArea.domain_id == domain_id).options(
        selectinload(orm.AssessmentArea.geometry_revisions).selectinload(orm.AssessmentAreaGeometryRevision.event_links).selectinload(orm.AssessmentEventLink.blast_event_geometry_revision),
        selectinload(orm.AssessmentArea.evaluation).selectinload(orm.AssessmentAreaEvaluation.revisions), selectinload(orm.AssessmentArea.evaluation).selectinload(orm.AssessmentAreaEvaluation.attachments))
    return events, areas


def _assert_payload(payload, expected, kind: str) -> None:
    for key, value in expected.items():
        if payload.get(key) != value:
            raise AssessmentPersistenceCorruptionError(
                f"{kind} payload field {key!r} disagrees with relational data")


def _state_from_domain(events_rows, areas_rows,
                          dataset_rows: list[orm.ProjectLinesDataset]) -> AssessmentDomainState:
    events, areas, cards, evaluations, attachments = [], [], [], [], []
    geometry_owner = {}
    for row in sorted(events_rows, key=lambda x: x.id):
        revisions = []
        for revision in sorted(row.geometry_revisions, key=lambda x: x.revision_number):
            geometry_owner[revision.id] = (row.logical_id, revision.logical_id)
            revisions.append({"id": revision.logical_id, "blast_event_id": row.logical_id,
                "revision_number": revision.revision_number, "imported_at": revision.imported_at.isoformat(),
                "source_file_name": revision.source_file_name, "source_geometry": revision.source_geometry_json,
                "plan_geometry": revision.plan_geometry_json, "elevation": float(revision.elevation_m),
                "is_active": revision.is_active})
        events.append({"id": row.logical_id, "name": row.name, "event_type": row.event_type,
            "event_date": row.event_date.isoformat() if row.event_date else None, "elevation": float(row.elevation_m),
            "blast_block_id": row.blast_block_id,
            "geometry_revisions": revisions,
            "active_geometry_revision_id": next((x.logical_id for x in row.geometry_revisions if x.is_active), None),
            "is_archived": row.is_archived, "archived_at": row.archived_at.isoformat() if row.archived_at else None,
            "archive_reason": row.archive_reason})
        if row.technical_card:
            card = row.technical_card
            revision_payloads = []
            for revision in sorted(card.revisions, key=lambda x: x.revision_number):
                payload = revision.payload_json
                owner = geometry_owner.get(revision.blast_event_geometry_revision_id)
                if owner is None or owner[0] != row.logical_id:
                    raise AssessmentPersistenceCorruptionError(
                        "technical-card geometry revision belongs to another BlastEvent or Domain")
                geometry_domain = owner[1]
                _assert_payload(payload, {"id": revision.logical_id, "revision_number": revision.revision_number,
                    "geometry_revision_id": geometry_domain, "event_type": revision.event_type,
                    "status": revision.status}, "technical-card revision")
                revision_payloads.append(payload)
            cards.append({"id": card.logical_id, "blast_event_id": row.logical_id,
                "revisions": revision_payloads,
                "active_revision_id": next((x.logical_id for x in card.revisions if x.is_active), None),
                "is_archived": card.is_archived})
        for item in sorted(row.attachments, key=lambda x: (x.created_at, x.id)):
            attachments.append(_attachment_dict(item, row.logical_id))
    datasets = _dataset_dicts(dataset_rows)
    for row in sorted(areas_rows, key=lambda x: x.id):
        revisions, links = [], []
        revision_domains = {x.id: x.logical_id for x in row.geometry_revisions}
        for revision in sorted(row.geometry_revisions, key=lambda x: x.revision_number):
            revisions.append({"id": revision.logical_id, "assessment_area_id": row.logical_id,
                "revision_number": revision.revision_number, "created_at": revision.created_at.isoformat(),
                "boundary": revision.boundary_json, "final_geometry_frozen": revision.final_geometry_json,
                "min_elevation": float(revision.min_elevation_m) if revision.min_elevation_m is not None else None,
                "max_elevation": float(revision.max_elevation_m) if revision.max_elevation_m is not None else None,
                "change_reason": revision.change_reason})
            for link in sorted(revision.event_links, key=lambda x: (x.created_at, x.id)):
                target = link.blast_event_geometry_revision
                if target.blast_event.domain_id != row.domain_id:
                    raise AssessmentPersistenceCorruptionError(
                        "AssessmentEventLink connects revisions from different Domains")
                event_domain, geometry_domain = geometry_owner[link.blast_event_geometry_revision_id]
                links.append({"id": link.logical_id, "assessment_area_geometry_revision_id": revision.logical_id,
                    "blast_event_id": event_domain, "geometry_revision_id": geometry_domain,
                    "status": link.status, "source": link.source, "created_at": link.created_at.isoformat(),
                    "frozen_intersection_geometry": link.frozen_intersection_geometry_json})
        areas.append({"id": row.logical_id, "name": row.name, "assessment_date": row.assessment_date.isoformat(),
            "geometry_revisions": revisions,
            "active_geometry_revision_id": next((x.logical_id for x in row.geometry_revisions if x.is_active), None),
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
                _assert_payload(payload, {"id": revision.logical_id, "revision_number": revision.revision_number,
                    "assessment_area_geometry_revision_id": area_geometry_domain, "status": revision.status,
                    "matrix_template_id": revision.matrix_template_id,
                    "matrix_template_version": revision.matrix_template_version}, "evaluation revision")
                payloads.append(payload)
            evaluations.append({"id": evaluation.logical_id, "assessment_area_id": row.logical_id,
                "revisions": payloads,
                "active_revision_id": next((x.logical_id for x in evaluation.revisions if x.is_active), None),
                "is_archived": evaluation.is_archived,
                "archived_at": evaluation.archived_at.isoformat() if evaluation.archived_at else None})
            for item in sorted(evaluation.attachments, key=lambda x: (x.created_at, x.id)):
                attachments.append(_attachment_dict(item, evaluation.logical_id))
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
    return [{"id": x.logical_id, "name": x.name, "imported_at": x.imported_at.isoformat(),
        "source_file_name": x.source_file_name, "is_active": x.is_active, "lines": x.lines_json}
        for x in sorted(rows, key=lambda x: x.id)]


def _attachment_dict(row, owner_id):
    return {"id": row.logical_id, "owner_type": row.owner_type, "owner_id": owner_id,
        "attachment_kind": row.attachment_kind, "subtype": row.subtype, "custom_subtype": row.custom_subtype,
        "title": row.title, "original_filename": row.original_filename, "stored_filename": row.stored_filename,
        "relative_path": row.relative_path, "file_date": row.file_date.isoformat(), "description": row.description,
        "mime_type": row.mime_type, "file_size_bytes": row.file_size_bytes, "created_at": row.created_at.isoformat()}


class AssessmentGraphSeeder:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def load_for_domain(self, domain_id: int) -> LoadedAssessmentState:
        with self._session_factory() as session:
            domain = session.get(Domain, domain_id)
            if domain is None:
                raise AssessmentSiteNotFoundError(f"Domain {domain_id} does not exist")
            event_q, area_q = _domain_graph(domain_id)
            events = list(session.scalars(event_q)); areas = list(session.scalars(area_q))
            datasets = list(session.scalars(select(orm.ProjectLinesDataset).where(
                orm.ProjectLinesDataset.site_id == domain.site_id)))
            return LoadedAssessmentState(domain.id, domain.site_id,
                _state_from_domain(events, areas, datasets), domain.version)

    def seed_for_domain(self, domain_id: int, state: AssessmentDomainState) -> LoadedAssessmentState:
        """Compatibility-only whole-state synchronization retained through Phase 5C."""
        # Keep the original public transaction boundary: validation, one owned
        # transaction, and the same fully reloaded return value.
        validate_assessment_state(state)
        with self._session_factory.begin() as session:
            return self.seed_for_domain_in_session(session, domain_id, state)

    def seed_for_domain_in_session(
        self, session: Session, domain_id: int, state: AssessmentDomainState,
    ) -> LoadedAssessmentState:
        """Synchronize whole state without commit; the caller owns the transaction."""
        validate_assessment_state(state)
        domain = session.get(Domain, domain_id)
        if domain is None:
            raise AssessmentSiteNotFoundError(f"Domain {domain_id} does not exist")
        event_q, area_q = _domain_graph(domain_id)
        events_rows = list(session.scalars(event_q)); areas_rows = list(session.scalars(area_q))
        datasets = list(session.scalars(select(orm.ProjectLinesDataset).where(
            orm.ProjectLinesDataset.site_id == domain.site_id)))
        self._synchronize(session, domain_id, events_rows, areas_rows, state, datasets)
        session.flush()
        # Refresh only this aggregate.  The supplied session can also contain a
        # newly-created BlastBlock/audit objects owned by the caller.
        event_q, area_q = _domain_graph(domain_id)
        saved = _state_from_domain(list(session.scalars(event_q)), list(session.scalars(area_q)), datasets)
        return LoadedAssessmentState(domain_id, domain.site_id, saved, domain.version)

    @staticmethod
    def _synchronize(session, domain_id, events_rows, areas_rows, state, dataset_rows):
        """Explicitly match Domain-owned rows by stable logical IDs."""
        datasets = {row.logical_id: row for row in dataset_rows}


        events = {row.logical_id: row for row in events_rows}
        areas = {row.logical_id: row for row in areas_rows}
        # Avoid transient partial-unique-index conflicts when the active row moves.
        active_rows = [r for e in events.values() for r in e.geometry_revisions if r.is_active]
        active_rows += [r for e in events.values() if e.technical_card
                       for r in e.technical_card.revisions if r.is_active]
        active_rows += [r for a in areas.values() for r in a.geometry_revisions if r.is_active]
        active_rows += [r for a in areas.values() if a.evaluation
                       for r in a.evaluation.revisions if r.is_active]
        for row in active_rows:
            row.is_active = False
        if active_rows:
            session.flush()

        desired_event_ids = {item.id for item in state.blast_events}
        geometries = {}
        for item in state.blast_events:
            row = events.get(item.id)
            if row is None:
                row = orm.BlastEvent(domain_id=domain_id, logical_id=item.id)
                session.add(row); events[item.id] = row
            row.name = item.name; row.event_type = item.event_type
            row.event_date = item.event_date; row.elevation_m = item.elevation
            row.blast_block_id = item.blast_block_id; row.is_archived = item.is_archived
            row.archived_at = item.archived_at; row.archive_reason = item.archive_reason
            existing = {r.logical_id: r for r in row.geometry_revisions}
            for revision in item.geometry_revisions:
                child = existing.get(revision.id)
                if child is None:
                    child = orm.BlastEventGeometryRevision(blast_event=row, logical_id=revision.id)
                    session.add(child)
                child.revision_number = revision.revision_number
                child.imported_at = revision.imported_at
                child.source_file_name = revision.source_file_name
                child.source_geometry_json = [x.to_dict() for x in revision.source_geometry]
                child.plan_geometry_json = revision.plan_geometry.to_dict()
                child.elevation_m = revision.elevation
                child.is_active = revision.id == item.active_geometry_revision_id
                geometries[revision.id] = child

        desired_area_ids = {item.id for item in state.assessment_areas}
        area_geometries = {}
        for item in state.assessment_areas:
            row = areas.get(item.id)
            if row is None:
                row = orm.AssessmentArea(domain_id=domain_id, logical_id=item.id)
                session.add(row); areas[item.id] = row
            row.name = item.name; row.assessment_date = item.assessment_date
            row.is_archived = item.is_archived; row.archived_at = item.archived_at
            row.archive_reason = item.archive_reason
            existing = {r.logical_id: r for r in row.geometry_revisions}
            for revision in item.geometry_revisions:
                child = existing.get(revision.id)
                if child is None:
                    child = orm.AssessmentAreaGeometryRevision(assessment_area=row, logical_id=revision.id)
                    session.add(child)
                child.revision_number = revision.revision_number; child.created_at = revision.created_at
                child.boundary_json = revision.boundary.to_dict()
                child.final_geometry_json = revision.final_geometry_frozen.to_dict()
                child.min_elevation_m = revision.min_elevation
                child.max_elevation_m = revision.max_elevation
                child.change_reason = revision.change_reason
                child.is_active = revision.id == item.active_geometry_revision_id
                area_geometries[revision.id] = child
        session.flush()

        existing_links = {(link.assessment_area_geometry_revision.logical_id, link.logical_id): link
                          for area in areas_rows for revision in area.geometry_revisions
                          for link in revision.event_links}
        desired_links = [(link.assessment_area_geometry_revision_id, link)
                         for area in state.assessment_areas for link in area.event_links]
        desired_link_keys = {(revision_id, link.id) for revision_id, link in desired_links}
        # Remove obsolete unique-key occupants before moving a retained link to
        # their (area revision, event revision, source) tuple.
        omitted_links = [row for key, row in existing_links.items()
                         if key not in desired_link_keys]
        for row in omitted_links:
            session.delete(row)
        if omitted_links:
            session.flush()
        for revision_id, link in desired_links:
            key = (revision_id, link.id)
            row = existing_links.get(key)
            if row is None:
                row = orm.AssessmentEventLink(logical_id=link.id); session.add(row)
            row.assessment_area_geometry_revision = area_geometries[link.assessment_area_geometry_revision_id]
            row.blast_event_geometry_revision = geometries[link.geometry_revision_id]
            row.status = link.status; row.source = link.source
            row.frozen_intersection_geometry_json = (link.frozen_intersection_geometry.to_dict()
                                                       if link.frozen_intersection_geometry else None)
            row.created_at = link.created_at

        cards = {e.technical_card.logical_id: e.technical_card for e in events_rows
                 if e.technical_card is not None}
        desired_card_ids = {card.id for card in state.technical_cards}
        desired_card_revision_ids = set()
        for card in state.technical_cards:
            row = cards.get(card.id)
            if row is None:
                row = orm.BlastEventTechnicalCard(blast_event=events[card.blast_event_id],
                                                   logical_id=card.id)
                session.add(row); cards[card.id] = row
            row.blast_event = events[card.blast_event_id]; row.is_archived = card.is_archived
            existing = {r.logical_id: r for r in row.revisions}
            payloads = {item["id"]: item for item in card.to_dict()["revisions"]}
            for revision in card.revisions:
                desired_card_revision_ids.add((card.id, revision.id))
                child = existing.get(revision.id)
                if child is None:
                    child = orm.BlastEventTechnicalCardRevision(technical_card=row,
                                                                 logical_id=revision.id)
                    session.add(child)
                child.revision_number = revision.revision_number; child.created_at = revision.created_at
                child.geometry_revision = geometries[revision.geometry_revision_id]
                child.event_type = revision.event_type; child.status = revision.status
                child.author = revision.author; child.change_reason = revision.change_reason
                child.payload_json = payloads[revision.id]
                child.is_active = revision.id == card.active_revision_id

        evaluations = {a.evaluation.logical_id: a.evaluation for a in areas_rows
                       if a.evaluation is not None}
        desired_evaluation_ids = {item.id for item in state.evaluations}
        desired_evaluation_revision_ids = set()
        for evaluation in state.evaluations:
            row = evaluations.get(evaluation.id)
            if row is None:
                row = orm.AssessmentAreaEvaluation(
                    assessment_area=areas[evaluation.assessment_area_id], logical_id=evaluation.id)
                session.add(row); evaluations[evaluation.id] = row
            row.assessment_area = areas[evaluation.assessment_area_id]
            row.is_archived = evaluation.is_archived; row.archived_at = evaluation.archived_at
            existing = {r.logical_id: r for r in row.revisions}
            for revision in evaluation.revisions:
                desired_evaluation_revision_ids.add((evaluation.id, revision.id))
                child = existing.get(revision.id)
                if child is None:
                    child = orm.AssessmentAreaEvaluationRevision(evaluation=row,
                                                                  logical_id=revision.id)
                    session.add(child)
                child.revision_number = revision.revision_number; child.created_at = revision.created_at
                child.geometry_revision = area_geometries[revision.assessment_area_geometry_revision_id]
                child.assessment_date = revision.assessment_date; child.inspector = revision.inspector
                child.status = revision.status; child.matrix_template_id = revision.matrix_template_id
                child.matrix_template_version = revision.matrix_template_version
                child.design_achievement_index = revision.design_achievement_index
                child.face_condition_index = revision.face_condition_index
                child.result_quadrant = revision.result_quadrant
                child.payload_json = revision.to_dict()
                child.is_active = revision.id == evaluation.active_revision_id
        session.flush()

        existing_attachments = {x.logical_id: x for e in events_rows for x in e.attachments}
        existing_attachments.update({x.logical_id: x for a in areas_rows if a.evaluation
                                     for x in a.evaluation.attachments})
        desired_attachment_ids = {item.id for item in state.attachments}
        for item in state.attachments:
            values = item.to_dict()
            for key in ("id", "owner_id", "file_date", "created_at"):
                values.pop(key)
            row = existing_attachments.get(item.id)
            if row is None:
                row = orm.AssessmentEntityAttachment(logical_id=item.id); session.add(row)
            row.blast_event = events[item.owner_id] if item.owner_type == "blast_event" else None
            row.assessment_area_evaluation = (evaluations[item.owner_id]
                                              if item.owner_type == "assessment_evaluation" else None)
            row.file_date = item.file_date; row.created_at = item.created_at
            for key, value in values.items():
                setattr(row, key, value)

        # RESTRICT-safe deletion: leaves, containers, revisions, then parents.
        for key, row in existing_attachments.items():
            if key not in desired_attachment_ids: session.delete(row)
        for card_id, row in cards.items():
            for revision in row.revisions:
                if (card_id, revision.logical_id) not in desired_card_revision_ids:
                    session.delete(revision)
        for evaluation_id, row in evaluations.items():
            for revision in row.revisions:
                if (evaluation_id, revision.logical_id) not in desired_evaluation_revision_ids:
                    session.delete(revision)
        session.flush()
        for key, row in cards.items():
            if key not in desired_card_ids: session.delete(row)
        for key, row in evaluations.items():
            if key not in desired_evaluation_ids: session.delete(row)
        session.flush()
        for row in events.values():
            for revision in row.geometry_revisions:
                if revision.logical_id not in geometries: session.delete(revision)
        for row in areas.values():
            for revision in row.geometry_revisions:
                if revision.logical_id not in area_geometries: session.delete(revision)
        session.flush()
        for key, row in events.items():
            if key not in desired_event_ids: session.delete(row)
        for key, row in areas.items():
            if key not in desired_area_ids: session.delete(row)
