from __future__ import annotations
import os
from datetime import date
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from application.dto.current_user import CurrentUser
from database.assessment_models import BlastEvent
from database.models import AuditLogEntry, Domain, Site, User
from repositories.audit_log_repository import AuditLogRepository
from repositories.production_blast_repository import ProductionBlastRepository
from repositories.domain_repository import DomainRepository
from infrastructure.services.production_blast_service import (
    PermissionDenied, ProductionBlastInput, ProductionBlastService,
)

URL=os.getenv("TEST_DATABASE_URL")
if not URL: pytest.skip("TEST_DATABASE_URL is not set",allow_module_level=True)
if "test" not in (make_url(URL).database or "").lower(): pytest.fail("Refusing audit tests outside a test database",pytrace=False)

class FailingAuditLogRepository(AuditLogRepository):
    def add_entry(self,*args,**kwargs): raise RuntimeError("audit failed")

@pytest.fixture(scope="module")
def factory(tmp_path_factory):
    from alembic import command
    from alembic.config import Config
    os.environ["DATABASE_URL"]=URL; os.environ["STORAGE_ROOT"]=str(tmp_path_factory.mktemp("audit-storage"))
    command.upgrade(Config("alembic.ini"),"head")
    engine=create_engine(URL); yield sessionmaker(engine,expire_on_commit=False); engine.dispose()

@pytest.fixture
def context(factory):
    with factory.begin() as session:
        user=User(username="audit-admin",password_hash="hash",full_name="Admin User",role="admin",is_active=True)
        site=Site(name="Audit Project");session.add_all((user,site));session.flush()
        domain=Domain(site_id=site.id,name="North");session.add(domain);session.flush()
        event=BlastEvent(domain_id=domain.id,logical_id="BE-B-001",name="B-001",
            event_type="production",event_date=date.today(),elevation_m=760,
            created_by_user_id=user.id)
        session.add(event);session.flush(); ids=(user.id,site.id,domain.id,event.logical_id)
    yield ids

def service(factory,audit=None):
    return ProductionBlastService(ProductionBlastRepository(factory),DomainRepository(factory),audit)

def user(ids,role="admin"): return CurrentUser(ids[0],"audit-admin","Admin User",role)

def test_generic_entity_audit_entry(factory,context):
    with factory.begin() as session:
        AuditLogRepository(factory).add_entry(session,user_id=context[0],action="create",
            entity_type="blast_event",entity_id=context[3],description="Created production Block")
    rows=AuditLogRepository(factory).list_for_blast_event(context[3])
    assert len(rows)==1 and rows[0].action=="create" and rows[0].entity_id==context[3]

def test_update_audits_changed_fields_and_noop(factory,context):
    current=service(factory)
    current.update_block(context[3],ProductionBlastInput(context[2],"B-001","760.5","Updated"),
        user(context),expected_version=0)
    rows=AuditLogRepository(factory).list_for_blast_event(context[3]); fields={row.field_name for row in rows}
    assert fields=={"elevation_m","comment"}
    count=len(rows)
    current.update_block(context[3],ProductionBlastInput(context[2],"B-001","760.5","Updated"),
        user(context),expected_version=1)
    assert len(AuditLogRepository(factory).list_for_blast_event(context[3]))==count

def test_audit_failure_rolls_back_production_update(factory,context):
    failing=service(factory,FailingAuditLogRepository(factory))
    with pytest.raises(RuntimeError,match="audit failed"):
        failing.update_block(context[3],ProductionBlastInput(context[2],"ROLLBACK","761","x"),
            user(context),expected_version=0)
    with factory() as session:
        row=session.scalar(select(BlastEvent).where(BlastEvent.logical_id==context[3]))
        assert row.name=="B-001" and float(row.elevation_m)==760.0
        assert row.comment is None
        assert session.get(Domain, context[2]).version == 0

def test_viewer_cannot_edit(factory,context):
    with pytest.raises(PermissionDenied):
        service(factory).update_block(context[3],ProductionBlastInput(context[2],"X","760.5","Updated"),
            user(context,"viewer"),expected_version=2)
