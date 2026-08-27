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
    UpperCrestStationEvaluation,
    WallAlignmentSample,
    WallProfileSet,
    WallTransitionLine,
)
from domain.wall_conformance.sections import (
    clip_section_segments_to_z_range,
    connected_section_segments,
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


def evaluate_upper_crest_station(
    sample: WallAlignmentSample,
    design_surface: TriangleSurface,
    assessment_polygon: PlanPolygon,
    role_mapping: SurfaceRoleMapping,
    toe_lines,
) -> UpperCrestStationEvaluation:
    """Validate one candidate origin using only its local wall geometry."""
    interval = _assessment_u_interval(sample, assessment_polygon)
    if interval is None:
        return UpperCrestStationEvaluation(False, "no local Assessment interval")
    width = interval[1] - interval[0]
    if width <= 1e-6 or interval[1] <= 1e-6:
        return UpperCrestStationEvaluation(False, "local Assessment width below tolerance")

    full_segments = intersect_surface_with_profile(
        design_surface, sample, role_mapping=role_mapping
    )
    local_segments = connected_section_segments(
        full_segments,
        SectionPoint(0.0, sample.origin.z, sample.origin.x, sample.origin.y),
    )
    if not local_segments:
        return UpperCrestStationEvaluation(
            False, "no Design geometry incident to sampled crest", interval
        )

    # Only connected Face geometry that lies inside the evaluated Assessment
    # interval can make this an internal crest. A farther upstream bench beyond
    # the Area, or a same-U/different-Z folded intersection, is irrelevant.
    if any(
        segment.semantic_role == "face"
        and segment.u_max < -1e-6
        and segment.u_max >= interval[0] - 1e-6
        for segment in local_segments
    ):
        return UpperCrestStationEvaluation(
            False, "connected evaluated Face exists upstream", interval
        )

    section = build_design_section(local_segments)
    first = next(
        (element for element in section.elements if element.horizontal_width > 1e-6),
        None,
    )
    if first is None or first.role != "face" or first.start.u > 1e-5:
        return UpperCrestStationEvaluation(False, "no adjacent downstream Design Face", interval)

    external_toe, _ = _toe_near_area_exit(section, interval[1])
    return UpperCrestStationEvaluation(
        True, "valid local wall section", interval, external_toe, full_segments
    )


def _crest_subline(line, start_chainage: float, end_chainage: float):
    """Return source-polyline geometry between confirmed sample chainages."""
    cumulative = [0.0]
    for first, second in zip(line.points, line.points[1:]):
        cumulative.append(cumulative[-1] + hypot(second.x - first.x, second.y - first.y))

    def interpolate(chainage):
        for index, (start, end) in enumerate(zip(cumulative, cumulative[1:])):
            if chainage <= end + 1e-9:
                span = end - start
                fraction = 0.0 if span <= 1e-12 else (chainage - start) / span
                first, second = line.points[index], line.points[index + 1]
                return SurfaceVertex(
                    first.x + (second.x - first.x) * fraction,
                    first.y + (second.y - first.y) * fraction,
                    first.z + (second.z - first.z) * fraction,
                ), index
        return line.points[-1], len(line.points) - 2

    first, first_index = interpolate(start_chainage)
    last, last_index = interpolate(end_chainage)
    if abs(end_chainage - start_chainage) <= 1e-9:
        return WallTransitionLine(
            "crest", (line.points[first_index], line.points[first_index + 1])
        )
    middle = tuple(line.points[index] for index in range(first_index + 1, last_index + 1))
    points = (first, *middle, last)
    deduplicated = tuple(
        point for index, point in enumerate(points)
        if index == 0 or point != points[index - 1]
    )
    return WallTransitionLine("crest", deduplicated)


def _collect_external_upper_stations(
    topology,
    design_surface,
    assessment_polygon,
    role_mapping,
    toe_lines,
    *,
    spacing_m,
    tangent_window_m,
):
    confirmed = []
    accepted = []
    candidates = tuple(
        boundary for boundary in topology.alignment_boundaries
        if transition_length_in_area(boundary.line, assessment_polygon) > 1e-9
    )
    for candidate_index, component in enumerate(candidates):
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
            logger.debug("Upper component %d has no samples: %s", candidate_index, error)
            continue
        evaluated = []
        for sample in component_samples:
            evaluation = evaluate_upper_crest_station(
                sample,
                design_surface,
                assessment_polygon,
                role_mapping,
                toe_lines,
            )
            evaluated.append((sample, evaluation))
            if not evaluation.valid:
                logger.debug(
                    "Upper station skipped: origin=(%.3f, %.3f, %.3f) "
                    "chainage=%.3f reason=%s",
                    sample.origin.x, sample.origin.y, sample.origin.z,
                    sample.chainage_m, evaluation.reason,
                )
                continue
        valid_stations = [item for item in evaluated if item[1].valid]
        if not valid_stations:
            continue
        component_index = len(confirmed)
        valid_chainages = {sample.chainage_m for sample, _ in valid_stations}
        if len(valid_stations) == len(evaluated):
            confirmed.append(component)
        else:
            # Display only source-geometry spans supported by neighboring valid
            # stations. Rejected samples split the confirmed Plan geometry.
            runs = []
            current = []
            for sample, _evaluation in evaluated:
                if sample.chainage_m in valid_chainages:
                    current.append(sample)
                elif current:
                    runs.append(current)
                    current = []
            if current:
                runs.append(current)
            for run in runs:
                confirmed.append(DesignAlignmentBoundary(
                    _crest_subline(
                        component.line, run[0].chainage_m, run[-1].chainage_m
                    ),
                    component.face_patch_index,
                    (),
                    component.source,
                ))
        accepted.extend((WallAlignmentSample(
            sample.chainage_m, sample.origin, sample.tangent_xy,
            sample.normal_xy, component_index,
        ), evaluation) for sample, evaluation in valid_stations)
    if not accepted:
        raise ValueError("No design wall alignment samples fall inside the Assessment Area")
    logger.debug(
        "External wall boundary: semantic crest edges=%d accepted components=%d "
        "profiles=%d",
        len(tuple(edge for edge in topology.boundary_edges if edge.kind == "crest")),
        len(confirmed), len(accepted),
    )
    return ExternalWallBoundary(tuple(confirmed)), tuple(accepted)


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
    alignment, stations = _collect_external_upper_stations(
        topology,
        design_surface,
        assessment_polygon,
        role_mapping,
        toe_lines,
        spacing_m=spacing_m,
        tangent_window_m=tangent_window_m,
    )
    profiles = []
    for sample, evaluation in stations:
        interval = evaluation.assessment_u_interval
        full_design_segments = evaluation.full_design_segments
        external_toe = evaluation.external_toe
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
