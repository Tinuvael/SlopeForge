---
name: pyqt-styling
description: >-
  Style SlopeForge PySide6 Qt Widgets with QSS and shared visual tokens. Use for
  colors, spacing, borders, control states, tables, forms, tabs, dialogs,
  status treatments, focus/disabled/read-only styling, and theme consistency.
metadata:
  upstream: https://github.com/CodeAtCode/oss-ai-skills/tree/master/frameworks/pyqt/styling
  upstream_commit: 18c1bc4132a371a0476bc9925f5875403fb60ef5
  upstream_license: GPL-3.0
  adaptation: SlopeForge QSS/design-system profile
---

# PyQt / PySide6 Styling — SlopeForge profile

Use this skill for QSS/theme implementation. Also load `qt-ui-design` for UX
and visual hierarchy decisions, and `pyqt-widgets` when widget structure or
layout changes.

The existing SlopeForge style direction and `AGENTS.md` override generic QSS
examples.

## SlopeForge visual baseline

The active UI should look like compact professional engineering desktop
software:

- light neutral application background;
- white/light content surfaces;
- subtle neutral borders and separators;
- restrained blue interactive accent;
- compact spacing and control heights;
- limited border radius;
- minimal or no shadows;
- no decorative gradients, glass effects, or animation;
- existing SlopeForge SVG icon family;
- clear readable focus, disabled, viewer, archive, warning, and error states.

Do not turn SlopeForge into a web/mobile card dashboard.

## Centralize style authority

Before adding QSS:

1. inspect existing shared style/theme helpers;
2. reuse existing semantic properties/tokens where possible;
3. extend the shared system instead of adding page-specific raw hex values;
4. remove duplicate style fragments only when caller audit shows replacement is
   safe.

Prefer semantic roles such as:

```text
surface
surface_muted
border
text_primary
text_secondary
interactive
interactive_hover
selection
warning
error
success
read_only
archived
```

The exact implementation may be Python constants, QSS generation, dynamic
properties, or existing project helpers. Do not create a second competing theme
system merely to satisfy this skill.

## QSS selectors

Prefer type selectors for truly global behavior and dynamic properties for
semantic variants:

```python
button.setProperty("role", "primary")
button.style().unpolish(button)
button.style().polish(button)
```

```css
QPushButton[role="primary"] { /* shared primary treatment */ }
QPushButton[role="danger"]  { /* destructive treatment */ }
```

Use `objectName` selectors only for genuinely unique controls. Avoid long chains
of page-specific selectors that make style behavior impossible to reason about.

## Do not overuse global selectors

Broad selectors such as `QWidget { ... }` can unintentionally restyle child
controls, dialogs, menus, plot canvases, and third-party widgets. Keep global
rules minimal and verify all major active pages after changing them.

When a style change is local, scope it through a stable parent object name or
semantic property rather than relying on fragile widget nesting.

## Control-state completeness

For interactive controls, consider at least:

- normal;
- hover;
- pressed;
- focus;
- checked/selected where applicable;
- disabled;
- read-only where distinct from disabled.

Do not remove native focus indication without adding an obvious replacement.
Disabled/read-only values must remain legible; grey-on-grey low-contrast text is
not acceptable for engineering data users still need to inspect.

## Forms

- Keep input borders subtle and consistent.
- Use one normal control height family rather than page-specific heights.
- Use compact horizontal padding.
- Do not make every field look like a large rounded web input.
- Validation should use a semantic error treatment plus text/tooltips, not color
  alone.
- Unit labels and secondary metadata should be visually quieter than editable
  values without becoming unreadable.

## Buttons and actions

Use a small hierarchy:

- primary: one principal action in a group;
- secondary: normal supporting action;
- tertiary/tool: low-emphasis toolbar/icon action;
- danger: destructive action, used sparingly.

Do not make every action blue. Decorative blue surfaces must not look clickable.
Archive/Restore should communicate actual action/state, not just color.

## Cards and panels

Cards are for meaningful grouping, not decoration.

- white/light surface;
- subtle 1 px border where separation is needed;
- restrained radius;
- compact internal padding;
- no stacked/nested cards without a clear information hierarchy reason;
- no large shadows.

If a simple layout/separator is clearer than another card, use the simpler
structure.

## Tables, lists, and trees

- Keep row height compact but readable.
- Use restrained selection highlight with adequate text contrast.
- Distinguish hover from selection.
- Avoid heavy grid lines; use subtle separators where useful.
- Header hierarchy must be clear without oversized bold text.
- Archived/read-only entities should remain readable and identifiable.
- Do not use color alone to represent assessment/problem states.

## Tabs and navigation

- Keep tabs compact and consistent across Block, Contour Blast, and Assessment
  Area.
- Selected state must be obvious without relying only on blue text.
- Avoid page-specific tab styles.
- Do not introduce excessive rounded pill navigation unless it already belongs
  to the established design system.

## Icons

- Reuse repository SlopeForge SVG assets.
- Preserve consistent icon size and alignment.
- Prefer text + icon for important actions when meaning is not obvious.
- Do not import a second unrelated icon library for isolated convenience.
- Directional/status icons should remain understandable in disabled/read-only
  states.

## Localization and resizing

- Never bake user-visible text into images.
- Leave enough room for translated strings.
- Avoid QSS fixed widths on text-bearing controls unless required by a compact
  product pattern and tested with localization.
- Verify high DPI and normal Windows scaling.

## Anti-patterns

Do not:

- paste large page-local `setStyleSheet()` blocks into every widget;
- use random hex colors independently across pages;
- use QSS as a substitute for fixing bad layout structure;
- force dimensions globally that clip localized text;
- add gradients, glossy effects, heavy shadows, or decorative motion;
- hide focus borders because they look less clean;
- style viewer/read-only controls so faintly that values cannot be read;
- restyle engineering plots/graphics accidentally through global selectors.

## Validation

After shared QSS/theme changes, inspect at minimum:

- Main window/header/tree;
- Project and Domain pages;
- Production Block;
- Contour Blast;
- Assessment Area;
- dialogs/forms;
- tables/lists;
- archived and viewer/read-only states.

Run relevant Qt tests and the standard repository checks in `AGENTS.md`.

## Upstream reference

Adapted from the `pyqt-styling` skill in CodeAtCode/oss-ai-skills:
https://github.com/CodeAtCode/oss-ai-skills/tree/master/frameworks/pyqt/styling
