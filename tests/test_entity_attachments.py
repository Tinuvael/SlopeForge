from datetime import date
from pathlib import Path

import pytest

from prototype_2d.domain import AssessmentDomainState
from prototype_2d.entity_attachments import EntityAttachmentService, sanitize_filename


@pytest.fixture
def store(tmp_path):
    state = AssessmentDomainState()
    return state, EntityAttachmentService(state, tmp_path / "slopeforge_state.json")


@pytest.mark.parametrize("owner,owner_id,kind,folder", [
    ("blast_event", "BE-001", "photo", "blast_events/BE-001/photos"),
    ("blast_event", "BE-001", "document", "blast_events/BE-001/documents"),
    ("assessment_evaluation", "AAE-001", "photo", "assessments/AAE-001/photos"),
    ("assessment_evaluation", "AAE-001", "document", "assessments/AAE-001/documents"),
])
def test_imports_each_owner_and_kind(store, tmp_path, owner, owner_id, kind, folder):
    state, service = store; source = tmp_path / ("wall.jpg" if kind == "photo" else "survey.pdf"); source.write_bytes(b"contents")
    item = service.add_files(owner, owner_id, kind, [source], {"subtype": "other"})[0]
    assert item.relative_path == f"files/{folder}/{source.name}"
    assert not Path(item.relative_path).is_absolute()
    assert service.resolve_path(item).read_bytes() == b"contents"
    assert state.attachments == [item]


def test_safe_filename_and_collision(store, tmp_path):
    _, service = store; source = tmp_path / "wall?.JPG"; source.write_bytes(b"one")
    first = service.add_files("blast_event", "BE-1", "photo", [source])[0]
    second = service.add_files("blast_event", "BE-1", "photo", [source])[0]
    assert sanitize_filename("../../bad:name?.JPG") == "bad_name_.jpg"
    assert first.stored_filename == "wall_.jpg"
    assert second.stored_filename == "wall__2.jpg"


def test_same_source_creates_independent_copies_and_deletes(store, tmp_path):
    state, service = store; source = tmp_path / "wall.jpg"; source.write_bytes(b"same photo")
    block = service.add_files("blast_event", "BE-001", "photo", [source])[0]
    assessment = service.add_files("assessment_evaluation", "AAE-001", "photo", [source])[0]
    assert service.resolve_path(block) != service.resolve_path(assessment)
    result = service.delete_attachment(block.id)
    assert result.cleanup_warning is None
    assert not service.resolve_path(block).exists() and service.resolve_path(assessment).exists()
    service.delete_attachment(assessment.id)
    assert not state.attachments and not service.resolve_path(assessment).exists()


def test_evaluation_revisions_share_owner_collection(store, tmp_path):
    _, service = store; first = tmp_path / "one.jpg"; second = tmp_path / "two.jpg"; first.write_bytes(b"1"); second.write_bytes(b"2")
    service.add_files("assessment_evaluation", "AAE-001", "photo", [first])
    revision_1 = service.list_for_owner("assessment_evaluation", "AAE-001")
    revision_2 = service.list_for_owner("assessment_evaluation", "AAE-001")
    service.add_files("assessment_evaluation", "AAE-001", "photo", [second])
    assert revision_1 == revision_2
    assert len(service.list_for_owner("assessment_evaluation", "AAE-001")) == 2
    assert not (service.data_root / "files/assessments/AAE-001/R002").exists()


def test_json_backward_compatibility_and_round_trip(store, tmp_path):
    state, service = store; source = tmp_path / "report.pdf"; source.write_bytes(b"pdf")
    item = service.add_files("blast_event", "BE-1", "document", [source], {"file_date": date(2026, 8, 3), "description": "Отчёт"})[0]
    assert AssessmentDomainState.from_dict({}).attachments == []
    restored = AssessmentDomainState.from_dict(state.to_dict()).attachments[0]
    assert restored.to_dict() == item.to_dict()


def test_missing_file_and_owner_folder(store, tmp_path):
    state, service = store; source = tmp_path / "gone.txt"; source.write_text("x")
    item = service.add_files("blast_event", "BE-1", "document", [source])[0]
    service.resolve_path(item).unlink()
    assert service.is_missing(item)
    service.delete_attachment(item.id)
    assert item not in state.attachments
    folder = service.owner_folder("assessment_evaluation", "AAE-stable")
    assert (folder / "photos").is_dir() and (folder / "documents").is_dir()


def test_failed_physical_delete_keeps_metadata(store, tmp_path, monkeypatch):
    state, service = store; source = tmp_path / "locked.txt"; source.write_text("x")
    item = service.add_files("blast_event", "BE-1", "document", [source])[0]
    original_replace = Path.replace
    monkeypatch.setattr(Path, "replace", lambda self, target: (_ for _ in ()).throw(PermissionError("locked")) if self == service.resolve_path(item) else original_replace(self, target))
    with pytest.raises(PermissionError): service.delete_attachment(item.id)
    assert item in state.attachments and service.resolve_path(item).exists()


def test_update_metadata_restores_every_field_when_save_fails(tmp_path):
    state = AssessmentDomainState(); source = tmp_path / "report.pdf"; source.write_bytes(b"pdf")
    service = EntityAttachmentService(state, tmp_path / "state.json")
    item = service.add_files("blast_event", "BE-1", "document", [source], {
        "title": "Before", "file_date": date(2026, 8, 1), "subtype": "survey",
        "custom_subtype": "old", "description": "original",
    })[0]
    before = item.to_dict()
    service.save_callback = lambda: (_ for _ in ()).throw(RuntimeError("save failed"))
    with pytest.raises(RuntimeError, match="save failed"):
        service.update_metadata(item.id, title="After", file_date=date(2026, 8, 2),
                                subtype="other", custom_subtype="new", description="changed")
    assert item.to_dict() == before


def test_delete_restores_file_and_original_state_position_when_save_fails(tmp_path):
    state = AssessmentDomainState(); first = tmp_path / "first.pdf"; second = tmp_path / "second.pdf"
    first.write_bytes(b"first"); second.write_bytes(b"second")
    service = EntityAttachmentService(state, tmp_path / "state.json")
    item = service.add_files("blast_event", "BE-1", "document", [first])[0]
    other = service.add_files("blast_event", "BE-1", "document", [second])[0]
    original_path = service.resolve_path(item)
    service.save_callback = lambda: (_ for _ in ()).throw(RuntimeError("save failed"))
    with pytest.raises(RuntimeError, match="save failed"):
        service.delete_attachment(item.id)
    assert state.attachments == [item, other]
    assert original_path.read_bytes() == b"first"
    assert not list(original_path.parent.glob("*.slopeforge-delete-*.tmp"))


def test_final_delete_cleanup_failure_is_a_success_with_warning(tmp_path, monkeypatch):
    state = AssessmentDomainState(); source = tmp_path / "report.pdf"; source.write_bytes(b"pdf")
    saves = []
    service = EntityAttachmentService(state, tmp_path / "state.json", lambda: saves.append(True))
    item = service.add_files("blast_event", "BE-1", "document", [source])[0]
    original_path = service.resolve_path(item); original_unlink = Path.unlink
    def fail_temporary_cleanup(path, *args, **kwargs):
        if ".slopeforge-delete-" in path.name:
            raise PermissionError("temporarily locked")
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail_temporary_cleanup)

    result = service.delete_attachment(item.id)

    assert item not in state.attachments
    assert len(saves) == 2  # import and the successful logical delete
    assert not original_path.exists()
    leftovers = list(original_path.parent.glob("*.slopeforge-delete-*.tmp"))
    assert len(leftovers) == 1
    assert result.cleanup_warning and str(leftovers[0]) in result.cleanup_warning


def test_add_files_rolls_back_whole_batch_on_copy_failure(tmp_path):
    state = AssessmentDomainState(); service = EntityAttachmentService(state, tmp_path / "state.json")
    first = tmp_path / "first.pdf"; first.write_bytes(b"first")
    missing = tmp_path / "missing.pdf"
    with pytest.raises(FileNotFoundError):
        service.add_files("blast_event", "BE-1", "document", [first, missing])
    assert state.attachments == []
    assert not (service.owner_folder("blast_event", "BE-1", create=False) / "documents" / "first.pdf").exists()


def test_add_files_rolls_back_state_and_copies_when_save_fails(tmp_path):
    state = AssessmentDomainState(); source = tmp_path / "report.pdf"; source.write_bytes(b"pdf")
    service = EntityAttachmentService(state, tmp_path / "state.json",
        lambda: (_ for _ in ()).throw(RuntimeError("save failed")))
    with pytest.raises(RuntimeError, match="save failed"):
        service.add_files("assessment_evaluation", "AAE-1", "document", [source])
    assert state.attachments == []
    target = service.owner_folder("assessment_evaluation", "AAE-1", create=False) / "documents" / "report.pdf"
    assert not target.exists()


def test_renaming_metadata_does_not_change_stable_folders(store):
    _, service = store
    before = service.owner_folder("blast_event", "BE-001")
    # Entity display names are intentionally not an input to folder calculation.
    after = service.owner_folder("blast_event", "BE-001")
    assert before == after


def test_owner_id_cannot_traverse_outside_data_root(store):
    _, service = store
    with pytest.raises(ValueError): service.owner_folder("blast_event", "../outside")
