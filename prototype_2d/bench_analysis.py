"""Лёгкие проверки и предложения для черновика уступа без GIS-зависимостей."""
from __future__ import annotations

from prototype_2d.geometry import extract_segment, line_length
from prototype_2d.models import CandidateIntermediateSegment, DatamineLine, LineSegmentSelection, PrototypeState


def _bbox(segment: LineSegmentSelection) -> tuple[float, float, float, float]:
    xs = [point.x for point in segment.extracted_points]
    ys = [point.y for point in segment.extracted_points]
    return min(xs), max(xs), min(ys), max(ys)


def segments_overlap(first: LineSegmentSelection, second: LineSegmentSelection) -> bool:
    """Консервативная проверка: общий участок той же линии или заметно общая область."""
    if first.source_line_id == second.source_line_id:
        return max(first.start_position, second.start_position) < min(first.end_position, second.end_position)
    ax1, ax2, ay1, ay2 = _bbox(first)
    bx1, bx2, by1, by2 = _bbox(second)
    overlap_x = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    overlap_y = max(0.0, min(ay2, by2) - max(ay1, by1))
    return overlap_x > 0 and overlap_y > 0


def conflicting_bench_ids(state: PrototypeState, lower: LineSegmentSelection, upper: LineSegmentSelection) -> list[str]:
    by_id = {segment.id: segment for segment in state.segments}
    conflicts: list[str] = []
    for bench in state.drafts:
        existing = [by_id.get(bench.lower_segment_id), by_id.get(bench.upper_segment_id)]
        if any(current and any(segments_overlap(candidate, current) for candidate in (lower, upper)) for current in existing):
            conflicts.append(bench.id)
    return conflicts


def suggest_intermediate_segments(state: PrototypeState, bench_id: str, lower: LineSegmentSelection, upper: LineSegmentSelection) -> list[CandidateIntermediateSegment]:
    """Предлагает целые горизонтальные линии между границами; пользователь принимает их вручную."""
    elevations = [value for value in (lower.elevation, upper.elevation) if value is not None]
    if len(elevations) != 2:
        return []
    low, high = sorted(elevations)
    candidates: list[CandidateIntermediateSegment] = []
    for line in state.lines:
        if not line.is_horizontal or line.elevation is None or not low < line.elevation < high:
            continue
        if len(line.points) < 2:
            continue
        start, end, points = extract_segment(line, 0.0, line_length(line))
        segment = LineSegmentSelection(
            id=f"{bench_id}-suggested-{len(candidates) + 1:03d}",
            source_line_id=line.source_id,
            start_position=start,
            end_position=end,
            extracted_points=points,
            role="intermediate_assessment",
            elevation=line.elevation,
            dataset_id=state.active_dataset_id,
        )
        candidates.append(CandidateIntermediateSegment(state.next_candidate_id(), bench_id, segment))
    return candidates
