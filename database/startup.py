from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from .base import Base
from .connection import check_connection, create_database_engine, create_session_factory
from .models import User  # noqa: F401
from .settings import ConfigurationError, Settings, safe_database_location


class StartupError(RuntimeError):
    def __init__(self, message: str, server: str | None = None):
        super().__init__(message)
        self.server = server


def initialize_database_runtime():
    try:
        settings = Settings.from_env()
        engine = create_database_engine(settings)
        check_connection(engine)
        if settings.is_sqlite_dev:
            Base.metadata.create_all(engine)
        existing = set(inspect(engine).get_table_names())
        required = set(Base.metadata.tables)
        missing = sorted(required - existing)
        if missing:
            raise StartupError(
                "В базе не найдены нужные таблицы: " + ", ".join(missing[:8]) + ("..." if len(missing) > 8 else ""),
                safe_database_location(settings.database_url),
            )
        return settings, engine, create_session_factory(engine)
    except ConfigurationError as exc:
        raise StartupError(str(exc)) from exc
    except SQLAlchemyError as exc:
        server = None
        try:
            server = safe_database_location(Settings.from_env().database_url)
        except Exception:
            server = None
        raise StartupError("Не удалось подключиться к базе или проверить таблицы.", server) from exc
