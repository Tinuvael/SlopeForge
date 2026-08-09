# MVP legacy/prototype audit

## Classification

### Active

- `ui/main_window.py`, `widgets/project_tree.py`, entity pages, dashboards, and the focused assessment-area geometry page are normal navigation.
- `prototype_2d/technical_card.py`, `wall_assessment.py`, `geometry.py`, `blast_geometry.py`, event-link, attachment, CSV, Project Lines, and BlastEvent services are proven domain/business algorithms. Their package name is historical; moving them would add risk without improving the UI architecture.

### Active but previously misplaced

The active attachment manager, Technical Card editor, assessment evaluation editor, plan view, geometry import dialog, and workspace-based geometry controller were moved from `ui/prototype_2d` into `ui/dialogs`, `ui/editors`, and `ui/widgets`. Normal entity pages no longer import `ui.prototype_2d`.

### Compatibility-only

- `ui/pages/assessment_workspace_page.py` and `ui/widgets/assessment_workspace.py` provide the minimum controller used by the focused create/edit boundary workflow. The standalone workspace is not exposed by normal navigation.
- `ui/prototype_2d/blast_event_window.py` remains for old prototype tests/tools. Production navigation does not import it.
- Legacy database `Mine` and `repositories/attachment_repository.py` remain for schema/repository compatibility. They are not exposed in normal UI and Block attachments no longer use the legacy owner.

### Dead

- `ui/pages/navigation_pages.py`: obsolete duplicate dashboards; deleted.
- The placeholder `ui/pages/block_page.py`: deleted and replaced by the real entity page formerly named `BlockListPage`.

## Remaining prototype references

Remaining references from active UI point only to proven domain services and data/geometry models. The only remaining `ui.prototype_2d` imports are inside compatibility tests/tools around `blast_event_window.py`; normal pages contain none.

## Schema impact

No schema migration is needed. The legacy attachment table was not removed because unrelated compatibility repositories still exercise it. A clean development database is not required.
