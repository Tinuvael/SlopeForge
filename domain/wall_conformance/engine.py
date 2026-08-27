from __future__ import annotations

from domain.geometry.surfaces import TriangleSurface
from domain.geometry.types import PlanPolygon
from domain.wall_conformance.design import (
    extract_design_wall_topology,
    sample_wall_alignment,
    select_design_alignment,
)
from domain.wall_conformance.models import (
    SurfaceRoleMapping,
    TransverseProfile,
    WallProfileSet,
)
from domain.wall_conformance.sections import intersect_surface_with_profile
from domain.wall_conformance.semantic_sections import build_design_section, build_design_variants


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
    alignment = select_design_alignment(topology, assessment_polygon)
    crest = alignment.line
    toe_lines = tuple(line for line in topology.transitions if line.kind == "toe")
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
    return WallProfileSet(
        crest_line=crest, toe_lines=toe_lines, profiles=profiles,
        design_variants=build_design_variants(profiles),
    )
