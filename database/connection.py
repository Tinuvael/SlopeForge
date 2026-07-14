from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .settings import Settings


class DatabaseConnectionError(RuntimeError):
    pass


def create_database_engine(settings: Settings | None = None) -> Engine:
    settings = settings or Settings.from_env()
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or create_database_engine(), autoflush=False, expire_on_commit=False)


def check_connection(engine: Engine | None = None) -> None:
    engine = engine or create_database_engine()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:
        raise DatabaseConnectionError(
            "Cannot connect to PostgreSQL. Check DATABASE_URL, network access, credentials, "
            "and that the target database exists. If the database does not exist, run "
            "`python -m database.cli prepare-db` or ask your PostgreSQL administrator to create it."
        ) from exc
    except SQLAlchemyError as exc:
        raise DatabaseConnectionError(f"PostgreSQL connection check failed: {exc}") from exc
