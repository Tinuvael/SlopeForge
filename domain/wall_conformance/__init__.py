"""Pure geometry primitives for design-vs-actual wall conformance."""

from .design import (
    extract_design_transition_lines,
    sample_wall_alignment,
    select_primary_crest_line,
)
from .engine import build_transverse_profiles
from .models import (
    SectionPoint,
    SectionSegment,
    SurfaceRoleMapping,
    TransverseProfile,
    WallAlignmentSample,
    WallProfileSet,
    WallTransitionLine,
)
from .sections import intersect_surface_with_profile

__all__ = [
    "SectionPoint",
    "SectionSegment",
    "SurfaceRoleMapping",
    "TransverseProfile",
    "WallAlignmentSample",
    "WallProfileSet",
    "WallTransitionLine",
    "build_transverse_profiles",
    "extract_design_transition_lines",
    "intersect_surface_with_profile",
    "sample_wall_alignment",
    "select_primary_crest_line",
]
