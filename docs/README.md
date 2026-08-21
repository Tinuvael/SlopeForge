# SlopeForge documentation

This folder contains the current maintained engineering/development documentation.
Git history preserves old migration snapshots; current docs should not intentionally keep contradictory historical states.

## Maintained documents

- `architecture.md` — current architecture, ownership boundaries, persistence/revision principles, and MVP target state.
- `database_setup.md` — PostgreSQL/Alembic setup and integration-test safety.
- `wall_assessment_concept.md` — stable final-wall assessment product model and the implemented Assessment geometry and scoring model.
- `release_checklist.md` — consolidated Windows/manual/localization/release-candidate checks.

## Source-of-truth rule

For implementation work use this order:

1. current `main` code/schema/tests;
2. the active GitHub issue/PR scope;
3. repository `AGENTS.md` invariants;
4. these documents.

Do not implement a historical behavior from documentation when current code/issues explicitly supersede it.

## Removed historical documents

Older one-off schema/audit/manual-checklist files were removed from the maintained set once they became misleading or duplicated the consolidated documents. They remain available through Git history if historical investigation is needed.
