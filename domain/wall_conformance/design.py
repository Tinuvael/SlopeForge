from __future__ import annotations

from collections import defaultdict
from math import hypot

from domain.geometry.operations import clip_datamine_line_by_polygon, point_in_polygon
from domain.geometry.surfaces import TriangleSurface, SurfaceVertex
from domain.geometry.types import PlanLineString, PlanPoint, PlanPolygon
from domain.wall_conformance.models import (
    DesignAlignmentBoundary,
    DesignWallTopology,
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
    del z_tolerance  # retained in the public extraction contract
    return _outer_face_boundary_kind(surface, edge, face_triangle_index)


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


def _triangle_components(
    edges: dict[tuple[int, int], list[int]], roles: tuple[str, ...], wanted: set[str]
) -> tuple[tuple[int, ...], ...]:
    adjacency: dict[int, set[int]] = defaultdict(set)
    for triangle_indices in edges.values():
        if len(triangle_indices) != 2:
            continue
        first, second = triangle_indices
        if roles[first] in wanted and roles[second] in wanted:
            adjacency[first].add(second)
            adjacency[second].add(first)
    unused = {index for index, role in enumerate(roles) if role in wanted}
    components = []
    while unused:
        pending = [min(unused)]
        component = []
        while pending:
            current = pending.pop()
            if current not in unused:
                continue
            unused.remove(current)
            component.append(current)
            pending.extend(adjacency[current])
        components.append(tuple(sorted(component)))
    return tuple(components)


def _third_vertex(surface, edge, triangle_index):
    triangle = surface.triangles[triangle_index]
    return surface.vertices[next(i for i in triangle.vertex_indices if i not in edge)]


def _outer_face_boundary_kind(
    surface: TriangleSurface,
    edge: tuple[int, int],
    face_triangle_index: int,
    *,
    downslope_xy: tuple[float, float] | None = None,
) -> str | None:
    """Classify a Face-patch rim from the triangle's local downslope plane.

    Upper/lower rims run predominantly across the local downslope direction;
    lateral rims run predominantly along it. This uses no triangle winding or
    absolute elevation assumption.
    """
    first, second = (surface.vertices[index] for index in edge)
    third = _third_vertex(surface, edge, face_triangle_index)
    ux, uy = second.x - first.x, second.y - first.y
    vx, vy = third.x - first.x, third.y - first.y
    determinant = ux * vy - uy * vx
    if abs(determinant) <= 1e-12:
        return None
    uz, vz = second.z - first.z, third.z - first.z
    gradient_x = (uz * vy - uy * vz) / determinant
    gradient_y = (ux * vz - uz * vx) / determinant
    down_x, down_y = downslope_xy or (-gradient_x, -gradient_y)
    down_length = hypot(down_x, down_y)
    edge_length = hypot(ux, uy)
    midpoint_x = (first.x + second.x) / 2.0
    midpoint_y = (first.y + second.y) / 2.0
    interior_x, interior_y = third.x - midpoint_x, third.y - midpoint_y
    interior_length = hypot(interior_x, interior_y)
    if down_length <= 1e-12 or edge_length <= 1e-12 or interior_length <= 1e-12:
        return None
    edge_projection = abs(
        (ux * down_x + uy * down_y) / (edge_length * down_length)
    )
    interior_projection = (
        interior_x * down_x + interior_y * down_y
    ) / (interior_length * down_length)
    if abs(interior_projection) <= edge_projection + 1e-9:
        return None
    return "crest" if interior_projection > 0.0 else "toe"


def _face_patch_downslope(
    surface: TriangleSurface, triangle_indices: tuple[int, ...]
) -> tuple[float, float] | None:
    """Area-weighted plan downslope for a connected Face patch."""
    sum_x = sum_y = total_weight = 0.0
    for triangle_index in triangle_indices:
        triangle = surface.triangles[triangle_index]
        first, second, third = (
            surface.vertices[index] for index in triangle.vertex_indices
        )
        ux, uy, uz = second.x - first.x, second.y - first.y, second.z - first.z
        vx, vy, vz = third.x - first.x, third.y - first.y, third.z - first.z
        determinant = ux * vy - uy * vx
        if abs(determinant) <= 1e-12:
            continue
        gradient_x = (uz * vy - uy * vz) / determinant
        gradient_y = (ux * vz - uz * vx) / determinant
        weight = abs(determinant)
        sum_x -= gradient_x * weight
        sum_y -= gradient_y * weight
        total_weight += weight
    if total_weight <= 1e-12 or hypot(sum_x, sum_y) <= 1e-12:
        return None
    return sum_x / total_weight, sum_y / total_weight


def _upper_outer_edges(
    surface: TriangleSurface,
    edges: dict[tuple[int, int], list[int]],
    face_patch: dict[int, int],
    face_triangles: tuple[int, ...],
    patch_index: int,
) -> set[tuple[int, int]]:
    """Return upper-rim chains without their lateral boundary tails.

    Strong strike grade can make an individual upper edge locally neutral.
    Neutral gaps between confidently upper edges are retained, while iterative
    leaf pruning removes side chains which merely hang from the upper rim.
    """
    patch_downslope = _face_patch_downslope(surface, face_triangles)
    classifications = {
        edge: _outer_face_boundary_kind(
            surface,
            edge,
            adjacent[0],
            downslope_xy=patch_downslope,
        )
        for edge, adjacent in edges.items()
        if len(adjacent) == 1 and face_patch.get(adjacent[0]) == patch_index
    }
    confirmed = {edge for edge, kind in classifications.items() if kind == "crest"}
    working = {
        edge for edge, kind in classifications.items() if kind != "toe"
    }
    changed = True
    while changed:
        changed = False
        degree: dict[int, int] = defaultdict(int)
        for first, second in working:
            degree[first] += 1
            degree[second] += 1
        removable = {
            edge
            for edge in working - confirmed
            if degree[edge[0]] <= 1 or degree[edge[1]] <= 1
        }
        if removable:
            working.difference_update(removable)
            changed = True
    return working


def extract_design_wall_topology(
    surface: TriangleSurface,
    role_mapping: SurfaceRoleMapping,
    *,
    z_tolerance: float = 1e-6,
) -> DesignWallTopology:
    """Build transition and upper-alignment relationships from mesh topology.

    A design crest/toe is not guessed from mesh winding. Shared face-platform
    topology remains authoritative. Uppermost outer Face rims are classified
    from their local triangle plane and downslope direction, keeping lateral
    and unknown-role mesh boundaries out of the alignment.
    """
    roles = tuple(
        role_mapping.resolve(triangle.source_attributes)
        for triangle in surface.triangles
    )
    edges = _shared_edges(surface)
    face_components = _triangle_components(edges, roles, {"face"})
    face_patch = {
        triangle: index
        for index, group in enumerate(face_components)
        for triangle in group
    }
    by_patch: dict[int, dict[str, set[tuple[int, int]]]] = {
        index: {"crest": set(), "toe": set()} for index in range(len(face_components))
    }
    for edge, triangle_indices in edges.items():
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
            patch_index = face_patch[face_index]
            by_patch[patch_index][kind].add(edge)

    # A Face without an upper platform may expose the Project's outer upper
    # boundary. These remain candidates; Assessment-envelope probing later
    # distinguishes the external Upper Crest from internal transitions.
    outer_by_patch: dict[int, set[tuple[int, int]]] = defaultdict(set)
    for patch_index in range(len(face_components)):
        if by_patch[patch_index]["crest"]:
            continue
        outer = _upper_outer_edges(
            surface,
            edges,
            face_patch,
            face_components[patch_index],
            patch_index,
        )
        outer_by_patch[patch_index].update(outer)
        # Only locally classified upper-rim edges are walked together, so an
        # alignment cannot turn down a multi-segment lateral crop boundary.
        by_patch[patch_index]["crest"].update(outer)

    transitions = []
    alignments = []
    for patch_index, kinds in by_patch.items():
        crest_lines = _walk_edges(surface, kinds["crest"], "crest")
        toe_lines = _walk_edges(surface, kinds["toe"], "toe")
        transitions.extend((*crest_lines, *toe_lines))
        for line in crest_lines:
            vertex_indices = {
                (vertex.x, vertex.y, vertex.z): index
                for index, vertex in enumerate(surface.vertices)
            }
            boundary_edges = [
                tuple(
                    sorted(
                        (
                            vertex_indices[(first.x, first.y, first.z)],
                            vertex_indices[(second.x, second.y, second.z)],
                        )
                    )
                )
                for first, second in zip(line.points, line.points[1:])
            ]
            interiors = tuple(
                _third_vertex(
                    surface,
                    edge,
                    next(
                        i for i in edges[edge] if face_patch.get(i) == patch_index
                    ),
                )
                for edge in boundary_edges
            )
            source = (
                "outer Face boundary"
                if boundary_edges and all(
                    edge in outer_by_patch[patch_index] for edge in boundary_edges
                )
                else "Face/Platform"
            )
            alignments.append(
                DesignAlignmentBoundary(line, patch_index, interiors, source)
            )

    return DesignWallTopology(tuple(transitions), tuple(alignments))


def extract_design_transition_lines(
    surface: TriangleSurface,
    role_mapping: SurfaceRoleMapping,
    *,
    z_tolerance: float = 1e-6,
) -> tuple[WallTransitionLine, ...]:
    return extract_design_wall_topology(
        surface, role_mapping, z_tolerance=z_tolerance
    ).transitions


def _plan_line(line: WallTransitionLine) -> PlanLineString:
    return PlanLineString(tuple(PlanPoint(point.x, point.y) for point in line.points))


def _fragment_plan_length(fragment: PlanLineString) -> float:
    return sum(
        hypot(b.x - a.x, b.y - a.y)
        for a, b in zip(fragment.points, fragment.points[1:])
    )


def transition_length_in_area(
    line: WallTransitionLine, polygon: PlanPolygon
) -> float:
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
    scored = [(transition_length_in_area(line, assessment_polygon), line) for line in crests]
    scored = [(length, line) for length, line in scored if length > 1e-9]
    if not scored:
        raise ValueError("No design crest intersects the Assessment Area")
    return max(scored, key=lambda item: (item[0], item[1].plan_length))[1]


def select_design_alignment(
    topology: DesignWallTopology, assessment_polygon: PlanPolygon
) -> DesignAlignmentBoundary:
    candidates = [
        boundary
        for boundary in topology.alignment_boundaries
        if transition_length_in_area(boundary.line, assessment_polygon) > 1e-9
    ]
    if not candidates:
        raise ValueError("No design crest intersects the Assessment Area")
    patches = {candidate.face_patch_index for candidate in candidates}
    if len(patches) > 1 or len(candidates) > 1:
        raise ValueError("Design wall alignment is ambiguous in the Assessment Area")
    return candidates[0]


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
    interior_points: tuple[SurfaceVertex, ...] = (),
) -> tuple[WallAlignmentSample, ...]:
    """Sample a design-derived wall alignment independent of Area azimuth.

    Tangents come only from the design crest. Each transverse normal is flipped
    toward the adjacent Face patch when that topology is available, giving a
    deterministic down-wall ``+U`` sign without depending on triangle winding,
    an unrelated global toe, or Assessment boundary orientation.
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

        if len(interior_points) == len(crest_line.points) - 1:
            segment_index = next(
                (
                    index
                    for index, end_chainage in enumerate(cumulative[1:])
                    if chainage <= end_chainage + 1e-9
                ),
                len(interior_points) - 1,
            )
            interior = interior_points[segment_index]
            target = (interior.x, interior.y)
        elif interior_points:
            # Compatibility for boundaries produced before segment provenance
            # was retained. New topology always follows the branch above.
            interior = min(
                interior_points,
                key=lambda point: (point.x - origin.x) ** 2
                + (point.y - origin.y) ** 2,
            )
            target = (interior.x, interior.y)
        else:
            # Compatibility fallback for callers that only have transition
            # lines. The production engine supplies Face-patch interior points.
            target = _nearest_plan_point(origin, toe_lines)
        if target is None:
            continue
        target_dx, target_dy = target[0] - origin.x, target[1] - origin.y
        if target_dx * nx + target_dy * ny < 0:
            nx, ny = -nx, -ny
        if hypot(target_dx, target_dy) <= 1e-9:
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
