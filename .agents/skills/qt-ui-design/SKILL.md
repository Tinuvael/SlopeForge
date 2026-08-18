---
name: qt-ui-design
description: >-
  Design or audit SlopeForge Qt/PySide6 desktop UI. Use for screens, layouts,
  navigation, information hierarchy, interaction patterns, usability reviews,
  accessibility, and visual consistency decisions before or during UI changes.
metadata:
  upstream: https://github.com/TheQtCompanyRnD/agent-skills/tree/main/skills/qt-ui-design
  upstream_commit: 0f107d12c10b88091c36ee644cbd6290eaacc917
  upstream_license: LicenseRef-Qt-Commercial OR BSD-3-Clause
  adaptation: SlopeForge PySide6/Qt Widgets desktop profile
---

# Qt UI Design — SlopeForge profile

This repo-local skill adapts the Qt Company `qt-ui-design` guidance to the
actual SlopeForge product. Repository instructions in `AGENTS.md` and the
current issue/PR always take precedence over generic examples in this skill.

## Fixed project context

Do not ask for information that is already established here:

- Target: Windows-first desktop engineering application, Python 3.12.
- UI framework: PySide6 / Qt Widgets. Do not migrate to QML, Qt Quick, web UI,
  Electron, or another toolkit.
- Primary input: mouse + keyboard. Preserve complete keyboard access and sane
  focus order.
- Source/default UI language: English. Russian is localization data.
- Product density: compact professional engineering desktop software, not a
  mobile/web dashboard.
- Visual language: light background, white cards/panels, subtle neutral
  borders, restrained blue accent, existing SlopeForge SVG icons, minimal
  shadows, no decorative gradients or animation.

## Before changing an existing screen

1. Inspect the current implementation and nearby reusable widgets/styles.
2. Identify the screen's primary task and the information users need first.
3. Preserve working interaction and domain behavior unless the issue explicitly
   changes it.
4. Prefer reuse and incremental normalization over replacing a working screen
   with a new bespoke widget hierarchy.
5. For broad UI work, compare Project, Domain, Block, Contour Blast, and
   Assessment Area so the result belongs to one application.

## Information hierarchy

- Put the entity identity, Project/Domain context, archive/read-only state, and
  primary action at the top.
- Keep primary engineering content visible without forcing users through
  decorative cards or unnecessary dialogs.
- Use progressive disclosure for secondary metadata and advanced actions.
- Group related content by proximity and shared container treatment.
- Do not create duplicate summaries of the same engineering data merely to fill
  space.
- Prefer one clear primary action per action group. Destructive actions must be
  visually secondary and confirmed when irreversible.

## Desktop layout rules

- Use layouts and size policies; avoid fixed geometry.
- Design for normal desktop resizing and high DPI. Do not assume one exact
  resolution.
- Keep forms compact. Avoid kilometre-wide label/input rows and giant empty
  vertical stretches.
- Use whitespace to separate concepts, not to mimic a marketing website.
- Tables/lists are appropriate for dense operational data when they improve
  scanning; dashboards should not become spreadsheet dumps.
- Scroll only when content genuinely exceeds a normal viewport; do not create
  scrolling because of oversized cards or spacing.

## Interaction and accessibility

- Every interactive control must be reachable by keyboard where practical.
- Tab order follows visual reading order.
- Escape should close dismissible dialogs/popovers without losing already saved
  state.
- Never remove visible focus feedback without an equivalent replacement.
- Do not rely on color alone for archive, warning, error, selected, or completed
  states; pair it with text/icon/shape.
- Preserve readable contrast and disabled/read-only legibility.
- Long operations need visible feedback; do not freeze the UI silently.

## SlopeForge-specific review checklist

For a UI design/audit, explicitly check:

- Does it use canonical terms: Project, Domain, Blast event, Production,
  Contour blast, Block, Assessment area, Project Lines, Horizon, Interval?
- Does it accidentally expose `Mine`, `Assessment Workspace`, prototype terms,
  database IDs, or internal implementation names?
- Does Production still present as Block while being persisted by a production
  BlastEvent?
- Does Contour remain free of Geomechanics?
- Are DAI and FCI shown separately where relevant?
- Are archived/viewer states clearly read-only?
- Are existing SlopeForge SVG icons reused instead of introducing an unrelated
  icon family?
- Is the screen compact enough for engineering desktop use?
- Is there any needless visual novelty: gradients, glass effects, giant rounded
  cards, heavy shadows, decorative animation?

## Audit severity

Classify findings as:

- `Critical`: broken workflow, inaccessible control, misleading engineering
  meaning, unsafe/destructive action, or severe state ambiguity.
- `Warning`: inconsistent hierarchy, excessive cognitive load, poor focus/order,
  weak resize behavior, or substantial visual inconsistency.
- `Opportunity`: polish/reuse improvements that do not block the workflow.

## Upstream reference

Adapted from The Qt Company R&D `qt-ui-design` agent skill:
https://github.com/TheQtCompanyRnD/agent-skills/tree/main/skills/qt-ui-design

When this local profile is insufficient for a specialized Qt design question,
consult the upstream skill/reference, but do not import QML-specific patterns
into SlopeForge unless the product architecture is explicitly changed.
