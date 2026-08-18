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
- Do not delete code merely because its path/name contains `prototype`, `legacy`, or `old`.
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
writers and concrete authentication/session services now live under
`infrastructure/`, and Qt widgets under `ui/widgets/`. Root `database/` and
`repositories/` remain an active, coupled ORM graph intentionally retained until
a focused move has more benefit than import churn. New adapters belong under
`infrastructure/`.

### Current migration state

Phase 4, 5A, 5B, and 5C are complete. Domain is the stable optimistic-concurrency owner; normal Assessment editing uses expected-version focused writes and has no whole-state save API. The reusable transaction guard can atomically protect multiple Domains for future moves.

Issue #79 architecture work established:

- 5C: COMPLETE — optimistic concurrency + removal of normal compatibility whole-state writes.
- 6A: COMPLETE — `AssessmentWorkspace` persistence container removed; Blast events and Assessment areas have direct Domain ownership, while persistence logical IDs use `logical_id`.
- 6B: COMPLETE — duplicate legacy engineering persistence and Block-owned attachment persistence removed; the revisioned Technical Card and AssessmentEntityAttachment remain canonical.
- 7A: COMPLETE — package/shim/dead-compatibility normalization.
- 7B code cleanup: COMPLETE — DXF import has a stable WCS/XYZ closure adapter contract.

Do not revive persistence models already removed by these phases or by later completed schema issues.

## Product model

```text
Project / Quarry
└── Domain
    ├── Blast events
    │   └── Horizon [virtual]
    │       ├── Production Block = BlastEvent(type='production')
    │       └── Contour Blast = BlastEvent(type='contour')
    └── Assessment areas
        └── Elevation Interval [virtual]
            └── Assessment Area
```

- Internal `Site` = user-facing Project / Quarry.
- Legacy `Mine` persistence has been removed. Do not reintroduce it or expose `Mine` in normal UI.
- Horizon and Interval are virtual groups, not DB entities.
- Project Lines belong to the whole Project/Site, are shared across Domains, and are managed from the Project dashboard.

## Blast events / Technical Card

There is one `BlastEvent` concept: `production` or `contour`.

- Keep one `Add blast event` action; do not split Production/Contour creation actions.
- Production `BlastEvent(event_type='production')` is itself the persisted user-facing Block; normal navigation opens the Block page.
- Do not reintroduce `BlastBlock`, `blast_blocks`, or `blast_event.blast_block_id` compatibility persistence.
- Contour `BlastEvent(event_type='contour')` opens the Contour Blast page and has no Geomechanics tab under the current product model.
- The revisioned BlastEvent Technical Card is the canonical active engineering record.
- Do not revive older parallel `RockMassProfile`, `RockStructure`, `BlastDesign`, `DrillingPattern`, `ChargeSegment`, or `ExplosiveType` persistence.
- Do not change Technical Card engineering formulas as collateral cleanup.

## Assessment

Current scoring is intentional:

- DAI = Design Achievement Index.
- FCI = Face Condition Index.
- Quadrant X = FCI; Y = DAI.
- Never replace them with an average.
- Dashboards/read models use stored completed evaluation results, not historical recalculation.

Assessment geometry is revisioned; boundary edits preserve history.

The current geometry model uses one continuous boundary operation that snaps/traces real Project Lines and uses explicit straight connectors where needed. Preserve frozen source-line provenance and a derived polygon. Do not implement the obsolete separate upper/lower-line selection workflow.

## Attachments

Each physical attachment has exactly one owner:

```text
Production BlastEvent (shown as Block) -> Photos / Documents
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

Normal source/default UI is English; Russian localization remains localization data where supported.

Preferred terminology: Project, Domain, Blast event, Production, Contour blast, Block, Assessment area, Project Lines, Horizon, Interval.

Avoid exposing Mine, Assessment Workspace, database implementation names, or prototype terminology.

Visual direction: compact professional engineering desktop software; light background, white cards/panels, subtle borders, restrained blue accent, existing SlopeForge SVG icons, minimal shadows, no excessive gradients or decorative animation.

Keep PySide6 / Qt Widgets. Do not migrate SlopeForge UI to QML/Qt Quick or a web framework unless the product architecture is explicitly changed.

## Repo-local UI skills

Codex-compatible repository skills live under `.agents/skills/` and are committed with the project. For UI work, load the relevant skill before proposing or editing production UI:

- `qt-ui-design` — `.agents/skills/qt-ui-design/SKILL.md`
  - Use for screen design, layout, navigation, information hierarchy, UX audit, accessibility, and visual consistency.
- `pyqt-widgets` — `.agents/skills/pyqt-widgets/SKILL.md`
  - Use for QWidget/dialog/form/table/tree/stack implementation, Qt layouts, signals, ownership, keyboard behavior, and widget lifecycle.
- `pyqt-styling` — `.agents/skills/pyqt-styling/SKILL.md`
  - Use for QSS, visual tokens, control states, cards, forms, tables, tabs, dialogs, and theme consistency.

For a broad UI redesign/refactor, use all three. For a narrow task, load only the relevant skills; do not add UI-skill context to unrelated persistence/domain work.

These skills are supporting guidance, not product authority. If generic upstream guidance conflicts with current `main`, the active issue, or SlopeForge invariants in this file, follow SlopeForge. In particular, generic Qt/QML examples must not cause a QML migration, and generic styling examples must not replace the established compact engineering-desktop direction.

Before deleting/replacing an existing UI component during a visual cleanup, classify it as `ACTIVE`, `ACTIVE_BUT_MISPLACED`, `COMPATIBILITY_ONLY`, or `DEAD` and preserve working business behavior.

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
