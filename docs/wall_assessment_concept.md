# Final-wall assessment product model

This document captures the stable product intent for SlopeForge final-wall assessment. It is not a migration diary.
For unfinished implementation details, the active GitHub issue is authoritative after verifying current `main`.

## Purpose

SlopeForge should accumulate a reproducible engineering history that connects:

- Project Lines / final-wall reference geometry;
- rock-mass / geomechanical inputs;
- blast design;
- actual execution;
- BlastEvent geometry and revisions;
- final-wall Assessment Areas and geometry revisions;
- completed DAI / FCI assessment results;
- photos, documents, notes, and audit/history.

After MVP, this accumulated database should support empirical/statistical analysis of what blast/geomechanical conditions are associated with better or worse wall outcomes and may later support ML experiments. The MVP itself does not implement automated recommendations or ML.

## Product hierarchy

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

Internal `Site` is the user-facing Project/Quarry. Legacy `Mine` is not normal UI terminology.

Horizon and Elevation Interval are virtual groups, not persistent business entities.

## Project Lines

Project Lines are reference geometry for the whole Project/Site and are shared by every Domain.

Multiple datasets may exist historically; one dataset is active for current work.
Historical Assessment geometry must remain reproducible after a new dataset is imported or activated.

Project Lines are managed from the Project dashboard, not as a separate tree branch.

Supported import currently includes Datamine CSV and supported straight DXF polyline entities through the existing geometry import infrastructure.

## BlastEvent

There is one BlastEvent concept with two types:

- `production`;
- `contour`.

### Production

A production BlastEvent is linked 1:1 with a BlastBlock. The Block page is the normal user-facing page and provides the Production engineering workflow.

Do not count the linked Block and BlastEvent as two independent blasts in dashboards/reports.

### Contour

A Contour BlastEvent has no BlastBlock and opens the Contour Blast page.
It has Blast design, Execution fact, Photos, Documents, and History, but no Geomechanics tab under the current product model.

## Blast geometry revisions

BlastEvent geometry is revisioned. Reimporting geometry creates a new revision rather than silently overwriting the old one.

Historical Assessment links should preserve the exact BlastEvent geometry revision that was relevant when the link was confirmed/stored.

## Technical Card

The revisioned BlastEvent Technical Card is the canonical active engineering record.

Production uses:

- Geomechanics;
- Blast design;
- Execution fact.

Contour uses:

- Blast design;
- Execution fact.

Do not redesign existing proven calculations as incidental UI cleanup.

Open issues #77 and #78 define the planned simplification of Geomechanics and the composable borehole charge builder. They should be implemented only after architecture issue #79 classifies/removes duplicate legacy engineering persistence.

## Assessment Area

An Assessment Area is a stable final-wall assessment object within a Domain.
More than one Assessment Area may exist on the same physical wall/bench, and spatial overlap is not inherently forbidden.

Assessment geometry is revisioned. Boundary changes create a new geometry revision; previous revisions remain historical records.

The user-facing page target is:

```text
Assessment Area
├── Overview
├── Assessment
├── Linked events
├── Photos
├── Documents
└── History
```

Issue #71 merges Assessment inputs and the live Result matrix into one Assessment page while preserving the existing scoring model.

## Assessment geometry: current implementation vs target

### Current `main`

The currently implemented creation flow is still based on a user selection polygon, horizontal Project-Line candidates, scalar lower/upper elevations, and a derived final polygon between selected horizontal fragments.

That workflow is a known limitation and should not be treated as the final product model.

### Target model — issue #80

The replacement is a single continuous boundary drawing operation with CAD/GIS-style snapping/tracing to Project Lines.

Core interaction:

1. Click on/near a Project Line.
2. The point snaps and that line becomes the active trace line.
3. Move along it; the preview follows the actual Project Line geometry, not a straight chord.
4. Click to commit the traced span.
5. Move away to create an explicit straight connector.
6. Click another Project Line to snap/switch the active trace source.
7. Continue mixing traced spans and free connectors.
8. Press **Close boundary** to close and validate the Assessment Area.

This one workflow must support:

- parallel upper/lower lines;
- sloping/non-horizontal Project Lines;
- interrupted source lines with explicit gap connectors;
- curved source lines;
- triangular/wedge Areas;
- general irregular simple polygons.

There is no separate "select upper boundary, then lower boundary" workflow.

### Canonical target geometry representation

The engineering definition should preserve an ordered closed Assessment boundary made from generic segments, conceptually:

```text
AssessmentBoundary
└── segments[]
    ├── ProjectLineSpan
    └── StraightConnector
```

A `ProjectLineSpan` preserves:

- source Project Lines dataset;
- source line stable identity/provenance;
- start/end anchors;
- frozen traced XYZ geometry between the anchors.

A `StraightConnector` preserves explicit user-created geometry between boundary points and must not pretend to be Project Line source geometry.

A frozen/derived plan polygon remains useful for:

- map rendering;
- spatial BlastEvent linking;
- dashboards;
- future spatial/statistical analysis.

The polygon is therefore a derived representation of the ordered boundary, not the only historical engineering definition.

For non-horizontal source geometry, preserve real Z variation. Elevation Interval shown in the tree/read model can be derived as a deterministic summary/range; it must not force the stored geometry back into horizontal slices.

## Assessment creation target

Issue #70 should be built after #65, #79, and #80.

Target creation flow:

```text
General information
-> Boundary
-> Review
-> Save
```

Do not add a separate upper/lower/horizon-selection step.

Editing boundaries on an existing Area is a focused geometry-revision workflow and should not duplicate metadata editing for Area name/Domain.

## Linked BlastEvents

An Assessment Area can have multiple linked BlastEvents and one BlastEvent can be related to multiple Areas.

Links preserve provenance and state such as suggested/confirmed/excluded and automatic/manual according to the existing model.

For later workflow status, only confirmed links with the qualifying completed current Assessment should contribute to an `Assessed` Blast status; suggested links are not equivalent to confirmed engineering relationships.

The target inline spatial preview for Linked events is tracked separately in issue #72 and must not change link semantics.

## Assessment scoring

The current scoring model is correct and should not be redesigned during MVP cleanup.

- DAI = Design Achievement Index.
- FCI = Face Condition Index.
- They are separate indices.
- Quadrant X = FCI.
- Quadrant Y = DAI.
- Do not average DAI and FCI into a single score.
- Completed stored evaluation results are historical facts used by dashboards/read models.

## Attachments

Attachment ownership is intentionally singular:

```text
Production Block
-> linked production BlastEvent
-> Photos / Documents

Contour BlastEvent
-> Photos / Documents

Assessment Area
-> Assessment evaluation
-> Photos / Documents
```

One physical attachment must not be duplicated across owners merely for presentation convenience.

## Historical reproducibility

A later user should be able to answer questions such as:

- Which Project Lines dataset defined this Assessment Area revision?
- Which exact Project-Line spans/connectors formed its boundary?
- Which BlastEvent geometry revision was linked?
- What geomechanical/blast-design values were stored at that time?
- What was actually executed?
- Which Assessment revision was completed and what DAI/FCI were stored?

Reimports, new active datasets, later catalogue edits, metadata moves, and UI changes must not silently mutate historical completed engineering records.

## Analytics direction after MVP

The intended analysis chain is approximately:

```text
Project / Domain context
+ geomechanics
+ blast design
+ execution facts
+ geometry / event-link provenance
-> completed final-wall outcome (DAI, FCI)
```

The transactional MVP should preserve these facts cleanly but should not include a feature store, ML model, AI recommendation system, or advanced analytical schema yet.

Later work can create read-side projections/views/ETL that flatten revisioned data into analysis-ready observations while leaving the operational revision model intact.