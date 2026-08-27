from __future__ import annotations

import logging
from math import hypot

from domain.geometry.operations import point_in_polygon
from domain.geometry.surfaces import TriangleSurface
from domain.geometry.types import PlanPoint, PlanPolygon
from domain.wall_conformance.design import (
    extract_design_wall_topology,
    sample_wall_alignment,
    transition_length_in_area,
)
from domain.wall_conformance.models import (
    DesignAlignmentBoundary,
    SectionPoint,
    SectionSegment,
    SurfaceRoleMapping,
    TransverseProfile,
    WallProfileSet,
)
from domain.wall_conformance.sections import intersect_surface_with_profile
from domain.wall_conformance.semantic_sections import build_design_section, build_design_variants


logger = logging.getLogger(__name__)


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


def _downstream_area_exit_u(sample, area: PlanPolygon) -> float | None:
    """Return the first downstream exit of the Assessment polygon.

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
        if ray_u >= -1e-8 and -1e-8 <= edge_fraction <= 1.0 + 1e-8:
            intersections.append(max(0.0, ray_u))
    ordered = []
    for value in sorted(intersections):
        if not ordered or abs(value - ordered[-1]) > 1e-7:
            ordered.append(value)
    if not ordered:
        return None
    bounds = [0.0, *ordered]
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
            return end
    return None


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
) -> DesignAlignmentBoundary:
    candidates = [
        boundary
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
    viable = [item for item in diagnostics if -item[1] > 0.0]
    if not viable:
        logger.debug("Wall-envelope selection failed: no valid downstream probes")
        raise ValueError("Unable to determine a unique Design wall envelope")
    viable.sort(
        key=lambda item: (
            *item[:3],
            tuple((point.x, point.y, point.z) for point in item[3].line.points),
        )
    )
    best = viable[0]
    equally_external = [item for item in viable if item[:3] == best[:3]]
    independent_patches = {item[3].face_patch_index for item in equally_external}
    if len(independent_patches) > 1:
        logger.debug(
            "Wall-envelope selection failed: equally external Face patches=%s",
            sorted(independent_patches),
        )
        raise ValueError("Unable to determine a unique Design wall envelope")
    selected = best[3]
    logger.debug(
        "Selected Upper Crest: source=%s face_patch=%d terminal_toes=%d",
        selected.source,
        selected.face_patch_index,
        len(best[4]),
    )
    return selected


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
        terminal
        for profile in profiles
        if profile.design_section is not None
        if (terminal := _terminal_toe(profile.design_section)) is not None
    ]
    if not observations or not toe_lines:
        return ()
    counts = {line: 0 for line in toe_lines}
    for observation in observations:
        closest = min(toe_lines, key=lambda line: _point_line_distance(observation, line))
        counts[closest] += 1
    maximum = max(counts.values())
    return tuple(line for line in toe_lines if counts[line] == maximum and maximum > 0)


def build_transverse_profiles(
    design_surface: TriangleSurface,
    actual_surface: TriangleSurface,
    assessment_polygon: PlanPolygon,
    role_mapping: SurfaceRoleMapping,
    *,
    spacing_m: float = 3.0,
    tangent_window_m: float = 6.0,
    half_width_m: float | None = None,
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
    crest = alignment.line
    samples = sample_wall_alignment(
        crest,
        toe_lines,
        assessment_polygon,
        spacing_m=spacing_m,
        tangent_window_m=tangent_window_m,
        interior_points=alignment.interior_points,
    )
    profiles = []
    for sample in samples:
        design_segments = intersect_surface_with_profile(
            design_surface, sample, role_mapping=role_mapping, half_width_m=half_width_m,
        )
        profiles.append(TransverseProfile(
            alignment=sample,
            design_segments=design_segments,
            actual_segments=intersect_surface_with_profile(
                actual_surface, sample, half_width_m=half_width_m,
            ),
            design_section=build_design_section(design_segments),
        ))
    profiles = tuple(profiles)
    external_toes = _external_toe_lines(profiles, toe_lines)
    return WallProfileSet(
        crest_line=crest, toe_lines=external_toes, profiles=profiles,
        design_variants=build_design_variants(profiles),
    )
