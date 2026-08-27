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
        vertices_with_unused = {vertex for edge in unused for vertex in edge}
        start_candidates = sorted(
            vertex
            for vertex in vertices_with_unused
            if sum(
                tuple(sorted((vertex, neighbour))) in unused
                for neighbour in adjacency[vertex]
            )
            != 2
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
            key=lambda line: (
                -line.plan_length,
                tuple((p.x, p.y, p.z) for p in line.points),
            ),
        )
    )


def extract_design_transition_lines(
    surface: TriangleSurface,
    role_mapping: SurfaceRoleMapping,
    *,
    z_tolerance: float = 1e-6,
) -> tuple[WallTransitionLine, ...]:
    """Extract breaklines from face-platform edges and upper face boundaries.

    A design crest/toe is not guessed from mesh winding. Shared face-platform
    topology remains authoritative. A one-triangle outer
    edge is accepted only as a crest when its face-side third vertex is lower;
    this conservative fallback supports the uppermost bench without treating
    lateral or unknown-role mesh boundaries as crests.
    """
    roles = tuple(
        role_mapping.resolve(triangle.source_attributes)
        for triangle in surface.triangles
    )
    by_kind: dict[str, set[tuple[int, int]]] = {"crest": set(), "toe": set()}
    for edge, triangle_indices in _shared_edges(surface).items():
        if len(triangle_indices) == 1:
            face_index = triangle_indices[0]
            if roles[face_index] != "face":
                continue
            first, second = (surface.vertices[index] for index in edge)
            if abs(first.z - second.z) > z_tolerance:
                continue
            if _face_transition_kind(
                surface, edge, face_index, z_tolerance=z_tolerance
            ) == "crest":
                by_kind["crest"].add(edge)
            continue
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


def _plan_line(line: WallTransitionLine) -> PlanLineString:
    return PlanLineString(tuple(PlanPoint(point.x, point.y) for point in line.points))


def _fragment_plan_length(fragment: PlanLineString) -> float:
    return sum(
        hypot(b.x - a.x, b.y - a.y)
        for a, b in zip(fragment.points, fragment.points[1:])
    )


def _clipped_plan_length(line: WallTransitionLine, polygon: PlanPolygon) -> float:
    return sum(
        _fragment_plan_length(fragment)
        for fragment in clip_datamine_line_by_polygon(_plan_line(line), polygon)
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


def _line_is_closed(points: tuple[SurfaceVertex, ...], tolerance: float = 1e-8) -> bool:
    if len(points) < 3:
        return False
    first, last = points[0], points[-1]
    return hypot(last.x - first.x, last.y - first.y) <= tolerance


def _interpolate_polyline(
    points: tuple[SurfaceVertex, ...],
    cumulative: tuple[float, ...],
    chainage: float,
    *,
    closed: bool = False,
) -> SurfaceVertex:
    total = cumulative[-1]
    if closed:
        chainage %= total
    elif chainage <= 0:
        return points[0]
    elif chainage >= total:
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


def _chainages(total_length: float, spacing: float, *, closed: bool) -> tuple[float, ...]:
    values = [0.0]
    current = spacing
    while current < total_length - 1e-9:
        values.append(current)
        current += spacing
    if (
        not closed
        and total_length > 1e-9
        and abs(values[-1] - total_length) > 1e-9
    ):
        values.append(total_length)
    return tuple(values)


def _fragment_midpoint(fragment: PlanLineString) -> PlanPoint:
    cumulative = [0.0]
    for first, second in zip(fragment.points, fragment.points[1:]):
        cumulative.append(cumulative[-1] + hypot(second.x - first.x, second.y - first.y))
    target = cumulative[-1] / 2.0
    for index, (start_s, end_s) in enumerate(zip(cumulative, cumulative[1:])):
        if target <= end_s:
            span = end_s - start_s
            fraction = 0.0 if span <= 1e-12 else (target - start_s) / span
            first, second = fragment.points[index], fragment.points[index + 1]
            return PlanPoint(
                first.x + (second.x - first.x) * fraction,
                first.y + (second.y - first.y) * fraction,
            )
    return fragment.points[-1]


def _plan_point_chainage(
    points: tuple[SurfaceVertex, ...],
    cumulative: tuple[float, ...],
    target: PlanPoint,
) -> float:
    best: tuple[float, float] | None = None
    for index, (first, second) in enumerate(zip(points, points[1:])):
        dx, dy = second.x - first.x, second.y - first.y
        length_sq = dx * dx + dy * dy
        fraction = (
            0.0
            if length_sq <= 1e-18
            else max(
                0.0,
                min(
                    1.0,
                    ((target.x - first.x) * dx + (target.y - first.y) * dy)
                    / length_sq,
                ),
            )
        )
        x = first.x + dx * fraction
        y = first.y + dy * fraction
        distance_sq = (target.x - x) ** 2 + (target.y - y) ** 2
        segment_length = hypot(dx, dy)
        chainage = cumulative[index] + segment_length * fraction
        candidate = (distance_sq, chainage)
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise ValueError("Design crest has no measurable segment")
    return best[1]


def _fallback_chainage_inside_polygon(
    crest_line: WallTransitionLine,
    assessment_polygon: PlanPolygon,
    cumulative: tuple[float, ...],
) -> float | None:
    fragments = clip_datamine_line_by_polygon(_plan_line(crest_line), assessment_polygon)
    if not fragments:
        return None
    fragment = max(fragments, key=_fragment_plan_length)
    if _fragment_plan_length(fragment) <= 1e-9:
        return None
    return _plan_point_chainage(
        crest_line.points,
        cumulative,
        _fragment_midpoint(fragment),
    )


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
    Closed crest loops wrap the tangent window across their storage seam. If a
    narrow Area falls entirely between regular chainage stations, the midpoint
    of its longest crest fragment supplies one deterministic fallback profile.
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
    closed = _line_is_closed(crest_line.points)

    candidate_chainages = [
        chainage
        for chainage in _chainages(total_length, spacing_m, closed=closed)
        if point_in_polygon(
            PlanPoint(
                _interpolate_polyline(
                    crest_line.points,
                    cumulative,
                    chainage,
                    closed=closed,
                ).x,
                _interpolate_polyline(
                    crest_line.points,
                    cumulative,
                    chainage,
                    closed=closed,
                ).y,
            ),
            assessment_polygon,
        )
    ]
    if not candidate_chainages:
        fallback = _fallback_chainage_inside_polygon(
            crest_line,
            assessment_polygon,
            cumulative,
        )
        if fallback is not None:
            candidate_chainages.append(fallback)

    samples: list[WallAlignmentSample] = []
    for chainage in candidate_chainages:
        origin = _interpolate_polyline(
            crest_line.points,
            cumulative,
            chainage,
            closed=closed,
        )
        if closed:
            before_chainage = chainage - tangent_window_m
            after_chainage = chainage + tangent_window_m
        else:
            before_chainage = max(0.0, chainage - tangent_window_m)
            after_chainage = min(total_length, chainage + tangent_window_m)
        before = _interpolate_polyline(
            crest_line.points,
            cumulative,
            before_chainage,
            closed=closed,
        )
        after = _interpolate_polyline(
            crest_line.points,
            cumulative,
            after_chainage,
            closed=closed,
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
