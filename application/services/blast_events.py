"""Create Blast Events and import or reimport their geometry."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import median

from domain.entity_ids import generate_entity_id
from domain.geometry.blast import BlastGeometryError, build_contour_geometry, build_production_geometry
from infrastructure.datamine.dmfile import DatamineUnavailableError
from infrastructure.geometry_import.lines import import_line_geometry
from domain.blasting.entities import BlastEvent, BlastEventGeometryRevision
from application.state.assessment_domain_state import AssessmentDomainState


class BlastEventValidationError(ValueError):
    """The Blast Event data is incomplete or invalid for saving."""


@dataclass(frozen=True)
class BlastEventImportPreview:
    suggested_elevation: float
    geometry_type: str
    selected_source_line_id: str | None = None
    selected_line_representative_z: float | None = None
    production_closed_polygon_count: int = 0
    accepted_contour_drillhole_count: int = 0
    ignored_flat_contour_line_count: int = 0
    warning_text: str | None = None


class BlastEventService:
    def __init__(self, state: AssessmentDomainState):
        self.state = state
        self.last_import_warning: str | None = None

    def create_event(self, *, name: str, event_type: str, event_date: date | None,
                     elevation: float | None, csv_path: str | Path) -> BlastEvent:
        if not name.strip():
            raise BlastEventValidationError("Enter a blast event name")
        if event_type not in {"production", "contour"}:
            raise BlastEventValidationError("Select the blast event type: production or contour")
        if elevation is None:
            raise BlastEventValidationError("Enter the blast event horizon")
        display_type = "block" if event_type == "production" else "contour"
        event_id = generate_entity_id(display_type, [event.id for event in self.state.blast_events])
        event = BlastEvent(event_id, name.strip(), event_type, event_date, float(elevation))
        self._add_imported_geometry(event, csv_path)
        self.state.blast_events.append(event)
        return event

    def reimport_geometry(self, event: BlastEvent, csv_path: str | Path) -> BlastEventGeometryRevision:
        return self._add_imported_geometry(event, csv_path)

    def inspect_event_geometry(self, event_type: str, csv_path: str | Path) -> BlastEventImportPreview:
        """Inspect with exactly the same importer/builders used by final event import."""
        if event_type not in {"production", "contour"}:
            raise BlastEventValidationError("Select the blast event type: production or contour")
        path = Path(csv_path)
        try:
            result = import_line_geometry(path)
        except (ValueError, DatamineUnavailableError) as exc:
            raise BlastEventValidationError(f"Could not import geometry file: {exc}") from exc
        if not result.lines:
            message = ("Geometry file contains no valid contour drillholes" if event_type == "contour"
                       else "Geometry file contains no suitable lines")
            raise BlastEventValidationError(message)
        try:
            if event_type == "production":
                geometry = build_production_geometry(result.lines)
                return BlastEventImportPreview(
                    suggested_elevation=geometry.representative_elevation,
                    geometry_type="Polygon", selected_source_line_id=geometry.selected_source_line_id,
                    selected_line_representative_z=geometry.representative_elevation,
                    production_closed_polygon_count=geometry.closed_polygon_count,
                    warning_text=geometry.multiple_polygons_warning,
                )
            geometry = build_contour_geometry(result.lines)
            return BlastEventImportPreview(
                suggested_elevation=float(median(point.z for point in geometry.collar_points)),
                geometry_type="MultiPoint",
                accepted_contour_drillhole_count=geometry.accepted_drillhole_count,
                ignored_flat_contour_line_count=geometry.ignored_flat_line_count,
            )
        except BlastGeometryError as exc:
            raise BlastEventValidationError(str(exc)) from exc

    def _add_imported_geometry(self, event: BlastEvent, csv_path: str | Path) -> BlastEventGeometryRevision:
        self.last_import_warning = None
        path = Path(csv_path)
        try:
            result = import_line_geometry(path)
        except (ValueError, DatamineUnavailableError) as exc:
            raise BlastEventValidationError(f"Could not import geometry file: {exc}") from exc
        if not result.lines:
            message = ("Geometry file contains no valid contour drillholes" if event.event_type == "contour"
                       else "Geometry file contains no suitable lines")
            raise BlastEventValidationError(message)
        try:
            if event.event_type == "production":
                geometry = build_production_geometry(result.lines)
                self.last_import_warning = geometry.multiple_polygons_warning
                source_geometry = [geometry.source_line]
                plan_geometry, geometry_elevation = geometry.plan_geometry, geometry.elevation
            else:
                geometry = build_contour_geometry(result.lines)
                source_geometry = list(geometry.source_lines)
                plan_geometry = geometry.plan_geometry
                # The user sets the working horizon; collar elevations describe only the geometry.
                geometry_elevation = max(point.z for point in geometry.collar_points)
        except BlastGeometryError as exc:
            raise BlastEventValidationError(str(exc)) from exc
        return event.add_geometry_revision(
            source_file_name=path.name, source_geometry=source_geometry,
            plan_geometry=plan_geometry, elevation=geometry_elevation,
        )
