# SlopeForge Qt Widgets style guide

SlopeForge uses a compact, light Windows engineering-desktop language. The Project and
Domain dashboards and entity Overview pages are the visual reference. Use white surfaces,
subtle borders, a restrained blue accent, dense layouts, existing SVG icons, and no
gradients, heavy shadows, decorative motion, or nested cards without a real grouping need.

## Shared foundation

`ui/theme.py` owns semantic colours, the 4/8/12/16 spacing rhythm, and conservative
application QSS. `ui/widgets/design_system.py` owns `CardFrame`, `set_button_role`, and
`set_status_role`. Prefer these APIs over page-local hexadecimal colours or full widget
stylesheets. Object names describe typography/surfaces; dynamic properties describe state.

- Surfaces: app `#f4f6f9`, card `#ffffff`, subtle `#f8fafc`, border `#d7dde6`.
- Text: primary `#111827`, secondary `#374151`, muted `#6b7280`.
- Interaction: accent `#1261a0`, hover `#0b4f86`, selected `#eaf3ff`, focus `#0b63ce`.
- Semantic: success, warning, error, and disabled tokens are defined by meaning in `Color`.
- Spacing: 4 px micro gap, 8 px normal gap, 12 px section gap, 16 px large separation.
  Pages normally use 10 px outer margins; cards use 14 × 12 px padding and 7 px radii.

Use the system font. `EntityTitle` is the page/entity title, `CardTitle`/`SectionTitle` is a
section heading, normal labels carry values, and `MutedText` carries metadata or hints.

## Components

- **Cards:** instantiate `CardFrame`; avoid local borders and cards inside cards.
- **Buttons:** call `set_button_role(button, "primary"|"secondary"|"link"|"danger")`.
  Use one primary action per action group. Navigation in card headers is `link`.
- **Entity tabs:** use `create_entity_tabs()`. They are a text navigation row with an active
  underline; do not change `EntityTabWidget` sizing and geometry safeguards.
- **Badges:** keep visible status text and call `set_status_role`. Workflow state determines
  the semantic role; Assessment quadrant colours are a separate engineering scale.
- **Rows:** use `StandardRow` (or the established dashboard row names), compact padding, and
  a subtle selected background/accent. Keyboard focus must remain separately visible.
- **Forms:** align labels consistently and keep controls compact. Keep native spin-box
  subcontrols: Windows arrow hit rectangles must never be altered by broad QSS.
- **Dialogs:** provide a clear title, optional short description, simple surface/form content,
  and a right-aligned action row with one primary action and a secondary Cancel.
- **States:** use `MutedText` for empty/read-only context, semantic badges for archived/stale
  state, and semantic warning/error text without hiding details.

## DPI, resizing, and localisation

Use layouts and size policies rather than fixed content geometry. Check 1920×1080 and
approximately 1366×768, plus Windows 100%, 125%, and 150% scaling where available. Allow
labels and buttons to grow for Russian strings that can be 30–40% longer than English;
prefer word wrap for descriptions and avoid fragile fixed widths. Preserve keyboard focus,
Enter/Escape behavior, and mouse hit targets.

```python
card = CardFrame("Blast design")
set_button_role(save_button, "primary")
set_button_role(history_button, "link")
set_status_role(status_label, "warning")
```
