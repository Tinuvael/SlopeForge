from __future__ import annotations
import os
from datetime import date
from pathlib import Path
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from database.app_context import CurrentUser
from database.models import AuditLogEntry, BlastBlock, Domain, Mine, Site, User
from repositories.audit_log_repository import AuditLogRepository
from repositories.blast_block_repository import BlastBlockRepository
from repositories.domain_repository import DomainRepository
from services.blast_block_service import BlastBlockInput, BlastBlockService, PermissionDenied

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
        mine=Mine(name="Audit Project");session.add_all((user,mine));session.flush()
        site=Site(mine_id=mine.id,name="Audit Project");session.add(site);session.flush()
        domain=Domain(site_id=site.id,name="North");session.add(domain);session.flush()
        block=BlastBlock(domain_id=domain.id,block_number="B-001",status="planned",created_by_user_id=user.id)
        session.add(block);session.flush(); ids=(user.id,mine.id,site.id,domain.id,block.id)
    yield ids
    with factory.begin() as session:
        session.query(AuditLogEntry).delete();session.query(BlastBlock).filter_by(domain_id=ids[3]).delete()
        session.query(Domain).filter_by(id=ids[3]).delete();session.query(Site).filter_by(id=ids[2]).delete()
        session.query(Mine).filter_by(id=ids[1]).delete();session.query(User).filter_by(id=ids[0]).delete()

def service(factory,audit=None):
    return BlastBlockService(BlastBlockRepository(factory),DomainRepository(factory),audit)

def data(domain_id,number="B-001",horizon="",status="planned",comment=""):
    return BlastBlockInput(domain_id,number,horizon,date(2026,7,15),status,comment)

def user(ids,role="admin"): return CurrentUser(ids[0],role,"Admin User",role)

def test_create_audit_entry(factory,context):
    block_id=service(factory).create_block(data(context[3],"B-002"),user(context))
    rows=AuditLogRepository(factory).list_for_block(block_id)
    assert len(rows)==1 and rows[0].action=="create" and rows[0].description=="Создан взрывной блок"

def test_update_audits_changed_fields_and_noop(factory,context):
    current=service(factory); current.update_block(context[4],data(context[3],horizon="760.5",status="blasted",comment="Updated"),user(context),expected_version=0)
    rows=AuditLogRepository(factory).list_for_block(context[4]); fields={row.field_name for row in rows}
    assert fields=={"horizon_m","planned_blast_date","status","comment"}
    assert any(row.old_value=="Запланирован" and row.new_value=="Взорван" for row in rows)
    count=len(rows)
    current.update_block(context[4],data(context[3],horizon="760.5",status="blasted",comment="Updated"),user(context),expected_version=1)
    assert len(AuditLogRepository(factory).list_for_block(context[4]))==count

def test_audit_failure_rolls_back_create(factory,context):
    with pytest.raises(RuntimeError,match="audit failed"):
        service(factory,FailingAuditLogRepository(factory)).create_block(data(context[3],"ROLLBACK"),user(context))
    with factory() as session: assert session.scalar(select(BlastBlock).where(BlastBlock.block_number=="ROLLBACK")) is None

def test_viewer_cannot_edit(factory,context):
    with pytest.raises(PermissionDenied):
        service(factory).update_block(context[4],data(context[3],number="X"),user(context,"viewer"),expected_version=0)
