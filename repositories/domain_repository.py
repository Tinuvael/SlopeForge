from __future__ import annotations
from collections.abc import Callable
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload
from database.models import Domain, Site

class DomainRepository:
    def __init__(self, session_factory: Callable[[], Session]): self.session_factory = session_factory
    def list_domains(self, site_id: int | None = None) -> list[Domain]:
        with self.session_factory() as session:
            stmt = select(Domain).options(joinedload(Domain.site)).order_by(Domain.name, Domain.id)
            if site_id is not None: stmt = stmt.where(Domain.site_id == site_id)
            rows = list(session.scalars(stmt))
            for row in rows: session.expunge(row)
            return rows
    def get_domain(self, domain_id: int) -> Domain | None:
        with self.session_factory() as session:
            row = session.scalar(select(Domain).options(joinedload(Domain.site)).where(Domain.id == domain_id))
            if row: session.expunge(row)
            return row
    def create_domain(self, site_id: int, name: str, description: str | None = None) -> Domain:
        return self._save(None, site_id, name, description)
    def update_domain(self, domain_id: int, name: str,
                      description: str | None = None) -> Domain:
        with self.session_factory() as session:
            row = session.get(Domain, domain_id)
            if row is None: raise ValueError("Domain not found")
            if not name.strip(): raise ValueError("Domain name is required")
            row.name = name.strip(); row.description = description or None
            try: session.commit(); session.refresh(row); session.expunge(row); return row
            except Exception: session.rollback(); raise
    def _save(self, domain_id, site_id, name, description):
        if not name.strip(): raise ValueError("Domain name is required")
        with self.session_factory() as session:
            if session.get(Site, site_id) is None: raise ValueError("Site not found")
            row = Domain(site_id=site_id) if domain_id is None else session.get(Domain, domain_id)
            if row is None: raise ValueError("Domain not found")
            row.name=name.strip(); row.description=description or None; session.add(row)
            try: session.commit(); session.refresh(row); session.expunge(row); return row
            except Exception: session.rollback(); raise
