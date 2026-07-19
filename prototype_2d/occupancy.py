"""Проверка уже занятой длины исходных линий внутри одного Dataset."""
from __future__ import annotations
from dataclasses import dataclass

from .models import LineSegmentSelection, PrototypeState

ENDPOINT_TOLERANCE = 1e-6

@dataclass(frozen=True)
class OccupiedInterval:
    dataset_id: str | None
    source_line_id: str
    start: float
    end: float
    bench_id: str
    role: str

    def contains(self, position: float) -> bool:
        return self.start + ENDPOINT_TOLERANCE < position < self.end - ENDPOINT_TOLERANCE

    def description(self) -> str:
        labels = {"upper_boundary": "верхняя граница", "lower_boundary": "нижняя граница", "intermediate_assessment": "промежуточный сегмент"}
        return f"Участок используется в {self.bench_id} как {labels.get(self.role, self.role)}"


def occupied_intervals(state: PrototypeState, dataset_id: str | None, source_line_id: str) -> list[OccupiedInterval]:
    segments = {segment.id: segment for segment in state.segments}
    result: list[OccupiedInterval] = []
    for bench in state.drafts:
        for segment_id in [bench.upper_segment_id, bench.lower_segment_id, *bench.intermediate_segment_ids]:
            segment = segments.get(segment_id)
            if segment and segment.dataset_id == dataset_id and segment.source_line_id == source_line_id:
                result.append(OccupiedInterval(dataset_id, source_line_id, min(segment.start_position, segment.end_position), max(segment.start_position, segment.end_position), bench.id, segment.role))
    return result


def interval_conflicts(intervals: list[OccupiedInterval], start: float, end: float) -> list[OccupiedInterval]:
    left, right = sorted((start, end))
    return [interval for interval in intervals if max(left, interval.start) < min(right, interval.end) - ENDPOINT_TOLERANCE]


def position_conflict(intervals: list[OccupiedInterval], position: float) -> OccupiedInterval | None:
    return next((interval for interval in intervals if interval.contains(position)), None)
