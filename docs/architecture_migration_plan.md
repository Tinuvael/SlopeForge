# Architecture migration plan

This is the short current migration map for SlopeForge. Historical completed phases are kept in Git history rather than repeated here.

The live architecture gate is GitHub issue #79. If this document and #79 differ, inspect current `main` and use the issue scope for the implementation PR.

## Completed

- Phase 3 complete: `prototype_2d` removed after active domain/geometry/import/attachment responsibilities were extracted.
- Phase 4 complete: important workflows moved from Qt UI into application use cases/services.
- Phase 5A complete: relational Assessment graph synchronization preserves existing workspace/entity/revision DB rows instead of replace-delete-recreate behavior.
- Phase 5B complete: ordinary UI/application writes are focused operations.
- Phase 5C complete: Domain owns optimistic concurrency; focused commands use an
  expected-version CAS, normal whole-state Assessment writes are gone, and a
  deterministic multi-Domain transaction guard is ready for future #75 work. Domain
  moves are not implemented. The aggregate repository is now read-only and permanent
  AST/signature ratchets prevent the removed writer or optional version contracts from
  returning.

## Remaining architecture sequence

### Phase 5C — COMPLETE

Goals:

- add optimistic concurrency on a stable Domain version/token;
- return/propagate expected version through edit sessions/commands;
- fail stale edits with an application conflict error rather than raw SQLAlchemy failure;
- increment the version once per successful logical command;
- make the UoW/transaction contract capable of atomically checking two Domains for future same-Project entity moves;
- remove ordinary compatibility whole-state save APIs and production `replace_for_domain*` callers;
- keep whole-state read mapping only where it still has real value;
- strengthen architecture ratchets against reintroducing whole-state writes.

Do not put the concurrency token on `AssessmentWorkspace`; that container is targeted for removal in Phase 6A.

### Phase 6A — ownership/schema cleanup

After 5C:

- audit `AssessmentWorkspace` callers;
- remove it if it is only a transitional persistence container;
- give BlastEvent and AssessmentArea explicit direct Domain ownership;
- keep stable logical/public IDs distinct from relational ownership FKs;
- rename misleading `domain_id` columns where they actually store logical/public IDs;
- keep revision rows parent-owned unless a direct ownership FK is required for a real invariant/index;
- preserve Project Lines at Project/Site scope;
- preserve Production BlastEvent ↔ BlastBlock semantics;
- preserve geometry/Technical Card/evaluation revision histories and one-owner attachments.

The development database is disposable, so prefer the clean target schema over compatibility complexity for current test records. Still use proper Alembic migrations and keep one Alembic head.

### Phase 6B — COMPLETE: duplicate legacy engineering/schema classification

Before implementing the large Geomechanics/Blast design redesigns (#77/#78), classify current legacy-looking persistence paths using actual callers/tests/migrations/packaging evidence.

Explicitly audit at least:

- `RockMassProfile`;
- `RockStructure`;
- `BlastDesign`;
- `DrillingPattern`;
- `ChargeSegment`;
- old `ExplosiveType`;
- legacy Mine paths;
- old attachment ownership paths;
- duplicated lifecycle/status/date persistence.

If a path has no normal production responsibility, remove it rather than wiring new UI back to it.
The revisioned BlastEvent Technical Card remains the canonical engineering record unless a separate product decision explicitly changes that.

### Phase 7 — NEXT: normalization and architecture freeze

After schema cleanup:

- move remaining active DB/repository/service/report/widget modules to canonical paths where the move has practical value;
- remove shims, dead compatibility, unused imports, and misleading names;
- reduce architecture-audit allowlists;
- resolve the known DXF-version-sensitive test debt as its own focused work;
- update current docs/README;
- verify a clean PostgreSQL database through migrations;
- run full tests and Windows/Python 3.12 manual checks;
- freeze architecture until after MVP release.

## Core prerequisites around architecture

Architecture work is not the only MVP gate:

- #65 must fix Project Lines fidelity before new Assessment geometry relies on imported lines.
- #80 defines the generalized Project-Line snapping/tracing Assessment boundary model.
- #70 creation UX must be built after #65/#79/#80 so it is not implemented twice.

## Work that should wait for the architecture gate

- #75 persistence-heavy Domain moves should follow Phase 5C/6A.
- #77/#78 should follow Phase 6B classification to avoid reviving duplicate engineering persistence.
- broad UI polish can proceed only where it does not depend on unstable ownership/persistence contracts.

## Non-negotiable invariants during migration

Do not change as collateral architecture cleanup:

- Technical Card engineering formulas;
- DAI/FCI scoring or quadrant semantics;
- Project Lines Project/Site ownership;
- one physical attachment owner;
- Production/Contour BlastEvent product model;
- revision-history semantics;
- stored completed Assessment result semantics;
- report semantics unless the dedicated report issue changes them.

## Post-MVP analytics readiness

The cleanup should preserve a future analytical chain without adding an ML subsystem now:

```text
geomechanical inputs
+ blast design
+ execution facts
+ exact geometry/link provenance
-> completed Assessment DAI / FCI
```

Keep stable identity, revision timestamps/authors, planned vs actual facts, exact linked revisions, and historical engineering inputs reproducible. Later analytics can flatten this through read projections/views/ETL rather than distorting the transactional MVP schema.

## Validation for architecture PRs

At minimum:

```bash
pytest <targeted tests>
python tools/architecture_audit.py
python -m compileall app application domain infrastructure database repositories services ui widgets
git diff --check
QT_QPA_PLATFORM=offscreen pytest -q
```

Schema/persistence work also requires PostgreSQL integration tests against an explicitly isolated `TEST_DATABASE_URL` and Alembic checks from a clean database.


## Phase 6A — COMPLETE

AssessmentWorkspace was audited as a persistence-only container and removed. The physical ownership path is now `Site -> Domain -> BlastBlock / BlastEvent / AssessmentArea`; BlastEvent and AssessmentArea use a real integer `domain_id` foreign key. Stable public persistence identifiers are separately named `logical_id`. Child revisions retain ownership through their parent. ProjectLinesDataset remains Site-owned and shared by all Site Domains. Phase 6B legacy-engineering classification is next. Domain moves from #75 are not implemented.


## Phase 6B — COMPLETE

The production caller audit classified the parallel RockMassProfile/RockStructure/BlastDesign/DrillingPattern/ChargeSegment/BlastExecution/WallAssessment graph, its Lithology and old ExplosiveType support tables, and the old directly Block-owned Attachment path as DEAD. They were removed in Alembic 0011. Revisioned BlastEvent Technical Card persistence is the sole canonical engineering path, while AssessmentEntityAttachment remains the canonical one-owner attachment path. Mine is retained as ACTIVE_BUT_MISPLACED because current Project/Site creation and read paths still require it. BlastBlock status and planned date remain ACTIVE pending #75. No #78A explosive catalogue was implemented. Phase 7 is next; #79 remains open.
