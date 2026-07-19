from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

from prototype_2d.geometry import extract_segment, line_length
from prototype_2d.models import BenchSectionDraft, DatamineLine, LineSegmentSelection, PrototypeState


class BenchWorkflowState(Enum):
    IDLE = auto()
    SELECT_LOWER_LINE = auto()
    SELECT_LOWER_START = auto()
    SELECT_LOWER_END = auto()
    CONFIRM_LOWER = auto()
    SELECT_UPPER_LINE = auto()
    SELECT_UPPER_START = auto()
    SELECT_UPPER_END = auto()
    CONFIRM_UPPER = auto()
    CONFIRM_BENCH = auto()
    BENCH_CREATED = auto()
    ADD_INTERMEDIATE_SELECT_LINE = auto()
    ADD_INTERMEDIATE_START = auto()
    ADD_INTERMEDIATE_END = auto()
    ADD_INTERMEDIATE_CONFIRM = auto()


@dataclass
class SegmentDraft:
    role: str
    line_id: str | None = None
    start_position: float | None = None
    end_position: float | None = None
    segment: LineSegmentSelection | None = None

    def reset_points(self) -> None:
        self.start_position = None
        self.end_position = None
        self.segment = None


@dataclass
class BenchCreationController:
    state: BenchWorkflowState = BenchWorkflowState.IDLE
    active_line_id: str | None = None
    selected_line_id: str | None = None
    lower: SegmentDraft = field(default_factory=lambda: SegmentDraft("lower_boundary"))
    upper: SegmentDraft = field(default_factory=lambda: SegmentDraft("upper_boundary"))
    intermediate: SegmentDraft = field(default_factory=lambda: SegmentDraft("intermediate_assessment"))
    selected_bench_id: str | None = None
    created_bench_id: str | None = None

    def start_bench(self) -> None:
        self.reset()
        self.state = BenchWorkflowState.SELECT_LOWER_LINE

    def start_intermediate(self, bench_id: str | None) -> None:
        if not bench_id:
            raise ValueError("Выберите уступ перед добавлением промежуточного сегмента")
        self.intermediate = SegmentDraft("intermediate_assessment")
        self.selected_bench_id = bench_id
        self.active_line_id = None
        self.selected_line_id = None
        self.state = BenchWorkflowState.ADD_INTERMEDIATE_SELECT_LINE

    def reset(self) -> None:
        self.state = BenchWorkflowState.IDLE
        self.active_line_id = None
        self.selected_line_id = None
        self.lower = SegmentDraft("lower_boundary")
        self.upper = SegmentDraft("upper_boundary")
        self.intermediate = SegmentDraft("intermediate_assessment")
        self.created_bench_id = None

    def has_work_in_progress(self) -> bool:
        return any((self.lower.segment, self.upper.segment, self.lower.line_id, self.upper.line_id, self.intermediate.line_id))

    def current_draft(self) -> SegmentDraft | None:
        if self.state in {BenchWorkflowState.SELECT_LOWER_LINE, BenchWorkflowState.SELECT_LOWER_START, BenchWorkflowState.SELECT_LOWER_END, BenchWorkflowState.CONFIRM_LOWER}:
            return self.lower
        if self.state in {BenchWorkflowState.SELECT_UPPER_LINE, BenchWorkflowState.SELECT_UPPER_START, BenchWorkflowState.SELECT_UPPER_END, BenchWorkflowState.CONFIRM_UPPER}:
            return self.upper
        if self.state in {BenchWorkflowState.ADD_INTERMEDIATE_SELECT_LINE, BenchWorkflowState.ADD_INTERMEDIATE_START, BenchWorkflowState.ADD_INTERMEDIATE_END, BenchWorkflowState.ADD_INTERMEDIATE_CONFIRM}:
            return self.intermediate
        return None

    def choose_line(self, line_id: str) -> None:
        if self.state not in {BenchWorkflowState.SELECT_LOWER_LINE, BenchWorkflowState.SELECT_UPPER_LINE, BenchWorkflowState.ADD_INTERMEDIATE_SELECT_LINE}:
            if self.active_line_id and line_id != self.active_line_id:
                raise ValueError("Сейчас активна другая линия")
            return
        self.selected_line_id = line_id

    def use_selected_line(self) -> None:
        draft = self.current_draft()
        if not draft or not self.selected_line_id:
            raise ValueError("Сначала выберите линию")
        draft.line_id = self.selected_line_id
        draft.reset_points()
        self.active_line_id = self.selected_line_id
        if self.state == BenchWorkflowState.SELECT_LOWER_LINE:
            self.state = BenchWorkflowState.SELECT_LOWER_START
        elif self.state == BenchWorkflowState.SELECT_UPPER_LINE:
            self.state = BenchWorkflowState.SELECT_UPPER_START
        elif self.state == BenchWorkflowState.ADD_INTERMEDIATE_SELECT_LINE:
            self.state = BenchWorkflowState.ADD_INTERMEDIATE_START

    def add_marker(self, line_id: str, position: float) -> None:
        draft = self.current_draft()
        if not draft or not self.active_line_id:
            raise ValueError("Нет активной линии")
        if line_id != self.active_line_id:
            raise ValueError("Маркер можно поставить только на активной линии")
        if draft.start_position is None:
            draft.start_position = position
            if self.state == BenchWorkflowState.SELECT_LOWER_START:
                self.state = BenchWorkflowState.SELECT_LOWER_END
            elif self.state == BenchWorkflowState.SELECT_UPPER_START:
                self.state = BenchWorkflowState.SELECT_UPPER_END
            elif self.state == BenchWorkflowState.ADD_INTERMEDIATE_START:
                self.state = BenchWorkflowState.ADD_INTERMEDIATE_END
            return
        draft.end_position = position
        if self.state == BenchWorkflowState.SELECT_LOWER_END:
            self.state = BenchWorkflowState.CONFIRM_LOWER
        elif self.state == BenchWorkflowState.SELECT_UPPER_END:
            self.state = BenchWorkflowState.CONFIRM_UPPER
        elif self.state == BenchWorkflowState.ADD_INTERMEDIATE_END:
            self.state = BenchWorkflowState.ADD_INTERMEDIATE_CONFIRM

    def update_marker(self, marker: str, line_id: str, position: float) -> None:
        if line_id != self.active_line_id:
            raise ValueError("Маркер можно перемещать только вдоль активной линии")
        draft = self.current_draft()
        if not draft:
            return
        if marker == "start":
            draft.start_position = position
        elif marker == "end":
            draft.end_position = position

    def build_current_segment(self, state: PrototypeState, line: DatamineLine) -> LineSegmentSelection:
        draft = self.current_draft()
        if not draft or draft.start_position is None or draft.end_position is None:
            raise ValueError("Нужно указать начало и конец")
        start, end, points = extract_segment(line, draft.start_position, draft.end_position)
        confirmed = sum(1 for item in (self.lower.segment, self.upper.segment, self.intermediate.segment) if item is not None)
        segment_id = f"S-{len(state.segments) + confirmed + 1:03d}"
        return LineSegmentSelection(segment_id, line.source_id, start, end, points, draft.role, line.elevation, dataset_id=state.active_dataset_id)

    def confirm_current_segment(self, state: PrototypeState, line: DatamineLine) -> LineSegmentSelection:
        draft = self.current_draft()
        if not draft:
            raise ValueError("Нет сегмента для подтверждения")
        draft.segment = self.build_current_segment(state, line)
        if self.state == BenchWorkflowState.CONFIRM_LOWER:
            self.active_line_id = None; self.selected_line_id = None; self.state = BenchWorkflowState.SELECT_UPPER_LINE
        elif self.state == BenchWorkflowState.CONFIRM_UPPER:
            self.active_line_id = None; self.selected_line_id = None; self.state = BenchWorkflowState.CONFIRM_BENCH
        elif self.state == BenchWorkflowState.ADD_INTERMEDIATE_CONFIRM:
            self.state = BenchWorkflowState.BENCH_CREATED
        return draft.segment

    def create_bench(self, state: PrototypeState) -> BenchSectionDraft:
        if not self.lower.segment or not self.upper.segment:
            raise ValueError("Нужны нижний и верхний сегменты")
        state.segments.extend([self.lower.segment, self.upper.segment])
        draft_id = state.next_draft_id()
        bench = BenchSectionDraft(draft_id, self.upper.segment.id, self.lower.segment.id, [self.upper.segment.id], draft_id)
        state.drafts.append(bench)
        self.created_bench_id = bench.id
        self.selected_bench_id = bench.id
        self.state = BenchWorkflowState.BENCH_CREATED
        return bench

    def add_intermediate_to_bench(self, state: PrototypeState) -> LineSegmentSelection:
        if not self.selected_bench_id:
            raise ValueError("Выберите уступ")
        if not self.intermediate.segment:
            raise ValueError("Подтвердите промежуточный сегмент")
        bench = next((d for d in state.drafts if d.id == self.selected_bench_id), None)
        if not bench:
            raise ValueError("Уступ не найден")
        state.segments.append(self.intermediate.segment)
        bench.add_intermediate(self.intermediate.segment.id)
        segment = self.intermediate.segment
        self.intermediate = SegmentDraft("intermediate_assessment")
        self.state = BenchWorkflowState.BENCH_CREATED
        self.active_line_id = None
        self.selected_line_id = None
        return segment

    def back(self) -> None:
        order = [
            BenchWorkflowState.IDLE,
            BenchWorkflowState.SELECT_LOWER_LINE,
            BenchWorkflowState.SELECT_LOWER_START,
            BenchWorkflowState.SELECT_LOWER_END,
            BenchWorkflowState.CONFIRM_LOWER,
            BenchWorkflowState.SELECT_UPPER_LINE,
            BenchWorkflowState.SELECT_UPPER_START,
            BenchWorkflowState.SELECT_UPPER_END,
            BenchWorkflowState.CONFIRM_UPPER,
            BenchWorkflowState.CONFIRM_BENCH,
            BenchWorkflowState.BENCH_CREATED,
        ]
        if self.state in order and order.index(self.state) > 1:
            self.state = order[order.index(self.state) - 1]
            if self.state in {BenchWorkflowState.SELECT_LOWER_LINE, BenchWorkflowState.SELECT_UPPER_LINE}:
                self.active_line_id = None

    def escape(self) -> None:
        draft = self.current_draft()
        if draft and draft.end_position is not None:
            draft.reset_points()
            if draft is self.lower: self.state = BenchWorkflowState.SELECT_LOWER_START
            elif draft is self.upper: self.state = BenchWorkflowState.SELECT_UPPER_START
            else: self.state = BenchWorkflowState.ADD_INTERMEDIATE_START
        elif draft and draft.start_position is not None:
            draft.start_position = None
            if draft is self.lower: self.state = BenchWorkflowState.SELECT_LOWER_START
            elif draft is self.upper: self.state = BenchWorkflowState.SELECT_UPPER_START
            else: self.state = BenchWorkflowState.ADD_INTERMEDIATE_START
        elif self.state in {BenchWorkflowState.SELECT_LOWER_LINE, BenchWorkflowState.SELECT_UPPER_LINE, BenchWorkflowState.ADD_INTERMEDIATE_SELECT_LINE}:
            self.selected_line_id = None


def segment_length(segment: LineSegmentSelection) -> float:
    temp = DatamineLine("segment", segment.extracted_points)
    return line_length(temp)
