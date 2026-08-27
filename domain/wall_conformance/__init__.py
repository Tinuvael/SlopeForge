"""Pure geometry primitives for design-vs-actual wall conformance."""

from .design import (
    extract_design_transition_lines,
    sample_wall_alignment,
    select_primary_crest_line,
)
from .engine import build_transverse_profiles
from .models import (
    PROTOTYPE_DESIGN_ROLE_MAPPING,
    SectionPoint,
    SectionSegment,
    SurfaceRoleMapping,
    TransverseProfile,
    WallAlignmentSample,
    WallProfileSet,
    WallTransitionLine,
    semantic_value_token,
)
from .sections import intersect_surface_with_profile
from .semantic_sections import build_design_section, build_design_variants

__all__ = [
    "SectionPoint",
    "SectionSegment",
    "SurfaceRoleMapping",
    "PROTOTYPE_DESIGN_ROLE_MAPPING",
    "TransverseProfile",
    "WallAlignmentSample",
    "WallProfileSet",
    "WallTransitionLine",
    "build_transverse_profiles",
    "extract_design_transition_lines",
    "intersect_surface_with_profile",
    "sample_wall_alignment",
    "select_primary_crest_line",
    "semantic_value_token",
    "build_design_section",
    "build_design_variants",
]
