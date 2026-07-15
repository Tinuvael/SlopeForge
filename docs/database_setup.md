# SlopeForge PostgreSQL setup

SlopeForge keeps the PySide desktop entry point (`python main.py`). New MVP data (users, mines, sites, blast blocks) goes to PostgreSQL only. Legacy SQLite code remains isolated for old UI parts that are not migrated yet.

## Install dependencies

```bash
python -m pip install -r requirements.txt
```

## Create `.env`

Copy the example and edit credentials/paths.

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
notepad .env
```

Example local PostgreSQL:

```env
DB_MODE=postgresql
DATABASE_URL=postgresql+psycopg://slopeforge_user:change-me@localhost:5432/slopeforge
STORAGE_ROOT=C:/SlopeForge/storage
```

Example PostgreSQL on a LAN server:

```env
DB_MODE=postgresql
DATABASE_URL=postgresql+psycopg://slopeforge_user:change-me@192.168.1.20:5432/slopeforge
STORAGE_ROOT=//fileserver/SlopeForge/storage
```

`.env` is ignored by Git. Real system environment variables have priority over values from `.env`. Never commit passwords.


## Temporary SQLite development mode

PostgreSQL remains the production/default backend. For quick local development only, you can start a temporary SQLite mode. Do not use it for working mine data, multi-user work, or production. There is no automatic SQLite-to-PostgreSQL data migration.

Expected `.env` for SQLite development:

```env
DB_MODE=sqlite-dev
DATABASE_URL=sqlite:///slopeforge_dev.db
STORAGE_ROOT=C:/SlopeForge/storage
```

Windows PowerShell quick start:

```powershell
$env:DB_MODE = 'sqlite-dev'
$env:DATABASE_URL = 'sqlite:///slopeforge_dev.db'
$env:STORAGE_ROOT = 'C:/SlopeForge/storage'
python -m database.cli prepare-db
python main.py
```

In `sqlite-dev`, schema creation uses `Base.metadata.create_all()` intentionally and only for local development. Alembic migrations remain the PostgreSQL workflow. First-admin creation uses only an in-process lock in this mode; it is not protection for several computers or several independent application processes.

## Prepare database

The app reads `.env` automatically, but command examples can also export variables explicitly.

Linux/macOS:

```bash
set -a; source .env; set +a
python -m database.cli prepare-db
```

Windows PowerShell:

```powershell
Get-Content .env | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') { [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process') }
}
python -m database.cli prepare-db
```

If your PostgreSQL user cannot create databases, ask an administrator to create `slopeforge` and grant access.

## Run migrations

Linux/macOS:

```bash
python -m database.cli migrate
python -m database.cli migration-status
```

Windows PowerShell:

```powershell
python -m database.cli migrate
python -m database.cli migration-status
```

## First administrator and login

CLI setup:

```bash
python -m database.cli init
```

GUI setup:

```bash
python main.py
```

If the `users` table is empty, the GUI shows a first-admin dialog. The first user becomes `admin`; later users do not automatically become admins. If users already exist, the GUI shows the login dialog.

## Minimal manual scenario

1. Install dependencies.
2. Create and edit `.env` with `DB_MODE=postgresql` for real PostgreSQL work.
3. Run `python -m database.cli prepare-db` if the database does not exist.
4. Run `python -m database.cli migrate`.
5. Run `python main.py`.
6. Create first administrator.
7. Log in.
8. Open `Справочники`, create a mine and a site.
9. Click `Новый блок`, fill common block fields, save.
10. Close and restart the app.
11. Log in again, find the saved block, open and edit it.

## Attachment storage

Files are stored on disk under `STORAGE_ROOT`, not inside PostgreSQL. The database stores only relative paths like:

```text
mine_<id>/site_<id>/block_<id>/attachments/<unique_file_name>
```

Physical files are deleted only by an explicit storage operation, not by cascade from database rows.

## Tests

```bash
pytest
python -m compileall database repositories services ui tests alembic
```

PostgreSQL integration tests are skipped unless `TEST_DATABASE_URL` is set:

Linux/macOS:

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:password@host:5432/slopeforge_test pytest
```

Windows PowerShell:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://user:password@host:5432/slopeforge_test'
pytest
```

Do not use SQLite as a replacement for PostgreSQL integration tests.
