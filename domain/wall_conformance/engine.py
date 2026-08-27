from __future__ import annotations

import logging
from math import hypot

from domain.geometry.operations import point_in_polygon
from domain.geometry.surfaces import SurfaceVertex, TriangleSurface
from domain.geometry.types import PlanPoint, PlanPolygon
from domain.wall_conformance.design import (
    extract_design_wall_topology,
    sample_wall_alignment,
    transition_length_in_area,
)
from domain.wall_conformance.models import (
    DesignAlignmentBoundary,
    ExternalWallBoundary,
    SectionPoint,
    SectionSegment,
    SurfaceRoleMapping,
    TransverseProfile,
    WallAlignmentSample,
    WallProfileSet,
)
from domain.wall_conformance.sections import (
    clip_section_segments_to_z_range,
    intersect_surface_with_profile,
)
from domain.wall_conformance.semantic_sections import build_design_section, build_design_variants


logger = logging.getLogger(__name__)


def _assemble_alignment_boundaries(boundaries, tolerance: float = 0.02):
    """Join continuous crest fragments without bridging separate wall sectors."""
    remaining = list(boundaries)
    assembled = []
    while remaining:
        current = remaining.pop(0)
        points = list(current.line.points)
        interiors = list(current.interior_points)
        sources = {current.source}
        patch_indices = {current.face_patch_index}
        changed = True
        while changed:
            changed = False
            for index, candidate in enumerate(remaining):
                variants = (
                    (candidate.line.points, candidate.interior_points),
                    (
                        tuple(reversed(candidate.line.points)),
                        tuple(reversed(candidate.interior_points)),
                    ),
                )
                joined = None
                for candidate_points, candidate_interiors in variants:
                    append_distance = hypot(
                        points[-1].x - candidate_points[0].x,
                        points[-1].y - candidate_points[0].y,
                    )
                    prepend_distance = hypot(
                        candidate_points[-1].x - points[0].x,
                        candidate_points[-1].y - points[0].y,
                    )

                    def direction_ok(first_a, first_b, second_a, second_b):
                        first = (first_b.x - first_a.x, first_b.y - first_a.y)
                        second = (second_b.x - second_a.x, second_b.y - second_a.y)
                        lengths = hypot(*first) * hypot(*second)
                        return lengths > 1e-12 and (
                            first[0] * second[0] + first[1] * second[1]
                        ) / lengths >= 0.5

                    if append_distance <= tolerance and direction_ok(
                        points[-2], points[-1], candidate_points[0], candidate_points[1]
                    ):
                        joined = "append", candidate_points, candidate_interiors
                        break
                    if prepend_distance <= tolerance and direction_ok(
                        candidate_points[-2], candidate_points[-1], points[0], points[1]
                    ):
                        joined = "prepend", candidate_points, candidate_interiors
                        break
                if joined is None:
                    continue
                mode, candidate_points, candidate_interiors = joined
                if mode == "append" and points[-1] != candidate_points[0]:
                    bridge = SurfaceVertex(
                        (points[-1].x + candidate_points[0].x) / 2.0,
                        (points[-1].y + candidate_points[0].y) / 2.0,
                        (points[-1].z + candidate_points[0].z) / 2.0,
                    )
                    points[-1] = bridge
                    candidate_points = (bridge, *candidate_points[1:])
                elif mode == "prepend" and candidate_points[-1] != points[0]:
                    bridge = SurfaceVertex(
                        (candidate_points[-1].x + points[0].x) / 2.0,
                        (candidate_points[-1].y + points[0].y) / 2.0,
                        (candidate_points[-1].z + points[0].z) / 2.0,
                    )
                    candidate_points = (*candidate_points[:-1], bridge)
                    points[0] = bridge
                if mode == "append":
                    points.extend(candidate_points[1:])
                    interiors.extend(candidate_interiors)
                else:
                    points = [*candidate_points[:-1], *points]
                    interiors = [*candidate_interiors, *interiors]
                sources.add(candidate.source)
                patch_indices.add(candidate.face_patch_index)
                remaining.pop(index)
                changed = True
                break
        source = next(iter(sources)) if len(sources) == 1 else "mixed crest sources"
        patch_index = next(iter(patch_indices)) if len(patch_indices) == 1 else -1
        assembled.append(
            DesignAlignmentBoundary(
                type(current.line)("crest", tuple(points)),
                patch_index,
                tuple(interiors),
                source,
            )
        )
    return tuple(assembled)


def _segment_inside_area(segment: SectionSegment, area: PlanPolygon) -> bool:
    return point_in_polygon(
        PlanPoint(
            (segment.start.x + segment.end.x) / 2.0,
            (segment.start.y + segment.end.y) / 2.0,
        ),
        area,
    )


def _terminal_toe(section) -> SectionPoint | None:
    transitions = _face_platform_toes(section)
    return transitions[-1] if transitions else None


def _face_platform_toes(section) -> tuple[SectionPoint, ...]:
    return tuple(
        first.end
        for first, second in zip(section.elements, section.elements[1:])
        if first.role == "face" and second.role in {"berm", "road"}
    )


def _cross_xy(
    first: tuple[float, float], second: tuple[float, float]
) -> float:
    return first[0] * second[1] - first[1] * second[0]


def _assessment_u_interval(
    sample, area: PlanPolygon
) -> tuple[float, float] | None:
    """Return the Assessment interval containing the profile origin.

    Intersections are converted into inside intervals along the positive-U ray.
    This handles an origin on/slightly outside the upper boundary and avoids
    selecting a later re-entry of a concave Assessment polygon.
    """
    origin = sample.origin
    direction = sample.normal_xy
    intersections = []
    for first, second in zip(area.ring, area.ring[1:]):
        edge = (second.x - first.x, second.y - first.y)
        offset = (first.x - origin.x, first.y - origin.y)
        denominator = _cross_xy(direction, edge)
        if abs(denominator) <= 1e-12:
            continue
        ray_u = _cross_xy(offset, edge) / denominator
        edge_fraction = _cross_xy(offset, direction) / denominator
        if -1e-8 <= edge_fraction <= 1.0 + 1e-8:
            intersections.append(ray_u)
    ordered = []
    for value in sorted(intersections):
        if not ordered or abs(value - ordered[-1]) > 1e-7:
            ordered.append(value)
    if not ordered:
        return None
    bounds = ordered
    for start, end in zip(bounds, bounds[1:]):
        if end - start <= 1e-8:
            continue
        midpoint = (start + end) / 2.0
        if point_in_polygon(
            PlanPoint(
                origin.x + midpoint * direction[0],
                origin.y + midpoint * direction[1],
            ),
            area,
        ):
            if start - 1e-7 <= 0.0 <= end + 1e-7:
                return start, end
    # The sampled crest can sit just outside the drawn polygon. Use the first
    # downstream inside interval rather than falling back to a fixed width.
    for start, end in zip(bounds, bounds[1:]):
        midpoint = (start + end) / 2.0
        if end > 0.0 and point_in_polygon(
            PlanPoint(
                origin.x + midpoint * direction[0],
                origin.y + midpoint * direction[1],
            ),
            area,
        ):
            return start, end
    return None


def _downstream_area_exit_u(sample, area: PlanPolygon) -> float | None:
    interval = _assessment_u_interval(sample, area)
    return None if interval is None else interval[1]


def _interpolate_section_point(first: SectionPoint, second: SectionPoint, u: float):
    span = second.u - first.u
    fraction = 0.0 if abs(span) <= 1e-12 else (u - first.u) / span
    return SectionPoint(
        u,
        first.z + (second.z - first.z) * fraction,
        first.x + (second.x - first.x) * fraction,
        first.y + (second.y - first.y) * fraction,
    )


def _clip_segments_to_interval(segments, interval):
    if interval is None:
        return ()
    lower, upper = interval
    clipped = []
    for segment in segments:
        if segment.u_max < lower - 1e-9 or segment.u_min > upper + 1e-9:
            continue
        start, end = segment.start, segment.end
        if start.u > end.u:
            start, end = end, start
        if start.u < lower:
            start = _interpolate_section_point(start, end, lower)
        if end.u > upper:
            end = _interpolate_section_point(start, end, upper)
        clipped.append(
            SectionSegment(
                start,
                end,
                segment.source_triangle_index,
                segment.semantic_role,
            )
        )
    return tuple(clipped)


def _toe_near_area_exit(
    section, downstream_area_u: float | None
) -> tuple[SectionPoint | None, tuple[SectionPoint, ...]]:
    transitions = _face_platform_toes(section)
    if downstream_area_u is None or not transitions:
        return None, transitions
    return min(
        transitions, key=lambda point: abs(point.u - downstream_area_u)
    ), transitions


def _select_upper_envelope(
    topology,
    design_surface: TriangleSurface,
    assessment_polygon: PlanPolygon,
    role_mapping: SurfaceRoleMapping,
    toe_lines,
    *,
    spacing_m: float,
    tangent_window_m: float,
) -> ExternalWallBoundary:
    candidates = [
        boundary
        # Topology extraction has already derived maximal chains from the
        # semantic edge network. Reassembling them here could join separate
        # branches again at a junction and destroy the network topology.
        for boundary in topology.alignment_boundaries
        if transition_length_in_area(boundary.line, assessment_polygon) > 1e-9
    ]
    logger.debug(
        "Assessment Area wall-envelope diagnostics: crest candidates=%d",
        len(candidates),
    )
    diagnostics = []
    for index, boundary in enumerate(candidates):
        probe_spacing = max(spacing_m, boundary.line.plan_length / 3.0)
        try:
            samples = sample_wall_alignment(
                boundary.line,
                toe_lines,
                assessment_polygon,
                spacing_m=probe_spacing,
                tangent_window_m=tangent_window_m,
                interior_points=boundary.interior_points,
            )
        except ValueError:
            samples = ()
        upstream_faces = 0
        valid_downstream = 0
        terminal_toes = []
        for probe_index, sample in enumerate(samples):
            full_segments = intersect_surface_with_profile(
                design_surface, sample, role_mapping=role_mapping
            )
            area_segments = tuple(
                segment for segment in full_segments
                if _segment_inside_area(segment, assessment_polygon)
            )
            upstream_face = any(
                segment.semantic_role == "face" and segment.u_max < -1e-4
                for segment in area_segments
            )
            if upstream_face:
                upstream_faces += 1
            full_section = build_design_section(full_segments)
            downstream_area_u = _downstream_area_exit_u(
                sample, assessment_polygon
            )
            terminal, toe_transitions = _toe_near_area_exit(
                full_section, downstream_area_u
            )
            first_downstream = next(
                (
                    element
                    for element in full_section.elements
                    if element.horizontal_width > 1e-4
                ),
                None,
            )
            if (
                terminal is not None
                and first_downstream is not None
                and first_downstream.role == "face"
            ):
                valid_downstream += 1
                terminal_toes.append(terminal)
            logger.debug(
                "Envelope candidate %d probe %d: area_exit_u=%s "
                "toe_transitions=%s terminal_toe_u=%s delta=%s upstream_face=%s",
                index,
                probe_index,
                None if downstream_area_u is None else round(downstream_area_u, 3),
                [round(point.u, 3) for point in toe_transitions],
                None if terminal is None else round(terminal.u, 3),
                None
                if terminal is None or downstream_area_u is None
                else round(abs(terminal.u - downstream_area_u), 3),
                upstream_face,
            )
        in_area_length = transition_length_in_area(
            boundary.line, assessment_polygon
        )
        sample_count = len(samples)
        upstream_fraction = upstream_faces / sample_count if sample_count else 1.0
        valid_fraction = valid_downstream / sample_count if sample_count else 0.0
        diagnostics.append(
            (
                upstream_fraction,
                -valid_fraction,
                -sample_count,
                boundary,
                tuple(terminal_toes),
            )
        )
        logger.debug(
            "Envelope candidate %d: length=%.3f source=%s samples=%d "
            "valid_downstream=%d upstream_faces=%d terminal_toes=%d",
            index,
            in_area_length,
            boundary.source,
            len(samples),
            valid_downstream,
            upstream_faces,
            len(terminal_toes),
        )
    # A component is external when it has coherent downstream probes and at
    # least one locally clean station. Remote folded-wall intersections may
    # make other probes report upstream Face geometry; they are not a reason
    # to discard the whole physical component. An internal crest, by contrast,
    # has evaluated Face geometry upstream at every sampled station.
    viable = [item for item in diagnostics if -item[1] > 0.0 and item[0] < 1.0]
    if not viable:
        logger.debug("Wall-envelope selection failed: no valid downstream probes")
        raise ValueError("Unable to determine a unique Design wall envelope")
    # A remote upstream intersection is diagnostic only. Membership is local:
    # every component with at least one coherent downstream Face/toe probe is
    # retained. One cleaner component must never suppress another valid part.
    external = [item[3] for item in viable]
    external.sort(key=lambda boundary: tuple(
        (point.x, point.y, point.z) for point in boundary.line.points
    ))

    def local_downstream(boundary):
        if not boundary.interior_points:
            return None
        first, second = boundary.line.points[0], boundary.line.points[-1]
        midpoint = ((first.x + second.x) / 2.0, (first.y + second.y) / 2.0)
        interior = min(boundary.interior_points, key=lambda point:
            (point.x - midpoint[0]) ** 2 + (point.y - midpoint[1]) ** 2)
        vector = interior.x - midpoint[0], interior.y - midpoint[1]
        length = hypot(*vector)
        return None if length <= 1e-9 else (vector[0] / length, vector[1] / length)

    directions = [direction for boundary in external
                  if (direction := local_downstream(boundary)) is not None]
    if any(
        first[0] * second[0] + first[1] * second[1] < -0.25
        for index, first in enumerate(directions)
        for second in directions[index + 1:]
    ):
        logger.debug(
            "Wall-envelope selection failed: conflicting local downstream sectors=%s",
            directions,
        )
        raise ValueError("Unable to determine a unique Design wall envelope")
    selected = ExternalWallBoundary(tuple(external))
    logger.debug(
        "External wall boundary: semantic crest edges=%d upper components=%d",
        len(tuple(edge for edge in topology.boundary_edges if edge.kind == "crest")),
        len(selected.upper_components),
    )
    return selected


def _sample_external_boundary(
    boundary: ExternalWallBoundary,
    toe_lines,
    assessment_polygon,
    *,
    spacing_m: float,
    tangent_window_m: float,
):
    samples = []
    for component_index, component in enumerate(boundary.upper_components):
        try:
            component_samples = sample_wall_alignment(
                component.line,
                toe_lines,
                assessment_polygon,
                spacing_m=spacing_m,
                tangent_window_m=tangent_window_m,
                interior_points=component.interior_points,
            )
        except ValueError as error:
            logger.debug("Upper component %d has no samples: %s", component_index, error)
            continue
        for sample in component_samples:
            interval = _assessment_u_interval(sample, assessment_polygon)
            if interval is None or interval[1] - interval[0] <= 1e-6:
                logger.debug(
                    "Station skipped: component=%d chainage=%.3f "
                    "reason=local Assessment width below geometry tolerance",
                    component_index, sample.chainage_m,
                )
                continue
            samples.append(WallAlignmentSample(
                sample.chainage_m, sample.origin, sample.tangent_xy,
                sample.normal_xy, component_index,
            ))
    if not samples:
        raise ValueError("No design wall alignment samples fall inside the Assessment Area")
    return tuple(samples)


def _point_line_distance(point: SectionPoint, line) -> float:
    best = float("inf")
    for first, second in zip(line.points, line.points[1:]):
        dx, dy = second.x - first.x, second.y - first.y
        length_sq = dx * dx + dy * dy
        fraction = 0.0 if length_sq <= 1e-18 else max(
            0.0,
            min(1.0, ((point.x - first.x) * dx + (point.y - first.y) * dy) / length_sq),
        )
        x, y = first.x + fraction * dx, first.y + fraction * dy
        best = min(best, hypot(point.x - x, point.y - y))
    return best


def _external_toe_lines(profiles, toe_lines):
    observations = [
        profile.external_toe
        for profile in profiles
        if profile.external_toe is not None
    ]
    if not observations or not toe_lines:
        return ()
    counts = {line: 0 for line in toe_lines}
    for observation in observations:
        closest = min(toe_lines, key=lambda line: _point_line_distance(observation, line))
        counts[closest] += 1
    retained = tuple(line for line in toe_lines if counts[line] > 0)
    logger.debug(
        "External Lower Toe: retained components=%d observations=%s",
        len(retained), tuple(counts[line] for line in retained),
    )
    return retained


def build_transverse_profiles(
    design_surface: TriangleSurface,
    actual_surface: TriangleSurface,
    assessment_polygon: PlanPolygon,
    role_mapping: SurfaceRoleMapping,
    *,
    spacing_m: float = 3.0,
    tangent_window_m: float = 6.0,
) -> WallProfileSet:
    """Build design-derived transverse sections through design and actual meshes.

    The Assessment Area is only a spatial mask. Profile orientation comes from
    the local design crest tangent and therefore remains normal to the design
    wall even when the Assessment Area boundary has a different azimuth.
    """
    topology = extract_design_wall_topology(design_surface, role_mapping)
    toe_lines = tuple(line for line in topology.transitions if line.kind == "toe")
    alignment = _select_upper_envelope(
        topology,
        design_surface,
        assessment_polygon,
        role_mapping,
        toe_lines,
        spacing_m=spacing_m,
        tangent_window_m=tangent_window_m,
    )
    samples = _sample_external_boundary(
        alignment,
        toe_lines,
        assessment_polygon,
        spacing_m=spacing_m,
        tangent_window_m=tangent_window_m,
    )
    profiles = []
    for sample in samples:
        interval = _assessment_u_interval(sample, assessment_polygon)
        full_design_segments = intersect_surface_with_profile(
            design_surface, sample, role_mapping=role_mapping
        )
        external_toe, _ = _toe_near_area_exit(
            build_design_section(full_design_segments),
            None if interval is None else interval[1],
        )
        design_segments = _clip_segments_to_interval(
            full_design_segments,
            interval,
        )
        evaluated_section = build_design_section(design_segments)
        full_section = build_design_section(full_design_segments)
        design_section = type(evaluated_section)(
            evaluated_section.elements,
            full_section.upstream_context,
        )
        context_triangle_indices = (
            set(full_section.upstream_context.source_triangle_indices)
            if full_section.upstream_context is not None
            else set()
        )
        display_design_segments = tuple(sorted(
            (
                *(
                    segment for segment in full_design_segments
                    if segment.source_triangle_index in context_triangle_indices
                    and segment.u_min < 0.0
                    and segment.u_max <= 1e-7
                ),
                *design_segments,
            ),
            key=lambda segment: (segment.u_min, segment.u_max),
        ))
        actual_segments = _clip_segments_to_interval(
            intersect_surface_with_profile(actual_surface, sample),
            interval,
        )
        design_points = [
            point
            for element in design_section.elements
            for point in (element.start, element.end)
        ]
        if design_points:
            actual_segments = clip_section_segments_to_z_range(
                actual_segments,
                min(point.z for point in design_points),
                max(point.z for point in design_points),
            )
        else:
            actual_segments = ()
        profiles.append(TransverseProfile(
            alignment=sample,
            design_segments=display_design_segments,
            actual_segments=actual_segments,
            design_section=design_section,
            assessment_u_interval=interval,
            external_toe=external_toe,
        ))
    profiles = tuple(profiles)
    external_toes = _external_toe_lines(profiles, toe_lines)
    return WallProfileSet(
        crest_lines=alignment.upper_lines, toe_lines=external_toes, profiles=profiles,
        design_variants=build_design_variants(profiles),
    )
