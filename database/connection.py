from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .settings import Settings


class DatabaseConnectionError(RuntimeError):
    pass


DEFAULT_CONNECT_TIMEOUT_SECONDS = 5


def create_database_engine(settings: Settings | None = None) -> Engine:
    settings = settings or Settings.from_env()
    # psycopg forwards connect_timeout to libpq. Keep an explicit URL value when
    # an administrator has intentionally configured a different timeout.
    query = make_url(settings.database_url).query
    connect_args = ({} if "connect_timeout" in query
                    else {"connect_timeout": DEFAULT_CONNECT_TIMEOUT_SECONDS})
    return create_engine(settings.database_url, pool_pre_ping=True, future=True,
                         connect_args=connect_args)


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=engine or create_database_engine(), autoflush=False, expire_on_commit=False)


def check_connection(engine: Engine | None = None) -> None:
    engine = engine or create_database_engine()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:
        raise DatabaseConnectionError(
            "Cannot connect to PostgreSQL. Check the server address, network, credentials, "
            "and that the target database exists. If necessary, contact your PostgreSQL administrator."
        ) from exc
    except SQLAlchemyError as exc:
        raise DatabaseConnectionError(f"PostgreSQL connection check failed: {exc}") from exc
