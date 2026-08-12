# SlopeForge Agent Guide

## What this project is

SlopeForge is a Python 3.12 / PySide6 desktop application for open-pit geotechnical and blasting engineering. PostgreSQL, SQLAlchemy 2.x, psycopg 3, and Alembic provide persistence.

## Source of truth

When information conflicts, use this order:

1. Current `main` code, schema, migrations, and tests.
2. The explicit GitHub issue / PR scope being implemented.
3. Product/architecture invariants in this file.
4. Current maintained documents in `docs/`.

For current code, architecture, bugs, or PR review, inspect the repository first. Do not implement from old conversation context or historical docs when `main` differs.

## Work discipline

- One logical issue/task -> one focused PR unless the issue explicitly defines staged PRs.
- Do not broaden scope because adjacent code looks improvable; report/open a separate issue.
- Before deleting/moving legacy-looking code, classify it as `ACTIVE`, `ACTIVE_BUT_MISPLACED`, `COMPATIBILITY_ONLY`, or `DEAD` using callers/tests/migrations/packaging evidence.
- Do not delete code merely because its path/name contains `prototype`, `legacy`, `old`, or `Mine`.
- Preserve proven engineering algorithms unless the issue explicitly requests redesign.
- Do not merge PRs unless the user explicitly asks.

## Architecture

Target dependency direction:

```text
PySide6 UI
  -> Application commands / queries / ports
    -> Domain models and policies
      <- Infrastructure adapters
```

- `domain/`: pure business/engineering models and policies. No PySide6, SQLAlchemy/PostgreSQL, desktop dialogs, filesystem UI, or Excel libraries.
- `application/`: use-case orchestration, ports/UoW, transactions, rollback semantics, read/write workflows. No PySide6.
- `infrastructure/`: PostgreSQL/SQLAlchemy, files, geometry import, report writers, external adapters.
- `ui/`: Qt presentation, interaction state, pages/dialogs/widgets/navigation.
- `app/` + `main.py`: bootstrap, configuration, localization, dependency wiring.
- Do not add microservices or interface-per-class ceremonial abstractions without a real boundary need.

Root `reports/`, `widgets/`, and `services/` were retired in Phase 7A. Report
writers and concrete authentication/session/Block services now live under
`infrastructure/`, and Qt widgets under `ui/widgets/`. Root `database/` and
`repositories/` remain an active, coupled ORM graph intentionally retained until
a focused move has more benefit than import churn. New adapters belong under
`infrastructure/`.

### Current migration state

Phase 4, 5A, 5B, and 5C are complete. Domain is the stable optimistic-concurrency owner; normal Assessment editing uses expected-version focused writes and has no whole-state save API. The reusable transaction guard can atomically protect multiple Domains for future #75 work, but Domain moves are not implemented.

Issue #79 is the architecture gate:

- 5C: COMPLETE — optimistic concurrency + removal of normal compatibility whole-state writes.
- 6A: COMPLETE — `AssessmentWorkspace` was a persistence-only container and is removed; Blast events and Assessment areas now have direct Domain ownership, while persistence logical IDs use `logical_id`.
- 6B: COMPLETE — duplicate legacy engineering persistence and Block-owned attachments are removed; the revisioned Technical Card and AssessmentEntityAttachment remain canonical.
- 7A: COMPLETE — package/shim/dead-compatibility normalization.
- 7B: NEXT — DXF debt, PostgreSQL-from-scratch verification, Windows/Python 3.12 validation, and final architecture freeze.

Do not build persistence-heavy new workflows on ownership that #79 is scheduled to remove.

## Product model

```text
Project / Quarry
└── Domain
    ├── Blast events
    │   └── Horizon [virtual]
    │       ├── Production Block
    │       └── Contour BlastEvent
    └── Assessment areas
        └── Elevation Interval [virtual]
            └── Assessment Area
```

- Internal `Site` = user-facing Project / Quarry.
- Legacy `Mine` must not appear in normal UI.
- Horizon and Interval are virtual groups, not DB entities.
- Project Lines belong to the whole Project/Site, are shared across Domains, and are managed from the Project dashboard.

## Blast events / Technical Card

There is one `BlastEvent` concept: `production` or `contour`.

- Keep one `Add blast event` action; do not split Production/Contour creation actions.
- Production BlastEvent is linked 1:1 to `BlastBlock`; normal navigation opens Block.
- Do not double-count Block + linked BlastEvent in dashboards/reports.
- Contour has no BlastBlock and no Geomechanics tab under the current product model.
- The revisioned BlastEvent Technical Card is the canonical active engineering record.
- Do not revive older parallel `RockMassProfile`, `RockStructure`, `BlastDesign`, `DrillingPattern`, `ChargeSegment`, or `ExplosiveType` persistence before #79 classification.
- Do not change Technical Card engineering formulas as collateral cleanup.

## Assessment

Current scoring is intentional:

- DAI = Design Achievement Index.
- FCI = Face Condition Index.
- Quadrant X = FCI; Y = DAI.
- Never replace them with an average.
- Dashboards/read models use stored completed evaluation results, not historical recalculation.

Assessment geometry is revisioned; boundary edits preserve history.

Issue #80 defines the target geometry model: one continuous boundary operation that snaps/traces real Project Lines and uses explicit straight connectors where needed. Preserve frozen source-line provenance and a derived polygon. Do not implement the obsolete separate upper/lower-line selection workflow.

## Attachments

Each physical attachment has exactly one owner:

```text
Production Block -> linked production BlastEvent -> Photos / Documents
Contour BlastEvent -> Photos / Documents
Assessment Area -> Assessment evaluation -> Photos / Documents
```

Do not introduce duplicate/shared physical ownership unless explicitly requested.

## Database / migrations

The current development DB is disposable during MVP work. Prefer a clean correct schema over complicated compatibility solely for dev/test records.

Still:

- use proper Alembic migrations for physical schema changes;
- keep one Alembic head;
- never use `alembic stamp` to mask an incompatible schema;
- never run destructive tests against normal `DATABASE_URL`;
- PostgreSQL integration tests use a dedicated `TEST_DATABASE_URL` whose database name clearly indicates a test DB.

## Future analytics / ML readiness

Post-MVP, accumulated geomechanical, blast-design, execution, geometry, and Assessment data should support statistical analysis and possible ML experiments.

Preserve stable identities, explicit relations, revision history, timestamps/authors, planned vs actual facts, exact event/Assessment revision provenance, frozen engineering inputs, and stored completed DAI/FCI results.

Do **not** add an ML subsystem, feature store, warehouse, or recommendations during MVP cleanup. Future analytics should use dedicated read projections/views/materialized views/ETL over the clean transactional model.

## UI conventions

Normal source/default UI is English; Russian localization must also be complete where active.

Preferred terminology: Project, Domain, Blast event, Production, Contour blast, Block, Assessment area, Project Lines, Horizon, Interval.

Avoid exposing Mine, Assessment Workspace, or prototype terminology.

Visual direction: compact professional engineering desktop software; light background, white cards, subtle borders, restrained blue accent, existing SlopeForge SVG icons, no excessive gradients/shadows/animation.

## Testing policy

For every PR:

```bash
pytest <relevant tests>
python tools/architecture_audit.py
python -m compileall app application domain infrastructure database repositories ui
git diff --check
```

Use `QT_QPA_PLATFORM=offscreen` when required by Qt tests.

Also run the full suite for architecture, persistence/schema/Alembic, geometry-core changes, broad cross-cutting refactors, and before merge / release-candidate validation:

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

## Ready-for-review checklist

- Scope matches the issue; no drive-by redesign.
- Final diff has no new duplicate source of truth.
- Focused regression tests cover the change.
- Revision/rollback/concurrency semantics are preserved where relevant.
- Windows / Python 3.12 is considered.
- Current docs are updated only when behavior/architecture actually changed.
- Known unrelated failures are reported, not opportunistically fixed.
