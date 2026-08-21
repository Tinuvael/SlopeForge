"""Validated CSV parsing and unsigned point-to-triangulated-surface statistics."""
from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Any


class WallSurveyValidationError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        self.code = code
        self.detail = detail
        super().__init__(detail or code)


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
        import trimesh
        import rtree  # noqa: F401 - required by trimesh.nearest.on_surface
    except (ImportError, AttributeError) as exc:
        raise WallSurveyValidationError("dependencies", str(exc)) from exc
    return np, trimesh


def load_design_surface(path: str | Path) -> Any:
    _np, trimesh = _dependencies()
    rows = _read_numeric_csv(path, ("PID", "X", "Y", "Z", "FID"), "design surface")
    vertices: list[list[float]] = []
    faces: list[list[int]] = []
    groups = defaultdict(list)
    for row in rows:
        groups[row["FID"]].append(row)
    for group in groups.values():
        if len(group) != 3:
            continue
        start = len(vertices)
        vertices.extend([[row["X"], row["Y"], row["Z"]] for row in group])
        faces.append([start, start + 1, start + 2])
    if not faces:
        raise WallSurveyValidationError("no_triangles")
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return mesh


def load_survey_points(path: str | Path) -> Any:
    np, _trimesh = _dependencies()
    rows = _read_numeric_csv(path, ("X", "Y", "Z"), "actual survey")
    if not rows:
        raise WallSurveyValidationError("no_points")
    return np.asarray([[row["X"], row["Y"], row["Z"]] for row in rows], dtype=float)


def calculate_wall_rms(design_surface: Any, points: Any) -> WallRmsResult:
    np, _trimesh = _dependencies()
    points = np.asarray(points, dtype=float)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) == 0 or not np.isfinite(points).all():
        raise WallSurveyValidationError("invalid_points")
    try:
        _nearest, distances, _triangles = design_surface.nearest.on_surface(points)
    except Exception as exc:
        raise WallSurveyValidationError("calculation", str(exc)) from exc
    distances = np.asarray(distances, dtype=float)
    return WallRmsResult(float(np.sqrt(np.mean(distances ** 2))), float(np.mean(distances)),
                         float(np.std(distances)), float(np.max(distances)), float(np.min(distances)), len(points))


def calculate_wall_rms_from_csv(design_path: str | Path, survey_path: str | Path) -> WallRmsResult:
    return calculate_wall_rms(load_design_surface(design_path), load_survey_points(survey_path))


def _read_numeric_csv(path, required, description):
    try:
        with Path(path).open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            headers = reader.fieldnames or []
            missing = [name for name in required if name not in headers]
            if missing:
                raise WallSurveyValidationError("missing_columns", ", ".join(missing))
            raw_rows = list(reader)
    except WallSurveyValidationError:
        raise
    except (OSError, UnicodeError, csv.Error) as exc:
        raise WallSurveyValidationError("read_csv", description) from exc
    numeric_rows = []
    for raw in raw_rows:
        try:
            row = {name: float(raw[name]) for name in required}
        except (TypeError, ValueError) as exc:
            raise WallSurveyValidationError("non_numeric", description) from exc
        if not all(isfinite(value) for value in row.values()):
            raise WallSurveyValidationError("non_finite", description)
        numeric_rows.append(row)
    return numeric_rows
