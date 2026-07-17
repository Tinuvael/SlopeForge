from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import SQLAlchemyError

from database.app_context import CurrentUser
<<<<<<< HEAD
from database.models import BlastBlock, Site
from repositories.audit_log_repository import AuditLogRepository
=======
>>>>>>> origin/main
from repositories.blast_block_repository import BlastBlockRepository, BlastBlockRow
from repositories.site_repository import SiteRepository

VALID_STATUSES = {"planned", "blasted", "assessed"}
STATUS_LABELS = {"planned": "Planned", "blasted": "Blasted", "assessed": "Assessed"}
<<<<<<< HEAD
AUDIT_STATUS_LABELS = {"planned": "Запланирован", "blasted": "Взорван", "assessed": "Оценён"}
AUDIT_FIELD_LABELS = {
    "block_number": "Номер блока",
    "site_id": "Участок",
    "horizon_m": "Горизонт",
    "planned_blast_date": "Плановая дата взрыва",
    "status": "Статус",
    "comment": "Комментарий",
}
AUDITED_FIELDS = ("block_number", "site_id", "horizon_m", "planned_blast_date", "status", "comment")
=======
>>>>>>> origin/main


class PermissionDenied(ValueError):
    pass


class ValidationError(ValueError):
    pass


@dataclass(frozen=True)
class BlastBlockInput:
    block_number: str
    mine_id: int | None
    site_id: int | None
    horizon_text: str
    planned_blast_date: date | None
    status: str
    comment: str | None


class BlastBlockService:
<<<<<<< HEAD
    def __init__(self, block_repository: BlastBlockRepository, site_repository: SiteRepository, audit_repository: AuditLogRepository | None = None):
        self.block_repository = block_repository
        self.site_repository = site_repository
        self.session_factory = getattr(block_repository, "session_factory", None)
        self.audit_repository = audit_repository or (AuditLogRepository(self.session_factory) if self.session_factory else None)
=======
    def __init__(self, block_repository: BlastBlockRepository, site_repository: SiteRepository):
        self.block_repository = block_repository
        self.site_repository = site_repository
>>>>>>> origin/main

    def list_blocks(self, **filters) -> list[BlastBlockRow]:
        return self.block_repository.list_blocks(**filters)

    def get_block(self, block_id: int) -> BlastBlockRow | None:
        return self.block_repository.get_block(block_id)

    def create_block(self, data: BlastBlockInput, user: CurrentUser) -> int:
        self._check_can_edit(user)
        horizon = self._validate(data)
<<<<<<< HEAD
        if self.session_factory is None:
=======
        try:
>>>>>>> origin/main
            block = self.block_repository.create_block(
                site_id=data.site_id,
                block_number=data.block_number,
                horizon_m=horizon,
                planned_blast_date=data.planned_blast_date,
                status=data.status,
                comment=data.comment,
                created_by_user_id=user.id,
            )
            return block.id
<<<<<<< HEAD
        try:
            with self.session_factory() as session:
                try:
                    block = BlastBlock(
                        site_id=data.site_id,
                        block_number=data.block_number.strip(),
                        horizon_m=horizon,
                        planned_blast_date=data.planned_blast_date,
                        status=data.status,
                        comment=data.comment or None,
                        created_by_user_id=user.id,
                    )
                    session.add(block)
                    session.flush()
                    self.audit_repository.add_entry(
                        session,
                        blast_block_id=block.id,
                        user_id=user.id,
                        action="create",
                        entity_type="blast_block",
                        entity_id=block.id,
                        description="Создан взрывной блок",
                    )
                    session.commit()
                    return block.id
                except Exception:
                    session.rollback()
                    raise
=======
>>>>>>> origin/main
        except SQLAlchemyError as exc:
            raise ValidationError("Could not save the block in PostgreSQL. Check the data and database migrations.") from exc

    def update_block(self, block_id: int, data: BlastBlockInput, user: CurrentUser) -> int:
        self._check_can_edit(user)
        horizon = self._validate(data)
<<<<<<< HEAD
        if self.session_factory is None:
=======
        try:
>>>>>>> origin/main
            self.block_repository.update_block(
                block_id=block_id,
                site_id=data.site_id,
                block_number=data.block_number,
                horizon_m=horizon,
                planned_blast_date=data.planned_blast_date,
                status=data.status,
                comment=data.comment,
            )
            return block_id
<<<<<<< HEAD
        try:
            with self.session_factory() as session:
                try:
                    block = session.get(BlastBlock, block_id)
                    if block is None:
                        raise ValueError("Blast block not found")
                    new_values = {
                        "block_number": data.block_number.strip(),
                        "site_id": data.site_id,
                        "horizon_m": horizon,
                        "planned_blast_date": data.planned_blast_date,
                        "status": data.status,
                        "comment": data.comment or None,
                    }
                    old_values = {field: getattr(block, field) for field in AUDITED_FIELDS}
                    site_names = self._site_names_for_audit(session, old_values["site_id"], new_values["site_id"])
                    changes = build_audit_changes(old_values, new_values, site_names)
                    for field, new_value in new_values.items():
                        setattr(block, field, new_value)
                    for field_name, old_text, new_text in changes:
                        self.audit_repository.add_entry(
                            session,
                            blast_block_id=block.id,
                            user_id=user.id,
                            action="update",
                            entity_type="blast_block",
                            entity_id=block.id,
                            field_name=field_name,
                            old_value=old_text,
                            new_value=new_text,
                            description=f"Изменено поле: {AUDIT_FIELD_LABELS[field_name]}",
                        )
                    session.commit()
                    return block_id
                except Exception:
                    session.rollback()
                    raise
=======
>>>>>>> origin/main
        except SQLAlchemyError as exc:
            raise ValidationError("Could not update the block in PostgreSQL. Check the data and database migrations.") from exc

    def _check_can_edit(self, user: CurrentUser) -> None:
        if not user.can_edit:
            raise PermissionDenied("Your role is not allowed to create or edit blocks")

    def _validate(self, data: BlastBlockInput) -> Decimal | None:
        if not data.block_number.strip():
            raise ValidationError("Block number is required")
        if data.site_id is None:
            raise ValidationError("Select a site")
        if data.mine_id is None:
            raise ValidationError("Select a mine")
        sites = self.site_repository.list_sites(data.mine_id)
        if not any(site.id == data.site_id for site in sites):
            raise ValidationError("Selected site does not belong to selected mine")
        if data.status not in VALID_STATUSES:
            raise ValidationError("Invalid block status")
        if not data.horizon_text.strip():
            return None
        try:
            return Decimal(data.horizon_text.replace(",", "."))
        except InvalidOperation as exc:
            raise ValidationError("Horizon must be a number") from exc
<<<<<<< HEAD

    @staticmethod
    def _site_names_for_audit(session, old_site_id: int | None, new_site_id: int | None) -> dict[int, str]:
        ids = {site_id for site_id in (old_site_id, new_site_id) if site_id is not None}
        return {site.id: site.name for site in session.query(Site).filter(Site.id.in_(ids)).all()} if ids else {}


def build_audit_changes(old_values: dict, new_values: dict, site_names: dict[int, str] | None = None) -> list[tuple[str, str | None, str | None]]:
    site_names = site_names or {}
    changes = []
    for field in AUDITED_FIELDS:
        old_value = old_values.get(field)
        new_value = new_values.get(field)
        if old_value == new_value:
            continue
        changes.append((field, format_audit_value(field, old_value, site_names), format_audit_value(field, new_value, site_names)))
    return changes


def format_audit_value(field_name: str, value, site_names: dict[int, str] | None = None) -> str | None:
    if value is None:
        return None
    if field_name == "status":
        return AUDIT_STATUS_LABELS.get(str(value), str(value))
    if field_name == "planned_blast_date" and isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    if field_name == "horizon_m" and isinstance(value, Decimal):
        return format(value.normalize(), "f").rstrip("0").rstrip(".") if "." in format(value.normalize(), "f") else format(value.normalize(), "f")
    if field_name == "site_id":
        return (site_names or {}).get(int(value), str(value))
    return str(value)
=======
>>>>>>> origin/main
