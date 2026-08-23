"""Metadata and canonical geometry for revisioned BlastEvent drillhole datasets."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class BlastEventDrillholeDataset(Base):
    __tablename__ = "blast_event_drillhole_datasets"
    __table_args__ = (
        UniqueConstraint(
            "blast_event_id",
            "logical_id",
            name="uq_blast_event_drillhole_datasets_event_logical_id",
        ),
        UniqueConstraint(
            "blast_event_id",
            "dataset_kind",
            "revision_number",
            name="uq_blast_event_drillhole_datasets_event_kind_revision",
        ),
        CheckConstraint(
            "dataset_kind IN ('design', 'actual')",
            name="ck_blast_event_drillhole_datasets_kind",
        ),
        CheckConstraint(
            "source_format IN ('dxf', 'datamine')",
            name="ck_blast_event_drillhole_datasets_format",
        ),
        CheckConstraint(
            "revision_number > 0",
            name="ck_blast_event_drillhole_datasets_revision_positive",
        ),
        CheckConstraint(
            "hole_count > 0",
            name="ck_blast_event_drillhole_datasets_hole_count",
        ),
        CheckConstraint(
            "total_drilling_length_m > 0",
            name="ck_blast_event_drillhole_datasets_total_length",
        ),
        CheckConstraint(
            "jsonb_typeof(source_files_json) = 'array'",
            name="ck_blast_event_drillhole_datasets_source_files_array",
        ),
        CheckConstraint(
            "jsonb_typeof(holes_json) = 'array'",
            name="ck_blast_event_drillhole_datasets_holes_array",
        ),
        CheckConstraint(
            "jsonb_typeof(summary_json) = 'object'",
            name="ck_blast_event_drillhole_datasets_summary_object",
        ),
        CheckConstraint(
            "jsonb_typeof(matches_json) = 'array'",
            name="ck_blast_event_drillhole_datasets_matches_array",
        ),
        Index(
            "ix_blast_event_drillhole_datasets_event_kind_revision",
            "blast_event_id",
            "dataset_kind",
            "revision_number",
        ),
        Index(
            "ix_blast_event_drillhole_datasets_imported_at",
            "imported_at",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blast_event_id: Mapped[int] = mapped_column(
        ForeignKey("blast_events.id", ondelete="CASCADE"), nullable=False
    )
    logical_id: Mapped[str] = mapped_column(String(255), nullable=False)
    dataset_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    imported_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source_format: Mapped[str] = mapped_column(String(20), nullable=False)
    source_files_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    holes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    summary_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    matches_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False, default=list)
    hole_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_drilling_length_m: Mapped[float] = mapped_column(Float, nullable=False)
