"""SQLAlchemy implementation of narrow, transactional Assessment writes."""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from database import assessment_models as orm
from database.models import Domain


class SqlAlchemyAssessmentWrites:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @staticmethod
    def _workspace(session, domain_id: int, *, create=False):
        row = session.scalar(select(orm.AssessmentWorkspace).where(
            orm.AssessmentWorkspace.domain_id == domain_id))
        if row is None and create:
            if session.get(Domain, domain_id) is None:
                raise ValueError(f"Domain {domain_id} does not exist")
            row = orm.AssessmentWorkspace(domain_id=domain_id)
            session.add(row); session.flush()
        if row is None:
            raise ValueError("Assessment Workspace does not exist")
        return row

    @staticmethod
    def _logical(session, model, workspace_id, logical_id):
        row = session.scalar(select(model).where(model.workspace_id == workspace_id,
                                                  model.domain_id == logical_id))
        if row is None:
            raise ValueError(f"Assessment entity {logical_id!r} is not persisted")
        return row

    def persist_area_archive(self, domain_id, area):
        with self._session_factory.begin() as s:
            w = self._workspace(s, domain_id)
            row = self._logical(s, orm.AssessmentArea, w.id, area.id)
            row.is_archived, row.archived_at, row.archive_reason = (
                area.is_archived, area.archived_at, area.archive_reason)
            return w.id

    def persist_contour_archive(self, domain_id, event):
        if event.event_type != "contour":
            raise ValueError("Only contour BlastEvents can use contour archive")
        with self._session_factory.begin() as s:
            w = self._workspace(s, domain_id)
            row = self._logical(s, orm.BlastEvent, w.id, event.id)
            row.is_archived, row.archived_at, row.archive_reason = (
                event.is_archived, event.archived_at, event.archive_reason)
            return w.id

    def append_blast_geometry_revision(self, domain_id, event_id, revision):
        with self._session_factory.begin() as s:
            w = self._workspace(s, domain_id)
            event = self._logical(s, orm.BlastEvent, w.id, event_id)
            s.query(orm.BlastEventGeometryRevision).filter_by(
                blast_event_id=event.id, is_active=True).update({"is_active": False})
            s.flush()
            s.add(orm.BlastEventGeometryRevision(
                blast_event=event, domain_id=revision.id,
                revision_number=revision.revision_number, imported_at=revision.imported_at,
                source_file_name=revision.source_file_name,
                source_geometry_json=[x.to_dict() for x in revision.source_geometry],
                plan_geometry_json=revision.plan_geometry.to_dict(),
                elevation_m=revision.elevation, is_active=True))
            return w.id

    def persist_technical_card_revision(self, domain_id, card, revision):
        with self._session_factory.begin() as s:
            w = self._workspace(s, domain_id)
            event = self._logical(s, orm.BlastEvent, w.id, card.blast_event_id)
            row = s.scalar(select(orm.BlastEventTechnicalCard).where(
                orm.BlastEventTechnicalCard.blast_event_id == event.id))
            if row is None:
                row = orm.BlastEventTechnicalCard(blast_event=event, domain_id=card.id,
                                                   is_archived=card.is_archived)
                s.add(row); s.flush()
            geometry = s.scalar(select(orm.BlastEventGeometryRevision).where(
                orm.BlastEventGeometryRevision.blast_event_id == event.id,
                orm.BlastEventGeometryRevision.domain_id == revision.geometry_revision_id))
            if geometry is None: raise ValueError("Technical Card geometry is not persisted")
            s.query(orm.BlastEventTechnicalCardRevision).filter_by(
                technical_card_id=row.id, is_active=True).update({"is_active": False})
            s.flush()
            payload = next(x for x in card.to_dict()["revisions"] if x["id"] == revision.id)
            s.add(orm.BlastEventTechnicalCardRevision(
                technical_card=row, domain_id=revision.id,
                revision_number=revision.revision_number, created_at=revision.created_at,
                geometry_revision=geometry, event_type=revision.event_type,
                status=revision.status, author=revision.author,
                change_reason=revision.change_reason, payload_json=payload, is_active=True))
            return w.id

    @staticmethod
    def _sync_links(s, area_row, area):
        revisions = {x.domain_id: x for x in area_row.geometry_revisions}
        existing = {(x.assessment_area_geometry_revision.domain_id, x.domain_id): x
                    for revision in area_row.geometry_revisions for x in revision.event_links}
        desired = {(x.assessment_area_geometry_revision_id, x.id): x for x in area.event_links}
        omitted = [row for key, row in existing.items() if key not in desired]
        for row in omitted: s.delete(row)
        if omitted: s.flush()
        workspace_id = area_row.workspace_id
        for key, link in desired.items():
            row = existing.get(key)
            if row is None:
                row = orm.AssessmentEventLink(domain_id=link.id); s.add(row)
            event_geometry = s.scalar(select(orm.BlastEventGeometryRevision).join(
                orm.BlastEvent).where(orm.BlastEvent.workspace_id == workspace_id,
                orm.BlastEventGeometryRevision.domain_id == link.geometry_revision_id))
            if event_geometry is None: raise ValueError("Linked event geometry is not persisted")
            row.assessment_area_geometry_revision = revisions[link.assessment_area_geometry_revision_id]
            row.blast_event_geometry_revision = event_geometry
            row.status, row.source, row.created_at = link.status, link.source, link.created_at
            row.frozen_intersection_geometry_json = (link.frozen_intersection_geometry.to_dict()
                                                       if link.frozen_intersection_geometry else None)

    def persist_assessment_area_geometry(self, domain_id, area):
        revision = area.active_geometry_revision()
        with self._session_factory.begin() as s:
            w = self._workspace(s, domain_id, create=True)
            row = s.scalar(select(orm.AssessmentArea).where(
                orm.AssessmentArea.workspace_id == w.id, orm.AssessmentArea.domain_id == area.id))
            if row is None:
                row = orm.AssessmentArea(workspace=w, domain_id=area.id, name=area.name,
                    assessment_date=area.assessment_date, is_archived=area.is_archived,
                    archived_at=area.archived_at, archive_reason=area.archive_reason)
                s.add(row); s.flush()
            dataset = s.scalar(select(orm.ProjectLinesDataset).join(Domain,
                Domain.site_id == orm.ProjectLinesDataset.site_id).where(
                    Domain.id == domain_id,
                    orm.ProjectLinesDataset.domain_id == revision.source_dataset_id))
            if dataset is None: raise ValueError("Project Lines dataset is outside this Site")
            s.query(orm.AssessmentAreaGeometryRevision).filter_by(
                assessment_area_id=row.id, is_active=True).update({"is_active": False})
            s.flush()
            if not any(x.domain_id == revision.id for x in row.geometry_revisions):
                s.add(orm.AssessmentAreaGeometryRevision(assessment_area=row,
                    domain_id=revision.id, revision_number=revision.revision_number,
                    created_at=revision.created_at, source_dataset=dataset,
                    selection_polygon_json=revision.selection_polygon_frozen.to_dict(),
                    final_geometry_json=revision.final_geometry_frozen.to_dict(),
                    lower_elevation_m=revision.lower_elevation,
                    upper_elevation_m=revision.upper_elevation,
                    horizon_slices_json=[x.to_dict() for x in revision.horizon_slices],
                    change_reason=revision.change_reason, is_active=True))
                s.flush()
            self._sync_links(s, row, area)
            return w.id

    def synchronize_area_links(self, domain_id, area):
        with self._session_factory.begin() as s:
            w = self._workspace(s, domain_id)
            row = self._logical(s, orm.AssessmentArea, w.id, area.id)
            self._sync_links(s, row, area)
            return w.id

    @staticmethod
    def _evaluation_owner(s, workspace_id, evaluation, *, create):
        row = s.scalar(select(orm.AssessmentAreaEvaluation).where(
            orm.AssessmentAreaEvaluation.domain_id == evaluation.id))
        if row is None and create:
            area = s.scalar(select(orm.AssessmentArea).where(
                orm.AssessmentArea.workspace_id == workspace_id,
                orm.AssessmentArea.domain_id == evaluation.assessment_area_id))
            if area is None: raise ValueError("Evaluation Assessment Area is not persisted")
            row = orm.AssessmentAreaEvaluation(assessment_area=area, domain_id=evaluation.id,
                is_archived=evaluation.is_archived, archived_at=evaluation.archived_at)
            s.add(row); s.flush()
        return row

    def persist_evaluation_owner(self, domain_id, evaluation):
        with self._session_factory.begin() as s:
            w = self._workspace(s, domain_id)
            self._evaluation_owner(s, w.id, evaluation, create=True)
            return w.id

    def persist_evaluation_revision(self, domain_id, evaluation, revision):
        with self._session_factory.begin() as s:
            w = self._workspace(s, domain_id)
            owner = self._evaluation_owner(s, w.id, evaluation, create=True)
            geometry = s.scalar(select(orm.AssessmentAreaGeometryRevision).where(
                orm.AssessmentAreaGeometryRevision.assessment_area_id == owner.assessment_area_id,
                orm.AssessmentAreaGeometryRevision.domain_id == revision.assessment_area_geometry_revision_id))
            if geometry is None: raise ValueError("Evaluation geometry is not persisted")
            s.query(orm.AssessmentAreaEvaluationRevision).filter_by(
                evaluation_id=owner.id, is_active=True).update({"is_active": False})
            s.flush()
            s.add(orm.AssessmentAreaEvaluationRevision(evaluation=owner, domain_id=revision.id,
                revision_number=revision.revision_number, created_at=revision.created_at,
                geometry_revision=geometry, assessment_date=revision.assessment_date,
                inspector=revision.inspector, status=revision.status,
                matrix_template_id=revision.matrix_template_id,
                matrix_template_version=revision.matrix_template_version,
                design_achievement_index=revision.design_achievement_index,
                face_condition_index=revision.face_condition_index,
                result_quadrant=revision.result_quadrant,
                payload_json=revision.to_dict(), is_active=True))
            return w.id

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

    def add_attachment_metadata(self, domain_id, attachment, evaluation_owner=None):
        with self._session_factory.begin() as s:
            w=self._workspace(s,domain_id)
            event=evaluation=None
            if attachment.owner_type == "blast_event":
                event=self._logical(s,orm.BlastEvent,w.id,attachment.owner_id)
            else:
                if evaluation_owner is None: raise ValueError("Evaluation owner is required")
                evaluation=self._evaluation_owner(s,w.id,evaluation_owner,create=True)
            row=orm.AssessmentEntityAttachment(domain_id=attachment.id); s.add(row)
            self._set_attachment(row,attachment,event,evaluation)
            s.flush()
            return w.id

    def update_attachment_metadata(self, domain_id, attachment):
        with self._session_factory.begin() as s:
            w=self._workspace(s,domain_id)
            row=s.scalar(select(orm.AssessmentEntityAttachment).where(
                orm.AssessmentEntityAttachment.domain_id==attachment.id))
            if row is None: raise ValueError("Attachment is not persisted")
            self._set_attachment(row,attachment,row.blast_event,row.assessment_area_evaluation)
            return w.id

    def delete_attachment_metadata(self, domain_id, attachment_id):
        with self._session_factory.begin() as s:
            w=self._workspace(s,domain_id)
            row=s.scalar(select(orm.AssessmentEntityAttachment).where(
                orm.AssessmentEntityAttachment.domain_id==attachment_id))
            if row is None: raise ValueError("Attachment is not persisted")
            s.delete(row)
            return w.id

    @classmethod
    def insert_event_in_session(cls, s, domain_id, event):
        helper=object.__new__(cls)
        w=helper._workspace(s,domain_id,create=True)
        row=orm.BlastEvent(workspace=w,domain_id=event.id,name=event.name,
            event_type=event.event_type,event_date=event.event_date,elevation_m=event.elevation,
            blast_block_id=event.blast_block_id,is_archived=event.is_archived,
            archived_at=event.archived_at,archive_reason=event.archive_reason)
        s.add(row); s.flush()
        for revision in event.geometry_revisions:
            s.add(orm.BlastEventGeometryRevision(blast_event=row,domain_id=revision.id,
                revision_number=revision.revision_number,imported_at=revision.imported_at,
                source_file_name=revision.source_file_name,
                source_geometry_json=[x.to_dict() for x in revision.source_geometry],
                plan_geometry_json=revision.plan_geometry.to_dict(),elevation_m=revision.elevation,
                is_active=revision.id==event.active_geometry_revision_id))
        s.flush()
        return w.id
