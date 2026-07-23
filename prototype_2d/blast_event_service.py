"""Сервис создания и переимпорта взрывных событий."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from uuid import uuid4

from .blast_geometry import BlastGeometryError, build_contour_geometry, build_production_geometry
from .csv_importer import DatamineCsvError, import_datamine_csv
from .domain import AssessmentDomainState, BlastEvent, BlastEventGeometryRevision


class BlastEventValidationError(ValueError):
    """Данные карточки события неполные или не подходят для сохранения."""


class BlastEventService:
    def __init__(self, state: AssessmentDomainState):
        self.state = state

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

    @staticmethod
    def _add_imported_geometry(event: BlastEvent, csv_path: str | Path) -> BlastEventGeometryRevision:
        path = Path(csv_path)
        try:
            result = import_datamine_csv(path)
        except DatamineCsvError as exc:
            raise BlastEventValidationError(f"Не удалось импортировать CSV: {exc}") from exc
        if not result.lines:
            raise BlastEventValidationError("CSV не содержит подходящих линий")
        try:
            if event.event_type == "production":
                geometry = build_production_geometry(result.lines)
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
