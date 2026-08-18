---
name: pyqt-widgets
description: >-
  Implement or refactor SlopeForge PySide6 Qt Widgets UI. Use for QWidget,
  dialogs, forms, tables, trees, stacked pages, layouts, signals, ownership,
  keyboard behavior, read-only states, and widget lifecycle work.
metadata:
  upstream: https://github.com/CodeAtCode/oss-ai-skills/tree/master/frameworks/pyqt/widgets
  upstream_commit: 0a74c3b43c0d637062db3e1e9d5287eea08122b5
  upstream_license: GPL-3.0
  adaptation: SlopeForge PySide6/Qt Widgets implementation profile
---

# PyQt / PySide6 Widgets — SlopeForge profile

Use this skill when implementing UI after the product/layout intent is clear.
For visual/UX decisions, also load `qt-ui-design`. For QSS/theme work, also
load `pyqt-styling`.

`AGENTS.md`, the current issue, and current production behavior override generic
widget examples.

## Framework boundary

- Use PySide6 / Qt Widgets.
- Do not introduce QML/Qt Quick, PyQt as a runtime dependency, web components,
  or another GUI framework.
- Keep domain/business calculations out of widgets.
- UI calls application/services/repositories through the existing architecture;
  do not move persistence logic into pages/dialogs for convenience.

## Layout rules

Prefer Qt layouts and size policies over manual coordinates:

```python
layout = QVBoxLayout(parent)
layout.setContentsMargins(12, 12, 12, 12)
layout.setSpacing(8)
layout.addWidget(content)
```

Avoid `setGeometry()` for normal production layout. Fixed dimensions are
acceptable only when the control genuinely has fixed semantics (for example a
compact icon button), not as a substitute for layout design.

Use:

- `QVBoxLayout` / `QHBoxLayout` for normal composition;
- `QGridLayout` for compact aligned metadata or engineering inputs;
- `QFormLayout` only when it produces a compact readable form;
- `QSplitter` when users benefit from adjustable neighboring panes;
- `QScrollArea` only when content can legitimately exceed the viewport;
- `QStackedWidget` for mutually exclusive pages, with explicit lifetime policy.

## QStackedWidget and page lifetime

SlopeForge must not accumulate abandoned transient pages during navigation.

When replacing a transient page:

1. remove the old page from the stack;
2. disconnect external signals where required;
3. clear application references to the page;
4. call `deleteLater()` when ownership is complete;
5. keep persistent pages only when persistence is intentional and bounded.

Add regression coverage for repeated navigation when touching page replacement
or lifecycle code.

## QObject ownership and signals

- Give widgets a clear QObject parent whenever practical.
- Avoid parentless long-lived widgets/dialogs unless ownership is explicit.
- Do not connect the same signal repeatedly during refresh/rebuild.
- Avoid lambdas that accidentally keep dead pages alive.
- Do not call methods on widgets after `deleteLater()`/destruction.
- Prefer one explicit signal connection path over reconnecting on every refresh.
- Preserve existing transaction/save boundaries; a signal is not a reason to
  save partial state unexpectedly.

## Forms and engineering inputs

- Keep labels short and aligned.
- Keep numeric fields compact; use appropriate `QSpinBox` / `QDoubleSpinBox`
  ranges, decimals, suffixes, and validators.
- Preserve units beside values.
- Do not duplicate derived engineering outputs as independently editable fields.
- Read-only/archive/viewer states must disable mutation without making values
  difficult to read or copy.
- Cancel must not persist edits.

## Tables, lists, and trees

- Use row selection for entity lists unless cell-level editing is the task.
- Keep columns focused on information users actually need.
- Hide internal PKs and implementation-only IDs from normal UI.
- Stable user-facing logical IDs may be shown where the product requires them.
- Use deterministic sorting where order matters.
- Keep project-tree Horizon and Interval nodes virtual; do not create persistence
  entities merely to simplify a widget model.
- Search/filter UI should not alter canonical data.

## Dialogs

- Use clear English titles and action labels in source UI.
- Primary save/confirm action and Cancel should be visually and behaviorally
  conventional.
- Escape should cancel/dismiss when safe.
- Destructive actions need explicit wording and confirmation where appropriate.
- Do not hide validation failures; keep the dialog open and show actionable
  feedback.
- Reuse shared dialog/button/footer patterns instead of inventing a new layout
  for each entity.

## Keyboard and focus

- Ensure sensible tab order.
- Set default buttons only where Enter cannot trigger an unsafe action.
- Preserve shortcuts already used by the application.
- Do not make mouse hover the only way to discover or invoke an action.
- Focus should move predictably after add/remove operations.

## Resize and DPI behavior

- Test typical desktop widths and high-DPI scaling.
- Prefer `QSizePolicy` and stretch factors over hardcoded wide sizes.
- Avoid text clipping in English and translated strings.
- Do not make icon-only controls so small that they are difficult to target.

## SlopeForge product invariants to preserve

- Production Block is `BlastEvent(event_type='production')` in persistence and
  opens the Block page.
- Contour Blast is `BlastEvent(event_type='contour')` and has no Geomechanics.
- Assessment geometry is revisioned.
- DAI and FCI remain separate; X = FCI and Y = DAI.
- Project Lines are Project/Site-wide, not Domain-owned.
- Technical Card calculations and revision semantics are not UI cleanup scope.
- Each physical attachment has one owner.

## Validation after widget changes

Run focused Qt tests plus the repository checks from `AGENTS.md`. For broad UI,
navigation, or lifecycle changes, also run:

```bash
QT_QPA_PLATFORM=offscreen pytest -q
```

Treat new Qt runtime warnings, deleted-object callbacks, duplicate connections,
and unbounded page growth as defects rather than suppressing them.

## Upstream reference

Adapted from the `pyqt-widgets` skill in CodeAtCode/oss-ai-skills:
https://github.com/CodeAtCode/oss-ai-skills/tree/master/frameworks/pyqt/widgets
