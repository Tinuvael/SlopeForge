# SlopeForge 1 schema snapshot

These files are frozen source components of the single Alembic revision `1`.
They preserve the exact pre-release schema operations that previously lived in
the disposable development migration chain.

They are **not** independent Alembic revisions because they live outside
`alembic/versions`. `alembic/versions/0001_slopeforge_1.py` executes them in
schema dependency order for upgrade and reverse order for downgrade.

After the SlopeForge 1.0 release this snapshot is immutable. Future physical
schema changes must append normal Alembic revisions after revision `1`; do not
edit these files to evolve a production database.
