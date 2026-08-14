from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, func,
    Integer, Numeric, String, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import JSONB

from .base import Base, TimestampMixin

user_role_enum = Enum("admin", "editor", "viewer", name="user_role", native_enum=True)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(user_role_enum, nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ExplosiveProduct(TimestampMixin, Base):
    """Application-wide editable reference product; historical facts use snapshots."""
    __tablename__ = "explosive_products"
    __table_args__ = (
        CheckConstraint("kind IN ('bulk', 'cartridge')", name="ck_explosive_products_kind"),
        CheckConstraint("length(btrim(name)) > 0", name="ck_explosive_products_name"),
        CheckConstraint("display_color ~ '^#[0-9A-Fa-f]{6}$'", name="ck_explosive_products_color"),
        CheckConstraint(
            "(kind = 'bulk' AND density_kg_m3 > 0 AND cartridge_diameter_mm IS NULL "
            "AND cartridge_mass_kg IS NULL AND default_pitch_m IS NULL) OR "
            "(kind = 'cartridge' AND density_kg_m3 IS NULL AND cartridge_diameter_mm > 0 "
            "AND cartridge_mass_kg > 0)", name="ck_explosive_products_kind_fields"),
        CheckConstraint("default_pitch_m IS NULL OR default_pitch_m > 0",
                        name="ck_explosive_products_pitch"),
        UniqueConstraint("name", name="uq_explosive_products_name"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    density_kg_m3: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    cartridge_diameter_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    cartridge_mass_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    display_color: Mapped[str] = mapped_column(String(7), nullable=False)
    default_pitch_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True,
                                             server_default="true", index=True)



class Mine(TimestampMixin, Base):
    __tablename__ = "mines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    sites: Mapped[list["Site"]] = relationship(back_populates="mine")


class Site(TimestampMixin, Base):
    __tablename__ = "sites"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mine_id: Mapped[int] = mapped_column(ForeignKey("mines.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    mine: Mapped[Mine] = relationship(back_populates="sites")
    domains: Mapped[list["Domain"]] = relationship(back_populates="site", cascade="all, delete-orphan")
    project_lines_datasets: Mapped[list["ProjectLinesDataset"]] = relationship(back_populates="site")
    charge_design_presets: Mapped[list["ChargeDesignPreset"]] = relationship(
        back_populates="site", cascade="all, delete-orphan")


class ChargeDesignPreset(TimestampMixin, Base):
    __tablename__ = "charge_design_presets"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="ck_charge_design_presets_name"),
        CheckConstraint("jsonb_typeof(components_json) = 'array'", name="ck_charge_design_presets_components_array"),
        UniqueConstraint("site_id", "name", name="uq_charge_design_presets_site_name"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    components_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    site: Mapped[Site] = relationship(back_populates="charge_design_presets")


class Domain(TimestampMixin, Base):
    __tablename__ = "domains"
    __table_args__ = (UniqueConstraint("site_id", "name", name="uq_domains_site_name"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    site: Mapped[Site] = relationship(back_populates="domains")
    blast_blocks: Mapped[list["BlastBlock"]] = relationship(back_populates="domain")
    blast_events: Mapped[list["BlastEvent"]] = relationship(back_populates="domain")
    assessment_areas: Mapped[list["AssessmentArea"]] = relationship(back_populates="domain")
    geometry: Mapped[Optional["DomainGeometry"]] = relationship(
        back_populates="domain", uselist=False, cascade="all, delete-orphan", passive_deletes=True
    )


class DomainGeometry(TimestampMixin, Base):
    """The single current, plan-view reference footprint for a Domain."""
    __tablename__ = "domain_geometries"
    __table_args__ = (
        CheckConstraint("jsonb_typeof(polygons_json) = 'array'", name="ck_domain_geometries_polygons_array"),
        CheckConstraint("source_kind IN ('imported', 'drawn')", name="ck_domain_geometries_source_kind"),
        UniqueConstraint("domain_id", name="uq_domain_geometries_domain_id"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain_id: Mapped[int] = mapped_column(
        ForeignKey("domains.id", ondelete="CASCADE"), nullable=False, index=True
    )
    polygons_json: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    source_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    source_file_name: Mapped[Optional[str]] = mapped_column(String(255))
    domain: Mapped[Domain] = relationship(back_populates="geometry")


class BlastBlock(TimestampMixin, Base):
    __tablename__ = "blast_blocks"
    __table_args__ = (Index("ix_blast_blocks_domain_block_number", "domain_id", "block_number"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey("domains.id", ondelete="RESTRICT"), nullable=False, index=True)
    block_number: Mapped[str] = mapped_column(String(80), nullable=False)
    horizon_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    archived_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    domain: Mapped[Domain] = relationship(back_populates="blast_blocks")
    created_by_user: Mapped[Optional[User]] = relationship()




class AuditLogEntry(Base):
    __tablename__ = "audit_log_entries"
    __table_args__ = (
        CheckConstraint("action IN ('create', 'update', 'delete', 'attach', 'detach')", name="ck_audit_log_entries_action"),
        CheckConstraint("entity_type IN ('blast_block', 'attachment', 'rock_mass_profile', 'rock_structure', 'blast_design', 'drilling_pattern', 'wall_assessment')", name="ck_audit_log_entries_entity_type"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blast_block_id: Mapped[int] = mapped_column(ForeignKey("blast_blocks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    field_name: Mapped[Optional[str]] = mapped_column(String(80))
    old_value: Mapped[Optional[str]] = mapped_column(Text)
    new_value: Mapped[Optional[str]] = mapped_column(Text)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    user: Mapped[Optional[User]] = relationship()
    blast_block: Mapped[BlastBlock] = relationship()


class RememberToken(Base):
    __tablename__ = "remember_tokens"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    device_name: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
    user: Mapped[User] = relationship()
