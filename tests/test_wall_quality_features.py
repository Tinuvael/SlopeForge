from copy import deepcopy
import json

import numpy as np
import pytest

from domain.assessment.evaluation import MeasuredWallGeometry, calculate_revision
from domain.blasting.technical_card import GeomechanicalParameters, JointSetOrientation, new_technical_card
from infrastructure.geometry_import.wall_rms import WallSurveyValidationError, calculate_wall_rms_from_csv, load_design_surface
from tests.test_technical_cards import event
from tests.test_wall_assessment import complete_revision


def test_engineering_inputs_and_actual_deviations_round_trip():
    card, draft = new_technical_card(event())
    draft.geomechanical_parameters = GeomechanicalParameters(rock_density_t_m3=2.71, ucs_mpa=80,
        joint_sets=[JointSetOrientation(45, 359, 1.2, 8.5)])
    draft.actual_execution.copy_from_design(draft.drilling_groups, mode="replace")
    actual = draft.actual_execution.actual_drilling_groups[0]
    actual.mean_collar_deviation_m, actual.max_collar_deviation_m = .1, .25
    actual.mean_toe_deviation_m, actual.max_toe_deviation_m = .4, .9
    draft.actual_execution.copy_from_design(draft.drilling_groups, mode="replace")
    saved = card.save_revision(draft)
    restored = type(card).from_dict(json.loads(json.dumps(card.to_dict()))).revisions[0]
    assert restored.geomechanical_parameters.rock_density_t_m3 == 2.71
    assert restored.geomechanical_parameters.joint_sets[0].spacing_m == 1.2
    assert restored.geomechanical_parameters.joint_sets[0].persistence_m == 8.5
    assert restored.actual_execution.actual_drilling_groups[0].design_group_id == saved.drilling_groups[0].id
    assert restored.actual_execution.actual_drilling_groups[0].mean_toe_deviation_m == .4


def test_compact_comparisons_wrap_azimuth_and_ratios_are_safe():
    _, revision = new_technical_card(event()); design = revision.drilling_groups[0]
    design.burden_m, design.spacing_m, design.azimuth_deg = 4, 5, 359
    revision.production_parameters.design_bench_height_m = 12
    revision.actual_execution.copy_from_design(revision.drilling_groups, mode="replace")
    actual = revision.actual_execution.actual_drilling_groups[0]
    actual.azimuth_deg = 1; actual.mean_toe_deviation_m = 1
    rows = {row["parameter"]: row for row in revision.compact_design_actual(design.id)}
    assert rows["Azimuth"]["delta"] == 2
    assert revision.compact_design_actual("missing")[0]["delta"] is None
    assert revision.engineering_ratios(design.id) == {"B/S": .8, "S/B": 1.25, "H/B": 3,
        "mean toe deviation / burden": .25, "mean toe deviation / spacing": .2}
    actual.burden_m = 0
    assert revision.engineering_ratios(design.id)["H/B"] is None


def test_measured_geometry_round_trip_does_not_change_scoring():
    revision = complete_revision(); calculate_revision(revision, True)
    before = (revision.design_achievement_index, revision.face_condition_index, revision.result_quadrant)
    revision.measured_wall_geometry = MeasuredWallGeometry(1, 2, .3, .2, .5, "survey", "design.csv", "actual.csv", 3, "unsigned_point_to_surface_v1")
    restored = type(revision).from_dict(json.loads(json.dumps(revision.to_dict())))
    calculate_revision(restored, True)
    assert restored.measured_wall_geometry.measurement_method == "survey"
    assert (restored.design_achievement_index, restored.face_condition_index, restored.result_quadrant) == before


def test_synthetic_surface_rms_and_invalid_csv(tmp_path):
    design = tmp_path / "design.csv"; survey = tmp_path / "survey.csv"
    design.write_text("PID,X,Y,Z,FID\n1,0,0,0,10\n2,10,0,0,10\n3,0,10,0,10\n")
    survey.write_text("X,Y,Z\n1,1,1\n2,2,2\n3,3,3\n")
    assert load_design_surface(design).faces.shape == (1, 3)
    result = calculate_wall_rms_from_csv(design, survey)
    assert result.rms_m == pytest.approx(np.sqrt(14 / 3))
    assert result.mean_m == 2 and result.std_m == pytest.approx(np.std([1, 2, 3]))
    assert (result.min_m, result.max_m, result.point_count) == (1, 3, 3)
    design.write_text("X,Y,Z\n0,0,0\n")
    with pytest.raises(WallSurveyValidationError, match="missing columns"):
        calculate_wall_rms_from_csv(design, survey)
