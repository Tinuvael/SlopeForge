"""Validated CSV parsing and unsigned point-to-triangulated-surface statistics."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def _dependencies():
    """Load optional RMS dependencies only when the calculator is used."""
    try:
        import numpy as np
        import pandas as pd
        import trimesh
    except (ImportError, AttributeError) as exc:
        raise WallSurveyValidationError(
            "Wall RMS calculation requires compatible numpy, pandas, trimesh and rtree installations"
        ) from exc
    return np, pd, trimesh


def load_design_surface(path: str | Path) -> Any:
    np, _pd, trimesh = _dependencies()
    frame = _read_numeric_csv(path, ("PID", "X", "Y", "Z", "FID"), "design surface")
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    for _fid, group in frame.groupby("FID", sort=False):
        if len(group) != 3:
            continue
        start = len(vertices)
        vertices.extend(group[["X", "Y", "Z"]].to_numpy(dtype=float).tolist())
        faces.append([start, start + 1, start + 2])
    if not faces:
        raise WallSurveyValidationError("Design surface contains no FID with exactly three rows")
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return mesh


def load_survey_points(path: str | Path) -> Any:
    np, _pd, _trimesh = _dependencies()
    frame = _read_numeric_csv(path, ("X", "Y", "Z"), "actual survey")
    if frame.empty:
        raise WallSurveyValidationError("Actual survey contains no points")
    return frame[["X", "Y", "Z"]].to_numpy(dtype=float)


def calculate_wall_rms(design_surface: Any, points: Any) -> WallRmsResult:
    np, _pd, _trimesh = _dependencies()
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
    np, pd, _trimesh = _dependencies()
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
