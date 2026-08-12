"""Atomic persistence API for the one current Domain Geometry record."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Sequence
from sqlalchemy.orm import Session
from database.models import Domain, DomainGeometry
from domain.geometry.types import PlanPolygon
from domain.geometry.operations import validate_simple_polygon
from infrastructure.db.domain_version import guard_domain_versions


@dataclass(frozen=True)
class StoredDomainGeometry:
    domain_id: int
    polygons: tuple[PlanPolygon, ...]
    source_kind: str
    source_file_name: str | None
    domain_version: int


class DomainGeometryRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @staticmethod
    def _detached(row: DomainGeometry | None) -> StoredDomainGeometry | None:
        if row is None:
            return None
        return StoredDomainGeometry(row.domain_id, tuple(PlanPolygon.from_dict(p) for p in row.polygons_json), row.source_kind, row.source_file_name, row.domain.version)

    def get_domain_version(self, domain_id: int) -> int:
        with self._session_factory() as session:
            domain = session.get(Domain, domain_id)
            if domain is None: raise LookupError(f"Domain {domain_id} not found")
            return domain.version

    def get_for_domain(self, domain_id: int) -> StoredDomainGeometry | None:
        with self._session_factory() as session:
            return self._detached(session.query(DomainGeometry).filter_by(domain_id=domain_id).one_or_none())

    def _replace(self, domain_id: int, expected_version: int, polygons: Sequence[PlanPolygon], kind: str, filename: str | None) -> StoredDomainGeometry:
        if not polygons:
            raise ValueError("Domain Geometry requires at least one polygon")
        for polygon in polygons:
            validate_simple_polygon(polygon)
        with self._session_factory.begin() as session:
            guard_domain_versions(session, {domain_id: expected_version})
            row = session.query(DomainGeometry).filter_by(domain_id=domain_id).one_or_none()
            if row is None:
                row = DomainGeometry(domain_id=domain_id)
                session.add(row)
            row.polygons_json = [polygon.to_dict() for polygon in polygons]
            row.source_kind, row.source_file_name = kind, filename
            session.flush()
            return self._detached(row)

    def replace_imported(self, domain_id: int, expected_version: int, polygons: Sequence[PlanPolygon], source_file_name: str) -> StoredDomainGeometry:
        return self._replace(domain_id, expected_version, polygons, "imported", source_file_name)

    def replace_drawn(self, domain_id: int, expected_version: int, polygons: Sequence[PlanPolygon]) -> StoredDomainGeometry:
        return self._replace(domain_id, expected_version, polygons, "drawn", None)

    def clear(self, domain_id: int, expected_version: int) -> int:
        with self._session_factory.begin() as session:
            new_version = guard_domain_versions(session, {domain_id: expected_version})[domain_id]
            row = session.query(DomainGeometry).filter_by(domain_id=domain_id).one_or_none()
            if row is not None:
                session.delete(row)
            return new_version
