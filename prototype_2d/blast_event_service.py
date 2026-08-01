"""Сервис создания и переимпорта взрывных событий."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from statistics import median
from uuid import uuid4

from .blast_geometry import BlastGeometryError, build_contour_geometry, build_production_geometry
from .csv_importer import DatamineCsvError, import_datamine_csv
from .domain import AssessmentDomainState, BlastEvent, BlastEventGeometryRevision


class BlastEventValidationError(ValueError):
    """Данные карточки события неполные или не подходят для сохранения."""


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
            raise BlastEventValidationError("Укажите название события")
        if event_type not in {"production", "contour"}:
            raise BlastEventValidationError("Выберите тип события: production или contour")
        if elevation is None:
            raise BlastEventValidationError("Укажите горизонт события")
        event = BlastEvent(f"BE-{uuid4().hex[:8].upper()}", name.strip(), event_type, event_date, float(elevation))
        self._add_imported_geometry(event, csv_path)
        self.state.blast_events.append(event)
        return event

    def reimport_geometry(self, event: BlastEvent, csv_path: str | Path) -> BlastEventGeometryRevision:
        return self._add_imported_geometry(event, csv_path)

    def inspect_event_geometry(self, event_type: str, csv_path: str | Path) -> BlastEventImportPreview:
        """Inspect with exactly the same importer/builders used by final event import."""
        if event_type not in {"production", "contour"}:
            raise BlastEventValidationError("Выберите тип события: production или contour")
        path = Path(csv_path)
        try:
            result = import_datamine_csv(path)
        except DatamineCsvError as exc:
            raise BlastEventValidationError(f"Не удалось импортировать CSV: {exc}") from exc
        if not result.lines:
            message = ("CSV не содержит валидных контурных скважин" if event_type == "contour"
                       else "CSV не содержит подходящих линий")
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
            result = import_datamine_csv(path)
        except DatamineCsvError as exc:
            raise BlastEventValidationError(f"Не удалось импортировать CSV: {exc}") from exc
        if not result.lines:
            message = ("CSV не содержит валидных контурных скважин" if event.event_type == "contour"
                       else "CSV не содержит подходящих линий")
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
                # Рабочий горизонт задаётся пользователем; отметки устьев — только свойство геометрии.
                geometry_elevation = max(point.z for point in geometry.collar_points)
        except BlastGeometryError as exc:
            raise BlastEventValidationError(str(exc)) from exc
        return event.add_geometry_revision(
            source_file_name=path.name, source_geometry=source_geometry,
            plan_geometry=plan_geometry, elevation=geometry_elevation,
        )
