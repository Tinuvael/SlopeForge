from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from domain.geometry.types import PlanPolygon
from domain.wall_conformance import (
    PROTOTYPE_DESIGN_ROLE_MAPPING,
    ProfileSectionAssemblyError,
    ProfileSectionDiagnostic,
    SurfaceRoleMapping,
    WallProfileSet,
    build_v2_profile_sections,
    semantic_value_token,
)


class WallConformanceUnavailableError(RuntimeError):
    pass


@dataclass(frozen=True)
class WallConformanceDiagnosticSettings:
    spacing_m: float = 3.0


@dataclass(frozen=True)
class WallConformanceDiagnosticResult:
    design_dataset: Any
    actual_dataset: Any
    profile_set: WallProfileSet
    settings: WallConformanceDiagnosticSettings
    role_mapping: SurfaceRoleMapping
    mapping_is_fallback: bool
    diagnostics: tuple[ProfileSectionDiagnostic, ...] = ()


@dataclass(frozen=True)
class SurfaceAttributeValueCount:
    value: object
    triangle_count: int


@dataclass(frozen=True)
class DesignSemanticInspection:
    dataset: Any
    attribute_values: dict[str, tuple[SurfaceAttributeValueCount, ...]]
    mapping: SurfaceRoleMapping
    is_fallback: bool


class WallConformanceDiagnosticService:
    """Orchestrate diagnostic geometry and Design-revision semantics.

    It persists only source-semantic metadata. Diagnostic results remain
    read-only and deterministic geometry stays in ``domain.wall_conformance``.
    """

    def __init__(self, surface_service):
        self.surface_service = surface_service

    def current_datasets(self, site_id: int) -> tuple[Any | None, Any | None]:
        return (
            self.surface_service.current(site_id, "design"),
            self.surface_service.current(site_id, "actual"),
        )

    @staticmethod
    def mapping_for_dataset(dataset) -> tuple[SurfaceRoleMapping, bool]:
        payload = getattr(dataset, "semantic_mapping_json", None)
        if payload:
            return SurfaceRoleMapping.from_dict(payload), False
        return PROTOTYPE_DESIGN_ROLE_MAPPING, True

    def inspect_design_semantics(self, site_id: int) -> DesignSemanticInspection:
        loaded = self.surface_service.load_current(site_id, "design")
        if loaded is None:
            raise WallConformanceUnavailableError(
                "No active Design surface is configured for this Project."
            )
        dataset, imported = loaded
        surface = getattr(imported, "surface", None)
        if surface is None:
            raise WallConformanceUnavailableError(
                "The active Design surface does not contain triangulated geometry."
            )
        attribute_names = sorted({
            str(key)
            for triangle in surface.triangles
            for key in triangle.source_attributes
        })
        counts: dict[str, dict[str, list[object]]] = {name: {} for name in attribute_names}
        for triangle in surface.triangles:
            attributes = {str(key): value for key, value in triangle.source_attributes.items()}
            for name in attribute_names:
                value = attributes.get(name, "<missing>")
                token = semantic_value_token(value)
                entry = counts.setdefault(name, {}).setdefault(token, [value, 0])
                entry[1] = int(entry[1]) + 1
        values = {
            name: tuple(
                SurfaceAttributeValueCount(item[0], int(item[1]))
                for _, item in sorted(grouped.items())
            )
            for name, grouped in sorted(counts.items())
        }
        mapping, fallback = self.mapping_for_dataset(dataset)
        return DesignSemanticInspection(dataset, values, mapping, fallback)

    def save_design_semantics(
        self, site_id: int, logical_id: str, mapping: SurfaceRoleMapping
    ):
        if not any(role == "face" for _, role in mapping.assignments):
            raise ValueError("Map at least one source value to Face before saving.")
        return self.surface_service.save_design_semantic_mapping(
            site_id, logical_id, mapping
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

        role_mapping, mapping_is_fallback = self.mapping_for_dataset(design_dataset)
        try:
            assembly_result = build_v2_profile_sections(
                design_surface,
                actual_surface,
                assessment_polygon,
                role_mapping,
                requested_spacing_m=settings.spacing_m,
            )
        except ProfileSectionAssemblyError as exc:
            raise WallConformanceUnavailableError(
                "No usable Design wall profiles could be assembled for this "
                "Assessment Area. Check the Assessment Area coverage and Design "
                "surface semantics."
            ) from exc
        return WallConformanceDiagnosticResult(
            design_dataset=design_dataset,
            actual_dataset=actual_dataset,
            profile_set=assembly_result.profile_set,
            settings=settings,
            role_mapping=role_mapping,
            mapping_is_fallback=mapping_is_fallback,
            diagnostics=assembly_result.diagnostics,
        )
