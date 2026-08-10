"""Explicit Site-scoped operations for shared Project Lines history."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from database import assessment_models as orm
from database.models import Site
from domain.project.project_lines import ProjectLinesDataset


class ProjectLinesDatasetNotFoundError(LookupError):
    pass


class ProjectLinesRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def list_for_site(self, site_id: int) -> list[orm.ProjectLinesDataset]:
        with self._session_factory() as session:
            return list(session.scalars(select(orm.ProjectLinesDataset).where(
                orm.ProjectLinesDataset.site_id == site_id
            ).order_by(orm.ProjectLinesDataset.imported_at, orm.ProjectLinesDataset.id)))

    def add_dataset(self, site_id: int, dataset: ProjectLinesDataset) -> orm.ProjectLinesDataset:
        return self.import_dataset(site_id, dataset, make_active=False)

    def import_dataset(self, site_id: int, dataset: ProjectLinesDataset,
                       *, make_active: bool = True) -> orm.ProjectLinesDataset:
        """Insert and optionally activate a Dataset in one transaction."""
        with self._session_factory.begin() as session:
            # Serialize ID allocation per Site.  Dashboard imports are built from
            # a fresh domain state and may initially propose D-001 every time.
            site = session.scalar(select(Site).where(Site.id == site_id).with_for_update())
            if site is None:
                raise ValueError(f"Site {site_id} does not exist")
            dataset.id = self._available_domain_id(session, site_id, dataset.id)
            row = orm.ProjectLinesDataset(site_id=site_id, domain_id=dataset.id, name=dataset.name,
                imported_at=dataset.imported_at, source_file_name=dataset.source_file_name,
                is_active=False, is_archived=False,
                lines_json=[line.to_dict() for line in dataset.lines])
            session.add(row)
            session.flush()
            if make_active:
                self._activate_imported_dataset(session, site_id, row)
                session.flush()
            row_id = row.id
        return self._get_row(row_id)

    @staticmethod
    def _available_domain_id(session: Session, site_id: int, proposed_id: str) -> str:
        used = set(session.scalars(select(orm.ProjectLinesDataset.domain_id).where(
            orm.ProjectLinesDataset.site_id == site_id
        )))
        if proposed_id not in used:
            return proposed_id
        number = 1
        while f"D-{number:03d}" in used:
            number += 1
        return f"D-{number:03d}"

    @staticmethod
    def _activate_imported_dataset(session: Session, site_id: int,
                                   row: orm.ProjectLinesDataset) -> None:
        session.execute(update(orm.ProjectLinesDataset).where(
            orm.ProjectLinesDataset.site_id == site_id,
            orm.ProjectLinesDataset.id != row.id,
        ).values(is_active=False))
        row.is_active = True

    def set_active(self, site_id: int, dataset_domain_id: str | None) -> None:
        with self._session_factory.begin() as session:
            target = None
            if dataset_domain_id is not None:
                target = session.scalar(select(orm.ProjectLinesDataset).where(
                    orm.ProjectLinesDataset.site_id == site_id,
                    orm.ProjectLinesDataset.domain_id == dataset_domain_id))
                if target is None:
                    raise ProjectLinesDatasetNotFoundError(dataset_domain_id)
                if target.is_archived:
                    raise ValueError("Archived Project Lines dataset cannot be active")
            session.execute(update(orm.ProjectLinesDataset).where(
                orm.ProjectLinesDataset.site_id == site_id
            ).values(is_active=False))
            if target is not None:
                target.is_active = True

    def get_active(self, site_id: int) -> orm.ProjectLinesDataset | None:
        with self._session_factory() as session:
            return session.scalar(select(orm.ProjectLinesDataset).where(
                orm.ProjectLinesDataset.site_id == site_id,
                orm.ProjectLinesDataset.is_active.is_(True)))

    def archive(self, site_id: int, dataset_domain_id: str) -> None:
        with self._session_factory.begin() as session:
            row = self._find(session, site_id, dataset_domain_id)
            row.is_active = False
            row.is_archived = True
            row.archived_at = datetime.now(timezone.utc)

    def restore(self, site_id: int, dataset_domain_id: str) -> None:
        with self._session_factory.begin() as session:
            row = self._find(session, site_id, dataset_domain_id)
            row.is_archived = False
            row.archived_at = None

    @staticmethod
    def _find(session: Session, site_id: int, dataset_domain_id: str):
        row = session.scalar(select(orm.ProjectLinesDataset).where(
            orm.ProjectLinesDataset.site_id == site_id,
            orm.ProjectLinesDataset.domain_id == dataset_domain_id))
        if row is None:
            raise ProjectLinesDatasetNotFoundError(dataset_domain_id)
        return row

    def _get_row(self, row_id: int):
        with self._session_factory() as session:
            return session.get(orm.ProjectLinesDataset, row_id)
