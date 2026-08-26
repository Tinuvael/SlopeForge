from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.geometry.types import PlanPolygon
from domain.wall_conformance import (
    SurfaceRoleMapping,
    WallProfileSet,
    build_transverse_profiles,
)


class WallConformanceUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class WallConformanceDiagnosticSettings:
    spacing_m: float = 3.0
    tangent_window_m: float = 6.0
    half_width_m: float = 12.0
    role_attribute: str = "COLOUR"
    face_value: object = 2
    berm_value: object = 5
    road_value: object = 3

    def role_mapping(self) -> SurfaceRoleMapping:
        return SurfaceRoleMapping(
            self.role_attribute,
            (
                (self.face_value, "face"),
                (self.berm_value, "berm"),
                (self.road_value, "road"),
            ),
        )


@dataclass(frozen=True)
class WallConformanceDiagnosticResult:
    design_dataset: Any
    actual_dataset: Any
    profile_set: WallProfileSet
    settings: WallConformanceDiagnosticSettings


class WallConformanceDiagnosticService:
    """Read-only orchestration for the first wall-conformance inspection UI.

    This service intentionally performs no persistence and no factual feature
    recognition. It loads the active Project design/actual surfaces and delegates
    deterministic geometry to ``domain.wall_conformance``.
    """

    def __init__(self, surface_service):
        self.surface_service = surface_service

    def current_datasets(self, site_id: int) -> tuple[Any | None, Any | None]:
        return (
            self.surface_service.current(site_id, "design"),
            self.surface_service.current(site_id, "actual"),
        )

    def calculate_current(
        self,
        site_id: int,
        assessment_polygon: PlanPolygon,
        settings: WallConformanceDiagnosticSettings | None = None,
    ) -> WallConformanceDiagnosticResult:
        settings = settings or WallConformanceDiagnosticSettings()
        design_dataset, actual_dataset = self.current_datasets(site_id)
        if design_dataset is None:
            raise WallConformanceUnavailableError(
                "No active Design surface is configured for this Project."
            )
        if actual_dataset is None:
            raise WallConformanceUnavailableError(
                "No active Actual survey is configured for this Project."
            )
        if not bool(getattr(self.surface_service, "storage_available", True)):
            raise WallConformanceUnavailableError(
                "Shared file storage is unavailable for this connection. "
                "Surface metadata can be viewed, but wall conformance cannot be calculated."
            )

        _, design_import = self.surface_service.load_dataset(
            site_id, design_dataset.logical_id
        )
        _, actual_import = self.surface_service.load_dataset(
            site_id, actual_dataset.logical_id
        )
        design_surface = getattr(design_import, "surface", None)
        actual_surface = getattr(actual_import, "surface", None)
        if design_surface is None or actual_surface is None:
            raise WallConformanceUnavailableError(
                "The active Project surface datasets do not contain triangulated geometry."
            )

        profile_set = build_transverse_profiles(
            design_surface,
            actual_surface,
            assessment_polygon,
            settings.role_mapping(),
            spacing_m=settings.spacing_m,
            tangent_window_m=settings.tangent_window_m,
            half_width_m=settings.half_width_m,
        )
        return WallConformanceDiagnosticResult(
            design_dataset=design_dataset,
            actual_dataset=actual_dataset,
            profile_set=profile_set,
            settings=settings,
        )
