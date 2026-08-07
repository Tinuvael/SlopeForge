"""Persistence operations for Site-owned geotechnical Domains."""
from __future__ import annotations

from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from database.models import Domain, Site


class DomainNotFoundError(LookupError):
    pass


class DomainRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def list_for_site(self, site_id: int) -> list[Domain]:
        with self._session_factory() as session:
            return list(session.scalars(
                select(Domain).where(Domain.site_id == site_id).order_by(Domain.name, Domain.id)
                .options(joinedload(Domain.site))
            ).unique())

    def get(self, domain_id: int) -> Domain | None:
        with self._session_factory() as session:
            return session.scalar(select(Domain).where(Domain.id == domain_id).options(joinedload(Domain.site)))

    def create(self, site_id: int, name: str, description: str | None = None) -> Domain:
        with self._session_factory.begin() as session:
            if session.get(Site, site_id) is None:
                raise ValueError(f"Site {site_id} does not exist")
            row = Domain(site_id=site_id, name=name.strip(), description=description or None)
            session.add(row)
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row

    def update(self, domain_id: int, name: str, description: str | None = None) -> Domain:
        with self._session_factory.begin() as session:
            row = session.get(Domain, domain_id)
            if row is None:
                raise DomainNotFoundError(f"Domain {domain_id} does not exist")
            # site_id is deliberately not accepted: an existing Domain cannot move.
            row.name = name.strip()
            row.description = description or None
            session.flush()
            session.refresh(row)
            session.expunge(row)
            return row
