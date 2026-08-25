from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect
from sqlalchemy.orm import configure_mappers

from .base import Base
from . import assessment_models  # noqa: F401  Register required Assessment tables.
from . import drillhole_models  # noqa: F401  Register required drillhole tables.
from . import project_surface_models  # noqa: F401  Register required surface tables.
from .models import User  # noqa: F401  Register core tables.


class SchemaCompatibilityState(str, Enum):
    UP_TO_DATE = "up_to_date"
    UPGRADE_REQUIRED = "upgrade_required"
    NEWER_THAN_RELEASE = "newer_than_release"
    UNKNOWN_OR_UNSUPPORTED = "unknown_or_unsupported"


@dataclass(frozen=True)
class SchemaCompatibilityReport:
    current_heads: tuple[str, ...]
    required_head: str
    state: SchemaCompatibilityState

    @property
    def current_revision(self) -> str | None:
        return self.current_heads[0] if len(self.current_heads) == 1 else None


def alembic_script() -> ScriptDirectory:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    return ScriptDirectory.from_config(config)


def expected_alembic_head() -> str:
    heads = alembic_script().get_heads()
    if len(heads) != 1:
        rendered = ", ".join(heads) if heads else "none"
        raise RuntimeError(
            f"The application migration graph must have exactly one head; found: {rendered}."
        )
    return heads[0]


def database_alembic_heads(engine) -> tuple[str, ...]:
    with engine.connect() as connection:
        return tuple(MigrationContext.configure(connection).get_current_heads())


def known_alembic_revisions() -> frozenset[str]:
    return frozenset(revision.revision for revision in alembic_script().walk_revisions())


def _numeric_revision(revision: str) -> int | None:
    return int(revision) if revision.isdecimal() else None


def classify_schema_compatibility(
    current_heads: tuple[str, ...],
    required_head: str,
    known_revisions: frozenset[str] | set[str],
) -> SchemaCompatibilityReport:
    if current_heads == (required_head,):
        state = SchemaCompatibilityState.UP_TO_DATE
    elif len(current_heads) != 1:
        state = SchemaCompatibilityState.UNKNOWN_OR_UNSUPPORTED
    else:
        current = current_heads[0]
        current_number = _numeric_revision(current)
        required_number = _numeric_revision(required_head)
        if (
            current_number is not None
            and required_number is not None
            and current_number > required_number
        ):
            # Production releases use monotonically increasing integer revisions.
            # An integer above this release's head belongs to a newer SlopeForge.
            state = SchemaCompatibilityState.NEWER_THAN_RELEASE
        elif current in known_revisions:
            # A recognized non-head revision is a safe, known migration ancestor.
            state = SchemaCompatibilityState.UPGRADE_REQUIRED
        else:
            # Never guess that an unknown revision is safe to migrate. This also
            # covers legacy development revisions and divergent histories.
            state = SchemaCompatibilityState.UNKNOWN_OR_UNSUPPORTED
    return SchemaCompatibilityReport(
        current_heads=tuple(current_heads),
        required_head=required_head,
        state=state,
    )


def inspect_schema_compatibility(engine) -> SchemaCompatibilityReport:
    required = expected_alembic_head()
    current = database_alembic_heads(engine)
    return classify_schema_compatibility(
        current,
        required,
        known_alembic_revisions(),
    )


def missing_required_tables(engine) -> tuple[str, ...]:
    """Return required ORM tables missing from an otherwise version-compatible DB."""
    configure_mappers()
    existing = set(inspect(engine).get_table_names())
    required = set(Base.metadata.tables)
    return tuple(sorted(required - existing))
