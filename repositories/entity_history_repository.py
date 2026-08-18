from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from database import assessment_models as orm
from database.models import AuditLogEntry


@dataclass(frozen=True)
class EntityHistoryEntry:
    timestamp: datetime
    actor: str
    title: str
    details: str = ""
    category: str = "change"
    source_type: str | None = None
    source_id: str | None = None
    revision_number: int | None = None
    sort_key: str = ""


def _actor(user) -> str:
    if user is None:
        return "—"
    return user.full_name or user.username or "—"


def _format_value(value: str | None) -> str:
    return "—" if value in (None, "") else str(value)


def _audit_title(entry: AuditLogEntry) -> str:
    if entry.description:
        return entry.description
    if entry.action == "create":
        return "Created"
    if entry.action == "delete":
        return "Deleted"
    if entry.action == "attach":
        return "Attachment added"
    if entry.action == "detach":
        return "Attachment removed"
    return "Updated"


def _audit_details(entry: AuditLogEntry) -> str:
    if entry.old_value is not None or entry.new_value is not None:
        return f"{_format_value(entry.old_value)} → {_format_value(entry.new_value)}"
    return ""


def _meaningful(value: Any) -> bool:
    if value in (None, "", [], {}):
        return False
    if isinstance(value, dict):
        return any(_meaningful(item) for item in value.values())
    if isinstance(value, list):
        return any(_meaningful(item) for item in value)
    return True


def _technical_sections(payload: dict[str, Any], event_type: str) -> dict[str, Any]:
    design = {
        "drilling_groups": payload.get("drilling_groups"),
        "production_parameters": payload.get("production_parameters"),
        "contour_parameters": payload.get("contour_parameters"),
        "design_slope_orientation": payload.get("design_slope_orientation"),
    }
    result = {"blast_design": design, "execution": payload.get("actual_execution")}
    if event_type == "production":
        result["geomechanics"] = payload.get("geomechanical_parameters")
    return result


def _execution_initialized(payload: dict[str, Any]) -> bool:
    actual = payload.get("actual_execution") or {}
    groups = actual.get("actual_drilling_groups") or []
    return any(group.get("copied_from_design") for group in groups if isinstance(group, dict))


def _assessment_result_details(revision) -> str:
    parts = [f"Evaluation R{revision.revision_number}"]
    if revision.design_achievement_index is not None:
        parts.append(f"DAI {float(revision.design_achievement_index):.3f}")
    if revision.face_condition_index is not None:
        parts.append(f"FCI {float(revision.face_condition_index):.3f}")
    if revision.result_quadrant:
        parts.append(str(revision.result_quadrant))
    return " · ".join(parts)


class EntityHistoryRepository:
    """Compose canonical revisions and generic audit rows into one read-only history."""

    _REVISION_MARKERS = {"geometry_revision", "assessment_revision"}

    def __init__(self, session_factory):
        self.session_factory = session_factory

    def for_blast_event(self, event_id: str) -> list[EntityHistoryEntry]:
        with self.session_factory() as session:
            event = session.scalar(
                select(orm.BlastEvent)
                .where(orm.BlastEvent.logical_id == event_id)
                .options(
                    selectinload(orm.BlastEvent.geometry_revisions),
                    selectinload(orm.BlastEvent.technical_card)
                    .selectinload(orm.BlastEventTechnicalCard.revisions)
                    .joinedload(orm.BlastEventTechnicalCardRevision.geometry_revision),
                )
            )
            if event is None:
                return []
            audits = list(session.scalars(
                select(AuditLogEntry)
                .options(joinedload(AuditLogEntry.user))
                .where(AuditLogEntry.entity_type == "blast_event",
                       AuditLogEntry.entity_id == event_id)
            ))
            marker_actor = {
                row.new_value: _actor(row.user)
                for row in audits
                if row.field_name in self._REVISION_MARKERS and row.new_value
            }
            entries = self._plain_audit_entries(audits)
            for revision in event.geometry_revisions:
                entries.append(EntityHistoryEntry(
                    revision.imported_at,
                    marker_actor.get(revision.logical_id, "—"),
                    "Geometry imported" if revision.revision_number == 1 else "Geometry reimported",
                    f"Geometry R{revision.revision_number} · {revision.source_file_name}",
                    "geometry", "blast_geometry", revision.logical_id,
                    revision.revision_number, f"geometry:{revision.id}",
                ))
            if event.technical_card is not None:
                entries.extend(self._technical_card_entries(event.technical_card.revisions, event.event_type))
            return self._sorted(entries)

    def for_assessment_area(self, area_id: str) -> list[EntityHistoryEntry]:
        with self.session_factory() as session:
            area = session.scalar(
                select(orm.AssessmentArea)
                .where(orm.AssessmentArea.logical_id == area_id)
                .options(
                    selectinload(orm.AssessmentArea.geometry_revisions),
                    selectinload(orm.AssessmentArea.evaluation)
                    .selectinload(orm.AssessmentAreaEvaluation.revisions),
                )
            )
            if area is None:
                return []
            audits = list(session.scalars(
                select(AuditLogEntry)
                .options(joinedload(AuditLogEntry.user))
                .where(AuditLogEntry.entity_type == "assessment_area",
                       AuditLogEntry.entity_id == area_id)
            ))
            marker_actor = {
                row.new_value: _actor(row.user)
                for row in audits
                if row.field_name in self._REVISION_MARKERS and row.new_value
            }
            entries = self._plain_audit_entries(audits)
            for revision in area.geometry_revisions:
                details = f"Geometry R{revision.revision_number}"
                if revision.change_reason:
                    details += f" · {revision.change_reason}"
                entries.append(EntityHistoryEntry(
                    revision.created_at,
                    marker_actor.get(revision.logical_id, "—"),
                    "Boundaries created" if revision.revision_number == 1 else "Boundaries revised",
                    details, "geometry", "assessment_geometry", revision.logical_id,
                    revision.revision_number, f"area-geometry:{revision.id}",
                ))
            if area.evaluation is not None:
                for revision in area.evaluation.revisions:
                    entries.append(EntityHistoryEntry(
                        revision.created_at,
                        marker_actor.get(revision.logical_id, "—"),
                        "Assessment completed" if revision.status == "completed" else "Assessment draft saved",
                        _assessment_result_details(revision),
                        "assessment", "assessment_evaluation", revision.logical_id,
                        revision.revision_number, f"evaluation:{revision.id}",
                    ))
            return self._sorted(entries)

    def _plain_audit_entries(self, audits: list[AuditLogEntry]) -> list[EntityHistoryEntry]:
        result = []
        for entry in audits:
            if entry.field_name in self._REVISION_MARKERS:
                continue
            result.append(EntityHistoryEntry(
                entry.created_at, _actor(entry.user), _audit_title(entry), _audit_details(entry),
                self._audit_category(entry), "audit", str(entry.id), None, f"audit:{entry.id}",
            ))
        return result

    @staticmethod
    def _audit_category(entry: AuditLogEntry) -> str:
        if entry.action in {"attach", "detach"} or (entry.field_name or "").startswith("attachment"):
            return "attachment"
        if (entry.field_name or "").startswith("link"):
            return "link"
        if entry.field_name == "archive_state":
            return "archive"
        return "change"

    @staticmethod
    def _technical_card_entries(revisions, event_type: str) -> list[EntityHistoryEntry]:
        entries: list[EntityHistoryEntry] = []
        previous = None
        for revision in revisions:
            payload = revision.payload_json or {}
            current_sections = _technical_sections(payload, event_type)
            previous_sections = _technical_sections(previous.payload_json or {}, event_type) if previous else {}
            labels = {
                "blast_design": "Blast design",
                "geomechanics": "Geomechanics",
                "execution": "Execution fact",
            }
            for key, value in current_sections.items():
                if previous is None:
                    if not _meaningful(value):
                        continue
                    title = f"{labels[key]} created"
                elif value != previous_sections.get(key):
                    if key == "execution" and _execution_initialized(payload) and not _execution_initialized(previous.payload_json or {}):
                        title = "Execution fact initialized from design"
                    else:
                        title = f"{labels[key]} updated"
                else:
                    continue
                geometry_number = revision.geometry_revision.revision_number if revision.geometry_revision else None
                details = f"Technical Card R{revision.revision_number}"
                if geometry_number is not None:
                    details += f" · Geometry R{geometry_number}"
                entries.append(EntityHistoryEntry(
                    revision.created_at, revision.author or "—", title, details,
                    key, "technical_card", revision.logical_id,
                    revision.revision_number, f"technical:{revision.id}:{key}",
                ))
            if revision.status == "completed":
                entries.append(EntityHistoryEntry(
                    revision.created_at, revision.author or "—", "Technical Card completed",
                    f"Technical Card R{revision.revision_number}", "technical_card",
                    "technical_card", revision.logical_id, revision.revision_number,
                    f"technical:{revision.id}:completed",
                ))
            previous = revision
        return entries

    @staticmethod
    def _sorted(entries: list[EntityHistoryEntry]) -> list[EntityHistoryEntry]:
        return sorted(entries, key=lambda item: (item.timestamp, item.sort_key), reverse=True)
