"""Validated CSV parsing and unsigned point-to-triangulated-surface statistics."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import trimesh


class WallSurveyValidationError(ValueError):
    pass


@dataclass(frozen=True)
class WallRmsResult:
    rms_m: float
    mean_m: float
    std_m: float
    max_m: float
    min_m: float
    point_count: int
    method: str = "unsigned_point_to_surface_v1"


def load_design_surface(path: str | Path) -> trimesh.Trimesh:
    frame = _read_numeric_csv(path, ("PID", "X", "Y", "Z", "FID"), "design surface")
    groups = list(frame.groupby("FID", sort=False))
    if not groups or any(len(group) != 3 for _, group in groups):
        raise WallSurveyValidationError("Each design-surface FID must contain exactly three rows")
    vertices = frame[["X", "Y", "Z"]].to_numpy(dtype=float)
    faces = np.arange(len(vertices), dtype=int).reshape((-1, 3))
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    if mesh.faces.shape[0] == 0:
        raise WallSurveyValidationError("Design surface contains no triangles")
    return mesh


def load_survey_points(path: str | Path) -> np.ndarray:
    frame = _read_numeric_csv(path, ("X", "Y", "Z"), "actual survey")
    if frame.empty:
        raise WallSurveyValidationError("Actual survey contains no points")
    return frame[["X", "Y", "Z"]].to_numpy(dtype=float)


def calculate_wall_rms(design_surface: trimesh.Trimesh, points: np.ndarray) -> WallRmsResult:
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) == 0 or not np.isfinite(points).all():
        raise WallSurveyValidationError("Actual survey must contain finite XYZ points")
    try:
        _nearest, distances, _triangles = design_surface.nearest.on_surface(points)
    except Exception as exc:
        raise WallSurveyValidationError(f"Could not calculate point-to-surface distances: {exc}") from exc
    distances = np.asarray(distances, dtype=float)
    return WallRmsResult(float(np.sqrt(np.mean(distances ** 2))), float(np.mean(distances)),
                         float(np.std(distances)), float(np.max(distances)), float(np.min(distances)), len(points))


def calculate_wall_rms_from_csv(design_path: str | Path, survey_path: str | Path) -> WallRmsResult:
    return calculate_wall_rms(load_design_surface(design_path), load_survey_points(survey_path))


def _read_numeric_csv(path, required, description):
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        raise WallSurveyValidationError(f"Could not read {description} CSV: {exc}") from exc
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise WallSurveyValidationError(f"{description.title()} CSV is missing columns: {', '.join(missing)}")
    try:
        numeric = frame.loc[:, required].apply(pd.to_numeric, errors="raise")
    except Exception as exc:
        raise WallSurveyValidationError(f"{description.title()} CSV contains non-numeric values") from exc
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise WallSurveyValidationError(f"{description.title()} CSV contains non-finite values")
    return numeric
