# SlopeForge

SlopeForge is a desktop MVP for managing open-pit blast engineering data and final-wall assessments.

## Implemented MVP

- Projects (quarries) and Domains with engineering dashboards.
- Production and contour BlastEvents grouped by virtual Horizons.
- Production Blocks with general information, geomechanics, blast design, execution facts, and Technical Card revision history.
- Assessment Areas grouped by virtual Intervals, boundary drawing/refinement, linked blast events, and revision history.
- Existing DAI and FCI assessment matrices and quadrant presentation.
- Site-wide Project Lines imported from Datamine CSV files.
- BlastEvent-owned and assessment-evaluation-owned Photos and Documents.
- Tree navigation, search, status filters, and archived-item visibility.
- PostgreSQL persistence through SQLAlchemy and Alembic.
- Role-aware editor and read-only Viewer experiences.

The MVP does not provide PDF/Excel reports, GIS, AI recommendations, TARP, or automatic engineering recommendations.

## Database setup

SlopeForge uses PostgreSQL, SQLAlchemy 2.x, psycopg 3, Alembic, environment variables, and Argon2 password hashing. See [docs/database_setup.md](docs/database_setup.md).

## Development

```bash
pip install -r requirements.txt
alembic upgrade head
python main.py
```

Run the test suite without a display server:

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

PostgreSQL integration tests require an explicitly isolated database in `SLOPEFORGE_TEST_DATABASE_URL`; they never use the normal `DATABASE_URL` as a destructive test target.

## Disclaimer

SlopeForge is an engineering data-management and decision-support tool. It does not replace professional engineering judgement, site-specific investigations, or engineering design. Users are responsible for verifying engineering decisions and the suitability of blasting parameters for their conditions.

## Translations

English source text is canonical, and `translations/slopeforge_ru.ts` is the
source-controlled Russian catalogue. SlopeForge reads this XML file through a
Qt translator adapter, so normal source execution does not require Qt Linguist,
`pyside6-lrelease`, or a precompiled `.qm` file. A future packaged release may
optionally compile TS to QM as a build-time optimization.
