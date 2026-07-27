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


def _shared_adjacent_boundary(candidate: LineSegmentSelection, existing: LineSegmentSelection) -> bool:
    """Общая линия соседних уступов допустима только в паре верх/низ."""
    return (
        candidate.dataset_id == existing.dataset_id
        and candidate.source_line_id == existing.source_line_id
        and abs(candidate.start_position - existing.start_position) <= 1e-6
        and abs(candidate.end_position - existing.end_position) <= 1e-6
        and {candidate.role, existing.role} == {"upper_boundary", "lower_boundary"}
    )


def conflicting_bench_ids(state: PrototypeState, lower: LineSegmentSelection, upper: LineSegmentSelection) -> list[str]:
    """Не считает общей границей разрешённое касание соседних уступов."""
    by_id = {segment.id: segment for segment in state.segments}
    conflicts: list[str] = []
    for bench in state.drafts:
        existing = [by_id.get(bench.lower_segment_id), by_id.get(bench.upper_segment_id), *(by_id.get(item) for item in bench.intermediate_segment_ids)]
        for current in existing:
            if not current:
                continue
            for candidate in (lower, upper):
                if _shared_adjacent_boundary(candidate, current):
                    continue
                if segments_overlap(candidate, current):
                    conflicts.append(bench.id)
                    break
            if bench.id in conflicts:
                break
    return conflicts
