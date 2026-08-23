"""Revisioned drillhole dataset persistence scoped to a BlastEvent."""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database.assessment_models import BlastEvent
from database.drillhole_models import BlastEventDrillholeDataset


class DrillholeDatasetNotFoundError(LookupError):
    pass


class BlastEventDrillholeDatasetRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    @staticmethod
    def _event_statement(domain_id: int, event_logical_id: str):
        return select(BlastEvent).where(
            BlastEvent.domain_id == int(domain_id),
            BlastEvent.logical_id == str(event_logical_id),
        )

    def add_dataset(
        self,
        domain_id: int,
        event_logical_id: str,
        *,
        logical_id: str,
        dataset_kind: str,
        imported_at: datetime,
        imported_by_user_id: int | None,
        source_format: str,
        source_files: list[dict[str, object]],
        holes: list[dict[str, object]],
        summary: dict[str, object],
        matches: list[dict[str, object]],
        hole_count: int,
        total_drilling_length_m: float,
    ) -> BlastEventDrillholeDataset:
        if dataset_kind not in {"design", "actual"}:
            raise ValueError(f"Unsupported drillhole dataset kind: {dataset_kind!r}")
        with self._session_factory.begin() as session:
            event = session.scalar(self._event_statement(domain_id, event_logical_id).with_for_update())
            if event is None:
                raise ValueError(f"BlastEvent {event_logical_id!r} does not exist in Domain {domain_id}")
            current_revision = session.scalar(
                select(func.max(BlastEventDrillholeDataset.revision_number)).where(
                    BlastEventDrillholeDataset.blast_event_id == event.id,
                    BlastEventDrillholeDataset.dataset_kind == dataset_kind,
                )
            )
            row = BlastEventDrillholeDataset(
                blast_event_id=event.id,
                logical_id=logical_id,
                dataset_kind=dataset_kind,
                revision_number=int(current_revision or 0) + 1,
                imported_at=imported_at,
                imported_by_user_id=imported_by_user_id,
                source_format=source_format,
                source_files_json=source_files,
                holes_json=holes,
                summary_json=summary,
                matches_json=matches,
                hole_count=int(hole_count),
                total_drilling_length_m=float(total_drilling_length_m),
            )
            session.add(row)
            session.flush()
            row_id = row.id
        return self._get_row(row_id)

    def list_for_event(
        self,
        domain_id: int,
        event_logical_id: str,
        *,
        dataset_kind: str | None = None,
    ) -> list[BlastEventDrillholeDataset]:
        with self._session_factory() as session:
            event = session.scalar(self._event_statement(domain_id, event_logical_id))
            if event is None:
                return []
            statement = select(BlastEventDrillholeDataset).where(
                BlastEventDrillholeDataset.blast_event_id == event.id
            )
            if dataset_kind is not None:
                statement = statement.where(
                    BlastEventDrillholeDataset.dataset_kind == dataset_kind
                )
            statement = statement.order_by(
                BlastEventDrillholeDataset.dataset_kind,
                BlastEventDrillholeDataset.revision_number.desc(),
            )
            return list(session.scalars(statement))

    def get_current(
        self,
        domain_id: int,
        event_logical_id: str,
        dataset_kind: str,
    ) -> BlastEventDrillholeDataset | None:
        if dataset_kind not in {"design", "actual"}:
            raise ValueError(f"Unsupported drillhole dataset kind: {dataset_kind!r}")
        with self._session_factory() as session:
            event = session.scalar(self._event_statement(domain_id, event_logical_id))
            if event is None:
                return None
            return session.scalar(
                select(BlastEventDrillholeDataset)
                .where(
                    BlastEventDrillholeDataset.blast_event_id == event.id,
                    BlastEventDrillholeDataset.dataset_kind == dataset_kind,
                )
                .order_by(BlastEventDrillholeDataset.revision_number.desc())
                .limit(1)
            )

    def get_by_logical_id(
        self,
        domain_id: int,
        event_logical_id: str,
        logical_id: str,
    ) -> BlastEventDrillholeDataset:
        with self._session_factory() as session:
            event = session.scalar(self._event_statement(domain_id, event_logical_id))
            if event is None:
                raise DrillholeDatasetNotFoundError(logical_id)
            row = session.scalar(
                select(BlastEventDrillholeDataset).where(
                    BlastEventDrillholeDataset.blast_event_id == event.id,
                    BlastEventDrillholeDataset.logical_id == logical_id,
                )
            )
            if row is None:
                raise DrillholeDatasetNotFoundError(logical_id)
            return row

    def _get_row(self, row_id: int) -> BlastEventDrillholeDataset:
        with self._session_factory() as session:
            row = session.get(BlastEventDrillholeDataset, row_id)
            if row is None:
                raise DrillholeDatasetNotFoundError(str(row_id))
            return row
