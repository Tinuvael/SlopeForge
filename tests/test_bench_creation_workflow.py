import pytest

from prototype_2d.models import DatamineLine, DataminePoint, PrototypeState
from ui.prototype_2d.bench_creation_controller import BenchCreationController, BenchWorkflowState


def line(line_id, z=700):
    return DatamineLine(line_id, [DataminePoint(0, 0, z, 1), DataminePoint(10, 0, z, 2)])


def test_full_bench_workflow_creates_draft():
    state = PrototypeState(lines=[line("LOW", 700), line("UP", 730)])
    c = BenchCreationController()
    c.start_bench()
    assert c.state == BenchWorkflowState.SELECT_LOWER_LINE
    c.choose_line("LOW"); c.use_selected_line()
    assert c.active_line_id == "LOW"
    assert c.state == BenchWorkflowState.SELECT_LOWER_START
    c.add_marker("LOW", 1); assert c.state == BenchWorkflowState.SELECT_LOWER_END
    c.add_marker("LOW", 9); assert c.state == BenchWorkflowState.CONFIRM_LOWER
    c.confirm_current_segment(state, state.lines[0]); assert c.state == BenchWorkflowState.SELECT_UPPER_LINE
    c.choose_line("UP"); c.use_selected_line(); c.add_marker("UP", 2); c.add_marker("UP", 8)
    assert c.state == BenchWorkflowState.CONFIRM_UPPER
    c.confirm_current_segment(state, state.lines[1]); assert c.state == BenchWorkflowState.CONFIRM_BENCH
    bench = c.create_bench(state)
    assert bench.id == "U-001"
    assert len(state.segments) == 2
    assert bench.lower_segment_id == "S-001"
    assert bench.upper_segment_id == "S-002"
    assert c.state == BenchWorkflowState.BENCH_CREATED


def test_active_line_blocks_other_line_markers():
    c = BenchCreationController(); c.start_bench(); c.choose_line("LOW"); c.use_selected_line()
    with pytest.raises(ValueError):
        c.add_marker("UP", 1)
    assert c.active_line_id == "LOW"


def test_escape_after_first_marker_removes_marker_only():
    c = BenchCreationController(); c.start_bench(); c.choose_line("LOW"); c.use_selected_line(); c.add_marker("LOW", 1)
    assert c.lower.start_position == 1
    c.escape()
    assert c.state == BenchWorkflowState.SELECT_LOWER_START
    assert c.lower.start_position is None
    assert c.active_line_id == "LOW"


def test_escape_after_two_markers_resets_segment():
    c = BenchCreationController(); c.start_bench(); c.choose_line("LOW"); c.use_selected_line(); c.add_marker("LOW", 1); c.add_marker("LOW", 9)
    assert c.state == BenchWorkflowState.CONFIRM_LOWER
    c.escape()
    assert c.state == BenchWorkflowState.SELECT_LOWER_START
    assert c.lower.start_position is None and c.lower.end_position is None


def test_back_keeps_confirmed_lower_segment():
    state = PrototypeState(lines=[line("LOW"), line("UP", 730)])
    c = BenchCreationController(); c.start_bench(); c.choose_line("LOW"); c.use_selected_line(); c.add_marker("LOW", 1); c.add_marker("LOW", 9); c.confirm_current_segment(state, state.lines[0])
    assert c.lower.segment is not None
    c.back()
    assert c.state == BenchWorkflowState.CONFIRM_LOWER
    assert c.lower.segment is not None


def test_cancel_resets_any_stage():
    c = BenchCreationController(); c.start_bench(); c.choose_line("LOW"); c.use_selected_line(); c.add_marker("LOW", 1)
    assert c.has_work_in_progress()
    c.reset()
    assert c.state == BenchWorkflowState.IDLE
    assert c.active_line_id is None


def test_add_intermediate_requires_selected_bench():
    c = BenchCreationController()
    with pytest.raises(ValueError):
        c.start_intermediate(None)


def test_add_intermediate_to_selected_bench():
    state = PrototypeState(lines=[line("LOW"), line("UP", 730), line("MID", 715)])
    c = BenchCreationController(); c.start_bench(); c.choose_line("LOW"); c.use_selected_line(); c.add_marker("LOW", 0); c.add_marker("LOW", 5); c.confirm_current_segment(state, state.lines[0]); c.choose_line("UP"); c.use_selected_line(); c.add_marker("UP", 0); c.add_marker("UP", 5); c.confirm_current_segment(state, state.lines[1]); c.create_bench(state)
    c.start_intermediate("U-001"); c.choose_line("MID"); c.use_selected_line(); c.add_marker("MID", 1); c.add_marker("MID", 4); c.confirm_current_segment(state, state.lines[2]); segment = c.add_intermediate_to_bench(state)
    assert segment.role == "intermediate_assessment"
    assert state.drafts[0].intermediate_segment_ids[-1] == segment.id


def test_marker_update_must_stay_on_active_line():
    c = BenchCreationController(); c.start_bench(); c.choose_line("LOW"); c.use_selected_line(); c.add_marker("LOW", 1)
    with pytest.raises(ValueError):
        c.update_marker("start", "UP", 2)
    c.update_marker("start", "LOW", 3)
    assert c.lower.start_position == 3


def test_created_bench_starts_in_editing_status():
    state = PrototypeState()
    controller = BenchCreationController()
    lower = line("LOW", z=600)
    upper = line("UP", z=620)
    controller.start_bench(); controller.choose_line("LOW"); controller.use_selected_line(); controller.add_marker("LOW", 0); controller.add_marker("LOW", 5); controller.confirm_current_segment(state, lower)
    controller.choose_line("UP"); controller.use_selected_line(); controller.add_marker("UP", 0); controller.add_marker("UP", 5); controller.confirm_current_segment(state, upper)
    bench = controller.create_bench(state)
    assert bench.status == "editing"
    assert bench.intermediate_segment_ids == []
