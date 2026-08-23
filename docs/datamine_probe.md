# Datamine DM/DMX discovery notes

This document records verified source schemas observed through the Datamine `DmFile.DmTable` API during #143 discovery. It is an implementation note, not a guarantee that every Datamine file uses exactly these fields.

## Verified Studio RM string sample

Observed fields:

- `XP`, `YP`, `ZP` — coordinates;
- `PTN` — point order inside one string;
- `PVALUE` — grouping value separating distinct strings in the verified sample;
- `LSTYLE`, `SYMBOL`, `COLOUR` — source presentation attributes.

In the sample, `PTN` restarted at `1` when `PVALUE` changed, confirming `PVALUE` as the practical string identity for that file. If an explicit `SID` field is present in another source file, the importer prefers `SID` and retains `PVALUE` as source metadata.

## Verified Studio RM wireframe pair

Normal file-pair naming observed:

- `XXtr.dmx` — triangle/topology records;
- `XXpt.dmx` — point records.

Triangle fields observed:

- `PID1`, `PID2`, `PID3`;
- `TRIANGLE`;
- `COLOUR`;
- `LINK`;
- `LSTYLE`;
- `SYMBOL`.

Point fields observed:

- `XP`, `YP`, `ZP`;
- `PID`.

The future surface adapter should reconstruct triangles by resolving `PID1/PID2/PID3` against `PID -> XYZ`, while preserving per-triangle colour and other source attributes.

`DefaultDatamineFormat` returned no value for the tested DMX files and must remain optional diagnostic metadata rather than a format discriminator.
