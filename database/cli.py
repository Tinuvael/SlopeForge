from __future__ import annotations

import argparse
import getpass
import re
import sys

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, ProgrammingError, SQLAlchemyError

from .connection import check_connection, create_database_engine, create_session_factory, DatabaseConnectionError
from .models import User
from .settings import ConfigurationError, Settings


def alembic_config() -> Config:
    return Config("alembic.ini")


def prepare_db() -> int:
    try:
        settings = Settings.from_env()
        url = make_url(settings.database_url)
        db_name = url.database
        if not db_name or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", db_name):
            print("Database name must contain only letters, digits, and underscores, and must not start with a digit.", file=sys.stderr)
            return 1
        admin_url = url.set(database="postgres")
        engine = create_engine(admin_url, isolation_level="AUTOCOMMIT", pool_pre_ping=True)
        with engine.connect() as conn:
            exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": db_name}).scalar()
            if exists:
                print(f"Database '{db_name}' already exists.")
                return 0
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            print(f"Database '{db_name}' created.")
        return 0
    except (OperationalError, ProgrammingError) as exc:
        print(
            "Cannot create target PostgreSQL database automatically. "
            "Ask an administrator to create it, for example:\n"
            "  createdb slopeforge\n"
            f"Details: {exc}",
            file=sys.stderr,
        )
        return 1
    except ConfigurationError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1


def migrate() -> int:
    command.upgrade(alembic_config(), "head")
    return 0


def migration_status() -> int:
    command.current(alembic_config(), verbose=True)
    return 0


def init_app() -> int:
    try:
        engine = create_database_engine()
        check_connection(engine)
        command.upgrade(alembic_config(), "head")
        Session = create_session_factory(engine)
        with Session.begin() as session:
            user_count = session.scalar(select(func.count(User.id))) or 0
            if user_count > 0:
                print("Users table is not empty. First administrator was not created again.")
                return 0
            username = input("First admin username: ").strip()
            full_name = input("Full name (optional): ").strip() or None
            password = getpass.getpass("Password: ")
            password_repeat = getpass.getpass("Repeat password: ")
            if password != password_repeat:
                print("Passwords do not match.", file=sys.stderr)
                return 1
            from .users import FirstAdminAlreadyExistsError, create_first_admin_with_lock
            try:
                create_first_admin_with_lock(session, username=username, password=password, full_name=full_name)
            except FirstAdminAlreadyExistsError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(f"First administrator '{username}' created.")
        return 0
    except (ConfigurationError, DatabaseConnectionError, SQLAlchemyError) as exc:
        print(f"Initialization failed: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SlopeForge PostgreSQL database utilities")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("prepare-db", help="Create target PostgreSQL database if permitted")
    sub.add_parser("migrate", help="Apply Alembic migrations")
    sub.add_parser("migration-status", help="Show current Alembic migration state")
    sub.add_parser("init", help="Initial setup and first administrator creation")
    args = parser.parse_args(argv)
    return {"prepare-db": prepare_db, "migrate": migrate, "migration-status": migration_status, "init": init_app}[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
