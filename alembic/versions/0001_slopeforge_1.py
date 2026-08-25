"""SlopeForge 1.0 PostgreSQL production baseline.

This is the final pre-1.0 consolidation of the disposable development migration
history. The database schema version stored by Alembic is intentionally ``1``.
After the SlopeForge 1.0 release this baseline is immutable; every physical schema
change must append a normal migration with ``down_revision = '1'`` (or the then
current head).

The frozen schema components live outside ``alembic/versions`` so Alembic sees
one revision only. They are exact snapshots of the pre-release migrations and
are executed here in dependency order.
"""
from __future__ import annotations

from pathlib import Path
import runpy

revision = "1"
down_revision = None
branch_labels = None
depends_on = None

_SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schema_v1"


def _run_component(name: str, action: str) -> None:
    namespace = runpy.run_path(str(_SCHEMA_DIR / f"{name}.py"))
    namespace[action]()


def upgrade() -> None:
    _run_component("core", "upgrade")
    _run_component("project_surfaces", "upgrade")
    _run_component("drillhole_datasets", "upgrade")


def downgrade() -> None:
    _run_component("drillhole_datasets", "downgrade")
    _run_component("project_surfaces", "downgrade")
    _run_component("core", "downgrade")
