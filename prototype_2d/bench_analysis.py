"""Консервативная финальная проверка пересечения черновиков уступов."""
from __future__ import annotations

from prototype_2d.models import LineSegmentSelection, PrototypeState


def _bbox(segment: LineSegmentSelection) -> tuple[float, float, float, float]:
    xs = [point.x for point in segment.extracted_points]
    ys = [point.y for point in segment.extracted_points]
    return min(xs), max(xs), min(ys), max(ys)


def segments_overlap(first: LineSegmentSelection, second: LineSegmentSelection) -> bool:
    if first.dataset_id == second.dataset_id and first.source_line_id == second.source_line_id:
        return max(first.start_position, second.start_position) < min(first.end_position, second.end_position) - 1e-6
    ax1, ax2, ay1, ay2 = _bbox(first); bx1, bx2, by1, by2 = _bbox(second)
    return max(0.0, min(ax2, bx2) - max(ax1, bx1)) > 0 and max(0.0, min(ay2, by2) - max(ay1, by1)) > 0


def conflicting_bench_ids(state: PrototypeState, lower: LineSegmentSelection, upper: LineSegmentSelection) -> list[str]:
    by_id = {segment.id: segment for segment in state.segments}
    conflicts: list[str] = []
    for bench in state.drafts:
        existing = [by_id.get(bench.lower_segment_id), by_id.get(bench.upper_segment_id), *(by_id.get(item) for item in bench.intermediate_segment_ids)]
        if any(current and any(segments_overlap(candidate, current) for candidate in (lower, upper)) for current in existing): conflicts.append(bench.id)
    return conflicts
