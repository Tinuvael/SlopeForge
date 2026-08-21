# Final-wall assessment product model

This document describes the implemented MVP model for SlopeForge final-wall assessment. Current code and tests remain authoritative.

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

A production BlastEvent is itself the user-facing Block. The Block page provides the Production engineering workflow.

Do not count the Block presentation and its production BlastEvent as two independent blasts in dashboards/reports.

### Contour

A Contour BlastEvent opens the Contour Blast page.
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

## Assessment geometry

The editor uses one continuous boundary drawing operation with CAD/GIS-style
snapping and tracing along Project Lines. A user can mix frozen traced spans
with explicit straight connectors and then close and validate the boundary. This
supports horizontal, sloping, interrupted, curved, wedge-shaped, and irregular
simple boundaries without a separate upper/lower selection workflow.

The canonical boundary is an ordered set of `ProjectLineSpan` and
`StraightConnector` segments. A traced span stores its source dataset and line
identity, anchors, and frozen XYZ path. A connector stores explicit user-created
geometry. The derived polygon supports rendering and spatial linking but does
not replace the revision's source provenance.

Creation follows General information → Boundary → Review → Save. Editing an
existing boundary creates a focused geometry revision without duplicating Area
metadata editing. Elevation Interval is a deterministic presentation summary,
not a constraint that flattens stored geometry.

## Linked BlastEvents

An Assessment Area can have multiple linked BlastEvents and one BlastEvent can be related to multiple Areas.

Links preserve provenance and state such as suggested/confirmed/excluded and automatic/manual according to the existing model.

For later workflow status, only confirmed links with the qualifying completed current Assessment should contribute to an `Assessed` Blast status; suggested links are not equivalent to confirmed engineering relationships.

The Linked events page includes a spatial preview without changing link semantics.

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
Production BlastEvent (shown as Block)
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
