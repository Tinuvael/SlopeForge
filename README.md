# SlopeForge

SlopeForge is a desktop MVP for managing open-pit blast engineering data and final-wall assessments.

## Implemented MVP

- Projects (quarries) and Domains with engineering dashboards.
- Production and contour BlastEvents grouped by virtual Horizons.
- Production Blocks with general information, geomechanics, blast design, execution facts, and Technical Card revision history.
- Assessment Areas grouped by virtual Intervals, boundary drawing/refinement, linked blast events, and revision history.
- Existing DAI and FCI assessment matrices and quadrant presentation.
- Site-wide Project Lines imported from Datamine CSV or supported DXF 2D/3D polylines.
- BlastEvent-owned and assessment-evaluation-owned Photos and Documents.
- Tree navigation, search, status filters, and archived-item visibility.
- Project-level Excel report generation from stored application data/results.
- PostgreSQL persistence through SQLAlchemy and Alembic.
- Role-aware editor and read-only Viewer experiences.

## Geometry import formats

Project Lines and Blast geometry accept Datamine CSV and supported DXF 2D/3D polylines.
DXF import is intentionally limited to straight `LWPOLYLINE`, 2D `POLYLINE`,
and 3D `POLYLINE` entities in modelspace. Curved segments are rejected; SPLINE,
ARC, mesh, polyface, and INSERT entities are not processed.

The MVP does not provide PDF reports, GIS, AI recommendations, TARP, or automatic engineering recommendations.

## Database setup

SlopeForge uses PostgreSQL as its only application database, with SQLAlchemy 2.x, psycopg 3, Alembic, environment variables, and Argon2 password hashing. The desktop package does not bundle a SQLite database. See [docs/database_setup.md](docs/database_setup.md).

### Connection configuration

On a normal first launch without a complete `DATABASE_URL` / `STORAGE_ROOT` environment configuration, SlopeForge opens a connection setup dialog before the login dialog. The user configures PostgreSQL host, port, database, user/password, and the shared attachment-storage folder, then tests and saves the configuration.

The same values can be edited later from `Settings > Connection`. Saved changes take effect after restarting SlopeForge so the running application never switches databases or storage roots halfway through a session.

On Windows the saved profile is stored in `%APPDATA%\SlopeForge\connection.ini`. `DATABASE_URL` and `STORAGE_ROOT` remain supported for development/administration and, when both are present, override the saved profile.

MVP limitation: the saved PostgreSQL password is currently stored in the per-user connection INI file rather than Windows Credential Manager. Do not share that file. Moving the secret to Windows-native credential storage can be done as a focused security hardening follow-up without changing the connection UI contract.

## Development

Repository-wide agent/development rules are in [AGENTS.md](AGENTS.md). Current architecture documentation is indexed in [docs/README.md](docs/README.md).

```bash
pip install -r requirements.txt
alembic upgrade head
python main.py
```

Run the test suite without a display server:

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

PostgreSQL integration tests require an explicitly isolated database in `TEST_DATABASE_URL`; destructive tests refuse obviously non-test database names. Never point it at the normal `DATABASE_URL`.

## Disclaimer

SlopeForge is an engineering data-management and decision-support tool. It does not replace professional engineering judgement, site-specific investigations, or engineering design. Users are responsible for verifying engineering decisions and the suitability of blasting parameters for their conditions.

## Translations

English source text is canonical, and `translations/slopeforge_ru.ts` is the
source-controlled Russian catalogue. SlopeForge reads this XML file through a
Qt translator adapter, so normal source execution does not require Qt Linguist,
`pyside6-lrelease`, or a precompiled `.qm` file. A future packaged release may
optionally compile TS to QM as a build-time optimization.

## Domain Geometry

A Domain may optionally have a lightweight plan-view reference footprint. It can be imported from CSV/DXF or drawn manually, and may contain multiple disconnected polygons. Imported 3D geometry is projected to XY. Domain Geometry is visual context only: it does not create 3D solids or automatically assign any object to a Domain.
