# SlopeForge architecture

This document describes the current architecture on `main` and the intended MVP end state.
For implementation work, current code/tests and the active GitHub issue always take precedence over historical text.

## Current status

SlopeForge is a pragmatic modular monolith built with Python 3.12, PySide6, PostgreSQL, SQLAlchemy 2.x, psycopg 3, and Alembic.

Completed architecture work:

- Phase 3: active domain/geometry/import/attachment logic was moved out of `prototype_2d`; the package was removed.
- Phase 4: application use cases own the important multi-step workflows; Qt UI no longer owns core transactions.
- Phase 5A: whole-state Assessment persistence stopped deleting/recreating the workspace graph on ordinary synchronization.
- Phase 5B: normal application writes became focused operations for BlastEvent, Technical Card, Assessment geometry, links, evaluations, archive state, and attachment metadata.
- Phase 5C: `Domain.version` became the stable optimistic-concurrency owner. Focused writes use expected-version CAS in the same transaction, and normal Assessment editing no longer has a whole-state save API. The guard supports deterministic multi-Domain transactions for future #75 work, but moves are not implemented.

`AssessmentStateRepository` is read-only: the retired whole-state synchronization
implementation was deleted rather than retained as test support. Block pages use the
editing controller's current version as their single token, so a successful Technical
Card, geometry, or attachment write cannot make a later Block edit self-stale.

Phase 5C is complete. Phase 6A (Assessment ownership/schema normalization) is the next architecture phase; issue #79 as a whole is not complete.

## Dependency direction

Target dependency direction:

```text
ui/ (PySide6 presentation)
    -> application/ (commands, queries, ports, orchestration)
        -> domain/ (business and engineering models/policies)

infrastructure/ implements application ports and talks to PostgreSQL/files/import/export.
app/ + main.py compose the desktop application.
```

Layer rules:

- `domain/` must stay independent of PySide6, SQLAlchemy/PostgreSQL, dialogs, desktop APIs, filesystem UI, and report libraries.
- `application/` may depend on domain abstractions but not on PySide6.
- `infrastructure/` owns external I/O and framework-specific adapters.
- `ui/` owns widgets, pages, dialogs, visual interaction state, and navigation.
- `app/` / `main.py` own bootstrap, configuration, localization, and dependency construction.

Do not introduce interfaces/repositories mechanically for every class. Add boundaries when they isolate I/O, transactions, or testable business behavior.

## Transitional packages

The repository still has root-level packages created before the canonical layering was established:

- `database/`
- `repositories/`
- `services/`
- `reports/`
- `widgets/`

They are not automatically dead. Some are active runtime code and some contain compatibility/legacy paths.
Issue #79 Phase 6/7 must classify each relevant path as `ACTIVE`, `ACTIVE_BUT_MISPLACED`, `COMPATIBILITY_ONLY`, or `DEAD` before moving/removing it.

## Product ownership model

User-facing hierarchy:

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

Implementation notes:

- Internal `Site` is the user-facing Project/Quarry.
- Legacy `Mine` is temporary compatibility and must not appear in normal UI.
- Horizon and Elevation Interval are virtual read-model/tree groups, not database entities.
- Project Lines are Project/Site-wide reference geometry shared by every Domain.
- Multiple Project Lines datasets may exist historically; one is active.

## BlastEvent / Block model

`BlastEvent` is one concept with `production` and `contour` types.

Production:

- exactly one linked `BlastBlock` in the normal model;
- navigation normally opens the Block page;
- Block + linked event must not be double-counted in dashboards/reports.

Contour:

- no `BlastBlock`;
- navigation opens the Contour Blast page;
- no Geomechanics tab under the current product model.

The revisioned BlastEvent Technical Card is the canonical active engineering record for geomechanics/blast design/execution. Older parallel engineering tables in `database/models.py` must be classified under #79 before #77/#78; do not create two sources of engineering truth.

## Assessment model

Assessment Area identity is stable and geometry is revisioned.

The existing DAI/FCI scoring is intentionally preserved:

- DAI = Design Achievement Index.
- FCI = Face Condition Index.
- Quadrant X = FCI, Y = DAI.
- Completed historical results are stored and read, not silently recalculated for dashboards.

Current `main` still contains the older horizontal-line/polygon geometry workflow. Issue #80 defines the target replacement: a single continuous boundary traced/snapped along Project Lines with explicit straight connectors and frozen source-line provenance. A derived plan polygon remains available for rendering and spatial intersection.

## Attachments

Each physical attachment has exactly one owner:

- Production Block attachments are owned through the linked production BlastEvent.
- Contour attachments are owned by the Contour BlastEvent.
- Assessment Area attachments are owned by the Assessment evaluation.

File I/O belongs to infrastructure; ownership policy/workflow belongs to domain/application as appropriate.

## Persistence and transactions

PostgreSQL is the only current database target.

Normal Phase 5B writes are focused. Compatibility whole-state Assessment read/save machinery remains only as transitional debt until #79 Phase 5C.

Required next architecture behavior from #79:

1. Add optimistic concurrency based on a stable Domain version/token rather than the temporary AssessmentWorkspace.
2. Remove normal compatibility whole-state save / `replace_for_domain()` paths after focused writes are protected.
3. Make the transaction/UoW contract capable of atomically touching two Domains for later same-Project entity moves.
4. Remove `AssessmentWorkspace` in Phase 6A if caller audit confirms it is only a persistence container, and give BlastEvent/AssessmentArea direct Domain ownership.
5. Separate stable logical/public IDs from actual ownership FK naming.
6. Remove duplicate legacy engineering/lifecycle persistence after caller classification.

The current development database is disposable. Prefer a clean correct schema to elaborate compatibility for test/dev records, but always express physical schema changes with proper Alembic migrations. Do not use `alembic stamp` as a substitute for schema migration.

## Revision and provenance principles

Historical engineering/assessment data must stay reproducible:

- BlastEvent geometry revisions are immutable historical records.
- Assessment Area geometry revisions are immutable historical records.
- Technical Card revisions preserve the engineering inputs used at that point in time.
- Evaluation revisions preserve completed DAI/FCI results.
- Event/Assessment links preserve exact relevant geometry revision provenance.
- Future configurable engineering catalogue values used in a completed revision should be frozen/snapshotted into that revision when required for reproducibility.

## Analytics readiness

Post-MVP work is expected to analyze accumulated geomechanical, blast-design, execution, geometry, and assessment data and may later include statistical/ML experiments.

The transactional architecture should therefore keep identity, relationships, dates, revision provenance, planned vs actual facts, and stored completed outcomes explicit/queryable.

Do **not** optimize the MVP transactional schema around hypothetical ML. Do not create a feature store or duplicate every JSONB engineering value into relational columns now. Future analytics should use dedicated read projections, SQL/materialized views, or ETL that flatten revisioned data into analysis-ready rows.

A representative future analytical relation is:

```text
geomechanics + blast design + execution
    -> confirmed spatial/event relationship
        -> completed Assessment outcome (DAI, FCI)
```

## Architecture guardrails

`tools/architecture_audit.py` and `tests/test_architecture_boundaries.py` protect important dependency boundaries.
Architecture PRs should reduce transitional allowlists rather than add new exceptions without justification.

Before architecture freeze for MVP:

- complete #79 Phase 5C/6/7;
- resolve remaining known DXF-version-sensitive test debt separately from unrelated work;
- verify PostgreSQL from a clean database;
- verify Windows/Python 3.12 behavior;
- update README/current docs;
- remove proven dead shims/compatibility paths.

After Phase 7, freeze architecture until after MVP release except for defects that block release correctness.


## Phase 6A — COMPLETE

AssessmentWorkspace was audited as a persistence-only container and removed. The physical ownership path is now `Site -> Domain -> BlastBlock / BlastEvent / AssessmentArea`; BlastEvent and AssessmentArea use a real integer `domain_id` foreign key. Stable public persistence identifiers are separately named `logical_id`. Child revisions retain ownership through their parent. ProjectLinesDataset remains Site-owned and shared by all Site Domains. Phase 6B legacy-engineering classification is next. Domain moves from #75 are not implemented.
