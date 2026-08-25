# PostgreSQL setup

SlopeForge uses PostgreSQL as its only application database through SQLAlchemy 2.x, psycopg 3, and Alembic. The retired desktop SQLite file is not a runtime or packaged asset.

## Install dependencies

```bash
python -m pip install -r requirements.txt
```

## Connection configuration

The normal desktop application stores named connection-profile metadata locally and asks the user to select a server before authentication. PostgreSQL passwords are not stored in the profile JSON; Windows builds keep them in Windows Credential Manager.

Saved profile metadata lives under the normal SlopeForge application configuration directory, on Windows:

```text
%APPDATA%\SlopeForge\connections.json
```

One installation may contain multiple independent server/database profiles. Each profile has a stable local identifier, display name, PostgreSQL host/port/database/user, a storage mode, and last-used metadata.

Two storage modes are supported:

- **Full** — PostgreSQL plus a configured shared file-storage directory. This is the normal site/workstation mode.
- **Database only** — PostgreSQL without physical shared storage. PostgreSQL-backed project, blast, assessment and attachment metadata remain available, while physical file preview/open/add/delete/import actions are unavailable and must not probe the missing network/share path.

`Database only` is a connection/storage mode, not an application permission role. SlopeForge `admin`, `editor`, and `viewer` permissions remain authoritative after the selected database authenticates the user.

### Environment-pinned deployment

Administratively managed single-server installations may still pin the runtime through environment variables or `.env`:

```env
DATABASE_URL=postgresql+psycopg://slopeforge_user:change-me@localhost:5432/slopeforge
STORAGE_ROOT=C:/SlopeForge/storage
```

A LAN PostgreSQL server and shared storage path are also valid:

```env
DATABASE_URL=postgresql+psycopg://slopeforge_user:change-me@192.168.1.20:5432/slopeforge
STORAGE_ROOT=//fileserver/SlopeForge/storage
```

If `DATABASE_URL` is set and `STORAGE_ROOT` is omitted, the pinned runtime is treated as `Database only`.

Environment configuration takes precedence over locally saved profiles. While `DATABASE_URL` pins the installation, interactive server switching is disabled. `.env` is ignored by Git; never commit credentials. Real process/system environment variables override `.env` values.

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

When the selected PostgreSQL database exists but has no user tables, SlopeForge applies the current Alembic baseline automatically. Automatic initialization is refused when an unversioned database already contains user tables or reports an incompatible migration revision.

On normal desktop startup:

1. SlopeForge shows `Select server` before SlopeForge user authentication unless a saved profile is configured to skip server selection.
2. `Add` / `Edit` collects and tests PostgreSQL settings plus optional Full-mode file storage.
3. A successful saved profile writes non-secret metadata to `connections.json` and its PostgreSQL password to Windows Credential Manager on Windows.
4. Only after a server profile is selected does SlopeForge create that profile's Engine / SessionFactory and authenticate the SlopeForge application user.
5. `Remember me on this server` stores a remember token separately for that connection profile; application-user passwords are not stored locally.

The former single `%APPDATA%\SlopeForge\connection.ini` format is migrated once when encountered. Its PostgreSQL password is moved to the credential store, the profile metadata is written to `connections.json`, and the plaintext legacy INI is removed after successful migration.

Manual Windows smoke check:

1. Start from no environment-pinned `DATABASE_URL` and no saved `connections.json`.
2. Launch SlopeForge; confirm `Select server` appears before the application login.
3. Add a Full profile, test it, connect, and sign in with `Remember me on this server` enabled.
4. Restart; confirm server selection appears again unless `Skip server selection on startup` was enabled, and confirm the remembered login is scoped to that server.
5. Add a second profile and switch to it from the header or `Settings → Connections`; confirm a clean new login/runtime is used.
6. Add a `Database only` profile with no storage path; confirm database-backed pages open and attachment metadata/counts render without probing physical shared files.

## First administrator

CLI setup:

```bash
python -m database.cli init
```

Or launch the desktop application:

```bash
python main.py
```

If there are no users in the selected database, the GUI can create the first administrator. Existing users prevent the first-admin flow from running again.

## Run SlopeForge

```bash
python main.py
```

Normal UI terminology is Project / Quarry and Domain. Internal `Site` is the persistence name for a user-facing Project; removed Mine terminology is not exposed in normal workflows.

## Attachment storage

Attachment metadata is stored in PostgreSQL. In a Full connection, physical files are stored under the configured file-storage root through the current storage/infrastructure layer.

In `Database only`, no substitute local attachment directory is created. Metadata and counts can be read from PostgreSQL, but physical file paths are unavailable. Physical preview/open/add/delete actions and source-file imports must remain disabled or fail before filesystem/network access.

Do not assume a database cascade removes physical files. File deletion/copy/move in Full mode must go through the application/storage workflow so rollback and one-owner semantics are preserved.

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