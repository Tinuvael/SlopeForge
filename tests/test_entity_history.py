from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from repositories.entity_history_repository import (
    EntityHistoryEntry, EntityHistoryRepository, _execution_content, _technical_sections,
)


def _revision(number, payload, *, status="draft", author="Engineer"):
    return SimpleNamespace(
        id=number,
        logical_id=f"TC-R{number:03d}",
        revision_number=number,
        created_at=datetime(2026, 8, 18, 10, number, tzinfo=timezone.utc),
        payload_json=payload,
        event_type="production",
        status=status,
        author=author,
        geometry_revision=SimpleNamespace(revision_number=1),
    )


def _default_execution():
    return {
        "actual_drilling_groups": [],
        "actual_blast_date": "2026-08-18",
        "actual_total_hole_count": 0,
        "actual_total_drilling_length_m": 0.0,
        "actual_total_explosive_mass_kg": 0.0,
        "execution_notes": "",
        "deviations_text": "",
        "completion_status": "planned",
        "migration_warnings": [],
    }


def test_default_only_execution_is_not_a_history_action():
    payload = {"actual_execution": _default_execution()}
    assert not any(_execution_content(payload).values())
    entries = EntityHistoryRepository._technical_card_entries(
        [_revision(1, payload)], "production"
    )
    assert "Execution fact created" not in [entry.title for entry in entries]


def test_production_section_history_is_semantic_not_field_level():
    first = {
        "drilling_groups": [{"id": "DG-1", "hole_count": 10}],
        "production_parameters": {"design_bench_height_m": 10},
        "contour_parameters": None,
        "design_slope_orientation": {},
        "geomechanical_parameters": {},
        "actual_execution": _default_execution(),
    }
    second = {
        **first,
        "drilling_groups": [{"id": "DG-1", "hole_count": 12}],
        "geomechanical_parameters": {"ucs_mpa": 80, "gsi": 55},
    }
    third_execution = _default_execution()
    third_execution["actual_drilling_groups"] = [
        {"id": "AG-1", "copied_from_design": True, "hole_count": 12}
    ]
    third = {**second, "actual_execution": third_execution}

    entries = EntityHistoryRepository._technical_card_entries(
        [_revision(1, first), _revision(2, second), _revision(3, third, status="completed")],
        "production",
    )
    titles = [entry.title for entry in entries]
    assert titles.count("Blast design created") == 1
    assert "Blast design updated" in titles
    assert "Geomechanics created" in titles
    assert "Execution fact initialized from design" in titles
    assert "Technical Card completed" in titles
    assert not any("UCS" in title or "hole_count" in title for title in titles)
    assert all(entry.actor == "Engineer" for entry in entries)


def test_contour_history_never_emits_geomechanics():
    payload = {
        "drilling_groups": [{"id": "DG-C"}],
        "contour_parameters": {"controlled_blasting_method": "presplit"},
        "production_parameters": None,
        "design_slope_orientation": {},
        "geomechanical_parameters": {"ucs_mpa": 99},
        "actual_execution": _default_execution(),
    }
    assert "geomechanics" not in _technical_sections(payload, "contour")
    titles = [entry.title for entry in EntityHistoryRepository._technical_card_entries(
        [_revision(1, payload)], "contour"
    )]
    assert all("Geomechanics" not in title for title in titles)


def test_completed_assessment_details_use_stored_results_without_recalculation():
    revision = SimpleNamespace(
        revision_number=4,
        design_achievement_index=0.81234,
        face_condition_index=0.66789,
        result_quadrant="Q2",
    )
    from repositories.entity_history_repository import _assessment_result_details
    assert _assessment_result_details(revision) == "Evaluation R4 · DAI 0.812 · FCI 0.668 · Q2"


def test_history_sort_is_reverse_chronological_and_deterministic():
    stamp = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    older = EntityHistoryEntry(datetime(2026, 8, 18, 11, 0, tzinfo=timezone.utc), "A", "Old", sort_key="z")
    same_a = EntityHistoryEntry(stamp, "A", "A", sort_key="a")
    same_b = EntityHistoryEntry(stamp, "A", "B", sort_key="b")
    assert [entry.title for entry in EntityHistoryRepository._sorted([older, same_a, same_b])] == ["B", "A", "Old"]


def test_shared_history_widget_has_documents_style_four_column_contract():
    widgets = pytest.importorskip("PySide6.QtWidgets", exc_type=ImportError)
    from ui.pages.entity_history_widget import CATEGORY_ICONS, EntityHistoryWidget

    app = widgets.QApplication.instance() or widgets.QApplication([])
    widget = EntityHistoryWidget()
    widget.set_entries([
        EntityHistoryEntry(
            datetime(2026, 8, 18, 12, 30, tzinfo=timezone.utc),
            "eugene", "Blast design updated", "Technical Card R2", "blast_design",
        )
    ])
    assert widget.table.columnCount() == 4
    assert [widget.table.horizontalHeaderItem(i).text() for i in range(4)] == [
        "Date & time", "User", "Change", "Details"
    ]
    assert not widget.table.showGrid()
    assert widget.table.item(0, 1).text() == "eugene"
    assert widget.table.item(0, 2).text() == "Blast design updated"
    assert widget.table.item(0, 3).text() == "Technical Card R2"
    assert set(CATEGORY_ICONS) >= {
        "change", "archive", "attachment", "geometry", "blast_design",
        "geomechanics", "execution", "technical_card", "assessment", "link",
    }
    widget.close(); app.processEvents()


def test_all_three_entity_pages_use_the_shared_history_widget():
    for path in (
        "ui/pages/block_page.py",
        "ui/pages/contour_event_page.py",
        "ui/pages/assessment_area_page.py",
    ):
        text = Path(path).read_text(encoding="utf-8")
        assert "EntityHistoryWidget" in text
        assert "EntityHistoryRepository" in text


def test_history_audit_scope_records_compact_attachment_batches_and_ignores_auto_link_refresh():
    writes = Path("infrastructure/db/assessment_writes.py").read_text(encoding="utf-8")
    assert 'description = f"Added {len(attachments)} {noun}s"' in writes
    assert 'action="attach", field_name="attachment_batch"' in writes
    assert 'description=f\'Deleted {noun} "{title}"\'' in writes
    assert 'if before is None and link.source == "manual"' in writes
    assert "refresh_suggestions" in writes
    assert 'description="Suggestions refreshed"' not in writes
