from prototype_2d.bench_analysis import conflicting_bench_ids, suggest_intermediate_segments
from prototype_2d.models import BenchSectionDraft, DatamineLine, DataminePoint, LineSegmentSelection, PrototypeState


def point(x, y, z):
    return DataminePoint(x, y, z, 1)


def segment(identifier, line_id, start, end, elevation):
    return LineSegmentSelection(identifier, line_id, start, end, [point(start, 0, elevation), point(end, 0, elevation)], "lower_boundary", elevation)


def test_suggests_horizontal_lines_strictly_between_bench_elevations():
    state = PrototypeState(lines=[
        DatamineLine("H610", [point(0, 0, 610), point(10, 0, 610)]),
        DatamineLine("H620", [point(0, 1, 620), point(10, 1, 620)]),
        DatamineLine("H630", [point(0, 2, 630), point(10, 2, 630)]),
    ])
    candidates = suggest_intermediate_segments(state, "U-001", segment("S-1", "LOW", 0, 10, 610), segment("S-2", "UP", 0, 10, 630))
    assert [(item.segment.source_line_id, item.status) for item in candidates] == [("H620", "suggested")]


def test_conflict_detects_reuse_of_same_source_line_area():
    existing = segment("S-1", "SID-10", 0, 10, 600)
    other = segment("S-2", "SID-20", 0, 10, 620)
    state = PrototypeState(segments=[existing, other], drafts=[BenchSectionDraft("U-003", "S-2", "S-1")])
    assert conflicting_bench_ids(state, segment("new-low", "SID-10", 5, 12, 600), segment("new-up", "SID-30", 0, 10, 640)) == ["U-003"]


def test_segments_keep_dataset_and_candidate_status_in_json_state():
    from prototype_2d.models import CandidateIntermediateSegment, PrototypeDataset

    selected = segment("S-1", "SID-1", 0, 5, 600)
    selected.dataset_id = "D-001"
    state = PrototypeState(
        segments=[selected],
        datasets=[PrototypeDataset("D-001", "first.csv", "first")],
        active_dataset_id="D-001",
        candidate_segments=[CandidateIntermediateSegment("C-001", "U-001", selected, "edited")],
    )
    restored = PrototypeState.from_dict(state.to_dict())
    assert restored.segments[0].dataset_id == "D-001"
    assert restored.candidate_segments[0].status == "edited"
