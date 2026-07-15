from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, Date, DateTime, Enum, ForeignKey, Index, func,
    Integer, Numeric, String, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

user_role_enum = Enum("admin", "editor", "viewer", name="user_role", native_enum=True)
blast_block_status_enum = Enum("planned", "blasted", "assessed", name="blast_block_status", native_enum=True)
structure_type_enum = Enum("joint_set", "tectonic_structure", name="structure_type", native_enum=True)
drilling_role_enum = Enum("production", "buffer", "contour", name="drilling_role", native_enum=True)
charge_segment_type_enum = Enum("explosive", "stemming", "air_deck", name="charge_segment_type", native_enum=True)
wall_rating_enum = Enum("good", "satisfactory", "poor", name="wall_rating", native_enum=True)
attachment_kind_enum = Enum("photo", "document", name="attachment_kind", native_enum=True)


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
    blast_blocks: Mapped[list["BlastBlock"]] = relationship(back_populates="site")


class BlastBlock(TimestampMixin, Base):
    __tablename__ = "blast_blocks"
    __table_args__ = (Index("ix_blast_blocks_site_block_number", "site_id", "block_number"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    site_id: Mapped[int] = mapped_column(ForeignKey("sites.id", ondelete="RESTRICT"), nullable=False, index=True)
    block_number: Mapped[str] = mapped_column(String(80), nullable=False)
    horizon_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2))
    planned_blast_date: Mapped[Optional[date]] = mapped_column(Date)
    status: Mapped[str] = mapped_column(blast_block_status_enum, nullable=False, default="planned", index=True)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    site: Mapped[Site] = relationship(back_populates="blast_blocks")
    created_by_user: Mapped[Optional[User]] = relationship()
    rock_mass_profile: Mapped[Optional["RockMassProfile"]] = relationship(back_populates="blast_block", uselist=False)
    blast_design: Mapped[Optional["BlastDesign"]] = relationship(back_populates="blast_block", uselist=False)


class Lithology(Base):
    __tablename__ = "lithologies"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)



class ExplosiveType(Base):
    __tablename__ = "explosive_types"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    updated_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    must_change_password: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)



class RockMassProfile(TimestampMixin, Base):
    __tablename__ = "rock_mass_profiles"
    __table_args__ = (
        CheckConstraint("rqd_percent IS NULL OR (rqd_percent >= 0 AND rqd_percent <= 100)", name="ck_rock_mass_profiles_rqd_percent_range"),
        CheckConstraint("rmr IS NULL OR (rmr >= 0 AND rmr <= 100)", name="ck_rock_mass_profiles_rmr_range"),
        CheckConstraint("gsi IS NULL OR (gsi >= 0 AND gsi <= 100)", name="ck_rock_mass_profiles_gsi_range"),
        CheckConstraint("q_value IS NULL OR q_value > 0", name="ck_rock_mass_profiles_q_value_positive"),
        CheckConstraint("ucs_mpa IS NULL OR ucs_mpa >= 0", name="ck_rock_mass_profiles_ucs_mpa_non_negative"),
        CheckConstraint("uts_mpa IS NULL OR uts_mpa >= 0", name="ck_rock_mass_profiles_uts_mpa_non_negative"),
        CheckConstraint("characteristic_block_size_m IS NULL OR characteristic_block_size_m >= 0", name="ck_rock_mass_profiles_block_size_non_negative"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blast_block_id: Mapped[int] = mapped_column(ForeignKey("blast_blocks.id", ondelete="CASCADE"), nullable=False, unique=True)
    lithology_id: Mapped[Optional[int]] = mapped_column(ForeignKey("lithologies.id", ondelete="SET NULL"), index=True)
    rqd_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    rmr: Mapped[Optional[int]] = mapped_column(Integer)
    gsi: Mapped[Optional[int]] = mapped_column(Integer)
    q_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    ucs_mpa: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    uts_mpa: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    characteristic_block_size_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    blast_block: Mapped[BlastBlock] = relationship(back_populates="rock_mass_profile")
    lithology: Mapped[Optional[Lithology]] = relationship()
    structures: Mapped[list["RockStructure"]] = relationship(back_populates="rock_mass_profile")


class RockStructure(TimestampMixin, Base):
    __tablename__ = "rock_structures"
    __table_args__ = (
        UniqueConstraint("rock_mass_profile_id", "structure_type", "sequence_number", name="uq_rock_structures_profile_type_sequence"),
        CheckConstraint("dip_deg IS NULL OR (dip_deg >= 0 AND dip_deg <= 90)", name="ck_rock_structures_dip_deg_range"),
        CheckConstraint("dip_direction_deg IS NULL OR (dip_direction_deg >= 0 AND dip_direction_deg < 360)", name="ck_rock_structures_dip_direction_deg_range"),
        CheckConstraint("thickness_m IS NULL OR thickness_m >= 0", name="ck_rock_structures_thickness_m_non_negative"),
        CheckConstraint("sequence_number >= 1 AND sequence_number <= 5", name="ck_rock_structures_sequence_number_range"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rock_mass_profile_id: Mapped[int] = mapped_column(ForeignKey("rock_mass_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    structure_type: Mapped[str] = mapped_column(structure_type_enum, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    dip_deg: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    dip_direction_deg: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2))
    thickness_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    description: Mapped[Optional[str]] = mapped_column(Text)
    rock_mass_profile: Mapped[RockMassProfile] = relationship(back_populates="structures")


class BlastDesign(TimestampMixin, Base):
    __tablename__ = "blast_designs"
    __table_args__ = (CheckConstraint("specific_explosive_consumption_kg_m3 IS NULL OR specific_explosive_consumption_kg_m3 >= 0", name="ck_blast_designs_sec_non_negative"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blast_block_id: Mapped[int] = mapped_column(ForeignKey("blast_blocks.id", ondelete="CASCADE"), nullable=False, unique=True)
    contour_drilling: Mapped[Optional[bool]] = mapped_column(Boolean)
    specific_explosive_consumption_kg_m3: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    blast_block: Mapped[BlastBlock] = relationship(back_populates="blast_design")
    drilling_patterns: Mapped[list["DrillingPattern"]] = relationship(back_populates="blast_design")


class DrillingPattern(TimestampMixin, Base):
    __tablename__ = "drilling_patterns"
    __table_args__ = tuple(CheckConstraint(f"{c} IS NULL OR {c} >= 0", name=f"ck_drilling_patterns_{c}_non_negative") for c in ["diameter_mm", "spacing_m", "burden_m", "depth_m", "toe_offset_m"])
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blast_design_id: Mapped[int] = mapped_column(ForeignKey("blast_designs.id", ondelete="CASCADE"), nullable=False, index=True)
    drilling_role: Mapped[str] = mapped_column(drilling_role_enum, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255))
    diameter_mm: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    spacing_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    burden_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    depth_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    toe_offset_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    explosive_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("explosive_types.id", ondelete="SET NULL"), index=True)
    comment: Mapped[Optional[str]] = mapped_column(Text)
    blast_design: Mapped[BlastDesign] = relationship(back_populates="drilling_patterns")
    explosive_type: Mapped[Optional[ExplosiveType]] = relationship()
    charge_segments: Mapped[list["ChargeSegment"]] = relationship(back_populates="drilling_pattern")


class ChargeSegment(TimestampMixin, Base):
    __tablename__ = "charge_segments"
    __table_args__ = (
        UniqueConstraint("drilling_pattern_id", "sequence_number", name="uq_charge_segments_pattern_sequence"),
        CheckConstraint("length_m > 0", name="ck_charge_segments_length_m_positive"),
        CheckConstraint("charge_mass_kg IS NULL OR charge_mass_kg >= 0", name="ck_charge_segments_charge_mass_kg_non_negative"),
        CheckConstraint("sequence_number > 0", name="ck_charge_segments_sequence_number_positive"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    drilling_pattern_id: Mapped[int] = mapped_column(ForeignKey("drilling_patterns.id", ondelete="CASCADE"), nullable=False, index=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    segment_type: Mapped[str] = mapped_column(charge_segment_type_enum, nullable=False)
    length_m: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    explosive_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("explosive_types.id", ondelete="SET NULL"), index=True)
    charge_mass_kg: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 3))
    comment: Mapped[Optional[str]] = mapped_column(Text)
    drilling_pattern: Mapped[DrillingPattern] = relationship(back_populates="charge_segments")
    explosive_type: Mapped[Optional[ExplosiveType]] = relationship()


class BlastExecution(TimestampMixin, Base):
    __tablename__ = "blast_executions"
    __table_args__ = (CheckConstraint("actual_explosive_consumption_kg_m3 IS NULL OR actual_explosive_consumption_kg_m3 >= 0", name="ck_blast_executions_sec_non_negative"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blast_block_id: Mapped[int] = mapped_column(ForeignKey("blast_blocks.id", ondelete="CASCADE"), nullable=False, unique=True)
    actual_blast_datetime: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    initiation_description: Mapped[Optional[str]] = mapped_column(Text)
    weather_conditions: Mapped[Optional[str]] = mapped_column(Text)
    actual_explosive_consumption_kg_m3: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    comment: Mapped[Optional[str]] = mapped_column(Text)


class WallAssessment(TimestampMixin, Base):
    __tablename__ = "wall_assessments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blast_block_id: Mapped[int] = mapped_column(ForeignKey("blast_blocks.id", ondelete="CASCADE"), nullable=False, unique=True)
    rms_deviation_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    mean_deviation_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    max_overbreak_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    max_underbreak_m: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    assessment_matrix_name: Mapped[Optional[str]] = mapped_column(String(255))
    assessment_matrix_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 3))
    rating: Mapped[Optional[str]] = mapped_column(wall_rating_enum, index=True)
    engineer_comment: Mapped[Optional[str]] = mapped_column(Text)
    assessed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    assessed_by_user: Mapped[Optional[User]] = relationship()


class Attachment(TimestampMixin, Base):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint("file_size_bytes IS NULL OR file_size_bytes >= 0", name="ck_attachments_file_size_bytes_non_negative"),
        CheckConstraint("attachment_kind <> 'photo' OR subtype IN ('before_blast', 'after_blast', 'drilling', 'final_wall', 'other')", name="ck_attachments_photo_subtype"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    blast_block_id: Mapped[int] = mapped_column(ForeignKey("blast_blocks.id", ondelete="RESTRICT"), nullable=False, index=True)
    attachment_kind: Mapped[str] = mapped_column(attachment_kind_enum, nullable=False, index=True)
    subtype: Mapped[Optional[str]] = mapped_column(String(80))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_relative_path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(255))
    file_size_bytes: Mapped[Optional[int]] = mapped_column(BigInteger)
    file_date: Mapped[Optional[date]] = mapped_column(Date)
    description: Mapped[Optional[str]] = mapped_column(Text)
    uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    uploaded_by_user: Mapped[Optional[User]] = relationship()


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
