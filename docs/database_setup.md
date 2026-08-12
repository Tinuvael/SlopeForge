# PostgreSQL setup

SlopeForge uses PostgreSQL as its application database through SQLAlchemy 2.x, psycopg 3, and Alembic.

## Install dependencies

```bash
python -m pip install -r requirements.txt
```

## Configure environment

Copy `.env.example` to `.env` and set the local database/storage values.

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
notepad .env
```

Example:

```env
DATABASE_URL=postgresql+psycopg://slopeforge_user:change-me@localhost:5432/slopeforge
STORAGE_ROOT=C:/SlopeForge/storage
```

A LAN PostgreSQL server and shared storage path are also valid, for example:

```env
DATABASE_URL=postgresql+psycopg://slopeforge_user:change-me@192.168.1.20:5432/slopeforge
STORAGE_ROOT=//fileserver/SlopeForge/storage
```

`.env` is ignored by Git. Never commit credentials. Real process/system environment variables override `.env` values.

## Create the database

If the configured PostgreSQL user can create databases:

```bash
python -m database.cli prepare-db
```

If it cannot, create the database with an administrator account and grant the application user access.

## Apply migrations

```bash
python -m database.cli migrate
python -m database.cli migration-status
```

Do not use `alembic stamp` to hide a physical schema mismatch. During MVP development the current development data is disposable, so it is acceptable to recreate the development database when a clean schema migration/rebuild is simpler than preserving test records.

## First administrator

CLI setup:

```bash
python -m database.cli init
```

Or launch the desktop application:

```bash
python main.py
```

If there are no users, the GUI can create the first administrator. Existing users prevent the first-admin flow from running again.

## Run SlopeForge

```bash
python main.py
```

Normal UI terminology is Project / Quarry and Domain. Legacy internal `Mine`/`Site` names may still exist in transitional persistence code while architecture issue #79 is open, but they should not be exposed in normal user workflows.

## Attachment storage

Attachment metadata is stored in PostgreSQL; physical files are stored under `STORAGE_ROOT` through the current storage/infrastructure layer.

Do not assume a database cascade removes physical files. File deletion/copy/move must go through the application/storage workflow so rollback and one-owner semantics are preserved.

## Tests

Fast/normal development checks:

```bash
pytest <relevant tests>
python tools/architecture_audit.py
python -m compileall app application domain infrastructure database repositories services ui widgets
git diff --check
```

For Qt tests without a display server:

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

### PostgreSQL integration tests

Destructive PostgreSQL/Alembic integration tests run only when `TEST_DATABASE_URL` is set.
Use a dedicated database whose database name clearly contains `test`.

Linux/macOS:

```bash
TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/slopeforge_test \
QT_QPA_PLATFORM=offscreen pytest -q
```

Windows PowerShell:

```powershell
$env:TEST_DATABASE_URL = 'postgresql+psycopg://user:password@localhost:5432/slopeforge_test'
$env:QT_QPA_PLATFORM = 'offscreen'
pytest -q
```

Never point `TEST_DATABASE_URL` at the normal development or production database. Migration integration tests intentionally perform upgrade/downgrade cycles and may destroy data in the target test database.

## Clean-database validation

For schema/architecture release checks:

1. Use a new disposable PostgreSQL database.
2. Set `DATABASE_URL` to that database.
3. Run `python -m database.cli migrate`.
4. Run `python -m database.cli migration-status` and confirm the expected head.
5. Launch `python main.py` and create the first administrator.
6. Exercise a minimal Project → Domain → Blast Event / Assessment Area flow appropriate to the current MVP.
7. Restart and confirm persisted data remains available.

For the complete release-candidate manual pass, see `docs/release_checklist.md`.