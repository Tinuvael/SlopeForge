"""SQLAlchemy implementation of narrow, transactional Assessment writes."""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import assessment_models as orm
from database.models import Domain
from application.ports.domain_version import DomainWriteResult
from infrastructure.db.domain_version import guard_domain_versions
from application.services.assessment_event_links import AssessmentEventLinkService
from repositories.assessment_state_repository import _domain_graph_queries, _state_from_domain


class SqlAlchemyAssessmentWrites:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @staticmethod
    def _logical(session, model, domain_id, logical_id):
        row = session.scalar(select(model).where(
            model.domain_id == domain_id, model.logical_id == logical_id))
        if row is None:
            raise ValueError(f"Assessment entity {logical_id!r} is not persisted in Domain {domain_id}")
        return row

    def persist_area_archive(self, domain_id, expected_version, area):
        with self._session_factory.begin() as s:
            new_version = guard_domain_versions(s, {domain_id: expected_version})[domain_id]
            row = self._logical(s, orm.AssessmentArea, domain_id, area.id)
            row.is_archived, row.archived_at, row.archive_reason = (
                area.is_archived, area.archived_at, area.archive_reason)
            return DomainWriteResult(new_version)

    def persist_contour_archive(self, domain_id, expected_version, event):
        if event.event_type != "contour":
            raise ValueError("Only contour BlastEvents can use contour archive")
        with self._session_factory.begin() as s:
            new_version = guard_domain_versions(s, {domain_id: expected_version})[domain_id]
            row = self._logical(s, orm.BlastEvent, domain_id, event.id)
            if row.event_type != "contour":
                raise ValueError("Stored BlastEvent is not contour")
            row.is_archived, row.archived_at, row.archive_reason = (
                event.is_archived, event.archived_at, event.archive_reason)
            return DomainWriteResult(new_version)

    @staticmethod
    def _same_project(s, source_id, target_id):
        domains = {row.id: row for row in s.scalars(
            select(Domain).where(Domain.id.in_({source_id, target_id})))}
        if len(domains) != (1 if source_id == target_id else 2):
            raise ValueError("Select an existing Domain")
        if domains[source_id].site_id != domains[target_id].site_id:
            raise ValueError("Entities can only move between Domains of the same Project")
        return domains[source_id].site_id

    @classmethod
    def _rebuild_current_suggestions(cls, s, domain_id, *, area_logical_id=None):
        events_query, areas_query = _domain_graph_queries(domain_id)
        events = list(s.scalars(events_query).unique())
        areas = list(s.scalars(areas_query).unique())
        site_id = s.get(Domain, domain_id).site_id
        datasets = list(s.scalars(select(orm.ProjectLinesDataset).where(
            orm.ProjectLinesDataset.site_id == site_id)))
        state = _state_from_domain(events, areas, datasets)
        service = AssessmentEventLinkService(state)
        for area in state.assessment_areas:
            if area_logical_id is not None and area.id != area_logical_id:
                continue
            service.refresh_suggestions(area)
            row = cls._logical(s, orm.AssessmentArea, domain_id, area.id)
            cls._sync_links(s, row, area.active_geometry_revision_id,
                            area.links_for_revision())

    @staticmethod
    def _remove_current_cross_domain_links(s, domain_id):
        rows = list(s.scalars(select(orm.AssessmentEventLink).join(
            orm.AssessmentAreaGeometryRevision).join(orm.AssessmentArea).join(
            orm.BlastEventGeometryRevision,
            orm.AssessmentEventLink.blast_event_geometry_revision_id == orm.BlastEventGeometryRevision.id
        ).join(orm.BlastEvent).where(
            orm.AssessmentAreaGeometryRevision.is_active.is_(True),
            orm.AssessmentArea.domain_id == domain_id,
            orm.BlastEvent.domain_id != domain_id)))
        for row in rows: s.delete(row)
        if rows: s.flush()

    def update_contour_metadata(self, domain_id, expected_version,
                                target_domain_id, target_expected_version,
                                event_id, name, elevation):
        if not name.strip(): raise ValueError("Name is required")
        with self._session_factory.begin() as s:
            self._same_project(s, domain_id, target_domain_id)
            expected = {domain_id: expected_version}
            if target_domain_id != domain_id:
                expected[target_domain_id] = target_expected_version
            versions = guard_domain_versions(s, expected)
            row = self._logical(s, orm.BlastEvent, domain_id, event_id)
            if row.event_type != "contour": raise ValueError("Stored BlastEvent is not contour")
            row.name, row.elevation_m = name.strip(), elevation
            if target_domain_id != domain_id:
                row.domain_id = target_domain_id; s.flush()
                self._remove_current_cross_domain_links(s, domain_id)
                self._remove_current_cross_domain_links(s, target_domain_id)
                self._rebuild_current_suggestions(s, target_domain_id)
            return DomainWriteResult(versions[target_domain_id])

    def update_assessment_area_metadata(self, domain_id, expected_version,
                                        target_domain_id, target_expected_version,
                                        area_id, name):
        if not name.strip(): raise ValueError("Name is required")
        with self._session_factory.begin() as s:
            self._same_project(s, domain_id, target_domain_id)
            expected = {domain_id: expected_version}
            if target_domain_id != domain_id:
                expected[target_domain_id] = target_expected_version
            versions = guard_domain_versions(s, expected)
            row = self._logical(s, orm.AssessmentArea, domain_id, area_id)
            row.name = name.strip()
            if target_domain_id != domain_id:
                row.domain_id = target_domain_id; s.flush()
                self._remove_current_cross_domain_links(s, target_domain_id)
                self._rebuild_current_suggestions(s, target_domain_id,
                                                  area_logical_id=area_id)
            return DomainWriteResult(versions[target_domain_id])

    def append_blast_geometry_revision(self, domain_id, expected_version, event_id, revision):
        with self._session_factory.begin() as s:
            new_version = guard_domain_versions(s, {domain_id: expected_version})[domain_id]
            event = self._logical(s, orm.BlastEvent, domain_id, event_id)
            duplicate = s.scalar(select(orm.BlastEventGeometryRevision.id).where(
                orm.BlastEventGeometryRevision.blast_event_id == event.id,
                (orm.BlastEventGeometryRevision.logical_id == revision.id) |
                (orm.BlastEventGeometryRevision.revision_number == revision.revision_number)))
            if duplicate is not None:
                raise ValueError("Blast geometry revision ID or number already exists")
            s.query(orm.BlastEventGeometryRevision).filter_by(
                blast_event_id=event.id, is_active=True).update({"is_active": False})
            s.flush()
            s.add(orm.BlastEventGeometryRevision(
                blast_event=event, logical_id=revision.id,
                revision_number=revision.revision_number, imported_at=revision.imported_at,
                source_file_name=revision.source_file_name,
                source_geometry_json=[x.to_dict() for x in revision.source_geometry],
                plan_geometry_json=revision.plan_geometry.to_dict(),
                elevation_m=revision.elevation, is_active=True))
            return DomainWriteResult(new_version)

    def persist_technical_card_revision(self, domain_id, expected_version, card, revision, event_date=...):
        with self._session_factory.begin() as s:
            new_version = guard_domain_versions(s, {domain_id: expected_version})[domain_id]
            event = self._logical(s, orm.BlastEvent, domain_id, card.blast_event_id)
            if event_date is not ...:
                event.event_date = event_date
            row = s.scalar(select(orm.BlastEventTechnicalCard).where(
                orm.BlastEventTechnicalCard.blast_event_id == event.id))
            if row is None:
                row = orm.BlastEventTechnicalCard(blast_event=event, logical_id=card.id,
                                                   is_archived=card.is_archived)
                s.add(row); s.flush()
            elif row.logical_id != card.id:
                raise ValueError("Technical Card logical ID does not match persisted container")
            geometry = s.scalar(select(orm.BlastEventGeometryRevision).where(
                orm.BlastEventGeometryRevision.blast_event_id == event.id,
                orm.BlastEventGeometryRevision.logical_id == revision.geometry_revision_id))
            if geometry is None: raise ValueError("Technical Card geometry is not persisted")
            s.query(orm.BlastEventTechnicalCardRevision).filter_by(
                technical_card_id=row.id, is_active=True).update({"is_active": False})
            s.flush()
            payload = next(x for x in card.to_dict()["revisions"] if x["id"] == revision.id)
            s.add(orm.BlastEventTechnicalCardRevision(
                technical_card=row, logical_id=revision.id,
                revision_number=revision.revision_number, created_at=revision.created_at,
                geometry_revision=geometry, event_type=revision.event_type,
                status=revision.status, author=revision.author,
                change_reason=revision.change_reason, payload_json=payload, is_active=True))
            return DomainWriteResult(new_version)

    @staticmethod
    def _sync_links(s, area_row, revision_id, links):
        revision = next((x for x in area_row.geometry_revisions
                         if x.logical_id == revision_id), None)
        if revision is None:
            raise ValueError("Assessment Area geometry revision is not persisted")
        if any(link.assessment_area_geometry_revision_id != revision_id for link in links):
            raise ValueError("Link belongs to another Assessment Area geometry revision")
        existing = {x.logical_id: x for x in revision.event_links}
        desired = {x.id: x for x in links}
        omitted = [row for key, row in existing.items() if key not in desired]
        for row in omitted: s.delete(row)
        if omitted: s.flush()
        for key, link in desired.items():
            row = existing.get(key)
            if row is None:
                row = orm.AssessmentEventLink(logical_id=link.id); s.add(row)
            event_geometry = s.scalar(select(orm.BlastEventGeometryRevision).join(
                orm.BlastEvent).where(orm.BlastEvent.domain_id == area_row.domain_id,
                orm.BlastEvent.logical_id == link.blast_event_id,
                orm.BlastEventGeometryRevision.logical_id == link.geometry_revision_id))
            if event_geometry is None: raise ValueError("Linked event geometry is not persisted")
            row.assessment_area_geometry_revision = revision
            row.blast_event_geometry_revision = event_geometry
            row.status, row.source, row.created_at = link.status, link.source, link.created_at
            row.frozen_intersection_geometry_json = (link.frozen_intersection_geometry.to_dict()
                                                       if link.frozen_intersection_geometry else None)

    def persist_assessment_area_geometry(self, domain_id, expected_version, area):
        revision = area.active_geometry_revision()
        with self._session_factory.begin() as s:
            new_version = guard_domain_versions(s, {domain_id: expected_version})[domain_id]
            row = s.scalar(select(orm.AssessmentArea).where(
                orm.AssessmentArea.domain_id == domain_id, orm.AssessmentArea.logical_id == area.id))
            if row is None:
                row = orm.AssessmentArea(domain_id=domain_id, logical_id=area.id, name=area.name,
                    assessment_date=area.assessment_date, is_archived=area.is_archived,
                    archived_at=area.archived_at, archive_reason=area.archive_reason)
                s.add(row); s.flush()
            duplicate = s.scalar(select(orm.AssessmentAreaGeometryRevision.id).where(
                orm.AssessmentAreaGeometryRevision.assessment_area_id == row.id,
                (orm.AssessmentAreaGeometryRevision.logical_id == revision.id) |
                (orm.AssessmentAreaGeometryRevision.revision_number == revision.revision_number)))
            if duplicate is not None:
                raise ValueError("Assessment Area geometry revision ID or number already exists")
            s.query(orm.AssessmentAreaGeometryRevision).filter_by(
                assessment_area_id=row.id, is_active=True).update({"is_active": False})
            s.flush()
            s.add(orm.AssessmentAreaGeometryRevision(assessment_area=row,
                logical_id=revision.id, revision_number=revision.revision_number,
                created_at=revision.created_at, boundary_json=revision.boundary.to_dict(),
                final_geometry_json=revision.final_geometry_frozen.to_dict(),
                min_elevation_m=revision.min_elevation, max_elevation_m=revision.max_elevation,
                change_reason=revision.change_reason, is_active=True))
            s.flush()
            links = [link for link in area.event_links
                     if link.assessment_area_geometry_revision_id == revision.id]
            self._sync_links(s, row, revision.id, links)
            return DomainWriteResult(new_version)

    def synchronize_area_links(self, domain_id, expected_version, area):
        with self._session_factory.begin() as s:
            new_version = guard_domain_versions(s, {domain_id: expected_version})[domain_id]
            row = self._logical(s, orm.AssessmentArea, domain_id, area.id)
            revision_id = area.active_geometry_revision_id
            links = [link for link in area.event_links
                     if link.assessment_area_geometry_revision_id == revision_id]
            self._sync_links(s, row, revision_id, links)
            return DomainWriteResult(new_version)

    @staticmethod
    def _evaluation_owner(s, domain_id, evaluation, *, create):
        row = s.scalar(select(orm.AssessmentAreaEvaluation).join(
            orm.AssessmentArea).where(
                orm.AssessmentArea.domain_id == domain_id,
                orm.AssessmentAreaEvaluation.logical_id == evaluation.id))
        if row is not None and row.assessment_area.logical_id != evaluation.assessment_area_id:
            raise ValueError("Evaluation belongs to another Assessment Area")
        if row is None and create:
            foreign = s.scalar(select(orm.AssessmentAreaEvaluation.id).where(
                orm.AssessmentAreaEvaluation.logical_id == evaluation.id))
            if foreign is not None:
                raise ValueError("Evaluation belongs to another Domain")
            area = s.scalar(select(orm.AssessmentArea).where(
                orm.AssessmentArea.domain_id == domain_id,
                orm.AssessmentArea.logical_id == evaluation.assessment_area_id))
            if area is None: raise ValueError("Evaluation Assessment Area is not persisted")
            row = orm.AssessmentAreaEvaluation(assessment_area=area, logical_id=evaluation.id,
                is_archived=evaluation.is_archived, archived_at=evaluation.archived_at)
            s.add(row); s.flush()
        return row

    def persist_evaluation_owner(self, domain_id, expected_version, evaluation):
        with self._session_factory.begin() as s:
            new_version = guard_domain_versions(s, {domain_id: expected_version})[domain_id]
            self._evaluation_owner(s, domain_id, evaluation, create=True)
            return DomainWriteResult(new_version)

    def persist_evaluation_revision(self, domain_id, expected_version, evaluation, revision):
        with self._session_factory.begin() as s:
            new_version = guard_domain_versions(s, {domain_id: expected_version})[domain_id]
            owner = self._evaluation_owner(s, domain_id, evaluation, create=True)
            geometry = s.scalar(select(orm.AssessmentAreaGeometryRevision).where(
                orm.AssessmentAreaGeometryRevision.assessment_area_id == owner.assessment_area_id,
                orm.AssessmentAreaGeometryRevision.logical_id == revision.assessment_area_geometry_revision_id))
            if geometry is None: raise ValueError("Evaluation geometry is not persisted")
            s.query(orm.AssessmentAreaEvaluationRevision).filter_by(
                evaluation_id=owner.id, is_active=True).update({"is_active": False})
            s.flush()
            s.add(orm.AssessmentAreaEvaluationRevision(evaluation=owner, logical_id=revision.id,
                revision_number=revision.revision_number, created_at=revision.created_at,
                geometry_revision=geometry, assessment_date=revision.assessment_date,
                inspector=revision.inspector, status=revision.status,
                matrix_template_id=revision.matrix_template_id,
                matrix_template_version=revision.matrix_template_version,
                design_achievement_index=revision.design_achievement_index,
                face_condition_index=revision.face_condition_index,
                result_quadrant=revision.result_quadrant,
                payload_json=revision.to_dict(), is_active=True))
            return DomainWriteResult(new_version)

    @staticmethod
    def _set_attachment(row, item, event=None, evaluation=None):
        row.owner_type=item.owner_type; row.blast_event=event
        row.assessment_area_evaluation=evaluation
        row.attachment_kind=item.attachment_kind; row.subtype=item.subtype
        row.custom_subtype=item.custom_subtype; row.title=item.title
        row.original_filename=item.original_filename; row.stored_filename=item.stored_filename
        row.relative_path=item.relative_path; row.file_date=item.file_date
        row.description=item.description; row.mime_type=item.mime_type
        row.file_size_bytes=item.file_size_bytes; row.created_at=item.created_at

    @staticmethod
    def _attachment_for_domain(s, domain_id, attachment_id):
        row = s.scalar(select(orm.AssessmentEntityAttachment).where(
            orm.AssessmentEntityAttachment.logical_id == attachment_id))
        if row is None:
            raise ValueError("Attachment is not persisted")
        owner_domain_id = (row.blast_event.domain_id if row.blast_event is not None
            else row.assessment_area_evaluation.assessment_area.domain_id)
        if owner_domain_id != domain_id:
            raise ValueError("Attachment belongs to another Domain")
        return row

    def add_attachment_metadata_batch(self, domain_id, expected_version, attachments, evaluation_owner=None):
        if not attachments:
            raise ValueError("Attachment batch is empty")
        with self._session_factory.begin() as s:
            new_version = guard_domain_versions(s, {domain_id: expected_version})[domain_id]
            event=evaluation=None
            owner_type, owner_id = attachments[0].owner_type, attachments[0].owner_id
            if any((item.owner_type, item.owner_id) != (owner_type, owner_id)
                   for item in attachments):
                raise ValueError("Attachment batch must have one owner")
            if owner_type == "blast_event":
                event=self._logical(s,orm.BlastEvent,domain_id,owner_id)
            else:
                if evaluation_owner is None: raise ValueError("Evaluation owner is required")
                if evaluation_owner.id != owner_id:
                    raise ValueError("Attachment owner does not match Evaluation")
                evaluation=self._evaluation_owner(s,domain_id,evaluation_owner,create=True)
            for attachment in attachments:
                row=orm.AssessmentEntityAttachment(logical_id=attachment.id); s.add(row)
                self._set_attachment(row,attachment,event,evaluation)
                s.flush()
            return DomainWriteResult(new_version)

    def update_attachment_metadata(self, domain_id, expected_version, attachment):
        with self._session_factory.begin() as s:
            new_version = guard_domain_versions(s, {domain_id: expected_version})[domain_id]
            row=self._attachment_for_domain(s,domain_id,attachment.id)
            # Metadata editing never reparents an attachment.
            for name in ("attachment_kind", "subtype", "custom_subtype", "title",
                         "original_filename", "stored_filename", "relative_path",
                         "file_date", "description", "mime_type", "file_size_bytes"):
                setattr(row, name, getattr(attachment, name))
            return DomainWriteResult(new_version)

    def delete_attachment_metadata(self, domain_id, expected_version, attachment_id):
        with self._session_factory.begin() as s:
            new_version = guard_domain_versions(s, {domain_id: expected_version})[domain_id]
            row=self._attachment_for_domain(s,domain_id,attachment_id)
            s.delete(row)
            return DomainWriteResult(new_version)

    @classmethod
    def insert_event_in_session(cls, s, domain_id, event):
        row=orm.BlastEvent(domain_id=domain_id,logical_id=event.id,name=event.name,
            event_type=event.event_type,event_date=event.event_date,elevation_m=event.elevation,
            blast_block_id=event.blast_block_id,is_archived=event.is_archived,
            archived_at=event.archived_at,archive_reason=event.archive_reason)
        s.add(row); s.flush()
        for revision in event.geometry_revisions:
            s.add(orm.BlastEventGeometryRevision(blast_event=row,logical_id=revision.id,
                revision_number=revision.revision_number,imported_at=revision.imported_at,
                source_file_name=revision.source_file_name,
                source_geometry_json=[x.to_dict() for x in revision.source_geometry],
                plan_geometry_json=revision.plan_geometry.to_dict(),elevation_m=revision.elevation,
                is_active=revision.id==event.active_geometry_revision_id))
        s.flush()
        return None
