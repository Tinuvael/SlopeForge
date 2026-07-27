from prototype_2d.models import BenchSectionDraft, DatamineLine, DataminePoint, LineSegmentSelection, PrototypeState
from prototype_2d.occupancy import interval_conflicts, occupied_intervals, position_conflict


def segment(identifier, dataset, sid, start, end, role="upper_boundary"):
    return LineSegmentSelection(identifier, sid, start, end, [DataminePoint(start, 0, 700, 1), DataminePoint(end, 0, 700, 2)], role, 700, dataset_id=dataset)


def state_with_used_segment():
    used = segment("S-001", "D-001", "261", 10, 20)
    return PrototypeState(segments=[used], drafts=[BenchSectionDraft("U-003", "S-001", "S-001")])


def test_occupied_interval_blocks_inner_start_and_reports_bench():
    occupied = occupied_intervals(state_with_used_segment(), "D-001", "261")
    conflict = position_conflict(occupied, 15)
    assert conflict and "U-003" in conflict.description()


def test_interval_overlap_blocks_all_positive_overlap_forms_but_allows_endpoint_touch():
    occupied = occupied_intervals(state_with_used_segment(), "D-001", "261")
    assert interval_conflicts(occupied, 12, 18)  # внутри занятого
    assert interval_conflicts(occupied, 5, 15)   # входит в занятое
    assert interval_conflicts(occupied, 5, 25)   # покрывает занятое
    assert interval_conflicts(occupied, 15, 25)  # пересекает занятое
    assert not interval_conflicts(occupied, 0, 10)
    assert not interval_conflicts(occupied, 20, 30)


def test_same_sid_in_another_dataset_is_free():
    assert occupied_intervals(state_with_used_segment(), "D-002", "261") == []


def test_pit_boundary_is_independent_from_segment_role_and_serializes():
    line = DatamineLine("PIT", [DataminePoint(0, 0, 700, 1), DataminePoint(1, 0, 700, 2)], semantic_role="pit_boundary")
    state = PrototypeState(lines=[line])
    restored = PrototypeState.from_dict(state.to_dict())
    assert restored.lines[0].semantic_role == "pit_boundary"
    assert segment("S-1", "D-001", "PIT", 0, 1, "upper_boundary").role == "upper_boundary"


def test_old_geometry_status_is_loaded_as_ready():
    state = PrototypeState.from_dict({"drafts": [{"id": "U-001", "upper_segment_id": "S-2", "lower_segment_id": "S-1", "status": "not_assessed"}]})
    assert state.drafts[0].status == "ready"


def test_editing_segment_can_be_excluded_from_occupied_intervals():
    state = state_with_used_segment()
    assert occupied_intervals(state, "D-001", "261", exclude_segment_id="S-001") == []


def test_adjacent_benches_may_share_full_upper_lower_boundary():
    from prototype_2d.bench_analysis import conflicting_bench_ids
    shared = segment("S-shared", "D-001", "SID-10", 0, 10, "upper_boundary")
    old_lower = segment("S-low", "D-001", "SID-20", 0, 10, "lower_boundary")
    state = PrototypeState(segments=[shared, old_lower], drafts=[BenchSectionDraft("U-001", "S-shared", "S-low")])
    new_lower = segment("new-low", "D-001", "SID-10", 0, 10, "lower_boundary")
    new_upper = segment("new-up", "D-001", "SID-30", 0, 10, "upper_boundary")
    assert conflicting_bench_ids(state, new_lower, new_upper) == []
