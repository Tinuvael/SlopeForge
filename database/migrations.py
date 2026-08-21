"""Alembic entry points that use already-resolved runtime settings."""
from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from .settings import Settings


def alembic_config(settings: Settings) -> Config:
    """Build Alembic configuration without changing process environment."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    config.attributes["database_url"] = settings.database_url
    return config


def upgrade_to_head(settings: Settings) -> None:
    """Apply the repository migration head using the supplied runtime URL."""
    command.upgrade(alembic_config(settings), "head")
