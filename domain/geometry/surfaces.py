from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite
from typing import Any


class SurfaceGeometryError(ValueError):
    pass


@dataclass(frozen=True)
class SurfaceVertex:
    x: float
    y: float
    z: float

    def __post_init__(self) -> None:
        if not all(isfinite(float(value)) for value in (self.x, self.y, self.z)):
            raise SurfaceGeometryError("Surface vertices must contain finite XYZ coordinates")


@dataclass(frozen=True)
class SurfaceTriangle:
    vertex_indices: tuple[int, int, int]
    source_id: str | None = None
    source_attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(set(self.vertex_indices)) != 3:
            raise SurfaceGeometryError("Surface triangle must reference three distinct vertices")
        if any(index < 0 for index in self.vertex_indices):
            raise SurfaceGeometryError("Surface triangle vertex indices must be non-negative")


@dataclass(frozen=True)
class TriangleSurface:
    vertices: tuple[SurfaceVertex, ...]
    triangles: tuple[SurfaceTriangle, ...]
    source_files: tuple[str, ...] = ()
    source_attributes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.vertices) < 3:
            raise SurfaceGeometryError("Surface requires at least three vertices")
        if not self.triangles:
            raise SurfaceGeometryError("Surface requires at least one triangle")
        vertex_count = len(self.vertices)
        for triangle in self.triangles:
            if any(index >= vertex_count for index in triangle.vertex_indices):
                raise SurfaceGeometryError("Surface triangle references a missing vertex")
            a, b, c = (self.vertices[index] for index in triangle.vertex_indices)
            ab = (b.x - a.x, b.y - a.y, b.z - a.z)
            ac = (c.x - a.x, c.y - a.y, c.z - a.z)
            cross = (
                ab[1] * ac[2] - ab[2] * ac[1],
                ab[2] * ac[0] - ab[0] * ac[2],
                ab[0] * ac[1] - ab[1] * ac[0],
            )
            if sum(value * value for value in cross) <= 1e-24:
                raise SurfaceGeometryError("Surface contains a degenerate triangle")
