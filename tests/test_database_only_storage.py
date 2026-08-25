from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from application.services.attachments import EntityAttachmentService
from application.services.drillhole_datasets import BlastEventDrillholeDatasetService
from application.services.project_surfaces import ProjectSurfaceDatasetService
from application.state.assessment_domain_state import AssessmentDomainState
from domain.attachments.entities import EntityAttachment
from infrastructure.files.drillhole_geometry import BlastEventDrillholeFileStorage
from infrastructure.files.project_geometry import ProjectGeometryFileStorage
from infrastructure.files.storage_availability import FileStorageUnavailableError


class _NoopRepository:
    def list_for_site(self, _site_id):
        return ["metadata-row"]

    def get_current(self, *_args):
        return None

    def list_for_event(self, *_args):
        return ["metadata-row"]


def _must_not_import(_path):
    raise AssertionError("physical importer must not run in Database only mode")


def _attachment() -> EntityAttachment:
    return EntityAttachment(
        id="ATT-001",
        owner_type="blast_event",
        owner_id="BE-001",
        attachment_kind="document",
        subtype="survey",
        custom_subtype="",
        title="Survey",
        original_filename="survey.pdf",
        stored_filename="survey.pdf",
        relative_path="files/blast_events/BE-001/documents/survey.pdf",
        file_date=date(2026, 8, 25),
        description="Database metadata remains available",
        mime_type="application/pdf",
        file_size_bytes=123,
        created_at=datetime(2026, 8, 25, tzinfo=timezone.utc),
    )


def test_database_only_attachments_keep_metadata_without_touching_files():
    state = AssessmentDomainState()
    item = _attachment()
    state.attachments.append(item)
    updates = []
    service = EntityAttachmentService(
        state,
        storage_path=None,
        storage_enabled=False,
        on_update=lambda attachment: updates.append(attachment.title),
    )

    assert service.storage_available is False
    assert service.list_for_owner("blast_event", "BE-001", "document") == [item]
    assert service.counts("blast_event", "BE-001") == (0, 1)
    assert service.is_missing(item) is True

    service.update_metadata(
        item.id,
        title="Updated survey",
        file_date=item.file_date,
        subtype=item.subtype,
        custom_subtype="",
        description=item.description,
    )
    assert updates == ["Updated survey"]

    # Read/open UI actions are harmless no-ops in metadata-only mode; destructive
    # and import operations still fail explicitly before touching a filesystem.
    assert service.open_file(item) is False
    assert service.open_owner_folder("blast_event", "BE-001") is False
    assert service.open_attachment_folder("blast_event", "BE-001", "document") is False
    with pytest.raises(FileStorageUnavailableError):
        service.delete_attachment(item.id)
    with pytest.raises(FileStorageUnavailableError):
        service.owner_folder("blast_event", "BE-001")
    assert item in state.attachments


def test_database_only_attachment_import_is_blocked_before_copy(tmp_path):
    state = AssessmentDomainState()
    service = EntityAttachmentService(state, storage_path=None, storage_enabled=False)
    source = tmp_path / "photo.jpg"
    source.write_bytes(b"photo")

    with pytest.raises(FileStorageUnavailableError):
        service.add_files("blast_event", "BE-001", "photo", [source])
    assert state.attachments == []


def test_database_only_project_surface_import_is_blocked_before_parser(tmp_path):
    storage = ProjectGeometryFileStorage(None)
    service = ProjectSurfaceDatasetService(_NoopRepository(), storage, _must_not_import)

    assert storage.available is False
    assert service.storage_available is False
    assert service.list_for_site(1) == ["metadata-row"]
    with pytest.raises(FileStorageUnavailableError):
        service.import_dataset(1, "design", tmp_path / "design.dxf")


def test_database_only_drillhole_import_is_blocked_before_parser(tmp_path):
    storage = BlastEventDrillholeFileStorage(None)
    service = BlastEventDrillholeDatasetService(_NoopRepository(), storage, _must_not_import)

    assert storage.available is False
    assert service.storage_available is False
    with pytest.raises(FileStorageUnavailableError):
        service.import_dataset(1, "BE-001", "design", tmp_path / "holes.dxf")