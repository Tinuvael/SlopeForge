"""Domain CRUD integration tests; destructive only on explicitly named test DB."""
import os
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

URL = os.getenv("SLOPEFORGE_TEST_DATABASE_URL") or os.getenv("TEST_DATABASE_URL")
if not URL:
    pytest.skip("No PostgreSQL test URL; Domain repository integration tests skipped", allow_module_level=True)
if "test" not in (make_url(URL).database or "").lower():
    pytest.fail("Refusing Domain tests: PostgreSQL database name must contain 'test'", pytrace=False)

from database.models import Domain, Mine, Site
from repositories.domain_repository import DomainRepository


def test_domain_create_list_update_uniqueness_and_immutable_site():
    engine = create_engine(URL); Session = sessionmaker(engine, expire_on_commit=False)
    suffix = uuid.uuid4().hex
    with Session.begin() as session:
        mine = Mine(name=f"Domain test {suffix}"); session.add(mine); session.flush()
        a = Site(mine_id=mine.id, name=f"A {suffix}"); b = Site(mine_id=mine.id, name=f"B {suffix}")
        session.add_all([a, b]); session.flush(); mine_id, site_a, site_b = mine.id, a.id, b.id
    repo = DomainRepository(Session)
    north = repo.create_domain(site_a, "North", "initial")
    assert [row.id for row in repo.list_domains(site_a)] == [north.id]
    renamed = repo.update_domain(north.id, "North renamed", "updated")
    assert (renamed.site_id, renamed.name, renamed.description) == (site_a, "North renamed", "updated")
    repo.create_domain(site_b, "North renamed", None)  # same name in another Site is valid
    with pytest.raises(IntegrityError): repo.create_domain(site_a, "North renamed", None)
    # update_domain has no site argument: an existing Domain cannot silently move.
    with pytest.raises(TypeError): repo.update_domain(north.id, site_b, "moved", None)
    with Session.begin() as session:
        session.query(Domain).filter(Domain.site_id.in_([site_a, site_b])).delete(synchronize_session=False)
        session.query(Site).filter(Site.id.in_([site_a, site_b])).delete(synchronize_session=False)
        session.query(Mine).filter_by(id=mine_id).delete()
    engine.dispose()
