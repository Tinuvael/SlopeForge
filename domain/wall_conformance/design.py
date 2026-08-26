from __future__ import annotations

from collections import defaultdict
from math import hypot

from domain.geometry.operations import clip_datamine_line_by_polygon, point_in_polygon
from domain.geometry.surfaces import TriangleSurface, SurfaceVertex
from domain.geometry.types import PlanLineString, PlanPoint, PlanPolygon
from domain.wall_conformance.models import (
    SurfaceRoleMapping,
    WallAlignmentSample,
    WallTransitionLine,
)


PLATFORM_ROLES = {"berm", "road"}


def _shared_edges(surface: TriangleSurface) -> dict[tuple[int, int], list[int]]:
    adjacency: dict[tuple[int, int], list[int]] = defaultdict(list)
    for triangle_index, triangle in enumerate(surface.triangles):
        a, b, c = triangle.vertex_indices
        for first, second in ((a, b), (b, c), (c, a)):
            adjacency[tuple(sorted((first, second)))].append(triangle_index)
    return adjacency


def _face_transition_kind(
    surface: TriangleSurface,
    edge: tuple[int, int],
    face_triangle_index: int,
    *,
    z_tolerance: float,
) -> str | None:
    face_triangle = surface.triangles[face_triangle_index]
    third_index = next(
        index for index in face_triangle.vertex_indices if index not in edge
    )
    first, second = (surface.vertices[index] for index in edge)
    third = surface.vertices[third_index]
    transition_z = (first.z + second.z) / 2.0
    if transition_z > third.z + z_tolerance:
        return "crest"
    if transition_z < third.z - z_tolerance:
        return "toe"
    return None


def _walk_edges(
    surface: TriangleSurface,
    edges: set[tuple[int, int]],
    kind: str,
) -> tuple[WallTransitionLine, ...]:
    if not edges:
        return ()
    adjacency: dict[int, set[int]] = defaultdict(set)
    for first, second in edges:
        adjacency[first].add(second)
        adjacency[second].add(first)

    unused = set(edges)
    lines: list[WallTransitionLine] = []
    while unused:
        vertices_with_unused = {
            vertex
            for edge in unused
            for vertex in edge
        }
        start_candidates = sorted(
            vertex
            for vertex in vertices_with_unused
            if sum(
                tuple(sorted((vertex, neighbour))) in unused
                for neighbour in adjacency[vertex]
            ) != 2
        )
        start = start_candidates[0] if start_candidates else min(vertices_with_unused)
        indices = [start]
        current = start
        previous: int | None = None
        while True:
            candidates = sorted(
                neighbour
                for neighbour in adjacency[current]
                if tuple(sorted((current, neighbour))) in unused
                and neighbour != previous
            )
            if not candidates:
                break
            neighbour = candidates[0]
            unused.remove(tuple(sorted((current, neighbour))))
            indices.append(neighbour)
            previous, current = current, neighbour
            if current == start:
                break
        if len(indices) >= 2:
            lines.append(
                WallTransitionLine(kind, tuple(surface.vertices[index] for index in indices))
            )
    return tuple(
        sorted(
            lines,
            key=lambda line: (-line.plan_length, tuple((p.x, p.y, p.z) for p in line.points)),
        )
    )


def extract_design_transition_lines(
    surface: TriangleSurface,
    role_mapping: SurfaceRoleMapping,
    *,
    z_tolerance: float = 1e-6,
) -> tuple[WallTransitionLine, ...]:
    """Extract crest/toe breaklines from shared face-platform design edges.

    A design crest/toe is not guessed from mesh winding. It must be a shared
    topological edge between a canonical ``face`` triangle and a ``berm`` or
    ``road`` triangle. The face-side third vertex determines whether that edge
    is the upper (crest) or lower (toe) boundary of the face.
    """
    roles = tuple(role_mapping.resolve(triangle.source_attributes) for triangle in surface.triangles)
    by_kind: dict[str, set[tuple[int, int]]] = {"crest": set(), "toe": set()}
    for edge, triangle_indices in _shared_edges(surface).items():
        if len(triangle_indices) != 2:
            continue
        first_index, second_index = triangle_indices
        first_role, second_role = roles[first_index], roles[second_index]
        if first_role == "face" and second_role in PLATFORM_ROLES:
            face_index = first_index
        elif second_role == "face" and first_role in PLATFORM_ROLES:
            face_index = second_index
        else:
            continue
        kind = _face_transition_kind(
            surface,
            edge,
            face_index,
            z_tolerance=z_tolerance,
        )
        if kind is not None:
            by_kind[kind].add(edge)

    return (
        *_walk_edges(surface, by_kind["crest"], "crest"),
        *_walk_edges(surface, by_kind["toe"], "toe"),
    )


def _clipped_plan_length(line: WallTransitionLine, polygon: PlanPolygon) -> float:
    plan_line = PlanLineString(tuple(PlanPoint(point.x, point.y) for point in line.points))
    fragments = clip_datamine_line_by_polygon(plan_line, polygon)
    return sum(
        hypot(b.x - a.x, b.y - a.y)
        for fragment in fragments
        for a, b in zip(fragment.points, fragment.points[1:])
    )


def select_primary_crest_line(
    transitions: tuple[WallTransitionLine, ...],
    assessment_polygon: PlanPolygon,
) -> WallTransitionLine:
    """Choose the design crest with the greatest plan length inside the Area."""
    crests = [line for line in transitions if line.kind == "crest"]
    scored = [(_clipped_plan_length(line, assessment_polygon), line) for line in crests]
    scored = [(length, line) for length, line in scored if length > 1e-9]
    if not scored:
        raise ValueError("No design crest intersects the Assessment Area")
    return max(scored, key=lambda item: (item[0], item[1].plan_length))[1]


def _cumulative_plan_lengths(points: tuple[SurfaceVertex, ...]) -> tuple[float, ...]:
    values = [0.0]
    for first, second in zip(points, points[1:]):
        values.append(values[-1] + hypot(second.x - first.x, second.y - first.y))
    return tuple(values)


def _interpolate_polyline(
    points: tuple[SurfaceVertex, ...],
    cumulative: tuple[float, ...],
    chainage: float,
) -> SurfaceVertex:
    if chainage <= 0:
        return points[0]
    if chainage >= cumulative[-1]:
        return points[-1]
    for index, (start_s, end_s) in enumerate(zip(cumulative, cumulative[1:])):
        if chainage <= end_s:
            span = end_s - start_s
            fraction = 0.0 if span <= 1e-12 else (chainage - start_s) / span
            first, second = points[index], points[index + 1]
            return SurfaceVertex(
                first.x + (second.x - first.x) * fraction,
                first.y + (second.y - first.y) * fraction,
                first.z + (second.z - first.z) * fraction,
            )
    return points[-1]


def _nearest_plan_point(
    origin: SurfaceVertex,
    lines: tuple[WallTransitionLine, ...],
) -> tuple[float, float] | None:
    best: tuple[float, float, float] | None = None
    for line in lines:
        for first, second in zip(line.points, line.points[1:]):
            dx, dy = second.x - first.x, second.y - first.y
            length_sq = dx * dx + dy * dy
            fraction = (
                0.0
                if length_sq <= 1e-18
                else max(
                    0.0,
                    min(
                        1.0,
                        ((origin.x - first.x) * dx + (origin.y - first.y) * dy)
                        / length_sq,
                    ),
                )
            )
            x = first.x + dx * fraction
            y = first.y + dy * fraction
            distance_sq = (x - origin.x) ** 2 + (y - origin.y) ** 2
            candidate = (distance_sq, x, y)
            if best is None or candidate < best:
                best = candidate
    return None if best is None else (best[1], best[2])


def _chainages(total_length: float, spacing: float) -> tuple[float, ...]:
    values = [0.0]
    current = spacing
    while current < total_length - 1e-9:
        values.append(current)
        current += spacing
    if total_length > 1e-9 and abs(values[-1] - total_length) > 1e-9:
        values.append(total_length)
    return tuple(values)


def sample_wall_alignment(
    crest_line: WallTransitionLine,
    toe_lines: tuple[WallTransitionLine, ...],
    assessment_polygon: PlanPolygon,
    *,
    spacing_m: float = 3.0,
    tangent_window_m: float = 6.0,
) -> tuple[WallAlignmentSample, ...]:
    """Sample a design-derived wall alignment independent of Area azimuth.

    Tangents come only from the design crest. Each transverse normal is flipped
    toward the nearest design toe, giving a deterministic downslope ``+U`` sign
    without depending on triangle winding or Assessment boundary orientation.
    """
    if crest_line.kind != "crest":
        raise ValueError("Wall alignment requires a design crest line")
    if not toe_lines or any(line.kind != "toe" for line in toe_lines):
        raise ValueError("Wall alignment requires at least one design toe line")
    if spacing_m <= 0 or tangent_window_m <= 0:
        raise ValueError("Alignment spacing and tangent window must be positive")

    cumulative = _cumulative_plan_lengths(crest_line.points)
    total_length = cumulative[-1]
    if total_length <= 1e-9:
        raise ValueError("Design crest has zero plan length")

    samples: list[WallAlignmentSample] = []
    for chainage in _chainages(total_length, spacing_m):
        origin = _interpolate_polyline(crest_line.points, cumulative, chainage)
        if not point_in_polygon(PlanPoint(origin.x, origin.y), assessment_polygon):
            continue
        before = _interpolate_polyline(
            crest_line.points,
            cumulative,
            max(0.0, chainage - tangent_window_m),
        )
        after = _interpolate_polyline(
            crest_line.points,
            cumulative,
            min(total_length, chainage + tangent_window_m),
        )
        tx, ty = after.x - before.x, after.y - before.y
        tangent_length = hypot(tx, ty)
        if tangent_length <= 1e-9:
            continue
        tx, ty = tx / tangent_length, ty / tangent_length
        nx, ny = -ty, tx

        toe = _nearest_plan_point(origin, toe_lines)
        if toe is None:
            continue
        toe_dx, toe_dy = toe[0] - origin.x, toe[1] - origin.y
        if toe_dx * nx + toe_dy * ny < 0:
            nx, ny = -nx, -ny
        if hypot(toe_dx, toe_dy) <= 1e-9:
            continue

        samples.append(
            WallAlignmentSample(
                chainage_m=chainage,
                origin=origin,
                tangent_xy=(tx, ty),
                normal_xy=(nx, ny),
            )
        )
    if not samples:
        raise ValueError("No design wall alignment samples fall inside the Assessment Area")
    return tuple(samples)
