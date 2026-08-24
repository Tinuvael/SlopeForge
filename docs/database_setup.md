# PostgreSQL setup

SlopeForge uses PostgreSQL as its only application database through SQLAlchemy 2.x, psycopg 3, and Alembic. The retired desktop SQLite file is not a runtime or packaged asset.

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

Do not use `alembic stamp` to hide a physical schema mismatch.

### SlopeForge 1 baseline reset

Immediately before the SlopeForge 1.0 release, the disposable development
migration chain was consolidated into one production baseline. Alembic revision
`1` is therefore the complete SlopeForge 1.0 database schema.

Databases carrying any former pre-1.0 development revision are **not** supported
upgrade origins. They must be recreated before release; do not stamp them to
revision `1`. For the one-time transition on Windows, close SlopeForge and
recreate only disposable development/test databases from PowerShell (replace the
database owner if needed):

```powershell
dropdb --if-exists --username postgres slopeforge
createdb --username postgres --owner slopeforge_user slopeforge
dropdb --if-exists --username postgres slopeforge_test
createdb --username postgres --owner slopeforge_user slopeforge_test
python -m alembic upgrade head
python -m database.cli migration-status
```

The final commands read `DATABASE_URL` from `.env`. `migration-status` should
report Alembic head/revision `1`.

After SlopeForge 1.0 is released, revision `1` and its frozen schema snapshot are
immutable. Every later physical schema change must append a normal Alembic
migration after the current head and must preserve production data as required.

### GUI first-run initialization

When the configured PostgreSQL database exists but has no user tables, SlopeForge
applies the current Alembic baseline automatically. The connection may come from
environment variables, the connection dialog, or the saved
`%APPDATA%\SlopeForge\connection.ini`; a temporary `.env` is not required.
Automatic initialization is refused when an unversioned database already contains
user tables or reports an obsolete migration revision.

Manual Windows smoke check:

1. Remove `.env` and `%APPDATA%\SlopeForge\connection.ini`.
2. Drop and recreate `slopeforge` as an empty PostgreSQL database.
3. Launch SlopeForge and enter the connection and storage paths in the connection dialog.
4. Confirm that baseline revision `1` is applied and the first-administrator dialog appears.
5. Restart SlopeForge; the saved connection should open normally without showing the connection dialog again.

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

Normal UI terminology is Project / Quarry and Domain. Internal `Site` is the persistence name for a user-facing Project; removed Mine terminology is not exposed in normal workflows.

## Attachment storage

Attachment metadata is stored in PostgreSQL; physical files are stored under `STORAGE_ROOT` through the current storage/infrastructure layer.

Do not assume a database cascade removes physical files. File deletion/copy/move must go through the application/storage workflow so rollback and one-owner semantics are preserved.

## Tests

Fast/normal development checks:

```bash
pytest <relevant tests>
python tools/architecture_audit.py
python -m compileall app application domain infrastructure database repositories ui
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
4. Run `python -m database.cli migration-status` and confirm revision `1`.
5. Launch `python main.py` and create the first administrator.
6. Exercise a minimal Project → Domain → Blast Event / Assessment Area flow appropriate to the current release.
7. Restart and confirm persisted data remains available.

For the complete release-candidate manual pass, see `docs/release_checklist.md`.
