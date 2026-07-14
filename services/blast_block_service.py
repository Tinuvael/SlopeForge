from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from sqlalchemy.exc import SQLAlchemyError

from database.app_context import CurrentUser
from repositories.blast_block_repository import BlastBlockRepository, BlastBlockRow
from repositories.site_repository import SiteRepository

VALID_STATUSES = {"planned", "blasted", "assessed"}
STATUS_LABELS = {"planned": "Запланирован", "blasted": "Взорван", "assessed": "Оценён"}


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
    def __init__(self, block_repository: BlastBlockRepository, site_repository: SiteRepository):
        self.block_repository = block_repository
        self.site_repository = site_repository

    def list_blocks(self, **filters) -> list[BlastBlockRow]:
        return self.block_repository.list_blocks(**filters)

    def get_block(self, block_id: int) -> BlastBlockRow | None:
        return self.block_repository.get_block(block_id)

    def create_block(self, data: BlastBlockInput, user: CurrentUser) -> int:
        self._check_can_edit(user)
        horizon = self._validate(data)
        try:
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
        except SQLAlchemyError as exc:
            raise ValidationError("Не удалось сохранить блок в PostgreSQL. Проверьте данные и миграции базы.") from exc

    def update_block(self, block_id: int, data: BlastBlockInput, user: CurrentUser) -> int:
        self._check_can_edit(user)
        horizon = self._validate(data)
        try:
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
        except SQLAlchemyError as exc:
            raise ValidationError("Не удалось обновить блок в PostgreSQL. Проверьте данные и миграции базы.") from exc

    def _check_can_edit(self, user: CurrentUser) -> None:
        if not user.can_edit:
            raise PermissionDenied("У вашей роли нет права создавать или редактировать блоки")

    def _validate(self, data: BlastBlockInput) -> Decimal | None:
        if not data.block_number.strip():
            raise ValidationError("Номер блока обязателен")
        if data.site_id is None:
            raise ValidationError("Выберите участок")
        if data.mine_id is None:
            raise ValidationError("Выберите месторождение")
        sites = self.site_repository.list_sites(data.mine_id)
        if not any(site.id == data.site_id for site in sites):
            raise ValidationError("Выбранный участок не относится к выбранному месторождению")
        if data.status not in VALID_STATUSES:
            raise ValidationError("Недопустимый статус блока")
        if not data.horizon_text.strip():
            return None
        try:
            return Decimal(data.horizon_text.replace(",", "."))
        except InvalidOperation as exc:
            raise ValidationError("Горизонт должен быть числом") from exc
